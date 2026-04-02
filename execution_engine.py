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
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from compile import GovernorSignal, is_mutate, is_observe
from step import Epistemic, Gap, Step
import manifest_engine as me


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


@dataclass
class ExecutionConfig:
    cors_root: Path
    chains_dir: Path
    tool_map: dict[str, dict]
    deterministic_vocab: set[str]
    observation_only_vocab: set[str]


@dataclass
class ExecutionOutcome:
    control: str = "continue"
    step_result: Step | None = None


def _record_step(step_result: Step, *, entry: Any, trajectory: Any, compiler: Any) -> None:
    passive_appended = False
    for ref in step_result.content_refs:
        passive_chains = trajectory.find_passive_chains(ref)
        for pc in passive_chains:
            if pc.hash != (entry.chain_id if entry else None):
                trajectory.append_to_passive_chain(pc.hash, step_result)
                passive_appended = True
                print(f"  → appended to passive chain:{pc.hash[:8]}")
                break
        if passive_appended:
            break

    if not passive_appended:
        trajectory.append(step_result)
    compiler.add_step_to_chain(step_result.hash)
    print(f"  step:{step_result.hash}" + (f" commit:{step_result.commit}" if step_result.commit else ""))


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
    for ref in gap.content_refs:
        skill = registry.resolve(ref)
        if skill is not None:
            return skill
    return None


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
        clarify_step = Step.create(
            desc=f"clarification needed: {gap.desc}",
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            gaps=[gap],
            chain_id=entry.chain_id,
        )
        trajectory.append(clarify_step)
        return ExecutionOutcome(control="break", step_result=clarify_step)

    resolved_data = hooks.resolve_all_refs(gap.step_refs, gap.content_refs, trajectory)
    vocab = gap.vocab
    step_result: Step | None = None

    if vocab in config.observation_only_vocab:
        print(f"  → observation-only ({vocab})")
        if resolved_data:
            session.inject(f"## Resolved hash data for gap:{gap.hash}\n{resolved_data}")
        step_result = Step.create(
            desc=f"resolved: {gap.desc}",
            step_refs=[origin_step.hash],
            content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
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

        raw = session.call(
            f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps."
        )
        print(f"  LLM: {raw[:150]}...")
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

    elif vocab and is_mutate(vocab):
        policy = hooks.load_tree_policy()
        reroute_vocab = None
        for ref in gap.content_refs:
            rule = hooks.match_policy(ref, policy)
            if rule and rule.get("on_mutate") and rule["on_mutate"] != vocab:
                reroute_vocab = rule["on_mutate"]
                break
        if not reroute_vocab:
            for path_prefix, rule in policy.items():
                if rule.get("on_mutate") and path_prefix.rstrip("/") in gap.desc.lower():
                    if rule["on_mutate"] != vocab:
                        reroute_vocab = rule["on_mutate"]
                        break
        if not reroute_vocab and vocab != "reprogramme_needed":
            if any(ref.endswith(".st") or registry.resolve(ref) is not None for ref in gap.content_refs):
                reroute_vocab = "reprogramme_needed"
            elif ".st" in gap.desc.lower():
                reroute_vocab = "reprogramme_needed"

        if reroute_vocab:
            print(f"  → policy auto-route: {vocab} → {reroute_vocab}")
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

        if vocab == "hash_edit_needed":
            compose_prompt = (
                f"Compose a file edit to resolve this gap:\n"
                f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
                f"Respond with JSON params for hash_manifest.py:\n"
                f'{{"action": "patch", "path": "relative/file/path", '
                f'"patch": {{"old": "exact text to replace", "new": "replacement text"}}}}\n\n'
                f"Or for a full rewrite:\n"
                f'{{"action": "write", "path": "relative/file/path", "content": "full file content"}}\n\n'
                f"Use the EXACT current file content for the 'old' field. Do not guess."
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

        if vocab == "hash_edit_needed":
            intent = hooks.extract_json(raw)
            if intent:
                output, code = hooks.execute_tool("tools/hash_manifest.py", intent)
                print(f"  → hash_manifest: {output[:100]}")
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
            step_result = Step.create(
                desc=f"FAILED: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            trajectory.append(step_result)
            compiler.add_step_to_chain(step_result.hash)
            return ExecutionOutcome(control="continue", step_result=step_result)

        if executed:
            commit_sha, on_reject = hooks.auto_commit(f"step: {gap.desc[:50]}")
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

                tool_conf = config.tool_map.get(vocab, {})
                post_observe = tool_conf.get("post_observe") if isinstance(tool_conf, dict) else None
                if post_observe:
                    tree_files = hooks.git(["ls-tree", "-r", "--name-only", commit_sha, post_observe], str(config.cors_root))
                    targeted_refs = [f"{commit_sha}:{f}" for f in tree_files.split("\n") if f.strip()]
                    postcond_refs = targeted_refs or [commit_sha]
                    postcond_desc = f"observe {post_observe}: {', '.join(postcond_refs)}"
                else:
                    postcond_refs = [commit_sha]
                    postcond_desc = f"observe commit:{commit_sha}"

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
                )
                trajectory.append(postcond_step)
                compiler.emit(postcond_step)
                compiler.resolve_current_gap(gap.hash)
                print(f"  → postcondition gap injected: hash_resolve_needed → {postcond_refs}")
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
                        )
                        trajectory.append(reject_step)
                        compiler.emit(reject_step)
                        compiler.resolve_current_gap(gap.hash)
                        return ExecutionOutcome(control="continue")
                    session.inject(
                        "## PROTECTED PATH VIOLATION\n"
                        "Your command tried to modify a protected system file. "
                        "The change was auto-reverted. Recompose your command to "
                        "only modify files in the workspace, not system files.\n"
                        f"Command output was:\n{output}"
                    )
                    step_result = Step.create(
                        desc=f"REVERTED: {gap.desc} (protected path violation)",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        chain_id=entry.chain_id,
                    )
                    trajectory.append(step_result)
                    compiler.add_step_to_chain(step_result.hash)
                    return ExecutionOutcome(control="continue", step_result=step_result)

                session.inject(f"## Command output (no mutation)\n{output}")
                step_result = Step.create(
                    desc=f"observed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                compiler.record_execution(vocab, False)
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

    elif vocab == "commit_needed":
        print("  → commit (end codon)")
        commit_skill = registry.resolve_by_name("commit")
        if commit_skill:
            session.inject(f"## Commitment reintegration: {gap.desc}")
            if resolved_data:
                session.inject(f"## Commitment chain data\n{resolved_data}")
            commit_step = Step.create(
                desc=f"commitment reintegrated: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=[commit_skill.hash] + gap.content_refs,
                chain_id=entry.chain_id,
            )
            for st_step in commit_skill.steps:
                child_gap = Gap.create(desc=st_step.desc, content_refs=gap.content_refs)
                child_gap.scores = Epistemic(
                    relevance=st_step.__dict__.get("relevance", 0.8),
                    confidence=0.8,
                    grounded=0.0,
                )
                child_gap.vocab = st_step.vocab
                child_gap.turn_id = current_turn
                commit_step.gaps.append(child_gap)
            trajectory.append(commit_step)
            compiler.emit(commit_step)
            compiler.resolve_current_gap(gap.hash)
            step_result = commit_step
        else:
            if resolved_data:
                session.inject(f"## Context\n{resolved_data}")
            raw = session.call(f"Reintegrate commitment: gap:{gap.hash} \"{gap.desc}\".")
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

    elif vocab == "reason_needed":
        print("  → reason (start codon)")
        reason_skill = registry.resolve_by_name("reason")
        if reason_skill:
            session.inject(f"## Reasoning activation: {gap.desc}")
            if resolved_data:
                session.inject(f"## Existing context\n{resolved_data}")
            session.inject(f"## Step Network\n{hooks.render_step_network(registry)}")
            raw = session.call(
                "Choose one manifestation for this reason_needed activation.\n"
                "Return JSON only.\n\n"
                "1. Emit the native reason codon:\n"
                '{"mode":"emit_reason_codon"}\n\n'
                "2. Submit a workflow skeleton for deterministic compilation:\n"
                '{"mode":"submit_skeleton","activation":"none|current_turn|background","skeleton":{...skeleton.v1...}}\n\n'
                "3. Activate an existing chain package by hash (.st skill hash or saved stepchain .json hash):\n"
                '{"mode":"activate_existing_chain","chain_ref":"hash","activation":"current_turn|background"}\n\n'
                "Use submit_skeleton when you are constructing a new action/workflow chain.\n"
                "Use activate_existing_chain when reusing an existing package.\n"
                "Use emit_reason_codon when you need the native reason.st toolset.\n"
                "If you activate background work, it will return through heartbeat reason_needed.\n"
                "If you submit a skeleton, it must be valid skeleton.v1."
            )
            intent = hooks.extract_json(raw) or {"mode": "emit_reason_codon"}
            mode = intent.get("mode", "emit_reason_codon")

            if mode == "submit_skeleton":
                skeleton = intent.get("skeleton")
                if isinstance(skeleton, dict) and skeleton.get("version") == "skeleton.v1":
                    output, code = hooks.execute_tool("tools/skeleton_compile.py", skeleton)
                    if code == 0:
                        compile_result = json.loads(output)
                        stepchain = compile_result["stepchain"]
                        package_hash = me.persist_chain_package(config.chains_dir, stepchain)
                        activation = intent.get("activation", "none")
                        session.inject(
                            "## Compiled chain package\n"
                            f"{me.render_chain_package(stepchain, package_hash)}"
                        )
                        if activation in {"current_turn", "background"}:
                            step_result = me.activate_chain_reference(
                                config.chains_dir,
                                package_hash,
                                activation,
                                gap,
                                origin_step,
                                entry.chain_id,
                                registry,
                                compiler,
                                trajectory,
                                current_turn,
                            )
                        else:
                            step_result = Step.create(
                                desc=f"compiled chain package:{package_hash} for {gap.desc}",
                                step_refs=[origin_step.hash],
                                content_refs=[package_hash] + gap.content_refs,
                                chain_id=entry.chain_id,
                            )
                    else:
                        session.inject(f"## Skeleton compile errors\n{output}")
                        step_result = hooks.emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                        trajectory.append(step_result)
                        compiler.emit(step_result)
                        compiler.add_step_to_chain(step_result.hash)
                        compiler.resolve_current_gap(gap.hash)
                        return ExecutionOutcome(control="continue")
                else:
                    step_result = hooks.emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                    trajectory.append(step_result)
                    compiler.emit(step_result)
                    compiler.add_step_to_chain(step_result.hash)
                    compiler.resolve_current_gap(gap.hash)
                    return ExecutionOutcome(control="continue")

            elif mode == "activate_existing_chain":
                chain_ref = intent.get("chain_ref")
                activation = intent.get("activation", "current_turn")
                if isinstance(chain_ref, str):
                    step_result = me.activate_chain_reference(
                        config.chains_dir,
                        chain_ref,
                        activation,
                        gap,
                        origin_step,
                        entry.chain_id,
                        registry,
                        compiler,
                        trajectory,
                        current_turn,
                    )
                if not step_result:
                    fallback = hooks.emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                    trajectory.append(fallback)
                    compiler.emit(fallback)
                    compiler.add_step_to_chain(fallback.hash)
                    compiler.resolve_current_gap(gap.hash)
                    return ExecutionOutcome(control="continue")
            else:
                step_result = hooks.emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                trajectory.append(step_result)
                compiler.emit(step_result)
                compiler.add_step_to_chain(step_result.hash)
                compiler.resolve_current_gap(gap.hash)
                return ExecutionOutcome(control="continue")

            if step_result:
                if step_result.gaps:
                    trajectory.append(step_result)
                    compiler.emit(step_result)
                compiler.resolve_current_gap(gap.hash)
        else:
            if resolved_data:
                session.inject(f"## Context\n{resolved_data}")
            raw = session.call(f"Reason about: gap:{gap.hash} \"{gap.desc}\". Articulate your reasoning chain.")
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
        target_entity = _entity_target_for_reprogramme(gap, registry)
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
        raw = session.call(
            f"You need to reprogramme your knowledge: gap:{gap.hash} \"{gap.desc}\"\n\n"
            "## Known entities (reference by hash, use as building blocks)\n"
            f"{entity_list}\n\n"
            "## Available /command workflows\n"
            f"{cmd_list}\n\n"
            "## Compose semantic state for a .st package\n\n"
            "Treat .st as step manifestation, not as plain file content.\n"
            "Your job here is to persist semantic state that keeps the system informed over time.\n\n"
            "### Structural distinction\n"
            "- entity.st: manifests primarily as semantic/context injection.\n"
            "- action.st: manifests primarily as executable step flow.\n"
            "- In this branch you may create or update entity state directly.\n"
            "- You may only edit an existing action package if the user explicitly asked.\n"
            "- You may not originate a new action workflow here.\n\n"
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
            "- Existing action updates: preserve explicit steps and refs; do not invent new workflow vocab\n\n"
            "### Entity format continuity\n"
            "When updating an existing entity, preserve its established file shape unless the user explicitly asked to change structure.\n"
            "- Preserve trigger, refs, and deterministic steps by default.\n"
            "- Preserve access_rules, init state, and other scaffolding fields that already exist.\n"
            "- Prefer additive semantic updates over rewriting desc or collapsing structure.\n"
            "- Do not replace a structured entity with steps: [] unless the user explicitly wants that simplification.\n"
            "- If you are updating an existing entity package, keep its manifestation pattern stable.\n\n"
            "### Contact identity continuity\n"
            "- If this gap is about updating an existing user/contact identity, update that existing entity in place.\n"
            "- Do not create a second on_contact entity for the same external contact.\n"
            "- Reuse the existing trigger and include existing_ref when you are updating a known entity.\n\n"
            "### Composition rule\n"
            "Compose from existing entities and workflows first. Reuse known hashes where possible.\n"
            "If you need executable structure, reference an existing action or chain package by hash.\n"
            "Only include steps when updating an already existing executable package.\n\n"
            "### Runtime note\n"
            "Entity-like packages usually manifest as semantic injection when resolved.\n"
            "Action-like packages belong to the structural workflow side of the system.\n"
            "Current persistence path still writes JSON .st files through st_builder.\n\n"
            "### Entity references\n"
            "Reference other entities by hash, not name.\n"
            'Use refs to map names to hashes: {"admin": "72b1d5ffc964"}\n\n'
            "### Triggers\n"
            "- manual: only when explicitly invoked\n"
            "- on_contact:X: fires when user X messages\n"
            "- command:X: hidden from LLM, triggered via /X command only\n\n"
            "```json\n"
            '{"artifact_kind": "entity | action_update | hybrid_update",\n'
            ' "name": "entity_name", "desc": "what this semantic package is",\n'
            ' "trigger": "manual | on_contact:X | command:X",\n'
            ' "refs": {"entity_name": "entity_hash", "chain_name": "chain_hash"},\n'
            ' "existing_ref": "required only for action_update/hybrid_update",\n'
            ' "steps": [\n'
            '   {"action": "step_name", "desc": "what this existing step does",\n'
            '    "vocab": "hash_resolve_needed", "post_diff": false, "resolve": ["hash"]}\n'
            ' ],\n'
            ' "identity": {}, "preferences": {}, "constraints": {}, "sources": [], "scope": ""}\n'
            "```\n"
            "Only include fields relevant to this semantic package. Omit empty fields.\n"
            "Do not invent new action workflows here. For executable updates, include existing_ref."
        )
        print(f"  LLM compose: {raw[:150]}...")
        intent = hooks.extract_json(raw)
        if isinstance(intent, dict) and target_entity is not None:
            intent.setdefault("existing_ref", target_entity.hash)
            intent.setdefault("trigger", target_entity.trigger)
        if hooks.is_reprogramme_intent(intent):
            output, code = hooks.execute_tool("tools/st_builder.py", intent)
            print(f"  st_builder: {output[:150]}")
            written_path = hooks.extract_written_path(output)
            commit_sha, _ = hooks.auto_commit(
                f"reprogramme: {gap.desc[:50]}",
                paths=[written_path] if written_path else None,
            )
            if commit_sha:
                print(f"  → committed: {commit_sha}")
                step_result = Step.create(
                    desc=f"reprogrammed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    commit=commit_sha,
                    chain_id=entry.chain_id,
                )
                compiler.resolve_current_gap(gap.hash)
            else:
                step_result = Step.create(
                    desc=f"reprogramme failed: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                compiler.resolve_current_gap(gap.hash)
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
