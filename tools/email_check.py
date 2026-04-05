#!/usr/bin/env python3
"""email_check — read-only email observation: outbox status, SMTP config.

Input JSON: {"action": "status"}
Env: WORKSPACE, EMAIL_SENDER, EMAIL_RECIPIENT.
"""
TOOL_DESC = 'read-only email observation: outbox status, SMTP config.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json, os, sys

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    lines = []

    # SMTP status
    sender = os.environ.get("EMAIL_SENDER", "")
    recipient = os.environ.get("EMAIL_RECIPIENT", "")
    if not sender:
        lines.append("SMTP: not configured (EMAIL_SENDER missing)")
    else:
        lines.append(f"SMTP: configured (sender: {sender})")
    if recipient:
        lines.append(f"Default recipient: {recipient}")

    # Outbox contents
    outbox = os.path.join(workspace, "outbox")
    if os.path.isdir(outbox):
        drafts = []
        for name in sorted(os.listdir(outbox)):
            if name.endswith(".json"):
                try:
                    with open(os.path.join(outbox, name)) as f:
                        draft = json.load(f)
                    to = draft.get("to", "?")
                    subj = draft.get("subject", "?")
                    status = draft.get("status", "draft")
                    drafts.append(f"  {name} → [{status}] to: {to}, subject: {subj}")
                except (json.JSONDecodeError, OSError):
                    pass
        if drafts:
            lines.append(f"Outbox: {len(drafts)} email(s)")
            lines.extend(drafts)
        else:
            lines.append("Outbox: empty (no previous drafts)")
    else:
        lines.append("Outbox: empty (no previous drafts)")

    # Workspace files summary
    if os.path.isdir(workspace):
        files = []
        for name in sorted(os.listdir(workspace)):
            if name.startswith(".") or name == "outbox":
                continue
            full = os.path.join(workspace, name)
            if os.path.isdir(full):
                files.append(f"  {name}/")
            else:
                files.append(f"  {name} ({os.path.getsize(full)}B)")
        if files:
            lines.append(f"Workspace files ({len(files)}):")
            lines.extend(files)

    print("\n".join(lines))

if __name__ == "__main__":
    main()
