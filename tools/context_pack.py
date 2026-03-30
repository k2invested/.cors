#!/usr/bin/env python3
"""context_pack — bundle multiple file excerpts into a single output.

Input JSON: {"items": [{"path": "<relative path>", "start": <optional int>, "end": <optional int>}], "max_chars": <optional int, default 32000>}
Env: WORKSPACE — sandbox root.

Each item produces a labeled header + file content (or line range).
Output is truncated to max_chars total.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

DEFAULT_MAX_CHARS = 32000
CHUNK_LINES = 300


def read_file_range(resolved_path, start, end):
    """Read lines [start, end] (1-indexed, inclusive) from resolved_path.
    If start/end are None, reads the whole file.
    Returns (content_str, total_lines).
    """
    with open(resolved_path) as f:
        lines = f.readlines()
    total = len(lines)

    if start is not None:
        s = max(start - 1, 0)
        e = end if end is not None else total
        e = min(e, total)
    else:
        s, e = 0, total

    selected = [f"{s + i + 1}: {lines[s + i].rstrip()}" for i in range(e - s)]
    return "\n".join(selected), total


def pack_item(item, workspace):
    """Resolve one item dict to a labeled block string.
    Returns a string like:
        ### path/to/file.py (lines 1-50 of 200)
        1: ...
        2: ...
    """
    path = item.get("path", "")
    if not path:
        return "### (missing path)\n(no content)"

    start = item.get("start", None)
    end = item.get("end", None)

    try:
        resolved = sandbox_path(path, workspace)
    except (ValueError, FileNotFoundError) as e:
        return f"### {path}\nError: {e}"

    if os.path.isdir(resolved):
        return f"### {path}\nError: path is a directory, not a file"

    try:
        content, total = read_file_range(resolved, start, end)
    except (UnicodeDecodeError, PermissionError) as e:
        return f"### {path}\nError: {e}"
    except OSError as e:
        return f"### {path}\nError: {e}"

    if start is not None:
        s_label = start
        e_label = end if end is not None else total
        header = f"### {path} (lines {s_label}-{min(e_label, total)} of {total})"
    else:
        header = f"### {path} ({total} lines)"

    return f"{header}\n{content}"


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    items = params.get("items", [])
    max_chars = params.get("max_chars", DEFAULT_MAX_CHARS)

    if not items:
        print("Error: missing 'items' parameter", file=sys.stderr)
        sys.exit(1)

    parts = []
    total_chars = 0
    truncated = False

    for item in items:
        block = pack_item(item, workspace)
        block_len = len(block)

        if total_chars + block_len > max_chars:
            remaining = max_chars - total_chars
            if remaining > 80:
                block = block[:remaining] + "\n... [truncated]"
                parts.append(block)
            truncated = True
            break

        parts.append(block)
        total_chars += block_len

    separator = "\n\n" + "-" * 60 + "\n\n"
    output = separator.join(parts)

    if truncated:
        output += f"\n\n[context_pack: truncated at {max_chars} chars — request fewer items or narrower line ranges]"

    print(output)


if __name__ == "__main__":
    main()
