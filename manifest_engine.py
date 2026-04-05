"""manifest_engine.py — stepchain package persistence and activation.

This module is the runtime surface for hash-addressed chain packages.
It persists deterministic workflow packages, resolves them by hash,
renders them back into semantic context, and activates them as the
first generation of runtime gaps.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import action_foundations as foundations
from step import Step, Gap, Epistemic, Trajectory, absolute_time, vocab_class
from skills.loader import Skill, SkillRegistry
from tools import st_builder as st_builder_module

ROOT = Path(__file__).resolve().parent
LEGACY_CHAINS_DIR = ROOT / "chains"
CHAINS_DIR = ROOT / "trajectory_store" / "command"
TRAJECTORY_STORE_NAMES = ("command", "subagent", "background_agent")


NODE_DEFAULT_RELEVANCE = {
    "observe": 1.0,
    "reason": 0.9,
    "higher_order": 0.9,
    "mutate": 0.8,
    "verify": 0.7,
    "embed": 0.75,
    "await": 0.65,
    "clarify": 1.0,
}

NODE_KIND_CODES = {
    "observe": "o",
    "reason": "b",
    "higher_order": "b",
    "mutate": "m",
    "verify": "v",
    "embed": "e",
    "await": "a",
    "clarify": "c",
    "terminal": "t",
}

SPAWN_CODES = {
    "none": "0",
    "context": "c",
    "action": "a",
    "mixed": "x",
    "embed": "e",
}

EXECUTION_MODE_CODES = {
    "runtime_vocab": "v",
    "curated_step_hash": "h",
    "inline": "i",
}

ENTITY_SEMANTIC_FIELDS = (
    "identity", "preferences", "constraints", "sources", "scope", "schema",
    "access_rules", "principles", "boundaries", "domain_knowledge", "init", "reasoning",
)


def stable_doc_hash(doc: dict) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def chain_package_path(chains_dir: Path, ref: str) -> Path:
    return chains_dir / f"{ref}.json"


def _candidate_chain_package_paths(chains_dir: Path, ref: str) -> list[Path]:
    candidates = [chain_package_path(chains_dir, ref)]
    if chains_dir.name in TRAJECTORY_STORE_NAMES:
        for sibling in TRAJECTORY_STORE_NAMES:
            sibling_dir = chains_dir.parent / sibling
            if sibling_dir == chains_dir:
                continue
            candidates.append(chain_package_path(sibling_dir, ref))
    if chains_dir != LEGACY_CHAINS_DIR:
        candidates.append(chain_package_path(LEGACY_CHAINS_DIR, ref))
    return candidates


def persist_chain_package(chains_dir: Path, doc: dict) -> str:
    chains_dir.mkdir(exist_ok=True)
    package_hash = stable_doc_hash(doc)
    path = chain_package_path(chains_dir, package_hash)
    if not path.exists():
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
    return package_hash


def load_chain_package(chains_dir: Path, ref: str, trajectory: Trajectory | None = None) -> dict | None:
    for path in _candidate_chain_package_paths(chains_dir, ref):
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return None

    if trajectory:
        chain = trajectory.chains.get(ref)
        if chain:
            steps = []
            for step_hash in chain.steps:
                step = trajectory.resolve(step_hash)
                if step:
                    steps.append(step.to_dict())
            return {
                "hash": chain.hash,
                "origin_gap": chain.origin_gap,
                "desc": chain.desc,
                "resolved": chain.resolved,
                "steps": steps,
            }
    return None


def _node_kind_code(node: dict) -> str:
    return NODE_KIND_CODES.get(node.get("kind"), "_")


def _compact_frontier_code(node: dict) -> str:
    kind = _node_kind_code(node)
    gaps = list(node.get("gaps", []) or [])
    if not gaps and isinstance(node.get("gap"), dict) and node.get("gap"):
        gap = dict(node.get("gap", {}) or {})
        if gap.get("status") in {"active", "dormant", "resolved"}:
            gaps = [gap]

    active = sum(1 for gap in gaps if gap.get("status") == "active")
    dormant = sum(1 for gap in gaps if gap.get("status") == "dormant")
    if active:
        return f"{kind}+{active}"
    if dormant:
        return f"{kind}~{dormant}"
    return f"{kind}="


def _spawn_code(node: dict) -> str:
    generation = node.get("generation", {})
    return SPAWN_CODES.get(generation.get("spawn_mode"), "_")


def _execution_mode_code(node: dict) -> str:
    manifestation = node.get("manifestation", {})
    return EXECUTION_MODE_CODES.get(manifestation.get("execution_mode"), "_")


def _node_signature(node: dict) -> str:
    """Compact package-node signature.

    Format: {kindspawnflowmode/s:c}
      kind: o observe, m mutate, b bridge/reason, v verify, a await, e embed, c clarify
      spawn: 0 none, c context, a action, x mixed, e embed
      flow: + post_diff/open re-entry, = closed/no re-entry
      mode: v runtime_vocab, h curated_step_hash, i inline, _ unknown
      s:c: gap_template step_refs:content_refs counts
    """
    gap_template = node.get("gap_template", {})
    flow = "+" if node.get("post_diff") else "="
    return (
        f"{{{_node_kind_code(node)}{_spawn_code(node)}{flow}{_execution_mode_code(node)}/"
        f"{len(gap_template.get('step_refs', []))}:{len(gap_template.get('content_refs', []))}}}"
    )


def _skill_package_tree_doc(skill: Skill) -> dict:
    payload = dict(skill.payload or skill.to_dict() or {})
    if payload.get("root") and isinstance(payload.get("phases"), list) and isinstance(payload.get("closure"), dict):
        return payload
    return st_builder_module.semantic_skeleton_from_st(payload)


def _render_ref_list(refs: list[str]) -> str:
    return ", ".join(refs) if refs else "(none)"


def _merged_refs(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for ref in group or []:
            if isinstance(ref, str) and ref not in merged:
                merged.append(ref)
    return merged


def _semantic_fields(doc: dict) -> dict:
    return {field: doc.get(field) for field in ENTITY_SEMANTIC_FIELDS if field in doc}


def _tree_latest_timestamp(nodes: list[dict]) -> float:
    values: list[float] = []
    for node in nodes:
        timestamp = dict(node.get("meta", {}) or {}).get("timestamp")
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            values.append(float(timestamp))
    return max(values) if values else 0.0


def _tree_compact_status(tree: dict) -> str:
    if tree.get("resolved") is True:
        return "resolved"
    return "active"


def _flat_ref_surface(node: dict) -> str:
    refs = dict(node.get("refs", {}) or {})
    own_refs = _merged_refs(refs.get("step_refs", []) or [], refs.get("content_refs", []) or [])
    return _render_ref_list(own_refs)


def _grouped_gap_refs(gap: dict) -> str:
    return (
        f"step:{_render_ref_list(gap.get('step_refs', []) or [])}, "
        f"content:{_render_ref_list(gap.get('content_refs', []) or [])}"
    )


def _render_gap_status(gap: dict, *, package_preview: bool) -> str:
    status = gap.get("status")
    if isinstance(status, str) and status not in {"", "(n/a)"}:
        return status
    return "planned" if package_preview else "active"


def _format_semantic_value(value, *, max_inline: int = 3) -> str:
    if isinstance(value, dict):
        keys = list(value.keys())
        if not keys:
            return "{}"
        preview = ", ".join(keys[:max_inline])
        suffix = " ..." if len(keys) > max_inline else ""
        return "{" + preview + suffix + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        preview = ", ".join(str(item) for item in value[:max_inline])
        suffix = " ..." if len(value) > max_inline else ""
        return "[" + preview + suffix + "]"
    return str(value)


def _semantic_gap_from_phase(phase: dict) -> dict:
    effective = st_builder_module.effective_phase_contract(phase)
    manifestation = dict(effective.get("manifestation", {}) or {})
    gap_template = dict(effective.get("gap_template", {}) or {})
    allowed_vocab = list(effective.get("allowed_vocab", []) or [])
    return {
        "desc": gap_template.get("desc", phase.get("goal", "")),
        "step_refs": list(gap_template.get("step_refs", []) or []),
        "content_refs": list(gap_template.get("content_refs", []) or []),
        "step_ref_count": len(gap_template.get("step_refs", []) or []),
        "content_ref_count": len(gap_template.get("content_refs", []) or []),
        "runtime_vocab": manifestation.get("runtime_vocab"),
        "allowed_vocab": allowed_vocab,
        "post_diff": bool(phase.get("post_diff", False)),
        "relevance": phase.get("relevance"),
    }


def _node_contract_from_phase(phase: dict, refs: dict[str, str] | None = None) -> dict | None:
    embedding = dict(phase.get("embedding", {}) or {})
    if not embedding:
        return None
    block_ref = embedding.get("block_ref")
    if isinstance(block_ref, str) and block_ref.startswith("@") and isinstance(refs, dict):
        block_ref = refs.get(block_ref[1:], block_ref)
    contract = {
        "block_ref": block_ref,
        "activation_mode": embedding.get("activation_mode", "hash_embedded"),
    }
    gap_override = embedding.get("gap_override")
    if isinstance(gap_override, dict) and gap_override:
        contract["gap_override"] = gap_override
    return contract


def _runtime_gap_status(gap: dict) -> str:
    if gap.get("dormant"):
        return "dormant"
    if gap.get("resolved"):
        return "resolved"
    return "active"


def _semantic_gap_from_runtime_gap(gap: dict, *, fallback_desc: str = "", post_diff: bool = False) -> dict:
    scores = dict(gap.get("scores", {}) or {})
    vocab = gap.get("vocab")
    desc = gap.get("desc") or fallback_desc
    expression = {
        "hash": gap.get("hash"),
        "desc": desc,
        "status": _runtime_gap_status(gap),
        "resolution_kind": gap.get("resolution_kind"),
        "step_refs": list(gap.get("step_refs", []) or []),
        "content_refs": list(gap.get("content_refs", []) or []),
        "step_ref_count": len(gap.get("step_refs", []) or []),
        "content_ref_count": len(gap.get("content_refs", []) or []),
        "runtime_vocab": vocab,
        "allowed_vocab": [vocab] if vocab else [],
        "post_diff": post_diff,
        "relevance": scores.get("relevance"),
        "confidence": scores.get("confidence"),
        "grounded": scores.get("grounded"),
    }
    if gap.get("origin"):
        expression["origin"] = gap["origin"]
    if gap.get("route_mode"):
        expression["route_mode"] = gap["route_mode"]
    return expression


def _runtime_step_kind(step: dict, gaps: list[dict]) -> str:
    if step.get("rogue"):
        return "higher_order"
    if step.get("commit"):
        return "mutate"
    primary = next((gap for gap in gaps if gap.get("status") == "active"), None)
    if primary is None:
        primary = next((gap for gap in gaps if gap.get("status") == "resolved"), None)
    if primary is None:
        primary = next((gap for gap in gaps if gap.get("status") == "dormant"), None)
    vocab = (primary or {}).get("runtime_vocab")
    klass = vocab_class(vocab)
    return {
        "o": "observe",
        "m": "mutate",
        "b": "reason",
        "c": "clarify",
    }.get(klass, "observe")


def _runtime_step_signature(step: dict, gaps: list[dict]) -> str:
    active = sum(1 for gap in gaps if gap.get("status") == "active")
    dormant = sum(1 for gap in gaps if gap.get("status") == "dormant")
    if step.get("rogue"):
        kind = "r"
    else:
        kind = "m" if step.get("commit") else "o"
    flow = "+" if active else "~" if dormant else "="
    count = str(active) if active else ""
    return f"{{{kind}{flow}{count}}}"


def _runtime_explicit_step_state(node: dict) -> str | None:
    meta = dict(node.get("meta", {}) or {})
    text = " ".join(
        str(part or "")
        for part in (
            node.get("goal"),
            node.get("action"),
            meta.get("failure_source"),
            meta.get("failure_detail"),
            meta.get("rogue_kind"),
        )
    ).lower()
    if "exhausted after" in text or "reason loop: exhausted" in text:
        return "exhausted"
    if "blocked" in text:
        return "blocked"
    return None


def _derive_runtime_step_states(nodes: list[dict]) -> None:
    downstream_state: str | None = None
    for node in reversed(nodes):
        gaps = list(node.get("gaps", []) or ([] if not node.get("gap") else [node.get("gap")]))
        has_active = any(gap.get("status") == "active" for gap in gaps)
        has_dormant = any(gap.get("status") == "dormant" for gap in gaps)
        explicit = _runtime_explicit_step_state(node)
        if explicit:
            state = explicit
        elif has_active:
            state = "open"
        elif downstream_state in {"blocked", "exhausted"}:
            state = downstream_state
        elif downstream_state in {"open", "progressed"}:
            state = "open"
        elif has_dormant:
            state = "progressed"
        else:
            state = "resolved"
        node.setdefault("meta", {})["state"] = state
        downstream_state = state if state in {"open", "progressed", "blocked", "exhausted"} else None


def _semantic_parent_map(phases: list[dict]) -> dict[str, str]:
    parents: dict[str, str] = {}
    ids = {phase.get("id") for phase in phases}
    for phase in phases:
        parent_id = phase.get("id")
        for target in (phase.get("transitions", {}) or {}).values():
            if target in ids and target != "phase_done" and target not in parents:
                parents[target] = parent_id
    return parents


def _semantic_summary(nodes: list[dict], root_id: str | None) -> dict:
    return {
        "root_id": root_id,
        "node_count": len(nodes),
        "post_diff_nodes": sum(1 for node in nodes if node.get("gap", {}).get("post_diff") is True),
        "runtime_vocab_nodes": sum(1 for node in nodes if node.get("gap", {}).get("runtime_vocab")),
        "bridge_nodes": sum(1 for node in nodes if node.get("kind") in {"reason", "higher_order", "await"}),
        "mutation_nodes": sum(1 for node in nodes if node.get("kind") == "mutate"),
        "max_depth": max((node.get("depth", 0) for node in nodes), default=0),
    }


def build_runtime_semantic_tree(steps: list[dict], *, source_type: str, source_ref: str | None = None,
                                root_id: str | None = None, summary_desc: str | None = None,
                                origin_gap: str | None = None, resolved: bool | None = None,
                                registry: SkillRegistry | None = None,
                                chains_dir: Path = CHAINS_DIR,
                                cors_root: Path = ROOT,
                                tool_map: dict[str, dict] | None = None,
                                git: Any = None) -> dict:
    git = git or _git_text
    nodes = []
    previous_id = None
    for depth, step in enumerate(steps):
        step_id = step.get("hash", f"step_{depth}")
        gaps = [
            _semantic_gap_from_runtime_gap(gap or {}, fallback_desc=step.get("desc", ""), post_diff=bool(step.get("commit")))
            for gap in (step.get("gaps", []) or [])
        ]
        primary_gap = next((gap for gap in gaps if gap.get("status") == "active"), None)
        if primary_gap is None:
            primary_gap = next((gap for gap in gaps if gap.get("status") == "resolved"), None)
        if primary_gap is None:
            primary_gap = next((gap for gap in gaps if gap.get("status") == "dormant"), None)
        if primary_gap is None:
            primary_gap = {
                "desc": step.get("desc", ""),
                "status": "resolved" if not gaps else "active",
                "step_refs": [],
                "content_refs": [],
                "step_ref_count": 0,
                "content_ref_count": 0,
                "runtime_vocab": None,
                "allowed_vocab": [],
                "post_diff": bool(step.get("commit")),
                "relevance": None,
                "confidence": None,
                "grounded": None,
            }
        effective_contract = _runtime_effective_contract(
            step,
            primary_gap,
            registry=registry,
            chains_dir=chains_dir,
            cors_root=cors_root,
            tool_map=tool_map,
            git=git,
        )
        nodes.append(
            {
                "id": step_id,
                "parent_id": previous_id,
                "depth": depth,
                "signature": _runtime_step_signature(step, gaps),
                "kind": _runtime_step_kind(step, gaps),
                "action": step.get("desc"),
                "goal": step.get("desc"),
                "gap": primary_gap,
                "gaps": gaps,
                "manifestation": {
                    "execution_mode": "runtime_vocab" if primary_gap.get("runtime_vocab") else "inline",
                    "background": False,
                },
                "generation": {"return_policy": "resume_parent"},
                "transitions": {},
                "effective_contract": effective_contract,
                "refs": {
                    "step_refs": list(step.get("step_refs", []) or []),
                    "content_refs": list(step.get("content_refs", []) or []),
                },
                "meta": {
                    "timestamp": step.get("t", 0.0),
                    "commit": step.get("commit"),
                    "chain_id": step.get("chain_id"),
                    "parent": step.get("parent"),
                    "rogue": bool(step.get("rogue")),
                    "rogue_kind": step.get("rogue_kind"),
                    "failure_source": step.get("failure_source"),
                    "failure_detail": step.get("failure_detail"),
                    "assessment": list(step.get("assessment", []) or []),
                },
            }
        )
        previous_id = step_id

    _derive_runtime_step_states(nodes)

    semantic_tree = {
        "version": "semantic_tree.v1",
        "source_type": source_type,
        "source_ref": source_ref or (nodes[0]["id"] if nodes else ""),
        "root_id": root_id or (nodes[0]["id"] if nodes else None),
        "nodes": nodes,
        "summary": _semantic_summary(nodes, root_id or (nodes[0]["id"] if nodes else None)),
    }
    if summary_desc is not None:
        semantic_tree["desc"] = summary_desc
    if origin_gap is not None:
        semantic_tree["origin_gap"] = origin_gap
    if resolved is not None:
        semantic_tree["resolved"] = resolved
    return semantic_tree


def build_semantic_tree(doc: dict, *, source_type: str, source_ref: str | None = None) -> dict:
    if doc.get("version") == "step_chain.v1":
        lowered, _, _ = st_builder_module.lower_step_chain(doc)
        return build_semantic_tree(lowered, source_type=source_type, source_ref=source_ref or doc.get("name"))

    if doc.get("version") == "stepchain.v1":
        phases = [dict(node or {}) for node in doc.get("nodes", []) if not (node or {}).get("terminal")]
        root_id = doc.get("root")
        parents = _semantic_parent_map(phases)
        nodes = []
        for phase in phases:
            node_id = phase.get("id")
            parent_id = parents.get(node_id)
            gap = _semantic_gap_from_phase(phase)
            nodes.append(
                {
                    "id": node_id,
                    "parent_id": parent_id,
                    "depth": 0 if parent_id is None else 1,
                    "signature": _node_signature(phase),
                    "kind": phase.get("kind"),
                    "action": phase.get("action"),
                    "goal": phase.get("goal"),
                    "gap": gap,
                    "manifestation": dict(phase.get("manifestation", {}) or {}),
                    "generation": dict(phase.get("generation", {}) or {}),
                    "transitions": dict(phase.get("transitions", {}) or {}),
                }
            )
        return {
            "version": "semantic_tree.v1",
            "source_type": source_type,
            "source_ref": source_ref or root_id or "",
            "root_id": root_id,
            "nodes": nodes,
            "summary": _semantic_summary(nodes, root_id),
        }

    if doc.get("origin_gap") is not None and isinstance(doc.get("steps"), list):
        return build_runtime_semantic_tree(
            list(doc.get("steps", []) or []),
            source_type=source_type,
            source_ref=source_ref or doc.get("hash"),
            root_id=None,
            summary_desc=doc.get("desc"),
            origin_gap=doc.get("origin_gap"),
            resolved=doc.get("resolved"),
        )

    normalized = doc
    if not (normalized.get("root") and isinstance(normalized.get("phases"), list) and isinstance(normalized.get("closure"), dict)):
        normalized = st_builder_module.semantic_skeleton_from_st(doc)
    phases = [dict(phase or {}) for phase in normalized.get("phases", []) if not (phase or {}).get("terminal")]
    root_id = normalized.get("root")
    parents = _semantic_parent_map(phases)
    nodes = []
    package_refs = dict(normalized.get("refs", {}) or {})
    for phase in phases:
        effective_phase = st_builder_module.effective_phase_contract(phase)
        node_id = phase.get("id")
        parent_id = parents.get(node_id)
        nodes.append(
            {
                "id": node_id,
                "parent_id": parent_id,
                "depth": 0 if parent_id is None else 1,
                "signature": _node_signature(phase),
                "kind": phase.get("kind"),
                "action": phase.get("action"),
                "goal": phase.get("goal"),
                "gap": _semantic_gap_from_phase(phase),
                "manifestation": dict(effective_phase.get("manifestation", {}) or {}),
                "generation": dict(effective_phase.get("generation", {}) or {}),
                "transitions": dict(effective_phase.get("transitions", {}) or {}),
                "contract": _node_contract_from_phase(phase, refs=package_refs),
            }
        )
    return {
        "version": "semantic_tree.v1",
        "source_type": source_type,
        "source_ref": source_ref or normalized.get("name") or root_id or "",
        "root_id": root_id,
        "nodes": nodes,
        "summary": _semantic_summary(nodes, root_id),
        "package": {
            "name": normalized.get("name"),
            "trigger": normalized.get("trigger"),
            "desc": normalized.get("desc"),
            "artifact": dict(normalized.get("artifact", {}) or {}),
            "refs": dict(normalized.get("refs", {}) or {}),
            "closure": dict(normalized.get("closure", {}) or {}),
            "semantics": _semantic_fields(doc),
        },
    }


def build_semantic_tree_from_trajectory(traj: Trajectory, *, chain_id: str | None = None,
                                        recent_n: int = 5, registry: SkillRegistry | None = None,
                                        chains_dir: Path = CHAINS_DIR, cors_root: Path = ROOT,
                                        tool_map: dict[str, dict] | None = None,
                                        git: Any = None) -> dict:
    git = git or _git_text
    if chain_id:
        chain = traj.chains.get(chain_id)
        if chain is None:
            chain = next((candidate for candidate in traj.chains.values() if candidate.hash == chain_id), None)
        if chain:
            steps = [traj.steps[step_hash].to_dict() for step_hash in chain.steps if step_hash in traj.steps]
            return build_runtime_semantic_tree(
                steps,
                source_type="realized_chain",
                source_ref=chain.hash,
                summary_desc=chain.desc,
                origin_gap=chain.origin_gap,
                resolved=chain.resolved,
                registry=registry,
                chains_dir=chains_dir,
                cors_root=cors_root,
                tool_map=tool_map,
                git=git,
            )
    steps = [step.to_dict() for step in traj.recent(recent_n)]
    return build_runtime_semantic_tree(
        steps,
        source_type="trajectory_recent",
        source_ref="recent",
        summary_desc="recent trajectory",
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map,
        git=git,
    )


def render_semantic_tree(tree: dict) -> str:
    source_type = tree.get("source_type", "unknown")
    source_ref = tree.get("source_ref", tree.get("root_id", ""))
    lines = [f"semantic_tree:{source_type}:{source_ref}"]
    nodes = list(tree.get("nodes", []) or [])
    if not nodes:
        lines.append("nodes: (none)")
        return "\n".join(lines)

    package = dict(tree.get("package", {}) or {})
    foundation = dict(tree.get("foundation", {}) or {})
    latest_ts = _tree_latest_timestamp(nodes)
    latest_suffix = f" [{absolute_time(latest_ts)}]" if latest_ts else ""

    if package:
        package_name = package.get("name", source_ref or "(none)")
        package_desc = package.get("desc") or package_name
        lines.append(f'package:{package_name} "{package_desc}" ({len(nodes)} steps){latest_suffix}')
        if package.get("trigger"):
            lines.append(f"trigger: {package.get('trigger')}")
    else:
        chain_desc = tree.get("desc") or source_ref or "semantic chain"
        lines.append(f'chain:{source_ref} "{chain_desc}" ({_tree_compact_status(tree)}, {len(nodes)} steps){latest_suffix}')
        if tree.get("origin_gap"):
            lines.append(f"origin: {tree.get('origin_gap')}")
    lines.append("legend: step{o/m/b/c + frontier}; gap{status + surface + ref-counts}")

    if foundation:
        lines.append(
            "foundation: "
            f"ref={foundation.get('ref', '(none)')} "
            f"kind={foundation.get('kind', '(none)')} "
            f"surface={foundation.get('surface', '(none)')} "
            f"activation={foundation.get('activation', '(none)')} "
            f"omo={foundation.get('omo_role', '(none)')}"
        )

    for index, node in enumerate(nodes):
        branch = "└" if index == len(nodes) - 1 else "├"
        cont = " " if index == len(nodes) - 1 else "│"
        gap = dict(node.get("gap", {}) or {})
        transitions = dict(node.get("transitions", {}) or {})
        meta = dict(node.get("meta", {}) or {})
        contract = dict(node.get("contract", {}) or {})
        effective_contract = dict(node.get("effective_contract", {}) or {})
        step_ts = meta.get("timestamp")
        step_ts_suffix = f" [{absolute_time(step_ts)}]" if isinstance(step_ts, (int, float)) and step_ts > 0 else ""
        step_label = f'"{node.get("action", "?")}"'
        lines.append(
            f'{branch}─ {{{_compact_frontier_code(node)}}} step:{node.get("id")} '
            f'{step_label} -> refs:[{_flat_ref_surface(node)}]{step_ts_suffix}'
        )
        if effective_contract or gap:
            gap_id = gap.get("hash", f"{node.get('id')}.gap")
            gap_surface = gap.get("runtime_vocab") or effective_contract.get("effective_gap") or effective_contract.get("default_gap")
            gap_role = (effective_contract.get("omo_role") if effective_contract else None) or vocab_class(gap_surface)
            if gap_role in {None, "", "_"}:
                gap_role = _node_kind_code(node)
            gap_status = _render_gap_status(gap, package_preview=bool(package))
            lines.append(
                f"{cont}  └─ {{{gap_status}:{gap_role}}} gap:{gap_id}"
                f"{f' [{gap_surface}]' if gap_surface else ''} -> refs:[{_grouped_gap_refs(gap)}]"
            )
        if transitions:
            lines.append(f"{cont}  next: {', '.join(f'{k}->{v}' for k, v in transitions.items())}")
        if contract:
            lines.append(f"{cont}  @embed:{contract.get('block_ref', '(none)')} [{contract.get('activation_mode', '(none)')}]")
            if contract.get("gap_override"):
                lines.append(f"{cont}  embed_override: {json.dumps(contract.get('gap_override'), sort_keys=True)}")
        all_gaps = list(node.get("gaps", []) or [])
        if len(all_gaps) > 1:
            for gap_index, item in enumerate(all_gaps[1:], start=1):
                gbranch = "└" if gap_index == len(all_gaps) - 1 else "├"
                gap_surface = item.get("runtime_vocab")
                gap_role = vocab_class(gap_surface)
                if gap_role in {None, "", "_"}:
                    gap_role = _node_kind_code(node)
                gap_status = _render_gap_status(item, package_preview=bool(package))
                lines.append(
                    f"{cont}  {gbranch}─ {{{gap_status}:{gap_role}}} "
                    f"gap:{item.get('hash', '(none)')}{f' [{gap_surface}]' if gap_surface else ''} "
                    f"-> refs:[{_grouped_gap_refs(item)}]"
                )
    return "\n".join(lines)


def render_skill_package(skill: Skill) -> str:
    package = _skill_package_tree_doc(skill)
    tree = build_semantic_tree(package, source_type="skill_package", source_ref=skill.hash)
    tree["foundation"] = foundations.foundation_from_skill(skill, cors_root=ROOT).__dict__
    return render_semantic_tree(tree)


def render_chain_package(package: dict, ref: str) -> str:
    if package.get("version") == "stepchain.v1":
        tree = build_semantic_tree(package, source_type="stepchain", source_ref=ref)
        tree["foundation"] = foundations.foundation_from_chain_doc(package, ref=ref, chains_dir=CHAINS_DIR).__dict__
        return render_semantic_tree(tree)

    if "origin_gap" in package and "steps" in package:
        tree = build_semantic_tree(package, source_type="realized_chain", source_ref=ref)
        tree["foundation"] = foundations.foundation_from_chain_doc(package, ref=ref, chains_dir=CHAINS_DIR).__dict__
        return render_semantic_tree(tree)

    return f"(unrenderable chain package: {ref})"


def render_trace_tree(trace_tree: dict) -> str:
    lines = [f"semantic_tree:trace_tree:{trace_tree.get('source_ref', trace_tree.get('root_trace', ''))}"]
    lines.append(f"  root: {trace_tree.get('root_trace', '(none)')}")
    summary = dict(trace_tree.get("summary", {}) or {})
    if summary:
        lines.append(
            "  summary: "
            f"max_depth={summary.get('max_depth', 0)} "
            f"generation_count={summary.get('generation_count', 0)} "
            f"bridge_nodes={summary.get('bridge_nodes', 0)} "
            f"mutation_nodes={summary.get('mutation_nodes', 0)} "
            f"reentry_points={summary.get('reentry_points', 0)}"
        )
    traces = list(trace_tree.get("traces", []) or [])
    lines.append("  nodes")
    for index, trace in enumerate(traces):
        branch = "└" if index == len(traces) - 1 else "├"
        cont = " " if index == len(traces) - 1 else "│"
        gap = dict(trace.get("gap", {}) or {})
        manifestation = dict(trace.get("manifestation", {}) or {})
        topology = dict(trace.get("topology", {}) or {})
        outcome = dict(trace.get("outcome", {}) or {})
        source = trace.get("source_phase") or trace.get("source_step") or "(none)"
        lines.append(f"  {branch}─ {gap.get('signature', '(sig)')} {trace.get('id')} source:{source}")
        lines.append(f"  {cont}  gap.desc: {gap.get('desc', '(none)')}")
        lines.append(
            f"  {cont}  gap.state: status={gap.get('status', '(n/a)')} "
            f"vocab={gap.get('vocab', '(none)')} "
            f"step_refs={gap.get('step_ref_count', 0)} "
            f"content_refs={gap.get('content_ref_count', 0)}"
        )
        lines.append(
            f"  {cont}  manifestation: kind={manifestation.get('kind', '(none)')} "
            f"spawn_mode={manifestation.get('spawn_mode', '(none)')} "
            f"activation_mode={manifestation.get('activation_mode', '(none)')} "
            f"return_policy={manifestation.get('return_policy', '(none)')}"
        )
        lines.append(
            f"  {cont}  topology: depth={topology.get('depth', 0)} "
            f"generation={topology.get('generation', 0)} "
            f"children={', '.join(topology.get('child_ids', []) or []) or '(none)'}"
        )
        lines.append(
            f"  {cont}  outcome: terminal_state={outcome.get('terminal_state', '(none)')} "
            f"closure_reason={outcome.get('closure_reason', '(none)')}"
        )
    return "\n".join(lines)


def available_chain_refs(chains_dir: Path, registry: SkillRegistry, is_entity_skill) -> str:
    lines = []
    for skill in sorted(registry.all_skills(), key=lambda s: s.display_name):
        if is_entity_skill(skill):
            continue
        kind = "codon" if "codons" in skill.source else "step"
        lines.append(f"  {skill.hash} ({skill.name}.st, {kind}) — {skill.desc[:80]}")
    if chains_dir.exists():
        for path in sorted(chains_dir.glob("*.json")):
            try:
                with open(path) as f:
                    package = json.load(f)
            except json.JSONDecodeError:
                continue
            if package.get("version") == "stepchain.v1":
                lines.append(
                    f"  {path.stem} ({package.get('name', 'unnamed')}.json, stepchain) — "
                    f"{package.get('desc', '')[:80]}"
                )
    return "\n".join(lines) if lines else "  (none)"


def render_step_network(chains_dir: Path, registry: SkillRegistry, is_entity_skill, load_payload) -> str:
    """Render the current semantic/executable package ecology.

    The network is a structural view for reason_needed and reprogramme_needed:
      - entity .st files as semantic-state nodes
      - executable .st files as step-package nodes
      - saved compiled stepchains as action-package nodes
      - /command entrypoints as explicit execution surfaces
    """
    lines = ["step_network"]

    entity_skills = sorted(
        [skill for skill in registry.all_skills() if is_entity_skill(skill)],
        key=lambda skill: skill.display_name,
    )
    lines.append("├─ entities")
    if entity_skills:
        for i, skill in enumerate(entity_skills):
            branch = "└" if i == len(entity_skills) - 1 else "├"
            cont = " " if i == len(entity_skills) - 1 else "│"
            payload = load_payload(skill) or {}
            lines.append(
                f"│  {branch}─ {skill.display_name}:{skill.hash} ({Path(skill.source).name}, trigger:{skill.trigger})"
            )
            fields = [
                field for field in (
                    "identity", "preferences", "constraints", "sources", "scope",
                    "schema", "access_rules", "principles", "boundaries", "domain_knowledge",
                )
                if field in payload
            ]
            if fields:
                lines.append(f"│  {cont}  ├─ semantics: {', '.join(sorted(fields))}")
            refs = payload.get("refs", {})
            if refs:
                lines.append(f"│  {cont}  └─ refs: {', '.join(sorted(refs.keys()))}")
            elif not fields:
                lines.append(f"│  {cont}  └─ semantics: (pure entity)")
    else:
        lines.append("│  └─ (none)")

    executable_skills = sorted(
        [skill for skill in registry.all_skills() if not is_entity_skill(skill)],
        key=lambda skill: skill.display_name,
    )
    lines.append("├─ executable_packages")
    if executable_skills:
        for skill in executable_skills:
            kind = "codon" if "codons" in skill.source else "step"
            steps = " → ".join(step.action for step in skill.steps[:4]) if skill.steps else "(none)"
            more = " ..." if len(skill.steps) > 4 else ""
            lines.append(
                f"│  ├─ {skill.hash} ({skill.name}.st, {kind}, trigger:{skill.trigger})"
            )
            lines.append(f"│  │  └─ steps: {steps}{more}")
    else:
        lines.append("│  └─ (none)")

    lines.append("├─ compiled_stepchains")
    compiled_paths = sorted(chains_dir.glob("*.json")) if chains_dir.exists() else []
    compiled_any = False
    for path in compiled_paths:
        try:
            with open(path) as f:
                package = json.load(f)
        except json.JSONDecodeError:
            continue
        if package.get("version") != "stepchain.v1":
            continue
        compiled_any = True
        phase_order = package.get("phase_order", [])
        lines.append(
            f"│  ├─ {path.stem} ({package.get('name', 'unnamed')}.json, trigger:{package.get('trigger', 'manual')})"
        )
        if phase_order:
            lines.append(f"│  │  └─ phases: {' -> '.join(phase_order)}")
    if not compiled_any:
        lines.append("│  └─ (none)")

    lines.append("└─ commands")
    commands = sorted(registry.all_commands(), key=lambda skill: skill.name)
    if commands:
        for i, skill in enumerate(commands):
            branch = "└" if i == len(commands) - 1 else "├"
            steps = " → ".join(step.action for step in skill.steps[:4]) if skill.steps else "(none)"
            more = " ..." if len(skill.steps) > 4 else ""
            lines.append(f"   {branch}─ /{skill.name} ({Path(skill.source).name})")
            lines.append(f"      └─ steps: {steps}{more}")
    else:
        lines.append("   └─ (none)")

    return "\n".join(lines)


def _runtime_ref_list(refs: list[str]) -> list[str]:
    return [ref for ref in refs if isinstance(ref, str) and not ref.startswith("$")]


def _git_text(cmd: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *cmd],
        cwd=cwd or str(ROOT),
        capture_output=True,
        text=True,
    )
    return result.stdout


def _node_runtime_vocab(node: dict) -> str | None:
    manifestation = node.get("manifestation", {})
    runtime_vocab = manifestation.get("runtime_vocab")
    if runtime_vocab:
        return runtime_vocab

    kernel_class = manifestation.get("kernel_class")
    if kernel_class == "observe":
        return "hash_resolve_needed"
    if kernel_class == "mutate":
        return "hash_edit_needed"
    if kernel_class == "clarify":
        return "clarify_needed"
    if kernel_class == "bridge":
        return "reason_needed"

    allowed_vocab = node.get("allowed_vocab", [])
    return allowed_vocab[0] if allowed_vocab else None


def _resolved_embedding_ref(node: dict, refs: dict[str, str]) -> str | None:
    embedding = dict(node.get("embedding", {}) or {})
    block_ref = embedding.get("block_ref")
    if not isinstance(block_ref, str):
        return None
    if block_ref.startswith("@"):
        return refs.get(block_ref[1:])
    return block_ref


def _runtime_effective_contract(step: dict, primary_gap: dict, *, registry: SkillRegistry | None,
                                chains_dir: Path, cors_root: Path, tool_map: dict[str, dict] | None,
                                git: Any) -> dict | None:
    refs: list[str] = []
    for ref in list(step.get("content_refs", []) or []) + list(primary_gap.get("content_refs", []) or []):
        if isinstance(ref, str) and ref not in refs:
            refs.append(ref)

    foundation = None
    for ref in refs:
        foundation = foundations.resolve_default_contract(
            ref,
            registry=registry,
            chains_dir=chains_dir,
            cors_root=cors_root,
            tool_map=tool_map or {},
            git=git,
        )
        if foundation:
            break

    runtime_vocab = primary_gap.get("runtime_vocab")
    if foundation is None and not runtime_vocab:
        return None

    default_gap = foundation.get("default_gap") if foundation else None
    effective_gap = runtime_vocab or default_gap
    activation_mode = None
    if foundation:
        if runtime_vocab and default_gap and runtime_vocab != default_gap:
            activation_mode = "hash_embedded"
        elif default_gap:
            activation_mode = "named_default"

    contract = {
        "effective_gap": effective_gap,
        "activation_mode": activation_mode,
    }
    if foundation:
        contract.update(foundation)
    return contract


def _apply_foundation_default_contract(node: dict, *, refs: dict[str, str], registry: SkillRegistry | None,
                                       chains_dir: Path, cors_root: Path, tool_map: dict[str, dict] | None,
                                       git: Any) -> tuple[dict, dict | None]:
    effective = st_builder_module.effective_phase_contract(node)
    block_ref = _resolved_embedding_ref(node, refs)
    if not block_ref:
        return effective, None
    contract = foundations.resolve_default_contract(
        block_ref,
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map or {},
        git=git,
    )
    if not contract:
        return effective, None
    embedding = dict(node.get("embedding", {}) or {})
    if embedding.get("activation_mode", "hash_embedded") == "named_default":
        manifestation = dict(effective.get("manifestation", {}) or {})
        if not manifestation.get("runtime_vocab") and contract.get("default_gap") not in {None, "", "internal_only"}:
            manifestation["runtime_vocab"] = contract["default_gap"]
            manifestation.setdefault("execution_mode", "runtime_vocab")
            effective["manifestation"] = manifestation
        if not effective.get("allowed_vocab") and contract.get("default_gap") not in {None, "", "internal_only"}:
            effective["allowed_vocab"] = [contract["default_gap"]]
    return effective, contract


def _node_relevance(node: dict, index: int) -> float:
    base = NODE_DEFAULT_RELEVANCE.get(node.get("kind"), 0.7)
    return max(0.3, base - (0.03 * index))


def _effective_skill_step_vocab(skill: Skill, st_step: Any, foundation_contract: dict | None) -> str | None:
    if getattr(st_step, "vocab", None):
        return st_step.vocab
    default_gap = (foundation_contract or {}).get("default_gap")
    if len(getattr(skill, "steps", []) or []) == 1 and default_gap not in {None, "", "internal_only"}:
        return default_gap
    return None


def _trigger_context_refs(registry: SkillRegistry | None) -> list[str]:
    if registry is None:
        return []
    trigger_skill = registry.resolve_by_name("trigger")
    if trigger_skill is None:
        return []
    return [trigger_skill.hash]


def activate_skill_package(skill: Skill, package_ref: str, gap: Gap,
                           origin_step: Step, entry_chain_id: str,
                           turn_counter: int, task_prompt: str | None = None,
                           embedded: bool = False,
                           registry: SkillRegistry | None = None,
                           chains_dir: Path = CHAINS_DIR,
                           cors_root: Path = ROOT,
                           tool_map: dict[str, dict] | None = None,
                           git: Any = _git_text) -> Step:
    activation_desc = (
        f"embedded workflow:{package_ref} for {gap.desc}"
        if embedded else
        f"activated workflow:{package_ref} for {gap.desc}"
    )
    if task_prompt:
        activation_desc += f" | task:{task_prompt}"
    trigger_refs = _trigger_context_refs(registry)
    step = Step.create(
        desc=activation_desc,
        step_refs=[origin_step.hash],
        content_refs=trigger_refs + [package_ref] + gap.content_refs,
        chain_id=entry_chain_id,
    )
    foundation_contract = foundations.resolve_default_contract(
        package_ref,
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map or {},
        git=git,
    )
    for st_step in skill.steps:
        child_refs = [package_ref] + gap.content_refs + list(st_step.resolve) + list(st_step.content_refs)
        child_desc = st_step.desc if not task_prompt else f"{st_step.desc}\n\nActivation task: {task_prompt}"
        effective_vocab = _effective_skill_step_vocab(skill, st_step, foundation_contract)
        if not child_desc and foundation_contract and foundation_contract.get("default_gap") not in {None, "", "internal_only"}:
            child_desc = f"activate foundation {foundation_contract['ref']} via {foundation_contract['default_gap']}"
        child_gap = Gap.create(
            desc=child_desc,
            content_refs=child_refs,
            step_refs=list(st_step.step_refs),
        )
        child_gap.scores = Epistemic(
            relevance=st_step.relevance if st_step.relevance is not None else 0.8,
            confidence=0.8,
            grounded=0.0,
        )
        child_gap.vocab = effective_vocab
        child_gap.turn_id = turn_counter
        step.gaps.append(child_gap)
    return step


def activate_stepchain_package(package: dict, package_ref: str, gap: Gap,
                               origin_step: Step, entry_chain_id: str,
                               turn_counter: int, task_prompt: str | None = None,
                               embedded: bool = False,
                               registry: SkillRegistry | None = None,
                               chains_dir: Path = CHAINS_DIR,
                               cors_root: Path = ROOT,
                               tool_map: dict[str, dict] | None = None,
                               git: Any = _git_text) -> Step:
    activation_desc = (
        f"embedded json chain:{package_ref} for {gap.desc}"
        if embedded else
        f"activated json chain:{package_ref} for {gap.desc}"
    )
    if task_prompt:
        activation_desc += f" | task:{task_prompt}"
    trigger_refs = _trigger_context_refs(registry)
    step = Step.create(
        desc=activation_desc,
        step_refs=[origin_step.hash],
        content_refs=trigger_refs + [package_ref] + gap.content_refs,
        chain_id=entry_chain_id,
    )
    nodes_by_id = {node["id"]: node for node in package.get("nodes", [])}
    refs = dict(package.get("refs", {}) or {})
    phase_order = package.get("phase_order", [])
    for index, node_id in enumerate(phase_order):
        node = nodes_by_id.get(node_id)
        if not node or node.get("terminal"):
            continue
        effective_node, foundation_contract = _apply_foundation_default_contract(
            node,
            refs=refs,
            registry=registry,
            chains_dir=chains_dir,
            cors_root=cors_root,
            tool_map=tool_map,
            git=git,
        )
        gap_template = dict(effective_node.get("gap_template", {}) or {})
        child_refs = [package_ref] + gap.content_refs + _runtime_ref_list(gap_template.get("content_refs", []))
        activation_ref = effective_node.get("manifestation", {}).get("activation_ref")
        if activation_ref:
            child_refs.append(activation_ref)
        block_ref = _resolved_embedding_ref(node, refs)
        if block_ref:
            child_refs.append(block_ref)
        child_desc = gap_template.get("desc", effective_node.get("goal", node.get("goal", "")))
        if not child_desc and foundation_contract and foundation_contract.get("default_gap") not in {None, "", "internal_only"}:
            child_desc = f"activate foundation {foundation_contract['ref']} via {foundation_contract['default_gap']}"
        if task_prompt:
            child_desc = f"{child_desc}\n\nActivation task: {task_prompt}"
        child_gap = Gap.create(
            desc=child_desc,
            content_refs=child_refs,
            step_refs=_runtime_ref_list(gap_template.get("step_refs", [])),
        )
        child_gap.scores = Epistemic(
            relevance=_node_relevance(effective_node, index),
            confidence=0.8,
            grounded=0.0,
        )
        child_gap.vocab = _node_runtime_vocab(effective_node)
        child_gap.turn_id = turn_counter
        step.gaps.append(child_gap)
    return step


def activate_chain_reference(chains_dir: Path, chain_ref: str, activation: str, gap: Gap,
                             origin_step: Step, entry_chain_id: str,
                             registry: SkillRegistry, compiler, trajectory: Trajectory,
                             turn_counter: int, task_prompt: str | None = None,
    embedded: bool = False,
    tool_map: dict[str, dict] | None = None,
    await_policy: str = "none",
    store_kind: str = "background_agent") -> Step | None:
    trigger_refs = _trigger_context_refs(registry)
    if activation == "background":
        compiler.record_background_trigger(
            entry_chain_id,
            refs=trigger_refs + [chain_ref] + gap.content_refs,
            activation_ref=chain_ref,
            await_policy=await_policy,
            store_kind=store_kind,
            parent_step=origin_step.hash,
        )
        return Step.create(
            desc=f"scheduled background chain:{chain_ref} [{await_policy}] for {gap.desc}",
            step_refs=[origin_step.hash],
            content_refs=trigger_refs + [chain_ref] + gap.content_refs,
            chain_id=entry_chain_id,
        )

    skill = registry.resolve(chain_ref)
    if skill:
        return activate_skill_package(
            skill, chain_ref, gap, origin_step, entry_chain_id, turn_counter,
            task_prompt=task_prompt, embedded=embedded,
            registry=registry, chains_dir=chains_dir, cors_root=ROOT, tool_map=tool_map or {}, git=_git_text,
        )

    package = load_chain_package(chains_dir, chain_ref, trajectory)
    if package and package.get("version") == "stepchain.v1":
        return activate_stepchain_package(
            package, chain_ref, gap, origin_step, entry_chain_id, turn_counter,
            task_prompt=task_prompt, embedded=embedded,
            registry=registry, chains_dir=chains_dir, cors_root=ROOT, tool_map=tool_map or {}, git=_git_text,
        )

    return None
