"""manifest_engine.py — stepchain package persistence and activation.

This module is the runtime surface for hash-addressed chain packages.
It persists deterministic workflow packages, resolves them by hash,
renders them back into semantic context, and activates them as the
first generation of runtime gaps.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from step import Step, Gap, Epistemic, Trajectory
from skills.loader import Skill, SkillRegistry


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


def stable_doc_hash(doc: dict) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def chain_package_path(chains_dir: Path, ref: str) -> Path:
    return chains_dir / f"{ref}.json"


def persist_chain_package(chains_dir: Path, doc: dict) -> str:
    chains_dir.mkdir(exist_ok=True)
    package_hash = stable_doc_hash(doc)
    path = chain_package_path(chains_dir, package_hash)
    if not path.exists():
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
    return package_hash


def load_chain_package(chains_dir: Path, ref: str, trajectory: Trajectory | None = None) -> dict | None:
    path = chain_package_path(chains_dir, ref)
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


def render_chain_package(package: dict, ref: str) -> str:
    if package.get("version") == "stepchain.v1":
        lines = [f"stepchain:{ref} \"{package.get('name', '')}\""]
        lines.append(f"  root: {package.get('root')}")
        lines.append(f"  trigger: {package.get('trigger')}")
        phase_order = package.get("phase_order", [])
        if phase_order:
            lines.append(f"  phases: {' -> '.join(phase_order)}")
        nodes = package.get("nodes", [])
        for node in nodes:
            if node.get("terminal"):
                continue
            activation = node.get("activation_key") or node.get("manifestation", {}).get("execution_mode")
            next_targets = list((node.get("transitions") or {}).values())
            next_str = f" -> {next_targets[0]}" if next_targets else ""
            lines.append(
                f"  - {_node_signature(node)} {node['id']} [{node.get('kind')}] "
                f"activate:{activation}{next_str}"
            )
        return "\n".join(lines)

    if "origin_gap" in package and "steps" in package:
        lines = [f"chain:{ref} \"{package.get('desc', '')}\""]
        lines.append(f"  origin_gap: {package.get('origin_gap')}")
        lines.append(f"  resolved: {package.get('resolved', False)}")
        for step in package.get("steps", [])[:6]:
            lines.append(f"  - step:{step.get('hash', '?')} \"{step.get('desc', '')}\"")
        if len(package.get("steps", [])) > 6:
            lines.append("  - ...")
        return "\n".join(lines)

    return f"(unrenderable chain package: {ref})"


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


def _node_relevance(node: dict, index: int) -> float:
    base = NODE_DEFAULT_RELEVANCE.get(node.get("kind"), 0.7)
    return max(0.3, base - (0.03 * index))


def activate_skill_package(skill: Skill, package_ref: str, gap: Gap,
                           origin_step: Step, entry_chain_id: str,
                           turn_counter: int, task_prompt: str | None = None,
                           embedded: bool = False) -> Step:
    activation_desc = (
        f"embedded workflow:{package_ref} for {gap.desc}"
        if embedded else
        f"activated workflow:{package_ref} for {gap.desc}"
    )
    if task_prompt:
        activation_desc += f" | task:{task_prompt}"
    step = Step.create(
        desc=activation_desc,
        step_refs=[origin_step.hash],
        content_refs=[package_ref] + gap.content_refs,
        chain_id=entry_chain_id,
    )
    for st_step in skill.steps:
        child_refs = [package_ref] + gap.content_refs + list(st_step.resolve) + list(st_step.content_refs)
        child_desc = st_step.desc if not task_prompt else f"{st_step.desc}\n\nActivation task: {task_prompt}"
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
        child_gap.vocab = st_step.vocab
        child_gap.turn_id = turn_counter
        step.gaps.append(child_gap)
    return step


def activate_stepchain_package(package: dict, package_ref: str, gap: Gap,
                               origin_step: Step, entry_chain_id: str,
                               turn_counter: int, task_prompt: str | None = None,
                               embedded: bool = False) -> Step:
    activation_desc = (
        f"embedded json chain:{package_ref} for {gap.desc}"
        if embedded else
        f"activated json chain:{package_ref} for {gap.desc}"
    )
    if task_prompt:
        activation_desc += f" | task:{task_prompt}"
    step = Step.create(
        desc=activation_desc,
        step_refs=[origin_step.hash],
        content_refs=[package_ref] + gap.content_refs,
        chain_id=entry_chain_id,
    )
    nodes_by_id = {node["id"]: node for node in package.get("nodes", [])}
    phase_order = package.get("phase_order", [])
    for index, node_id in enumerate(phase_order):
        node = nodes_by_id.get(node_id)
        if not node or node.get("terminal"):
            continue
        gap_template = node.get("gap_template", {})
        child_refs = [package_ref] + gap.content_refs + _runtime_ref_list(gap_template.get("content_refs", []))
        activation_ref = node.get("manifestation", {}).get("activation_ref")
        if activation_ref:
            child_refs.append(activation_ref)
        child_desc = gap_template.get("desc", node.get("goal", ""))
        if task_prompt:
            child_desc = f"{child_desc}\n\nActivation task: {task_prompt}"
        child_gap = Gap.create(
            desc=child_desc,
            content_refs=child_refs,
            step_refs=_runtime_ref_list(gap_template.get("step_refs", [])),
        )
        child_gap.scores = Epistemic(
            relevance=_node_relevance(node, index),
            confidence=0.8,
            grounded=0.0,
        )
        child_gap.vocab = _node_runtime_vocab(node)
        child_gap.turn_id = turn_counter
        step.gaps.append(child_gap)
    return step


def activate_chain_reference(chains_dir: Path, chain_ref: str, activation: str, gap: Gap,
                             origin_step: Step, entry_chain_id: str,
                             registry: SkillRegistry, compiler, trajectory: Trajectory,
                             turn_counter: int, task_prompt: str | None = None,
                             embedded: bool = False) -> Step | None:
    if activation == "background":
        compiler.record_background_trigger(entry_chain_id, refs=[chain_ref])
        return Step.create(
            desc=f"scheduled background chain:{chain_ref} for {gap.desc}",
            step_refs=[origin_step.hash],
            content_refs=[chain_ref] + gap.content_refs,
            chain_id=entry_chain_id,
        )

    skill = registry.resolve(chain_ref)
    if skill:
        return activate_skill_package(
            skill, chain_ref, gap, origin_step, entry_chain_id, turn_counter,
            task_prompt=task_prompt, embedded=embedded,
        )

    package = load_chain_package(chains_dir, chain_ref, trajectory)
    if package and package.get("version") == "stepchain.v1":
        return activate_stepchain_package(
            package, chain_ref, gap, origin_step, entry_chain_id, turn_counter,
            task_prompt=task_prompt, embedded=embedded,
        )

    return None
