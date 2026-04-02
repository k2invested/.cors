import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SEMANTIC_SCHEMA = ROOT / "schemas" / "semantic_skeleton.v1.json"

from tools import semantic_skeleton_compile as semantic_compile_module


def load_schema() -> dict:
    return json.loads(SEMANTIC_SCHEMA.read_text())


def entity_doc() -> dict:
    return {
        "version": "semantic_skeleton.v1",
        "artifact": {
            "kind": "entity",
            "protected_kind": "entity",
            "lineage": "kenny",
            "version_strategy": "hash_pinned",
        },
        "name": "kenny",
        "desc": "primary architect entity",
        "trigger": "manual",
        "refs": {
            "self_hash": "abc123def456",
        },
        "semantics": {
            "identity": {
                "name": "Kenny",
                "role": "architect",
            },
            "preferences": {
                "communication": {
                    "style": "direct",
                }
            },
            "domain_knowledge": {
                "system": "cors"
            }
        }
    }


def hybrid_doc() -> dict:
    return {
        "version": "semantic_skeleton.v1",
        "artifact": {
            "kind": "hybrid",
            "protected_kind": "action",
            "lineage": "review_flow",
            "version_strategy": "hash_pinned",
        },
        "name": "review_flow",
        "desc": "review with persistent domain context",
        "trigger": "manual",
        "refs": {
            "target": "blob:abc123",
            "reviewer_flow": "9a8b7c6d5e4f",
        },
        "semantics": {
            "scope": "review and feedback",
            "entity_refs": ["kenny:abc123def456"]
        },
        "root": "phase_reason",
        "phases": [
            {
                "id": "phase_reason",
                "kind": "reason",
                "goal": "assess and route",
                "action": "assess_and_route",
                "gap_template": {
                    "desc": "target must be reviewed",
                    "content_refs": ["@target"],
                    "step_refs": []
                },
                "manifestation": {
                    "kernel_class": "bridge",
                    "dispersal": "mixed",
                    "execution_mode": "curated_step_hash",
                    "activation_ref": "@reviewer_flow",
                    "activation_alias": "reviewer_flow"
                },
                "generation": {
                    "spawn_mode": "mixed",
                    "spawn_trigger": "conditional",
                    "branch_policy": "depth_first_to_parent",
                    "sibling_policy": "after_descendants",
                    "return_policy": "resume_transition"
                },
                "allowed_vocab": ["reason_needed", "hash_edit_needed"],
                "post_diff": True,
                "transitions": {
                    "on_close": "phase_done"
                }
            },
            {
                "id": "phase_done",
                "kind": "terminal",
                "goal": "done",
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


def test_semantic_schema_file_exists():
    assert SEMANTIC_SCHEMA.exists()


def test_semantic_schema_declares_unified_artifact_kinds():
    schema = load_schema()
    assert schema["properties"]["version"]["const"] == "semantic_skeleton.v1"
    assert schema["$defs"]["artifactKind"]["enum"] == ["entity", "action", "hybrid"]
    assert schema["properties"]["existing_ref"]["type"] == "string"
    assert "init" in schema["$defs"]["semantics"]["properties"]


def test_semantic_compile_accepts_entity_only_doc():
    result = semantic_compile_module.compile_semantic_skeleton(entity_doc())
    assert result["status"] == "ok"
    package = result["package"]
    assert package["artifact"]["kind"] == "entity"
    assert "semantics" in package
    assert "stepchain" not in package


def test_semantic_compile_accepts_hybrid_doc_and_lowers_stepchain():
    result = semantic_compile_module.compile_semantic_skeleton(hybrid_doc())
    assert result["status"] == "ok"
    package = result["package"]
    assert package["artifact"]["kind"] == "hybrid"
    assert package["semantics"]["scope"] == "review and feedback"
    assert package["stepchain"]["version"] == "stepchain.v1"
    node = package["stepchain"]["nodes"][0]
    assert node["manifestation"]["activation_ref"] == "9a8b7c6d5e4f"
    assert node["activation_key"] == "9a8b7c6d5e4f"


def test_semantic_compile_rejects_entity_without_semantics():
    broken = entity_doc()
    del broken["semantics"]
    result = semantic_compile_module.compile_semantic_skeleton(broken)
    assert result["status"] == "error"
    assert "entity artifact requires semantics" in result["errors"]


def test_semantic_compile_rejects_action_without_workflow_fields():
    broken = entity_doc()
    broken["artifact"]["kind"] = "action"
    result = semantic_compile_module.compile_semantic_skeleton(broken)
    assert result["status"] == "error"
    assert "action artifact requires root" in result["errors"]


def test_semantic_compile_cli_outputs_package():
    payload = json.dumps(hybrid_doc())
    result = subprocess.run(
        ["python3", str(ROOT / "tools" / "semantic_skeleton_compile.py")],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["package"]["artifact"]["kind"] == "hybrid"
