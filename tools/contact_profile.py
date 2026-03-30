#!/usr/bin/env python3
"""contact_profile.py — Get/set/merge contact profile and preferences.

Shares the same backing store (registry.json) as commitments and task coordination.
Profile records have _type="profile" and are keyed by contact_id.

Actions:
  get    — retrieve a contact's profile
  set    — set/overwrite specific fields on a profile
  merge  — merge fields into a profile (existing fields preserved unless overwritten)
  list   — list all profiles (optional contact_id filter)

Input (JSON on stdin):
  {
    "action": "get|set|merge|list",
    "contact_id": "<required for get/set/merge>",
    "fields": {"<key>": "<value>", ...}  (for set/merge)
  }

Output (stdout): human-readable summary.

Env: REGISTRY_PATH — path to shared registry.json.
"""

import json
import os
import sys
import time
from pathlib import Path

_env_path = os.environ.get("REGISTRY_PATH", "")
STORE_FILE = Path(_env_path) if _env_path else Path(__file__).resolve().parent / "tasks.json"
RECORD_TYPE = "profile"


def load_store():
    if not STORE_FILE.exists():
        return []
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_store(items):
    STORE_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def find_profile(store, contact_id):
    for item in store:
        if item.get("_type") == RECORD_TYPE and item.get("contact_id") == contact_id:
            return item
    return None


def format_profile(profile):
    lines = [f"Profile: {profile.get('contact_id', '?')}"]
    for k, v in profile.items():
        if k.startswith("_") or k == "contact_id":
            continue
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def action_get(params, store):
    contact_id = str(params.get("contact_id", "")).strip()
    if not contact_id:
        return store, "Error: contact_id is required"
    profile = find_profile(store, contact_id)
    if not profile:
        return store, f"No profile found for {contact_id!r}"
    return store, format_profile(profile)


def action_set(params, store):
    contact_id = str(params.get("contact_id", "")).strip()
    if not contact_id:
        return store, "Error: contact_id is required"
    fields = params.get("fields", {})
    if not isinstance(fields, dict) or not fields:
        return store, "Error: fields dict is required for set"

    profile = find_profile(store, contact_id)
    if not profile:
        profile = {"_type": RECORD_TYPE, "contact_id": contact_id, "created_at": now_iso()}
        store.append(profile)

    for k, v in fields.items():
        if k.startswith("_") or k == "contact_id":
            continue
        profile[k] = v
    profile["updated_at"] = now_iso()

    return store, f"Set {len(fields)} field(s) on profile {contact_id!r}"


def action_merge(params, store):
    contact_id = str(params.get("contact_id", "")).strip()
    if not contact_id:
        return store, "Error: contact_id is required"
    fields = params.get("fields", {})
    if not isinstance(fields, dict) or not fields:
        return store, "Error: fields dict is required for merge"

    profile = find_profile(store, contact_id)
    if not profile:
        profile = {"_type": RECORD_TYPE, "contact_id": contact_id, "created_at": now_iso()}
        store.append(profile)

    merged = 0
    for k, v in fields.items():
        if k.startswith("_") or k == "contact_id":
            continue
        if k not in profile:
            profile[k] = v
            merged += 1
        elif profile[k] != v:
            profile[k] = v
            merged += 1
    profile["updated_at"] = now_iso()

    return store, f"Merged {merged} field(s) on profile {contact_id!r}"


def action_list(params, store):
    contact_id = str(params.get("contact_id", "")).strip()
    profiles = [r for r in store if r.get("_type") == RECORD_TYPE]
    if contact_id:
        profiles = [p for p in profiles if p.get("contact_id") == contact_id]

    if not profiles:
        return store, "No profiles found"

    lines = [f"{len(profiles)} profile(s):"]
    for p in profiles:
        cid = p.get("contact_id", "?")
        fields = {k: v for k, v in p.items() if not k.startswith("_") and k != "contact_id"}
        line = f"  {cid}: {', '.join(f'{k}={v}' for k, v in fields.items())}" if fields else f"  {cid}: (empty)"
        lines.append(line)
    return store, "\n".join(lines)


ACTIONS = {
    "get": action_get,
    "set": action_set,
    "merge": action_merge,
    "list": action_list,
}

MUTATING = {"set", "merge"}


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: no input", file=sys.stderr)
        sys.exit(1)

    try:
        params = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    action = str(params.get("action", "")).strip()
    if action not in ACTIONS:
        print(f"Error: unknown action {action!r}. Valid: {', '.join(sorted(ACTIONS))}", file=sys.stderr)
        sys.exit(1)

    store = load_store()
    try:
        updated, output = ACTIONS[action](params, store)
    except Exception as e:
        print(f"Error: {action!r} failed: {e}", file=sys.stderr)
        sys.exit(1)

    if action in MUTATING and not output.startswith("Error:"):
        try:
            save_store(updated)
        except OSError as e:
            print(f"Error: save failed: {e}", file=sys.stderr)
            sys.exit(1)

    print(output)


if __name__ == "__main__":
    main()
