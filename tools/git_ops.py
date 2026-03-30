#!/usr/bin/env python3
"""git_ops — version control operations on the project repository.

Input JSON:
  {"action": "log", "count": 15, "path": "<optional file filter>"}
  {"action": "diff", "ref": "<commit hash or ref>", "path": "<optional>"}
  {"action": "show", "ref": "<commit hash>"}
  {"action": "commit", "message": "<commit message>", "paths": ["<optional file paths>"]}
  {"action": "revert", "ref": "<commit hash>", "message": "<optional>"}
  {"action": "checkout", "ref": "<commit hash>", "path": "<required file path>"}

Operates on the project git repository (auto-detected from script location).
"""
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


def git_log(count=15, path=None):
    args = ["log", f"--oneline", f"-{count}"]
    if path:
        args += ["--", path]
    return _git(*args)


def git_diff(ref, path=None):
    args = ["diff", ref]
    if path:
        args += ["--", path]
    return _git(*args)


def git_show(ref):
    return _git("show", "--stat", ref)


def git_revert(ref, message=None):
    result = _git("revert", "--no-edit", ref)
    if result.startswith("Error:"):
        return result
    if message:
        _git("commit", "--amend", "-m", message)
    return f"Reverted {ref}\n{_git('log', '--oneline', '-1')}"


def git_commit(message, paths=None):
    if not message:
        return "Error: message is required for commit"
    if paths:
        for p in paths:
            _git("add", p)
    else:
        _git("add", "-A")
    result = _git("commit", "-m", message)
    if result.startswith("Error:"):
        return result
    return f"Committed\n{_git('log', '--oneline', '-1')}"


def git_checkout(ref, path):
    if not path:
        return "Error: path is required for checkout"
    result = _git("checkout", ref, "--", path)
    if result.startswith("Error:"):
        return result
    _git("add", path)
    commit_msg = f"Restore {path} from {ref[:8]}"
    _git("commit", "-m", commit_msg)
    return f"Restored {path} from {ref}\n{_git('log', '--oneline', '-1')}"


def main():
    params = json.load(sys.stdin)
    action = params.get("action", "log")

    if action == "log":
        print(git_log(params.get("count", 15), params.get("path")))
    elif action == "diff":
        print(git_diff(params.get("ref", "HEAD~1"), params.get("path")))
    elif action == "show":
        print(git_show(params.get("ref", "HEAD")))
    elif action == "revert":
        ref = params.get("ref")
        if not ref:
            print("Error: ref is required for revert", file=sys.stderr)
            sys.exit(1)
        print(git_revert(ref, params.get("message")))
    elif action == "commit":
        msg = params.get("message")
        if not msg:
            print("Error: message is required for commit", file=sys.stderr)
            sys.exit(1)
        print(git_commit(msg, params.get("paths")))
    elif action == "checkout":
        ref = params.get("ref")
        path = params.get("path")
        if not ref or not path:
            print("Error: ref and path are required for checkout", file=sys.stderr)
            sys.exit(1)
        print(git_checkout(ref, path))
    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
