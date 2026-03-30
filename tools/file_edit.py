#!/usr/bin/env python3
"""file_edit — line-range replacement or full rewrite of a file.

Input JSON (edit mode):
  {"path": "<relative path>", "start_line": N, "end_line": M, "new_content": "<replacement text>"}
Input JSON (rewrite mode):
  {"path": "<relative path>", "op": "rewrite", "content": "<complete new file content>"}

Env: WORKSPACE — sandbox root.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    path = params.get("path")

    if not path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)

    # Rewrite mode — replace entire file content
    if params.get("op") == "rewrite":
        content = params.get("content")
        if content is None:
            print("Error: missing 'content' parameter for rewrite", file=sys.stderr)
            sys.exit(1)
        resolved = sandbox_path(path, workspace)
        with open(resolved, "w") as f:
            f.write(content)
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        print(f"Rewrote {path} — {line_count} lines")
        return

    # Edit mode — line-range replacement
    start_line = params.get("start_line")
    end_line = params.get("end_line")
    new_content = params.get("new_content")

    if start_line is None or end_line is None:
        print("Error: missing 'start_line' or 'end_line' parameter", file=sys.stderr)
        sys.exit(1)
    if new_content is None:
        print("Error: missing 'new_content' parameter", file=sys.stderr)
        sys.exit(1)

    start_line = int(start_line)
    end_line = int(end_line)

    if start_line < 1:
        print("Error: start_line must be >= 1", file=sys.stderr)
        sys.exit(1)
    if end_line < start_line:
        print("Error: end_line must be >= start_line", file=sys.stderr)
        sys.exit(1)

    resolved = sandbox_path(path, workspace)
    with open(resolved) as f:
        lines = f.readlines()

    if start_line > len(lines):
        print(f"Error: start_line {start_line} exceeds file length {len(lines)}", file=sys.stderr)
        sys.exit(1)
    if end_line > len(lines):
        end_line = len(lines)

    # Replace lines start_line..end_line (1-indexed, inclusive) with new_content
    before = lines[:start_line - 1]
    after = lines[end_line:]

    # Ensure new_content ends with newline if it doesn't
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"

    new_lines = new_content.splitlines(keepends=True) if new_content else []
    result = before + new_lines + after
    new_text = "".join(result)

    with open(resolved, "w") as f:
        f.write(new_text)

    replaced_count = end_line - start_line + 1
    print(f"Edited {resolved} — replaced lines {start_line}-{end_line} ({replaced_count} lines) with {len(new_lines)} lines\n\n---\n{new_text}")

if __name__ == "__main__":
    main()
