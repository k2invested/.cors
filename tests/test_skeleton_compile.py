import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import skeleton_compile as skeleton_compile_module
from tools import st_builder as st_builder_module


def example_skeleton() -> dict:
    return {
        "version": "skeleton.v1",
        "name": "config_fix",
        "desc": "observe, assess, mutate, verify",
        "trigger": "manual",
        "refs": {
            "target": "blob:abc123",
            "workflow_hash": "2f3e4d5c6b7a",
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
                    "content_refs": ["@target"],
                    "step_refs": [],
                },
                "manifestation": {
                    "kernel_class": "observe",
                    "dispersal": "context",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "hash_resolve_needed",
                },
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
                "transitions": {"on_done": "phase_reason"},
            },
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "route work",
                "action": "assess_and_route",
                "gap_template": {
                    "desc": "target must be assessed against referred context",
                    "content_refs": ["@target"],
                    "step_refs": ["$prev"],
                },
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "reason_needed",
                },
                "allowed_vocab": ["reason_needed", "hash_edit_needed"],
                "post_diff": True,
                "transitions": {"on_mutate": "phase_mutate", "on_close": "phase_done"},
            },
            {
                "id": "phase_mutate",
                "kind": "mutate",
                "goal": "apply change",
                "action": "apply_change",
                "gap_template": {
                    "desc": "target must be aligned",
                    "content_refs": ["@target"],
                    "step_refs": ["$prev"],
                },
                "manifestation": {
                    "kernel_class": "mutate",
                    "dispersal": "action",
                    "execution_mode": "curated_step_hash",
                    "activation_ref": "@workflow_hash",
                    "activation_alias": "config_mutator",
                    "emits_commit": True,
                    "protected_kind": "action",
                },
                "allowed_vocab": ["hash_edit_needed"],
                "post_diff": True,
                "requires_postcondition": True,
                "transitions": {"on_done": "phase_done"},
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "done",
                "action": "close_loop",
                "terminal": True,
            },
        ],
        "closure": {
            "success": {
                "requires_terminal": "phase_done",
                "requires_no_active_gaps": True,
            },
            "failure": {
                "allow_force_close": True,
                "allow_clarify_terminal": True,
            },
            "limits": {
                "max_chain_depth": 15,
                "max_redirects": 4,
            },
        },
    }


def test_compile_skeleton_returns_stepchain_package():
    result = skeleton_compile_module.compile_skeleton(example_skeleton())
    assert result["status"] == "ok"
    stepchain = result["stepchain"]
    assert stepchain["version"] == "stepchain.v1"
    assert stepchain["source_version"] == "skeleton.v1"
    assert stepchain["root"] == "phase_observe"
    assert stepchain["phase_order"] == ["phase_observe", "phase_reason", "phase_mutate", "phase_done"]


def test_compile_skeleton_resolves_top_level_symbolic_refs():
    stepchain = skeleton_compile_module.compile_skeleton(example_skeleton())["stepchain"]
    observe = next(node for node in stepchain["nodes"] if node["id"] == "phase_observe")
    mutate = next(node for node in stepchain["nodes"] if node["id"] == "phase_mutate")
    assert observe["gap_template"]["content_refs"] == ["blob:abc123"]
    assert mutate["manifestation"]["activation_ref"] == "2f3e4d5c6b7a"
    assert mutate["activation_key"] == "2f3e4d5c6b7a"


def test_compile_skeleton_derives_priority_from_structure():
    stepchain = skeleton_compile_module.compile_skeleton(example_skeleton())["stepchain"]
    priorities = {node["id"]: node.get("priority") for node in stepchain["nodes"]}
    assert priorities["phase_observe"] == 20
    assert priorities["phase_reason"] == 90
    assert priorities["phase_mutate"] == 40


def test_compile_skeleton_groups_allowed_vocab_by_family():
    stepchain = skeleton_compile_module.compile_skeleton(example_skeleton())["stepchain"]
    reason = next(node for node in stepchain["nodes"] if node["id"] == "phase_reason")
    assert reason["vocab_buckets"]["bridge"] == ["reason_needed"]
    assert reason["vocab_buckets"]["mutate"] == ["hash_edit_needed"]


def test_compile_skeleton_rejects_invalid_contract():
    broken = example_skeleton()
    del broken["phases"][1]["manifestation"]["runtime_vocab"]
    result = skeleton_compile_module.compile_skeleton(broken)
    assert result["status"] == "error"
    assert any("runtime_vocab manifestation requires runtime_vocab" in error for error in result["errors"])


def test_st_builder_detects_skeleton_input():
    assert st_builder_module.looks_like_skeleton(example_skeleton()) is True
    assert st_builder_module.looks_like_skeleton({"name": "entity", "desc": "d", "actions": []}) is False


def test_st_builder_cli_rejects_skeleton_input():
    payload = json.dumps(example_skeleton())
    result = subprocess.run(
        ["python3", str(ROOT / "tools" / "st_builder.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 1
    assert "skeleton.v1 input should be compiled with tools/skeleton_compile.py" in result.stdout


def test_skeleton_compile_cli_outputs_json():
    payload = json.dumps(example_skeleton())
    result = subprocess.run(
        ["python3", str(ROOT / "tools" / "skeleton_compile.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["stepchain"]["version"] == "stepchain.v1"
