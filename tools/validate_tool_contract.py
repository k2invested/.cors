#!/usr/bin/env python3
"""validate_tool_contract — validate required tool contract fields."""
from __future__ import annotations
TOOL_DESC = 'validate required tool contract fields.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'none'

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path
from tool_contract import validate_tool_file


def main() -> None:
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    file_path = params.get("path", "")
    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)
    try:
        resolved = sandbox_path(file_path, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    errors = validate_tool_file(resolved)
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {file_path} — tool contract valid")


if __name__ == "__main__":
    main()
