#!/usr/bin/env python3
"""trace_tree_build — derive trace_tree.v1 from step-shaped sources.

This tool is the bridge between runtime/package storage and future replay.
It does not simulate. It derives a canonical unfolding trace from:

  - realized chains
  - compiled stepchains
  - skeletons (via compilation)
  - semantic skeletons (via compilation)

The result is trace_tree.v1: a replay-oriented structure that captures
gap expression, manifestation, topology, and local outcome.
"""
from __future__ import annotations
TOOL_DESC = 'derive trace_tree.v1 from step-shaped sources.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'none'

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import manifest_engine as manifest_engine_module
from step import score_band, vocab_class
from system.skeleton_compile import compile_skeleton
from system.semantic_skeleton_compile import compile_semantic_skeleton


KIND_MAP = {
    "observe": "observe",
    "verify": "verify",
    "mutate": "mutate",
    "reason": "bridge",
    "higher_order": "bridge",
    "await": "await",
    "embed": "embed",
    "clarify": "clarify",
    "terminal": "terminal",
    "gap": "unknown",
}


def _gap_signature(gap: dict) -> str:
    status = "~" if gap.get("status") == "dormant" else "=" if gap.get("status") == "resolved" else "?"
    klass = vocab_class(gap.get("vocab"))
    rel = score_band(gap.get("relevance", 0.0))
    conf = score_band(gap.get("confidence", 0.0))
    gr = score_band(gap.get("grounded", 0.0))
    return f"{{{status}{klass}{rel}{conf}{gr}/{gap.get('step_ref_count', 0)}:{gap.get('content_ref_count', 0)}}}"


def _node_gap_expression(
    *,
    desc: str,
    vocab: str | None,
    status: str,
    step_refs: list[str],
    content_refs: list[str],
    relevance: float | None = None,
    confidence: float | None = None,
    grounded: float | None = None,
    gap_hash: str | None = None,
) -> dict:
    expression = {
        "desc": desc,
        "status": status,
        "step_refs": list(step_refs),
        "content_refs": list(content_refs),
        "step_ref_count": len(step_refs),
        "content_ref_count": len(content_refs),
        "score_bands": {
            "relevance": int(score_band(relevance or 0.0)),
            "confidence": int(score_band(confidence or 0.0)),
            "grounded": int(score_band(grounded or 0.0)),
        },
    }
    if gap_hash:
        expression["hash"] = gap_hash
    if vocab:
        expression["vocab"] = vocab
    expression["signature"] = _gap_signature(
        {
            "status": status,
            "vocab": vocab,
            "relevance": relevance or 0.0,
            "confidence": confidence or 0.0,
            "grounded": grounded or 0.0,
            "step_ref_count": len(step_refs),
            "content_ref_count": len(content_refs),
        }
    )
    return expression


def _stepchain_manifestation(node: dict) -> dict:
    manifestation = node.get("manifestation", {})
    generation = node.get("generation", {})
    out = {
        "kind": KIND_MAP.get(node.get("kind"), "unknown"),
        "spawn_mode": generation.get("spawn_mode", "none"),
        "spawn_trigger": generation.get("spawn_trigger", "none"),
        "post_diff": bool(node.get("post_diff", False)),
        "activation_mode": manifestation.get("execution_mode", "none"),
        "return_policy": generation.get("return_policy", "resume_transition"),
    }
    if manifestation.get("activation_ref"):
        out["activation_ref"] = manifestation["activation_ref"]
    if node.get("emits_commit"):
        out["emitted_commit"] = True
    if manifestation.get("background"):
        out["background"] = True
    return out


def _realized_gap_manifestation(gap: dict) -> dict:
    klass = vocab_class(gap.get("vocab"))
    kind = {
        "o": "observe",
        "m": "mutate",
        "b": "bridge",
        "c": "clarify",
        "_": "unknown",
    }.get(klass, "unknown")
    return {
        "kind": kind,
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "post_diff": False,
        "activation_mode": "runtime_vocab" if gap.get("vocab") else "none",
        "return_policy": "terminal" if gap.get("resolved") else "resume_parent",
    }


def _trace_summary(traces: list[dict]) -> dict:
    max_depth = max((trace["topology"]["depth"] for trace in traces), default=0)
    generation_count = max((trace["topology"]["generation"] for trace in traces), default=-1) + 1
    return {
        "max_depth": max_depth,
        "generation_count": max(0, generation_count),
        "bridge_nodes": sum(1 for trace in traces if trace["manifestation"]["kind"] == "bridge"),
        "mutation_nodes": sum(1 for trace in traces if trace["manifestation"]["kind"] == "mutate"),
        "reentry_points": sum(1 for trace in traces if trace["manifestation"]["post_diff"]),
        "await_nodes": sum(1 for trace in traces if trace["manifestation"]["kind"] == "await"),
        "background_nodes": sum(1 for trace in traces if trace["manifestation"].get("background") is True),
    }


def _trace_tree_from_semantic_tree(semantic_tree: dict, *, source_type: str, source_ref: str | None = None) -> dict:
    nodes = list(semantic_tree.get("nodes", []) or [])
    nodes_by_id = {node.get("id"): node for node in nodes if node.get("id")}
    traces: list[dict] = []
    root_id = semantic_tree.get("root_id")

    if source_type in {"stepchain", "skeleton", "semantic_skeleton"}:
        top_level_trace_ids = [f"trace_{node['id']}" for node in nodes if int(node.get("depth", 0)) == 0]
        for node in nodes:
            node_id = node.get("id")
            transitions = dict(node.get("transitions", {}) or {})
            child_ids = [f"trace_{target}" for target in transitions.values() if target in nodes_by_id]
            gap = dict(node.get("gap", {}) or {})
            topology = {
                "depth": int(node.get("depth", 0)),
                "generation": int(node.get("depth", 0)),
                "child_ids": child_ids,
                "sibling_index": top_level_trace_ids.index(f"trace_{node_id}") if int(node.get("depth", 0)) == 0 and f"trace_{node_id}" in top_level_trace_ids else 0,
                "sibling_count": len(top_level_trace_ids) if int(node.get("depth", 0)) == 0 else 1,
                "sibling_policy": "after_descendants",
                "blocked_siblings": [],
            }
            if int(node.get("depth", 0)) == 0 and f"trace_{node_id}" in top_level_trace_ids:
                idx = top_level_trace_ids.index(f"trace_{node_id}")
                topology["blocked_siblings"] = top_level_trace_ids[idx + 1:]
            if node.get("parent_id"):
                topology["parent_id"] = f"trace_{node['parent_id']}"
            trace = {
                "id": f"trace_{node_id}",
                "source_phase": node_id,
                "gap": _node_gap_expression(
                    desc=gap.get("desc", node.get("goal", "")),
                    vocab=gap.get("runtime_vocab"),
                    status="resolved" if not child_ids else "active",
                    step_refs=list(gap.get("step_refs", []) or []),
                    content_refs=list(gap.get("content_refs", []) or []),
                    relevance=gap.get("relevance", 0.0),
                    confidence=gap.get("confidence", 0.0),
                    grounded=gap.get("grounded", 0.0),
                ),
                "manifestation": _stepchain_manifestation(
                    {
                        "kind": node.get("kind"),
                        "manifestation": node.get("manifestation", {}) or {},
                        "generation": node.get("generation", {}) or {},
                        "post_diff": gap.get("post_diff", False),
                    }
                ),
                "topology": topology,
                "outcome": {
                    "terminal_state": "resolved" if not child_ids else "active",
                    "closure_reason": "compiled transition node" if not child_ids else "transitions remain open",
                },
            }
            if child_ids:
                trace["outcome"]["return_target"] = child_ids[0]
            traces.append(trace)
    else:
        previous_trace_id: str | None = None
        generation = 0
        for node in nodes:
            step_id = node.get("id")
            gaps = list(node.get("gaps", []) or ([] if not node.get("gap") else [node.get("gap")]))
            sibling_ids = [f"trace_{gap.get('hash', f'{step_id}_gap_{idx}')}" for idx, gap in enumerate(gaps)]
            for gap_idx, gap in enumerate(gaps):
                gap_hash = gap.get("hash", f"{step_id}_gap_{gap_idx}")
                trace_id = f"trace_{gap_hash}"
                topology = {
                    "depth": 0 if previous_trace_id is None else 1,
                    "generation": generation,
                    "child_ids": [],
                    "sibling_index": gap_idx,
                    "sibling_count": max(1, len(sibling_ids)),
                    "sibling_policy": "after_descendants",
                    "blocked_siblings": sibling_ids[gap_idx + 1:],
                }
                if previous_trace_id:
                    topology["parent_id"] = previous_trace_id
                traces.append(
                    {
                        "id": trace_id,
                        "source_step": step_id,
                        "gap": _node_gap_expression(
                            desc=gap.get("desc", ""),
                            vocab=gap.get("runtime_vocab"),
                            status=gap.get("status", "active"),
                            step_refs=list(gap.get("step_refs", []) or []),
                            content_refs=list(gap.get("content_refs", []) or []),
                            relevance=gap.get("relevance", 0.0),
                            confidence=gap.get("confidence", 0.0),
                            grounded=gap.get("grounded", 0.0),
                            gap_hash=gap_hash,
                        ),
                        "manifestation": _realized_gap_manifestation(
                            {
                                "vocab": gap.get("runtime_vocab"),
                                "resolved": gap.get("status") == "resolved",
                                "dormant": gap.get("status") == "dormant",
                            }
                        ),
                        "topology": topology,
                        "outcome": {
                            "terminal_state": gap.get("status", "active"),
                            "closure_reason": "recorded runtime gap state",
                        },
                    }
                )
                previous_trace_id = trace_id
                generation += 1

    root_trace = (
        f"trace_{root_id}"
        if source_type in {"stepchain", "skeleton", "semantic_skeleton"} and root_id
        else (traces[0]["id"] if traces else "")
    )
    return {
        "version": "trace_tree.v1",
        "source_type": source_type,
        "source_ref": source_ref or semantic_tree.get("source_ref") or root_trace,
        "root_trace": root_trace,
        "traces": traces,
        "summary": _trace_summary(traces),
    }


def build_from_stepchain(stepchain: dict, *, source_type: str = "stepchain", source_ref: str | None = None) -> dict:
    semantic_tree = manifest_engine_module.build_semantic_tree(
        stepchain,
        source_type=source_type,
        source_ref=source_ref or stepchain.get("name"),
    )
    return _trace_tree_from_semantic_tree(semantic_tree, source_type=source_type, source_ref=source_ref)


def build_from_realized_chain(chain_doc: dict, *, source_ref: str | None = None) -> dict:
    semantic_tree = manifest_engine_module.build_semantic_tree(
        chain_doc,
        source_type="realized_chain",
        source_ref=source_ref or chain_doc.get("hash"),
    )
    return _trace_tree_from_semantic_tree(semantic_tree, source_type="realized_chain", source_ref=source_ref)


def build_trace_tree(doc: dict) -> dict:
    artifact_type = doc.get("artifact_type")
    candidate = doc.get("candidate", {})
    source_ref = doc.get("source_ref")

    if artifact_type == "stepchain":
        return {"status": "ok", "trace_tree": build_from_stepchain(candidate, source_ref=source_ref)}
    if artifact_type == "skeleton":
        compiled = compile_skeleton(candidate)
        if compiled.get("status") != "ok":
            return {"status": "error", "errors": compiled.get("errors", ["skeleton compile failed"])}
        return {
            "status": "ok",
            "trace_tree": build_from_stepchain(
                compiled["stepchain"],
                source_type="skeleton",
                source_ref=source_ref or candidate.get("name"),
            ),
        }
    if artifact_type == "semantic_skeleton":
        compiled = compile_semantic_skeleton(candidate)
        if compiled.get("status") != "ok":
            return {"status": "error", "errors": compiled.get("errors", ["semantic skeleton compile failed"])}
        package = compiled["package"]
        if "stepchain" not in package:
            return {"status": "error", "errors": ["semantic skeleton does not contain action structure to trace"]}
        return {
            "status": "ok",
            "trace_tree": build_from_stepchain(
                package["stepchain"],
                source_type="semantic_skeleton",
                source_ref=source_ref or candidate.get("name"),
            ),
        }
    if artifact_type == "realized_chain":
        return {
            "status": "ok",
            "trace_tree": build_from_realized_chain(candidate, source_ref=source_ref),
        }
    return {"status": "error", "errors": [f"artifact_type not supported: {artifact_type}"]}


def main() -> int:
    try:
        doc = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "errors": [f"invalid JSON input: {exc}"]}, indent=2))
        return 1

    result = build_trace_tree(doc)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
