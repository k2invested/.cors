"""execution_engine.py — live gap execution and branch dispatch.

This module owns the per-gap execution machinery used inside the turn loop:

  gap -> resolve refs -> route by vocab -> execute -> emit/commit -> record

The turn loop remains responsible for:
  - turn setup
  - first step / identity bootstrap
  - synthesis
  - heartbeat persistence
  - saving trajectory

This module is the execution core for iteration-time branch handling.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from compile import ChainState, GovernorSignal, is_mutate, is_observe
import manifest_engine as me
import note_engine
from step import Chain, Epistemic, Gap, Step, StepNote
from system.chain_registry import public_chain_ref_map, render_public_chain_registry
from system.control_surface import render_admin_surface, render_system_control_surface
from tools import st_builder as st_builder_module
from system.tool_contract import ToolContract, load_tool_contract
from system.tool_registry import public_tool_ref_map, render_public_tool_registry
from skills.loader import load_all
from vocab_registry import FOUNDATIONAL_BRIDGE_POST_OBSERVE, find_vocab_for_tool_ref, get_vocab, render_configurable_vocab_registry


@dataclass
class ExecutionHooks:
    resolve_all_refs: Callable[[list[str], list[str], Any], str]
    execute_tool: Callable[[str, dict], tuple[str, int]]
    auto_commit: Callable[..., tuple[str | None, str | None]]
    parse_step_output: Callable[..., tuple[Step, list[Gap]]]
    extract_json: Callable[[str], dict | None]
    extract_command: Callable[[str], str | None]
    extract_written_path: Callable[[str], str | None]
    is_reprogramme_intent: Callable[[dict | None], bool]
    load_tree_policy: Callable[[], dict]
    match_policy: Callable[[str, dict], dict | None]
    resolve_entity: Callable[[list[str], Any, Any], str | None]
    render_step_network: Callable[[Any], str]
    emit_reason_skill: Callable[[Any, Gap, Step, str], Step]
    git: Callable[[list[str], str | None], str]
    commit_assessment: Callable[[str], list[str]]
    step_assessment: Callable[[dict | None, dict | None, str | None], list[str]]
    run_isolated_workflow: Callable[..., dict[str, Any]] = field(
        default=lambda ref, **kwargs: {"status": "missing", "activation_ref": ref}
    )
    queue_background_completion: Callable[[dict[str, Any]], None] = field(
        default=lambda payload: None
    )
    render_session_context: Callable[[Any, Any, str, str | None, str | None], str] = field(
        default=lambda trajectory, registry, user_message, active_chain_id=None, active_gap=None: ""
    )


@dataclass
class ExecutionConfig:
    cors_root: Path
    chains_dir: Path
    tool_map: dict[str, dict]
    deterministic_vocab: set[str]
    observation_only_vocab: set[str]
    session_message: str = ""


@dataclass
class ExecutionOutcome:
    control: str = "continue"
    step_result: Step | None = None


def _compact_line(text: str, limit: int = 220) -> str:
    line = " ".join(str(text).strip().split())
    if len(line) <= limit:
        return line
    return line[: limit - 3].rstrip() + "..."


def _canonical_workflow_ref(ref: str | None) -> str | None:
    if not isinstance(ref, str):
        return None
    candidate = ref.strip()
    if not candidate:
        return None
    match = re.fullmatch(r"[A-Za-z0-9_.-]+:([0-9a-f]{12,64})", candidate)
    if match:
        return match.group(1)
    return candidate


def _extract_reason_activation_intent(raw: str, hooks: ExecutionHooks) -> dict[str, Any] | None:
    data = hooks.extract_json(raw)
    if not isinstance(data, dict) or "gaps" in data:
        return None
    activate_ref = data.get("activate_ref")
    activate_ref = _canonical_workflow_ref(activate_ref)
    if not activate_ref:
        return None
    prompt = data.get("prompt")
    if prompt is not None and not isinstance(prompt, str):
        return None
    await_needed = data.get("await_needed")
    if not isinstance(await_needed, bool):
        return None
    content_refs = data.get("content_refs")
    if content_refs is None:
        content_refs = []
    if not isinstance(content_refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in content_refs):
        return None
    step_refs = data.get("step_refs")
    if step_refs is None:
        step_refs = []
    if not isinstance(step_refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in step_refs):
        return None
    note = StepNote.from_dict(data.get("note"))
    return {
        "activate_ref": activate_ref,
        "prompt": prompt.strip() if isinstance(prompt, str) and prompt.strip() else None,
        "await_needed": await_needed,
        "content_refs": [ref.strip() for ref in content_refs if ref.strip()],
        "step_refs": [ref.strip() for ref in step_refs if ref.strip()],
        "note": note,
    }


def _reason_controller_prompt(gap: Gap) -> str:
    return (
        f"Reason over the current semantic tree for gap:{gap.hash} \"{gap.desc}\".\n"
        "Treat the injected trajectory, active chain, and persisted step notes as your historical progress while processing the user's message.\n"
        "Reason over the step trajectory and semantic tree first.\n"
        "Treat resolved files and hashes as already-observed evidence that has been summarized into the chain; do not reframe the task as raw file review unless a fresh observation gap is actually needed.\n"
        "Use the accumulated step notes to compare, contrast, detect drift, and decide whether a targeted edit or follow-on abstraction is required.\n"
        "Choose the next abstraction required in the current turn.\n"
        "Always include a top-level `note` object in your JSON so the reasoning step persists its judgment.\n"
        "Use this note shape:\n"
        '{"note":{"summary":"...","salient_observations":["..."],"material_points":["..."],"deltas":["..."],"relations":[{"type":"supports|conflicts|depends_on|updates|aliases|references","from_ref":"...","to_ref":"...","note":"..."}],"drift":["..."],"mutation_implications":["..."],"open_questions":["..."]},"gaps":[...]}\n'
        "If a child workflow should run, you may respond with JSON only in this shape:\n"
        '{"note":{"summary":"...","salient_observations":["..."],"material_points":["..."],"deltas":["..."],"relations":[{"type":"supports|conflicts|depends_on|updates|aliases|references","from_ref":"...","to_ref":"...","note":"..."}],"drift":["..."],"mutation_implications":["..."],"open_questions":["..."]},"activate_ref":"<workflow-hash>","prompt":"task for the child workflow","await_needed":true,"content_refs":["relevant content hash or path"],"step_refs":["relevant step hash"]}\n'
        "or the same shape with await_needed=false.\n"
        "Use only public workflow hashes.\n"
        "- If judgment and existing context are enough, emit the next clarified gap(s) or no gaps.\n"
        "- Prefer reasoning from the existing chain and note structure over surfacing another observation gap when the needed evidence is already present in the semantic tree.\n"
        "- Use the note as your explicit reasoning record: summarize what mattered, what drift exists or does not exist, and what edit or no-edit decision follows from the evidence.\n"
        "- Use the step note as a real reasoning artifact, not a post-hoc summary. If your note surfaces drift, tension, open questions, or mutation implications that are not fully resolved by the current evidence, you should ideally emit concrete gap(s) to address them.\n"
        "- Do not close with no gaps while leaving your own note in a state that still implies unresolved comparison work, untested contradiction, or a plausible edit target. Either resolve those concerns explicitly in the note, or surface the next gap(s) needed to address them.\n"
        "- When concluding that no edit is needed, the note should explicitly reconcile or dismiss the strongest earlier drift candidates from the referenced step notes rather than merely restating a no-edit result.\n"
        "- Use reason_needed for structural ambiguity, competing interpretations, semantic boundary crossing, and deciding the next concrete abstraction.\n"
        "- tool_needed, vocab_reg_needed, and clarify_needed may only be surfaced through reason_needed.\n"
        "- reprogramme_needed may only be surfaced when semantic persistence into entity/admin state is already warranted; it edits semantic profile state only and should not be used for delete, remove, unlink, move, or rename operations.\n"
        "- hash_edit_needed is for in-place content edits only; do not use it for delete, remove, unlink, move, or rename operations.\n"
        "- For deletion, removal, move, or other shell-level destructive workspace operations, prefer bash_needed rather than hash_edit_needed or reprogramme_needed.\n"
        "- Use clarify_needed only for genuinely user-only blockers after available semantic context is exhausted.\n"
        "- If a tool or workflow should exist but does not yet, emit the concrete creation or edit gap(s) needed to make that happen.\n"
        "Keep reasoning stateful and current-turn; do not defer by scheduling background work unless background execution is actually required."
    )


def _render_public_tool_registry(cors_root: Path) -> str:
    return render_public_tool_registry(cors_root)


def _merge_dedupe_refs(*groups: list[str] | tuple[str, ...] | None) -> list[str]:
    refs: list[str] = []
    for group in groups:
        if not group:
            continue
        for ref in group:
            if isinstance(ref, str) and ref and ref not in refs:
                refs.append(ref)
    return refs


def _step_ref_content_refs(step_refs: list[str], trajectory: Any) -> list[str]:
    carried: list[str] = []
    for ref in step_refs:
        if not isinstance(ref, str):
            continue
        candidate = ref.strip()
        if candidate.startswith("step:"):
            candidate = candidate.split(":", 1)[1].strip()
        if not candidate:
            continue
        step = trajectory.resolve(candidate)
        if not step:
            continue
        carried = _merge_dedupe_refs(carried, step.content_refs)
    return carried


def _resolve_step_ref(step_ref: str, trajectory: Any) -> Step | None:
    if not isinstance(step_ref, str):
        return None
    candidate = step_ref.strip()
    if candidate.startswith("step:"):
        candidate = candidate.split(":", 1)[1].strip()
    if not candidate:
        return None
    return trajectory.resolve(candidate)


def _render_step_note_summary(step_ref: str, trajectory: Any) -> str | None:
    step = _resolve_step_ref(step_ref, trajectory)
    if step is None:
        return None
    note = step.effective_note()
    lines = [f"step:{step.hash} {_compact_line(step.desc, 160)}"]
    if note.summary:
        lines.append(f"note.summary: {_compact_line(note.summary, 200)}")
    if note.drift:
        lines.append(f"note.drift: {_compact_line(note.drift[0], 200)}")
    if note.mutation_implications:
        lines.append(f"note.mutation: {_compact_line(note.mutation_implications[0], 200)}")
    if step.commit:
        lines.append(f"commit: {step.commit}")
    if step.content_refs:
        lines.append(f"content_refs: {step.content_refs[:4]}")
    return "\n".join(lines)


def _referenced_resolved_chain(gap: Gap, trajectory: Any) -> Chain | None:
    if not gap.step_refs or len(gap.step_refs) < 2:
        return None
    resolved_steps: list[Step] = []
    for step_ref in gap.step_refs:
        step = _resolve_step_ref(step_ref, trajectory)
        if step is None or not step.chain_id:
            return None
        resolved_steps.append(step)
    chain_ids = {step.chain_id for step in resolved_steps if step.chain_id}
    if len(chain_ids) != 1:
        return None
    chain = trajectory.chains.get(next(iter(chain_ids)))
    if chain is None or not chain.resolved:
        return None
    if not all(step.hash in chain.steps for step in resolved_steps):
        return None
    return chain


def _render_reason_context(gap: Gap, *, trajectory: Any, hooks: ExecutionHooks, registry: Any) -> str:
    blocks: list[str] = []

    direct_content = hooks.resolve_all_refs([], gap.content_refs, trajectory)
    if direct_content:
        blocks.append(f"## Current Gap Resolved Content\n{direct_content}")

    referenced_chain = _referenced_resolved_chain(gap, trajectory)
    if referenced_chain is not None:
        blocks.append(
            "## Referenced Child Chain\n"
            f"{trajectory.render_chain(referenced_chain.hash, registry=registry, mode='full')}"
        )
    else:
        step_blocks: list[str] = []
        for step_ref in gap.step_refs:
            rendered = _render_step_note_summary(step_ref, trajectory)
            if rendered:
                step_blocks.append(rendered)
        if step_blocks:
            blocks.append("## Referenced Step Notes\n" + "\n\n".join(step_blocks))

    return "\n\n".join(blocks)


def _render_note_for_injection(note: StepNote, *, title: str) -> str:
    lines = [title]
    if note.summary:
        lines.append(f"summary: {_compact_line(note.summary, 400)}")
    for label, items in (
        ("salient_observations", note.salient_observations[:4]),
        ("material_points", note.material_points[:5]),
        ("deltas", note.deltas[:4]),
        ("drift", note.drift[:4]),
        ("mutation_implications", note.mutation_implications[:4]),
        ("open_questions", note.open_questions[:3]),
    ):
        if not items:
            continue
        lines.append(f"{label}:")
        for item in items:
            lines.append(f"- {_compact_line(item, 300)}")
    if note.relations:
        lines.append("relations:")
        for relation in note.relations[:4]:
            relation_line = (
                f"- {relation.type}: {relation.from_ref} -> {relation.to_ref}"
                + (f" | {_compact_line(relation.note, 220)}" if relation.note else "")
            )
            lines.append(relation_line)
    return "\n".join(lines)


def _generate_pre_step_note(
    *,
    gap: Gap,
    note_context: str,
) -> StepNote | None:
    if not isinstance(note_context, str) or not note_context.strip():
        return None
    return note_engine.generate_step_note(
        gap_desc=gap.desc,
        resolved_data=note_context,
        step_refs=list(gap.step_refs or []),
        content_refs=list(gap.content_refs or []),
    )


def _attach_note(step_result: Step | None, note: StepNote | None) -> Step | None:
    if step_result is None or note is None or step_result.note is not None:
        return step_result
    step_result.note = note
    return step_result


def _attach_generated_note(
    step_result: Step | None,
    *,
    gap: Gap,
    resolved_data: str,
) -> Step | None:
    if step_result is None or step_result.note is not None:
        return step_result
    note = note_engine.generate_step_note(
        gap_desc=gap.desc,
        resolved_data=resolved_data,
        step_refs=list(gap.step_refs or []),
        content_refs=list(gap.content_refs or []),
    )
    if note is not None:
        step_result.note = note
    return step_result


def _public_tool_path_for_ref(tool_ref: str | None, cors_root: Path) -> str | None:
    if not isinstance(tool_ref, str) or not tool_ref:
        return None
    return public_tool_ref_map(cors_root).get(tool_ref)


def _resolve_workflow_skill(registry: Any, activate_ref: str, cors_root: Path) -> Any | None:
    activate_ref = _canonical_workflow_ref(activate_ref) or activate_ref
    skill = registry.resolve(activate_ref)
    if skill is not None:
        return skill
    chain_path = public_chain_ref_map(cors_root).get(activate_ref)
    if not chain_path:
        return None
    expected_source = str((cors_root / chain_path).resolve())
    for candidate in getattr(registry, "by_hash", {}).values():
        if str(Path(candidate.source).resolve()) == expected_source:
            return candidate
    return None


def _direct_tool_ref_from_gap(gap: Gap, cors_root: Path) -> str | None:
    if gap.route_mode == "tool_ref_direct":
        for ref in gap.content_refs:
            if _public_tool_path_for_ref(ref, cors_root):
                return ref
    if gap.vocab:
        return None
    for ref in gap.content_refs:
        if _public_tool_path_for_ref(ref, cors_root):
            return ref
    return None


def _tool_input_surface(tool_path: str, cors_root: Path) -> str:
    path = cors_root / tool_path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'"""(.*?)"""', text, re.S)
    if not match:
        return ""
    doc = match.group(1).strip()
    if not doc:
        return ""
    return doc[:1600]


def _compose_direct_tool_prompt(*, gap: Gap, tool_ref: str, tool_path: str, contract: ToolContract, cors_root: Path) -> str:
    doc_surface = _tool_input_surface(tool_path, cors_root)
    prompt = (
        f"Compose JSON params for public tool {tool_path} (ref={tool_ref}) to resolve this gap:\n"
        f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
        f"Tool contract: mode={contract.mode} scope={contract.scope} post_observe={contract.post_observe}\n"
        "Return JSON params only. Use supported input keys only. Infer concrete params from the resolved context when possible.\n"
    )
    if doc_surface:
        prompt += f"\nTool interface:\n{doc_surface}\n"
    return prompt


def _record_step(step_result: Step, *, entry: Any, trajectory: Any, compiler: Any) -> None:
    if step_result.chain_id:
        trajectory.append(step_result)
        compiler.add_step_to_chain(step_result.hash, chain_id=step_result.chain_id)
        print(f"  step:{step_result.hash}" + (f" commit:{step_result.commit}" if step_result.commit else ""))
        return

    passive_appended = False
    for ref in step_result.content_refs:
        passive_chains = trajectory.find_passive_chains(ref)
        for pc in passive_chains:
            if pc.hash != (entry.chain_id if entry else None):
                trajectory.append_to_passive_chain(pc.hash, step_result)
                passive_appended = True
                print(f"  → appended to passive chain:{_chain_log_label(pc)}")
                break
        if passive_appended:
            break

    if not passive_appended:
        trajectory.append(step_result)
    compiler.add_step_to_chain(step_result.hash)
    print(f"  step:{step_result.hash}" + (f" commit:{step_result.commit}" if step_result.commit else ""))


def _chain_log_label(chain: Any | None) -> str:
    if chain is None:
        return "unknown"
    return str(getattr(chain, "hash", "unknown"))[:8]


def _post_observe_resolution(
    *,
    vocab: str | None,
    tool_conf: dict | Any,
    commit_sha: str | None,
    runtime_refs: list[str] | None,
    hooks: ExecutionHooks,
    config: ExecutionConfig,
) -> tuple[list[str], str] | tuple[None, None]:
    post_observe = tool_conf.get("post_observe") if isinstance(tool_conf, dict) else None
    if isinstance(post_observe, str) and post_observe.endswith(".log"):
        return [post_observe], f"observe {post_observe}: {post_observe}"
    if runtime_refs:
        return runtime_refs, f"observe artifacts: {', '.join(runtime_refs)}"
    if post_observe and commit_sha:
        tree_files = hooks.git(["ls-tree", "-r", "--name-only", commit_sha, post_observe], str(config.cors_root))
        targeted_refs = [f"{commit_sha}:{f}" for f in tree_files.split("\n") if f.strip()]
        return targeted_refs or [commit_sha], f"observe {post_observe}: {', '.join(targeted_refs or [commit_sha])}"
    if commit_sha:
        return [commit_sha], f"observe commit:{commit_sha}"
    return None, None


def _bridge_reintegration_target(
    *,
    vocab: str | None,
    written_path: str | None,
    commit_sha: str | None,
) -> tuple[list[str], str] | tuple[None, None]:
    next_vocab = FOUNDATIONAL_BRIDGE_POST_OBSERVE.get(vocab or "")
    if next_vocab != "reason_needed":
        return None, None
    refs = [written_path] if isinstance(written_path, str) and written_path else ([commit_sha] if commit_sha else [])
    if not refs:
        return None, None
    subject = written_path or f"commit:{commit_sha}"
    return refs, f"reintegrate {subject} after {vocab}"


def _dedupe_refs(refs: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for ref in refs:
        candidate = str(ref).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _collect_contract_artifact_refs(
    *,
    contract: ToolContract | None,
    intent: dict | None,
    output: str,
    hooks: ExecutionHooks,
) -> tuple[list[str], str | None]:
    refs: list[str] = []
    runtime_commit: str | None = None
    try:
        data = hooks.extract_json(output)
    except Exception:
        data = None
    if isinstance(data, dict):
        commit = data.get("commit")
        if isinstance(commit, str) and commit.strip():
            runtime_commit = commit.strip()
        if contract and contract.runtime_artifact_key:
            artifact_value = data.get(contract.runtime_artifact_key)
            if isinstance(artifact_value, str) and artifact_value.strip():
                refs.append(artifact_value.strip())
            elif isinstance(artifact_value, list):
                refs.extend(str(item).strip() for item in artifact_value if isinstance(item, str) and item.strip())

    written_path = hooks.extract_written_path(output)
    if written_path:
        refs.append(written_path)

    if contract and isinstance(intent, dict):
        for key in contract.artifact_params:
            value = intent.get(key)
            if isinstance(value, str) and value.strip():
                refs.append(value.strip())
            elif isinstance(value, list):
                refs.extend(str(item).strip() for item in value if isinstance(item, str) and item.strip())

    if contract:
        refs.extend(contract.default_artifacts)

    refs = _dedupe_refs(refs)
    return refs, runtime_commit


def _normalize_command_target_path(path: str, cors_root: Path) -> str | None:
    candidate = str(path).strip()
    if not candidate or candidate.startswith("-") or candidate.startswith("$"):
        return None
    try:
        parsed = Path(candidate)
        if parsed.is_absolute():
            parsed = parsed.resolve().relative_to(cors_root.resolve())
        normalized = str(parsed).replace("\\", "/").lstrip("./")
    except (ValueError, OSError):
        normalized = candidate.replace("\\", "/").lstrip("./")
    if not normalized or normalized in {".", ".."}:
        return None
    return normalized


def _infer_bash_commit_paths(intent: dict | None, cors_root: Path) -> list[str]:
    if not isinstance(intent, dict):
        return []
    commands: list[str] = []
    single = intent.get("command")
    if isinstance(single, str) and single.strip():
        commands.append(single.strip())
    multi = intent.get("commands")
    if isinstance(multi, list):
        commands.extend(str(item).strip() for item in multi if isinstance(item, str) and item.strip())

    inferred: list[str] = []
    seen: set[str] = set()
    for command in commands:
        for segment in re.split(r"\s*(?:&&|\|\||;|\|)\s*", command):
            if not segment.strip():
                continue
            try:
                tokens = shlex.split(segment)
            except ValueError:
                continue
            if not tokens:
                continue
            index = 0
            while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith(("/", "./", "../")):
                index += 1
            if index >= len(tokens):
                continue
            command_name = Path(tokens[index]).name
            operands = [tok for tok in tokens[index + 1 :] if tok and not tok.startswith("-")]
            if command_name not in {"rm", "unlink", "rmdir", "mv", "cp", "touch", "mkdir", "install", "ln"}:
                continue
            for operand in operands:
                normalized = _normalize_command_target_path(operand, cors_root)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                inferred.append(normalized)
    return inferred


def _mutate_tool_compose_prompt(*, vocab: str, gap: Gap, tool_path: str, contract: ToolContract | None) -> str:
    if vocab == "bash_needed":
        return (
            f"Compose params for {tool_path} to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Respond with JSON params for code_exec.py:\n"
            f'{{"command": "..."}}\n'
            f"Or:\n"
            f'{{"commands": ["step 1", "step 2"]}}\n\n'
            f"This is macOS. Use python3 one-liners for JSON edits, not sed."
        )
    if vocab == "email_needed":
        return (
            f"Compose params for {tool_path} to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Respond with JSON params for email_send.py:\n"
            f'{{"to": "recipient@example.com", "subject": "subject", "body": "message body", "attachment": "optional/relative/path"}}\n\n'
            f"If a default recipient should be used, you may omit `to`."
        )
    if vocab == "git_revert_needed":
        return (
            f"Compose params for {tool_path} to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Respond with JSON params for git_ops.py. Allowed shapes:\n"
            f'{{"action": "revert", "ref": "<commit hash>", "message": "optional"}}\n'
            f'{{"action": "checkout", "ref": "<commit hash>", "path": "relative/file/path"}}\n'
            f'{{"action": "commit", "message": "commit message", "paths": ["optional/path"]}}'
        )
    if vocab == "stitch_needed":
        return (
            f"Compose params for {tool_path} to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Respond with JSON params for stitch_generate.py:\n"
            f'{{"prompt": "UI description", "device": "MOBILE|DESKTOP|TABLET|AGNOSTIC", "project": "optional", "variant_mode": "optional"}}'
        )
    if vocab == "json_patch_needed":
        return (
            f"Compose a JSON file edit to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Respond with JSON params for hash_manifest.py:\n"
            f'{{"action": "patch", "path": "relative/file.json", "patch": {{"old": "exact JSON text to replace", "new": "replacement JSON text"}}}}\n\n'
            f"Use the EXACT current file content for the `old` field. Do not guess."
        )
    if contract:
        return (
            f"Compose params for {tool_path} to resolve this gap:\n"
            f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
            f"Tool contract: mode={contract.mode} scope={contract.scope} post_observe={contract.post_observe}\n"
            f"Respond with JSON params only."
        )
    return (
        f"Compose params for {tool_path} to resolve this gap:\n"
        f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
        f"Respond with JSON params only."
    )


def _make_rogue_step(
    *,
    desc: str,
    reference_step: Step,
    gap: Gap,
    chain_id: str | None,
    rogue_kind: str,
    failure_source: str,
    failure_detail: str | None = None,
    commit: str | None = None,
    assessment: list[str] | None = None,
) -> Step:
    return Step.create(
        desc=desc,
        step_refs=[reference_step.hash],
        content_refs=gap.content_refs,
        commit=commit,
        chain_id=chain_id,
        parent=reference_step.hash,
        rogue=True,
        rogue_kind=rogue_kind,
        failure_source=failure_source,
        failure_detail=failure_detail,
        assessment=assessment or [],
    )


def _make_failure_attempt_step(
    *,
    origin_step: Step,
    gap: Gap,
    chain_id: str | None,
    failure_source: str,
    failure_detail: str | None = None,
) -> Step:
    assessment = [f"failure_source: {failure_source}"]
    if failure_detail:
        first_line = failure_detail.strip().splitlines()[0]
        if first_line:
            assessment.append(f"failure_detail: {first_line[:200]}")
    return Step.create(
        desc=f"failed attempt: {gap.desc}",
        step_refs=[origin_step.hash],
        content_refs=gap.content_refs,
        chain_id=chain_id,
        assessment=assessment,
    )


def _debug_activation_payload(
    *,
    registry: Any,
    origin_step: Step,
    rogue_step: Step,
    gap: Gap,
    rogue_kind: str,
    failure_source: str,
    failure_detail: str | None = None,
) -> dict[str, Any] | None:
    debug_skill = registry.resolve_by_name("debug")
    if debug_skill is None:
        return None
    if debug_skill.hash in gap.content_refs or debug_skill.hash in origin_step.content_refs or debug_skill.hash in rogue_step.content_refs:
        return None
    content_refs = _merge_dedupe_refs(gap.content_refs, rogue_step.content_refs)
    step_refs = _merge_dedupe_refs([origin_step.hash], rogue_step.step_refs, [rogue_step.hash])
    prompt = (
        f"Debug execution failure. rogue_kind={rogue_kind}; source={failure_source}; "
        f"original_gap={gap.hash} \"{gap.desc}\"."
    )
    if failure_detail:
        first_line = failure_detail.strip().splitlines()[0]
        if first_line:
            prompt += f" failure_detail={first_line[:300]}"
    return {
        "activate_ref": debug_skill.hash,
        "task_prompt": prompt,
        "content_refs": content_refs,
        "step_refs": step_refs,
        "await_policy": "none",
        "store_kind": "background_agent",
    }


def _auto_activate_debug_for_rogue(
    *,
    registry: Any,
    origin_step: Step,
    rogue_step: Step,
    gap: Gap,
    chain_id: str | None,
    rogue_kind: str,
    failure_source: str,
    failure_detail: str | None,
    trajectory: Any,
    hooks: ExecutionHooks,
    compiler: Any,
    session: Any,
) -> None:
    activation = _debug_activation_payload(
        registry=registry,
        origin_step=origin_step,
        rogue_step=rogue_step,
        gap=gap,
        rogue_kind=rogue_kind,
        failure_source=failure_source,
        failure_detail=failure_detail,
    )
    if not activation:
        return
    activate_ref = activation["activate_ref"]
    run_kwargs = {
        "task_prompt": activation["task_prompt"],
        "store_kind": activation["store_kind"],
        "await_policy": activation["await_policy"],
        "content_refs": activation["content_refs"],
        "step_refs": activation["step_refs"],
    }
    activation_context = hooks.resolve_all_refs(
        activation["step_refs"],
        activation["content_refs"],
        trajectory,
    )
    if activation_context:
        run_kwargs["activation_context"] = activation_context
    child_result = hooks.run_isolated_workflow(activate_ref, **run_kwargs)
    if chain_id:
        compiler.record_background_trigger(
            chain_id,
            refs=[activate_ref] + activation["content_refs"] + activation["step_refs"],
            activation_ref=activate_ref,
            await_policy=activation["await_policy"],
            store_kind=activation["store_kind"],
            parent_step=origin_step.hash,
        )
    session.inject(
        "## Auto Debug Activation\n"
        f"activation_ref: {activate_ref}\n"
        f"status: {child_result.get('status', 'unknown')}\n"
        f"store_kind: {child_result.get('store_kind', activation['store_kind'])}\n"
        f"task: {activation['task_prompt']}\n"
        f"content_refs: {activation['content_refs']}\n"
        f"step_refs: {activation['step_refs']}"
    )


def _emit_rogue_with_diagnosis(
    *,
    desc: str,
    origin_step: Step,
    gap: Gap,
    chain_id: str | None,
    rogue_kind: str,
    failure_source: str,
    trajectory: Any,
    compiler: Any,
    failure_detail: str | None = None,
    commit: str | None = None,
    assessment: list[str] | None = None,
) -> Step:
    attempt_step = _make_failure_attempt_step(
        origin_step=origin_step,
        gap=gap,
        chain_id=chain_id,
        failure_source=failure_source,
        failure_detail=failure_detail,
    )
    trajectory.append(attempt_step)
    compiler.add_step_to_chain(attempt_step.hash)
    diagnose_gap = Gap.create(
        desc=(
            f"Diagnose rogue step: classify the failure, determine whether state changed or was reverted, "
            f"and choose the next safe correction path for {rogue_kind} from {failure_source}."
        ),
        content_refs=gap.content_refs,
        step_refs=[attempt_step.hash],
    )
    diagnose_gap.scores = Epistemic(relevance=1.0, confidence=0.9, grounded=0.0)
    diagnose_gap.vocab = "reason_needed"
    diagnose_gap.carry_forward = True

    rogue_step = _make_rogue_step(
        desc=desc,
        reference_step=attempt_step,
        gap=gap,
        chain_id=chain_id,
        rogue_kind=rogue_kind,
        failure_source=failure_source,
        failure_detail=failure_detail,
        commit=commit,
        assessment=assessment,
    )
    rogue_step.gaps.append(diagnose_gap)
    trajectory.append(rogue_step)
    compiler.emit(rogue_step)
    compiler.add_step_to_chain(rogue_step.hash)
    return rogue_step


def _extract_invalid_generated_json(output: str) -> dict | None:
    marker = "Generated (invalid):"
    if marker not in output:
        return None
    candidate = output.split(marker, 1)[1].strip()
    if not candidate:
        return None
    decoder = json.JSONDecoder()
    for i, ch in enumerate(candidate):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(candidate[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _policy_drift_assessment(source: str, detail: str | None = None) -> list[str]:
    lines = [
        "policy.status: rejected",
        "policy.drift: true",
        f"policy.source: {source}",
    ]
    if detail:
        lines.append(f"policy.detail: {detail}")
    return lines

def _pattern_tool_params(gap: Gap) -> dict[str, str] | None:
    """Infer file_grep params when pattern_needed provides a concrete search term."""
    pattern = None
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', gap.desc)
    for left, right in quoted:
        candidate = (left or right).strip()
        if candidate:
            pattern = candidate
            break

    path = None
    for ref in gap.content_refs:
        candidate = ref.split(":", 1)[1] if ":" in ref and "/" in ref.split(":", 1)[1] else ref
        if "/" in candidate or candidate.endswith((".st", ".py", ".json", ".md", ".txt", ".yaml", ".yml")):
            path = candidate
            break

    if not pattern:
        return None

    params = {"pattern": pattern}
    if path:
        params["path"] = path
    return params


def _entity_target_for_reprogramme(gap: Gap, registry: Any) -> Any | None:
    requested_name = _explicit_action_name_from_gap(gap)
    for ref in gap.content_refs:
        skill = registry.resolve(ref)
        if skill is not None:
            if requested_name and getattr(skill, "name", None) != requested_name:
                continue
            return skill
    return None


def _new_action_origination_requires_reason(
    gap: Gap,
    *,
    route_mode: str | None,
    target_entity: Any | None,
) -> bool:
    return (
        route_mode == "action_editor"
        and target_entity is None
        and gap.vocab not in {"reason_needed", "reprogramme_needed"}
    )


STRUCTURAL_BOUNDARY_TARGETS = ("skills/actions/", "tools/")
STRUCTURAL_BOUNDARY_MARKERS = (
    "embedding",
    "embed ",
    "block_ref",
    "activation_ref",
    "on_vocab:",
    "public trigger",
    "next_layer_desc",
    "higher-order layer",
    "higher order layer",
)


def _structural_ref_candidate(ref: str) -> str:
    if ":" in ref:
        prefix, suffix = ref.split(":", 1)
        if "/" in suffix or suffix.endswith((".st", ".py", ".json", ".md", ".txt", ".yaml", ".yml")):
            return suffix
    return ref


def _gap_mentions_structural_target(gap: Gap, target: str) -> bool:
    lowered = gap.desc.lower()
    if target in lowered:
        return True
    for ref in gap.content_refs:
        if target in _structural_ref_candidate(str(ref)).lower():
            return True
    return False


def _infer_reason_judgment_route_mode(
    gap: Gap,
    *,
    registry: Any,
    policy: dict,
    target_entity: Any | None,
    route_mode: str | None = None,
) -> str | None:
    if route_mode:
        return route_mode
    if _gap_mentions_structural_target(gap, "tools/"):
        return "action_editor"
    if any(_gap_mentions_structural_target(gap, target) for target in STRUCTURAL_BOUNDARY_TARGETS):
        return "action_editor"
    lowered = gap.desc.lower()
    if any(marker in lowered for marker in STRUCTURAL_BOUNDARY_MARKERS):
        return "action_editor"
    return _determine_reprogramme_mode(gap, target_entity, policy) if (target_entity is not None or ".st" in lowered) else None


def _requires_reason_judgment(
    gap: Gap,
    *,
    registry: Any,
    policy: dict,
    route_mode: str | None,
    target_entity: Any | None,
) -> bool:
    if gap.vocab == "reason_needed":
        return False
    effective_route_mode = _infer_reason_judgment_route_mode(
        gap,
        registry=registry,
        policy=policy,
        target_entity=target_entity,
        route_mode=route_mode,
    )
    lowered = gap.desc.lower()
    if effective_route_mode == "action_editor" and target_entity is None:
        return True
    if any(marker in lowered for marker in STRUCTURAL_BOUNDARY_MARKERS):
        return True
    return any(_gap_mentions_structural_target(gap, target) for target in STRUCTURAL_BOUNDARY_TARGETS)


def _explicit_action_name_from_gap(gap: Gap) -> str | None:
    lowered = gap.desc.lower()
    path_match = re.search(r"skills/actions/([a-z0-9_]+)\.st", lowered)
    if path_match:
        return path_match.group(1)
    file_match = re.search(r"\b([a-z0-9_]+)\.st\b", lowered)
    if file_match:
        return file_match.group(1)
    return None


def _inferred_action_name_from_gap(gap: Gap) -> str:
    lowered = gap.desc.lower()
    explicit_name = _explicit_action_name_from_gap(gap)
    if explicit_name:
        return explicit_name
    trigger_match = re.search(r"triggered by(?: the vocab(?: term)?)? ([a-z_]+)", lowered)
    if trigger_match:
        name = trigger_match.group(1)
        if name.endswith("_needed"):
            return name[:-7]
        return name
    words = re.findall(r"[a-z0-9_]+", lowered)
    for token in words:
        if token in {"workflow", "step", "package", "semantic", "triggered", "research_needed"}:
            continue
        if token.endswith("_needed"):
            return token[:-7]
    return "new_action"


def _target_path_from_gap(gap: Gap) -> str | None:
    lowered = gap.desc.lower()
    match = re.search(r"(skills/actions/[a-z0-9_]+\.st|tools/[a-z0-9_]+\.py)", lowered)
    if match:
        return match.group(1)
    for ref in gap.content_refs:
        candidate = _structural_ref_candidate(str(ref))
        if "/" in candidate and candidate.endswith((".st", ".py")):
            return candidate
    return None


def _assessment_validator_ok(lines: list[str] | None) -> bool:
    if not lines:
        return True
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("validator.status:"):
            return stripped.endswith("ok")
    return True


def _load_json_doc(path: str | None) -> dict | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        return json.loads(candidate.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _restore_written_step(path: str | None, previous_doc: dict | None) -> None:
    if not path:
        return
    candidate = Path(path)
    if previous_doc is None:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass
        return
    try:
        candidate.write_text(json.dumps(previous_doc, indent=2))
    except OSError:
        pass


def _collect_clarify_frontier(compiler: Any, current_gap: Gap, *, current_turn: int | None = None) -> list[Gap]:
    merged: list[Gap] = []
    seen: set[str] = set()
    candidate_gaps = [current_gap]
    for entry in compiler.ledger.active_gaps():
        gap = entry.gap
        if gap.vocab != "clarify_needed":
            continue
        if current_turn is not None and gap.turn_id not in (None, current_turn):
            continue
        candidate_gaps.append(gap)

    for gap in candidate_gaps:
        if gap.hash in seen:
            continue
        seen.add(gap.hash)
        merged.append(gap)
    return merged


def _merged_clarify_desc(gaps: list[Gap]) -> str:
    descs: list[str] = []
    for gap in gaps:
        if gap.desc not in descs:
            descs.append(gap.desc)
    if not descs:
        return "clarification needed"
    if len(descs) == 1:
        return f"clarify frontier: {descs[0]}"
    return "clarify frontier:\n- " + "\n- ".join(descs)


def _build_clarify_frontier_step(
    *,
    origin_step: Step,
    merged_gaps: list[Gap],
    chain_id: str | None,
) -> Step:
    step_refs = list(dict.fromkeys(
        [origin_step.hash] + [ref for gap in merged_gaps for ref in gap.step_refs]
    ))
    content_refs = list(dict.fromkeys(
        ref for gap in merged_gaps for ref in gap.content_refs
    ))
    return Step.create(
        desc=_merged_clarify_desc(merged_gaps),
        step_refs=step_refs,
        content_refs=content_refs,
        gaps=merged_gaps,
        chain_id=chain_id,
    )


def _reprogramme_mode_for_source(path: str | None) -> str | None:
    if not path:
        return None
    source = Path(path)
    if source.name == "admin.st" or "entities" in source.parts:
        return "entity_editor"
    if source.suffix == ".st" and "skills" in source.parts:
        return "action_editor"
    return None


def _determine_reprogramme_mode(gap: Gap, target_entity: Any | None, policy: dict) -> str:
    if gap.route_mode:
        return gap.route_mode
    if target_entity is not None:
        mode = _reprogramme_mode_for_source(getattr(target_entity, "source", None))
        if mode:
            return mode
    for ref in gap.content_refs:
        rule = None
        if isinstance(ref, str):
            if ref in policy:
                rule = policy[ref]
            else:
                best_len = 0
                for prefix, candidate in policy.items():
                    if prefix.endswith("/") and ref.startswith(prefix) and len(prefix) > best_len:
                        rule = candidate
                        best_len = len(prefix)
        if rule and isinstance(rule, dict) and rule.get("reprogramme_mode"):
            return str(rule["reprogramme_mode"])
        mode = _reprogramme_mode_for_source(ref if isinstance(ref, str) else None)
        if mode:
            return mode
    if ".st" in gap.desc.lower() and "entity" not in gap.desc.lower():
        return "action_editor"
    return "entity_editor"


def _sanitize_reason_child_gaps(child_gaps: list[Gap], *, registry: Any, policy: dict) -> int:
    """Keep reason-owned action/workflow authoring out of reprogramme.

    reason_needed may surface reprogramme_needed only for entity-tree persistence.
    If reason tries to hand action/workflow origination or repair to reprogramme,
    rewrite it back to reason_needed so authoring stays under reason ownership.
    """
    rewrites = 0
    for gap in child_gaps:
        if gap.vocab != "reprogramme_needed":
            continue
        target_entity = _entity_target_for_reprogramme(gap, registry)
        route_mode = _determine_reprogramme_mode(gap, target_entity, policy)
        if route_mode != "entity_editor":
            gap.vocab = "reason_needed"
            gap.route_mode = None
            rewrites += 1
    return rewrites


def _coerce_semantic_frame_for_mode(frame: dict | None, route_mode: str) -> dict | None:
    if not isinstance(frame, dict):
        return frame
    if route_mode != "entity_editor":
        return frame

    artifact = dict(frame.get("artifact", {}))
    artifact["kind"] = "entity"
    artifact["protected_kind"] = "entity"
    frame["artifact"] = artifact
    frame.pop("root", None)
    frame.pop("phases", None)
    frame.pop("closure", None)
    return frame


def _system_surface_sections_for_path(path: str | None) -> set[str]:
    if not isinstance(path, str) or not path.strip():
        return set()
    normalized = str(Path(path)).replace("\\", "/").lstrip("./")
    sections: set[str] = set()
    if normalized == "vocab_registry.py":
        sections.add("vocab")
    if normalized == "system/tool_registry.py" or normalized.startswith("tools/"):
        sections.update({"tools", "vocab"})
    if normalized == "system/chain_registry.py" or normalized.startswith("skills/actions/"):
        sections.update({"workflows", "vocab"})
    if normalized.startswith("skills/entities/"):
        sections.add("entities")
    return sections


def _is_entity_admin_surface(path: str | None) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    candidate = Path(path)
    normalized = str(candidate).replace("\\", "/").lstrip("./")
    parts = candidate.parts
    return (
        candidate.name == "admin.st"
        or normalized == "skills/admin.st"
        or ("skills" in parts and "entities" in parts)
        or normalized == "skills/entities"
        or normalized.startswith("skills/entities/")
    )


def _is_destructive_bash_gap(gap: Gap) -> bool:
    if gap.vocab != "bash_needed":
        return False
    text = " ".join([gap.desc] + [ref for ref in gap.content_refs if isinstance(ref, str)]).lower()
    return bool(re.search(r"\b(delete|remove|unlink|rm|move|rename)\b", text))


def _preserve_destructive_bash_on_entity_surface(gap: Gap, policy: dict, target_entity: Any | None = None) -> bool:
    if not _is_destructive_bash_gap(gap):
        return False
    if target_entity is not None and _is_entity_admin_surface(getattr(target_entity, "source", None)):
        return True
    if any(_is_entity_admin_surface(ref) for ref in gap.content_refs if isinstance(ref, str)):
        return True
    if "skills/entities/" in gap.desc.lower() or "skills/admin.st" in gap.desc.lower():
        return True
    for path_prefix in policy:
        if not _is_entity_admin_surface(path_prefix):
            continue
        if path_prefix.rstrip("/").lower() in gap.desc.lower():
            return True
    return False


def _refresh_runtime_control_surfaces(
    *,
    written_path: str | None,
    session: Any,
    config: ExecutionConfig,
) -> None:
    if not isinstance(written_path, str) or not written_path.strip():
        return
    normalized = str(Path(written_path)).replace("\\", "/").lstrip("./")
    registry = load_all(str(config.cors_root / "skills"))
    if normalized == "skills/admin.st":
        admin = registry.resolve_by_name("admin")
        if admin is not None:
            session.inject(f"## Refreshed Admin Surface\n{render_admin_surface(admin, cors_root=config.cors_root)}")
        return
    sections = _system_surface_sections_for_path(normalized)
    if sections:
        session.inject(
            render_system_control_surface(
                registry,
                cors_root=config.cors_root,
                title="## Refreshed System Control Surface",
                sections=sections,
            )
        )


def execute_iteration(
    *,
    entry: Any,
    signal: GovernorSignal,
    session: Any,
    origin_step: Step,
    trajectory: Any,
    compiler: Any,
    registry: Any,
    current_turn: int,
    hooks: ExecutionHooks,
    config: ExecutionConfig,
) -> ExecutionOutcome:
    gap = entry.gap

    if signal == GovernorSignal.REVERT:
        print("  → REVERT: divergence detected, skipping")
        compiler.resolve_current_gap(gap.hash)
        return ExecutionOutcome(control="continue")

    if gap.vocab == "clarify_needed":
        print("  → clarify needed: halting iteration")
        merged_gaps = _collect_clarify_frontier(compiler, gap, current_turn=current_turn)
        clarify_step = _build_clarify_frontier_step(
            origin_step=origin_step,
            merged_gaps=merged_gaps,
            chain_id=entry.chain_id,
        )
        trajectory.append(clarify_step)
        return ExecutionOutcome(control="break", step_result=clarify_step)

    resolved_data = hooks.resolve_all_refs(gap.step_refs, gap.content_refs, trajectory)
    pre_step_note: StepNote | None = None
    vocab = gap.vocab
    direct_tool_ref = _direct_tool_ref_from_gap(gap, config.cors_root)
    if not vocab and direct_tool_ref:
        mapped_vocab = find_vocab_for_tool_ref(direct_tool_ref)
        if mapped_vocab:
            vocab = mapped_vocab
            gap.vocab = mapped_vocab
            direct_tool_ref = None
    step_result: Step | None = None
    session_context_block = hooks.render_session_context(
        trajectory,
        registry,
        config.session_message,
        entry.chain_id if getattr(entry, "chain_id", None) else None,
        gap.hash if gap else None,
    )
    if session_context_block:
        session.inject(session_context_block)

    if not vocab and direct_tool_ref:
        tool_path = _public_tool_path_for_ref(direct_tool_ref, config.cors_root)
        tool_contract = load_tool_contract(config.cors_root / tool_path) if tool_path else None
        if not tool_path or tool_contract is None:
            compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
            step_result = _emit_rogue_with_diagnosis(
                desc=f"FAILED: {gap.desc}",
                origin_step=origin_step,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source="tool_ref_direct",
                trajectory=trajectory,
                compiler=compiler,
                failure_detail=f"unresolved public tool ref: {direct_tool_ref}",
            )
            _auto_activate_debug_for_rogue(
                registry=registry,
                origin_step=origin_step,
                rogue_step=step_result,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source="tool_ref_direct",
                failure_detail=f"unresolved public tool ref: {direct_tool_ref}",
                trajectory=trajectory,
                hooks=hooks,
                compiler=compiler,
                session=session,
            )
            return ExecutionOutcome(control="continue", step_result=step_result)

        print(f"  → direct tool ({tool_contract.mode}) [{direct_tool_ref}]")
        if tool_contract.mode == "mutate" and not compiler.validate_omo("content_needed"):
            print("  → OMO violation: need observation first")

        compose_prompt = _compose_direct_tool_prompt(
            gap=gap,
            tool_ref=direct_tool_ref,
            tool_path=tool_path,
            contract=tool_contract,
            cors_root=config.cors_root,
        )
        raw = session.call(compose_prompt)
        print(f"  LLM compose: {raw[:150]}...")
        intent = hooks.extract_json(raw)
        if not intent:
            compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
            step_result = _emit_rogue_with_diagnosis(
                desc=f"FAILED: {gap.desc}",
                origin_step=origin_step,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=tool_path,
                trajectory=trajectory,
                compiler=compiler,
                failure_detail="no valid JSON params extracted for direct tool execution",
            )
            _auto_activate_debug_for_rogue(
                registry=registry,
                origin_step=origin_step,
                rogue_step=step_result,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=tool_path,
                failure_detail="no valid JSON params extracted for direct tool execution",
                trajectory=trajectory,
                hooks=hooks,
                compiler=compiler,
                session=session,
            )
            return ExecutionOutcome(control="continue", step_result=step_result)

        output, code = hooks.execute_tool(tool_path, intent)
        session.inject(f"## Tool output ({tool_path})\n{output}")
        if code != 0:
            compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
            step_result = _emit_rogue_with_diagnosis(
                desc=f"FAILED: {gap.desc}",
                origin_step=origin_step,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=tool_path,
                trajectory=trajectory,
                compiler=compiler,
                failure_detail=output[:500] if output else None,
            )
            _auto_activate_debug_for_rogue(
                registry=registry,
                origin_step=origin_step,
                rogue_step=step_result,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=tool_path,
                failure_detail=output[:500] if output else None,
                trajectory=trajectory,
                hooks=hooks,
                compiler=compiler,
                session=session,
            )
            return ExecutionOutcome(control="continue", step_result=step_result)

        runtime_refs, runtime_commit = _collect_contract_artifact_refs(
            contract=tool_contract,
            intent=intent,
            output=output,
            hooks=hooks,
        )
        if tool_contract.mode == "observe":
            observe_context_parts: list[str] = []
            if resolved_data:
                observe_context_parts.append(f"## Resolved data\n{resolved_data}")
            if output:
                observe_context_parts.append(f"## Tool output ({tool_path})\n{output}")
            pre_step_note = _generate_pre_step_note(
                gap=gap,
                note_context="\n\n".join(observe_context_parts),
            )
            if pre_step_note is not None:
                session.inject(_render_note_for_injection(pre_step_note, title=f"## Pre-step note for gap:{gap.hash}"))
            raw = session.call(f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps.")
            print(f"  LLM: {raw[:150]}...")
            step_result, child_gaps = hooks.parse_step_output(
                raw,
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            step_result = _attach_note(step_result, pre_step_note)
            if step_result is not None and step_result.note is None and resolved_data:
                step_result = _attach_generated_note(step_result, gap=gap, resolved_data=resolved_data)
            compiler.record_execution("hash_resolve_needed", False)
            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)
        else:
            written_path = hooks.extract_written_path(output)
            if not written_path:
                for ref in runtime_refs:
                    if "/" in ref or "." in Path(ref).name:
                        written_path = ref
                        break
            commit_sha = runtime_commit
            on_reject = None
            if not commit_sha:
                commit_paths = [written_path] if written_path else None
                commit_sha, on_reject = hooks.auto_commit(f"step: {gap.desc[:50]}", paths=commit_paths)
            if commit_sha:
                print(f"  → committed: {commit_sha}")
                step_result = Step.create(
                    desc=f"executed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    commit=commit_sha,
                    chain_id=entry.chain_id,
                )
                compiler.record_execution("content_needed", True)
                postcond_refs, postcond_desc = _post_observe_resolution(
                    vocab=None,
                    tool_conf={"post_observe": tool_contract.post_observe},
                    commit_sha=commit_sha,
                    runtime_refs=runtime_refs,
                    hooks=hooks,
                    config=config,
                )
                if postcond_refs and postcond_desc:
                    postcond = Gap.create(
                        desc=postcond_desc,
                        content_refs=postcond_refs,
                        step_refs=[step_result.hash],
                    )
                    postcond.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
                    postcond.vocab = "hash_resolve_needed"
                    postcond_step = Step.create(
                        desc=f"postcondition: {gap.desc}",
                        step_refs=[step_result.hash],
                        content_refs=postcond_refs,
                        gaps=[postcond],
                        chain_id=entry.chain_id,
                        assessment=hooks.commit_assessment(commit_sha),
                    )
                    trajectory.append(postcond_step)
                    compiler.emit(postcond_step)
                compiler.resolve_current_gap(gap.hash)
            else:
                compiler.resolve_current_gap(gap.hash)
                step_result = Step.create(
                    desc=f"executed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )

    elif (
        vocab
        and (spec := get_vocab(vocab)) is not None
        and spec.target_kind == "chain"
        and isinstance(spec.target_ref, str)
        and spec.target_ref
    ):
        triggered_skills = registry.resolve_vocab_trigger(vocab)
        skill = triggered_skills[0] if triggered_skills else None
        if skill is None:
            print(f"  → missing inline chain trigger for {vocab}")
            compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
            step_result = _emit_rogue_with_diagnosis(
                desc=f"FAILED: {gap.desc}",
                origin_step=origin_step,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=vocab,
                trajectory=trajectory,
                compiler=compiler,
                failure_detail=f"no loaded on_vocab trigger skill for {vocab}",
            )
            _auto_activate_debug_for_rogue(
                registry=registry,
                origin_step=origin_step,
                rogue_step=step_result,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=vocab,
                failure_detail=f"no loaded on_vocab trigger skill for {vocab}",
                trajectory=trajectory,
                hooks=hooks,
                compiler=compiler,
                session=session,
            )
            return ExecutionOutcome(control="continue", step_result=step_result)
        print(f"  → activate chain-backed vocab:{vocab} [inline]")
        step_result = me.activate_skill_package(
            skill,
            skill.hash,
            gap,
            origin_step,
            entry.chain_id,
            current_turn,
            task_prompt=gap.desc,
            activation_content_refs=list(gap.content_refs),
            activation_step_refs=list(gap.step_refs),
            registry=registry,
            chains_dir=config.chains_dir,
            cors_root=config.cors_root,
            tool_map=config.tool_map,
        )
        child_chain = Chain.create(origin_gap=gap.hash, first_step=step_result.hash)
        child_chain.parent_chain_id = entry.chain_id
        child_chain.activation_ref = skill.hash
        child_chain.await_policy = "none"
        trajectory.add_chain(child_chain)
        compiler.ledger.chain_states[child_chain.hash] = ChainState.OPEN
        step_result.chain_id = child_chain.hash
        session.inject(
            "## Chain workflow activation\n"
            f"vocab: {vocab}\n"
            f"activation_ref: {skill.hash}\n"
            "mode: inline\n"
            f"chain_id: {child_chain.hash}\n"
            f"parent_chain_id: {entry.chain_id}\n"
            f"task: {gap.desc}\n"
            f"content_refs: {gap.content_refs or []}\n"
            f"step_refs: {gap.step_refs or []}"
        )
        compiler.emit(step_result)
        compiler.resolve_current_gap(gap.hash)

    elif vocab in config.observation_only_vocab:
        print(f"  → observation-only ({vocab})")
        if resolved_data:
            session.inject(f"## Resolved hash data for gap:{gap.hash}\n{resolved_data}")
            pre_step_note = _generate_pre_step_note(gap=gap, note_context=resolved_data)
            if pre_step_note is not None:
                session.inject(_render_note_for_injection(pre_step_note, title=f"## Pre-step note for gap:{gap.hash}"))
        step_result = Step.create(
            desc=f"resolved: {gap.desc}",
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
        step_result = _attach_note(step_result, pre_step_note)
        if step_result is not None and step_result.note is None and resolved_data:
            step_result = _attach_generated_note(step_result, gap=gap, resolved_data=resolved_data)
        compiler.resolve_current_gap(gap.hash)

    elif vocab and vocab in config.deterministic_vocab:
        print(f"  → deterministic ({vocab})")
        tool_conf = config.tool_map.get(vocab, {})
        tool_path = tool_conf.get("tool") if isinstance(tool_conf, dict) else tool_conf
        if tool_path:
            output, _ = hooks.execute_tool(tool_path, {"refs": gap.content_refs, "desc": gap.desc})
            session.inject(f"## Tool output ({vocab})\n{output}")
        elif resolved_data:
            session.inject(f"## Resolved data\n{resolved_data}")

        observe_context_parts: list[str] = []
        if resolved_data:
            observe_context_parts.append(f"## Resolved data\n{resolved_data}")
        if tool_path and 'output' in locals() and output:
            observe_context_parts.append(f"## Tool output ({vocab})\n{output}")
        pre_step_note = _generate_pre_step_note(
            gap=gap,
            note_context="\n\n".join(observe_context_parts),
        )
        if pre_step_note is not None:
            session.inject(_render_note_for_injection(pre_step_note, title=f"## Pre-step note for gap:{gap.hash}"))

        follow_on_guidance = ""
        if vocab == "hash_resolve_needed":
            follow_on_guidance = (
                "\nIf this observation resolves a prerequisite for an explicit requested change, "
                "surface the actual next gap now rather than stopping at observation.\n"
                "For .st files, identities, profiles, preferences, and long-horizon semantic state, "
                "use reprogramme_needed as the mutate gap.\n"
                "For ordinary workspace file edits, use the relevant mutate vocab instead.\n"
                "Do not answer with a future-action promise unless the next gap is actually surfaced."
            )

        raw = session.call(
            f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps.{follow_on_guidance}"
        )
        print(f"  LLM: {raw[:150]}...")
        step_result, child_gaps = hooks.parse_step_output(
            raw,
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
        step_result = _attach_note(step_result, pre_step_note)
        if vocab == "hash_resolve_needed" and step_result is not None and step_result.note is None and resolved_data:
            step_result = _attach_generated_note(step_result, gap=gap, resolved_data=resolved_data)
        if child_gaps:
            compiler.emit(step_result)
        else:
            compiler.resolve_current_gap(gap.hash)

    elif vocab in {"tool_needed", "vocab_reg_needed"} or (vocab and is_mutate(vocab)):
        policy = hooks.load_tree_policy()
        target_skill = _entity_target_for_reprogramme(gap, registry)
        reroute_vocab = None
        sealed_builder_branch = vocab == "vocab_reg_needed"
        if not sealed_builder_branch:
            for ref in gap.content_refs:
                rule = hooks.match_policy(ref, policy)
                if _preserve_destructive_bash_on_entity_surface(gap, policy, target_skill) and _is_entity_admin_surface(ref):
                    continue
                if rule and rule.get("on_mutate") and rule["on_mutate"] != vocab:
                    reroute_vocab = rule["on_mutate"]
                    if rule.get("reprogramme_mode"):
                        gap.route_mode = str(rule["reprogramme_mode"])
                    break
            if not reroute_vocab:
                for path_prefix, rule in policy.items():
                    if _preserve_destructive_bash_on_entity_surface(gap, policy, target_skill) and _is_entity_admin_surface(path_prefix):
                        continue
                    if rule.get("on_mutate") and path_prefix.rstrip("/") in gap.desc.lower():
                        if rule["on_mutate"] != vocab:
                            reroute_vocab = rule["on_mutate"]
                            if rule.get("reprogramme_mode"):
                                gap.route_mode = str(rule["reprogramme_mode"])
                            break
            if not reroute_vocab and vocab != "reprogramme_needed" and not _preserve_destructive_bash_on_entity_surface(gap, policy, target_skill):
                if any(ref.endswith(".st") or registry.resolve(ref) is not None for ref in gap.content_refs):
                    reroute_vocab = "reprogramme_needed"
                elif ".st" in gap.desc.lower():
                    reroute_vocab = "reprogramme_needed"

            if not reroute_vocab:
                structural_route_mode = _infer_reason_judgment_route_mode(
                    gap,
                    registry=registry,
                    policy=policy,
                    target_entity=target_skill,
                    route_mode=gap.route_mode,
                )
                if _requires_reason_judgment(
                    gap,
                    registry=registry,
                    policy=policy,
                    route_mode=structural_route_mode,
                    target_entity=target_skill,
                ):
                    reroute_vocab = "reason_needed"
                    if structural_route_mode:
                        gap.route_mode = structural_route_mode

            if reroute_vocab == "reprogramme_needed" and not gap.route_mode:
                gap.route_mode = _determine_reprogramme_mode(gap, target_skill, policy)

            if reroute_vocab == "reprogramme_needed" and _new_action_origination_requires_reason(
                gap,
                route_mode=gap.route_mode,
                target_entity=target_skill,
            ):
                reroute_vocab = "reason_needed"
                gap.route_mode = None

            if reroute_vocab:
                print(f"  → policy auto-route: {vocab} → {reroute_vocab}")
                if gap.route_mode:
                    print(f"    route_mode: {gap.route_mode}")
                gap.vocab = reroute_vocab
                compiler.ledger.stack.append(entry)
                return ExecutionOutcome(control="continue")

        print(f"  → mutation ({vocab})")
        if not compiler.validate_omo(vocab):
            print("  → OMO violation: need observation first")
            if resolved_data:
                session.inject(f"## Context for gap:{gap.hash}\n{resolved_data}")
            compiler.record_execution("scan_needed", False)

        if resolved_data:
            session.inject(f"## Resolved context for mutation\n{resolved_data}")

        tool_conf = config.tool_map.get(vocab, {})
        tool_path = tool_conf.get("tool") if isinstance(tool_conf, dict) else None
        tool_contract = load_tool_contract(config.cors_root / tool_path) if isinstance(tool_path, str) and tool_path else None

        if vocab == "hash_edit_needed":
            compose_prompt = (
                f"Compose a file edit to resolve this gap:\n"
                f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
                f"Available content refs: {gap.content_refs or []}\n"
                f"Available step refs: {gap.step_refs or []}\n\n"
                "Targeting rules:\n"
                "- Use the carried refs and resolved context to choose the exact files that need mutation.\n"
                "- Prefer concrete non-.st workspace files when they are present.\n"
                "- Treat workflow/entity .st refs as context only unless the task explicitly asks to edit a workflow or entity file.\n"
                "- If multiple refs are present, mutate only the files that actually require change.\n\n"
                f"Respond with JSON params for hash_manifest.py:\n"
                f'{{"action": "patch", "path": "relative/file/path", '
                f'"patch": {{"old": "exact text to replace", "new": "replacement text"}}}}\n\n'
                f"Or for a full rewrite:\n"
                f'{{"action": "write", "path": "relative/file/path", "content": "full file content"}}\n\n'
                f"Use the EXACT current file content for the 'old' field. Do not guess."
            )
        elif vocab == "tool_needed":
            session.inject(_render_public_tool_registry(config.cors_root))
            compose_prompt = (
                f"Compose a tool scaffold to resolve this gap:\n"
                f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
                f"Respond with JSON params for system/tool_builder.py:\n"
                f'{{"path": "tools/new_tool.py", "desc": "what the tool does", '
                f'"mode": "observe|mutate", "scope": "workspace|external", '
                f'"post_observe": "none|log|artifacts", '
                f'"default_artifacts": ["optional/path"], '
                f'"artifact_params": ["output_path"], '
                f'"runtime_artifact_key": "artifacts"}}\n\n'
                f"Workspace mutate tools must use post_observe='artifacts'. "
                f"Observe tools must use post_observe='none'. Artifact tools must "
                f"declare fixed artifact paths, artifact-bearing params, or a runtime artifact key."
            )
        elif vocab == "vocab_reg_needed":
            session.inject(_render_public_tool_registry(config.cors_root))
            session.inject(render_public_chain_registry(config.cors_root))
            session.inject(render_configurable_vocab_registry())
            compose_prompt = (
                f"Compose a semantic vocab skeleton to resolve this gap:\n"
                f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
                "This is a dedicated vocab-registry branch. Stay on the vocab builder path.\n"
                "Do not surface reason_needed, reprogramme_needed, or hash_edit_needed here.\n"
                "Use exact public tool or chain hashes for target_ref.\n\n"
                f"Respond with JSON params for system/vocab_builder.py:\n"
                f'{{"version": "vocab_skeleton.v1", "operation": "upsert|delete", '
                f'"name": "new_vocab_needed", "classifiable": "observe|mutate", '
                f'"target_kind": "tool|chain", "target_ref": "da6ab1b8070b", '
                f'"desc": "what the semantic route means", "prompt_hint": "how the route should be used"}}\n\n'
                "Use operation='delete' only when removing an existing configurable vocab.\n"
                "Do not invent bridge vocab here."
            )
        elif tool_path:
            compose_prompt = _mutate_tool_compose_prompt(
                vocab=vocab or "",
                gap=gap,
                tool_path=tool_path,
                contract=tool_contract,
            )
        else:
            compose_prompt = (
                f"Compose a shell command to resolve this gap:\n"
                f"  gap:{gap.hash} \"{gap.desc}\"\n"
                f"  vocab: {vocab}\n\n"
                f"This is macOS. Use python3 one-liners for JSON edits, not sed.\n"
                f"Respond with JSON: {{\"command\": \"...\", \"reasoning\": \"...\"}}"
            )

        raw = session.call(compose_prompt)
        print(f"  LLM compose: {raw[:150]}...")

        executed = False
        exec_failed = False
        output = ""
        intent = None
        written_path = None
        commit_paths: list[str] | None = None
        runtime_refs: list[str] = []
        runtime_commit: str | None = None

        if vocab == "hash_edit_needed":
            intent = hooks.extract_json(raw)
            if intent:
                output, code = hooks.execute_tool("tools/hash_manifest.py", intent)
                print(f"  → hash_manifest: {output[:100]}")
                written_path = hooks.extract_written_path(output)
                if not written_path and isinstance(intent, dict):
                    path = intent.get("path")
                    if isinstance(path, str) and path:
                        written_path = path
                executed = True
                exec_failed = code != 0
            else:
                print("  → no valid params extracted")
        elif vocab == "tool_needed":
            intent = hooks.extract_json(raw)
            if intent:
                output, code = hooks.execute_tool("system/tool_builder.py", intent)
                print(f"  → tool_builder: {output[:100]}")
                written_path = hooks.extract_written_path(output)
                if not written_path and isinstance(intent, dict):
                    path = intent.get("path")
                    if isinstance(path, str) and path:
                        written_path = path
                executed = True
                exec_failed = code != 0
            else:
                print("  → no valid params extracted")
        elif vocab == "vocab_reg_needed":
            intent = hooks.extract_json(raw)
            if intent:
                output, code = hooks.execute_tool("system/vocab_builder.py", intent)
                print(f"  → vocab_builder: {output[:100]}")
                written_path = hooks.extract_written_path(output)
                if not written_path:
                    written_path = "vocab_registry.py"
                executed = True
                exec_failed = code != 0
            else:
                print("  → no valid params extracted")
        elif tool_path:
            intent = hooks.extract_json(raw)
            if intent:
                output, code = hooks.execute_tool(tool_path, intent)
                print(f"  → {Path(tool_path).name}: {output[:100]}")
                runtime_refs, runtime_commit = _collect_contract_artifact_refs(
                    contract=tool_contract,
                    intent=intent,
                    output=output,
                    hooks=hooks,
                )
                if vocab == "bash_needed":
                    commit_paths = _infer_bash_commit_paths(intent, config.cors_root)
                if not written_path:
                    for ref in runtime_refs:
                        if "/" in ref or "." in Path(ref).name:
                            written_path = ref
                            break
                executed = True
                exec_failed = code != 0
            else:
                print("  → no valid params extracted")
        else:
            command = hooks.extract_command(raw)
            if command:
                print(f"  → executing: {command[:100]}")
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(config.cors_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                output = result.stdout[:500] or result.stderr[:500] or "(no output)"
                print(f"  → output: {output[:100]}")
                executed = True
                exec_failed = result.returncode != 0
                if exec_failed:
                    print(f"  → FAILED (exit {result.returncode})")
            else:
                print("  → no command extracted")

        if exec_failed:
            print("  → execution failed, recording on trajectory")
            session.inject(f"## EXECUTION FAILED for gap:{gap.hash}\n{output}")
            step_result = _emit_rogue_with_diagnosis(
                desc=f"FAILED: {gap.desc}",
                origin_step=origin_step,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=vocab or "mutation",
                trajectory=trajectory,
                compiler=compiler,
                failure_detail=output[:500] if output else None,
            )
            _auto_activate_debug_for_rogue(
                registry=registry,
                origin_step=origin_step,
                rogue_step=step_result,
                gap=gap,
                chain_id=entry.chain_id,
                rogue_kind="tool_failure",
                failure_source=vocab or "mutation",
                failure_detail=output[:500] if output else None,
                trajectory=trajectory,
                hooks=hooks,
                compiler=compiler,
                session=session,
            )
            compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
            return ExecutionOutcome(control="continue", step_result=step_result)

        if executed:
            commit_sha = runtime_commit
            on_reject = None
            if not commit_sha:
                if not commit_paths:
                    commit_paths = [written_path] if written_path else None
                commit_sha, on_reject = hooks.auto_commit(f"step: {gap.desc[:50]}", paths=commit_paths)
            if commit_sha:
                print(f"  → committed: {commit_sha}")
                step_result = Step.create(
                    desc=f"executed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    commit=commit_sha,
                    chain_id=entry.chain_id,
                )
                compiler.record_execution(vocab, True)
                _refresh_runtime_control_surfaces(
                    written_path=written_path,
                    session=session,
                    config=config,
                )
                postcond_vocab = "hash_resolve_needed"
                postcond_refs, postcond_desc = _bridge_reintegration_target(
                    vocab=vocab,
                    written_path=written_path,
                    commit_sha=commit_sha,
                )
                if not postcond_refs or not postcond_desc:
                    postcond_refs, postcond_desc = _post_observe_resolution(
                        vocab=vocab,
                        tool_conf=tool_conf,
                        commit_sha=commit_sha,
                        runtime_refs=runtime_refs,
                        hooks=hooks,
                        config=config,
                    )
                else:
                    postcond_vocab = "reason_needed"

                postcond = Gap.create(
                    desc=postcond_desc,
                    content_refs=postcond_refs,
                    step_refs=[step_result.hash],
                )
                postcond.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
                postcond.vocab = postcond_vocab
                assessment_lines = hooks.commit_assessment(commit_sha)
                postcond_step = Step.create(
                    desc=f"postcondition: {gap.desc}",
                    step_refs=[step_result.hash],
                    content_refs=postcond_refs,
                    gaps=[postcond],
                    chain_id=entry.chain_id,
                    assessment=assessment_lines,
                )
                trajectory.append(postcond_step)
                compiler.emit(postcond_step)
                compiler.resolve_current_gap(gap.hash)
                print(f"  → postcondition gap injected: {postcond_vocab} → {postcond_refs}")
                if assessment_lines:
                    print("  → postcondition assessment:")
                    for line in assessment_lines:
                        print(f"    {line}")
            else:
                last_msg = hooks.git(["log", "--oneline", "-1"], str(config.cors_root))
                if "auto-revert: protected path violation" in last_msg:
                    if on_reject:
                        print(f"  → codon immutability → {on_reject}")
                        session.inject(
                            "## CODON IMMUTABILITY VIOLATION\n"
                            "You tried to modify an immutable codon file. "
                            "Codons are primitives — they cannot be changed. "
                            "The change was auto-reverted. Recalibrate your approach."
                        )
                        reject_gap = Gap.create(
                            desc=f"reorientation needed: attempted to modify immutable codon — {gap.desc}",
                            step_refs=[origin_step.hash],
                            content_refs=gap.content_refs,
                        )
                        reject_gap.scores = Epistemic(relevance=1.0, confidence=0.8, grounded=0.0)
                        reject_gap.vocab = on_reject
                        reject_gap.turn_id = current_turn
                        reject_step = Step.create(
                            desc=f"REVERTED: {gap.desc} (codon immutability → {on_reject})",
                            step_refs=[origin_step.hash],
                            content_refs=gap.content_refs,
                            gaps=[reject_gap],
                            chain_id=entry.chain_id,
                            rogue=True,
                            rogue_kind="auto_reverted_mutation",
                            failure_source="tree_policy",
                            failure_detail=f"immutable path violation → {on_reject}",
                            assessment=_policy_drift_assessment("tree_policy", f"immutable path violation → {on_reject}"),
                        )
                        trajectory.append(reject_step)
                        compiler.emit(reject_step)
                        diagnose_step = _emit_rogue_with_diagnosis(
                            desc=f"ROGUE: {gap.desc} (codon immutability)",
                            origin_step=origin_step,
                            gap=gap,
                            chain_id=entry.chain_id,
                            rogue_kind="auto_reverted_mutation",
                            failure_source="tree_policy",
                            trajectory=trajectory,
                            compiler=compiler,
                            failure_detail=f"immutable path violation → {on_reject}",
                            assessment=_policy_drift_assessment("tree_policy", f"immutable path violation → {on_reject}"),
                        )
                        _auto_activate_debug_for_rogue(
                            registry=registry,
                            origin_step=origin_step,
                            rogue_step=diagnose_step,
                            gap=gap,
                            chain_id=entry.chain_id,
                            rogue_kind="auto_reverted_mutation",
                            failure_source="tree_policy",
                            failure_detail=f"immutable path violation → {on_reject}",
                            trajectory=trajectory,
                            hooks=hooks,
                            compiler=compiler,
                            session=session,
                        )
                        compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
                        return ExecutionOutcome(control="continue", step_result=diagnose_step)
                    session.inject(
                        "## PROTECTED PATH VIOLATION\n"
                        "Your command tried to modify a protected system file. "
                        "The change was auto-reverted. Recompose your command to "
                        "only modify files in the workspace, not system files.\n"
                        f"Command output was:\n{output}"
                    )
                    step_result = _emit_rogue_with_diagnosis(
                        desc=f"REVERTED: {gap.desc} (protected path violation)",
                        origin_step=origin_step,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="policy_violation",
                        failure_source="tree_policy",
                        trajectory=trajectory,
                        compiler=compiler,
                        failure_detail=output[:500] if output else "protected path violation",
                        assessment=_policy_drift_assessment("tree_policy", output[:500] if output else "protected path violation"),
                    )
                    _auto_activate_debug_for_rogue(
                        registry=registry,
                        origin_step=origin_step,
                        rogue_step=step_result,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="policy_violation",
                        failure_source="tree_policy",
                        failure_detail=output[:500] if output else "protected path violation",
                        trajectory=trajectory,
                        hooks=hooks,
                        compiler=compiler,
                        session=session,
                    )
                    compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
                    return ExecutionOutcome(control="continue", step_result=step_result)

                session.inject(f"## Command output (no mutation)\n{output}")
                step_result = Step.create(
                    desc=f"executed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                compiler.record_execution(vocab, False)
                postcond_vocab = "hash_resolve_needed"
                postcond_refs, postcond_desc = _bridge_reintegration_target(
                    vocab=vocab,
                    written_path=written_path,
                    commit_sha=None,
                )
                if not postcond_refs or not postcond_desc:
                    postcond_refs, postcond_desc = _post_observe_resolution(
                        vocab=vocab,
                        tool_conf=tool_conf,
                        commit_sha=None,
                        runtime_refs=runtime_refs,
                        hooks=hooks,
                        config=config,
                    )
                else:
                    postcond_vocab = "reason_needed"
                if postcond_refs and postcond_desc:
                    postcond = Gap.create(
                        desc=postcond_desc,
                        content_refs=postcond_refs,
                        step_refs=[step_result.hash],
                    )
                    postcond.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
                    postcond.vocab = postcond_vocab
                    postcond_step = Step.create(
                        desc=f"postcondition: {gap.desc}",
                        step_refs=[step_result.hash],
                        content_refs=postcond_refs,
                        gaps=[postcond],
                        chain_id=entry.chain_id,
                    )
                    trajectory.append(postcond_step)
                    compiler.emit(postcond_step)
                    print(f"  → postcondition gap injected: {postcond_vocab} → {postcond_refs}")
                compiler.resolve_current_gap(gap.hash)
        else:
            compiler.resolve_current_gap(gap.hash)
            step_result = Step.create(
                desc=f"skipped: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )

    elif vocab and is_observe(vocab):
        print(f"  → observation ({vocab})")
        tool_conf = config.tool_map.get(vocab, {})
        tool_path = tool_conf.get("tool") if isinstance(tool_conf, dict) else tool_conf
        if tool_path:
            if vocab == "pattern_needed":
                params = _pattern_tool_params(gap)
                if params:
                    output, _ = hooks.execute_tool(tool_path, params)
                    session.inject(f"## Tool output ({vocab})\n{output}")
                elif resolved_data:
                    session.inject(f"## Resolved data\n{resolved_data}")
                else:
                    session.inject(
                        "## Pattern observation fallback\n"
                        "No concrete search pattern was available, so no grep was executed."
                    )
            else:
                output, _ = hooks.execute_tool(tool_path, {"refs": gap.content_refs, "desc": gap.desc})
                session.inject(f"## Tool output ({vocab})\n{output}")
        elif resolved_data:
            session.inject(f"## Resolved data\n{resolved_data}")

        raw = session.call(f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps.")
        print(f"  LLM: {raw[:150]}...")
        step_result, child_gaps = hooks.parse_step_output(
            raw,
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
        compiler.record_execution(vocab, False)
        if child_gaps:
            compiler.emit(step_result)
        else:
            compiler.resolve_current_gap(gap.hash)

    elif vocab == "reason_needed":
        print("  → reason controller")
        reason_context = _render_reason_context(gap, trajectory=trajectory, hooks=hooks, registry=registry)
        if reason_context:
            session.inject(reason_context)
        pre_reason_context = reason_context or (f"## Current Gap Resolved Content\n{resolved_data}" if resolved_data else "")
        pre_step_note = _generate_pre_step_note(
            gap=gap,
            note_context=pre_reason_context,
        )
        if pre_step_note is not None:
            session.inject(_render_note_for_injection(pre_step_note, title=f"## Pre-step note for gap:{gap.hash}"))
        raw = session.call(_reason_controller_prompt(gap))
        activation_intent = _extract_reason_activation_intent(raw, hooks)
        if activation_intent:
            activate_ref = activation_intent["activate_ref"]
            await_needed = activation_intent["await_needed"]
            task_prompt = activation_intent["prompt"] or gap.desc
            activation_content_refs = activation_intent["content_refs"]
            activation_step_refs = activation_intent["step_refs"]
            activation_note = activation_intent.get("note") or pre_step_note
            await_policy = "manual" if await_needed else "none"
            activation_context = None
            if activation_content_refs or activation_step_refs:
                activation_context = hooks.resolve_all_refs(activation_step_refs, activation_content_refs, trajectory)
            if await_needed:
                print(f"  → activate isolated workflow:{activate_ref} [{await_policy}]")
                run_kwargs = {
                    "task_prompt": task_prompt,
                    "store_kind": "background_agent",
                    "await_policy": await_policy,
                }
                if activation_content_refs:
                    run_kwargs["content_refs"] = activation_content_refs
                if activation_step_refs:
                    run_kwargs["step_refs"] = activation_step_refs
                if activation_context:
                    run_kwargs["activation_context"] = activation_context
                child_result = hooks.run_isolated_workflow(activate_ref, **run_kwargs)
                child_status = str(child_result.get("status", "unknown") or "unknown")
                if child_status != "ok":
                    compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
                    failure_detail = f"isolated workflow launch failed: status={child_status}, activation_ref={activate_ref}"
                    step_result = _emit_rogue_with_diagnosis(
                        desc=f"FAILED: {gap.desc}",
                        origin_step=origin_step,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="tool_failure",
                        failure_source="reason_needed",
                        trajectory=trajectory,
                        compiler=compiler,
                        failure_detail=failure_detail,
                    )
                    _auto_activate_debug_for_rogue(
                        registry=registry,
                        origin_step=origin_step,
                        rogue_step=step_result,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="tool_failure",
                        failure_source="reason_needed",
                        failure_detail=failure_detail,
                        trajectory=trajectory,
                        hooks=hooks,
                        compiler=compiler,
                        session=session,
                    )
                    return ExecutionOutcome(control="continue", step_result=step_result)
                compiler.record_background_trigger(
                    entry.chain_id,
                    refs=[activate_ref] + activation_content_refs + activation_step_refs,
                    activation_ref=activate_ref,
                    await_policy=await_policy,
                    store_kind="background_agent",
                    parent_step=origin_step.hash,
                )
                session.inject(
                    "## Child workflow activation\n"
                    f"activation_ref: {activate_ref}\n"
                    f"await_needed: {str(await_needed).lower()}\n"
                    f"status: {child_result.get('status', 'unknown')}\n"
                    f"store_kind: {child_result.get('store_kind', 'background_agent')}\n"
                    f"resolved: {str(bool(child_result.get('resolved'))).lower()}\n"
                    f"task: {task_prompt}\n"
                    f"content_refs: {activation_content_refs or []}\n"
                    f"step_refs: {activation_step_refs or []}"
                )
                if child_result.get("resolved") and child_result.get("response"):
                    hooks.queue_background_completion(
                        {
                            "activation_ref": activate_ref,
                            "task": task_prompt,
                            "store_kind": child_result.get("store_kind", "background_agent"),
                            "trajectory": child_result.get("trajectory"),
                            "chains_file": child_result.get("chains_file"),
                            "tree_render": child_result.get("tree_render"),
                            "response": child_result.get("response"),
                        }
                    )
                step_result = Step.create(
                    desc=f"activated child workflow:{activate_ref}",
                    step_refs=[origin_step.hash],
                    content_refs=[activate_ref] + activation_content_refs,
                    chain_id=entry.chain_id,
                    note=activation_note,
                )
            else:
                skill = _resolve_workflow_skill(registry, activate_ref, config.cors_root)
                if skill is None:
                    compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
                    step_result = _emit_rogue_with_diagnosis(
                        desc=f"FAILED: {gap.desc}",
                        origin_step=origin_step,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="tool_failure",
                        failure_source="reason_needed",
                        trajectory=trajectory,
                        compiler=compiler,
                        failure_detail=f"unresolved workflow activation ref: {activate_ref}",
                    )
                    _auto_activate_debug_for_rogue(
                        registry=registry,
                        origin_step=origin_step,
                        rogue_step=step_result,
                        gap=gap,
                        chain_id=entry.chain_id,
                        rogue_kind="tool_failure",
                        failure_source="reason_needed",
                        failure_detail=f"unresolved workflow activation ref: {activate_ref}",
                        trajectory=trajectory,
                        hooks=hooks,
                        compiler=compiler,
                        session=session,
                    )
                    return ExecutionOutcome(control="continue", step_result=step_result)
                print(f"  → activate inline workflow:{activate_ref}")
                step_result = me.activate_skill_package(
                    skill,
                    skill.hash,
                    gap,
                    origin_step,
                    entry.chain_id,
                    current_turn,
                    task_prompt=task_prompt,
                    activation_content_refs=activation_content_refs,
                    activation_step_refs=activation_step_refs,
                    registry=registry,
                    chains_dir=config.chains_dir,
                    cors_root=config.cors_root,
                    tool_map=config.tool_map,
                )
                child_chain = Chain.create(origin_gap=gap.hash, first_step=step_result.hash)
                child_chain.parent_chain_id = entry.chain_id
                child_chain.activation_ref = skill.hash
                child_chain.await_policy = "none"
                trajectory.add_chain(child_chain)
                compiler.ledger.chain_states[child_chain.hash] = ChainState.OPEN
                step_result.chain_id = child_chain.hash
                session.inject(
                    "## Child workflow activation\n"
                    f"activation_ref: {skill.hash}\n"
                    "await_needed: false\n"
                    "mode: inline\n"
                    f"chain_id: {child_chain.hash}\n"
                    f"parent_chain_id: {entry.chain_id}\n"
                    f"task: {task_prompt}\n"
                    f"content_refs: {activation_content_refs or []}\n"
                    f"step_refs: {activation_step_refs or []}"
                )
                if activation_note is not None:
                    step_result.note = activation_note
                compiler.emit(step_result)
            compiler.resolve_current_gap(gap.hash)
        else:
            step_result, child_gaps = hooks.parse_step_output(
                raw,
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            step_result = _attach_note(step_result, pre_step_note)
            rewrites = _sanitize_reason_child_gaps(
                child_gaps,
                registry=registry,
                policy=hooks.load_tree_policy(),
            )
            if rewrites:
                print(f"  → rewrote {rewrites} reason-emitted reprogramme gap(s) to reason_needed")
            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)

    elif vocab == "await_needed":
        print("  → await (pause codon)")
        compiler.record_await(entry.chain_id)
        await_skill = registry.resolve_by_name("await")
        if await_skill:
            session.inject(f"## Await checkpoint: {gap.desc}")
            if resolved_data:
                session.inject(f"## Sub-agent context\n{resolved_data}")
            await_step = Step.create(
                desc=f"await checkpoint: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=[await_skill.hash] + gap.content_refs,
                chain_id=entry.chain_id,
            )
            for st_step in await_skill.steps:
                child_gap = Gap.create(desc=st_step.desc, content_refs=gap.content_refs)
                child_gap.scores = Epistemic(
                    relevance=st_step.__dict__.get("relevance", 0.8),
                    confidence=0.8,
                    grounded=0.0,
                )
                child_gap.vocab = st_step.vocab
                child_gap.turn_id = current_turn
                await_step.gaps.append(child_gap)
            trajectory.append(await_step)
            compiler.emit(await_step)
            compiler.resolve_current_gap(gap.hash)
            step_result = await_step
        else:
            if resolved_data:
                session.inject(f"## Context\n{resolved_data}")
            raw = session.call(f"Await checkpoint: gap:{gap.hash} \"{gap.desc}\". Inspect sub-agent results.")
            step_result, child_gaps = hooks.parse_step_output(
                raw,
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)

    elif vocab == "reprogramme_needed":
        print(f"  → reprogramme ({vocab})")
        policy = hooks.load_tree_policy()
        target_entity = _entity_target_for_reprogramme(gap, registry)
        route_mode = _determine_reprogramme_mode(gap, target_entity, policy)
        if route_mode != "entity_editor":
            print("  → reprogramme is entity-only; rerouting to reason_needed")
            gap.vocab = "reason_needed"
            gap.route_mode = None
            compiler.ledger.stack.append(entry)
            return ExecutionOutcome(control="continue")
        if _requires_reason_judgment(
            gap,
            registry=registry,
            policy=policy,
            route_mode=route_mode,
            target_entity=target_entity,
        ):
            print("  → structural boundary requires reason_needed first")
            gap.vocab = "reason_needed"
            gap.route_mode = None
            compiler.ledger.stack.append(entry)
            return ExecutionOutcome(control="continue")
        entity_data = hooks.resolve_entity(gap.content_refs, registry, trajectory)
        if entity_data:
            session.inject(f"## Existing entity data\n{entity_data}")
        elif resolved_data:
            session.inject(f"## Context\n{resolved_data}")

        principles_path = config.cors_root / "docs" / "PRINCIPLES.md"
        if principles_path.exists():
            principles_content = principles_path.read_text()
            session.inject(
                "## System Principles (PRINCIPLES.md)\n"
                "Every .st file you create must be consistent with these principles.\n"
                "This is the architectural constitution.\n\n"
                f"{principles_content}"
            )

        entity_lines = []
        for s in registry.all_skills():
            steps_summary = " → ".join(st.action for st in s.steps) if s.steps else "(pure entity)"
            entity_lines.append(
                f"  {s.display_name}:{s.hash} ({s.name}.st) — {s.desc[:80]}\n"
                f"    steps: {steps_summary}"
            )
        entity_list = "\n".join(entity_lines)
        cmd_lines = []
        for name, s in registry.commands.items():
            steps_summary = " → ".join(st.action for st in s.steps) if s.steps else "(pure entity)"
            cmd_lines.append(
                f"  /{name} ({s.name}.st) — {s.desc[:80]}\n"
                f"    steps: {steps_summary}"
            )
        cmd_list = "\n".join(cmd_lines) if cmd_lines else "  (none)"
        session.inject(f"## Step Network\n{hooks.render_step_network(registry)}")
        if target_entity is not None and target_entity.payload:
            frame = st_builder_module.semantic_skeleton_from_st(
                target_entity.payload,
                existing_ref=target_entity.hash,
            )
        else:
            frame = st_builder_module.blank_semantic_skeleton(
                name=(target_entity.name if target_entity is not None else "entity_name"),
                desc=gap.desc,
                trigger=(target_entity.trigger if target_entity is not None else "manual"),
                artifact_kind="entity",
            )
        frame = _coerce_semantic_frame_for_mode(frame, route_mode)
        session.inject(
            "## Editable semantic frame\n"
            "Edit this frame in place. Keep structure unless the user explicitly asked to change it.\n"
            f"{json.dumps(frame, indent=2)}"
        )
        if target_entity is not None and Path(target_entity.source).name == "admin.st":
            session.inject(
                "## Admin Primitive\n"
                "admin.st is the admin-user primitive for this system.\n"
                "- On this machine, operator identity resolves to admin.st with priority over all other entities.\n"
                "- Entity/profile machinery may exist for others, but admin.st is the canonical operator entity.\n"
                "- Do not rename it away from admin.\n"
                "- Update admin.st in place when persisting operator preferences or corrections.\n"
                "- Treat requested preference changes as additive semantic updates, not a license to rewrite the package shape.\n"
                "- Do not rewrite desc, lineage, or package identity unless the user explicitly asked.\n"
            )
        route_mode_guidance = (
            "- This target lives in the admin/entity tree.\n"
            "- Return an entity frame only.\n"
            "- Do not include root, phases, or closure.\n"
            "- Preserve or restore deterministic context-injection steps; do not manifest workflow scaffolding.\n\n"
        )
        raw = session.call(
            f"You need to reprogramme your knowledge: gap:{gap.hash} \"{gap.desc}\"\n\n"
            "## Known entities (reference by hash, use as building blocks)\n"
            f"{entity_list}\n\n"
            "## Available /command workflows\n"
            f"{cmd_list}\n\n"
            "## Edit the semantic frame\n\n"
            "Treat .st as step manifestation, not as plain file content.\n"
            "Your job here is to edit the surfaced semantic frame so the persisted state stays structurally stable over time.\n\n"
            f"### Deterministic route mode\n"
            f"- route_mode: {route_mode}\n"
            f"{route_mode_guidance}"
            "### Structural distinction\n"
            "- entity.st: manifests primarily as semantic/context injection.\n"
            "- In this branch you may create or update entity state directly.\n"
            "- Action/workflow authoring belongs to reason-controlled structural primitives, not reprogramme.\n\n"
            "### Frame contract\n"
            "- Return JSON only.\n"
            "- Use semantic_skeleton.v1 as the author-time frame.\n"
            "- Keep artifact.kind = entity.\n"
            "- Do not include root, phases, or closure in the returned frame.\n"
            "- The persistence layer will lower this frame back into the current entity .st runtime format.\n\n"
            "### What reprogramme is for\n"
            "Use this branch to persist:\n"
            "- people, identities, preferences, communication style\n"
            "- concepts, domains, constraints, sources, scope\n"
            "- long-horizon tracked entities and background concerns\n"
            "- corrections to the system's internal model\n\n"
            "### Manifestation fields\n"
            "Include only fields relevant to the semantic state being persisted:\n"
            "- People: identity + preferences\n"
            "- Domain/compliance: constraints + sources + scope\n"
            "- Concepts: refs linking to related entity or chain hashes\n"
            "- Keep executable flow concerns out of this branch\n\n"
            "### Entity format continuity\n"
            "When updating an existing entity, preserve its established file shape unless the user explicitly asked to change structure.\n"
            "- Preserve trigger, refs, and deterministic steps by default.\n"
            "- Entity packages must carry deterministic context-injection steps derived from their semantic sections.\n"
            "- Those steps are resolve-only surfaces like load_identity or load_preferences; they are not workflow mutation steps.\n"
            "- Do not delete or collapse those context-injection steps. If they are missing, the builder will restore them from semantics.\n"
            "- Preserve access_rules, init state, and other scaffolding fields that already exist.\n"
            "- Prefer additive semantic updates over rewriting desc or collapsing structure.\n"
            "- Do not replace a structured entity with an empty flow unless the user explicitly wants that simplification.\n"
            "- If you are updating an existing entity package, keep its manifestation pattern stable.\n\n"
            "### Contact identity continuity\n"
            "- If this gap is about updating an existing user/contact identity, update that existing entity in place.\n"
            "- Do not create a second on_contact entity for the same external contact.\n"
            "- Reuse the existing trigger and include existing_ref when you are updating a known entity.\n\n"
            "### Admin primitive rule\n"
            "- admin.st is the admin-user primitive on this machine and has priority over all other entities for operator identity.\n"
            "- If the target is the operator, update admin.st in place rather than creating or preferring another entity profile.\n"
            "- Limit admin.st changes to additive semantic updates unless the user explicitly requested a structural rewrite.\n\n"
            "### Composition rule\n"
            "Compose from existing entities and workflows first. Reuse known hashes where possible.\n"
            "If you need executable structure, surface reason_needed so a structural primitive can own it.\n\n"
            "### Runtime note\n"
            "Entity-like packages usually manifest as semantic injection when resolved.\n"
            "Current persistence path writes JSON .st files through st_builder after lowering the semantic frame.\n\n"
            "### Entity references\n"
            "Reference other entities by hash, not name.\n"
            'Use refs to map names to hashes: {"admin": "72b1d5ffc964"}\n\n'
            "### Triggers\n"
            "- manual: only when explicitly invoked\n"
            "- on_contact:X: fires when user X messages\n"
            "- command:X: hidden from LLM, triggered via /X command only\n\n"
            "```json\n"
            '{"version": "semantic_skeleton.v1",\n'
            ' "artifact": {"kind": "entity", "protected_kind": "entity", "lineage": "stable_name", "version_strategy": "hash_pinned"},\n'
            ' "name": "entity_name", "desc": "what this semantic package is",\n'
            ' "trigger": "manual | on_contact:X | command:X",\n'
            ' "refs": {"entity_name": "entity_hash", "chain_name": "chain_hash"},\n'
            ' "existing_ref": "include when updating a known entity",\n'
            ' "semantics": {"identity": {}, "preferences": {}, "constraints": {}, "sources": [], "scope": ""}}\n'
            "```\n"
            "Only include fields relevant to this semantic package. Omit empty fields.\n"
            "Do not invent or edit action workflows here."
        )
        print(f"  LLM compose: {raw[:150]}...")
        intent = hooks.extract_json(raw)
        if isinstance(intent, dict) and target_entity is not None:
            intent.setdefault("existing_ref", target_entity.hash)
            intent.setdefault("trigger", target_entity.trigger)
        intent = _coerce_semantic_frame_for_mode(intent, route_mode)
        if hooks.is_reprogramme_intent(intent):
            previous_doc = target_entity.payload if target_entity is not None else None
            output, code = hooks.execute_tool("tools/st_builder.py", intent)
            print(f"  st_builder: {output[:150]}")
            written_path = hooks.extract_written_path(output)
            if code == 0 and written_path:
                precommit_assessment = hooks.step_assessment(previous_doc, _load_json_doc(written_path), written_path)
                if _assessment_validator_ok(precommit_assessment):
                    commit_sha, _ = hooks.auto_commit(
                        f"reprogramme: {gap.desc[:50]}",
                        paths=[written_path],
                    )
                else:
                    _restore_written_step(written_path, previous_doc)
                    session.inject("## ST BUILDER FAILED\n" + "\n".join(precommit_assessment))
                    output = "\n".join(precommit_assessment)
                    code = 1
                    commit_sha = None
            else:
                commit_sha = None
            if commit_sha:
                print(f"  → committed: {commit_sha}")
                compiler.record_execution(vocab, True)
                step_result = Step.create(
                    desc=f"reprogrammed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    commit=commit_sha,
                    chain_id=entry.chain_id,
                )
                commit_path = None
                if written_path:
                    try:
                        commit_path = str(Path(written_path).resolve().relative_to(config.cors_root))
                    except ValueError:
                        commit_path = written_path
                postcond_refs = [f"{commit_sha}:{commit_path}"] if commit_path else [commit_sha]
                postcond = Gap.create(
                    desc=f"observe reprogramme commit:{commit_sha}",
                    content_refs=postcond_refs,
                    step_refs=[step_result.hash],
                )
                postcond.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
                postcond.vocab = "hash_resolve_needed"
                assessment_lines = hooks.commit_assessment(commit_sha)
                postcond_step = Step.create(
                    desc=f"postcondition: {gap.desc}",
                    step_refs=[step_result.hash],
                    content_refs=postcond_refs,
                    gaps=[postcond],
                    chain_id=entry.chain_id,
                    assessment=assessment_lines,
                )
                trajectory.append(postcond_step)
                compiler.emit(postcond_step)
                compiler.resolve_current_gap(gap.hash)
                print(f"  → postcondition gap injected: hash_resolve_needed → {postcond_refs}")
                if assessment_lines:
                    print("  → postcondition assessment:")
                    for line in assessment_lines:
                        print(f"    {line}")
            else:
                if code != 0:
                    session.inject(f"## ST BUILDER FAILED\n{output}")
                invalid_doc = _extract_invalid_generated_json(output) if code != 0 else None
                assessment_lines = []
                if code != 0:
                    first_error = next((line.strip()[2:] for line in output.splitlines() if line.strip().startswith("- ")), None)
                    if first_error:
                        assessment_lines.append(f"builder-error: {first_error}")
                if target_entity is not None:
                    assessment_lines.extend(hooks.step_assessment(target_entity.payload, invalid_doc or target_entity.payload, target_entity.source))
                step_result = _emit_rogue_with_diagnosis(
                    desc=f"reprogramme failed: {gap.desc}",
                    origin_step=origin_step,
                    gap=gap,
                    chain_id=entry.chain_id,
                    rogue_kind="validation_error" if code != 0 else "manifest_failure",
                    failure_source="st_builder",
                    trajectory=trajectory,
                    compiler=compiler,
                    failure_detail=output[:500] if output else None,
                    assessment=assessment_lines,
                )
                _auto_activate_debug_for_rogue(
                    registry=registry,
                    origin_step=origin_step,
                    rogue_step=step_result,
                    gap=gap,
                    chain_id=entry.chain_id,
                    rogue_kind="validation_error" if code != 0 else "manifest_failure",
                    failure_source="st_builder",
                    failure_detail=output[:500] if output else None,
                    trajectory=trajectory,
                    hooks=hooks,
                    compiler=compiler,
                    session=session,
                )
                compiler.resolve_current_gap(gap.hash, resolution_kind="rogue_handoff")
        else:
            print("  → no valid st_builder intent extracted")
            step_result = Step.create(
                desc=f"reprogramme skipped: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            compiler.resolve_current_gap(gap.hash)

    else:
        print(f"  → unknown ({vocab})")
        if resolved_data:
            session.inject(f"## Context\n{resolved_data}")
        raw = session.call(f"Address gap:{gap.hash} \"{gap.desc}\". What's needed?")
        step_result, child_gaps = hooks.parse_step_output(
            raw,
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
        if child_gaps:
            compiler.emit(step_result)
        else:
            compiler.resolve_current_gap(gap.hash)

    if step_result:
        _record_step(step_result, entry=entry, trajectory=trajectory, compiler=compiler)

    if compiler.is_done():
        return ExecutionOutcome(control="break", step_result=step_result)

    return ExecutionOutcome(control="continue", step_result=step_result)
