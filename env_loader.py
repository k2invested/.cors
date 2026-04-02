from __future__ import annotations

import os
from pathlib import Path


def default_env_paths(base_dir: str | Path | None = None) -> list[Path]:
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    return [
        root / ".env",
        root.parent / "KernelAgent" / ".env",
        root.parent / ".env",
    ]


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_env(path: str | Path | None = None, *, override: bool = False) -> Path | None:
    paths = [Path(path)] if path is not None else default_env_paths()
    env_path = next((candidate for candidate in paths if candidate.exists()), None)
    if env_path is None:
        return None

    for raw_line in env_path.read_text().splitlines():
        parsed = _parse_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value
    return env_path
