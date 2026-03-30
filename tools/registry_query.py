#!/usr/bin/env python3
"""registry_query.py — Read-only query against the unified registry.

Lists and searches commitments, profiles, and tasks from registry.json.
Deterministic — no LLM parameterization needed.

Input (JSON on stdin):
  {
    "type": "<optional: commitment|profile|task|all>",
    "status": "<optional filter>",
    "contact_id": "<optional filter>",
    "project": "<optional filter>",
    "query": "<optional text search>"
  }

Output (stdout): human-readable formatted records.

Env: REGISTRY_PATH — path to shared registry.json.
"""

import json
import os
import sys
from pathlib import Path

_env_path = os.environ.get("REGISTRY_PATH", "")
STORE_FILE = Path(_env_path) if _env_path else Path(__file__).resolve().parent / "tasks.json"


def load_store():
    if not STORE_FILE.exists():
        return []
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def format_commitment(r):
    line = f"[{r.get('status', '?')}] {r.get('commitment_id', '?')}: {r.get('title', '')}"
    if r.get("due_at"):
        line += f" — due {r['due_at']}"
    if r.get("project"):
        line += f" — project: {r['project']}"
    if r.get("participants"):
        line += f" — {', '.join(r['participants'])}"
    reqs = r.get("requirements", [])
    if reqs:
        for i, req in enumerate(reqs):
            line += f"\n  req {i+1}: {req}"
    return line


def format_profile(r):
    fields = {k: v for k, v in r.items() if not k.startswith("_") and k != "contact_id"}
    field_str = ", ".join(f"{k}={v}" for k, v in fields.items()) if fields else "(empty)"
    return f"Profile {r.get('contact_id', '?')}: {field_str}"


def format_task(r):
    line = f"[{r.get('status', '?')}] {r.get('task_id', '?')}: {r.get('title', '')}"
    if r.get("contributors"):
        line += f" — {', '.join(r['contributors'])}"
    return line


def format_record(r):
    rtype = r.get("_type", "unknown")
    if rtype == "commitment":
        return format_commitment(r)
    elif rtype == "profile":
        return format_profile(r)
    elif rtype == "task":
        return format_task(r)
    else:
        return f"[{rtype}] {json.dumps(r, default=str)[:200]}"


def main():
    raw = sys.stdin.read().strip()
    params = json.loads(raw) if raw else {}

    store = load_store()
    if not store:
        print("Registry is empty — no commitments, profiles, or tasks.")
        return

    # Filters
    type_filter = str(params.get("type", "")).strip().lower()
    status_filter = str(params.get("status", "")).strip()
    contact_filter = str(params.get("contact_id", "")).strip()
    project_filter = str(params.get("project", "")).strip().lower()
    query = str(params.get("query", "")).strip().lower()
    query_terms = query.split() if query else []

    filtered = []
    for r in store:
        if not isinstance(r, dict):
            continue
        rtype = r.get("_type", "")
        if type_filter and type_filter != "all" and rtype != type_filter:
            continue
        if status_filter and r.get("status", "") != status_filter:
            continue
        if contact_filter:
            participants = r.get("participants", [])
            cid = r.get("contact_id", "")
            contributors = r.get("contributors", [])
            if contact_filter not in participants and contact_filter != cid and contact_filter not in contributors:
                continue
        if project_filter and project_filter != str(r.get("project", "")).lower():
            continue
        if query_terms:
            text = json.dumps(r, default=str).lower()
            if not all(t in text for t in query_terms):
                continue
        filtered.append(r)

    if not filtered:
        print("No matching records found.")
        return

    # Group by type
    by_type = {}
    for r in filtered:
        rtype = r.get("_type", "other")
        by_type.setdefault(rtype, []).append(r)

    lines = [f"{len(filtered)} record(s) in registry:"]
    for rtype, records in by_type.items():
        lines.append(f"\n## {rtype.title()}s ({len(records)})")
        for r in records:
            lines.append(f"  {format_record(r)}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
