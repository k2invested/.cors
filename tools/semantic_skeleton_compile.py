#!/usr/bin/env python3
"""semantic_skeleton_compile — unified semantic_skeleton.v1 compiler.

Entity, action, and hybrid artifacts share one semantic envelope here.
Action structure is lowered through the deterministic skeleton compiler.
Entity semantics are preserved as package metadata.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.skeleton_compile import compile_skeleton


def validate_semantic_skeleton(doc: dict) -> list[str]:
    errors: list[str] = []
    required = {"version", "artifact", "name", "desc", "trigger", "refs"}
    missing = required - set(doc)
    if missing:
        return [f"missing top-level fields: {sorted(missing)}"]

    if doc["version"] != "semantic_skeleton.v1":
        errors.append("version must be semantic_skeleton.v1")

    artifact = doc.get("artifact", {})
    kind = artifact.get("kind")
    if kind not in {"entity", "action", "hybrid"}:
        errors.append("artifact.kind must be entity, action, or hybrid")
        return errors

    if kind == "entity":
        if "semantics" not in doc:
            errors.append("entity artifact requires semantics")

    if kind in {"action", "hybrid"}:
        for field in ("root", "phases", "closure"):
            if field not in doc:
                errors.append(f"{kind} artifact requires {field}")

    return errors


def compile_semantic_skeleton(doc: dict) -> dict:
    errors = validate_semantic_skeleton(doc)
    if errors:
        return {"status": "error", "errors": errors}

    artifact = doc["artifact"]
    kind = artifact["kind"]

    result = {
        "status": "ok",
        "package": {
            "version": "semantic_package.v1",
            "source_version": doc["version"],
            "artifact": artifact,
            "name": doc["name"],
            "desc": doc["desc"],
            "trigger": doc["trigger"],
            "refs": dict(doc["refs"]),
        },
    }

    if "semantics" in doc:
        result["package"]["semantics"] = doc["semantics"]

    if kind in {"action", "hybrid"}:
        action_doc = {
            "version": "skeleton.v1",
            "name": doc["name"],
            "desc": doc["desc"],
            "trigger": doc["trigger"],
            "refs": doc["refs"],
            "root": doc["root"],
            "phases": doc["phases"],
            "closure": doc["closure"],
        }
        compiled = compile_skeleton(action_doc)
        if compiled["status"] != "ok":
            return compiled
        result["package"]["stepchain"] = compiled["stepchain"]

    return result


def main() -> int:
    try:
        doc = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "errors": [f"invalid JSON input: {exc}"]}, indent=2))
        return 1

    result = compile_semantic_skeleton(doc)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
