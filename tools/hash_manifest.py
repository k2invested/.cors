#!/usr/bin/env python3
"""hash_manifest — universal file I/O by hash reference.

Single tool for all file mutations. Read by hash, write, diff.
Every file mutation goes through here. Postcondition (hash_resolve_needed)
auto-fires on commit.

Input (stdin JSON):
{
  "action": "read | write | patch | diff",
  "path": "relative/file/path",
  "content": "full content (for write)",
  "patch": {"old": "...", "new": "..."} (for patch),
  "ref": "commit_sha" (for diff — diffs against this ref)
}
or a JSON array of those operation objects for ordered batch execution.

Output: file content, diff, or confirmation.
"""
TOOL_DESC = 'universal file I/O by hash reference.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'artifacts'


import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from system.hash_registry import HASH_MANIFEST_ROUTES

CORS_ROOT = str(ROOT)


def git(cmd: list[str]) -> str:
    result = subprocess.run(
        ["git"] + cmd, cwd=CORS_ROOT,
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def read_file(path: str) -> str:
    full = os.path.join(CORS_ROOT, path)
    if not os.path.exists(full):
        return f"(file not found: {path})"
    with open(full) as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    full = os.path.join(CORS_ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    return f"written: {path} ({len(content)} chars)"


def patch_file(path: str, old: str, new: str) -> str:
    full = os.path.join(CORS_ROOT, path)
    if not os.path.exists(full):
        return f"(file not found: {path})"
    with open(full) as f:
        content = f.read()
    if old not in content:
        return f"(patch target not found in {path})"
    content = content.replace(old, new, 1)
    with open(full, "w") as f:
        f.write(content)
    return f"patched: {path} ({len(old)} → {len(new)} chars)"


def diff_file(path: str, ref: str = "HEAD") -> str:
    return git(["diff", ref, "--", path])


def delegate_to_tool(tool_rel_path: str, params: dict) -> str:
    """Delegate to a specialised tool script."""
    tool_path = os.path.join(CORS_ROOT, tool_rel_path)
    if not os.path.exists(tool_path):
        return f"(tool not found: {tool_rel_path})"
    result = subprocess.run(
        ["python3", tool_path],
        input=json.dumps(params),
        capture_output=True, text=True,
        timeout=30, cwd=CORS_ROOT,
    )
    return (result.stdout or result.stderr or "(no output)").strip()


# File type → specialised tool for mutations
TOOL_ROUTES = dict(HASH_MANIFEST_ROUTES)


def route_by_type(path: str, params: dict) -> str | None:
    """Route mutation to specialised tool by file extension.
    Returns tool output, or None to use default handler."""
    ext = os.path.splitext(path)[1].lower()
    tool = TOOL_ROUTES.get(ext)
    if tool and os.path.exists(os.path.join(CORS_ROOT, tool)):
        return delegate_to_tool(tool, params)
    return None


def execute_operation(params: dict) -> str:
    action = params.get("action", "read")
    path = params.get("path", "")

    if not path:
        raise ValueError("missing 'path'")

    if action == "read":
        return read_file(path)
    if action == "write":
        # Route by file type first
        routed = route_by_type(path, params)
        if routed:
            return routed
        content = params.get("content", "")
        if not content:
            raise ValueError("missing 'content' for write")
        return write_file(path, content)
    if action == "patch":
        # Route by file type first
        routed = route_by_type(path, params)
        if routed:
            return routed
        patch = params.get("patch", {})
        old = patch.get("old", "")
        new = patch.get("new", "")
        if not old:
            raise ValueError("missing patch.old")
        return patch_file(path, old, new)
    if action == "diff":
        ref = params.get("ref", "HEAD")
        result = diff_file(path, ref)
        return result if result else "(no diff)"
    raise ValueError(f"unknown action '{action}'")


def main():
    try:
        params = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON — {e}")
        sys.exit(1)

    try:
        if isinstance(params, list):
            results: list[str] = []
            artifacts: list[str] = []
            for idx, item in enumerate(params):
                if not isinstance(item, dict):
                    raise ValueError(f"batch item {idx} must be an object")
                result = execute_operation(item)
                results.append(result)
                path = item.get("path", "")
                if isinstance(path, str) and path.strip():
                    artifacts.append(path.strip())
            print(json.dumps({"status": "ok", "artifacts": artifacts, "results": results}))
            return

        if not isinstance(params, dict):
            raise ValueError("top-level JSON must be an object or array of objects")
        print(execute_operation(params))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
