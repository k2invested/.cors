import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "trace_tree.v1.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def valid_doc() -> dict:
    return {
        "version": "trace_tree.v1",
        "source_type": "realized_chain",
        "source_ref": "chainabc123",
        "root_trace": "trace_root",
        "traces": [
            {
                "id": "trace_root",
                "source_step": "stepaaa111",
                "gap": {
                    "hash": "gaproot111",
                    "desc": "target must be assessed",
                    "vocab": "reason_needed",
                    "status": "active",
                    "step_refs": [],
                    "content_refs": ["blob:abc123"],
                    "step_ref_count": 0,
                    "content_ref_count": 1,
                    "score_bands": {
                        "relevance": 8,
                        "confidence": 7,
                        "grounded": 2
                    },
                    "signature": "{?b872/0:1}"
                },
                "manifestation": {
                    "kind": "bridge",
                    "spawn_mode": "mixed",
                    "spawn_trigger": "conditional",
                    "post_diff": True,
                    "activation_mode": "curated_step_hash",
                    "activation_ref": "pkg111",
                    "background": False,
                    "return_policy": "resume_transition"
                },
                "topology": {
                    "depth": 0,
                    "generation": 0,
                    "child_ids": ["trace_verify"],
                    "sibling_index": 0,
                    "sibling_count": 2,
                    "sibling_policy": "after_descendants",
                    "blocked_siblings": ["trace_sibling"]
                },
                "outcome": {
                    "terminal_state": "resolved",
                    "return_target": "trace_verify",
                    "closure_reason": "reason routed into verify branch"
                }
            },
            {
                "id": "trace_verify",
                "source_phase": "phase_verify",
                "gap": {
                    "hash": "gapverify222",
                    "desc": "result must be observed",
                    "vocab": "hash_resolve_needed",
                    "status": "resolved",
                    "step_refs": ["stepaaa111"],
                    "content_refs": ["commit:def456"],
                    "step_ref_count": 1,
                    "content_ref_count": 1,
                    "score_bands": {
                        "relevance": 7,
                        "confidence": 6,
                        "grounded": 6
                    }
                },
                "manifestation": {
                    "kind": "verify",
                    "spawn_mode": "none",
                    "spawn_trigger": "none",
                    "post_diff": False,
                    "activation_mode": "runtime_vocab",
                    "emitted_commit": False,
                    "return_policy": "terminal"
                },
                "topology": {
                    "parent_id": "trace_root",
                    "depth": 1,
                    "generation": 1,
                    "child_ids": [],
                    "sibling_index": 0,
                    "sibling_count": 1,
                    "sibling_policy": "after_descendants",
                    "blocked_siblings": []
                },
                "outcome": {
                    "terminal_state": "resolved",
                    "closure_reason": "postcondition closed"
                }
            }
        ],
        "summary": {
            "max_depth": 1,
            "generation_count": 2,
            "bridge_nodes": 1,
            "mutation_nodes": 0,
            "reentry_points": 1,
            "await_nodes": 0,
            "background_nodes": 0
        }
    }


def test_trace_tree_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_trace_tree_schema_declares_top_level_contract():
    schema = load_schema()
    assert schema["properties"]["version"]["const"] == "trace_tree.v1"
    assert set(schema["required"]) == {"version", "source_type", "root_trace", "traces"}


def test_trace_tree_schema_declares_supported_source_types():
    schema = load_schema()
    assert schema["$defs"]["sourceType"]["enum"] == [
        "trajectory",
        "realized_chain",
        "stepchain",
        "skeleton",
        "semantic_skeleton",
        "manual_fixture",
    ]


def test_trace_tree_schema_declares_required_trace_node_sections():
    schema = load_schema()
    trace_node = schema["$defs"]["traceNode"]
    assert trace_node["required"] == ["id", "gap", "manifestation", "topology", "outcome"]
    manifestation = schema["$defs"]["manifestation"]
    assert manifestation["required"] == [
        "kind",
        "spawn_mode",
        "spawn_trigger",
        "post_diff",
        "activation_mode",
        "return_policy",
    ]


def test_trace_tree_schema_valid_example_shape():
    doc = valid_doc()
    assert doc["root_trace"] == "trace_root"
    assert doc["traces"][0]["manifestation"]["kind"] == "bridge"
    assert doc["traces"][0]["topology"]["blocked_siblings"] == ["trace_sibling"]
    assert doc["summary"]["reentry_points"] == 1
