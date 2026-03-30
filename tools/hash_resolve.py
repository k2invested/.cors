#!/usr/bin/env python3
"""hash_resolve — resolve blob hashes from trajectory.

Reads hashes from params, resolves them against self.json trajectory,
and returns the full step data for each hash found.

Input (stdin JSON):
  {"hashes": ["abc123", "def456"], "depth": 1}

Output (stdout):
  Resolved steps with their content, refs, and metadata.
"""

import json
import os
import sys


def main():
    params = json.load(sys.stdin)
    hashes = params.get("hashes", [])
    depth = params.get("depth", 1)

    if not hashes:
        print("No hashes provided")
        return

    # Load trajectory from self.json
    self_path = os.environ.get("SELF_JSON_PATH", "")
    if not self_path or not os.path.exists(self_path):
        print(f"Trajectory not found at {self_path}")
        return

    trajectory = json.load(open(self_path))

    # Build hash index
    hash_index = {}
    for atom in trajectory:
        bh = atom.get("_blob_hash", "")
        if bh:
            hash_index[bh] = atom

    # Resolve requested hashes
    resolved = []
    seen = set()

    def resolve(h, current_depth):
        if h in seen or current_depth > depth:
            return
        seen.add(h)

        atom = hash_index.get(h)
        if not atom:
            resolved.append(f"[{h}] (not found in trajectory)")
            return

        # Format the resolved step
        role = atom.get("_role", "step")
        assess = atom.get("assessment", "")
        content = atom.get("content", "")
        if isinstance(content, dict):
            content = content.get("content", "")
        commit = atom.get("_commit", "")
        refs = atom.get("_refs", [])
        tool = atom.get("_tool", "")

        lines = [f"[{h}] ({role})"]
        if tool:
            lines.append(f"  tool: {tool}")
        if commit:
            lines.append(f"  commit: {commit}")
        if assess:
            lines.append(f"  assessment: {assess[:300]}")
        if content:
            content_str = str(content)[:500]
            lines.append(f"  content: {content_str}")
        if refs:
            lines.append(f"  refs: {refs}")

        resolved.append("\n".join(lines))

        # Follow refs if depth allows
        if current_depth < depth:
            for ref in refs:
                resolve(ref, current_depth + 1)

    for h in hashes:
        resolve(h, 0)

    if resolved:
        print("\n\n".join(resolved))
    else:
        print("No matching hashes found in trajectory")


if __name__ == "__main__":
    main()
