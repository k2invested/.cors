#!/usr/bin/env python3
"""principles — CRUD for the admin dev agent's architectural knowledge store.

Same pattern as commitments.py but for system design principles.

Input JSON:
  {"action": "create", "title": "<principle name>", "fact": "<what is true>", "source": "<file:line>", "category": "<architecture|pattern|invariant|threshold>"}
  {"action": "update", "principle_id": "<id>", "fact": "<updated fact>", "source": "<updated source>"}
  {"action": "retire", "principle_id": "<id>", "reason": "<why>"}
  {"action": "list"}

Env: WORKSPACE — sandbox root.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

STORE_FILENAME = "principles.json"


def load_store(workspace: str) -> list:
    path = os.path.join(workspace, STORE_FILENAME)
    if os.path.isfile(path):
        return json.load(open(path))
    return []


def save_store(workspace: str, store: list):
    path = os.path.join(workspace, STORE_FILENAME)
    json.dump(store, open(path, "w"), indent=2, ensure_ascii=False)


def make_id(title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', title.lower().strip())[:40].strip('_')
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"{slug}_{ts}"


def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    action = params.get("action", "list")
    store = load_store(workspace)
    now = datetime.now(timezone.utc).isoformat()

    if action == "list":
        active = [p for p in store if p.get("status") != "retired"]
        print(f"{len(active)} active principles:")
        for p in active:
            print(f"  [{p['principle_id']}] {p['title']}")
            print(f"    {p['fact'][:120]}")
            print(f"    source: {p.get('source', '?')} | category: {p.get('category', '?')}")
        return

    elif action == "create":
        title = params.get("title", "")
        fact = params.get("fact", "")
        source = params.get("source", "")
        category = params.get("category", "architecture")

        if not title or not fact:
            print("Error: 'title' and 'fact' required", file=sys.stderr)
            sys.exit(1)

        pid = make_id(title)
        entry = {
            "principle_id": pid,
            "title": title,
            "fact": fact,
            "source": source,
            "category": category,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "history": [{"t": now, "kind": "created"}],
        }
        store.append(entry)
        save_store(workspace, store)
        print(f"Created principle '{pid}': {title}")

    elif action == "update":
        pid = params.get("principle_id", "")
        entry = next((p for p in store if p["principle_id"] == pid), None)
        if not entry:
            print(f"Error: principle '{pid}' not found", file=sys.stderr)
            sys.exit(1)

        changed = []
        for field in ("fact", "source", "category", "title"):
            if field in params and params[field] != entry.get(field):
                old = entry.get(field, "")
                entry[field] = params[field]
                changed.append(field)

        if changed:
            entry["updated_at"] = now
            entry["history"].append({"t": now, "kind": "updated", "fields": changed})
            save_store(workspace, store)
            print(f"Updated '{pid}': {', '.join(changed)}")
        else:
            print(f"No changes to '{pid}'")

    elif action == "retire":
        pid = params.get("principle_id", "")
        entry = next((p for p in store if p["principle_id"] == pid), None)
        if not entry:
            print(f"Error: principle '{pid}' not found", file=sys.stderr)
            sys.exit(1)

        entry["status"] = "retired"
        entry["updated_at"] = now
        reason = params.get("reason", "")
        entry["history"].append({"t": now, "kind": "retired", "reason": reason})
        save_store(workspace, store)
        print(f"Retired '{pid}': {reason}")

    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
