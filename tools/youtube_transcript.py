#!/usr/bin/env python3
"""youtube_transcript — fetch a YouTube transcript through the imported helper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SKILL_SCRIPT = (
    Path(__file__).resolve().parent
    / "skills"
    / "media"
    / "youtube-content"
    / "scripts"
    / "fetch_transcript.py"
)


def main() -> None:
    params = json.load(sys.stdin)
    url = params.get("url") or params.get("video_id") or ""
    if not url:
        print("Error: missing 'url' or 'video_id' parameter", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(SKILL_SCRIPT), str(url)]
    language = params.get("language")
    if isinstance(language, list) and language:
        cmd.extend(["--language", ",".join(str(item) for item in language)])
    elif isinstance(language, str) and language.strip():
        cmd.extend(["--language", language.strip()])
    if params.get("timestamps"):
        cmd.append("--timestamps")
    if params.get("text_only"):
        cmd.append("--text-only")

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout or result.stderr or "(no output)"
    print(output.rstrip("\n"))
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
