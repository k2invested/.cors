#!/usr/bin/env python3
"""pptx_add_slide — add or duplicate a slide in an unpacked PPTX tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path


SKILL_SCRIPT = (
    Path(__file__).resolve().parent
    / "skills"
    / "productivity"
    / "powerpoint"
    / "scripts"
    / "add_slide.py"
)


def main() -> None:
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    unpacked_dir = params.get("unpacked_dir", "")
    source = params.get("source", "")
    if not unpacked_dir or not source:
        print("Error: missing 'unpacked_dir' or 'source' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        resolved_dir = sandbox_path(unpacked_dir, workspace)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(SKILL_SCRIPT), resolved_dir, source],
        capture_output=True,
        text=True,
    )
    output = result.stdout or result.stderr or "(no output)"
    print(output.rstrip("\n"))
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
