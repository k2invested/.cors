#!/usr/bin/env python3
"""scan_tree — scan directory tree (listing only) or read a single file.

Input JSON: {"path": "<relative path, default '.'>"}
Env: WORKSPACE — sandbox root.

Directory path → recursive listing (no file contents).
File path → full file read (chunked if large).
"""
import json, os, sys

MAX_RESULT_CHARS = 32000
SKIP_DIRS = {
    "node_modules", "__pycache__", "target", ".git", ".venv",
    "venv", ".tox", "dist", "build", ".mypy_cache", ".pytest_cache",
}
CHUNK_LINES = 300


def sandbox_path(path, workspace):
    ws = os.path.realpath(workspace)
    p = os.path.join(workspace, path) if not os.path.isabs(path) else path
    rp = os.path.realpath(p) if os.path.exists(p) else None
    if rp and not rp.startswith(ws):
        raise ValueError(f"path {rp} is outside workspace {ws}")
    if not rp:
        parent = os.path.dirname(p)
        if os.path.exists(parent):
            rp_parent = os.path.realpath(parent)
            if not rp_parent.startswith(ws):
                raise ValueError("path is outside workspace")
            return os.path.join(rp_parent, os.path.basename(p))
        raise FileNotFoundError(f"path {p} does not exist")
    return rp


def parse_path_range(path):
    if ':' in path:
        colon = path.rfind(':')
        file_part = path[:colon]
        range_part = path[colon+1:]
        if '-' in range_part:
            dash = range_part.index('-')
            try:
                start = int(range_part[:dash])
            except ValueError:
                return path, None, None
            end_str = range_part[dash+1:]
            end = int(end_str) if end_str else None
            return file_part, start, end
    return path, None, None


def file_read(path, workspace):
    file_path, start, end = parse_path_range(path)
    resolved = sandbox_path(file_path, workspace)

    if os.path.isdir(resolved):
        return read_directory(resolved, workspace)

    with open(resolved) as f:
        lines = f.readlines()
    total = len(lines)

    if start is not None:
        s = max(start - 1, 0)
        e = end if end else total
        e = min(e, total)
    else:
        s, e = 0, total

    selected = [f"{s + i + 1}: {lines[s + i].rstrip()}" for i in range(e - s)]
    result = "\n".join(selected)

    if len(result) > MAX_RESULT_CHARS:
        result = result[:MAX_RESULT_CHARS]
        result += f"\n... [truncated at {MAX_RESULT_CHARS} chars, file has {total} lines, showing lines {s+1}-{e}]"
    return result


def read_directory(path, workspace):
    ws = os.path.realpath(workspace)
    rel = os.path.relpath(path, ws)
    entries = []
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.isdir(full):
            if name.startswith(".") or name in SKIP_DIRS:
                continue
            entries.append(f"  {name}/ (directory)")
        else:
            size = os.path.getsize(full)
            try:
                with open(full) as f:
                    lc = sum(1 for _ in f)
                entries.append(f"  {name} ({lc} lines, {size} bytes)")
            except (UnicodeDecodeError, PermissionError):
                entries.append(f"  {name} ({size} bytes, binary)")
    return f"Directory: {rel if rel != '.' else '.'}\n" + "\n".join(entries)


def scan_tree(root, workspace, max_depth=3):
    """Recursive directory listing only — no file contents."""
    output_parts = []
    _scan_recursive(root, workspace, max_depth, output_parts)
    return "\n\n".join(output_parts)


def _scan_recursive(path, workspace, depth, output_parts):
    listing = read_directory(sandbox_path(path, workspace), workspace)
    output_parts.append(listing)

    for line in listing.split("\n"):
        line = line.strip()
        if not line or line.startswith("Directory:"):
            continue
        if line.endswith("(directory)"):
            name = line.rstrip("(directory)").strip().rstrip("/")
            if name.startswith(".") or name in SKIP_DIRS:
                continue
            if depth > 0:
                child = name if path == "." else f"{path}/{name}"
                _scan_recursive(child, workspace, depth - 1, output_parts)


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    path = params.get("path", ".")

    resolved = sandbox_path(path, workspace)

    # File path → read the file (chunked if large)
    if os.path.isfile(resolved):
        with open(resolved) as f:
            lc = sum(1 for _ in f)
        if lc <= CHUNK_LINES:
            print(file_read(path, workspace))
        else:
            parts = []
            start = 1
            while start <= lc:
                end = min(start + CHUNK_LINES - 1, lc)
                range_path = f"{path}:{start}-{end}"
                try:
                    content = file_read(range_path, workspace)
                    parts.append(f"--- {range_path} ---\n{content}")
                except Exception as e:
                    parts.append(f"--- {range_path} ---\nError: {e}")
                start = end + 1
            print("\n\n".join(parts))
        return

    # Directory path → listing only (no batch reads)
    print(scan_tree(path, workspace))


if __name__ == "__main__":
    main()
