"""tool_registry — public first-class tool surface.

Hash internals remain implementation detail. Only the two hash primitives are
publicly exposed as tools; the routed handlers behind them are not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.hash.registry import HASH_CORE_TOOLS, HASH_SUPPORT_TOOLS

_HELPER_EXCLUDES = {
    "tools/hash/registry.py",
    "tools/tool_contract.py",
    "tools/tool_registry.py",
    "tools/gap_config_report.py",
}

INTERNAL_TOOL_PATHS = tuple(sorted(set(HASH_SUPPORT_TOOLS) | _HELPER_EXCLUDES))


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


def internal_tool_blob_refs(cors_root: Path) -> set[str]:
    refs: set[str] = set()
    for path in INTERNAL_TOOL_PATHS:
        blob = _git_head_blob(path, cors_root=cors_root) or _working_tree_blob(path, cors_root=cors_root)
        if blob:
            refs.add(blob)
    return refs


PUBLIC_TOOL_PATHS = public_tool_paths(Path(__file__).resolve().parent.parent)
