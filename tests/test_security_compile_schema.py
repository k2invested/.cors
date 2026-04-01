import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "security_compile.v1.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def valid_doc() -> dict:
    return {
        "version": "security_compile.v1",
        "input": {
            "artifact_type": "stepchain",
            "candidate_ref": "abc123def456",
            "source": "authoring",
            "mode": "pre_persist",
            "candidate": {
                "version": "stepchain.v1",
                "name": "review_flow"
            },
            "context": {
                "parent_chain": "chain123",
                "workspace_ref": "head456",
                "registry_refs": ["pkg111", "pkg222"]
            }
        },
        "result": {
            "status": "accepted_with_warnings",
            "artifact_type": "stepchain",
            "normalized": {
                "artifact_kind": "action",
                "root_kind": "reason",
                "node_count": 4,
                "edge_count": 3,
                "hash_refs": ["pkg111"],
                "protected_surface_targets": []
            },
            "checks": [
                {"domain": "structural_law", "verdict": "pass"},
                {"domain": "recursive_execution_risk", "verdict": "warn", "notes": ["post_diff fanout is bounded"]}
            ],
            "violations": [],
            "risks": [
                {
                    "domain": "recursive_execution_risk",
                    "code": "recursive_bridge_fanout",
                    "severity": "high",
                    "message": "Bridge phase can recursively emit mixed offspring without bounded closure.",
                    "path": "nodes.phase_reason",
                    "refs": ["pkg111"]
                }
            ],
            "projection": {
                "spawn_depth": 3,
                "branch_points": 2,
                "bridge_count": 1,
                "mutation_count": 1,
                "post_diff_reentry_points": 2,
                "background_reintegration_required": True,
                "await_required": False,
                "commit_consumption_required": True,
                "protected_surface_touches": []
            },
            "summary": "Accepted with warnings due to bounded recursive bridge fanout."
        }
    }


def test_security_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_security_schema_declares_expected_top_level_contract():
    schema = load_schema()
    assert schema["properties"]["version"]["const"] == "security_compile.v1"
    assert set(schema["required"]) == {"version", "input", "result"}


def test_security_schema_declares_supported_artifact_types():
    schema = load_schema()
    assert schema["$defs"]["artifactType"]["enum"] == [
        "atomic_step",
        "gap",
        "st_package",
        "skeleton",
        "semantic_skeleton",
        "stepchain",
        "realized_chain",
    ]


def test_security_schema_declares_check_domains():
    schema = load_schema()
    assert schema["$defs"]["checkDomain"]["enum"] == [
        "structural_law",
        "manifestation_law",
        "protected_surfaces",
        "recursive_execution_risk",
        "semantic_integrity",
    ]


def test_security_schema_valid_example_shape():
    doc = valid_doc()
    assert doc["result"]["status"] == "accepted_with_warnings"
    assert doc["result"]["projection"]["spawn_depth"] == 3
    assert doc["result"]["risks"][0]["code"] == "recursive_bridge_fanout"


def test_security_projection_requires_os_health_fields():
    schema = load_schema()
    projection = schema["$defs"]["projection"]
    assert projection["required"] == [
        "spawn_depth",
        "branch_points",
        "bridge_count",
        "mutation_count",
        "post_diff_reentry_points",
        "background_reintegration_required",
        "protected_surface_touches",
    ]
    assert "await_required" in projection["properties"]
    assert "commit_consumption_required" in projection["properties"]
