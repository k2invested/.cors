"""chain_registry — public first-class action chain surface.

This registry derives chain contracts directly from `skills/actions/*.st`.
Each chain is identified by a blob hash and exposes a compact deterministic
selection surface for higher-order composition.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from system.tool_registry import _working_tree_blob, public_tool_blob_refs
from vocab_registry import TOOL_MAP, is_bridge, is_mutate, is_observe


@dataclass(frozen=True)
class ChainContract:
    ref: str
    source: str
    name: str
    desc: str
    trigger: str
    activation: str
    default_gap: str
    entry_vocab: str | None
    step_count: int
    omo_shape: str
    vocab_sequence: tuple[str, ...]
    tool_paths: tuple[str, ...]
    tool_blob_refs: tuple[str, ...]


def _chains_root(cors_root: Path) -> Path:
    return cors_root / "skills" / "actions"


def public_chain_paths(cors_root: Path) -> tuple[str, ...]:
    root = _chains_root(cors_root)
    paths = [str(path.relative_to(cors_root)) for path in sorted(root.glob("*.st"))]
    return tuple(paths)


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


def _blob_ref(path: str, *, cors_root: Path) -> str | None:
    return _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)


def _load_chain_doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _vocab_role(vocab: str | None) -> str:
    if not vocab:
        return "bridge"
    if is_observe(vocab):
        return "observe"
    if is_mutate(vocab):
        return "mutate"
    if is_bridge(vocab):
        return "bridge"
    return "bridge"


def _compress_roles(roles: list[str]) -> str:
    compact: list[str] = []
    for role in roles:
        if not compact or compact[-1] != role:
            compact.append(role)
    return "->".join(compact) if compact else "bridge"


def _activation(trigger: str, entry_vocab: str | None) -> str:
    if trigger.startswith("on_vocab:"):
        return f"name:{trigger.split(':', 1)[1]}"
    if trigger == "manual":
        return f"name:{entry_vocab}" if entry_vocab else "internal_only"
    return trigger


def _default_gap(trigger: str, entry_vocab: str | None) -> str:
    if trigger.startswith("on_vocab:"):
        return trigger.split(":", 1)[1]
    return entry_vocab or "internal_only"


def _tool_paths_from_vocabs(vocabs: list[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for vocab in vocabs:
        tool = (TOOL_MAP.get(vocab) or {}).get("tool")
        if isinstance(tool, str) and tool not in seen:
            seen.append(tool)
    return tuple(seen)


def list_public_chain_contracts(cors_root: Path) -> tuple[ChainContract, ...]:
    tool_blobs = public_tool_blob_refs(cors_root)
    contracts: list[ChainContract] = []
    for rel in public_chain_paths(cors_root):
        ref = _blob_ref(rel, cors_root=cors_root)
        if not ref:
            continue
        doc = _load_chain_doc(cors_root / rel)
        steps = list(doc.get("steps", []) or [])
        vocab_sequence = tuple(step.get("vocab") for step in steps if step.get("vocab"))
        entry_vocab = next((step.get("vocab") for step in steps if step.get("vocab")), None)
        trigger = str(doc.get("trigger", "manual") or "manual")
        tool_paths = _tool_paths_from_vocabs(list(vocab_sequence))
        tool_blob_list: list[str] = []
        for path in tool_paths:
            blob = _blob_ref(path, cors_root=cors_root)
            if blob and blob in tool_blobs and blob not in tool_blob_list:
                tool_blob_list.append(blob)
        contracts.append(
            ChainContract(
                ref=ref,
                source=rel,
                name=str(doc.get("name", Path(rel).stem)),
                desc=str(doc.get("desc", "")),
                trigger=trigger,
                activation=_activation(trigger, entry_vocab),
                default_gap=_default_gap(trigger, entry_vocab),
                entry_vocab=entry_vocab,
                step_count=len(steps),
                omo_shape=_compress_roles([_vocab_role(step.get("vocab")) for step in steps]),
                vocab_sequence=vocab_sequence,
                tool_paths=tool_paths,
                tool_blob_refs=tuple(tool_blob_list),
            )
        )
    return tuple(sorted(contracts, key=lambda c: (c.name, c.ref)))


def public_chain_blob_refs(cors_root: Path) -> set[str]:
    return {contract.ref for contract in list_public_chain_contracts(cors_root)}


def public_chain_ref_map(cors_root: Path) -> dict[str, str]:
    return {contract.ref: contract.source for contract in list_public_chain_contracts(cors_root)}


def render_public_chain_registry(cors_root: Path) -> str:
    lines = ["## Public Chain Registry"]
    for contract in list_public_chain_contracts(cors_root):
        tools = ",".join(contract.tool_paths) if contract.tool_paths else "none"
        lines.append(
            f"- {contract.source} | ref={contract.ref} | activation={contract.activation} "
            f"| default_gap={contract.default_gap} | steps={contract.step_count} "
            f"| omo={contract.omo_shape} | tools={tools} | {contract.desc}"
        )
    return "\n".join(lines)


PUBLIC_CHAIN_PATHS = public_chain_paths(Path(__file__).resolve().parent.parent)
