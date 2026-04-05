#!/usr/bin/env python3
"""git_ops — mutating version control operations on the project repository.

Input JSON:
  {"action": "commit", "message": "<commit message>", "paths": ["<optional file paths>"]}
  {"action": "revert", "ref": "<commit hash>", "message": "<optional>"}
  {"action": "checkout", "ref": "<commit hash>", "path": "<required file path>"}

Operates on the project git repository (auto-detected from script location).
"""
TOOL_DESC = 'mutating git operations: commit, revert, and restore workspace state.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'artifacts'
TOOL_RUNTIME_ARTIFACT_KEY = 'commit'

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[3])


def _git(*args, timeout=30):
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        return f"Error: {result.stderr.strip()}"
    return result.stdout.strip()

def _head_sha() -> str:
    return _git("rev-parse", "HEAD")


def git_revert(ref, message=None):
    result = _git("revert", "--no-edit", ref)
    if result.startswith("Error:"):
        return {"status": "error", "error": result}
    if message:
        _git("commit", "--amend", "-m", message)
    return {
        "status": "ok",
        "action": "revert",
        "target": ref,
        "commit": _head_sha(),
        "summary": _git("log", "--oneline", "-1"),
    }


def git_commit(message, paths=None):
    if not message:
        return {"status": "error", "error": "message is required for commit"}
    if paths:
        for p in paths:
            _git("add", p)
    else:
        _git("add", "-A")
    result = _git("commit", "-m", message)
    if result.startswith("Error:"):
        return {"status": "error", "error": result}
    return {
        "status": "ok",
        "action": "commit",
        "commit": _head_sha(),
        "summary": _git("log", "--oneline", "-1"),
    }


def git_checkout(ref, path):
    if not path:
        return {"status": "error", "error": "path is required for checkout"}
    result = _git("checkout", ref, "--", path)
    if result.startswith("Error:"):
        return {"status": "error", "error": result}
    _git("add", path)
    commit_msg = f"Restore {path} from {ref[:8]}"
    _git("commit", "-m", commit_msg)
    return {
        "status": "ok",
        "action": "checkout",
        "path": path,
        "target": ref,
        "commit": _head_sha(),
        "summary": _git("log", "--oneline", "-1"),
    }


def main():
    params = json.load(sys.stdin)
    action = params.get("action", "revert")

    if action == "revert":
        ref = params.get("ref")
        if not ref:
            print("Error: ref is required for revert", file=sys.stderr)
            sys.exit(1)
        result = git_revert(ref, params.get("message"))
    elif action == "commit":
        msg = params.get("message")
        if not msg:
            print("Error: message is required for commit", file=sys.stderr)
            sys.exit(1)
        result = git_commit(msg, params.get("paths"))
    elif action == "checkout":
        ref = params.get("ref")
        path = params.get("path")
        if not ref or not path:
            print("Error: ref and path are required for checkout", file=sys.stderr)
            sys.exit(1)
        result = git_checkout(ref, path)
    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))
    if result.get("status") != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
