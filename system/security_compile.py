#!/usr/bin/env python3
"""security_compile — unified structural security compiler for step-shaped artifacts.

Current implementation supports:
  - atomic_step
  - gap
  - st_package
  - skeleton
  - semantic_skeleton
  - stepchain
  - realized_chain

The tool normalizes candidate structure into a shared graph, runs basic law and
security checks, projects recursive execution shape, recursively composes
embedded package profiles where possible, and emits a security_compile.v1
result.
"""
from __future__ import annotations
TOOL_DESC = 'unified structural security compiler for step-shaped artifacts.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'none'

import json
import sys
import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compile import OBSERVE_VOCAB, MUTATE_VOCAB, BRIDGE_VOCAB
from skills.loader import load_skill, load_all
from system.skeleton_compile import compile_skeleton
from system.semantic_skeleton_compile import compile_semantic_skeleton


RUNTIME_VOCAB = set(OBSERVE_VOCAB) | set(MUTATE_VOCAB) | set(BRIDGE_VOCAB)
OBSERVE_WORDS = {"read", "scan", "check", "inspect", "verify", "view", "observe", "resolve", "look"}
MUTATE_WORDS = {"edit", "update", "change", "modify", "fix", "patch", "write", "create", "delete", "remove"}
PROTECTED_PREFIXES = [
    "skills/codons/",
    "step.py",
    "compile.py",
    "loop.py",
    "skills/loader.py",
    "trajectory.json",
    "chains.json",
]
CHAINS_DIR = ROOT / "trajectory_store" / "command"
_REGISTRY = None


@dataclass
class SecurityNode:
    id: str
    kind: str
    desc: str
    vocab: str | None = None
    post_diff: bool = False
    relevance: float | None = None
    confidence: float | None = None
    grounded: float | None = None
    content_refs: list[str] = field(default_factory=list)
    step_refs: list[str] = field(default_factory=list)
    manifestation: dict = field(default_factory=dict)
    generation: dict = field(default_factory=dict)
    transitions: dict = field(default_factory=dict)
    terminal: bool = False
    requires_postcondition: bool = False


@dataclass
class SecurityGraph:
    artifact_type: str
    artifact_kind: str
    nodes: list[SecurityNode]
    root_ids: list[str]
    protected_surface_targets: list[str]
    raw: dict


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            _REGISTRY = load_all(str(ROOT / "skills"))
    return _REGISTRY


def finding(domain: str, code: str, severity: str, message: str, *, path: str | None = None,
            refs: list[str] | None = None) -> dict:
    item = {
        "domain": domain,
        "code": code,
        "severity": severity,
        "message": message,
    }
    if path:
        item["path"] = path
    if refs:
        item["refs"] = refs
    return item


def build_error_result(inp: dict, message: str, code: str = "normalization_failed") -> dict:
    return {
        "version": "security_compile.v1",
        "input": inp,
        "result": {
            "status": "rejected",
            "artifact_type": inp.get("artifact_type", "gap"),
            "checks": [
                {"domain": "structural_law", "verdict": "fail", "notes": [message]},
            ],
            "violations": [
                finding("structural_law", code, "critical", message),
            ],
            "risks": [],
            "projection": {
                "spawn_depth": 0,
                "branch_points": 0,
                "bridge_count": 0,
                "mutation_count": 0,
                "post_diff_reentry_points": 0,
                "background_reintegration_required": False,
                "await_required": False,
                "commit_consumption_required": False,
                "protected_surface_touches": [],
            },
            "summary": message,
        },
    }


def normalize_gap(candidate: dict) -> SecurityGraph:
    scores = candidate.get("scores", {})
    node = SecurityNode(
        id=candidate.get("hash", "gap"),
        kind="gap",
        desc=candidate.get("desc", ""),
        vocab=candidate.get("vocab"),
        post_diff=False,
        relevance=scores.get("relevance"),
        confidence=scores.get("confidence"),
        grounded=scores.get("grounded"),
        content_refs=list(candidate.get("content_refs", []) or []),
        step_refs=list(candidate.get("step_refs", []) or []),
    )
    return SecurityGraph(
        artifact_type="gap",
        artifact_kind="unknown",
        nodes=[node],
        root_ids=[node.id],
        protected_surface_targets=[],
        raw=candidate,
    )


def normalize_atomic_step(candidate: dict) -> SecurityGraph:
    step_hash = candidate.get("hash", "step")
    step_kind = "mutate" if candidate.get("commit") else "observe"
    step_node = SecurityNode(
        id=step_hash,
        kind=step_kind,
        desc=candidate.get("desc", ""),
        vocab="hash_edit_needed" if candidate.get("commit") else "hash_resolve_needed",
        post_diff=bool(candidate.get("gaps")),
        content_refs=list(candidate.get("content_refs", []) or []),
        step_refs=list(candidate.get("step_refs", []) or []),
    )
    nodes = [step_node]
    transitions = {}
    for idx, gap in enumerate(candidate.get("gaps", []) or []):
        gap_id = gap.get("hash", f"{step_hash}_gap_{idx}")
        scores = gap.get("scores", {})
        node = SecurityNode(
            id=gap_id,
            kind="gap",
            desc=gap.get("desc", ""),
            vocab=gap.get("vocab"),
            post_diff=False,
            relevance=scores.get("relevance"),
            confidence=scores.get("confidence"),
            grounded=scores.get("grounded"),
            content_refs=list(gap.get("content_refs", []) or []),
            step_refs=list(gap.get("step_refs", []) or []),
        )
        nodes.append(node)
        transitions[f"gap_{idx}"] = gap_id
    step_node.transitions = transitions
    return SecurityGraph(
        artifact_type="atomic_step",
        artifact_kind="action" if candidate.get("commit") else "unknown",
        nodes=nodes,
        root_ids=[step_hash],
        protected_surface_targets=[],
        raw=candidate,
    )


def _node_kind_from_vocab(vocab: str | None) -> str:
    if vocab in OBSERVE_VOCAB:
        return "observe"
    if vocab in MUTATE_VOCAB:
        return "mutate"
    if vocab in BRIDGE_VOCAB:
        return "bridge"
    return "unknown"


def normalize_st_package(candidate: dict, *, candidate_path: str | None = None) -> SecurityGraph:
    if candidate_path:
        skill = load_skill(candidate_path)
        if skill is None:
            raise ValueError(f"failed to load skill package at {candidate_path}")
        protected = [candidate_path] if any(candidate_path.startswith(prefix) for prefix in PROTECTED_PREFIXES) else []
        nodes = [
            SecurityNode(
                id=f"step_{idx}",
                kind=step.kind or _node_kind_from_vocab(step.vocab),
                desc=step.desc,
                vocab=step.vocab,
                post_diff=step.post_diff,
                relevance=step.relevance,
                content_refs=list(step.resolve) + list(step.content_refs),
                step_refs=list(step.step_refs),
                manifestation=dict(step.manifestation),
                generation=dict(step.generation),
                transitions=dict(step.transitions),
                terminal=step.terminal,
                requires_postcondition=step.requires_postcondition,
            )
            for idx, step in enumerate(skill.steps)
        ]
        return SecurityGraph(
            artifact_type="st_package",
            artifact_kind=skill.artifact_kind,
            nodes=nodes,
            root_ids=[nodes[0].id] if nodes else [],
            protected_surface_targets=protected,
            raw=skill.payload,
        )

    artifact_kind = candidate.get("artifact_kind", "unknown")
    protected = []
    nodes = []
    for idx, step in enumerate(candidate.get("steps", [])):
        nodes.append(SecurityNode(
            id=f"step_{idx}",
            kind=step.get("kind") or _node_kind_from_vocab(step.get("vocab")),
            desc=step.get("desc", ""),
            vocab=step.get("vocab"),
            post_diff=step.get("post_diff", True),
            relevance=step.get("relevance"),
            content_refs=list(step.get("resolve", []) or []) + list(step.get("content_refs", []) or []),
            step_refs=list(step.get("step_refs", []) or []),
            manifestation=dict(step.get("manifestation", {}) or {}),
            generation=dict(step.get("generation", {}) or {}),
            transitions=dict(step.get("transitions", {}) or {}),
            terminal=bool(step.get("terminal", False)),
            requires_postcondition=bool(step.get("requires_postcondition", False)),
        ))
    return SecurityGraph(
        artifact_type="st_package",
        artifact_kind=artifact_kind,
        nodes=nodes,
        root_ids=[nodes[0].id] if nodes else [],
        protected_surface_targets=protected,
        raw=candidate,
    )


def normalize_stepchain(candidate: dict) -> SecurityGraph:
    nodes = []
    for node in candidate.get("nodes", []):
        gap_template = node.get("gap_template", {})
        manifestation = dict(node.get("manifestation", {}) or {})
        runtime_vocab = manifestation.get("runtime_vocab")
        if runtime_vocab is None:
            allowed = node.get("allowed_vocab", [])
            runtime_vocab = allowed[0] if allowed else None
        content_refs = list(gap_template.get("content_refs", []) or [])
        activation_ref = manifestation.get("activation_ref")
        if activation_ref:
            content_refs.append(activation_ref)
        nodes.append(SecurityNode(
            id=node["id"],
            kind=node.get("kind", "unknown"),
            desc=gap_template.get("desc", node.get("goal", "")),
            vocab=runtime_vocab,
            post_diff=node.get("post_diff", False),
            relevance=node.get("relevance"),
            content_refs=content_refs,
            step_refs=list(gap_template.get("step_refs", []) or []),
            manifestation=manifestation,
            generation=dict(node.get("generation", {}) or {}),
            transitions=dict(node.get("transitions", {}) or {}),
            terminal=bool(node.get("terminal", False)),
            requires_postcondition=bool(node.get("requires_postcondition", False)),
        ))
    artifact_kind = candidate.get("artifact", {}).get("kind", "action") if isinstance(candidate.get("artifact"), dict) else "action"
    return SecurityGraph(
        artifact_type="stepchain",
        artifact_kind=artifact_kind,
        nodes=nodes,
        root_ids=[candidate.get("root")] if candidate.get("root") else ([nodes[0].id] if nodes else []),
        protected_surface_targets=[],
        raw=candidate,
    )


def normalize_realized_chain(candidate: dict) -> SecurityGraph:
    steps = candidate.get("steps", []) or candidate.get("resolved_steps", []) or []
    nodes: list[SecurityNode] = []
    previous_step_id = None
    for idx, step in enumerate(steps):
        step_id = step.get("hash", f"step_{idx}")
        step_kind = "mutate" if step.get("commit") else "observe"
        step_node = SecurityNode(
            id=step_id,
            kind=step_kind,
            desc=step.get("desc", ""),
            vocab="hash_edit_needed" if step.get("commit") else "hash_resolve_needed",
            post_diff=bool(step.get("gaps")),
            content_refs=list(step.get("content_refs", []) or []),
            step_refs=list(step.get("step_refs", []) or []),
        )
        transitions = {}
        if previous_step_id is not None:
            prev = next(node for node in nodes if node.id == previous_step_id)
            prev.transitions["on_done"] = step_id
        for gap_idx, gap in enumerate(step.get("gaps", []) or []):
            gap_id = gap.get("hash", f"{step_id}_gap_{gap_idx}")
            scores = gap.get("scores", {})
            gap_node = SecurityNode(
                id=gap_id,
                kind="gap",
                desc=gap.get("desc", ""),
                vocab=gap.get("vocab"),
                post_diff=False,
                relevance=scores.get("relevance"),
                confidence=scores.get("confidence"),
                grounded=scores.get("grounded"),
                content_refs=list(gap.get("content_refs", []) or []),
                step_refs=list(gap.get("step_refs", []) or []),
            )
            nodes.append(gap_node)
            transitions[f"gap_{gap_idx}"] = gap_id
        step_node.transitions = transitions
        nodes.append(step_node)
        previous_step_id = step_id
    return SecurityGraph(
        artifact_type="realized_chain",
        artifact_kind="action",
        nodes=nodes,
        root_ids=[steps[0].get("hash", "step_0")] if steps else [],
        protected_surface_targets=[],
        raw=candidate,
    )


def normalize_input(inp: dict) -> SecurityGraph:
    artifact_type = inp["artifact_type"]
    candidate = inp.get("candidate", {})
    candidate_path = inp.get("candidate_path")

    if artifact_type == "atomic_step":
        return normalize_atomic_step(candidate)
    if artifact_type == "gap":
        return normalize_gap(candidate)
    if artifact_type == "st_package":
        return normalize_st_package(candidate, candidate_path=candidate_path)
    if artifact_type == "stepchain":
        return normalize_stepchain(candidate)
    if artifact_type == "skeleton":
        compiled = compile_skeleton(candidate)
        if compiled.get("status") != "ok":
            raise ValueError("; ".join(compiled.get("errors", ["skeleton compile failed"])))
        return normalize_stepchain(compiled["stepchain"])
    if artifact_type == "semantic_skeleton":
        compiled = compile_semantic_skeleton(candidate)
        if compiled.get("status") != "ok":
            raise ValueError("; ".join(compiled.get("errors", ["semantic skeleton compile failed"])))
        package = compiled["package"]
        if "stepchain" in package:
            graph = normalize_stepchain(package["stepchain"])
            graph.artifact_kind = package.get("artifact", {}).get("kind", graph.artifact_kind)
            graph.raw = package
            return graph
        return normalize_st_package(package)
    if artifact_type == "realized_chain":
        return normalize_realized_chain(candidate)
    raise ValueError(f"artifact_type not yet supported: {artifact_type}")


def semantic_desc_vocab_mismatch(desc: str, vocab: str | None) -> bool:
    if not vocab or not desc:
        return False
    words = {w.strip(".,:;!?").lower() for w in desc.split()}
    observeish = bool(words & OBSERVE_WORDS)
    mutateish = bool(words & MUTATE_WORDS)
    if vocab in OBSERVE_VOCAB and mutateish and not observeish:
        return True
    if vocab in MUTATE_VOCAB and observeish and not mutateish:
        return True
    return False


def check_structural_law(graph: SecurityGraph) -> tuple[dict, list[dict], list[dict]]:
    notes: list[str] = []
    violations: list[dict] = []
    risks: list[dict] = []
    node_ids = {node.id for node in graph.nodes}
    seen_mutation = False

    for node in graph.nodes:
        if not node.desc.strip():
            violations.append(finding("structural_law", "empty_desc", "high", "Node description must not be empty.", path=node.id))
        if node.vocab is not None and node.vocab not in RUNTIME_VOCAB:
            violations.append(finding("structural_law", "invalid_runtime_vocab", "critical", f"Invalid runtime vocab '{node.vocab}'.", path=node.id))
        spawn_trigger = node.generation.get("spawn_trigger")
        if spawn_trigger in {"on_post_diff", "conditional"} and not node.post_diff:
            violations.append(finding("structural_law", "illegal_post_diff_spawn", "critical", "Node declares offspring generation but post_diff is false.", path=node.id))
        for target in node.transitions.values():
            if target not in node_ids:
                violations.append(finding("structural_law", "broken_transition_target", "critical", f"Transition points to missing target '{target}'.", path=node.id))
        if node.kind == "mutate" or node.vocab in MUTATE_VOCAB:
            if seen_mutation:
                violations.append(finding("structural_law", "illegal_mutation_sequence", "critical", "Consecutive mutate nodes detected without intervening observation.", path=node.id))
            seen_mutation = True
        elif node.vocab in OBSERVE_VOCAB or node.kind in {"observe", "verify"}:
            seen_mutation = False
        if semantic_desc_vocab_mismatch(node.desc, node.vocab):
            risks.append(finding("structural_law", "semantic_desc_vocab_mismatch", "medium", "Description language and runtime vocab pull in different directions.", path=node.id))
        if node.requires_postcondition and not node.post_diff:
            violations.append(finding("structural_law", "missing_post_diff_for_postcondition", "high", "Node requires postcondition but post_diff is false.", path=node.id))

    verdict = "fail" if violations else ("warn" if risks else "pass")
    if not graph.nodes:
        notes.append("No executable nodes present in normalized graph.")
    return {"domain": "structural_law", "verdict": verdict, "notes": notes}, violations, risks


def check_manifestation_law(graph: SecurityGraph, context: dict) -> tuple[dict, list[dict], list[dict]]:
    notes: list[str] = []
    violations: list[dict] = []
    risks: list[dict] = []

    if graph.artifact_kind == "entity":
        if any(node.vocab in MUTATE_VOCAB or node.kind == "mutate" for node in graph.nodes):
            risks.append(finding("manifestation_law", "entity_action_misclassification", "high", "Entity-like package carries mutate behavior.", path=graph.nodes[0].id if graph.nodes else None))

    if graph.artifact_kind in {"action", "hybrid"} and context.get("mode") == "pre_persist":
        if context.get("source") == "manual" and not context.get("existing_action_ref"):
            risks.append(finding("manifestation_law", "untracked_action_persist", "medium", "Executable package is being persisted without explicit existing_action_ref context."))

    if graph.artifact_type == "st_package" and graph.raw.get("artifact_kind") in {"action", "hybrid"} and not context.get("existing_action_ref"):
        risks.append(finding("manifestation_law", "semantic_update_originates_action", "high", "Action or hybrid package should usually originate through skeleton compilation, not semantic persistence."))

    verdict = "fail" if violations else ("warn" if risks else "pass")
    return {"domain": "manifestation_law", "verdict": verdict, "notes": notes}, violations, risks


def check_protected_surfaces(graph: SecurityGraph, context: dict) -> tuple[dict, list[dict], list[dict]]:
    notes: list[str] = []
    violations: list[dict] = []
    risks: list[dict] = []
    mode = context.get("mode")

    for target in graph.protected_surface_targets:
        if target.startswith("skills/codons/") and mode == "pre_persist":
            violations.append(finding("protected_surfaces", "codon_mutation_attempt", "critical", "Codon package is on a protected surface and must not be mutated.", path=target))
        elif mode == "pre_persist":
            risks.append(finding("protected_surfaces", "protected_surface_touch", "high", "Candidate touches a protected OS surface.", path=target))

    for node in graph.nodes:
        for ref in node.content_refs:
            if isinstance(ref, str) and any(prefix in ref for prefix in ("skills/codons/", "step.py", "compile.py", "loop.py")):
                risks.append(finding("protected_surfaces", "indirect_protected_activation", "high", "Node references a protected OS surface.", path=node.id, refs=[ref]))

    verdict = "fail" if violations else ("warn" if risks else "pass")
    return {"domain": "protected_surfaces", "verdict": verdict, "notes": notes}, violations, risks


def _successors(node: SecurityNode) -> list[str]:
    return list(node.transitions.values())


def project_execution(graph: SecurityGraph) -> dict:
    nodes_by_id = {node.id: node for node in graph.nodes}

    def dfs(node_id: str, depth: int, seen: set[str]) -> int:
        if node_id not in nodes_by_id or node_id in seen:
            return depth
        node = nodes_by_id[node_id]
        succs = _successors(node)
        if not succs:
            return depth
        new_seen = set(seen)
        new_seen.add(node_id)
        return max(dfs(child, depth + 1, new_seen) for child in succs)

    root_ids = [rid for rid in graph.root_ids if rid in nodes_by_id]
    spawn_depth = max((dfs(rid, 1, set()) for rid in root_ids), default=(1 if graph.nodes else 0))
    branch_points = sum(1 for node in graph.nodes if len(_successors(node)) > 1 or node.generation.get("spawn_mode") not in {None, "none"})
    bridge_count = sum(1 for node in graph.nodes if node.vocab in BRIDGE_VOCAB or node.kind in {"reason", "higher_order", "await"})
    mutation_count = sum(1 for node in graph.nodes if node.vocab in MUTATE_VOCAB or node.kind == "mutate")
    post_diff_reentry_points = sum(1 for node in graph.nodes if node.post_diff)
    await_required = any(
        node.vocab == "await_needed" or node.manifestation.get("await_policy") in {"manual", "heartbeat"}
        for node in graph.nodes
    )
    commit_consumption_required = any(
        node.requires_postcondition or node.manifestation.get("emits_commit") or node.kind == "mutate"
        for node in graph.nodes
    )
    background_reintegration_required = any(
        node.manifestation.get("background") or node.manifestation.get("await_policy") == "heartbeat"
        for node in graph.nodes
    )
    return {
        "spawn_depth": spawn_depth,
        "branch_points": branch_points,
        "bridge_count": bridge_count,
        "mutation_count": mutation_count,
        "post_diff_reentry_points": post_diff_reentry_points,
        "background_reintegration_required": background_reintegration_required,
        "await_required": await_required,
        "commit_consumption_required": commit_consumption_required,
        "protected_surface_touches": list(graph.protected_surface_targets),
    }


def load_embedded_graph(ref: str) -> SecurityGraph | None:
    reg = registry()
    skill = reg.resolve(ref)
    if skill:
        return normalize_st_package({}, candidate_path=skill.source)

    path = CHAINS_DIR / f"{ref}.json"
    if path.exists():
        try:
            package = json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
        if package.get("version") == "stepchain.v1":
            return normalize_stepchain(package)
    return None


def score_execution_hazard(graph: SecurityGraph, projection: dict) -> float:
    mutate_weight = min(1.0, 0.3 * projection["mutation_count"])
    protected_weight = 0.5 if projection["protected_surface_touches"] else 0.0
    mismatch_weight = 0.15 * sum(1 for node in graph.nodes if semantic_desc_vocab_mismatch(node.desc, node.vocab))
    bridge_weight = min(0.2, 0.05 * projection["bridge_count"])
    return min(1.0, mutate_weight + protected_weight + mismatch_weight + bridge_weight)


def score_structural_integrity(graph: SecurityGraph, projection: dict, structural_violations: list[dict]) -> float:
    penalty = 0.0
    penalty += 0.3 * len(structural_violations)
    penalty += 0.1 * sum(1 for node in graph.nodes if not node.desc.strip())
    penalty += 0.1 * sum(1 for node in graph.nodes if node.post_diff and node.vocab in OBSERVE_VOCAB)
    return max(0.0, 1.0 - min(1.0, penalty))


def score_recursion_pressure(graph: SecurityGraph, projection: dict) -> float:
    score = 0.0
    score += min(0.4, 0.08 * projection["bridge_count"])
    score += min(0.3, 0.06 * projection["post_diff_reentry_points"])
    score += min(0.3, 0.08 * max(0, projection["spawn_depth"] - 1))
    return min(1.0, score)


def score_semantic_drift(graph: SecurityGraph) -> float:
    drift = 0.0
    drift += 0.2 * sum(1 for node in graph.nodes if semantic_desc_vocab_mismatch(node.desc, node.vocab))
    drift += 0.1 * sum(1 for node in graph.nodes if node.vocab is None and node.kind == "unknown")
    return min(1.0, drift)


def score_protected_surface_risk(graph: SecurityGraph, projection: dict) -> float:
    risk = 0.0
    if projection["protected_surface_touches"]:
        risk += 0.7
    risk += 0.15 * sum(
        1 for node in graph.nodes for ref in node.content_refs
        if isinstance(ref, str) and any(prefix in ref for prefix in ("skills/codons/", "step.py", "compile.py", "loop.py"))
    )
    return min(1.0, risk)


def compose_embedded_profiles(
    graph: SecurityGraph,
    *,
    depth: int = 0,
    max_depth: int = 3,
    visited_refs: set[str] | None = None,
) -> tuple[list[dict], list[dict], dict]:
    if visited_refs is None:
        visited_refs = set()
    if depth >= max_depth:
        return [], [], {
            "spawn_depth": 0,
            "branch_points": 0,
            "bridge_count": 0,
            "mutation_count": 0,
            "post_diff_reentry_points": 0,
            "background_reintegration_required": False,
            "await_required": False,
            "commit_consumption_required": False,
            "protected_surface_touches": [],
        }

    violations: list[dict] = []
    risks: list[dict] = []
    aggregate = {
        "spawn_depth": 0,
        "branch_points": 0,
        "bridge_count": 0,
        "mutation_count": 0,
        "post_diff_reentry_points": 0,
        "background_reintegration_required": False,
        "await_required": False,
        "commit_consumption_required": False,
        "protected_surface_touches": [],
    }

    refs = {
        ref
        for node in graph.nodes
        for ref in node.content_refs
        if isinstance(ref, str) and ref and not ref.startswith("$") and ref not in visited_refs
    }
    for ref in sorted(refs):
        child = load_embedded_graph(ref)
        if child is None:
            continue
        child_result = analyze_graph(child, {"mode": "pre_activation", "source": "registry"}, depth=depth + 1, visited_refs=visited_refs | {ref})
        if child_result["result"]["status"] == "rejected":
            violations.append(
                finding(
                    "recursive_execution_risk",
                    "embedded_artifact_rejected",
                    "critical",
                    "Embedded package fails security compilation.",
                    refs=[ref],
                )
            )
        else:
            risks.append(
                finding(
                    "recursive_execution_risk",
                    "activation_cascade",
                    "medium",
                    "Artifact activates an embedded package and inherits its execution profile.",
                    refs=[ref],
                )
            )
            if child_result["result"]["risks"]:
                risks.append(
                    finding(
                        "recursive_execution_risk",
                        "embedded_artifact_warns",
                        "medium",
                        "Embedded package carries security warnings.",
                        refs=[ref],
                    )
                )

        child_proj = child_result["result"]["projection"]
        aggregate["spawn_depth"] = max(aggregate["spawn_depth"], child_proj["spawn_depth"])
        aggregate["branch_points"] += child_proj["branch_points"]
        aggregate["bridge_count"] += child_proj["bridge_count"]
        aggregate["mutation_count"] += child_proj["mutation_count"]
        aggregate["post_diff_reentry_points"] += child_proj["post_diff_reentry_points"]
        aggregate["background_reintegration_required"] = (
            aggregate["background_reintegration_required"] or child_proj["background_reintegration_required"]
        )
        aggregate["await_required"] = aggregate["await_required"] or child_proj["await_required"]
        aggregate["commit_consumption_required"] = (
            aggregate["commit_consumption_required"] or child_proj["commit_consumption_required"]
        )
        aggregate["protected_surface_touches"].extend(child_proj["protected_surface_touches"])

    aggregate["protected_surface_touches"] = sorted(set(aggregate["protected_surface_touches"]))
    return violations, risks, aggregate


def check_recursive_execution_risk(graph: SecurityGraph, projection: dict) -> tuple[dict, list[dict]]:
    risks: list[dict] = []
    pressure = score_recursion_pressure(graph, projection)
    if graph.artifact_type == "stepchain" and projection["bridge_count"] > 0 and projection["branch_points"] > 0:
        risks.append(finding("recursive_execution_risk", "recursive_bridge_fanout", "high", "Bridge structure can recursively fan out through branching execution patterns."))
    if projection["post_diff_reentry_points"] >= 4:
        risks.append(finding("recursive_execution_risk", "unbounded_post_diff_reentry", "medium", "Many post_diff re-entry points may create recursive pressure."))
    verdict = "warn" if risks or pressure >= 0.5 else "pass"
    notes = [f"recursion_pressure={pressure:.2f}"]
    return {"domain": "recursive_execution_risk", "verdict": verdict, "notes": notes}, risks


def check_semantic_integrity(graph: SecurityGraph) -> tuple[dict, list[dict]]:
    risks: list[dict] = []
    drift = score_semantic_drift(graph)
    for node in graph.nodes:
        if semantic_desc_vocab_mismatch(node.desc, node.vocab):
            risks.append(finding("semantic_integrity", "semantic_desc_vocab_mismatch", "medium", "Description and manifestation mode are semantically misaligned.", path=node.id))
        if ("continue" in node.desc.lower() or "verify" in node.desc.lower()) and not node.step_refs:
            risks.append(finding("semantic_integrity", "orphaned_causal_gap", "medium", "Node implies prior causal context but has no step refs.", path=node.id))
    verdict = "warn" if risks or drift >= 0.4 else "pass"
    return {"domain": "semantic_integrity", "verdict": verdict, "notes": [f"semantic_drift={drift:.2f}"]}, risks


def run_checks(graph: SecurityGraph, context: dict) -> tuple[list[dict], list[dict], list[dict]]:
    checks: list[dict] = []
    violations: list[dict] = []
    risks: list[dict] = []

    check, v, r = check_structural_law(graph)
    checks.append(check)
    violations.extend(v)
    risks.extend(r)

    check, v, r = check_manifestation_law(graph, context)
    checks.append(check)
    violations.extend(v)
    risks.extend(r)

    check, v, r = check_protected_surfaces(graph, context)
    checks.append(check)
    violations.extend(v)
    risks.extend(r)

    projection = project_execution(graph)

    check, r = check_recursive_execution_risk(graph, projection)
    checks.append(check)
    risks.extend(r)

    check, r = check_semantic_integrity(graph)
    checks.append(check)
    risks.extend(r)

    return checks, violations, risks


def decide_status(violations: list[dict], risks: list[dict], projection: dict, graph: SecurityGraph) -> str:
    if violations:
        return "rejected"
    protected_surface_risk = score_protected_surface_risk(graph, projection)
    execution_hazard = score_execution_hazard(graph, projection)
    structural_integrity = score_structural_integrity(graph, projection, [])
    if protected_surface_risk >= 0.8 or execution_hazard >= 0.85 or structural_integrity <= 0.35:
        return "rejected"
    if risks:
        return "accepted_with_warnings"
    return "accepted"


def build_result(inp: dict, graph: SecurityGraph, checks: list[dict], violations: list[dict], risks: list[dict], projection: dict) -> dict:
    execution_hazard = score_execution_hazard(graph, projection)
    structural_integrity = score_structural_integrity(graph, projection, violations)
    recursion_pressure = score_recursion_pressure(graph, projection)
    semantic_drift = score_semantic_drift(graph)
    protected_surface_risk = score_protected_surface_risk(graph, projection)

    normalized = {
        "artifact_kind": graph.artifact_kind,
        "root_kind": graph.nodes[0].kind if graph.nodes else "unknown",
        "node_count": len(graph.nodes),
        "edge_count": sum(len(node.transitions) for node in graph.nodes),
        "hash_refs": sorted({
            ref for node in graph.nodes for ref in node.content_refs + node.step_refs
            if isinstance(ref, str) and ref
        }),
        "protected_surface_targets": list(graph.protected_surface_targets),
    }

    status = decide_status(violations, risks, projection, graph)
    summary = (
        f"{status}; execution_hazard={execution_hazard:.2f}, "
        f"structural_integrity={structural_integrity:.2f}, "
        f"recursion_pressure={recursion_pressure:.2f}, "
        f"semantic_drift={semantic_drift:.2f}, "
        f"protected_surface_risk={protected_surface_risk:.2f}"
    )

    return {
        "version": "security_compile.v1",
        "input": inp,
        "result": {
            "status": status,
            "artifact_type": graph.artifact_type,
            "normalized": normalized,
            "checks": checks,
            "violations": violations,
            "risks": risks,
            "projection": projection,
            "summary": summary,
        },
    }


def analyze_graph(graph: SecurityGraph, context: dict, *, depth: int = 0, visited_refs: set[str] | None = None) -> dict:
    checks, violations, risks = run_checks(graph, context)
    projection = project_execution(graph)
    child_violations, child_risks, child_projection = compose_embedded_profiles(
        graph,
        depth=depth,
        visited_refs=visited_refs,
    )
    violations.extend(child_violations)
    risks.extend(child_risks)
    projection["spawn_depth"] = max(projection["spawn_depth"], projection["spawn_depth"] + child_projection["spawn_depth"])
    projection["branch_points"] += child_projection["branch_points"]
    projection["bridge_count"] += child_projection["bridge_count"]
    projection["mutation_count"] += child_projection["mutation_count"]
    projection["post_diff_reentry_points"] += child_projection["post_diff_reentry_points"]
    projection["background_reintegration_required"] = (
        projection["background_reintegration_required"] or child_projection["background_reintegration_required"]
    )
    projection["await_required"] = projection["await_required"] or child_projection["await_required"]
    projection["commit_consumption_required"] = (
        projection["commit_consumption_required"] or child_projection["commit_consumption_required"]
    )
    projection["protected_surface_touches"] = sorted(set(projection["protected_surface_touches"] + child_projection["protected_surface_touches"]))
    return build_result(
        {
            "artifact_type": graph.artifact_type,
            "candidate": graph.raw,
            **({"context": context} if context else {}),
        },
        graph,
        checks,
        violations,
        risks,
        projection,
    )


def security_compile(doc: dict) -> dict:
    inp = doc.get("input")
    if not isinstance(inp, dict):
        return build_error_result({"artifact_type": "gap", "candidate": {}}, "missing input object")
    try:
        graph = normalize_input(inp)
    except Exception as exc:
        return build_error_result(inp, str(exc))

    context = {
        **(inp.get("context") or {}),
        "mode": inp.get("mode"),
        "source": inp.get("source"),
    }
    result = analyze_graph(graph, context)
    result["input"] = inp
    return result


def main() -> int:
    try:
        doc = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps(build_error_result({"artifact_type": "gap", "candidate": {}}, f"invalid JSON input: {exc}"), indent=2))
        return 1

    result = security_compile(doc)
    print(json.dumps(result, indent=2))
    return 0 if result["result"]["status"] != "rejected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
