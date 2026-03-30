#!/usr/bin/env python3
"""file_grep — regex grep across files.

Input JSON: {"pattern": "<regex>", "path": "<relative scope, default '.'>"}
Env: WORKSPACE — sandbox root.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

MAX_MATCHES = 100
MAX_FILE_SIZE = 500_000
SKIP_DIRS = {
    "node_modules", "__pycache__", "target", ".git", ".venv",
    "venv", ".tox", "dist", "build", ".mypy_cache", ".pytest_cache",
    "mem", "mem_admin", "data", "mem_seed",
}


def grep_file(path, regex, matches, workspace):
    if os.path.getsize(path) > MAX_FILE_SIZE:
        return
    try:
        with open(path) as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError):
        return

    ws = os.path.realpath(workspace)
    rel = os.path.relpath(path, ws)

    for i, line in enumerate(content.splitlines()):
        if len(matches) >= MAX_MATCHES * 2:
            break
        if regex.search(line):
            matches.append(f"{rel}:{i+1}: {line.strip()}")


def walk_grep(dir_path, regex, matches, workspace):
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        return
    for name in entries:
        if len(matches) >= MAX_MATCHES * 2:
            break
        if name.startswith(".") or name in SKIP_DIRS:
            continue
        full = os.path.join(dir_path, name)
        if os.path.isdir(full):
            walk_grep(full, regex, matches, workspace)
        elif os.path.isfile(full):
            grep_file(full, regex, matches, workspace)


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    pattern = params.get("pattern", "")
    path = params.get("path", ".")

    if not pattern:
        print("Error: missing 'pattern' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    search_root = sandbox_path(path, workspace)
    matches = []

    if os.path.isfile(search_root):
        grep_file(search_root, regex, matches, workspace)
    else:
        walk_grep(search_root, regex, matches, workspace)

    if not matches:
        print(f"No matches for '{pattern}' in {search_root}")
    else:
        total = len(matches)
        if total > MAX_MATCHES:
            matches = matches[:MAX_MATCHES]
            matches.append(f"... ({total} total matches, showing first {MAX_MATCHES})")
        print("\n".join(matches))


if __name__ == "__main__":
    main()
