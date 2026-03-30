#!/usr/bin/env python3
"""commitments.py — Persistent commitments tracker (reminders, deadlines, recurring tasks).

Shares the same backing store as task_registry.py (tasks.json).
Commitment records have _type="commitment" to distinguish from task records.

Actions:
  create    — create a new commitment (idempotent on external_key)
  update    — update an existing commitment by commitment_id or external_key
  get       — retrieve a single commitment
  search    — list commitments filtered by status, participant, project, tag, or text
  due       — list commitments due by a given timestamp (or now)
  complete  — mark completed and optionally roll recurrence forward
  tick      — scan all commitments and surface those currently due

Input (JSON on stdin):
  {
    "action": "create|update|get|search|due|complete|tick",
    "commitment_id": "<optional>",
    "external_key": "<optional idempotency key>",
    "title": "<optional>",
    "details": "<optional>",
    "status": "<optional: open|in_progress|blocked|done|cancelled>",
    "participants": ["<optional contact id>"],
    "project": "<optional>",
    "tags": ["<optional>"],
    "due_at": "<optional ISO 8601 UTC>",
    "recurrence": {"freq": "daily|weekly|monthly", "interval": 1},
    "note": "<optional>",
    "query": "<optional text search>",
    "contact_id": "<optional actor>",
    "now": "<optional ISO 8601 UTC override>",
    "limit": 20
  }

Output (stdout): human-readable summary.
"""

import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Store path: from REGISTRY_PATH env var (persistent memory) ─────
_env_path = os.environ.get("REGISTRY_PATH", "")
STORE_FILE = Path(_env_path) if _env_path else Path(__file__).resolve().parent / "tasks.json"

VALID_STATUSES = {"open", "in_progress", "blocked", "done", "cancelled"}
VALID_FREQS = {"daily", "weekly", "monthly"}
RECORD_TYPE = "commitment"


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


def commitments_only(store):
    return [r for r in store if r.get("_type") == RECORD_TYPE]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_iso(ts):
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def fmt_iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text, max_len=32):
    chars = []
    prev_us = False
    for ch in (text or "").lower():
        if ch.isalnum():
            chars.append(ch)
            prev_us = False
        elif not prev_us:
            chars.append("_")
            prev_us = True
    return "".join(chars).strip("_")[:max_len] or "commitment"


def make_id(title=""):
    return f"{slugify(title)}_{int(time.time())}"


def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    seen = set()
    out = []
    for item in value:
        s = str(item).strip() if item is not None else ""
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def normalize_recurrence(value):
    if value in (None, "", {}):
        return None
    if not isinstance(value, dict):
        raise ValueError("recurrence must be an object")
    freq = str(value.get("freq", "")).strip().lower()
    if freq not in VALID_FREQS:
        raise ValueError("recurrence.freq must be daily, weekly, or monthly")
    interval = value.get("interval", 1)
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        raise ValueError("recurrence.interval must be a positive integer")
    if interval <= 0:
        raise ValueError("recurrence.interval must be a positive integer")
    return {"freq": freq, "interval": interval}


def add_months(dt, months):
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = dt.day
    while True:
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
            if day <= 0:
                raise


def advance_due(due_at, recurrence):
    base = parse_iso(due_at)
    if not base or not recurrence:
        return None
    freq = recurrence.get("freq")
    interval = recurrence.get("interval", 1)
    if freq == "daily":
        return fmt_iso(base + timedelta(days=interval))
    if freq == "weekly":
        return fmt_iso(base + timedelta(weeks=interval))
    if freq == "monthly":
        return fmt_iso(add_months(base, interval))
    return None


def append_history(item, kind, actor="", note="", extra=None, when=None):
    entry = {"t": when or now_iso(), "kind": kind, "actor": actor or "", "note": note or ""}
    if extra:
        entry.update(extra)
    item.setdefault("history", []).append(entry)


def find_commitment(items, commitment_id="", external_key=""):
    for item in commitments_only(items):
        if commitment_id and item.get("commitment_id") == commitment_id:
            return item
        if external_key and item.get("external_key") == external_key:
            return item
    return None


# ── Actions ───────────────────────────────────────────────────────────

def action_create(params, store):
    external_key = str(params.get("external_key", "")).strip()
    if external_key:
        existing = find_commitment(store, external_key=external_key)
        if existing:
            return store, f"Exists: {existing.get('commitment_id')!r} — {existing.get('title', '')!r} [{existing.get('status', 'open')}]"

    title = str(params.get("title", "")).strip()
    if not title:
        return store, "Error: title is required"

    status = str(params.get("status", "open")).strip() or "open"
    if status not in VALID_STATUSES:
        return store, f"Error: status must be one of {', '.join(sorted(VALID_STATUSES))}"

    due_at = params.get("due_at")
    if due_at and not parse_iso(due_at):
        return store, "Error: due_at must be ISO 8601"

    try:
        recurrence = normalize_recurrence(params.get("recurrence"))
    except ValueError as e:
        return store, f"Error: {e}"

    actor = str(params.get("contact_id", "")).strip()
    participants = normalize_list(params.get("participants"))
    if actor and actor not in participants:
        participants.append(actor)

    item = {
        "_type": RECORD_TYPE,
        "commitment_id": str(params.get("commitment_id") or make_id(title)),
        "external_key": external_key,
        "title": title,
        "details": str(params.get("details", "")).strip(),
        "status": status,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "completed_at": "",
        "participants": participants,
        "project": str(params.get("project", "")).strip(),
        "tags": normalize_list(params.get("tags")),
        "due_at": due_at or "",
        "recurrence": recurrence,
        "requirements": normalize_list(params.get("requirements")),
        "last_tick_at": "",
        "history": [],
    }
    append_history(item, "created", actor=actor,
                   note=str(params.get("note", "")).strip(),
                   extra={"status": status})
    store.append(item)
    return store, f"Created commitment {item['commitment_id']!r}: {title!r} [{status}]"


def action_update(params, store):
    cid = str(params.get("commitment_id", "")).strip()
    ekey = str(params.get("external_key", "")).strip()
    item = find_commitment(store, commitment_id=cid, external_key=ekey)
    if not item:
        return store, "Error: commitment not found"

    actor = str(params.get("contact_id", "")).strip()
    changed = []

    for field, key in [("title", "title"), ("details", "details"), ("project", "project")]:
        if field in params:
            val = str(params[field]).strip()
            if val or field != "title":
                item[key] = val
                changed.append(field)

    if "status" in params:
        status = str(params["status"]).strip()
        if status not in VALID_STATUSES:
            return store, f"Error: invalid status {status!r}"
        item["status"] = status
        if status != "done":
            item["completed_at"] = ""
        changed.append("status")

    if "participants" in params:
        item["participants"] = normalize_list(params["participants"])
        changed.append("participants")

    if actor and actor not in item.get("participants", []):
        item.setdefault("participants", []).append(actor)

    if "tags" in params:
        item["tags"] = normalize_list(params["tags"])
        changed.append("tags")

    if "due_at" in params:
        due_at = params["due_at"]
        if due_at and not parse_iso(due_at):
            return store, "Error: due_at must be ISO 8601"
        item["due_at"] = due_at or ""
        changed.append("due_at")

    if "recurrence" in params:
        try:
            item["recurrence"] = normalize_recurrence(params["recurrence"])
        except ValueError as e:
            return store, f"Error: {e}"
        changed.append("recurrence")

    # Handle requirement(s) — single or list
    req = str(params.get("requirement", "")).strip()
    reqs_list = params.get("requirements", [])
    if isinstance(reqs_list, str):
        reqs_list = [reqs_list]
    if req:
        reqs_list.append(req)
    existing = item.setdefault("requirements", [])
    added_reqs = []
    for r in reqs_list:
        r = str(r).strip()
        if r and r not in existing:
            existing.append(r)
            added_reqs.append(r)
            changed.append("requirement")

    if not changed and not str(params.get("note", "")).strip():
        return store, f"No changes to {item.get('commitment_id')!r}"

    item["updated_at"] = now_iso()
    if added_reqs:
        for r in added_reqs:
            append_history(item, "requirement_added", actor=actor, note=r)
    else:
        append_history(item, "updated", actor=actor,
                       note=str(params.get("note", "")).strip(),
                       extra={"fields": changed})
    summary = f"Updated {item.get('commitment_id')!r}: {item.get('title', '')!r} [{item.get('status', 'open')}]"
    if added_reqs:
        summary += f" — added {len(added_reqs)} requirement(s) ({len(existing)} total)"
    return store, summary


def action_add_requirement(params, store):
    cid = str(params.get("commitment_id", "")).strip()
    ekey = str(params.get("external_key", "")).strip()
    item = find_commitment(store, commitment_id=cid, external_key=ekey)
    if not item:
        return store, "Error: commitment not found"

    req = str(params.get("requirement", "")).strip()
    if not req:
        return store, "Error: requirement text is required"

    actor = str(params.get("contact_id", "")).strip()
    reqs = item.setdefault("requirements", [])

    # Don't add duplicates
    if req in reqs:
        return store, f"Requirement already exists on {item.get('commitment_id')!r}: {req!r}"

    reqs.append(req)
    item["updated_at"] = now_iso()
    append_history(item, "requirement_added", actor=actor, note=req)
    return store, f"Added requirement to {item.get('commitment_id')!r} ({len(reqs)} total): {req!r}"


def format_commitment(item):
    lines = [
        f"Commitment: {item.get('commitment_id', '')}",
        f"Title: {item.get('title', '')}",
        f"Status: {item.get('status', 'open')}",
        f"Created: {item.get('created_at', '')}",
        f"Updated: {item.get('updated_at', '')}",
    ]
    if item.get("external_key"):
        lines.append(f"External key: {item['external_key']}")
    if item.get("details"):
        lines.append(f"Details: {item['details']}")
    if item.get("project"):
        lines.append(f"Project: {item['project']}")
    if item.get("participants"):
        lines.append(f"Participants: {', '.join(item['participants'])}")
    if item.get("tags"):
        lines.append(f"Tags: {', '.join(item['tags'])}")
    if item.get("due_at"):
        lines.append(f"Due: {item['due_at']}")
    rec = item.get("recurrence")
    if rec:
        freq = rec.get("freq", "?")
        interval = rec.get("interval", 1)
        lines.append(f"Recurrence: {'every ' + str(interval) + ' ' if interval > 1 else ''}{freq}")
    reqs = item.get("requirements", [])
    if reqs:
        lines.append(f"Requirements ({len(reqs)}):")
        for r in reqs:
            lines.append(f"  - {r}")
    if item.get("completed_at"):
        lines.append(f"Completed: {item['completed_at']}")
    history = item.get("history", [])
    if history:
        lines.append(f"History ({len(history)}):")
        for h in history[-5:]:
            line = f"  [{h.get('t', '')}] {h.get('kind', '?')}"
            if h.get("actor"):
                line += f" by {h['actor']}"
            if h.get("note"):
                line += f": {h['note']}"
            lines.append(line)
    return "\n".join(lines)


def action_get(params, store):
    item = find_commitment(store,
                           commitment_id=str(params.get("commitment_id", "")).strip(),
                           external_key=str(params.get("external_key", "")).strip())
    if not item:
        return store, "Commitment not found"
    return store, format_commitment(item)


def action_search(params, store):
    status = str(params.get("status", "")).strip()
    participant = str(params.get("participant", params.get("contact_id", ""))).strip()
    project = str(params.get("project", "")).strip().lower()
    tags = normalize_list(params.get("tags"))
    query = str(params.get("query", "")).strip().lower()
    limit = min(max(1, int(params.get("limit", 20) or 20)), 100)

    query_terms = query.split() if query else []
    filtered = []
    for item in commitments_only(store):
        if status and item.get("status") != status:
            continue
        if participant and participant not in item.get("participants", []):
            continue
        if project and project != str(item.get("project", "")).lower():
            continue
        if tags and not any(t in item.get("tags", []) for t in tags):
            continue
        if query_terms:
            hay = " ".join([
                item.get("commitment_id", ""), item.get("external_key", ""),
                item.get("title", ""), item.get("details", ""),
                item.get("project", ""), " ".join(item.get("participants", [])),
                " ".join(item.get("tags", [])),
            ]).lower()
            if not all(term in hay for term in query_terms):
                continue
        filtered.append(item)

    filtered.sort(key=lambda x: (x.get("status", ""), x.get("due_at", "") or "9999"))
    filtered = filtered[:limit]

    if not filtered:
        return store, "No commitments found"

    lines = [f"{len(filtered)} commitment(s):"]
    for item in filtered:
        line = f"  [{item.get('status', 'open')}] {item.get('commitment_id')}: {item.get('title', '')}"
        if item.get("due_at"):
            line += f" — due {item['due_at']}"
        if item.get("project"):
            line += f" — project: {item['project']}"
        if item.get("participants"):
            line += f" — {', '.join(item['participants'])}"
        lines.append(line)
    return store, "\n".join(lines)


def action_due(params, store):
    now = parse_iso(params.get("now")) or parse_iso(now_iso())
    due_items = []
    for item in commitments_only(store):
        if item.get("status") not in {"open", "in_progress", "blocked"}:
            continue
        due_at = parse_iso(item.get("due_at", ""))
        if due_at and due_at <= now:
            due_items.append(item)

    due_items.sort(key=lambda x: x.get("due_at", ""))
    if not due_items:
        return store, f"No commitments due as of {fmt_iso(now)}"

    lines = [f"{len(due_items)} commitment(s) due as of {fmt_iso(now)}:"]
    for item in due_items:
        line = f"  [{item.get('status', 'open')}] {item.get('commitment_id')}: {item.get('title', '')} — due {item.get('due_at', '')}"
        if item.get("project"):
            line += f" — project: {item['project']}"
        lines.append(line)
    return store, "\n".join(lines)


def action_complete(params, store):
    item = find_commitment(store,
                           commitment_id=str(params.get("commitment_id", "")).strip(),
                           external_key=str(params.get("external_key", "")).strip())
    if not item:
        return store, "Error: commitment not found"

    actor = str(params.get("contact_id", "")).strip()
    note = str(params.get("note", "")).strip()
    completed_at = params.get("now") if parse_iso(params.get("now")) else now_iso()

    recurrence = deepcopy(item.get("recurrence"))
    old_due = item.get("due_at", "")
    item["status"] = "done"
    item["completed_at"] = completed_at
    item["updated_at"] = now_iso()
    append_history(item, "completed", actor=actor, note=note, extra={"due_at": old_due})

    if recurrence and old_due:
        next_due = advance_due(old_due, recurrence)
        if next_due:
            item["status"] = "open"
            item["due_at"] = next_due
            item["updated_at"] = now_iso()
            append_history(item, "rescheduled", actor=actor,
                           note="rolled recurrence forward",
                           extra={"previous_due_at": old_due, "next_due_at": next_due})
            return store, f"Completed and rescheduled {item.get('commitment_id')!r} → next due {next_due}"

    return store, f"Completed {item.get('commitment_id')!r}: {item.get('title', '')!r}"


def action_tick(params, store):
    now = parse_iso(params.get("now")) or parse_iso(now_iso())
    actor = str(params.get("contact_id", "system")).strip() or "system"
    due_now = []
    for item in commitments_only(store):
        if item.get("status") not in {"open", "in_progress", "blocked"}:
            continue
        due_at = parse_iso(item.get("due_at", ""))
        if not due_at or due_at > now:
            continue
        last_tick = parse_iso(item.get("last_tick_at", ""))
        if not last_tick or last_tick < due_at:
            item["last_tick_at"] = fmt_iso(now)
            item["updated_at"] = now_iso()
            append_history(item, "tick", actor=actor, note="commitment is due",
                           extra={"due_at": item.get("due_at", "")}, when=fmt_iso(now))
        due_now.append(item)

    if not due_now:
        return store, f"No commitments due at {fmt_iso(now)}"

    due_now.sort(key=lambda x: x.get("due_at", ""))
    lines = [f"{len(due_now)} due commitment(s) at {fmt_iso(now)}:"]
    for item in due_now:
        line = f"  [{item.get('status', 'open')}] {item.get('commitment_id')}: {item.get('title', '')}"
        if item.get("due_at"):
            line += f" — due {item['due_at']}"
        if item.get("project"):
            line += f" — project: {item['project']}"
        lines.append(line)
    return store, "\n".join(lines)


ACTIONS = {
    "create": action_create,
    "update": action_update,
    "add_requirement": action_add_requirement,
    "get": action_get,
    "search": action_search,
    "due": action_due,
    "complete": action_complete,
    "tick": action_tick,
}

MUTATING = {"create", "update", "add_requirement", "complete", "tick"}


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
