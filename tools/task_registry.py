#!/usr/bin/env python3
"""
task_registry.py — Shared multi-party task coordination tool.

Reads/writes principle/tasks.json (a JSON array of task objects).

Actions:
  upsert         — create or update a task by task_id
  update_status  — set the status field on an existing task
  add_update     — append a progress note to a task's updates list
  get            — retrieve a single task by task_id
  list           — list all tasks (optionally filtered by status or tag)

Input (JSON on stdin):
  {
    "action": "upsert|update_status|add_update|get|list",
    "task_id": "<optional task identifier — auto-generated if omitted on upsert>",
    "title": "<optional task title>",
    "status": "<optional: open|in_progress|blocked|done>",
    "contact_id": "<optional: contact who owns or updated the task>",
    "note": "<optional: progress note or update text>",
    "tags": ["<optional tag>"]
  }

Output (stdout): human-readable summary of the result.
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Storage path ──────────────────────────────────────────────────────
# Resolved relative to this script's directory (principle/)
SCRIPT_DIR = Path(__file__).resolve().parent
TASKS_FILE = SCRIPT_DIR / "tasks.json"


# ── Persistence helpers ───────────────────────────────────────────────

def load_tasks():
    """Load tasks from TASKS_FILE. Returns a list of task dicts."""
    if not TASKS_FILE.exists():
        return []
    try:
        data = TASKS_FILE.read_text(encoding="utf-8")
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return []


def save_tasks(tasks):
    """Persist tasks list to TASKS_FILE."""
    TASKS_FILE.write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def now_iso():
    """Current UTC time as ISO 8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def make_task_id(title=""):
    """Generate a short deterministic task ID from title + timestamp."""
    ts = str(int(time.time()))
    slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:24]
    return f"{slug}_{ts}" if slug else f"task_{ts}"


# ── Action handlers ───────────────────────────────────────────────────

def action_upsert(params, tasks):
    """
    Create a new task or update an existing one.
    If task_id is omitted, a new ID is generated.
    Returns (updated_tasks, output_string).
    """
    task_id = params.get("task_id") or make_task_id(params.get("title", ""))
    title = params.get("title", "")
    status = params.get("status", "open")
    contact_id = params.get("contact_id", "")
    tags = params.get("tags") or []
    note = params.get("note", "")

    # Find existing task
    existing = next((t for t in tasks if t.get("task_id") == task_id), None)

    if existing:
        # Update fields that were supplied
        if title:
            existing["title"] = title
        if status:
            existing["status"] = status
        if contact_id and contact_id not in existing.get("contributors", []):
            existing.setdefault("contributors", []).append(contact_id)
        if tags:
            for tag in tags:
                if tag not in existing.get("tags", []):
                    existing.setdefault("tags", []).append(tag)
        if note:
            existing.setdefault("updates", []).append({
                "contact_id": contact_id,
                "note": note,
                "t": now_iso(),
            })
        existing["updated_at"] = now_iso()
        return tasks, f"Updated task {task_id!r}: {existing.get('title', '')!r} [{existing['status']}]"
    else:
        # Create new task
        task = {
            "task_id": task_id,
            "title": title,
            "status": status,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "contributors": [contact_id] if contact_id else [],
            "tags": tags,
            "updates": [],
        }
        if note:
            task["updates"].append({
                "contact_id": contact_id,
                "note": note,
                "t": now_iso(),
            })
        tasks.append(task)
        return tasks, f"Created task {task_id!r}: {title!r} [{status}]"


def action_update_status(params, tasks):
    """
    Set the status field on an existing task.
    Returns (updated_tasks, output_string).
    """
    task_id = params.get("task_id", "")
    status = params.get("status", "")
    contact_id = params.get("contact_id", "")

    if not task_id:
        return tasks, "Error: task_id is required for update_status"
    if not status:
        return tasks, "Error: status is required for update_status"

    task = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not task:
        return tasks, f"Error: task {task_id!r} not found"

    old_status = task.get("status", "unknown")
    task["status"] = status
    task["updated_at"] = now_iso()
    if contact_id and contact_id not in task.get("contributors", []):
        task.setdefault("contributors", []).append(contact_id)

    return tasks, (
        f"Task {task_id!r} status updated: {old_status!r} → {status!r}"
        + (f" (by {contact_id})" if contact_id else "")
    )


def action_add_update(params, tasks):
    """
    Append a progress note to a task's updates list.
    Returns (updated_tasks, output_string).
    """
    task_id = params.get("task_id", "")
    note = params.get("note", "")
    contact_id = params.get("contact_id", "")

    if not task_id:
        return tasks, "Error: task_id is required for add_update"
    if not note:
        return tasks, "Error: note is required for add_update"

    task = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not task:
        return tasks, f"Error: task {task_id!r} not found"

    entry = {"contact_id": contact_id, "note": note, "t": now_iso()}
    task.setdefault("updates", []).append(entry)
    task["updated_at"] = now_iso()
    if contact_id and contact_id not in task.get("contributors", []):
        task.setdefault("contributors", []).append(contact_id)

    return tasks, (
        f"Added update to task {task_id!r}"
        + (f" from {contact_id}" if contact_id else "")
        + f": {note[:80]}"
    )


def action_get(params, tasks):
    """
    Retrieve a single task by task_id.
    Returns (tasks_unchanged, output_string).
    """
    task_id = params.get("task_id", "")
    if not task_id:
        return tasks, "Error: task_id is required for get"

    task = next((t for t in tasks if t.get("task_id") == task_id), None)
    if not task:
        return tasks, f"Task {task_id!r} not found"

    lines = [
        f"Task: {task.get('task_id')}",
        f"Title: {task.get('title', '')}",
        f"Status: {task.get('status', 'open')}",
        f"Created: {task.get('created_at', '')}",
        f"Updated: {task.get('updated_at', '')}",
    ]
    contributors = task.get("contributors", [])
    if contributors:
        lines.append(f"Contributors: {', '.join(contributors)}")
    tags = task.get("tags", [])
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
    updates = task.get("updates", [])
    if updates:
        lines.append(f"Updates ({len(updates)}):")
        for u in updates[-5:]:  # show last 5
            who = u.get("contact_id", "?")
            when = u.get("t", "")
            note = u.get("note", "")
            lines.append(f"  [{when}] {who}: {note}")
    return tasks, "\n".join(lines)


def action_list(params, tasks):
    """
    List all tasks, optionally filtered by status or tag.
    Returns (tasks_unchanged, output_string).
    """
    status_filter = params.get("status", "")
    tag_filter = params.get("tags", [])
    if isinstance(tag_filter, str):
        tag_filter = [tag_filter]

    # Filter to task records only (exclude commitments)
    task_records = [t for t in tasks if t.get("_type") != "commitment"]
    filtered = task_records
    if status_filter:
        filtered = [t for t in filtered if t.get("status") == status_filter]
    if tag_filter:
        filtered = [t for t in filtered if any(tag in t.get("tags", []) for tag in tag_filter)]

    if not filtered:
        msg = "No tasks found"
        if status_filter:
            msg += f" with status={status_filter!r}"
        if tag_filter:
            msg += f" with tags={tag_filter}"
        return tasks, msg

    lines = [f"{len(filtered)} task(s):"]
    for t in filtered:
        tid = t.get("task_id", "?")
        title = t.get("title", "(no title)")
        status = t.get("status", "open")
        contributors = ", ".join(t.get("contributors", []))
        update_count = len(t.get("updates", []))
        line = f"  [{status}] {tid}: {title}"
        if contributors:
            line += f" — contributors: {contributors}"
        if update_count:
            line += f" ({update_count} update(s))"
        lines.append(line)
    return tasks, "\n".join(lines)


def action_list_commitments(params, tasks):
    """
    List commitments from the shared store, optionally filtered by participant or project.
    Enables coordination to surface individual commitment data.
    Returns (tasks_unchanged, output_string).
    """
    participant = params.get("contact_id", "")
    project = str(params.get("project", "")).strip().lower()
    status_filter = params.get("status", "")

    # Read from persistent memory store (REGISTRY_PATH) if available
    _cpath = os.environ.get("REGISTRY_PATH", "")
    if _cpath and os.path.exists(_cpath):
        try:
            commitments = json.loads(Path(_cpath).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            commitments = []
    else:
        commitments = [t for t in tasks if t.get("_type") == "commitment"]
    if status_filter:
        commitments = [c for c in commitments if c.get("status") == status_filter]
    if participant:
        commitments = [c for c in commitments if participant in c.get("participants", [])]
    if project:
        commitments = [c for c in commitments if project == str(c.get("project", "")).lower()]

    if not commitments:
        return tasks, "No commitments found"

    lines = [f"{len(commitments)} commitment(s):"]
    for c in commitments:
        line = f"  [{c.get('status', 'open')}] {c.get('commitment_id', '?')}: {c.get('title', '')}"
        if c.get("due_at"):
            line += f" — due {c['due_at']}"
        if c.get("project"):
            line += f" — project: {c['project']}"
        if c.get("participants"):
            line += f" — {', '.join(c['participants'])}"
        lines.append(line)
    return tasks, "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────

ACTIONS = {
    "upsert": action_upsert,
    "update_status": action_update_status,
    "add_update": action_add_update,
    "get": action_get,
    "list": action_list,
    "list_commitments": action_list_commitments,
}


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: no input provided", file=sys.stderr)
        sys.exit(1)

    try:
        params = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    action = params.get("action", "").strip()
    if not action:
        print("Error: 'action' field is required", file=sys.stderr)
        sys.exit(1)

    if action not in ACTIONS:
        valid = ", ".join(sorted(ACTIONS))
        print(f"Error: unknown action {action!r}. Valid actions: {valid}", file=sys.stderr)
        sys.exit(1)

    tasks = load_tasks()
    handler = ACTIONS[action]
    is_mutating = action in ("upsert", "update_status", "add_update")

    try:
        updated_tasks, output = handler(params, tasks)
    except Exception as e:
        print(f"Error: action {action!r} failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Persist only if the action mutated state
    if is_mutating and not output.startswith("Error:"):
        try:
            save_tasks(updated_tasks)
        except OSError as e:
            print(f"Error: could not save tasks: {e}", file=sys.stderr)
            sys.exit(1)

    print(output)


if __name__ == "__main__":
    main()
