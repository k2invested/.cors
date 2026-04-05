#!/usr/bin/env python3
"""office_manifest — mutate Office packages through unpack/edit/repack.

Supports package-style mutation for existing .pptx and .xlsx files.
The primary operation is a single text patch applied across unpacked XML/rels
files, followed by repacking into the original package path.

Input JSON:
{
  "action": "patch | write",
  "path": "<relative package path>",
  "patch": {"old": "...", "new": "..."},
  "source_dir": "<relative unpacked dir for write>"
}
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

TEXTUAL_SUFFIXES = {".xml", ".rels", ".txt", ".html", ".htm"}
SUPPORTED_SUFFIXES = {".pptx", ".xlsx"}


def _iter_textual_files(unpacked_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in unpacked_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXTUAL_SUFFIXES:
            files.append(path)
    return sorted(files)


def _replace_once_in_tree(unpacked_dir: Path, old: str, new: str) -> tuple[int, str | None]:
    touched = 0
    first_rel_path: str | None = None
    for file_path in _iter_textual_files(unpacked_dir):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if old not in content:
            continue
        file_path.write_text(content.replace(old, new, 1), encoding="utf-8")
        touched += 1
        if first_rel_path is None:
            first_rel_path = str(file_path.relative_to(unpacked_dir))
        break
    return touched, first_rel_path


def patch_package(path: str, old: str, new: str) -> str:
    package_path = Path(path)
    suffix = package_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return f"Error: unsupported format '{suffix}'. Supported: {sorted(SUPPORTED_SUFFIXES)}"
    if not package_path.is_file():
        return f"Error: '{package_path}' is not a file"
    if not old:
        return "Error: missing patch.old"

    with tempfile.TemporaryDirectory(prefix="office_manifest_") as temp_dir:
        unpacked_dir = Path(temp_dir) / "unpacked"
        unpacked_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                zf.extractall(unpacked_dir)
        except zipfile.BadZipFile:
            return f"Error: {package_path.name} is not a valid Office package"

        touched, first_rel_path = _replace_once_in_tree(unpacked_dir, old, new)
        if touched == 0:
            return f"Error: patch target not found in {package_path.name}"

        try:
            with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(unpacked_dir.rglob("*")):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(unpacked_dir))
        except Exception as e:
            return f"Error: failed to repack {package_path.name}: {e}"
        first_display = first_rel_path or "(unknown)"
        return f"ok: {package_path.name} — patched package XML in {first_display}"


def write_package(path: str, source_dir: str) -> str:
    package_path = Path(path)
    suffix = package_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return f"Error: unsupported format '{suffix}'. Supported: {sorted(SUPPORTED_SUFFIXES)}"
    source_path = Path(source_dir)
    if not source_path.is_dir():
        return f"Error: '{source_path}' is not a directory"
    try:
        package_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(source_path.rglob("*")):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(source_path))
    except Exception as e:
        return f"Error: failed to pack {package_path.name}: {e}"
    return f"ok: {package_path.name} — packed from {source_path.name}"


def main() -> None:
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    action = params.get("action", "patch")

    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        resolved_path = sandbox_path(file_path, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if action == "patch":
        patch = params.get("patch", {})
        old = patch.get("old", "")
        new = patch.get("new", "")
        message = patch_package(resolved_path, old, new)
    elif action == "write":
        source_dir = params.get("source_dir", "")
        if not source_dir:
            print(
                "Error: office_manifest write requires 'source_dir' for an unpacked package",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            resolved_source_dir = sandbox_path(source_dir, workspace)
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        message = write_package(resolved_path, resolved_source_dir)
    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)

    print(message)
    if message.startswith("Error:"):
        sys.exit(1)


if __name__ == "__main__":
    main()
