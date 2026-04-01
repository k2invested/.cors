import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import security_compile as security_compile_module


def gap_doc(vocab="hash_resolve_needed", desc="inspect current state") -> dict:
    return {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "gap",
            "source": "runtime",
            "mode": "pre_admission",
            "candidate": {
                "hash": "gap123",
                "desc": desc,
                "content_refs": ["blob:abc123"],
                "step_refs": ["step:def456"],
                "vocab": vocab,
                "scores": {
                    "relevance": 0.8,
                    "confidence": 0.7,
                    "grounded": 0.4,
                },
            },
        },
        "result": {},
    }


def stepchain_doc() -> dict:
    return {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "stepchain",
            "source": "authoring",
            "mode": "pre_persist",
            "candidate": {
                "version": "stepchain.v1",
                "name": "review_flow",
                "desc": "review and refine",
                "trigger": "manual",
                "root": "phase_reason",
                "phase_order": ["phase_reason", "phase_mutate", "phase_done"],
                "nodes": [
                    {
                        "id": "phase_reason",
                        "kind": "reason",
                        "goal": "assess and branch",
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
                        "gap_template": {
                            "desc": "review target and route next action",
                            "content_refs": ["blob:abc123"],
                            "step_refs": [],
                        },
                        "transitions": {"on_mutate": "phase_mutate", "on_close": "phase_done"},
                    },
                    {
                        "id": "phase_mutate",
                        "kind": "mutate",
                        "goal": "apply fix",
                        "manifestation": {
                            "kernel_class": "mutate",
                            "dispersal": "action",
                            "execution_mode": "runtime_vocab",
                            "runtime_vocab": "hash_edit_needed",
                            "emits_commit": True,
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
                        "gap_template": {
                            "desc": "apply patch to target",
                            "content_refs": ["blob:abc123"],
                            "step_refs": ["$prev"],
                        },
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
            },
        },
        "result": {},
    }


def test_security_compile_accepts_simple_gap():
    result = security_compile_module.security_compile(gap_doc())
    assert result["result"]["status"] == "accepted"
    assert result["result"]["artifact_type"] == "gap"
    assert result["result"]["projection"]["mutation_count"] == 0


def test_security_compile_rejects_invalid_gap_vocab():
    result = security_compile_module.security_compile(gap_doc(vocab="url_needed"))
    assert result["result"]["status"] == "rejected"
    codes = {item["code"] for item in result["result"]["violations"]}
    assert "invalid_runtime_vocab" in codes


def test_security_compile_warns_on_desc_vocab_mismatch():
    result = security_compile_module.security_compile(gap_doc(vocab="hash_edit_needed", desc="inspect and verify current state"))
    assert result["result"]["status"] == "accepted_with_warnings"
    codes = {item["code"] for item in result["result"]["risks"]}
    assert "semantic_desc_vocab_mismatch" in codes


def test_security_compile_warns_on_recursive_stepchain_pattern():
    result = security_compile_module.security_compile(stepchain_doc())
    assert result["result"]["status"] == "accepted_with_warnings"
    projection = result["result"]["projection"]
    assert projection["bridge_count"] == 1
    assert projection["mutation_count"] == 1
    codes = {item["code"] for item in result["result"]["risks"]}
    assert "recursive_bridge_fanout" in codes


def test_security_compile_accepts_atomic_step_shape():
    doc = {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "atomic_step",
            "source": "runtime",
            "mode": "retrospective_audit",
            "candidate": {
                "hash": "step123",
                "desc": "observed state and emitted one gap",
                "step_refs": ["step_root"],
                "content_refs": ["blob:abc123"],
                "gaps": [
                    {
                        "hash": "gap456",
                        "desc": "apply fix",
                        "content_refs": ["blob:abc123"],
                        "step_refs": ["step123"],
                        "vocab": "hash_edit_needed",
                        "scores": {"relevance": 0.8, "confidence": 0.6, "grounded": 0.4},
                    }
                ],
            },
        },
        "result": {},
    }
    result = security_compile_module.security_compile(doc)
    assert result["result"]["artifact_type"] == "atomic_step"
    assert result["result"]["normalized"]["node_count"] >= 2


def test_security_compile_accepts_realized_chain_shape():
    doc = {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "realized_chain",
            "source": "runtime",
            "mode": "retrospective_audit",
            "candidate": {
                "hash": "chain123",
                "steps": [
                    {
                        "hash": "step_a",
                        "desc": "observe current state",
                        "content_refs": ["blob:abc123"],
                        "step_refs": [],
                        "gaps": [
                            {
                                "hash": "gap_a",
                                "desc": "apply patch",
                                "content_refs": ["blob:abc123"],
                                "step_refs": ["step_a"],
                                "vocab": "hash_edit_needed",
                                "scores": {"relevance": 0.8, "confidence": 0.7, "grounded": 0.5},
                            }
                        ],
                    },
                    {
                        "hash": "step_b",
                        "desc": "applied patch",
                        "content_refs": ["blob:abc123"],
                        "step_refs": ["step_a"],
                        "commit": "commit123",
                        "gaps": [],
                    },
                ],
            },
        },
        "result": {},
    }
    result = security_compile_module.security_compile(doc)
    assert result["result"]["artifact_type"] == "realized_chain"
    assert result["result"]["projection"]["mutation_count"] >= 1


def test_security_compile_embedded_package_adds_activation_cascade_warning():
    doc = stepchain_doc()
    doc["input"]["candidate"]["nodes"][0]["manifestation"]["activation_ref"] = "72b1d5ffc964"
    result = security_compile_module.security_compile(doc)
    codes = {item["code"] for item in result["result"]["risks"]}
    assert "activation_cascade" in codes


def test_security_compile_rejects_codon_surface_persist():
    doc = {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "st_package",
            "candidate_path": "skills/codons/reason.st",
            "source": "authoring",
            "mode": "pre_persist",
            "candidate": {},
        },
        "result": {},
    }
    result = security_compile_module.security_compile(doc)
    assert result["result"]["status"] == "rejected"
    codes = {item["code"] for item in result["result"]["violations"]}
    assert "codon_mutation_attempt" in codes


def test_security_compile_allows_codon_activation_surface():
    doc = {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "st_package",
            "candidate_path": "skills/codons/reason.st",
            "source": "registry",
            "mode": "pre_activation",
            "candidate": {},
        },
        "result": {},
    }
    result = security_compile_module.security_compile(doc)
    assert result["result"]["status"] != "rejected"


def test_security_compile_cli_outputs_contract():
    payload = json.dumps(gap_doc())
    result = subprocess.run(
        ["python3", str(ROOT / "tools" / "security_compile.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["version"] == "security_compile.v1"
    assert data["result"]["artifact_type"] == "gap"
