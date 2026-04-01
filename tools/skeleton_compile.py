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


def compile_skeleton(doc: dict) -> dict:
    errors = validate_skeleton(doc)
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
