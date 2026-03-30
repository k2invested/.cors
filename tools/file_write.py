#!/usr/bin/env python3
"""file_write — write content to a file.

Input JSON: {"path": "<relative path>", "content": "<file content>"}
Env: WORKSPACE — sandbox root.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    path = params.get("path")
    content = params.get("content", "")

    if not path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)

    resolved = sandbox_path(path, workspace)
    parent = os.path.dirname(resolved)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(resolved, "w") as f:
        f.write(content)

    print(f"Written {len(content)} chars to {resolved}\n\n---\n{content}")

if __name__ == "__main__":
    main()
