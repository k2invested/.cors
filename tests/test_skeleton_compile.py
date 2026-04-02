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
                "generation": {
                    "spawn_mode": "none",
                    "spawn_trigger": "none",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
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
                "generation": {
                    "spawn_mode": "mixed",
                    "spawn_trigger": "conditional",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
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
                "generation": {
                    "spawn_mode": "action",
                    "spawn_trigger": "on_post_diff",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
                },
                "allowed_vocab": ["hash_edit_needed"],
                "post_diff": True,
                "requires_postcondition": True,
                "transitions": {"on_done": "phase_verify"},
            },
            {
                "id": "phase_verify",
                "kind": "verify",
                "goal": "verify result",
                "action": "verify_result",
                "gap_template": {
                    "desc": "mutation result must be observed",
                    "content_refs": ["$commit"],
                    "step_refs": ["$prev"],
                },
                "manifestation": {
                    "kernel_class": "observe",
                    "dispersal": "mixed",
                    "execution_mode": "runtime_vocab",
                    "runtime_vocab": "hash_resolve_needed",
                },
                "generation": {
                    "spawn_mode": "mixed",
                    "spawn_trigger": "on_post_diff",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition",
                },
                "allowed_vocab": ["hash_resolve_needed", "reason_needed"],
                "post_diff": True,
                "transitions": {"on_close": "phase_done"},
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
    assert stepchain["phase_order"] == [
        "phase_observe",
        "phase_reason",
        "phase_mutate",
        "phase_verify",
        "phase_done",
    ]


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


def test_compile_skeleton_preserves_generation_contract():
    stepchain = skeleton_compile_module.compile_skeleton(example_skeleton())["stepchain"]
    reason = next(node for node in stepchain["nodes"] if node["id"] == "phase_reason")
    mutate = next(node for node in stepchain["nodes"] if node["id"] == "phase_mutate")
    assert reason["generation"]["spawn_mode"] == "mixed"
    assert reason["generation"]["spawn_trigger"] == "conditional"
    assert mutate["generation"]["branch_policy"] == "depth_first_to_parent"


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


def test_compile_skeleton_rejects_invalid_generation_reentry():
    broken = example_skeleton()
    broken["phases"][0]["generation"]["spawn_mode"] = "context"
    broken["phases"][0]["generation"]["spawn_trigger"] = "on_post_diff"
    result = skeleton_compile_module.compile_skeleton(broken)
    assert result["status"] == "error"
    assert any("uses on_post_diff offspring but post_diff is false" in error for error in result["errors"])


def test_compile_skeleton_rejects_mutation_without_observe_closure():
    broken = example_skeleton()
    broken["phases"][2]["transitions"] = {"on_done": "phase_done"}
    result = skeleton_compile_module.compile_skeleton(broken)
    assert result["status"] == "error"
    assert any("must reach observe/verify before terminal or next mutate" in error for error in result["errors"])


def test_compile_skeleton_rejects_commit_without_commit_consumer():
    broken = example_skeleton()
    broken["phases"][3]["gap_template"]["content_refs"] = ["@target"]
    result = skeleton_compile_module.compile_skeleton(broken)
    assert result["status"] == "error"
    assert any("emits_commit but no downstream phase consumes $commit" in error for error in result["errors"])


def test_compile_skeleton_rejects_unreachable_phase():
    broken = example_skeleton()
    broken["phases"].insert(
        -1,
        {
            "id": "phase_orphan",
            "kind": "observe",
            "goal": "orphan",
            "action": "observe_orphan",
            "gap_template": {
                "desc": "orphan",
                "content_refs": [],
                "step_refs": [],
            },
            "manifestation": {
                "kernel_class": "observe",
                "dispersal": "context",
                "execution_mode": "runtime_vocab",
                "runtime_vocab": "hash_resolve_needed",
            },
            "generation": {
                "spawn_mode": "none",
                "spawn_trigger": "none",
                "branch_policy": "depth_first_to_parent",
                "sibling_policy": "after_descendants",
                "return_policy": "resume_transition",
            },
            "allowed_vocab": ["hash_resolve_needed"],
            "post_diff": False,
            "transitions": {"on_done": "phase_done"},
        },
    )
    result = skeleton_compile_module.compile_skeleton(broken)
    assert result["status"] == "error"
    assert any("phase phase_orphan is unreachable from root phase_observe" in error for error in result["errors"])


def test_st_builder_detects_skeleton_input():
    assert st_builder_module.looks_like_skeleton(example_skeleton()) is True
    assert st_builder_module.looks_like_skeleton({"name": "entity", "desc": "d", "actions": []}) is False


def test_st_builder_detects_semantic_skeleton_input():
    assert st_builder_module.looks_like_semantic_skeleton({
        "version": "semantic_skeleton.v1",
        "artifact": {"kind": "entity"},
        "name": "entity",
        "desc": "d",
        "trigger": "manual",
        "refs": {},
        "semantics": {},
    }) is True


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


def test_st_builder_cli_rejects_new_action_origination():
    payload = json.dumps({
        "artifact_kind": "action",
        "name": "new_workflow",
        "desc": "should be compiled from skeleton",
        "steps": [{"action": "inspect", "desc": "inspect", "vocab": "hash_resolve_needed"}],
    })
    result = subprocess.run(
        ["python3", str(ROOT / "tools" / "st_builder.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 1
    assert "new action or hybrid workflow origination belongs to skeleton.v1" in result.stdout


def test_lower_semantic_skeleton_to_entity_intent():
    doc = {
        "version": "semantic_skeleton.v1",
        "artifact": {
            "kind": "entity",
            "protected_kind": "entity",
            "lineage": "admin",
            "version_strategy": "hash_pinned",
        },
        "name": "admin",
        "desc": "admin identity",
        "trigger": "on_contact:discord:1",
        "refs": {"architect": "abc123"},
        "existing_ref": "deadbeefcafe",
        "semantics": {
            "identity": {"name": "Kenny"},
            "preferences": {"communication": {"style": "direct"}},
            "init": {"status": "pending"},
        },
    }

    lowered, artifact_kind, existing_ref = st_builder_module.lower_semantic_skeleton(doc)
    assert artifact_kind == "entity"
    assert existing_ref == "deadbeefcafe"
    assert lowered["identity"]["name"] == "Kenny"
    assert lowered["preferences"]["communication"]["style"] == "direct"
    assert lowered["init"]["status"] == "pending"


def test_semantic_skeleton_from_st_derives_flow_from_steps():
    st = {
        "name": "review_flow",
        "desc": "review flow",
        "trigger": "manual",
        "refs": {"target": "blob:abc123"},
        "steps": [
            {
                "action": "inspect_target",
                "desc": "inspect current target state",
                "vocab": "hash_resolve_needed",
                "post_diff": False,
                "resolve": ["@target"],
            },
            {
                "action": "persist_update",
                "desc": "persist updated semantic state",
                "vocab": "reprogramme_needed",
                "post_diff": False,
            },
        ],
        "preferences": {"workflow": {"bridge_first": True}},
    }

    frame = st_builder_module.semantic_skeleton_from_st(st, existing_ref="abc123def456")
    assert frame["version"] == "semantic_skeleton.v1"
    assert frame["artifact"]["kind"] == "hybrid"
    assert frame["existing_ref"] == "abc123def456"
    assert frame["root"].startswith("phase_")
    assert len(frame["phases"]) == 3
    assert frame["phases"][0]["gap_template"]["desc"] == "inspect current target state"
    assert frame["phases"][1]["manifestation"]["runtime_vocab"] == "reprogramme_needed"


def test_st_builder_writes_existing_ref_in_place(tmp_path):
    original = {
        "name": "entity_a",
        "desc": "old",
        "trigger": "manual",
        "steps": [],
        "identity": {"name": "Ada"},
    }
    original_path = tmp_path / "entity_a.st"
    original_path.write_text(json.dumps(original, indent=2))
    existing_ref = st_builder_module.compute_skill_hash(original_path.read_text())

    updated = {
        "name": "entity_a",
        "desc": "new",
        "trigger": "manual",
        "steps": [],
        "identity": {"name": "Ada"},
    }
    path = st_builder_module.write_st(updated, output_dir=str(tmp_path), existing_ref=existing_ref)
    assert path == str(original_path)
    written = json.loads(original_path.read_text())
    assert written["desc"] == "new"


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
