"""Unified hash-native action foundation inventory.

This module derives the compositional building blocks that reason_needed
should see when authoring workflows:
  - action/codon packages by committed skill hash
  - extracted chains by committed chain hash
  - tool scripts by committed blob hash

Public/classified activation is metadata on top of a stable hash
identity. Name/vocab activation uses the default gap contract; hash-based
embedding may specialize manifestation in an enclosing chain.
"""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.tool_contract import load_tool_contract
from tools.tool_registry import public_tool_paths
from vocab_registry import is_bridge, is_mutate, is_observe


@dataclass(frozen=True)
class FoundationSpec:
    ref: str
    kind: str
    surface: str
    source: str
    desc: str
    activation: str
    default_gap: str
    omo_role: str


def _git_head_blob(path: str, *, cors_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=cors_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    return lines[0][:12] if lines else None


def _first_line(text: str, limit: int = 100) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""
    return clean.splitlines()[0][:limit]


def _vocab_role(vocab: str | None) -> str:
    if not vocab:
        return "internal"
    if is_observe(vocab):
        return "observe"
    if is_mutate(vocab):
        return "mutate"
    if is_bridge(vocab):
        return "bridge"
    return "internal"


def _compress_roles(roles: list[str]) -> str:
    compact: list[str] = []
    for role in roles:
        if not role or role == "internal":
            continue
        if not compact or compact[-1] != role:
            compact.append(role)
    return "->".join(compact) if compact else "internal"


def _skill_default_gap(skill: Any) -> str:
    trigger = getattr(skill, "trigger", "") or ""
    if isinstance(trigger, str) and trigger.startswith("on_vocab:"):
        return trigger.split(":", 1)[1]
    for step in getattr(skill, "steps", []) or []:
        vocab = getattr(step, "vocab", None)
        if vocab:
            return vocab
    return "internal_only"


def _skill_activation(skill: Any) -> str:
    trigger = getattr(skill, "trigger", "manual") or "manual"
    if isinstance(trigger, str) and trigger.startswith("on_vocab:"):
        return f"name:{trigger.split(':', 1)[1]}"
    if trigger == "manual":
        return "internal_only"
    return trigger


def _skill_omo_role(skill: Any) -> str:
    roles = [_vocab_role(getattr(step, "vocab", None)) for step in getattr(skill, "steps", []) or []]
    return _compress_roles(roles)


def _tool_doc_summary(path: Path) -> str:
    try:
        raw = path.read_text()
    except OSError:
        return ""
    try:
        module = ast.parse(raw)
    except SyntaxError:
        return ""
    return _first_line(ast.get_docstring(module) or "")


def _tool_blob_ref(path: Path, *, git: Any, cors_root: Path) -> str | None:
    try:
        rel = str(path.resolve().relative_to(cors_root))
    except ValueError:
        return None
    try:
        raw = git(["rev-parse", f"HEAD:{rel}"], None).strip().splitlines()
    except Exception:
        return None
    if not raw:
        return None
    return raw[0][:12]


def _tool_specs(*, cors_root: Path, tool_map: dict[str, dict], git: Any) -> list[FoundationSpec]:
    inverse_tool_map: dict[str, str] = {}
    for vocab, spec in sorted(tool_map.items()):
        tool = spec.get("tool")
        if isinstance(tool, str) and tool.startswith("tools/") and tool not in inverse_tool_map:
            inverse_tool_map[tool] = vocab

    specs: list[FoundationSpec] = []
    for rel in public_tool_paths(cors_root):
        path = cors_root / rel
        blob = _tool_blob_ref(path, git=git, cors_root=cors_root)
        if not blob:
            continue
        default_gap = inverse_tool_map.get(rel, "internal_only")
        activation = f"name:{default_gap}" if default_gap != "internal_only" else "internal_only"
        contract = load_tool_contract(path)
        desc = contract.desc if contract is not None else _tool_doc_summary(path)
        omo_role = _vocab_role(default_gap)
        if omo_role == "internal" and contract is not None:
            omo_role = contract.mode
        specs.append(
            FoundationSpec(
                ref=blob,
                kind="tool_blob",
                surface="described_blob",
                source=rel,
                desc=desc,
                activation=activation,
                default_gap=default_gap,
                omo_role=omo_role,
            )
        )
    return specs


def _chain_specs(*, chains_dir: Path) -> list[FoundationSpec]:
    specs: list[FoundationSpec] = []
    if not chains_dir.exists():
        return specs
    for path in sorted(chains_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        ref = str(doc.get("hash") or path.stem)
        trigger = doc.get("trigger", "manual")
        activation = "internal_only"
        default_gap = "internal_only"
        omo_role = "chain"
        if doc.get("version") == "stepchain.v1":
            nodes = [node for node in doc.get("nodes", []) if not (node or {}).get("terminal")]
            first_vocab = None
            roles: list[str] = []
            for node in nodes:
                manifestation = dict((node or {}).get("manifestation", {}) or {})
                vocab = manifestation.get("runtime_vocab") or next(iter((node or {}).get("allowed_vocab", []) or []), None)
                if first_vocab is None and vocab:
                    first_vocab = vocab
                roles.append(_vocab_role(vocab))
            if isinstance(trigger, str) and trigger.startswith("on_vocab:"):
                default_gap = trigger.split(":", 1)[1]
                activation = f"name:{default_gap}"
            elif first_vocab:
                default_gap = first_vocab
                activation = f"name:{first_vocab}"
            omo_role = _compress_roles(roles) if roles else "chain"
        elif "steps" in doc:
            first_vocab = None
            roles: list[str] = []
            for step in doc.get("steps", []) or []:
                gaps = list((step or {}).get("gaps", []) or [])
                vocab = next((gap.get("vocab") for gap in gaps if gap.get("vocab")), None)
                if first_vocab is None and vocab:
                    first_vocab = vocab
                roles.append(_vocab_role(vocab))
            if first_vocab:
                default_gap = first_vocab
                activation = f"name:{first_vocab}"
            omo_role = _compress_roles(roles) if roles else "chain"
        specs.append(
            FoundationSpec(
                ref=ref,
                kind="extracted_chain",
                surface="semantic_tree",
                source=str(path.relative_to(chains_dir.parent)),
                desc=_first_line(str(doc.get("desc", "") or "")),
                activation=activation,
                default_gap=default_gap,
                omo_role=omo_role,
            )
        )
    return specs


def foundation_from_chain_doc(doc: dict, *, ref: str, chains_dir: Path) -> FoundationSpec:
    for spec in _chain_specs(chains_dir=chains_dir):
        if spec.ref == ref:
            return spec
    return FoundationSpec(
        ref=ref,
        kind="extracted_chain",
        surface="semantic_tree",
        source=str(chains_dir / f"{ref}.json"),
        desc=_first_line(str(doc.get("desc", "") or "")),
        activation="internal_only",
        default_gap="internal_only",
        omo_role="chain",
    )


def _skill_specs(registry: Any, *, cors_root: Path) -> list[FoundationSpec]:
    specs: list[FoundationSpec] = []
    if registry is None:
        return specs
    for skill in sorted(registry.all_skills(), key=lambda s: (s.artifact_kind, s.name)):
        if getattr(skill, "artifact_kind", None) not in {"action", "codon"}:
            continue
        try:
            source = str(Path(skill.source).resolve().relative_to(cors_root))
        except ValueError:
            source = str(Path(skill.source))
        specs.append(
            FoundationSpec(
                ref=skill.hash,
                kind=f"{skill.artifact_kind}_package",
                surface="semantic_tree",
                source=source,
                desc=_first_line(getattr(skill, "desc", "")),
                activation=_skill_activation(skill),
                default_gap=_skill_default_gap(skill),
                omo_role=_skill_omo_role(skill),
            )
        )
    return specs


def foundation_from_skill(skill: Any, *, cors_root: Path) -> FoundationSpec:
    try:
        source = str(Path(skill.source).resolve().relative_to(cors_root))
    except ValueError:
        source = str(Path(skill.source))
    return FoundationSpec(
        ref=skill.hash,
        kind=f"{skill.artifact_kind}_package",
        surface="semantic_tree",
        source=source,
        desc=_first_line(getattr(skill, "desc", "")),
        activation=_skill_activation(skill),
        default_gap=_skill_default_gap(skill),
        omo_role=_skill_omo_role(skill),
    )


def list_action_foundations(*, registry: Any, chains_dir: Path, cors_root: Path, tool_map: dict[str, dict], git: Any) -> list[FoundationSpec]:
    specs = [
        *_skill_specs(registry, cors_root=cors_root),
        *_chain_specs(chains_dir=chains_dir),
        *_tool_specs(cors_root=cors_root, tool_map=tool_map, git=git),
    ]
    return sorted(specs, key=lambda spec: (spec.kind, spec.ref))


def resolve_action_foundation(
    ref: str,
    *,
    registry: Any,
    chains_dir: Path,
    cors_root: Path,
    tool_map: dict[str, dict],
    git: Any,
) -> FoundationSpec | None:
    for spec in list_action_foundations(
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map,
        git=git,
    ):
        if spec.ref == ref:
            return spec
    return None


def resolve_default_contract(
    ref: str,
    *,
    registry: Any,
    chains_dir: Path,
    cors_root: Path,
    tool_map: dict[str, dict],
    git: Any,
) -> dict[str, str] | None:
    spec = resolve_action_foundation(
        ref,
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map,
        git=git,
    )
    if spec is None:
        return None
    return {
        "ref": spec.ref,
        "kind": spec.kind,
        "surface": spec.surface,
        "activation": spec.activation,
        "default_gap": spec.default_gap,
        "omo_role": spec.omo_role,
    }


def resolve_trigger_owner(
    term: str,
    *,
    registry: Any,
    chains_dir: Path,
    cors_root: Path,
    tool_map: dict[str, dict],
    git: Any,
) -> FoundationSpec | None:
    matches = [
        spec for spec in list_action_foundations(
            registry=registry,
            chains_dir=chains_dir,
            cors_root=cors_root,
            tool_map=tool_map,
            git=git,
        )
        if spec.activation == f"name:{term}"
    ]
    if not matches:
        return None
    kind_rank = {
        "extracted_chain": 3,
        "action_package": 2,
        "codon_package": 1,
        "tool_blob": 0,
    }
    matches.sort(key=lambda spec: (kind_rank.get(spec.kind, -1), spec.ref), reverse=True)
    return matches[0]


def render_action_foundations(*, registry: Any, chains_dir: Path, cors_root: Path, tool_map: dict[str, dict], git: Any) -> str:
    lines = ["## Action Foundations"]
    lines.append("Hashes are the stable block identity. activation/default_gap are the canonical public contract. Hash embedding may specialize manifestation explicitly.")
    for spec in list_action_foundations(
        registry=registry,
        chains_dir=chains_dir,
        cors_root=cors_root,
        tool_map=tool_map,
        git=git,
    ):
        suffix = f" — {spec.desc}" if spec.desc else ""
        lines.append(
            f"  {spec.ref} kind={spec.kind} surface={spec.surface} omo={spec.omo_role} "
            f"activation={spec.activation} default_gap={spec.default_gap} source={spec.source}{suffix}"
        )
    return "\n".join(lines)
