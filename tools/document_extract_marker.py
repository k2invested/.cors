#!/usr/bin/env python3
"""document_extract_marker — OCR/layout extraction for complex documents and images.

JSON stdin:
{
  "path": "<relative path>",
  "json": false,
  "output_dir": "<optional relative dir for extracted images>",
  "use_llm": false
}
"""

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
    / "ocr-and-documents"
    / "scripts"
    / "extract_marker.py"
)


def main() -> None:
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)

    try:
        resolved_path = sandbox_path(file_path, workspace)
        resolved_output = (
            sandbox_path(params["output_dir"], workspace)
            if params.get("output_dir")
            else None
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(SKILL_SCRIPT), resolved_path]
    if params.get("json"):
        cmd.append("--json")
    if resolved_output:
        cmd.extend(["--output_dir", resolved_output])
    if params.get("use_llm"):
        cmd.append("--use_llm")

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout or result.stderr or "(no output)"
    print(output.rstrip("\n"))
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
