import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop
from compile import Compiler
from step import Gap, Step, Trajectory
from skills.loader import load_all


def registry():
    return load_all(str(ROOT / "skills"))


def test_entity_skill_detection_distinguishes_entity_from_action_and_codon():
    reg = registry()
    admin = reg.resolve_by_name("admin")
    hash_edit = reg.resolve_by_name("hash_edit")
    reason = reg.resolve_by_name("reason")

    assert admin is not None and loop._is_entity_skill(admin) is True
    assert hash_edit is not None and loop._is_entity_skill(hash_edit) is False
    assert reason is not None and loop._is_entity_skill(reason) is False


def test_render_entity_tree_shows_entity_space():
    reg = registry()
    tree = loop._render_entity_tree(reg)
    assert tree.startswith("entity_tree")
    assert "kenny:" in tree
    assert "admin.st" in tree


def example_stepchain() -> dict:
    return {
        "version": "stepchain.v1",
        "name": "review_flow",
        "desc": "review and verify",
        "trigger": "manual",
        "refs": {"target": "blob:abc123"},
        "root": "phase_reason",
        "phase_order": ["phase_reason", "phase_verify", "phase_done"],
        "nodes": [
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess",
                "action": "assess_and_route",
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "curated_step_hash",
                    "activation_ref": "flow:123",
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
                "gap_template": {
                    "desc": "target must be assessed",
                    "content_refs": ["blob:abc123"],
                    "step_refs": [],
                },
                "activation_key": "flow:123",
                "transitions": {"on_close": "phase_verify"},
            },
            {
                "id": "phase_verify",
                "kind": "verify",
                "goal": "verify",
                "action": "verify_result",
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
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": True,
                "gap_template": {
                    "desc": "result must be observed",
                    "content_refs": ["$commit"],
                    "step_refs": ["$prev"],
                },
                "activation_key": "hash_resolve_needed",
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
                "max_chain_depth": 8,
                "max_redirects": 2,
            },
        },
    }


def test_chain_package_persist_load_and_render(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "CHAINS_DIR", tmp_path)
    package = example_stepchain()
    package_hash = loop._persist_chain_package(package)
    loaded = loop._load_chain_package(package_hash)
    rendered = loop._render_chain_package(loaded, package_hash)

    assert loaded["version"] == "stepchain.v1"
    assert package_hash == loop._stable_doc_hash(package)
    assert rendered.startswith(f"stepchain:{package_hash}")
    assert "phase_reason" in rendered


def test_activate_stepchain_package_creates_runtime_gaps():
    package = example_stepchain()
    origin_step = Step.create(desc="origin")
    gap = Gap.create(desc="activate flow", content_refs=["blob:seed"])
    step = loop._activate_stepchain_package(package, "pkg123", gap, origin_step, "chain123")

    assert step.content_refs[0] == "pkg123"
    assert len(step.gaps) == 2
    assert step.gaps[0].desc == "target must be assessed"
    assert step.gaps[0].vocab == "reason_needed"
    assert "flow:123" in step.gaps[0].content_refs
    assert step.gaps[1].vocab == "hash_resolve_needed"


def test_resolve_hash_renders_persisted_stepchain_package(tmp_path, monkeypatch):
    monkeypatch.setattr(loop, "CHAINS_DIR", tmp_path)
    traj = Trajectory()
    package_hash = loop._persist_chain_package(example_stepchain())
    rendered = loop.resolve_hash(package_hash, traj)
    assert rendered is not None
    assert rendered.startswith(f"stepchain:{package_hash}")


def test_background_trigger_refs_round_trip():
    compiler = Compiler(Trajectory())
    compiler.record_background_trigger("chain_a", refs=["abc123", "def456"])
    compiler.record_background_trigger("chain_b", refs=["abc123"])
    assert compiler.needs_heartbeat() is True
    assert compiler.background_refs() == ["abc123", "def456"]
