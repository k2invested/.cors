import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import trace_tree_build as trace_tree_build_module


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
                    "spawn_mode": "none",
                    "spawn_trigger": "none",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "terminal",
                },
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
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
            "success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True},
            "failure": {"allow_force_close": True, "allow_clarify_terminal": True},
            "limits": {"max_chain_depth": 8, "max_redirects": 2},
        },
    }


def example_realized_chain() -> dict:
    return {
        "hash": "chain123",
        "origin_gap": "gaproot",
        "desc": "review flow",
        "resolved": False,
        "steps": [
            {
                "hash": "step1",
                "desc": "assessed target",
                "gaps": [
                    {
                        "hash": "gap1",
                        "desc": "target must be assessed",
                        "content_refs": ["blob:abc123"],
                        "step_refs": [],
                        "scores": {"relevance": 0.8, "confidence": 0.7, "grounded": 0.2},
                        "vocab": "reason_needed",
                    }
                ],
            },
            {
                "hash": "step2",
                "desc": "verified result",
                "step_refs": ["step1"],
                "gaps": [
                    {
                        "hash": "gap2",
                        "desc": "result must be observed",
                        "content_refs": ["commit:def456"],
                        "step_refs": ["step1"],
                        "scores": {"relevance": 0.7, "confidence": 0.6, "grounded": 0.6},
                        "vocab": "hash_resolve_needed",
                        "resolved": True,
                    }
                ],
            },
        ],
    }


def example_skeleton() -> dict:
    return {
        "version": "skeleton.v1",
        "name": "review_flow",
        "desc": "review and verify",
        "trigger": "manual",
        "refs": {"target": "blob:abc123"},
        "root": "phase_reason",
        "phases": [
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess",
                "action": "assess_and_route",
                "gap_template": {
                    "desc": "target must be assessed",
                    "content_refs": ["@target"],
                    "step_refs": [],
                },
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
                "allowed_vocab": ["reason_needed"],
                "post_diff": True,
                "transitions": {"on_close": "phase_verify"},
            },
            {
                "id": "phase_verify",
                "kind": "verify",
                "goal": "verify",
                "action": "verify_result",
                "gap_template": {
                    "desc": "result must be observed",
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
                    "spawn_mode": "none",
                    "spawn_trigger": "none",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "terminal",
                },
                "allowed_vocab": ["hash_resolve_needed"],
                "post_diff": False,
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
            "success": {"requires_terminal": "phase_done", "requires_no_active_gaps": True},
            "failure": {"allow_force_close": True, "allow_clarify_terminal": True},
            "limits": {"max_chain_depth": 8, "max_redirects": 2},
        },
    }


def test_build_trace_tree_from_stepchain():
    result = trace_tree_build_module.build_trace_tree({
        "artifact_type": "stepchain",
        "candidate": example_stepchain(),
        "source_ref": "pkg123",
    })
    assert result["status"] == "ok"
    trace_tree = result["trace_tree"]
    assert trace_tree["version"] == "trace_tree.v1"
    assert trace_tree["source_type"] == "stepchain"
    assert trace_tree["root_trace"] == "trace_phase_reason"
    assert trace_tree["traces"][0]["manifestation"]["kind"] == "bridge"


def test_build_trace_tree_from_realized_chain():
    result = trace_tree_build_module.build_trace_tree({
        "artifact_type": "realized_chain",
        "candidate": example_realized_chain(),
    })
    assert result["status"] == "ok"
    trace_tree = result["trace_tree"]
    assert trace_tree["source_type"] == "realized_chain"
    assert trace_tree["root_trace"] == "trace_gap1"
    assert len(trace_tree["traces"]) == 2
    assert trace_tree["traces"][1]["outcome"]["terminal_state"] == "resolved"


def test_build_trace_tree_derives_from_canonical_semantic_tree(monkeypatch):
    calls = []
    original = trace_tree_build_module.manifest_engine_module.build_semantic_tree

    def wrapped(doc, *, source_type, source_ref=None):
        calls.append((source_type, source_ref))
        return original(doc, source_type=source_type, source_ref=source_ref)

    monkeypatch.setattr(trace_tree_build_module.manifest_engine_module, "build_semantic_tree", wrapped)
    result = trace_tree_build_module.build_trace_tree({
        "artifact_type": "stepchain",
        "candidate": example_stepchain(),
        "source_ref": "pkg123",
    })
    assert result["status"] == "ok"
    assert calls == [("stepchain", "pkg123")]


def test_build_trace_tree_from_skeleton():
    result = trace_tree_build_module.build_trace_tree({
        "artifact_type": "skeleton",
        "candidate": example_skeleton(),
    })
    assert result["status"] == "ok"
    assert result["trace_tree"]["source_type"] == "skeleton"
    assert result["trace_tree"]["summary"]["bridge_nodes"] == 1


def test_trace_tree_cli_outputs_contract():
    proc = subprocess.run(
        ["python3", str(ROOT / "tools" / "trace_tree_build.py")],
        input=json.dumps({"artifact_type": "stepchain", "candidate": example_stepchain()}),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "ok"
    assert data["trace_tree"]["version"] == "trace_tree.v1"
