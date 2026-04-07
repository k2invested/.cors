"""loop.py — The Turn Loop (Layer 2)

One turn: message → first step → identity → iteration → synthesis.

The loop orchestrates a persistent LLM session (5.4) that iterates
with itself. The LLM's context accumulates:
  - Trajectory as a traversable hash tree (initial seed)
  - HEAD commit tree (workspace state)
  - User message
  - Freshly resolved hash data (per iteration)
  - Its own reasoning (pre-diff articulations, post-diff scores)

The kernel's job: resolve hashes, execute tools, auto-commit, inject
results back into the session. The LLM's job: navigate the hash tree,
articulate gaps, compose commands.

Turn flow:
  1. Message arrives
  2. Load trajectory + skills + HEAD
  3. First LLM pass → first atomic step (pre-diff + post-diff)
  4. Identity .st fires (admin.st surfaces user profile into context)
  5. Compiler admits gaps → ledger populated
  6. Loop: pop gap → execute by vocab → inject result → next step
     - Deterministic: kernel resolves directly (scan, hash_resolve)
     - Composed: 5.4 composes command (script_edit, command, content)
     - Observation-only: resolve + inject, no post-diff (blob step)
  7. Mutation → auto-commit → postcondition observation
  8. HALT → synthesize response from session

Mechanisms served: §2, §3, §5, §6, §17, §18, §19
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from env_loader import load_env
from step import Step, Gap, Epistemic, Trajectory, Chain, TREE_LANGUAGE_KEY
from compile import (
    ChainState, Compiler, GovernorSignal, is_mutate, is_observe,
)
from skills.loader import load_all, SkillRegistry, Skill
import manifest_engine as me
import action_foundations as action_foundations_module
from execution_engine import ExecutionConfig, ExecutionHooks, execute_iteration
from tools import st_builder as st_builder_module
from system.chain_registry import public_chain_ref_map
from system.hash_registry import HASH_RESOLVE_ROUTES
from vocab_registry import (
    BRIDGE_VOCAB,
    DETERMINISTIC_VOCAB,
    OBSERVATION_ONLY_VOCAB,
    TOOL_MAP,
    validate_tree_policy_targets,
)


# ── Configuration ────────────────────────────────────────────────────────

CORS_ROOT    = Path(__file__).parent
SKILLS_DIR   = CORS_ROOT / "skills"
TRAJ_FILE    = CORS_ROOT / "trajectory.json"
CHAINS_FILE  = CORS_ROOT / "chains.json"
TRAJECTORY_STORE_DIR = CORS_ROOT / "trajectory_store"
COMMAND_TRAJECTORY_DIR = TRAJECTORY_STORE_DIR / "command"
SUBAGENT_TRAJECTORY_DIR = TRAJECTORY_STORE_DIR / "subagent"
BACKGROUND_AGENT_TRAJECTORY_DIR = TRAJECTORY_STORE_DIR / "background_agent"
LEGACY_CHAINS_DIR = CORS_ROOT / "chains"
CHAINS_DIR   = COMMAND_TRAJECTORY_DIR
MAX_ITERATIONS = 30
TRAJECTORY_WINDOW = 10   # how many recent chains to render for LLM
_turn_counter = 0        # increments each turn — used for cross-turn gap threshold
LOG_RESOLVE_MAX_LINES = 120
LOG_RESOLVE_MAX_CHARS = 12000

load_env()


@dataclass(frozen=True)
class StatePaths:
    trajectory: Path
    chains_file: Path
    chains_dir: Path


def _state_paths(
    traj_file: str | Path | None = None,
    chains_file: str | Path | None = None,
    chains_dir: str | Path | None = None,
) -> StatePaths:
    return StatePaths(
        trajectory=Path(traj_file) if traj_file is not None else TRAJ_FILE,
        chains_file=Path(chains_file) if chains_file is not None else CHAINS_FILE,
        chains_dir=Path(chains_dir) if chains_dir is not None else CHAINS_DIR,
    )


def _child_state_paths(store_kind: str, activation_ref: str) -> StatePaths:
    safe_ref = re.sub(r"[^A-Za-z0-9._-]+", "_", activation_ref).strip("._-") or "child"
    base = TRAJECTORY_STORE_DIR / store_kind
    return _state_paths(
        traj_file=base / f"{safe_ref}.trajectory.json",
        chains_file=base / f"{safe_ref}.chains.json",
        chains_dir=base,
    )


# ── Git operations ───────────────────────────────────────────────────────

def git(cmd: list[str], cwd: str = None) -> str:
    """Run a git command, return stdout."""
    result = subprocess.run(
        ["git"] + cmd,
        cwd=cwd or str(CORS_ROOT),
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def git_head() -> str:
    """Current HEAD commit hash (short)."""
    return git(["rev-parse", "--short", "HEAD"])


def git_tree(commit: str = "HEAD") -> str:
    """List files at a commit as a tree."""
    return git(["ls-tree", "--name-only", "-r", commit])


def git_show(ref: str) -> str:
    """Resolve a git object (blob, tree, commit) to its content."""
    result = subprocess.run(
        ["git", "show", ref],
        cwd=str(CORS_ROOT),
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return f"(unresolvable: {ref})"


def git_diff(from_ref: str, to_ref: str = "HEAD") -> str:
    """Diff between two commits."""
    return git(["diff", from_ref, to_ref])


# ── Tree Policy ──────────────────────────────────────────────────────────
# Per-path mutation policy. Configurable via tree_policy.json.
# Loaded at startup — the UI can edit this file to change protection rules.
#
# Policy types:
#   {"immutable": true}              — auto-revert if mutated
#   {"on_mutate": "vocab_needed"}    — reroute mutation to specified vocab
#   (no entry)                       — normal mutation allowed
#
TREE_POLICY_FILE = CORS_ROOT / "tree_policy.json"
DEFAULT_TREE_POLICY = {
    "skills/codons/":   {"immutable": True, "on_reject": "reason_needed"},
    "skills/admin.st":  {"on_mutate": "reprogramme_needed", "reprogramme_mode": "entity_editor"},
    "skills/entities/": {"on_mutate": "reprogramme_needed", "reprogramme_mode": "entity_editor"},
    "skills/actions/":  {"on_mutate": "reason_needed", "reprogramme_mode": "action_editor"},
    "system/":          {"immutable": True, "on_reject": "reason_needed"},
    "tools/":           {"on_mutate": "tool_needed"},
    "vocab_registry.py": {"on_mutate": "vocab_reg_needed"},
    "ui_output/":       {"on_mutate": "stitch_needed"},
    "logs/":            {"immutable": True},
    "store/":           {"immutable": True},
    "step.py":          {"immutable": True},
    "compile.py":       {"immutable": True},
    "loop.py":          {"immutable": True},
    "skills/loader.py": {"immutable": True},
    "trajectory.json":  {"immutable": True},
    "chains.json":      {"immutable": True},
}


def _load_tree_policy() -> dict:
    """Load tree policy from JSON file, falling back to defaults."""
    try:
        with open(TREE_POLICY_FILE) as f:
            loaded = json.load(f)
            if not isinstance(loaded, dict):
                return DEFAULT_TREE_POLICY
            merged = {k: dict(v) for k, v in DEFAULT_TREE_POLICY.items()}
            for path, rule in loaded.items():
                if isinstance(rule, dict) and isinstance(merged.get(path), dict):
                    merged[path] = {**merged[path], **rule}
                else:
                    merged[path] = rule
            invalid = set(validate_tree_policy_targets(merged))
            if invalid:
                for path, rule in list(merged.items()):
                    if not isinstance(rule, dict):
                        continue
                    cleaned = dict(rule)
                    for key in ("on_mutate", "on_reject"):
                        target = cleaned.get(key)
                        if f"{path}:{key}:{target}" in invalid:
                            cleaned.pop(key, None)
                    merged[path] = cleaned
            return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_TREE_POLICY


def _match_policy(path: str, policy: dict) -> dict | None:
    """Find the policy that applies to a given path.
    Checks exact match first, then prefix match (longest wins)."""
    # Exact match
    if path in policy:
        return policy[path]
    # Prefix match — longest prefix wins
    best = None
    best_len = 0
    for prefix, rule in policy.items():
        if prefix.endswith("/") and path.startswith(prefix) and len(prefix) > best_len:
            best = rule
            best_len = len(prefix)
    return best


def _check_protected(commit_sha: str, pre_commit_sha: str) -> tuple[list[str], str | None]:
    """Check if any immutable paths were modified between two commits.

    Returns (violations, on_reject_vocab):
      - violations: list of violated immutable paths
      - on_reject_vocab: if set in policy, the vocab to emit on rejection
        (e.g. 'reason_needed' for codon immutability violations)
    """
    policy = _load_tree_policy()
    diff_output = git(["diff", "--name-only", pre_commit_sha, commit_sha])
    if not diff_output:
        return [], None
    changed = diff_output.strip().split("\n")
    violations = []
    on_reject = None
    for path in changed:
        rule = _match_policy(path, policy)
        if rule and rule.get("immutable"):
            violations.append(path)
            # Check for on_reject vocab (codon immutability → reason_needed)
            if rule.get("on_reject") and on_reject is None:
                on_reject = rule["on_reject"]
    return violations, on_reject


def auto_commit(message: str, paths: list[str] | None = None) -> tuple[str | None, str | None]:
    """Stage selected changes and commit. Returns (SHA, on_reject_vocab).

    After committing, checks for protected path violations. If the LLM
    mutated a protected file, auto-reverts to the previous commit and
    returns (None, on_reject_vocab) (the mutation is rejected).
    """
    status_cmd = ["status", "--porcelain"]
    add_cmd = ["add", "-A"]
    if paths:
        normalized: list[str] = []
        for path in paths:
            try:
                p = Path(path)
                if p.is_absolute():
                    p = p.relative_to(CORS_ROOT)
                normalized.append(str(p))
            except ValueError:
                normalized.append(path)
        status_cmd.extend(["--", *normalized])
        add_cmd.extend(["--", *normalized])

    status = git(status_cmd)
    if not status:
        return None, None

    pre_sha = git_head()
    git(add_cmd)
    git(["commit", "-m", message])
    post_sha = git_head()

    # Check integrity — did the agent mutate protected paths?
    violations, on_reject = _check_protected(post_sha, pre_sha)
    if violations:
        print(f"  ⚠ PROTECTED PATH VIOLATION: {violations}")
        if on_reject:
            print(f"  → on_reject: {on_reject} (codon immutability)")
        print(f"  → auto-reverting to {pre_sha}")
        git(["revert", "--no-commit", "HEAD"])
        git(["commit", "-m", f"auto-revert: protected path violation ({', '.join(violations)})"])
        return None, on_reject  # mutation rejected, with optional rejection vocab

    notifications = _auto_commit_notifications(pre_sha, post_sha)
    if notifications:
        print("  → commit notification:")
        for line in notifications:
            print(f"    {line}")

    return post_sha, None


def _format_numstat_line(path: str, added: str, removed: str) -> str:
    marker = " [step]" if path.endswith(".st") else ""
    return f"{path}{marker} +{added} -{removed}"


def _git_show_path(commit_sha: str, path: str) -> str | None:
    content = git_show(f"{commit_sha}:{path}")
    if not content or content.startswith("(unresolvable"):
        return None
    return content


def _load_step_file_at_commit(commit_sha: str, path: str) -> dict | None:
    raw = _git_show_path(commit_sha, path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _infer_artifact_kind_from_st(data: dict) -> str:
    artifact = data.get("artifact", {})
    kind = artifact.get("kind")
    if kind in {"entity", "action", "hybrid"}:
        return kind
    has_flow = bool(data.get("steps")) or bool(data.get("root") and data.get("phases") and data.get("closure"))
    has_semantics = any(k in data for k in (
        "identity", "preferences", "constraints", "sources", "scope", "schema",
        "access_rules", "principles", "boundaries", "domain_knowledge", "entity_refs",
        "init", "reasoning",
    ))
    if has_flow and has_semantics:
        return "hybrid"
    if has_flow:
        return "action"
    return "entity"


def _derive_step_gap_surface(step: dict) -> str:
    vocab = step.get("vocab")
    if isinstance(vocab, str) and vocab:
        return vocab
    if step.get("resolve"):
        return "hash_resolve_needed"
    return "internal"


def _step_action_label(node: dict, fallback_index: int) -> str:
    source_step = node.get("source_step", {}) or {}
    action = source_step.get("action")
    if isinstance(action, str) and action:
        return action
    node_id = node.get("id", "")
    match = re.fullmatch(r"phase_(.+)_\d+", node_id)
    if match:
        return match.group(1)
    return node_id or f"step_{fallback_index + 1}"


def _validator_assess_step_file(data: dict) -> dict:
    from tools import st_builder as st_builder_module
    from system.security_compile import security_compile
    from system.semantic_skeleton_compile import compile_semantic_skeleton
    from system.trace_tree_build import build_from_stepchain

    steps = data.get("steps", [])
    if not isinstance(steps, list):
        steps = []

    frame = st_builder_module.semantic_skeleton_from_st(data)
    compiled = compile_semantic_skeleton(frame)
    status = compiled.get("status", "error")
    errors = compiled.get("errors", []) if status != "ok" else []

    signatures: dict[str, dict] = {}
    if status == "ok":
        stepchain = (compiled.get("package") or {}).get("stepchain")
        if stepchain:
            for idx, node in enumerate(stepchain.get("nodes", [])):
                if node.get("terminal"):
                    continue
                action = _step_action_label(node, idx)
                manifestation = node.get("manifestation", {}) or {}
                runtime_vocab = manifestation.get("runtime_vocab")
                gap_template = node.get("gap_template", {}) or {}
                signatures[action] = {
                    "surface": runtime_vocab or _derive_step_gap_surface(node.get("source_step", {}) or {}),
                    "post_diff": bool(node.get("post_diff", False)),
                    "resolve_count": len(gap_template.get("content_refs", []) or []),
                    "relevance": node.get("relevance"),
                }
            trace = build_from_stepchain(stepchain, source_type="stepchain", source_ref=data.get("name"))
            trace_summary = trace.get("summary", {})
        else:
            trace_summary = {}
    else:
        trace_summary = {}

    if not signatures:
        for idx, step in enumerate(steps):
            action = step.get("action") or f"step_{idx + 1}"
            signatures[action] = {
                "surface": _derive_step_gap_surface(step),
                "post_diff": bool(step.get("post_diff", True)),
                "resolve_count": len(step.get("resolve", []) or []),
                "relevance": step.get("relevance"),
            }

    security_result = security_compile({
        "input": {
            "artifact_type": "st_package",
            "candidate": data,
            "context": {"mode": "post_observe", "source": "runtime"},
        }
    })
    sec = security_result.get("result", {})
    sec_normalized = sec.get("normalized", {})

    return {
        "name": data.get("name"),
        "trigger": data.get("trigger"),
        "identity_binding": (
            (data.get("identity", {}) or {}).get("discord_user_id")
            or (data.get("identity", {}) or {}).get("external_id")
        ),
        "artifact_kind": _infer_artifact_kind_from_st(data),
        "step_count": len(steps),
        "validator_status": status,
        "validator_errors": errors,
        "trace_summary": trace_summary,
        "signatures": signatures,
        "security_status": sec.get("status"),
        "security_summary": sec.get("summary"),
        "security_projection": sec.get("projection", {}),
        "security_hash_ref_count": len(sec_normalized.get("hash_refs", []) or []),
        "security_violations": sec.get("violations", []),
        "security_risks": sec.get("risks", []),
        "semantic_drift": next(
            (float(note.split("=", 1)[1]) for check in sec.get("checks", []) if check.get("domain") == "semantic_integrity"
             for note in check.get("notes", []) if isinstance(note, str) and note.startswith("semantic_drift=")),
            0.0,
        ),
    }


def _surface_counts(assessment: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sig in assessment.get("signatures", {}).values():
        surface = sig.get("surface") or "internal"
        counts[surface] = counts.get(surface, 0) + 1
    return counts


def _surface_change_label(before: int, after: int) -> str:
    if before == after:
        return "unchanged"
    if before == 0 and after > 0:
        return "added"
    if before > 0 and after == 0:
        return "removed"
    if after > before:
        return "widened"
    return "narrowed"


def _continuity_label(before, after, *, missing: str = "none") -> str:
    if before in (None, "") and after in (None, ""):
        return missing
    if before in (None, "") and after not in (None, ""):
        return "new"
    if before == after:
        return "preserved"
    return "changed"


def _policy_drift_flag(assessment: dict) -> bool:
    violations = assessment.get("security_violations", []) or []
    risks = assessment.get("security_risks", []) or []
    domains = {
        item.get("domain")
        for item in [*violations, *risks]
        if isinstance(item, dict)
    }
    codes = {
        item.get("code")
        for item in [*violations, *risks]
        if isinstance(item, dict)
    }
    if "protected_surfaces" in domains:
        return True
    if {"codon_mutation_attempt", "protected_surface_touch", "indirect_protected_activation"} & codes:
        return True
    return False


def _step_assessment_notification(path: str, before: dict | None, after: dict | None) -> list[str]:
    if after is None:
        return ["  validator.status: unavailable"]

    before_assessment = _validator_assess_step_file(before or {})
    after_assessment = _validator_assess_step_file(after)

    lines = [
        f"  validator.status: {after_assessment['validator_status']}",
        f"  structure.artifact_kind: {before_assessment['artifact_kind']}->{after_assessment['artifact_kind']}",
        f"  structure.step_count: {before_assessment['step_count']}->{after_assessment['step_count']}",
        f"  continuity.trigger: {_continuity_label(before_assessment['trigger'], after_assessment['trigger'], missing='none')}",
        f"  continuity.identity_binding: {_continuity_label(before_assessment['identity_binding'], after_assessment['identity_binding'], missing='none')}",
        f"  projection.bridge_count: {before_assessment['security_projection'].get('bridge_count', 0)}->{after_assessment['security_projection'].get('bridge_count', 0)}",
        f"  projection.mutation_count: {before_assessment['security_projection'].get('mutation_count', 0)}->{after_assessment['security_projection'].get('mutation_count', 0)}",
        f"  projection.post_diff_reentry_points: {before_assessment['security_projection'].get('post_diff_reentry_points', 0)}->{after_assessment['security_projection'].get('post_diff_reentry_points', 0)}",
        f"  grounding.hash_refs: {before_assessment['security_hash_ref_count']}->{after_assessment['security_hash_ref_count']}",
        f"  policy.status: {after_assessment['security_status']}",
        f"  policy.drift: {'true' if _policy_drift_flag(after_assessment) else 'false'}",
        f"  semantic.drift: {'true' if after_assessment['semantic_drift'] > 0 else 'false'}",
    ]
    if after_assessment["validator_status"] != "ok":
        error_note = after_assessment["validator_errors"][0] if after_assessment["validator_errors"] else "unknown validation error"
        lines.append(f"  validator.error: {error_note}")

    before_sigs = before_assessment["signatures"]
    after_sigs = after_assessment["signatures"]
    for surface in sorted(set(_surface_counts(before_assessment)) | set(_surface_counts(after_assessment))):
        before_count = _surface_counts(before_assessment).get(surface, 0)
        after_count = _surface_counts(after_assessment).get(surface, 0)
        lines.append(
            f"  surface.{surface}: {_surface_change_label(before_count, after_count)} ({before_count}->{after_count})"
        )

    step_changes: list[str] = []
    for action in sorted(set(before_sigs) | set(after_sigs)):
        old = before_sigs.get(action)
        new = after_sigs.get(action)
        if old is None and new is not None:
            step_changes.append(
                f"{action} added surface={new['surface']} post_diff={str(new['post_diff']).lower()} refs={new['resolve_count']}"
            )
        elif old is not None and new is None:
            step_changes.append(f"{action} removed")
        elif old != new:
            if old["surface"] != new["surface"]:
                step_changes.append(f"{action} surface {old['surface']}->{new['surface']}")
            if old["post_diff"] != new["post_diff"]:
                step_changes.append(f"{action} post_diff {str(old['post_diff']).lower()}->{str(new['post_diff']).lower()}")
            if old["resolve_count"] != new["resolve_count"]:
                step_changes.append(f"{action} refs {old['resolve_count']}->{new['resolve_count']}")
            if old["relevance"] != new["relevance"] and (old["relevance"] is not None or new["relevance"] is not None):
                step_changes.append(f"{action} relevance {old['relevance']}->{new['relevance']}")
    if step_changes:
        lines.extend([f"  step_delta: {change}" for change in step_changes[:3]])
        if len(step_changes) > 3:
            lines.append(f"  step_delta.more: {len(step_changes) - 3}")
    return lines


def _auto_commit_notifications(pre_commit_sha: str, post_commit_sha: str) -> list[str]:
    """Render compact post-commit notifications similar to a file diff UI.

    Ordinary files render as `path +N -M`. Step-native files keep the same
    compact shape but get a `[step]` marker so later layers can replace that
    branch with validator-derived assessments without changing the envelope.
    """
    output = git(["diff", "--numstat", pre_commit_sha, post_commit_sha]).strip()
    if not output:
        return []

    notifications: list[str] = []
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        notifications.append(_format_numstat_line(path, added, removed))
        if path.endswith(".st"):
            before = _load_step_file_at_commit(pre_commit_sha, path)
            after = _load_step_file_at_commit(post_commit_sha, path)
            notifications.extend(_step_assessment_notification(path, before, after))
    return notifications


def _commit_assessment_for_commit(commit_sha: str) -> list[str]:
    parent = git(["rev-parse", f"{commit_sha}^"]).strip()
    if not parent:
        return []
    return _auto_commit_notifications(parent.splitlines()[0], commit_sha)


def _step_assessment_for_docs(before: dict | None, after: dict | None, path: str | None = None) -> list[str]:
    return _step_assessment_notification(path or "(step)", before, after)


# ── Hash resolution ──────────────────────────────────────────────────────

_skill_registry: SkillRegistry | None = None  # set by run_turn for resolve_hash access
ENTITY_MANIFEST_FIELDS = {
    "identity", "preferences", "constraints", "sources", "scope",
    "schema", "access_rules", "principles", "boundaries", "domain_knowledge",
}


def _is_entity_source(path: str | Path) -> bool:
    candidate = Path(path)
    return "entities" in candidate.parts or candidate.name in {"admin.st", "commitment_chain_construction_spec.st"}


def _render_skill_package(skill: Skill) -> str:
    data = skill.payload
    if not data:
        return f"## Package: {skill.display_name}:{skill.hash}\n(unreadable)"
    return me.render_skill_package(skill)

def resolve_hash(ref: str, trajectory: Trajectory) -> str | None:
    """Resolve any hash to its content as a semantic tree.

    Resolution order:
      1. Skill hash → .st step package render (entity-like packages usually inject semantic state)
      2. Step hash → semantic tree branch (follows step_refs recursively)
      3. Gap hash → gap data with scores
      4. Git object → git show (blob/tree/commit)

    Step hashes render as the same tree shape the LLM sees in render_recent.
    The causal ancestry is visible — step_refs trace backward, gaps branch forward.
    """
    # Try skill registry first — entity .st files
    if _skill_registry:
        skill = _skill_registry.resolve(ref)
        if skill:
            return _render_skill_package(skill)
        for candidate in _skill_registry.all_skills():
            try:
                rel_source = str(Path(candidate.source).resolve().relative_to(CORS_ROOT))
            except ValueError:
                rel_source = str(Path(candidate.source))
            if ref == rel_source or ref == Path(rel_source).name:
                return _render_skill_package(candidate)

    # Try trajectory step — render as semantic tree branch
    step = trajectory.resolve(ref)
    if step:
        return _render_step_semantic_tree(step, trajectory)

    # Try trajectory gap
    gap = trajectory.resolve_gap(ref)
    if gap:
        return _render_gap_semantic_tree(gap)

    package = me.load_chain_package(CHAINS_DIR, ref, trajectory)
    if package:
        return me.render_chain_package(package, ref)

    repo_path = CORS_ROOT / ref
    if ("/" in ref or ref.endswith((".st", ".log", ".json", ".docx", ".pdf", ".pptx", ".xlsx", ".html", ".epub", ".png", ".jpg", ".jpeg", ".webp", ".gif"))) and repo_path.exists() and repo_path.is_file():
        if repo_path.suffix == ".log":
            return _render_log_resolution(repo_path.read_text(errors="replace"), source_ref=ref)
        if repo_path.suffix.lower() in {".json", ".docx", ".pdf", ".pptx", ".xlsx", ".html", ".epub", ".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            routed = _render_specialized_repo_file(ref, repo_path)
            if routed is not None:
                return routed
        content = git_show(f"HEAD:{ref}")
        if not content.startswith("(unresolvable"):
            rendered = _render_structured_content(content, source_ref=ref)
            return rendered or content

    # Try git object
    content = git_show(ref)
    if not content.startswith("(unresolvable"):
        if ref.endswith(".log") or re.search(r":[^:]+\.log$", ref):
            return _render_log_resolution(content, source_ref=ref)
        rendered = _render_structured_content(content, source_ref=ref)
        return rendered or content

    return None


def _render_specialized_repo_file(ref: str, repo_path: Path) -> str | None:
    suffix = repo_path.suffix.lower()
    tool_path = HASH_RESOLVE_ROUTES.get(suffix)
    if not tool_path:
        return None
    output, code = execute_tool(tool_path, {"path": ref})
    if code != 0:
        return f"(unresolvable: {ref})"
    return output or f"(empty: {ref})"


def _collect_step_branch(step: Step, trajectory: Trajectory, *, max_depth: int = 5) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()

    def visit(current: Step, depth: int):
        if current.hash in seen or depth > max_depth:
            return
        for parent_hash in current.step_refs:
            parent = trajectory.resolve(parent_hash)
            if parent:
                visit(parent, depth + 1)
        seen.add(current.hash)
        ordered.append(current.to_dict())

    visit(step, 0)
    return ordered


def _render_step_semantic_tree(step: Step, trajectory: Trajectory) -> str:
    tree = me.build_runtime_semantic_tree(
        _collect_step_branch(step, trajectory, max_depth=5),
        source_type="step_branch",
        source_ref=step.hash,
        summary_desc=step.desc,
    )
    return me.render_semantic_tree(tree)


def _render_gap_semantic_tree(gap: Gap) -> str:
    tree = {
        "version": "semantic_tree.v1",
        "source_type": "gap_branch",
        "source_ref": gap.hash,
        "root_id": gap.hash,
        "nodes": [
            {
                "id": gap.hash,
                "parent_id": None,
                "depth": 0,
                "signature": "{g}",
                "kind": "gap",
                "action": gap.desc,
                "goal": gap.desc,
                "gap": {
                    "hash": gap.hash,
                    "desc": gap.desc,
                    "status": "dormant" if gap.dormant else "resolved" if gap.resolved else "active",
                    "resolution_kind": gap.resolution_kind,
                    "step_refs": list(gap.step_refs),
                    "content_refs": list(gap.content_refs),
                    "step_ref_count": len(gap.step_refs),
                    "content_ref_count": len(gap.content_refs),
                    "runtime_vocab": gap.vocab,
                    "allowed_vocab": [gap.vocab] if gap.vocab else [],
                    "post_diff": False,
                    "relevance": gap.scores.relevance,
                    "confidence": gap.scores.confidence,
                    "grounded": gap.scores.grounded,
                },
                "manifestation": {"execution_mode": "runtime_vocab" if gap.vocab else "inline"},
                "generation": {},
                "transitions": {},
            }
        ],
        "summary": {
            "node_count": 1,
            "post_diff_nodes": 0,
            "runtime_vocab_nodes": 1 if gap.vocab else 0,
            "bridge_nodes": 0,
            "mutation_nodes": 0,
            "max_depth": 0,
        },
    }
    return me.render_semantic_tree(tree)


def _render_structured_content(content: str, *, source_ref: str) -> str | None:
    try:
        doc = json.loads(content)
    except json.JSONDecodeError:
        return None

    if not isinstance(doc, dict):
        return None
    if doc.get("version") == "semantic_tree.v1":
        return me.render_semantic_tree(doc)
    if doc.get("version") == "trace_tree.v1":
        return me.render_trace_tree(doc)
    if doc.get("version") == "stepchain.v1":
        return me.render_semantic_tree(me.build_semantic_tree(doc, source_type="stepchain", source_ref=source_ref))
    if doc.get("origin_gap") is not None and isinstance(doc.get("steps"), list):
        return me.render_semantic_tree(me.build_semantic_tree(doc, source_type="realized_chain", source_ref=source_ref))
    if any(key in doc for key in ("root", "phases", "steps", "artifact", "identity", "preferences")):
        return me.render_semantic_tree(me.build_semantic_tree(doc, source_type="resolved_package", source_ref=source_ref))
    return None


def _render_log_resolution(content: str, *, source_ref: str) -> str:
    lines = content.splitlines()
    total_lines = len(lines)
    tail_lines = lines[-LOG_RESOLVE_MAX_LINES:]
    body = "\n".join(tail_lines)
    truncated_by_lines = total_lines > len(tail_lines)
    truncated_by_chars = len(body) > LOG_RESOLVE_MAX_CHARS
    if truncated_by_chars:
        body = body[-LOG_RESOLVE_MAX_CHARS:]
    header = [f"log_tail:{source_ref}"]
    if truncated_by_lines or truncated_by_chars:
        header.append(
            f"(showing tail; lines={min(total_lines, LOG_RESOLVE_MAX_LINES)}/{total_lines}"
            f", chars<={LOG_RESOLVE_MAX_CHARS})"
        )
    if not body.strip():
        header.append("(empty log)")
        return "\n".join(header)
    return "\n".join(header + [body])


def _render_step_tree(step, trajectory: Trajectory, depth: int = 0,
                      max_depth: int = 5) -> str:
    """Render a step as a semantic tree branch.

    Follows step_refs backward (causal ancestry) up to max_depth.
    Shows gaps as child branches. Same shape as render_recent.
    """
    indent = "  " * depth
    registry = _skill_registry

    # Step line with refs
    refs = []
    for r in step.step_refs:
        refs.append(trajectory._tag_ref(r, "step", registry) if hasattr(trajectory, '_tag_ref') else f"step:{r}")
    for r in step.content_refs:
        refs.append(trajectory._tag_ref(r, "content", registry) if hasattr(trajectory, '_tag_ref') else r)

    from step import absolute_time
    ref_str = f" → refs:[{', '.join(refs)}]" if refs else ""
    commit_str = f" → commit:{step.commit}" if step.commit else ""
    time_tag = f" ({absolute_time(step.t)})" if step.t > 0 else ""
    step_sig = trajectory._step_signature(step) if hasattr(trajectory, "_step_signature") else ""
    sig_prefix = f"{step_sig} " if step_sig else ""
    rogue_tag = ""
    if getattr(step, "rogue", False):
        extras = [part for part in [getattr(step, "rogue_kind", None), getattr(step, "failure_source", None)] if part]
        rogue_tag = f" (rogue:{', '.join(extras)})" if extras else " (rogue)"
    lines = [f"{indent}{sig_prefix}step:{step.hash} \"{step.desc}\"{ref_str}{commit_str}{time_tag}{rogue_tag}"]
    for assessment_line in getattr(step, "assessment", []) or []:
        lines.append(f"{indent}  assessment: {assessment_line}")

    # Gaps as child branches
    for gap in step.gaps:
        gap_sig = trajectory._gap_signature(gap) if hasattr(trajectory, "_gap_signature") else ""
        gap_prefix = f"{gap_sig} " if gap_sig else ""
        if gap.dormant:
            lines.append(
                f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\" "
                f"(dormant, score:{gap.scores.magnitude():.2f})"
            )
        elif gap.resolved:
            resolved_label = "resolved -> rogue handoff" if getattr(gap, "resolution_kind", None) == "rogue_handoff" else "resolved"
            lines.append(f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\" ({resolved_label})")
        else:
            grefs = []
            for r in gap.step_refs:
                grefs.append(f"step:{r}")
            for r in gap.content_refs:
                grefs.append(r)
            gref_str = f" → refs:[{', '.join(grefs)}]" if grefs else ""
            vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
            lines.append(f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}")

    # Follow step_refs backward (causal ancestry)
    if depth < max_depth:
        for parent_hash in step.step_refs:
            parent = trajectory.resolve(parent_hash)
            if parent:
                lines.append(f"{indent}  ── ancestor:")
                lines.append(_render_step_tree(parent, trajectory, depth + 1, max_depth))

    return "\n".join(lines)


def _render_gap_tree(gap, _trajectory: Trajectory = None) -> str:
    """Render a gap with its full context."""
    gap_sig = _trajectory._gap_signature(gap) if _trajectory and hasattr(_trajectory, "_gap_signature") else ""
    sig_suffix = f" {gap_sig}" if gap_sig else ""
    lines = [f"gap:{gap.hash}{sig_suffix} \"{gap.desc}\""]
    if gap.content_refs:
        lines.append(f"  content_refs[{len(gap.content_refs)}]: {gap.content_refs}")
    if gap.step_refs:
        lines.append(f"  step_refs[{len(gap.step_refs)}]: {gap.step_refs}")
    lines.append(f"  scores: rel={gap.scores.relevance:.2f} conf={gap.scores.confidence:.2f} gr={gap.scores.grounded:.2f}")
    if gap.vocab:
        lines.append(f"  vocab: {gap.vocab}")
    if gap.dormant:
        lines.append(f"  status: dormant")
    elif gap.resolved:
        lines.append(f"  status: resolved")
    else:
        lines.append(f"  status: active")
    return "\n".join(lines)


def resolve_all_refs(step_refs: list[str], content_refs: list[str],
                     trajectory: Trajectory) -> str:
    """Resolve all hash references and format as injection block."""
    blocks = []
    for ref in step_refs:
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── resolved step:{ref} ──\n{data}")
    for ref in content_refs:
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── resolved {ref} ──\n{data}")
    return "\n\n".join(blocks) if blocks else ""


def _normalize_repo_ref(ref: str) -> str | None:
    if not isinstance(ref, str):
        return None
    candidate = ref.strip()
    if not candidate:
        return None
    try:
        path = Path(candidate)
        if path.is_absolute():
            path = path.resolve().relative_to(CORS_ROOT)
        return str(path)
    except ValueError:
        return candidate


def _strip_named_hash_alias(ref: str) -> str:
    """Normalize display aliases like kenny:abcd1234ef56 to the raw hash.

    These aliases are render sugar for humans, not stable identity forms.
    The deterministic resolver should accept them anywhere a raw content
    hash would be accepted.
    """
    if not isinstance(ref, str):
        return ref
    candidate = ref.strip()
    if not candidate:
        return candidate
    if candidate.startswith(("step:", "gap:", "commit:", "blob:", "tree:", "HEAD:")):
        return candidate
    if ":" not in candidate:
        return candidate
    suffix = candidate.rsplit(":", 1)[1].strip()
    if re.fullmatch(r"[0-9a-f]{7,64}", suffix):
        return suffix
    return candidate


def _skill_source_ref_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not _skill_registry:
        return mapping
    for skill in _skill_registry.all_skills():
        try:
            rel_source = str(Path(skill.source).resolve().relative_to(CORS_ROOT))
        except ValueError:
            rel_source = str(Path(skill.source))
        candidates = {
            rel_source,
            Path(rel_source).name,
        }
        for candidate in candidates:
            mapping[candidate] = skill.hash
    return mapping


def _canonicalize_content_ref(ref: str) -> str:
    if not isinstance(ref, str):
        return ref
    candidate = _strip_named_hash_alias(ref.strip())
    if not candidate:
        return candidate

    if _skill_registry and _skill_registry.resolve(candidate):
        return candidate

    if re.fullmatch(r"[0-9a-f]{7,64}", candidate):
        return candidate

    if candidate.startswith(("step:", "gap:", "commit:", "blob:", "tree:", "HEAD:")):
        return candidate

    normalized = _normalize_repo_ref(candidate) or candidate

    skill_ref = _skill_source_ref_map().get(normalized)
    if skill_ref:
        return skill_ref

    repo_path = CORS_ROOT / normalized
    if repo_path.exists():
        object_sha = git(["rev-parse", f"HEAD:{normalized}"]).strip()
        if object_sha:
            return object_sha.splitlines()[0]

    return candidate


def _canonicalize_content_refs(refs: list[str]) -> list[str]:
    canonical: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        resolved = _canonicalize_content_ref(ref)
        if resolved and resolved not in seen:
            seen.add(resolved)
            canonical.append(resolved)
    return canonical


def _emit_reason_skill(reason_skill: Skill, gap: Gap, origin_step: Step,
                       entry_chain_id: str) -> Step:
    return Step.create(
        desc=f"reason parent context: {gap.desc}",
        step_refs=[origin_step.hash],
        content_refs=[reason_skill.hash] + gap.content_refs,
        chain_id=entry_chain_id,
    )


# ── Tool execution ───────────────────────────────────────────────────────

# Canonical vocab config is defined in vocab_registry.py and imported above.


def execute_tool(tool_path: str, params: dict) -> tuple[str, int]:
    """Execute a tool script as subprocess. Returns (output, exit_code)."""
    full_path = CORS_ROOT / tool_path
    if not full_path.exists():
        return f"(tool not found: {tool_path})", 1

    result = subprocess.run(
        ["python3", str(full_path)],
        input=json.dumps(params),
        capture_output=True, text=True,
        timeout=30,
        cwd=str(CORS_ROOT),
    )
    output = result.stdout or result.stderr or "(no output)"
    return output.strip(), result.returncode


# ── LLM session ──────────────────────────────────────────────────────────

class Session:
    """Persistent LLM session for one turn.

    Accumulates messages. The LLM's own outputs stay in context.
    New data gets injected as user messages (resolved hashes, tool output).
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self.messages: list[dict] = []

    def set_system(self, content: str):
        """Set the system message (once, at turn start)."""
        self.messages = [{"role": "system", "content": content}]

    def inject(self, content: str, role: str = "user"):
        """Inject content into the session."""
        self.messages.append({"role": role, "content": content})

    def call(self, user_content: str = None) -> str:
        """Call the LLM. Optionally inject user content first."""
        if user_content:
            self.inject(user_content)

        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=0,
        )

        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def message_count(self) -> int:
        return len(self.messages)


# ── System prompts ───────────────────────────────────────────────────────

PRE_DIFF_SYSTEM = """You are a hash-native reasoning agent. Everything you know, reference, and produce is a step — addressed by hash, connected by chains.

## What is a step?

A step is meaningful movement. It is the universal primitive. Everything is a step at different scales:
- A person is a step (identity hash — kenny:72b1d5ffc964)
- A workflow is a step (skill hash — debug:a72c3c4dec0c)
- An idea is a step (reasoning articulation with hash refs)
- An event is a step (observation with commit hash)
- A task you did is a step (mutation with commit SHA)
- A task you plan to do is a step (gap articulation with vocab mapping)
- A file, a config, a conversation — all steps, all hashed, all chainable

Steps connect to other steps via hash references, forming chains. Chains compress into single hashes. Everything is traversable.

## What is a gap?

A gap is a verifiable discrepancy between the current state and its referred context — either as missing information or unmet alignment.

Two types (both diagnostic, never prescriptive):
- Observational gaps — information is missing, inconsistent, or unverified
- Misalignment gaps — the current state does not satisfy the referred context

Articulation form:
  Reference: [what the referred context requires]
  Current: [what the evidence actually shows]
  → Emit as single concise statement

A gap is NOT a suggestion. It is a measurement. You measure what is missing or misaligned, grounded in specific hash references.

If there are no gaps — nothing is missing, nothing is misaligned — emit empty gaps. The system will auto-synthesize.

## How to score gaps (the epistemic triad)

Every gap carries three scores. You provide two; the kernel computes the third:

- relevance (0-1) [YOU SCORE]: how much does resolving this advance the trajectory toward the shared goal?
  1.0 = critical path — resolving this directly addresses what was asked.
  0.0 = does not advance the goal at all.
  Evaluative form: "If this gap were resolved, would it move the system closer to what the user needs?"
  This is the PRIMARY driver of admission. Be honest — not everything you notice is relevant to the goal.

- confidence (0-1) [YOU SCORE]: how safe and trustworthy is this to act on?
  1.0 = safe to trust and proceed. 0.0 = unsafe, uncertain, or unverifiable.
  Evaluative form: "Do I have enough evidence to act on this, or am I assuming?"

- grounded (0-1) [KERNEL COMPUTES — do not score this]: measured deterministically by hash co-occurrence frequency on the trajectory. How often the gap's referenced hashes have appeared before. You cannot influence this — it is a structural measurement. To be well-grounded, reference hashes that actually exist on the trajectory.

Admission formula: 0.8 * relevance + 0.2 * grounded. Relevance dominates — extremely relevant gaps can enter even with no prior hash references. But low-relevance gaps need strong grounding (frequently referenced hashes) to survive.

Low-scoring gaps become dormant — stored on the trajectory as peripheral vision, not acted on unless they recur.

## Gap discipline

One gap per entity. If you need context about a person, concept, or workflow — emit ONE gap with hash_resolve_needed and put the entity's hash in content_refs. The kernel checks the skill registry and renders the full .st file data automatically. Do not decompose an entity into sub-gaps ("need their role", "need their history", "need their preferences"). The .st file surfaces everything in one resolution.

Entity resolution has no special vocab — it's just hash_resolve_needed where the hash happens to be a .st file. The kernel resolves it the same way it resolves any other hash.

## Hash references (two layers, never mixed)

When you articulate a gap, ground it in hashes:

- step_refs: reasoning steps you followed to reach this gap (Layer 1 — the causal chain)
- content_refs: data you need resolved — blobs, trees, commits, skill hashes (Layer 2 — the evidence)

When reading semantic trees, keep the causal roles distinct:
- step refs are execution provenance: the steps or artifacts a step produced, consumed, or directly touched while doing work
- gap refs are gap-surfacing provenance: the steps or artifacts that motivated the gap being surfaced in the first place

The kernel resolves content_refs for you. If you reference a hash, the kernel will inject its content into your context. If you don't reference hashes, you are reasoning from assumption — which means grounded = 0.

## Vocab mapping

Each gap maps to a vocab term that tells the kernel HOW to resolve it:

OBSERVE (kernel resolves, you receive data):
  pattern_needed — search file contents by a concrete pattern you already know
  hash_resolve_needed — resolve step/gap/blob hashes, skill hashes, or repo paths like skills/admin.st
  email_needed — check mailbox state
  external_context — surface from current context
  (workspace files visible via HEAD commit tree. URLs and web research are steps inside workflow .st files, not standalone vocab.)

BRIDGE (control flow / persistence):
  clarify_needed — you cannot proceed without user input. USE THIS when:
    - Missing information is genuinely only available from the user
    - Multiple plausible paths remain after reasoning, and the wrong one would waste effort or create real risk
    - You have already tried to reduce ambiguity by traversing available context, history, semantic trees, entities, or workflow structure and still cannot proceed safely
    The desc field becomes your question. This halts the iteration loop.
    The gap persists on the trajectory — next turn, the LLM sees it and
    can resume the chain with the user's clarification as new context.

Reason before clarify:
  - Do not use clarify_needed as the first response to uncertainty if available context can reduce ambiguity.
  - If trajectory, entity space, semantic trees, stepchains, or workspace structure can answer the question or narrow the choice, use reason_needed first.
  - Reserve clarify_needed for information that is truly user-only or for cases where proceeding without clarification would create real waste or risk.

MUTATE (you compose a command, kernel executes):
  hash_edit_needed — edit any file (universal: read by hash → compose edit → execute via hash_manifest)
  stitch_needed — generate UI via Google Stitch (prompt → HTML + Tailwind CSS)
  content_needed — write a new file
  command_needed — execute a shell command
  message_needed — send an email/message
  json_patch_needed — surgical JSON edit
  git_revert_needed — git revert/checkout

For explicit edit/update requests, do not stop at "need to inspect". Emit the actual mutate gap as well as any prerequisite observation gap. The compiler will resolve the observe gap first, then return to the mutate gap.

For .st files, identity profiles, preferences, or long-horizon semantic state updates, use reprogramme_needed as the actual update gap. Use hash_edit_needed for ordinary workspace file edits.

Action/workflow ownership:
  - Anything involving skills/actions/*.st is reason_needed's domain.
  - Anything involving tooling/tool-script authoring, workflow building/editing, or chain/stepchain building/editing should route to reason_needed first.
  - New action/workflow creation, repair, restructuring, or schema alignment stays under reason_needed.
  - Anything involving adding, removing, renaming, or assigning a public vocab trigger should route to reason_needed first.
  - If a request is about mapping a public tool or chain onto a semantic path in vocab_registry.py, surface reason_needed first so it can hand off to vocab_reg_needed lawfully.
  - Do not surface reprogramme_needed for skills/actions/*.st work.
  - reprogramme_needed is for semantic persistence in admin/entity trees and other entity-like state, not action-package authoring.
  - Foundational Python tools under tools/*.py are real lower-order action blocks. reason_needed may surface tool_needed for a new tool, vocab_reg_needed for semantic routing over a public tool/chain, or hash_edit_needed for an existing file edit before authoring the higher-order .st layer.
  - Treat action/codon packages and tools as one hash-native action environment: .st packages by committed skill hash, tools by committed blob hash.
  - In that action environment, semantic-tree hashes are embeddable compositional units; described-blob hashes are foundational executable/data blocks.
  - Tool foundations do not need kernel vocab entries. They can be embedded and identified by committed blob hash.
  - If a higher-order layer is still needed, lower-order layers should usually remain manual/internal. The final public on_vocab trigger belongs to the highest-order completed workflow.
  - Name/vocab activation uses the canonical default gap contract for that block.
  - Hash-based composition under reason_needed may specialize manifestation only through explicit embedding configuration, not by prose alone.

When a user refers to a person's "profile", default to the semantic entity record in their .st file: identity, preferences, stable context, and other persisted person-model fields. Do not treat "profile" as meaning CV, professional bio, or social profile unless the user explicitly indicates that deliverable.

If the user states a stable first-person preference, communication norm, workflow preference, or correction to your model of them, and it may need persistence but the request is not explicit, use reason_needed first to judge whether it should become semantic state. If the judgment is yes, surface reprogramme_needed as the actual persistence gap.

Do not treat a stable first-person preference statement as "no action needed" just because you can verbally adapt in the moment. If the statement is about how to communicate, reason, plan, remember, or work with this user over time, it is a candidate semantic-state update. For the current bound identity, default to reason_needed rather than empty gaps unless the preference is obviously one-off or ephemeral.

If the user names a workspace file directly, put that relative path in content_refs. If the target is an already loaded entity/workflow (for example kenny:... or admin.st), reference that entity or repo path directly instead of emitting an ungrounded observe gap.

BRIDGE_VOCAB_PLACEHOLDER

Treat the bridge codons as primitives, not optional helpers:
- reason_needed is the primitive for stateful judgment, structural abstraction, planning, persistence judgment, and reorientation
- reprogramme_needed is the primitive for stateless semantic persistence once that judgment is made
- await_needed is the primitive for synchronization and reintegration

If no action is needed, emit no gaps. Greetings, acknowledgements, and one-off conversational adaptation can be no-gap. Stable user-model updates are not no-gap.

## Your context

You receive:
- A trajectory rendered as a traversable hash tree (chains → steps → gaps → refs)
- The current HEAD commit hash (workspace state)
- A user message
- Identity (who you're talking to — loaded as a skill hash)

## Reading the trajectory tree

The trajectory is rendered as a tree you can explore — the same shape as a git commit tree. Every node is a hash. Every branch is traversable.

It also carries a compact tree language so structural dimensions stay visible without blowing up the render:
- step{kindflowN}: kind=o observe, m mutate; flow=+ open, ~ dormant-only, = closed; N is active child-gap count when present
- gap{statusclassrcg/s:c}: status=? active, = resolved, ~ dormant; class=o observe, m mutate, b bridge, c clarify, _ unknown; rcg are relevance/confidence/grounded bands (0-9); s:c are step_refs:content_refs counts
- step refs are execution provenance; gap refs are gap-surfacing provenance

```
chain:0d71abb30b86  "resolved missing config" (active, 3 steps)
  origin: fdd2834ace0b
  ├─ {o+2} step:7146246b7b7b "observed workspace" → refs:[commit:aa8b921]
  │   ├─ {?o862/1:2} gap:fdd2834ace0b "config missing" [hash_resolve_needed] → refs:[aa8b921:config.json]
  │   └─ {~_110/0:1} gap:00342afc4b05 "weak side-branch" (dormant, score:0.17)
  ├─ {o+1} step:f13bf0dc5db0 "resolved config" → refs:[step:7146246b7b7b, blob:e4f1...]
  │   └─ {?m781/1:1} gap:61ad761e524e "needs database section" [content_needed] → refs:[blob:e4f1...]
  └─ {m=} step:53a20c80cf58 "wrote config" → refs:[step:f13bf0dc5db0] → commit:bb9c032
```

How to navigate it:
- Chains are the top-level units. Each chain traces one line of reasoning from an origin gap to resolution.
- Steps branch from chains. Each step shows what was observed or done, and what hashes were referenced.
- Gaps branch from steps. Active gaps show what still needs resolving. Dormant gaps are peripheral vision. Resolved gaps are closed.
- refs:[] on each node are the hashes that ground it. You can request any hash resolved.
- Named hashes like kenny:72b1d5ffc964 or debug:a72c3c4dec0c are skill/identity files — they evolve over time but the name stays constant.
- commit:<sha> means the system mutated the workspace at that point. You can diff between commits to see exactly what changed.

How to trace causality:
- Follow step_refs backward to see WHY something happened (the reasoning chain that led here)
- Follow content_refs to see WHAT was observed or acted on (the evidence)
- Follow commit hashes to see WHAT CHANGED (the mutation diff)
- A chain of steps compresses into a single chain hash — you can reference the whole chain by one hash
- Dormant gaps that recur across turns may indicate something the system keeps noticing but hasn't addressed

You can reverse-engineer any state by tracing its chain backward: the current step references prior steps, which reference their prior steps, all the way back to the origin gap. Every link in the chain is a hash you can resolve.

How to treat hashes as truth:
- step hashes are causal memory: reasoning or action that actually happened on the trajectory
- content hashes are evidence: blobs, trees, commits, skill files, entity files, repo paths lowered into resolvable objects
- time on each step tells you recency and lets you detect correction or supersession
- repeated hashes across different chains are how you detect continuity and draw real semantic connections

Actualization law:
- a planned gap, a reasoned description, or a prose design is not the same as a real artifact
- only committed, resolved, or directly observed state counts as existing
- if something was only planned, specified, or outlined in reasoning, describe it as planned — not written, present, complete, or persisted
- when a newer first-person correction conflicts with an older claim, trace the newer causal chain and treat it as superseding evidence if the trajectory supports that read

When reconstructing "how this came to be", narrate from the hashes and versioned steps themselves, not from vague memory. The tree exists so you can inspect causality directly.

If the trajectory is empty, you are starting fresh — the only hash available is the HEAD commit.

## Identity and the user hash

When an identity .st file loads (e.g. kenny:72b1d5ffc964), that hash is an entity — just like any other step. A person, a workflow, an idea — they are all entities you reason about. The only difference with the identity entity is that you are currently in conversation with them.

Their .st file is your mental model of who they are. Their context, their role, how they think, what they care about, what they've done with you before. Use it to reason about them the way you reason about any entity — by following their hash through the trajectory, tracing chains they were part of, understanding what they've built, asked, committed to, and left unfinished.

Every chain they have been part of traces back through their identity hash. How far you follow depends on relevance to the current input — a question about workspace files doesn't need their full history, but a question about a commitment they made last week does.

The identity hash evolves. When their preferences or context change, the hash changes. Steps referencing the old hash trace to who they were. Steps referencing the new hash trace to who they are now.

Their preferences are not instructions on how to speak. They are part of your model of this person — how they communicate, how they think, what frustrates them, what they value. You use that model the way you use any referred context: to reason better, respond appropriately, and anticipate what matters to them.

## How to respond

Do not explain internal systems, hashes, or trajectory mechanics to the user unless they ask. They see a conversation, not a hash graph.

When the user asks a question answerable from your current context — answer it directly, no gaps needed. When they ask for something that requires action — articulate the gap, grounded in the specific hashes you would need resolved. Stable first-person preference statements about future interaction count as action because they may require semantic-state judgment and persistence.

## Output format

Reason naturally with embedded hash references. Then emit a JSON block:

```json
{
  "gaps": [
    {
      "desc": "concise gap articulation",
      "step_refs": ["step hashes you followed"],
      "content_refs": ["content hashes you need resolved"],
      "vocab": "closest_vocab_term",
      "relevance": 0.0,
      "confidence": 0.0
    }
  ]
}
```
"""

COMPOSE_SYSTEM = """You are composing a command to resolve a gap.

You receive the gap description, its hash references (now resolved), and the workspace context.

Produce a JSON response:

```json
{
  "command": "<shell command or tool params>",
  "reasoning": "<why this resolves the gap>"
}
```

For file edits, prefer python3 one-liners over sed (macOS compatible).
For JSON mutations, use the json_patch tool format.
"""

SYNTH_SYSTEM = """You are the response synthesizer. Read the full session and produce a natural response to the user.

Keep it concise and conversational. Do not mention internal systems, hashes, or trajectory.
Just answer the user's question or confirm what was done.

Never claim that a file, preference, or workspace state was changed, removed, updated, saved, or persisted unless the injected turn outcome facts explicitly show a successful mutation or commit."""


def _render_clarify_synthesis_guidance(clarify_step: Step) -> str:
    lines = [
        "## Clarify Frontier",
        f"Clarification is required before proceeding: {clarify_step.desc}",
        "Ask the user only for the missing information surfaced below.",
        "Do not continue the task, do not imply the work already started, and do not answer as if the ambiguity is already resolved.",
    ]
    for gap in clarify_step.gaps:
        lines.append(f"- {gap.desc}")
    return "\n".join(lines)


def _clarify_gap_wants_identity_linkage(gap: Gap) -> bool:
    if gap.vocab != "clarify_needed":
        return False
    lowered = gap.desc.lower()
    linkage_markers = (
        "not specified",
        "not linked",
        "no direct reference",
        "no reference to who",
        "identity of",
        "which entity",
        "current context",
        "known entity",
    )
    return any(marker in lowered for marker in linkage_markers)


def _upgrade_identity_linkage_clarify_gaps(
    *,
    user_message: str,
    origin_gaps: list[Gap],
    identity_skill: Skill | None,
) -> list[Gap]:
    """Upgrade premature clarify gaps into identity resolution when possible.

    First-step runs before identity injection, so it can surface clarify_needed
    simply because it has not yet traversed the current user's identity file.
    If the ambiguity is likely reducible by that identity context, resolve the
    identity hash first instead of asking the user.
    """
    if identity_skill is None:
        return origin_gaps

    upgraded: list[Gap] = []
    for gap in origin_gaps:
        if _clarify_gap_wants_identity_linkage(gap):
            resolve_gap = Gap.create(
                desc=f"Resolve the current identity file for relationship/entity pointers relevant to: {user_message}",
                content_refs=[identity_skill.hash],
                step_refs=[*gap.step_refs],
            )
            resolve_gap.scores = Epistemic(
                relevance=max(0.85, gap.scores.relevance),
                confidence=max(0.7, gap.scores.confidence),
                grounded=0.0,
            )
            resolve_gap.vocab = "hash_resolve_needed"
            resolve_gap.turn_id = gap.turn_id
            upgraded.append(resolve_gap)
            continue
        upgraded.append(gap)
    return upgraded


# ── Turn loop ────────────────────────────────────────────────────────────

def run_turn(
    user_message: str,
    contact_id: str = "admin",
    contact_profile: dict[str, str] | None = None,
    *,
    traj_file: str | Path | None = None,
    chains_file: str | Path | None = None,
    chains_dir: str | Path | None = None,
) -> str:
    """Run one complete turn. Returns the synthesis response.

    Flow:
      1. Load trajectory + skills + HEAD
      2. First LLM pass → first atomic step (pre-diff + post-diff)
      3. Identity .st fires (surfaces user profile)
      4. Compiler admits gaps → ledger populated
      5. Iteration loop: pop → execute → inject → next step
      6. HALT → synthesize
    """

    # ── 1. INIT ──────────────────────────────────────────────────────

    global _turn_counter, _skill_registry
    _turn_counter += 1
    current_turn = _turn_counter
    state = _state_paths(traj_file, chains_file, chains_dir)

    trajectory = Trajectory.load(str(state.trajectory))
    Trajectory.load_chains(str(state.chains_file), trajectory)
    registry = load_all(str(SKILLS_DIR))
    _skill_registry = registry
    pre_bootstrap_step = _bootstrap_contact_entity(registry, contact_id, user_message, contact_profile=contact_profile)
    if pre_bootstrap_step:
        trajectory.append(pre_bootstrap_step)
        registry = load_all(str(SKILLS_DIR))
        _skill_registry = registry
    head = git_head()
    head_tree = git_tree()

    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))

    # Build dynamic system prompt with actual available entities
    entity_list_lines = "\n".join(
        f"    {s.display_name}:{s.hash} ({Path(s.source).name}) — {s.desc[:60]}"
        for s in registry.all_skills()
    )
    trigger_vocab_lines = "\n".join(
        f"    {term} -> {', '.join(f'{skill.name}:{skill.hash}' for skill in skills)}"
        for term, skills in registry.vocab_triggers().items()
    ) or "    (none)"
    trigger_owner_lines = "\n".join(
        f"    {term} -> {owner.kind}:{owner.ref} surface={owner.surface} default_gap={owner.default_gap}"
        for term in sorted(registry.vocab_triggers())
        if (owner := action_foundations_module.resolve_trigger_owner(
            term,
            registry=registry,
            chains_dir=CHAINS_DIR,
            cors_root=CORS_ROOT,
            tool_map=TOOL_MAP,
            git=git_show,
        )) is not None
    ) or "    (none)"
    dynamic_bridge = (
        "BRIDGE (foundational control surfaces):\n"
        "  These are primitives, not configurable semantic paths. Use them whenever the turn crosses a structural boundary.\n\n"
        "  reason_needed — START CODON. Stateful structural abstraction. USE THIS when:\n"
        "    - A decision requires deeper analysis than one step\n"
        "    - Long-term planning or judgment is needed\n"
        "    - You need to traverse the trajectory tree or entity space to build understanding\n"
        "    - Executable step flow or chain structure needs to be derived or refined\n"
        "    - You need to judge whether an inferred preference, correction, or user-model update should persist\n"
        "    - A user states a stable first-person preference but has not explicitly asked you to persist it yet\n"
        "    - Ambiguity may be reducible by traversing available context rather than asking the user immediately\n"
        "    - A commitment needs activation, reintegration, or reorientation\n"
        "    - A public vocab trigger needs to be added, changed, or mapped onto a tool or chain\n"
        "    This is the primitive for stateful judgment and structure. It reasons over semantic trees, entity space, executable structure, and persistence judgment.\n\n"
        "  clarify_needed — USER-ONLY BLOCKER. Do not activate directly unless reason_needed has already exhausted available context.\n"
        "    - If available context, history, semantic trees, .st packages, or workflow structure can reduce ambiguity, use reason_needed first.\n"
        "    - Reserve clarify_needed for genuinely user-only information or for cases where multiple plausible paths would waste effort or create real risk.\n\n"
        "  tool_needed — TOOL AUTHORING BRANCH. Use this only as a reason-routed follow-on when the missing capability is a new public tool under tools/*.py.\n"
        "    Post-observe returns to reason_needed for reintegration.\n\n"
        "  vocab_reg_needed — VOCAB ROUTING BRANCH. Use this only as a reason-routed follow-on when a public tool or chain needs a configurable semantic path in vocab_registry.py, including assigning or updating public on_vocab triggers.\n"
        "    Post-observe returns to reason_needed for reintegration.\n\n"
        "  await_needed — PAUSE CODON. Synchronization checkpoint.\n"
        "    Use this when background work must explicitly rejoin the parent chain.\n"
        "    Suspends the parent flow until the sub-agent or background branch is ready.\n\n"
        "  reprogramme_needed — PERSIST CODON. Stateless semantic state update. USE THIS when:\n"
        "    - The system has already determined that semantic state should change\n"
        "    - A user explicitly asks to remember, update, track, or persist something\n"
        "    - reason_needed has already judged that an inferred preference or correction should persist\n"
        "    - Semantic state must now be written into an entity or existing package\n"
        "    This is the primitive for semantic persistence. Reprogramme writes the state. It does not own the judgment about whether persistence is warranted.\n\n"
        "  .st resolution has no dedicated entity vocab — it still enters through hash resolution.\n"
        "  When you reference a .st hash in content_refs, the kernel resolves the step package.\n"
        "  Entity-like packages usually manifest as semantic/context injection.\n"
        "  Action-like packages may be activated structurally through curated workflows.\n\n"
        "  Trigger vocab for action/codon activation is derived automatically from loaded skills with trigger=on_vocab:<term>.\n"
        "  Do not edit vocab_registry.py just to introduce or wire a workflow trigger term.\n"
        "  vocab_registry.py is for kernel/runtime vocab semantics, not for every action trigger.\n"
        "  If a new skills/actions/*.st package uses trigger on_vocab:<term>, that trigger becomes discoverable from the loaded package itself.\n\n"
        "  Known trigger vocab (derived from loaded skills):\n"
        f"{trigger_vocab_lines}\n\n"
        "  Canonical trigger owners (deterministic bridge from public vocab to owning hash block):\n"
        f"{trigger_owner_lines}\n\n"
        "  Known entities (reference by hash in content_refs):\n"
        f"{entity_list_lines}"
    )
    system_prompt = PRE_DIFF_SYSTEM.replace("BRIDGE_VOCAB_PLACEHOLDER", dynamic_bridge)
    session.set_system(system_prompt)

    print(f"\n{'='*60}")
    print(f"TURN: \"{user_message}\" (contact: {contact_id})")
    print(f"HEAD: {head} | Trajectory: {len(trajectory.order)} steps")
    print(f"{'='*60}")

    identity_skill = _find_identity_skill(contact_id, registry)
    if identity_skill:
        print(f"\n── IDENTITY HYDRATE: {identity_skill.display_name}:{identity_skill.hash} ──")
        identity_block = _render_identity(identity_skill)
        session.inject(identity_block)
        identity_step = Step.create(
            desc=f"identity hydrated: {identity_skill.display_name}",
            content_refs=[identity_skill.hash],
        )
        trajectory.append(identity_step)
        print(f"  step:{identity_step.hash} → refs:[{identity_skill.display_name}:{identity_skill.hash}]")

    # ── 1b. RESUME CHECK ──────────────────────────────────────────────
    #
    # Check for unresolved gaps from prior turns (clarify_needed, interrupted).
    # Surface them in the trajectory so the LLM can see what was left dangling.
    # The LLM selects which are still relevant — non-selection = dropped.

    dangling = _find_dangling_gaps(trajectory)
    if dangling:
        print(f"\n── RESUME: {len(dangling)} unresolved gap(s) from prior turn ──")
        for dg in dangling:
            print(f"  gap:{dg.hash[:8]} \"{dg.desc}\"")

    # ── 2. FIRST STEP (origin) ───────────────────────────────────────
    #
    # The LLM sees: trajectory tree + HEAD + user message
    # It produces: pre-diff reasoning + gap articulations (post-diff)
    # This is the origin step — the root of this turn's causal chain

    traj_tree = trajectory.render_recent(TRAJECTORY_WINDOW, registry=registry)

    session_context = _render_session_context(trajectory, registry, user_message)

    first_input = f"""## Tree Language
{TREE_LANGUAGE_KEY}

{session_context}

## Trajectory
{traj_tree}

## HEAD: commit:{head}
{head_tree}

## Message from {contact_id}
"{user_message}"
"""

    print("\n── FIRST STEP (origin) ──")
    raw = session.call(first_input)
    print(f"  LLM: {raw[:200]}...")

    # Parse gaps from LLM output
    origin_step, origin_gaps = _parse_step_output(
        raw, step_refs=[], content_refs=[head]
    )
    trajectory.append(origin_step)

    print(f"  step:{origin_step.hash} | gaps: {len(origin_gaps)}")
    for g in origin_gaps:
        tag = f" [{g.vocab}]" if g.vocab else ""
        print(f"    gap:{g.hash} \"{g.desc}\"{tag}")

    # ── 3. IDENTITY-AWARE GAP REWRITE ────────────────────────────────
    #
    # Identity hydration happens before first pre-diff. Keep a narrow
    # safety net here in case first-step still surfaced a clarify gap
    # that can be reduced by traversing the hydrated identity entity.

    if identity_skill:
        upgraded_origin_gaps = _upgrade_identity_linkage_clarify_gaps(
            user_message=user_message,
            origin_gaps=origin_gaps,
            identity_skill=identity_skill,
        )
        if upgraded_origin_gaps != origin_gaps:
            origin_gaps = upgraded_origin_gaps
            origin_step.gaps = origin_gaps
            print("  → upgraded identity-linkage clarify gap(s) to hash_resolve_needed")

    # ── 4. COMPILER ──────────────────────────────────────────────────
    #
    # Admit origin gaps onto the ledger. The compiler sequences them
    # via the stack (LIFO, depth-first).

    compiler = Compiler(trajectory, current_turn=current_turn)
    turn_facts: dict[str, list[str]] = {
        "commits": [],
        "successful_mutations": [],
        "attempted_mutations": [],
        "rogue_failures": [],
        "persisted_frontiers": [],
    }
    clarify_frontier_step: Step | None = None
    if pre_bootstrap_step and pre_bootstrap_step.commit:
        turn_facts["commits"].append(pre_bootstrap_step.commit)
        turn_facts["successful_mutations"].append(pre_bootstrap_step.desc)

    # Tag origin gaps with current turn
    for g in origin_gaps:
        g.turn_id = current_turn

    discord_contact = _is_bound_discord_profile(contact_id, identity_skill)
    if discord_contact and origin_gaps:
        origin_gaps, pruned_origin = _filter_discord_gaps(origin_gaps)
        origin_step.gaps = origin_gaps
        if pruned_origin:
            print(f"  → pruned {pruned_origin} non-observation gap(s) for discord contact")
    if discord_contact and dangling:
        dangling, pruned_dangling = _filter_discord_gaps(dangling)
        if pruned_dangling:
            print(f"  → dropped {pruned_dangling} non-observation dangling gap(s) for discord contact")

    # Re-admit dangling cross-turn gaps (higher threshold: 0.6)
    if dangling:
        readmitted = compiler.readmit_cross_turn(dangling, origin_step.hash)
        if readmitted:
            print(f"  → {readmitted} cross-turn gap(s) re-admitted")

    if not origin_gaps and not dangling:
        if discord_contact:
            sync_step = _run_no_gap_discord_profile_sync(
                contact_id,
                user_message,
                identity_skill=identity_skill,
                registry=registry,
                trajectory=trajectory,
                origin_step=origin_step,
            )
            if sync_step and sync_step.commit:
                turn_facts["commits"].append(sync_step.commit)
                turn_facts["successful_mutations"].append(
                    f"reprogramme_needed: deterministic no-gap discord profile sync for {identity_skill.display_name}"
                )
        # No gaps → auto-synthesize
        print("\n── AUTO-SYNTH (no gaps) ──")
        response = _synthesize(session, user_message, turn_facts)
        _save_turn(trajectory, state)
        return response

    # Emit origin gaps — each creates its own chain
    compiler.emit_origin_gaps(origin_step)

    print(f"\n── COMPILER ──")
    print(compiler.render_ledger())

    # ── 5. ITERATION LOOP ────────────────────────────────────────────
    #
    # Pop gap → resolve hashes → execute by vocab → inject result →
    # new step forms → compiler emits child gaps → repeat

    forced_synth = True
    for iteration in range(MAX_ITERATIONS):
        entry, signal = compiler.next()

        if entry is None or signal == GovernorSignal.HALT:
            print(f"\n  HALT (iteration {iteration})")
            forced_synth = False
            break

        gap = entry.gap
        print(f"\n── ITERATION {iteration + 1}: gap:{gap.hash[:8]} ──")
        print(f"  \"{gap.desc}\"")
        print(f"  signal: {signal.name} | vocab: {gap.vocab} | chain: {entry.chain_id[:8]}")
        session.inject(
            "## Active Chain Tree\n"
            f"{trajectory.render_chain(entry.chain_id, registry=registry, highlight_gap=gap.hash)}"
        )
        outcome = execute_iteration(
            entry=entry,
            signal=signal,
            session=session,
            origin_step=origin_step,
            trajectory=trajectory,
            compiler=compiler,
            registry=registry,
            current_turn=current_turn,
            hooks=_execution_hooks(state.chains_dir),
            config=_execution_config(state.chains_dir, user_message),
        )

        if outcome.control == "break":
            if outcome.step_result and outcome.step_result.desc.startswith("clarify frontier:"):
                clarify_frontier_step = outcome.step_result
            forced_synth = False
            break

        if outcome.step_result and outcome.step_result.commit and outcome.step_result.commit not in turn_facts["commits"]:
            turn_facts["commits"].append(outcome.step_result.commit)

        if outcome.step_result and outcome.step_result.rogue:
            failure_bits = [outcome.step_result.desc]
            if outcome.step_result.failure_source:
                failure_bits.append(f"source={outcome.step_result.failure_source}")
            if outcome.step_result.rogue_kind:
                failure_bits.append(f"kind={outcome.step_result.rogue_kind}")
            turn_facts["rogue_failures"].append(" | ".join(failure_bits))
        if discord_contact:
            pruned_runtime = _prune_discord_ledger(compiler)
            if pruned_runtime:
                print(f"  → pruned {pruned_runtime} non-observation runtime gap(s) for discord contact")

        mutation_attempt = (
            gap.vocab == "reprogramme_needed"
            or (gap.vocab and is_mutate(gap.vocab))
            or (
                gap.vocab == "reason_needed"
                and outcome.step_result is not None
                and outcome.step_result.rogue
                and outcome.step_result.failure_source == "st_builder"
            )
        )
        if mutation_attempt:
            descriptor = f"{gap.vocab}: {gap.desc}"
            if outcome.step_result and outcome.step_result.commit:
                turn_facts["commits"].append(outcome.step_result.commit)
                turn_facts["successful_mutations"].append(descriptor)
            else:
                turn_facts["attempted_mutations"].append(descriptor)

        # Check if done
        if compiler.is_done():
            print(f"\n  ALL GAPS RESOLVED (iteration {iteration + 1})")
            forced_synth = False
            break

    if forced_synth:
        print("\n── FORCED SYNTH: persisting unresolved frontier for next turn ──")
        forced_step = _persist_forced_synth_frontier(trajectory, compiler, origin_step, current_turn)
        if forced_step:
            print(f"  → forced frontier persisted with {len(forced_step.gaps)} gap(s)")
            turn_facts["persisted_frontiers"].append(forced_step.desc)

    manual_await_step = _persist_manual_await_frontier(trajectory, compiler, origin_step, current_turn)
    if manual_await_step:
        print("\n── MANUAL AWAIT: persisting synchronization checkpoint before synthesis ──")
        print(f"  → await frontier persisted with {len(manual_await_step.gaps)} gap(s)")
        turn_facts["persisted_frontiers"].append(manual_await_step.desc)

    # ── 6. SYNTHESIS ─────────────────────────────────────────────────

    print("\n── SYNTHESIS ──")
    if clarify_frontier_step is not None:
        session.inject(_render_clarify_synthesis_guidance(clarify_frontier_step), role="system")
    response = _synthesize(session, user_message, turn_facts)

    # ── 7. HEARTBEAT ─────────────────────────────────────────────────
    #
    # Law 9: the loop always closes.
    #
    # If any background trigger fired without a manual await, persist
    # an automatic reason_needed as a dangling gap. Next turn, this
    # heartbeat fires — the agent renders the sub-agent's tree,
    # inspects results, and either closes, revisits, or refines.
    #
    # The heartbeat is recursive: if the inspection triggers further
    # background work, another heartbeat persists. The loop closes
    # when all background chains are resolved.

    if compiler.needs_heartbeat():
        print("\n── HEARTBEAT: persisting reason_needed for background sub-agent ──")
        heartbeat_refs = compiler.background_refs()
        heartbeat_gap = Gap.create(
            desc="heartbeat: background sub-agent in progress — inspect results, close or revisit",
            step_refs=[origin_step.hash],
            content_refs=heartbeat_refs,
        )
        heartbeat_gap.scores = Epistemic(relevance=0.9, confidence=0.8, grounded=0.0)
        heartbeat_gap.vocab = "reason_needed"
        heartbeat_gap.turn_id = current_turn
        heartbeat_gap.carry_forward = True
        # Don't resolve — persist as dangling for next turn's resume
        heartbeat_step = Step.create(
            desc="heartbeat: automatic post-synth reason_needed for background workflow",
            step_refs=[origin_step.hash],
            gaps=[heartbeat_gap],
        )
        trajectory.append(heartbeat_step)
        print(f"  → heartbeat gap:{heartbeat_gap.hash[:8]} persisted for next turn")

    # ── 8. SAVE ──────────────────────────────────────────────────────

    _save_turn(trajectory, state)

    return response


# ── Helpers ──────────────────────────────────────────────────────────────

def _extract_json_block(raw: str) -> tuple[dict | None, int | None]:
    """Extract the first valid top-level JSON object from model output."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj, i
    return None, None

def _parse_step_output(raw: str, step_refs: list[str], content_refs: list[str],
                       chain_id: str = None) -> tuple[Step, list[Gap]]:
    """Parse LLM output into a Step with gaps.

    The LLM produces natural text with an embedded JSON block.
    Extract the gaps from the JSON, build a Step.
    """
    gaps = []
    data, json_start = _extract_json_block(raw)
    try:
        if data:
            for g in data.get("gaps", []):
                canonical_content_refs = _canonicalize_content_refs(g.get("content_refs", []))
                gap = Gap.create(
                    desc=g.get("desc", ""),
                    content_refs=canonical_content_refs,
                    step_refs=g.get("step_refs", []),
                )
                gap.scores = Epistemic(
                    relevance=g.get("relevance", 0.5),
                    confidence=g.get("confidence", 0.5),
                    grounded=0.0,
                )
                gap.vocab = g.get("vocab")
                if gap.vocab:
                    gap.vocab_score = 0.8
                gap.turn_id = _turn_counter
                gaps.append(gap)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # Extract desc from the natural text portion (before JSON)
    desc = raw[:json_start].strip() if isinstance(json_start, int) and json_start > 0 else raw[:200].strip()
    # Trim to a reasonable length
    if len(desc) > 200:
        desc = desc[:200] + "..."

    step = Step.create(
        desc=desc,
        step_refs=step_refs,
        content_refs=_canonicalize_content_refs(content_refs),
        gaps=gaps,
        chain_id=chain_id,
    )

    return step, gaps


def _extract_json(raw: str) -> dict | None:
    """Extract a JSON object from LLM output."""
    data, _json_start = _extract_json_block(raw)
    return data


def _extract_command(raw: str) -> str | None:
    """Extract a command from LLM JSON output."""
    data = _extract_json(raw)
    return data.get("command") if isinstance(data, dict) else None


def _extract_written_path(tool_output: str) -> str | None:
    data = _extract_json(tool_output)
    if isinstance(data, dict):
        path = data.get("path")
        if isinstance(path, str) and path.strip():
            return path.strip()
        artifacts = data.get("artifacts")
        if isinstance(artifacts, list):
            for item in artifacts:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    for line in tool_output.splitlines():
        lowered = line.lower()
        if lowered.startswith("written: "):
            return line.split(":", 1)[1].strip()
        if lowered.startswith("patched: "):
            return line.split(":", 1)[1].split("(", 1)[0].strip()
    return None


def _is_reprogramme_intent(intent: dict | None) -> bool:
    if not isinstance(intent, dict):
        return False
    if "gaps" in intent:
        return False
    if intent.get("version") == "semantic_skeleton.v1":
        artifact = intent.get("artifact", {}) or {}
        return artifact.get("kind") in {"entity", "action", "hybrid"}
    if "version" in intent:
        return False
    if "name" not in intent or "desc" not in intent:
        return False
    artifact_kind = intent.get("artifact_kind", "entity")
    return artifact_kind in {"entity", "action_update", "hybrid_update"}


def _resolve_entity(content_refs: list[str], registry: SkillRegistry,
                    trajectory: Trajectory) -> str | None:
    """Resolve entity .st files referenced in content_refs.

    Checks each ref against the skill registry. If it matches a known
    .st file (person, task, commitment, skill), render its full data.
    Falls back to trajectory resolution for non-.st hashes.
    """
    blocks = []
    for ref in content_refs:
        # Check if this hash is a known skill/entity
        skill = registry.resolve(ref)
        if skill:
            blocks.append(_render_entity(skill) if _is_entity_source(skill.source) else _render_skill_package(skill))
            continue
        # Try trajectory
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── {ref} ──\n{data}")
    return "\n\n".join(blocks) if blocks else None


def _skill_payload(skill: Skill) -> dict | None:
    return skill.payload or None


def _is_entity_skill(skill: Skill) -> bool:
    if skill.artifact_kind == "codon":
        return False
    return _is_entity_source(skill.source)


def _render_entity_tree(registry: SkillRegistry) -> str:
    """Render entity-like .st files as a compact semantic tree."""
    entity_skills = [skill for skill in registry.all_skills() if _is_entity_skill(skill)]
    if not entity_skills:
        return "(no entity .st files)"

    lines = ["entity_tree"]
    sorted_skills = sorted(entity_skills, key=lambda skill: skill.display_name)
    for i, skill in enumerate(sorted_skills):
        payload = _skill_payload(skill) or {}
        branch = "└" if i == len(sorted_skills) - 1 else "├"
        cont = " " if i == len(sorted_skills) - 1 else "│"
        lines.append(
            f"{branch}─ {skill.display_name}:{skill.hash} ({Path(skill.source).name}, trigger:{skill.trigger})"
        )

        fields = [field for field in ENTITY_MANIFEST_FIELDS if field in payload]
        if fields:
            lines.append(f"{cont}  ├─ semantics: {', '.join(sorted(fields))}")

        refs = payload.get("refs", {})
        if refs:
            lines.append(f"{cont}  ├─ refs: {', '.join(sorted(refs.keys()))}")

        steps = payload.get("steps", [])
        if steps:
            step_names = " → ".join(step.get("action", "?") for step in steps[:4])
            more = " ..." if len(steps) > 4 else ""
            lines.append(f"{cont}  └─ steps: {step_names}{more}")
        else:
            lines.append(f"{cont}  └─ steps: (pure entity)")

    return "\n".join(lines)


def _render_step_network(registry: SkillRegistry, chains_dir: Path | None = None) -> str:
    return me.render_step_network(chains_dir or CHAINS_DIR, registry, _is_entity_skill, _skill_payload)


def _recent_structural_attempts(trajectory: Trajectory, limit: int = 5) -> list[Step]:
    keywords = (
        "reason actualized workflow:",
        "reason actualization failed:",
        "failed attempt:",
        "reprogrammed discord profile:",
    )
    selected: list[Step] = []
    seen: set[str] = set()
    for step in reversed(trajectory.recent(25)):
        if step.hash in seen:
            continue
        if step.rogue or any(step.desc.startswith(prefix) for prefix in keywords):
            selected.append(step)
            seen.add(step.hash)
        if len(selected) >= limit:
            break
    return list(reversed(selected))


def _render_session_context(
    trajectory: Trajectory,
    registry: SkillRegistry,
    user_message: str,
    active_chain_id: str | None = None,
    active_gap: str | None = None,
) -> str:
    lines = ["## Session Context"]
    if user_message:
        lines.append("### Current Message")
        lines.append(f"\"{user_message}\"")

    if active_chain_id:
        lines.append("### Active Chain")
        lines.append(trajectory.render_chain(active_chain_id, registry=registry, highlight_gap=active_gap, mode="collapsed"))
    else:
        lines.append("### Recent Session Tree")
        lines.append(trajectory.render_recent(TRAJECTORY_WINDOW, registry=registry, mode="collapsed"))

    attempts = _recent_structural_attempts(trajectory)
    if attempts:
        lines.append("### Recent Structural Attempts")
        for step in attempts:
            commit = f" commit:{step.commit}" if step.commit else ""
            rogue = ""
            if step.rogue:
                extras = [part for part in [step.rogue_kind, step.failure_source] if part]
                rogue = f" [rogue:{', '.join(extras)}]" if extras else " [rogue]"
            lines.append(f"- step:{step.hash} \"{step.desc}\"{commit}{rogue}")

    return "\n".join(lines)


def _execution_hooks(chains_dir: Path | None = None) -> ExecutionHooks:
    active_chains_dir = chains_dir or CHAINS_DIR
    return ExecutionHooks(
        resolve_all_refs=resolve_all_refs,
        execute_tool=execute_tool,
        auto_commit=auto_commit,
        parse_step_output=_parse_step_output,
        extract_json=_extract_json,
        extract_command=_extract_command,
        extract_written_path=_extract_written_path,
        is_reprogramme_intent=_is_reprogramme_intent,
        load_tree_policy=_load_tree_policy,
        match_policy=_match_policy,
        resolve_entity=_resolve_entity,
        render_step_network=lambda registry: _render_step_network(registry, active_chains_dir),
        render_session_context=lambda trajectory, registry, user_message, active_chain_id=None, active_gap=None: _render_session_context(
            trajectory,
            registry,
            user_message,
            active_chain_id=active_chain_id,
            active_gap=active_gap,
        ),
        emit_reason_skill=_emit_reason_skill,
        git=git,
        commit_assessment=_commit_assessment_for_commit,
        step_assessment=_step_assessment_for_docs,
        run_isolated_workflow=run_isolated_workflow_ref,
    )


def _execution_config(chains_dir: Path | None = None, session_message: str = "") -> ExecutionConfig:
    return ExecutionConfig(
        cors_root=CORS_ROOT,
        chains_dir=chains_dir or CHAINS_DIR,
        tool_map=TOOL_MAP,
        deterministic_vocab=DETERMINISTIC_VOCAB,
        observation_only_vocab=OBSERVATION_ONLY_VOCAB,
        session_message=session_message,
    )


def _render_entity(skill: Skill) -> str:
    """Render a .st entity's full data for session injection."""
    data = skill.payload
    if not data:
        return f"## {skill.display_name}:{skill.hash}\n(unreadable)"

    lines = [f"## Entity: {skill.display_name}:{skill.hash}"]
    lines.append(f"  name: {skill.name}")
    lines.append(f"  desc: {skill.desc}")
    lines.append(f"  trigger: {skill.trigger}")

    # Identity fields (for people)
    identity = data.get("identity", {})
    if identity:
        lines.append("  identity:")
        for k, v in identity.items():
            lines.append(f"    {k}: {v}")

    # Preferences
    preferences = data.get("preferences", {})
    if preferences:
        lines.append("  preferences:")
        for category, prefs in preferences.items():
            lines.append(f"    {category}:")
            if isinstance(prefs, dict):
                for k, v in prefs.items():
                    lines.append(f"      {k}: {v}")
            else:
                lines.append(f"      {prefs}")

    # Refs
    refs = data.get("refs", {})
    if refs:
        lines.append("  refs:")
        for k, v in refs.items():
            lines.append(f"    {k}: {v}")

    # Steps summary
    lines.append(f"  steps: {' → '.join(s.action for s in skill.steps)}")

    return "\n".join(lines)


def _bootstrap_contact_entity(registry: SkillRegistry, contact_id: str,
                              user_message: str,
                              *,
                              contact_profile: dict[str, str] | None = None) -> Step | None:
    """Bootstrap a thin entity for a first-seen inbound contact.

    This is the only automatic persistence path. Ongoing semantic updates
    must come through explicit reprogramme_needed gaps surfaced by the
    agent, not a per-turn housekeeping pass.
    """
    identity_skill = _find_identity_skill(contact_id, registry)
    if identity_skill is not None:
        return None

    print(f"\n── REPROGRAMME BOOTSTRAP ({contact_id}) ──")
    intent = _build_init_user_intent(contact_id, user_message, contact_profile=contact_profile)
    output, code = execute_tool("tools/st_builder.py", intent)
    print(f"  st_builder: {output[:150]}")
    if code == 0:
        written_path = _extract_written_path(output)
        commit_sha, _on_reject = auto_commit(
            f"reprogramme bootstrap: {intent['name']}",
            paths=[written_path] if written_path else None,
        )
        if commit_sha:
            print(f"  → bootstrapped: {commit_sha}")
            return Step.create(
                desc=f"reprogrammed bootstrap: {intent['name']}",
                content_refs=[commit_sha],
                commit=commit_sha,
            )
    return None


def _find_dangling_gaps(trajectory: Trajectory) -> list[Gap]:
    """Find explicitly persisted unresolved gaps from prior turns.

    Cross-turn carry is opt-in. Successful turns clear their frontier.
    Only explicitly persisted non-clarify gaps are re-admitted automatically.
    Clarify gaps are one-turn frontier questions; later user turns should
    produce fresh judgment rather than replaying old clarify leaves.
    """
    dangling: list[Gap] = []
    seen: set[str] = set()
    for step_hash in trajectory.order:
        step = trajectory.resolve(step_hash)
        if step:
            for gap in step.gaps:
                if (
                    not gap.resolved
                    and not gap.dormant
                    and gap.carry_forward
                    and gap.vocab != "clarify_needed"
                    and gap.hash not in seen
                ):
                    seen.add(gap.hash)
                    dangling.append(gap)
    return dangling


def _clone_gap_for_carry_forward(gap: Gap, *, current_turn: int) -> Gap:
    cloned = Gap.create(
        desc=gap.desc,
        content_refs=list(gap.content_refs),
        step_refs=list(gap.step_refs),
        origin=gap.origin,
    )
    cloned.scores = Epistemic(
        relevance=gap.scores.relevance,
        confidence=gap.scores.confidence,
        grounded=gap.scores.grounded,
    )
    cloned.vocab = gap.vocab
    cloned.vocab_score = gap.vocab_score
    cloned.turn_id = current_turn
    cloned.carry_forward = True
    return cloned


def _discord_gap_is_allowed(gap: Gap) -> bool:
    return bool(gap.vocab) and (is_observe(gap.vocab) or gap.vocab == "clarify_needed")


def _is_bound_discord_profile(contact_id: str, identity_skill: Skill | None) -> bool:
    if not contact_id.startswith("discord:"):
        return False
    if identity_skill is None or not _is_entity_source(identity_skill.source):
        return False
    if Path(identity_skill.source).name == "admin.st" or identity_skill.name == "admin":
        return False
    return identity_skill.trigger == f"on_contact:{contact_id}"


def _message_warrants_discord_profile_update(user_message: str, identity_skill: Skill | None) -> bool:
    text = user_message.strip().lower()
    if not text:
        return False

    greeting_only = re.fullmatch(r"(hey|hi|hello|yo|sup|what'?s up|morning|afternoon|evening)[!. ]*", text)
    if greeting_only:
        return False

    init_pending = bool((identity_skill.payload or {}).get("init", {}).get("status") == "pending") if identity_skill else False
    has_first_person = bool(re.search(r"\b(i|i'm|im|i am|my|me|my name)\b", text))
    profile_signals = any(token in text for token in (
        "my name",
        "i'm",
        "i am",
        "based",
        "live",
        "from",
        "work",
        "working",
        "currently",
        "goal",
        "looking for work",
        "years",
        "year",
        "assistant",
        "analyst",
        "manager",
        "editor",
        "developer",
        "scientist",
        "science",
        "caribbean",
        "black",
        "knee",
        "knees",
    )) or bool(re.search(r"\b\d+\b", text))
    declarative_fragment = "?" not in text and len(text.split()) >= 2

    if has_first_person and profile_signals:
        return True
    if init_pending and declarative_fragment and profile_signals:
        return True
    return False


def _filter_discord_gaps(gaps: list[Gap]) -> tuple[list[Gap], int]:
    kept: list[Gap] = []
    pruned = 0
    for gap in gaps:
        if _discord_gap_is_allowed(gap):
            kept.append(gap)
        else:
            gap.dormant = True
            pruned += 1
    return kept, pruned


def _prune_discord_ledger(compiler: Compiler) -> int:
    kept = []
    pruned = 0
    for entry in compiler.ledger.stack:
        if _discord_gap_is_allowed(entry.gap):
            kept.append(entry)
        else:
            entry.gap.dormant = True
            pruned += 1
    compiler.ledger.stack = kept
    return pruned


def _persist_forced_synth_frontier(trajectory: Trajectory, compiler: Compiler, origin_step: Step, current_turn: int) -> Step | None:
    pending = [entry.gap for entry in compiler.ledger.active_gaps() if not entry.gap.resolved and not entry.gap.dormant]
    if not pending:
        return None
    forced_step = Step.create(
        desc="forced synth: unresolved frontier persisted for next turn",
        step_refs=[origin_step.hash],
        gaps=[_clone_gap_for_carry_forward(gap, current_turn=current_turn) for gap in pending],
    )
    trajectory.append(forced_step)
    return forced_step


def _persist_manual_await_frontier(
    trajectory: Trajectory,
    compiler: Compiler,
    origin_step: Step,
    current_turn: int,
) -> Step | None:
    refs = compiler.manual_await_refs()
    if not refs:
        return None
    for chain_id in compiler.manual_await_chain_ids():
        compiler.record_await(chain_id)
    await_gap = Gap.create(
        desc="await: background workflow in progress — inspect committed child semantic tree when ready",
        step_refs=[origin_step.hash],
        content_refs=refs,
    )
    await_gap.scores = Epistemic(relevance=0.95, confidence=0.8, grounded=0.0)
    await_gap.vocab = "await_needed"
    await_gap.turn_id = current_turn
    await_gap.carry_forward = True
    await_step = Step.create(
        desc="await frontier: manual background synchronization checkpoint",
        step_refs=[origin_step.hash],
        content_refs=refs,
        gaps=[await_gap],
    )
    trajectory.append(await_step)
    return await_step


def _find_identity_skill(contact_id: str, registry: SkillRegistry) -> Skill | None:
    """Find the canonical .st identity bound to this contact."""
    bound_matches: list[Skill] = []
    trigger_matches: list[Skill] = []

    for skill in registry.all_skills():
        payload = skill.payload or {}
        identity = payload.get("identity", {}) or {}
        if identity.get("external_id") == contact_id:
            bound_matches.append(skill)
        if contact_id.startswith("discord:"):
            discord_user_id = contact_id.split(":", 1)[1]
            if str(identity.get("discord_user_id", "")).strip() == discord_user_id:
                bound_matches.append(skill)
        if skill.trigger == f"on_contact:{contact_id}":
            trigger_matches.append(skill)

    matches = bound_matches or trigger_matches
    if not matches:
        return None

    deduped: list[Skill] = []
    seen_hashes: set[str] = set()
    for skill in matches:
        if skill.hash in seen_hashes:
            continue
        seen_hashes.add(skill.hash)
        deduped.append(skill)
    deduped.sort(
        key=lambda skill: (
            skill.name == "admin",
            len(skill.steps),
            skill.trigger == f"on_contact:{contact_id}",
        ),
        reverse=True,
    )
    return deduped[0]


def _slug_contact_id(contact_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", contact_id.lower()).strip("_")
    return slug or "contact"


def _build_init_user_intent(contact_id: str, user_message: str, *, contact_profile: dict[str, str] | None = None) -> dict:
    """Build a deterministic bootstrap entity for a first-seen inbound contact.

    This is intentionally thin. It should give the system continuity on the
    next turn without pretending the user is already well known.
    """
    slug = _slug_contact_id(contact_id)
    seed = user_message.strip()
    if len(seed) > 200:
        seed = seed[:200] + "..."
    profile = contact_profile or {}
    username = str(profile.get("username", "")).strip()
    global_name = str(profile.get("global_name", "")).strip()
    display_name = str(profile.get("display_name", "")).strip()
    semantic_name = username or global_name or display_name or f"user_{slug}"

    return {
        "artifact_kind": "entity",
        "name": semantic_name,
        "desc": f"Bootstrap entity for inbound contact {contact_id}",
        "trigger": f"on_contact:{contact_id}",
        "author": "system",
        "refs": {},
        "identity": {
            "external_id": contact_id,
            "username": username or contact_id,
            "discord_user_id": contact_id.split(":", 1)[1] if contact_id.startswith("discord:") else "",
            "name": semantic_name,
            "source": "inbound_contact",
            "context": (
                "Auto-bootstrapped from a first inbound message. "
                "Minimal identity only until init is completed."
            ),
        },
        "preferences": {
            "onboarding": {
                "deterministic_reprogramme_mode": "bootstrap_only",
                "get_to_know_entity": True,
                "ask_concise_questions": True,
                "question_strategy": (
                    "Ask a small number of concise get-to-know-you questions when useful, "
                    "rather than interrogating every turn."
                ),
                "profile_update_mode": (
                    "Passively surface explicit reprogramme_needed gaps when stable traits, "
                    "preferences, or user-corrected context should be persisted."
                ),
                "passive_reprogramme_optional": True,
                "passive_reprogramme_removal": (
                    "The user may later ask to remove passive profile-maintenance behavior from this entity."
                ),
                "completion_rule": (
                    "Once enough stable profile is known, update this entity and set init.status to complete."
                ),
            }
        },
        "access_rules": {
            "observe": True,
            "reprogramme": True,
            "compile": False,
            "activate_existing": False,
            "mutate": False,
        },
        "init": {
            "status": "pending",
            "mode": "first_contact",
            "ask_profile_questions": True,
            "seed_message": seed,
            "next_action": (
                "Ask a small number of concise onboarding questions when useful. "
                "When enough stable profile is known, reprogramme this entity to set init.status to complete."
            ),
        },
        "steps": [
            {
                "action": "initiate_entity",
                "desc": (
                    "This is a newly bound contact entity. Ask a small number of concise get-to-know-you questions "
                    "when useful, learn stable facts and preferences over time, and surface reprogramme_needed when "
                    "new durable knowledge should be written back to this entity."
                ),
                "resolve": ["identity", "preferences", "access_rules", "init"],
                "post_diff": False,
            },
        ],
    }


def _run_no_gap_discord_profile_sync(
    contact_id: str,
    user_message: str,
    *,
    identity_skill: Skill | None,
    registry: SkillRegistry,
    trajectory: Trajectory,
    origin_step: Step,
) -> Step | None:
    """Deterministically attempt an in-place profile sync for Discord contacts on no-gap turns.

    This path is narrow by design:
    - only runs for bound Discord contact entities
    - only runs when the natural first step surfaced no gaps
    - does not emit new live gaps; it either commits an in-place update or no-ops
    """
    if not _is_bound_discord_profile(contact_id, identity_skill):
        return None
    if not identity_skill.payload:
        return None

    print("\n── NO-GAP DISCORD PROFILE SYNC ──")
    sync_session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))
    sync_session.set_system(PRE_DIFF_SYSTEM)
    force_update = _message_warrants_discord_profile_update(user_message, identity_skill)

    entity_data = _resolve_entity([identity_skill.hash], registry, trajectory)
    if entity_data:
        sync_session.inject(f"## Bound Contact Entity\n{entity_data}")
    sync_session.inject(
        "## Recent Trajectory\n"
        f"{trajectory.render_recent(TRAJECTORY_WINDOW, registry=registry)}"
    )

    frame = st_builder_module.semantic_skeleton_from_st(
        identity_skill.payload,
        existing_ref=identity_skill.hash,
    )
    sync_session.inject(
        "## Editable Semantic Frame\n"
        "Update this bound contact entity in place only if this turn established durable semantic state.\n"
        f"{json.dumps(frame, indent=2)}"
    )
    if force_update:
        sync_session.inject(
            "## Deterministic Sync Signal\n"
            "The latest message contains durable self-description that should be persisted into the bound contact entity."
        )
    noop_rule = (
        '- Do not return {"noop": true}; this message warrants a profile update.\n'
        if force_update
        else '- If no durable semantic update is warranted from this turn, return {"noop": true}.\n'
    )

    raw = sync_session.call(
        f"Task: deterministically maintain the bound Discord contact profile after a no-gap turn.\n"
        f"Contact: {contact_id}\n"
        f"Latest message: \"{user_message}\"\n\n"
        "Rules:\n"
        "- Return JSON only.\n"
        f"{noop_rule}"
        "- Otherwise return a semantic_skeleton.v1 entity update for this existing contact entity.\n"
        "- Use existing_ref and update the current entity in place.\n"
        "- Preserve trigger, identity bindings, access_rules, init, refs, and entity shape.\n"
        "- Persist only stable facts, corrections, preferences, goals, or durable context learned from this turn.\n"
        "- Prefer the latest explicit first-person statement over stale historical ambiguity.\n"
        "- If the latest message states identity, role, work history, health context, goals, or preferences in first person, treat those as durable unless clearly temporary.\n"
        "- If the latest message fills a pending profile field, update the entity instead of returning noop.\n"
        "- Do not ask questions.\n"
        "- Do not emit gaps.\n"
    )
    print(f"  LLM sync: {raw[:150]}...")
    intent = _extract_json(raw)
    if force_update and isinstance(intent, dict) and intent.get("noop") is True:
        raw = sync_session.call(
            "The latest message contained durable self-description. No noop allowed. "
            "Return only a semantic_skeleton.v1 entity update for the current bound contact entity."
        )
        print(f"  LLM sync retry: {raw[:150]}...")
        intent = _extract_json(raw)
    if not isinstance(intent, dict) or intent.get("noop") is True:
        print("  → no durable profile update warranted")
        return None

    intent.setdefault("existing_ref", identity_skill.hash)
    intent.setdefault("trigger", identity_skill.trigger)
    if not _is_reprogramme_intent(intent):
        print("  → no valid reprogramme intent extracted")
        return None

    output, code = execute_tool("tools/st_builder.py", intent)
    print(f"  st_builder: {output[:150]}")
    written_path = _extract_written_path(output)
    if code != 0 or not written_path:
        print("  → profile sync skipped (builder produced no writable update)")
        return None

    commit_sha, _ = auto_commit(
        f"reprogramme discord profile: {identity_skill.display_name}",
        paths=[written_path],
    )
    if not commit_sha:
        print("  → no profile changes to commit")
        return None

    print(f"  → committed: {commit_sha}")
    step_result = Step.create(
        desc=f"reprogrammed discord profile: {identity_skill.display_name}",
        step_refs=[origin_step.hash],
        content_refs=[identity_skill.hash],
        commit=commit_sha,
    )
    trajectory.append(step_result)

    commit_path = None
    try:
        commit_path = str(Path(written_path).resolve().relative_to(CORS_ROOT))
    except ValueError:
        commit_path = written_path
    assessment_refs = [f"{commit_sha}:{commit_path}"] if commit_path else [commit_sha]
    assessment_step = Step.create(
        desc=f"observed discord profile sync: {identity_skill.display_name}",
        step_refs=[step_result.hash],
        content_refs=assessment_refs,
        assessment=_commit_assessment_for_commit(commit_sha),
    )
    trajectory.append(assessment_step)
    return step_result


def _render_identity(skill: Skill) -> str:
    """Render a skill's identity, preferences, and init state for session injection."""
    try:
        with open(skill.source) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return ""

    def _render_section_value(lines: list[str], value, indent: int = 2):
        prefix = " " * indent
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}{k}:")
                    _render_section_value(lines, v, indent + 2)
                else:
                    lines.append(f"{prefix}{k}: {v}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}-")
                    _render_section_value(lines, item, indent + 2)
                else:
                    lines.append(f"{prefix}- {item}")
        else:
            lines.append(f"{prefix}{value}")

    lines = [f"## Identity: {skill.display_name}:{skill.hash}"]
    try:
        rel_source = Path(skill.source).resolve().relative_to(CORS_ROOT)
        lines.append(f"  source: {rel_source}")
    except ValueError:
        lines.append(f"  source: {skill.source}")

    identity = data.get("identity", {})
    if identity:
        for k, v in identity.items():
            lines.append(f"  {k}: {v}")

    preferences = data.get("preferences", {})
    if preferences:
        lines.append("## Preferences")
        for category, prefs in preferences.items():
            lines.append(f"  {category}:")
            if isinstance(prefs, dict):
                for k, v in prefs.items():
                    lines.append(f"    {k}: {v}")
            else:
                lines.append(f"    {prefs}")

    access_rules = data.get("access_rules", {})
    if access_rules:
        lines.append("## Access Rules")
        for k, v in access_rules.items():
            lines.append(f"  {k}: {v}")

    init = data.get("init", {})
    if init:
        lines.append("## Init")
        for k, v in init.items():
            lines.append(f"  {k}: {v}")

    if init.get("status") == "pending" and skill.steps:
        lines.append("## Initiation")
        lines.append(f"  {skill.steps[0].desc}")

    rendered_sections = {"name", "desc", "trigger", "author", "refs", "steps", "identity", "preferences", "access_rules", "init"}
    extra_sections = [
        key for key in data.keys()
        if key not in rendered_sections and data.get(key) not in ({}, [], "", None)
    ]
    for key in extra_sections:
        lines.append(f"## {key.replace('_', ' ').title()}")
        _render_section_value(lines, data[key], indent=2)

    return "\n".join(lines)


def _render_turn_outcome_facts(turn_facts: dict[str, list[str]]) -> str:
    commits = turn_facts.get("commits", [])
    successful = turn_facts.get("successful_mutations", [])
    attempted = turn_facts.get("attempted_mutations", [])
    rogue_failures = turn_facts.get("rogue_failures", [])
    persisted = turn_facts.get("persisted_frontiers", [])

    lines = ["## Turn Outcome Facts"]
    lines.append("Successful commits:")
    lines.extend(f"- {item}" for item in commits) if commits else lines.append("- none")
    lines.append("Successful mutations:")
    lines.extend(f"- {item}" for item in successful) if successful else lines.append("- none")
    lines.append("Attempted but unconfirmed mutations:")
    lines.extend(f"- {item}" for item in attempted) if attempted else lines.append("- none")
    lines.append("Observed failures:")
    lines.extend(f"- {item}" for item in rogue_failures) if rogue_failures else lines.append("- none")
    lines.append("Persisted unresolved frontiers:")
    lines.extend(f"- {item}" for item in persisted) if persisted else lines.append("- none")
    lines.append(
        "Rule: only say something was changed, removed, updated, saved, or persisted if Successful commits or Successful mutations above prove it."
    )
    if not commits and not successful:
        lines.append(
            "No mutation succeeded this turn. Describe observations, clarifications, or next steps instead of claiming the change already happened."
        )
        lines.append(
            "Do not say 'I'll update', 'I will proceed', or any equivalent future-write promise when no mutation succeeded this turn."
        )
    if attempted or rogue_failures or persisted:
        lines.append(
            "If authoring or actualization was attempted but failed validation, manifestation, or persistence, say it was attempted but not validated or persisted."
        )
        lines.append(
            "Do not describe a workflow, file, or structure as ready, live, built, or complete unless a successful commit above proves it."
        )
        lines.append(
            "Describe repeated structural failure directly as still structurally invalid, unresolved, exhausted, or persisted for a later turn instead of saying it is ready to be built."
        )
    return "\n".join(lines)


def _synthesize(session: Session, user_message: str, turn_facts: dict[str, list[str]] | None = None) -> str:
    """Produce the final response from the session."""
    if turn_facts is not None:
        session.inject(_render_turn_outcome_facts(turn_facts), role="system")
    session.inject(SYNTH_SYSTEM, role="system")
    response = session.call(f"Synthesize your response to: \"{user_message}\"")
    print(f"  Response: {response[:200]}")
    return response


def _save_turn(trajectory: Trajectory, state: StatePaths | None = None):
    """Persist trajectory, chains, and extract long chains to files."""
    active_state = state or _state_paths()
    active_state.trajectory.parent.mkdir(parents=True, exist_ok=True)
    active_state.chains_file.parent.mkdir(parents=True, exist_ok=True)
    active_state.chains_dir.parent.mkdir(parents=True, exist_ok=True)
    (active_state.chains_dir.parent / "subagent").mkdir(parents=True, exist_ok=True)
    (active_state.chains_dir.parent / "background_agent").mkdir(parents=True, exist_ok=True)
    active_state.chains_dir.mkdir(parents=True, exist_ok=True)
    trajectory.save(str(active_state.trajectory))
    trajectory.save_chains(str(active_state.chains_file))
    # Extract long resolved chains to individual files
    trajectory.extract_chains(str(active_state.chains_dir))
    extracted = sum(1 for c in trajectory.chains.values() if c.extracted)
    print(f"  Saved: {len(trajectory.order)} steps, {len(trajectory.chains)} chains"
          + (f" ({extracted} extracted)" if extracted else ""))


def run_isolated_workflow_ref(
    ref: str,
    *,
    task_prompt: str | None = None,
    content_refs: list[str] | None = None,
    step_refs: list[str] | None = None,
    activation_context: str | None = None,
    store_kind: str = "background_agent",
    await_policy: str = "none",
    contact_id: str = "admin",
) -> dict[str, str | int | None]:
    """Run a workflow reference in an isolated trajectory store.

    This is the child-runtime primitive for subagent/background execution.
    The child workflow gets its own trajectory/chains files, but resolved
    chains are aliased by activation ref so the parent can resolve them
    through hash_resolve_needed later.
    """

    global _turn_counter, _skill_registry
    _turn_counter += 1
    current_turn = _turn_counter

    state = _child_state_paths(store_kind, ref)
    trajectory = Trajectory.load(str(state.trajectory))
    Trajectory.load_chains(str(state.chains_file), trajectory)

    registry = load_all(str(SKILLS_DIR))
    _skill_registry = registry
    activation_content_refs = [str(item).strip() for item in (content_refs or []) if isinstance(item, str) and str(item).strip()]
    activation_step_refs = [str(item).strip() for item in (step_refs or []) if isinstance(item, str) and str(item).strip()]
    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))
    session.set_system(PRE_DIFF_SYSTEM)
    session.inject(
        "## Isolated Workflow Activation\n"
        f"activation_ref: {ref}\n"
        f"store_kind: {store_kind}\n"
        f"await_policy: {await_policy}\n"
        f"task: {task_prompt or '(none)'}\n"
        f"content_refs: {activation_content_refs or []}\n"
        f"step_refs: {activation_step_refs or []}"
    )
    if activation_context:
        session.inject(f"## Activation Context\n{activation_context}")

    origin_gap = Gap.create(
        desc=task_prompt or f"run isolated workflow {ref}",
        content_refs=[ref] + activation_content_refs,
        step_refs=activation_step_refs,
    )
    origin_gap.resolved = True
    origin_gap.turn_id = current_turn
    origin = Step.create(
        desc=f"child activation:{ref}",
        step_refs=activation_step_refs,
        content_refs=[ref] + activation_content_refs,
        gaps=[origin_gap],
    )
    trajectory.append(origin)

    compiler = Compiler(trajectory, current_turn=current_turn)
    chain = Chain.create(origin_gap.hash, origin.hash)
    chain.store_kind = store_kind
    chain.activation_ref = ref
    chain.await_policy = await_policy
    trajectory.add_chain(chain)
    compiler.active_chain = chain
    compiler.ledger.chain_states[chain.hash] = ChainState.OPEN

    skill = registry.resolve(ref)
    if skill is None:
        chain_path = public_chain_ref_map(CORS_ROOT).get(ref)
        if chain_path:
            expected_source = str((CORS_ROOT / chain_path).resolve())
            for candidate in registry.by_hash.values():
                if str(Path(candidate.source).resolve()) == expected_source:
                    skill = candidate
                    break
    if skill is not None:
        activation_step = me.activate_skill_package(
            skill,
            ref,
            origin_gap,
            origin,
            chain.hash,
            current_turn,
            task_prompt=task_prompt,
            activation_content_refs=activation_content_refs,
            activation_step_refs=activation_step_refs,
            registry=registry,
            chains_dir=state.chains_dir,
            cors_root=CORS_ROOT,
            tool_map=TOOL_MAP,
            git=git_show,
        )
        session.inject(f"## Activated workflow\n{_render_skill_package(skill)}")
    else:
        activation_step = me.activate_chain_reference(
            state.chains_dir,
            ref,
            "inline",
            origin_gap,
            origin,
            chain.hash,
            registry,
            compiler,
            trajectory,
            current_turn,
            task_prompt=task_prompt,
            activation_content_refs=activation_content_refs,
            activation_step_refs=activation_step_refs,
            tool_map=TOOL_MAP,
        )
        package = me.load_chain_package(state.chains_dir, ref, trajectory)
        if package is not None:
            session.inject(f"## Activated workflow\n{me.render_chain_package(package, ref)}")

    if activation_step is None:
        _save_turn(trajectory, state)
        return {
            "status": "missing",
            "activation_ref": ref,
            "store_kind": store_kind,
            "trajectory": str(state.trajectory),
            "chains_file": str(state.chains_file),
            "chains_dir": str(state.chains_dir),
            "response": None,
        }

    trajectory.append(activation_step)
    compiler.add_step_to_chain(activation_step.hash)
    compiler.emit(activation_step)

    for iteration in range(MAX_ITERATIONS):
        entry, signal = compiler.next()
        if entry is None or signal == GovernorSignal.HALT:
            break
        gap = entry.gap
        session.inject(
            "## Active Chain Tree\n"
            f"{trajectory.render_chain(entry.chain_id, registry=registry, highlight_gap=gap.hash)}"
        )
        outcome = execute_iteration(
            entry=entry,
            signal=signal,
            session=session,
            origin_step=origin,
            trajectory=trajectory,
            compiler=compiler,
            registry=registry,
            current_turn=current_turn,
            hooks=_execution_hooks(state.chains_dir),
            config=_execution_config(state.chains_dir, task_prompt or ref),
        )
        if outcome.control == "break" or compiler.is_done():
            break

    child_response = _synthesize(session, task_prompt or f"child workflow {ref}")

    chain.store_kind = store_kind
    chain.activation_ref = ref
    chain.await_policy = await_policy
    if chain.resolved:
            commit_step = Step.create(
                desc=f"commit: reintegrate child workflow {ref}",
                step_refs=[activation_step.hash],
                content_refs=[ref, chain.hash],
                chain_id=chain.hash,
            )
            trajectory.append(commit_step)
            chain.add_step(commit_step.hash)

    for child_chain in trajectory.chains.values():
        if child_chain.resolved:
            child_chain.store_kind = store_kind
            child_chain.activation_ref = child_chain.activation_ref or ref
            child_chain.await_policy = child_chain.await_policy or await_policy
            child_chain.extracted = True

    _save_turn(trajectory, state)
    return {
        "status": "ok",
        "activation_ref": ref,
        "store_kind": store_kind,
        "trajectory": str(state.trajectory),
        "chains_file": str(state.chains_file),
        "chains_dir": str(state.chains_dir),
        "response": child_response,
    }


# ── Main ─────────────────────────────────────────────────────────────────

def run_command(cmd_name: str, args: str = "") -> str:
    """Run a /command .st file directly. Bypasses LLM gap routing."""
    global _turn_counter, _skill_registry
    _turn_counter += 1
    current_turn = _turn_counter

    registry = load_all(str(SKILLS_DIR))
    _skill_registry = registry
    skill = registry.resolve_command(cmd_name)
    if not skill:
        return f"Unknown command: /{cmd_name}"

    trajectory = Trajectory.load(str(TRAJ_FILE))
    Trajectory.load_chains(str(CHAINS_FILE), trajectory)

    print(f"\n── COMMAND: /{cmd_name} ({skill.display_name}:{skill.hash}) ──")

    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))
    session.set_system(PRE_DIFF_SYSTEM)

    # Inject entity data
    entity_data = _render_entity(skill)
    session.inject(entity_data)
    if args:
        session.inject(f"## Command args\n{args}")

    # Create origin step for the command
    origin = Step.create(
        desc=f"command: /{cmd_name}",
        content_refs=[skill.hash],
    )
    trajectory.append(origin)

    # Inject skill steps as gaps onto compiler
    compiler = Compiler(trajectory, current_turn=current_turn)
    for st_step in skill.steps:
        gap = Gap.create(
            desc=st_step.desc,
            content_refs=[skill.hash],
        )
        gap.scores = Epistemic(relevance=0.9, confidence=0.8, grounded=0.0)
        gap.vocab = st_step.vocab
        gap.turn_id = current_turn
        origin.gaps.append(gap)

    compiler.emit_origin_gaps(origin)
    print(compiler.render_ledger())

    # Run iteration loop through the shared execution engine.
    for iteration in range(MAX_ITERATIONS):
        entry, signal = compiler.next()
        if entry is None or signal == GovernorSignal.HALT:
            break

        gap = entry.gap
        print(f"  [{iteration+1}] gap:{gap.hash[:8]} \"{gap.desc}\" [{gap.vocab}]")
        session.inject(
            "## Active Chain Tree\n"
            f"{trajectory.render_chain(entry.chain_id, registry=registry, highlight_gap=gap.hash)}"
        )
        outcome = execute_iteration(
            entry=entry,
            signal=signal,
            session=session,
            origin_step=origin,
            trajectory=trajectory,
            compiler=compiler,
            registry=registry,
            current_turn=current_turn,
            hooks=_execution_hooks(),
            config=_execution_config(),
        )

        if outcome.control == "break" or compiler.is_done():
            break

    # Synthesize
    response = _synthesize(session, f"/{cmd_name}")
    _save_turn(trajectory)
    return response


if __name__ == "__main__":
    print("v5 Step Kernel — cors")
    print("Type /quit to exit, /wipe to reset, /cmd to run a command\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/wipe":
            if TRAJ_FILE.exists():
                TRAJ_FILE.unlink()
            if CHAINS_FILE.exists():
                CHAINS_FILE.unlink()
            print("trajectory wiped")
            continue

        # /policy — view or edit tree policy
        if user_input.startswith("/policy"):
            parts = user_input.split(" ", 2)
            if len(parts) == 1:
                # /policy — show current policy
                policy = _load_tree_policy()
                print("\n── Tree Policy ──")
                for path, rule in sorted(policy.items()):
                    if rule.get("immutable"):
                        print(f"  {path:30s} immutable")
                    elif rule.get("on_mutate"):
                        print(f"  {path:30s} on_mutate → {rule['on_mutate']}")
                print()
            elif len(parts) == 3:
                # /policy path rule  (e.g. /policy media/ stitch_needed)
                path = parts[1]
                rule_str = parts[2]
                policy = _load_tree_policy()
                if rule_str == "immutable":
                    policy[path] = {"immutable": True}
                elif rule_str == "remove":
                    policy.pop(path, None)
                else:
                    policy[path] = {"on_mutate": rule_str}
                with open(TREE_POLICY_FILE, "w") as f:
                    json.dump(policy, f, indent=2)
                print(f"  policy updated: {path} → {rule_str}")
            else:
                print("  usage: /policy [path rule]")
                print("  examples:")
                print("    /policy                        — show all")
                print("    /policy media/ stitch_needed   — add on_mutate rule")
                print("    /policy data/ immutable        — add immutable rule")
                print("    /policy media/ remove          — remove rule")
            continue

        # /command routing
        if user_input.startswith("/"):
            parts = user_input[1:].split(" ", 1)
            cmd_name = parts[0]
            cmd_args = parts[1] if len(parts) > 1 else ""
            response = run_command(cmd_name, cmd_args)
            print(f"\nv5> {response}\n")
            continue

        response = run_turn(user_input)
        print(f"\nv5> {response}\n")
