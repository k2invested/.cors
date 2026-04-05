#!/usr/bin/env python3
"""pdf_extract_pymupdf — rich PDF extraction via the imported pymupdf helper.

JSON stdin:
{
  "path": "<relative path>",
  "markdown": false,
  "tables": false,
  "images": "<optional relative output dir>",
  "metadata": false,
  "pages": "0-4"
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
    / "extract_pymupdf.py"
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
        resolved_images = (
            sandbox_path(params["images"], workspace)
            if params.get("images")
            else None
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(SKILL_SCRIPT), resolved_path]
    if params.get("pages"):
        cmd.extend(["--pages", str(params["pages"])])
    if params.get("metadata"):
        cmd.append("--metadata")
    elif params.get("tables"):
        cmd.append("--tables")
    elif resolved_images:
        cmd.extend(["--images", resolved_images])
    elif params.get("markdown"):
        cmd.append("--markdown")

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout or result.stderr or "(no output)"
    print(output.rstrip("\n"))
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
