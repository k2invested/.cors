"""Small dependency-free .env loader for local entrypoints."""

from __future__ import annotations

import os
from pathlib import Path


def default_env_paths(base_dir: str | Path | None = None) -> list[Path]:
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    candidates: list[Path] = [
        root / ".env",
        root.parent / "KernelAgent" / ".env",
        root.parent / ".env",
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def load_env(path: str | Path | None = None, *, override: bool = False) -> None:
    paths = [Path(path)] if path is not None else default_env_paths()
    for env_path in paths:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if override or key not in os.environ:
                os.environ[key] = value
