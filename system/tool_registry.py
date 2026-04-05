"""tool_registry — public first-class tool surface.

Hash internals remain implementation detail. Only the two hash primitives are
publicly exposed as tools; the routed handlers behind them are not.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from system.hash_registry import HASH_CORE_TOOLS, HASH_SUPPORT_TOOLS
from system.tool_contract import load_tool_contract, render_artifact_contract

_HELPER_EXCLUDES: set[str] = set()
_SYSTEM_EXCLUDES: set[str] = {
    "system/tool_registry.py",
    "system/chain_registry.py",
    "system/tool_contract.py",
    "system/hash_registry.py",
    "system/tool_builder.py",
    "system/vocab_builder.py",
    "system/validate_tool_contract.py",
    "system/gap_config_report.py",
    "system/security_compile.py",
    "system/semantic_skeleton_compile.py",
    "system/skeleton_compile.py",
    "system/trace_tree_build.py",
}

INTERNAL_TOOL_PATHS = tuple(sorted(set(HASH_SUPPORT_TOOLS) | _HELPER_EXCLUDES | _SYSTEM_EXCLUDES))


@dataclass(frozen=True)
class PublicToolContract:
    ref: str
    source: str
    desc: str
    mode: str
    scope: str
    post_observe: str
    artifacts: str


def _tool_root(cors_root: Path) -> Path:
    return cors_root / "tools"


def public_tool_paths(cors_root: Path) -> tuple[str, ...]:
    paths = []
    for path in sorted(_tool_root(cors_root).glob("*.py")):
        rel = f"tools/{path.name}"
        if rel in INTERNAL_TOOL_PATHS:
            continue
        paths.append(rel)
    return tuple(paths)


def is_public_tool_path(path: str, *, cors_root: Path) -> bool:
    return path in public_tool_paths(cors_root)


def _git_head_blob(path: str, *, cors_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=cors_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    line = result.stdout.strip().splitlines()
    return line[0][:12] if line else None


def _working_tree_blob(path: str, *, cors_root: Path) -> str | None:
    full_path = cors_root / path
    if not full_path.exists():
        return None
    result = subprocess.run(
        ["git", "hash-object", path],
        cwd=cors_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    line = result.stdout.strip().splitlines()
    return line[0][:12] if line else None


def public_tool_blob_refs(cors_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in public_tool_paths(cors_root):
        blob = _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)
        if blob:
            refs.add(blob)
    return refs


def public_tool_ref_map(cors_root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in public_tool_paths(cors_root):
        blob = _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)
        if blob:
            mapping[blob] = path
    return mapping


def public_tool_path_to_ref_map(cors_root: Path) -> dict[str, str]:
    return {path: ref for ref, path in public_tool_ref_map(cors_root).items()}


def internal_tool_blob_refs(cors_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in INTERNAL_TOOL_PATHS:
        blob = _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)
        if blob:
            refs.add(blob)
    return refs


def list_public_tool_contracts(cors_root: Path) -> tuple[PublicToolContract, ...]:
    contracts: list[PublicToolContract] = []
    for path in public_tool_paths(cors_root):
        ref = _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)
        if not ref:
            continue
        contract = load_tool_contract(cors_root / path)
        if contract is None:
            continue
        contracts.append(
            PublicToolContract(
                ref=ref,
                source=path,
                desc=contract.desc,
                mode=contract.mode,
                scope=contract.scope,
                post_observe=contract.post_observe,
                artifacts=render_artifact_contract(contract),
            )
        )
    return tuple(sorted(contracts, key=lambda c: (c.source, c.ref)))


def render_public_tool_registry(cors_root: Path) -> str:
    lines = ["## Public Tool Registry"]
    for contract in list_public_tool_contracts(cors_root):
        lines.append(
            f"- {contract.source} | ref={contract.ref} | {contract.mode}/{contract.scope} "
            f"| post_observe={contract.post_observe} | artifacts={contract.artifacts} | {contract.desc}"
        )
    return "\n".join(lines)


PUBLIC_TOOL_PATHS = public_tool_paths(Path(__file__).resolve().parent.parent)
