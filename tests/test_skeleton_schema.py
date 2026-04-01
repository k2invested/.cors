import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "skeleton.v1.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def validate_skeleton_contract(doc: dict) -> list[str]:
    errors: list[str] = []

    required_top = {"version", "name", "desc", "trigger", "refs", "root", "phases", "closure"}
    missing_top = required_top - set(doc)
    if missing_top:
        errors.append(f"missing top-level fields: {sorted(missing_top)}")
        return errors

    if doc["version"] != "skeleton.v1":
        errors.append("version must be skeleton.v1")

    phase_ids = [phase.get("id") for phase in doc.get("phases", [])]
    if not phase_ids:
        errors.append("phases must not be empty")
        return errors

    if len(phase_ids) != len(set(phase_ids)):
        errors.append("phase ids must be unique")

    if doc["root"] not in set(phase_ids):
        errors.append("root must reference an existing phase id")

    terminal_ids = set()
    for phase in doc["phases"]:
        kind = phase.get("kind")
        pid = phase.get("id")
        if not all(field in phase for field in ("id", "kind", "goal", "action")):
            errors.append(f"phase {pid or '?'} missing one of id/kind/goal/action")
            continue

        if kind == "terminal":
            if phase.get("terminal") is not True:
                errors.append(f"terminal phase {pid} must set terminal=true")
            terminal_ids.add(pid)
            continue

        manifestation = phase.get("manifestation")
        if manifestation is None:
            errors.append(f"phase {pid} missing manifestation")
        else:
            required_manifest = {"kernel_class", "dispersal", "execution_mode"}
            missing_manifest = required_manifest - set(manifestation)
            if missing_manifest:
                errors.append(
                    f"phase {pid} manifestation missing fields: {sorted(missing_manifest)}"
                )
            mode = manifestation.get("execution_mode")
            if mode == "runtime_vocab" and "runtime_vocab" not in manifestation:
                errors.append(f"phase {pid} runtime_vocab manifestation requires runtime_vocab")
            if mode == "curated_step_hash" and "activation_ref" not in manifestation:
                errors.append(f"phase {pid} curated_step_hash manifestation requires activation_ref")
            if manifestation.get("kernel_class") == "clarify" and manifestation.get("runtime_vocab") not in (None, "clarify_needed"):
                errors.append(f"phase {pid} clarify manifestation must use clarify_needed")

        if "allowed_vocab" not in phase:
            errors.append(f"phase {pid} missing allowed_vocab")
        if "post_diff" not in phase:
            errors.append(f"phase {pid} missing post_diff")
        if "transitions" not in phase and phase.get("terminal") is not True:
            errors.append(f"phase {pid} missing transitions")
        if "gap_template" not in phase and kind != "terminal":
            errors.append(f"phase {pid} missing gap_template")

        if kind == "mutate" and phase.get("requires_postcondition") and "on_done" not in phase.get("transitions", {}):
            errors.append(f"mutate phase {pid} requires a postcondition successor")

        if kind == "clarify":
            if phase.get("terminal") is not True:
                errors.append(f"clarify phase {pid} must be terminal")
            if phase.get("allowed_vocab") != ["clarify_needed"]:
                errors.append(f"clarify phase {pid} must allow only clarify_needed")
            terminal_ids.add(pid)

    for phase in doc["phases"]:
        for target in phase.get("transitions", {}).values():
            if target not in set(phase_ids):
                errors.append(f"phase {phase['id']} transition points to missing target {target}")

    closure = doc["closure"]
    success_terminal = closure.get("success", {}).get("requires_terminal")
    if success_terminal not in set(phase_ids):
        errors.append("closure.success.requires_terminal must reference an existing phase id")

    if success_terminal and success_terminal not in terminal_ids:
        errors.append("closure.success.requires_terminal must reference a terminal phase")

    return errors


def test_skeleton_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_skeleton_schema_declares_expected_top_level_contract():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["version"]["const"] == "skeleton.v1"
    assert set(schema["required"]) == {
        "version",
        "name",
        "desc",
        "trigger",
        "refs",
        "root",
        "phases",
        "closure",
    }


def test_skeleton_schema_has_phase_variants():
    schema = load_schema()
    phase_defs = schema["$defs"]["phase"]["oneOf"]
    assert len(phase_defs) == 9
    assert schema["$defs"]["phaseBase"]["properties"]["kind"]["enum"] == [
        "observe",
        "reason",
        "mutate",
        "verify",
        "higher_order",
        "clarify",
        "await",
        "embed",
        "terminal",
    ]
    manifestation = schema["$defs"]["manifestation"]
    assert manifestation["required"] == ["kernel_class", "dispersal", "execution_mode"]
    assert schema["$defs"]["executionMode"]["enum"] == ["runtime_vocab", "curated_step_hash", "inline"]
    assert schema["$defs"]["dispersalMode"]["enum"] == ["context", "action", "mixed", "embed"]


def test_skeleton_schema_restricts_vocab_to_runtime_surface():
    schema = load_schema()
    allowed = set(schema["$defs"]["anyRuntimeVocab"]["enum"])
    assert "hash_resolve_needed" in allowed
    assert "reason_needed" in allowed
    assert "hash_edit_needed" in allowed
    assert "scan_needed" not in allowed
    assert "research_needed" not in allowed
    assert "url_needed" not in allowed


def test_skeleton_schema_valid_example_contract():
    doc = {
        "version": "skeleton.v1",
        "name": "config_fix",
        "desc": "observe, assess, mutate, verify",
        "trigger": "manual",
        "refs": {
            "target": "blob:abc123",
            "context": "commit:def456"
        },
        "root": "phase_observe",
        "phases": [
            {
                "id": "phase_observe",
                "kind": "observe",
                "goal": "resolve target state",
                "action": "resolve_target_state",
                "gap_template": {
                    "desc": "current target state must be resolved",
                    "content_refs": ["@target", "@context"],
                    "step_refs": []
                },
                "manifestation": {
                    "kernel_class": "observe",
                    "dispersal": "context",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "hash_resolve_needed",
                    "protected_kind": "generic"
                },
                "allowed_vocab": ["hash_resolve_needed", "pattern_needed"],
                "post_diff": False,
                "resolve": ["target", "context"],
                "transitions": {
                    "on_done": "phase_reason"
                }
            },
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess mismatch",
                "action": "assess_and_route",
                "gap_template": {
                    "desc": "target must be assessed against referred context",
                    "content_refs": ["@target"],
                    "step_refs": ["$prev"]
                },
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "reason_needed",
                    "await_policy": "none"
                },
                "allowed_vocab": ["reason_needed", "hash_edit_needed", "clarify_needed"],
                "post_diff": True,
                "transitions": {
                    "on_mutate": "phase_mutate",
                    "on_clarify": "phase_clarify",
                    "on_close": "phase_done"
                }
            },
            {
                "id": "phase_mutate",
                "kind": "mutate",
                "goal": "apply change",
                "action": "apply_change",
                "gap_template": {
                    "desc": "target must be aligned",
                    "content_refs": ["@target"],
                    "step_refs": ["$prev"]
                },
                "manifestation": {
                    "kernel_class": "mutate",
                    "dispersal": "action",
                    "execution_mode": "curated_step_hash",
                    "activation_ref": "@target",
                    "activation_alias": "config_mutator",
                    "protected_kind": "action",
                    "emits_commit": True
                },
                "allowed_vocab": ["hash_edit_needed"],
                "post_diff": True,
                "requires_postcondition": True,
                "transitions": {
                    "on_done": "phase_verify"
                }
            },
            {
                "id": "phase_verify",
                "kind": "verify",
                "goal": "verify mutation result",
                "action": "verify_result",
                "gap_template": {
                    "desc": "result must be validated",
                    "content_refs": ["$commit"],
                    "step_refs": ["$prev"]
                },
                "manifestation": {
                    "kernel_class": "observe",
                    "dispersal": "mixed",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "hash_resolve_needed"
                },
                "allowed_vocab": ["hash_resolve_needed", "reason_needed"],
                "post_diff": True,
                "transitions": {
                    "on_close": "phase_done",
                    "on_redirect": "phase_reason"
                }
            },
            {
                "id": "phase_clarify",
                "kind": "clarify",
                "goal": "request missing context",
                "action": "ask_for_missing_context",
                "gap_template": {
                    "desc": "required information is missing",
                    "content_refs": [],
                    "step_refs": ["$prev"]
                },
                "manifestation": {
                    "kernel_class": "clarify",
                    "dispersal": "context",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "clarify_needed"
                },
                "allowed_vocab": ["clarify_needed"],
                "post_diff": False,
                "terminal": True
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "workflow closed",
                "action": "close_loop",
                "terminal": True
            }
        ],
        "closure": {
            "success": {
                "requires_terminal": "phase_done",
                "requires_no_active_gaps": True
            },
            "failure": {
                "allow_force_close": True,
                "allow_clarify_terminal": True
            },
            "limits": {
                "max_chain_depth": 15,
                "max_redirects": 4
            }
        }
    }

    assert validate_skeleton_contract(doc) == []


def test_skeleton_schema_invalid_example_contract():
    doc = {
        "version": "skeleton.v1",
        "name": "broken",
        "desc": "invalid example",
        "trigger": "manual",
        "refs": {},
        "root": "missing_phase",
        "phases": [
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess mismatch",
                "action": "assess_and_route",
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "curated_step_hash"
                },
                "allowed_vocab": ["reason_needed"]
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "done",
                "action": "close_loop"
            }
        ],
        "closure": {
            "success": {
                "requires_terminal": "phase_reason",
                "requires_no_active_gaps": True
            },
            "failure": {
                "allow_force_close": True,
                "allow_clarify_terminal": True
            },
            "limits": {
                "max_chain_depth": 15,
                "max_redirects": 4
            }
        }
    }

    errors = validate_skeleton_contract(doc)

    assert "root must reference an existing phase id" in errors
    assert "phase phase_reason curated_step_hash manifestation requires activation_ref" in errors
    assert "phase phase_reason missing transitions" in errors
    assert "phase phase_reason missing gap_template" in errors
    assert "terminal phase phase_done must set terminal=true" in errors
    assert "closure.success.requires_terminal must reference a terminal phase" in errors
