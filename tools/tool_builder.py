#!/usr/bin/env python3
"""tool_builder — write validated tool script scaffolds for tool_needed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from string import Template

sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import sandbox_path
from tool_contract import validate_tool_file


def _render_stub(
    *,
    name: str,
    desc: str,
    mode: str,
    scope: str,
    post_observe: str,
    default_artifacts: list[str],
    runtime_artifacts: bool,
) -> str:
    artifact_lines: list[str] = []
    if default_artifacts:
        artifact_lines.append(f"TOOL_DEFAULT_ARTIFACTS = {default_artifacts!r}")
    if runtime_artifacts:
        artifact_lines.append("TOOL_RUNTIME_ARTIFACTS = True")
    artifact_block = "\n".join(artifact_lines)
    if artifact_block:
        artifact_block += "\n"
    template = Template('''#!/usr/bin/env python3
"""$name — $desc"""

import json
import os
import sys

TOOL_DESC = "$desc"
TOOL_MODE = "$mode"
TOOL_SCOPE = "$scope"
TOOL_POST_OBSERVE = "$post_observe"
$artifact_block

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    print({"status": "todo", "tool": "$name", "workspace": workspace, "params": params})


if __name__ == "__main__":
    main()
''')
    return template.substitute(
        name=name,
        desc=desc,
        mode=mode,
        scope=scope,
        post_observe=post_observe,
        artifact_block=artifact_block.rstrip(),
    ) + "\n"


def main() -> None:
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")

    file_path = params.get("path", "")
    desc = params.get("desc", "")
    mode = params.get("mode", "")
    scope = params.get("scope", "")
    post_observe = params.get("post_observe", "")
    default_artifacts = list(params.get("default_artifacts", []) or [])
    runtime_artifacts = bool(params.get("runtime_artifacts", False))
    overwrite = bool(params.get("overwrite", False))

    if not file_path:
        print("Error: missing 'path' parameter", file=sys.stderr)
        sys.exit(1)
    if not desc:
        print("Error: missing 'desc' parameter", file=sys.stderr)
        sys.exit(1)

    candidate = Path(workspace) / file_path if not os.path.isabs(file_path) else Path(file_path)
    candidate.parent.mkdir(parents=True, exist_ok=True)

    try:
        resolved = Path(sandbox_path(file_path, workspace))
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if resolved.exists() and not overwrite:
        print(f"Error: tool already exists: {file_path}", file=sys.stderr)
        sys.exit(1)

    resolved.parent.mkdir(parents=True, exist_ok=True)
    content = _render_stub(
        name=resolved.stem,
        desc=desc,
        mode=mode,
        scope=scope,
        post_observe=post_observe,
        default_artifacts=default_artifacts,
        runtime_artifacts=runtime_artifacts,
    )
    resolved.write_text(content, encoding="utf-8")
    errors = validate_tool_file(resolved)
    if errors:
        resolved.unlink(missing_ok=True)
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"written: {file_path}")


if __name__ == "__main__":
    main()
