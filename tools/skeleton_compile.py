#!/usr/bin/env python3
"""skeleton_compile — deterministic skeleton.v1 -> stepchain.v1 compiler.

This compiler does not invent structure. It normalizes an authored
`skeleton.v1` document into a machine-facing `stepchain.v1` package.

Design rules:
  - structural law lives in the skeleton
  - kernel routing is derived from manifestation config
  - exact curated package activation may be carried by hash reference
  - top-level symbolic refs (@name) are resolved deterministically
  - runtime placeholders ($prev, $origin, $commit, $phase:...) remain symbolic
"""
from __future__ import annotations
TOOL_DESC = 'deterministic skeleton.v1 -> stepchain.v1 compiler.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'none'

import json
import sys
from copy import deepcopy
from pathlib import Path


CORS_ROOT = Path(__file__).parent.parent


def _is_runtime_placeholder(ref: str) -> bool:
    return ref.startswith("$")


def resolve_symbolic_ref(ref: str, refs: dict[str, str]) -> str:
    """Resolve @top-level refs; keep runtime placeholders symbolic."""
    if ref.startswith("@"):
        return refs.get(ref[1:], ref)
    if _is_runtime_placeholder(ref):
        return ref
    return ref


def resolve_symbolic_refs(refs_list: list[str], refs: dict[str, str]) -> list[str]:
    return [resolve_symbolic_ref(ref, refs) for ref in refs_list]


def derive_priority(kind: str, manifestation: dict) -> int:
    """Derive ledger priority from structural manifestation config."""
    kernel_class = manifestation["kernel_class"]
    runtime_vocab = manifestation.get("runtime_vocab")

    if kind == "clarify" or kernel_class == "clarify":
        return 20
    if kernel_class == "observe":
        return 20
    if kernel_class == "mutate":
        return 40

    # bridge-like phases preserve the current runtime ordering where possible
    if runtime_vocab == "reason_needed":
        return 90
    if runtime_vocab == "await_needed":
        return 95
    if runtime_vocab == "commit_needed":
        return 98
    if runtime_vocab == "reprogramme_needed":
        return 99

    if manifestation.get("await_policy") in {"manual", "heartbeat"}:
        return 95
    if manifestation.get("protected_kind") == "entity" or manifestation.get("background"):
        return 99
    return 90


def classify_allowed_vocab(allowed_vocab: list[str]) -> dict[str, list[str]]:
    buckets = {
        "observe": [],
        "mutate": [],
        "bridge": [],
    }
    for vocab in allowed_vocab:
        if vocab in {"pattern_needed", "hash_resolve_needed", "email_needed", "external_context", "clarify_needed"}:
            buckets["observe"].append(vocab)
        elif vocab in {"hash_edit_needed", "stitch_needed", "content_needed", "script_edit_needed", "command_needed", "message_needed", "json_patch_needed", "git_revert_needed"}:
            buckets["mutate"].append(vocab)
        elif vocab in {"reason_needed", "await_needed", "commit_needed", "reprogramme_needed"}:
            buckets["bridge"].append(vocab)
    return buckets


def normalize_embed(embed, refs: dict[str, str]) -> list[str]:
    if embed is None:
        return []
    if isinstance(embed, list):
        return resolve_symbolic_refs(embed, refs)
    return [resolve_symbolic_ref(embed, refs)]


def is_terminal_phase(phase: dict) -> bool:
    return phase.get("kind") == "terminal" or phase.get("terminal") is True


def phase_successors(phase: dict) -> list[str]:
    return list(phase.get("transitions", {}).values())


def reachable_phase_ids(root: str, phase_map: dict[str, dict]) -> set[str]:
    seen: set[str] = set()
    stack = [root]
    while stack:
        pid = stack.pop()
        if pid in seen or pid not in phase_map:
            continue
        seen.add(pid)
        stack.extend(phase_successors(phase_map[pid]))
    return seen


def can_reach_target(
    start: str,
    phase_map: dict[str, dict],
    predicate,
    *,
    stop_predicate=None,
    memo: dict[str, bool] | None = None,
    visiting: set[str] | None = None,
) -> bool:
    if start not in phase_map:
        return False
    if memo is None:
        memo = {}
    if visiting is None:
        visiting = set()
    if start in memo:
        return memo[start]
    phase = phase_map[start]
    if predicate(phase):
        memo[start] = True
        return True
    if stop_predicate is not None and stop_predicate(phase):
        memo[start] = False
        return False
    if start in visiting:
        return False
    visiting.add(start)
    result = any(
        can_reach_target(
            target,
            phase_map,
            predicate,
            stop_predicate=stop_predicate,
            memo=memo,
            visiting=visiting,
        )
        for target in phase_successors(phase)
    )
    visiting.remove(start)
    memo[start] = result
    return result


def phase_consumes_commit(phase: dict) -> bool:
    gap_template = phase.get("gap_template", {})
    return "$commit" in gap_template.get("content_refs", [])


def is_observe_like(phase: dict) -> bool:
    if phase.get("kind") in {"observe", "verify"}:
        return True
    manifestation = phase.get("manifestation", {})
    return manifestation.get("kernel_class") == "observe"


def is_mutate_like(phase: dict) -> bool:
    if phase.get("kind") == "mutate":
        return True
    manifestation = phase.get("manifestation", {})
    return manifestation.get("kernel_class") == "mutate"


def is_reason_like(phase: dict) -> bool:
    if phase.get("kind") in {"reason", "higher_order"}:
        return True
    manifestation = phase.get("manifestation", {})
    return manifestation.get("runtime_vocab") == "reason_needed"


def compile_phase(phase: dict, refs: dict[str, str]) -> dict:
    node = {
        "id": phase["id"],
        "kind": phase["kind"],
        "goal": phase["goal"],
        "action": phase["action"],
    }

    if phase["kind"] == "terminal":
        node["terminal"] = True
        return node

    manifestation = deepcopy(phase["manifestation"])
    if "activation_ref" in manifestation:
        manifestation["activation_ref"] = resolve_symbolic_ref(manifestation["activation_ref"], refs)

    node["manifestation"] = manifestation
    node["generation"] = deepcopy(phase["generation"])
    node["priority"] = derive_priority(phase["kind"], manifestation)
    node["allowed_vocab"] = list(phase["allowed_vocab"])
    node["vocab_buckets"] = classify_allowed_vocab(phase["allowed_vocab"])
    node["post_diff"] = phase["post_diff"]

    gap_template = phase["gap_template"]
    node["gap_template"] = {
        "desc": gap_template["desc"],
        "content_refs": resolve_symbolic_refs(gap_template.get("content_refs", []), refs),
        "step_refs": resolve_symbolic_refs(gap_template.get("step_refs", []), refs),
    }

    if "resolve" in phase:
        node["resolve"] = [refs.get(name, name) for name in phase["resolve"]]
    if "transitions" in phase:
        node["transitions"] = dict(phase["transitions"])
    if "requires_postcondition" in phase:
        node["requires_postcondition"] = phase["requires_postcondition"]
    if "inject" in phase:
        node["inject"] = deepcopy(phase["inject"])
    if "embed" in phase:
        node["embed"] = normalize_embed(phase["embed"], refs)

    # Stable activation key for downstream ledgers / analytics.
    if manifestation["execution_mode"] == "runtime_vocab":
        node["activation_key"] = manifestation.get("runtime_vocab")
    elif manifestation["execution_mode"] == "curated_step_hash":
        node["activation_key"] = manifestation.get("activation_ref")
    else:
        node["activation_key"] = None

    return node


def validate_skeleton(doc: dict) -> list[str]:
    errors: list[str] = []

    required = {"version", "name", "desc", "trigger", "refs", "root", "phases", "closure"}
    missing = required - set(doc)
    if missing:
        return [f"missing top-level fields: {sorted(missing)}"]

    if doc["version"] != "skeleton.v1":
        errors.append("version must be skeleton.v1")

    phase_ids = [phase.get("id") for phase in doc.get("phases", [])]
    if not phase_ids:
        errors.append("phases must not be empty")
        return errors
    if len(phase_ids) != len(set(phase_ids)):
        errors.append("phase ids must be unique")
    if doc["root"] not in phase_ids:
        errors.append("root must reference an existing phase id")

    for phase in doc["phases"]:
        pid = phase.get("id", "?")
        if phase.get("kind") == "terminal":
            if phase.get("terminal") is not True:
                errors.append(f"terminal phase {pid} must set terminal=true")
            continue

        manifestation = phase.get("manifestation")
        if manifestation is None:
            errors.append(f"phase {pid} missing manifestation")
            continue
        generation = phase.get("generation")
        if generation is None:
            errors.append(f"phase {pid} missing generation")
        else:
            for field in (
                "spawn_mode",
                "spawn_trigger",
                "branch_policy",
                "sibling_policy",
                "return_policy",
            ):
                if field not in generation:
                    errors.append(f"phase {pid} generation missing {field}")

            spawn_mode = generation.get("spawn_mode")
            spawn_trigger = generation.get("spawn_trigger")
            if spawn_mode == "none" and spawn_trigger not in {None, "none"}:
                errors.append(f"phase {pid} generation with spawn_mode=none must use spawn_trigger=none")
            if spawn_mode in {"context", "action", "mixed", "embed"} and spawn_trigger == "none":
                errors.append(f"phase {pid} generation with offspring must declare a spawn trigger")
            if (spawn_trigger in {"on_post_diff", "conditional"}) and not phase.get("post_diff", False):
                errors.append(f"phase {pid} uses {spawn_trigger} offspring but post_diff is false")
            if spawn_mode in {"context", "action", "mixed", "embed"} and generation.get("sibling_policy") != "after_descendants":
                errors.append(f"phase {pid} offspring must block siblings until descendants return")
            if spawn_mode in {"context", "action", "mixed", "embed"} and generation.get("branch_policy") not in {
                "depth_first_to_parent",
                "depth_first_to_root",
            }:
                errors.append(f"phase {pid} offspring must declare a depth-first branch policy")

        for field in ("kernel_class", "dispersal", "execution_mode"):
            if field not in manifestation:
                errors.append(f"phase {pid} manifestation missing {field}")

        mode = manifestation.get("execution_mode")
        if mode == "runtime_vocab" and "runtime_vocab" not in manifestation:
            errors.append(f"phase {pid} runtime_vocab manifestation requires runtime_vocab")
        if mode == "curated_step_hash" and "activation_ref" not in manifestation:
            errors.append(f"phase {pid} curated_step_hash manifestation requires activation_ref")

        for target in phase.get("transitions", {}).values():
            if target not in phase_ids:
                errors.append(f"phase {pid} transition points to missing target {target}")

    return errors


def validate_workflow_coherence(doc: dict) -> list[str]:
    errors: list[str] = []
    phase_map = {phase["id"]: phase for phase in doc["phases"]}
    root = doc["root"]
    reachable = reachable_phase_ids(root, phase_map)
    terminal_ids = {pid for pid, phase in phase_map.items() if is_terminal_phase(phase)}
    success_terminal = doc["closure"]["success"]["requires_terminal"]

    for pid in phase_map:
        if pid not in reachable:
            errors.append(f"phase {pid} is unreachable from root {root}")

    if success_terminal not in reachable:
        errors.append(f"success terminal {success_terminal} is not reachable from root {root}")

    terminal_path_memo: dict[str, bool] = {}
    for pid in reachable:
        phase = phase_map[pid]
        if is_terminal_phase(phase):
            continue
        if not can_reach_target(
            pid,
            phase_map,
            is_terminal_phase,
            memo=terminal_path_memo,
        ):
            errors.append(f"phase {pid} has no path to a terminal phase")

    observe_path_memo: dict[str, bool] = {}
    commit_path_memo: dict[str, bool] = {}
    reason_path_memo: dict[str, bool] = {}
    for pid in reachable:
        phase = phase_map[pid]
        if is_mutate_like(phase):
            successors = phase_successors(phase)
            if not successors:
                errors.append(f"mutate phase {pid} must have a successor for OMO closure")
            elif not any(
                can_reach_target(
                    target,
                    phase_map,
                    is_observe_like,
                    stop_predicate=lambda p: is_terminal_phase(p) or is_mutate_like(p),
                    memo=observe_path_memo,
                )
                for target in successors
            ):
                errors.append(
                    f"mutate phase {pid} must reach observe/verify before terminal or next mutate"
                )

            manifestation = phase.get("manifestation", {})
            if manifestation.get("emits_commit") and successors and not any(
                can_reach_target(
                    target,
                    phase_map,
                    phase_consumes_commit,
                    stop_predicate=lambda p: is_terminal_phase(p) or is_mutate_like(p),
                    memo=commit_path_memo,
                )
                for target in successors
            ):
                errors.append(
                    f"mutate phase {pid} emits_commit but no downstream phase consumes $commit before branch closure"
                )

        manifestation = phase.get("manifestation", {})
        await_policy = manifestation.get("await_policy")
        if phase.get("kind") == "await" and "await_needed" not in phase.get("allowed_vocab", []):
            errors.append(f"await phase {pid} must allow await_needed")
        if await_policy in {"manual", "heartbeat"} or manifestation.get("background"):
            successors = phase_successors(phase)
            if not successors:
                errors.append(f"phase {pid} uses await/background semantics but has no reintegration path")
            elif not any(
                can_reach_target(
                    target,
                    phase_map,
                    is_reason_like,
                    stop_predicate=is_terminal_phase,
                    memo=reason_path_memo,
                )
                for target in successors
            ):
                errors.append(
                    f"phase {pid} uses await/background semantics but cannot reach reason_needed-style reintegration"
                )

        generation = phase.get("generation")
        if generation:
            spawn_mode = generation.get("spawn_mode")
            return_policy = generation.get("return_policy")
            if spawn_mode in {"context", "action", "mixed", "embed"}:
                if return_policy == "terminal" and not any(
                    target in terminal_ids for target in phase_successors(phase)
                ):
                    errors.append(
                        f"phase {pid} uses terminal return_policy but has no terminal successor"
                    )
                if return_policy == "resume_transition" and not phase_successors(phase):
                    errors.append(
                        f"phase {pid} uses resume_transition return_policy but has no transition target"
                    )

    return errors


def compile_skeleton(doc: dict) -> dict:
    errors = validate_skeleton(doc)
    if not errors:
        errors.extend(validate_workflow_coherence(doc))
    if errors:
        return {"status": "error", "errors": errors}

    refs = dict(doc["refs"])
    nodes = [compile_phase(phase, refs) for phase in doc["phases"]]
    phase_order = [phase["id"] for phase in doc["phases"]]

    stepchain = {
        "version": "stepchain.v1",
        "source_version": doc["version"],
        "name": doc["name"],
        "desc": doc["desc"],
        "trigger": doc["trigger"],
        "refs": refs,
        "root": doc["root"],
        "phase_order": phase_order,
        "nodes": nodes,
        "closure": deepcopy(doc["closure"]),
    }
    return {"status": "ok", "stepchain": stepchain}


def main() -> int:
    try:
        doc = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "errors": [f"invalid JSON input: {exc}"]}, indent=2))
        return 1

    result = compile_skeleton(doc)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
