#!/usr/bin/env python3
"""file_read — read a file or directory listing.

Input JSON: {"path": "<relative path or path:start-end>"}
Env: WORKSPACE — sandbox root.
"""
import json, os, sys

# Reuse scan_tree's file_read (same logic)
sys.path.insert(0, os.path.dirname(__file__))
from scan_tree import file_read, sandbox_path

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    path = params.get("path", ".")
    print(file_read(path, workspace))

if __name__ == "__main__":
    main()
