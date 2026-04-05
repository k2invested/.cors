#!/usr/bin/env python3
"""email — compose email draft AND send via SMTP.

Input JSON: {"to": "<email>", "subject": "<subject>", "body": "<body>",
             "attachment": "<optional: relative file path>"}
Env: WORKSPACE, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT (default to).
"""
TOOL_DESC = 'compose email draft AND send via SMTP.'
TOOL_MODE = 'mutate'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'artifacts'
TOOL_RUNTIME_ARTIFACT_KEY = 'path'

import json, os, smtplib, sys, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def main():
    params = json.load(sys.stdin)
    workspace = os.environ.get("WORKSPACE", ".")
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    default_recipient = os.environ.get("EMAIL_RECIPIENT", "")

    to = params.get("to", default_recipient)
    subject = params.get("subject", "(no subject)")
    body = params.get("body", "")
    attachment = params.get("attachment")

    if not to:
        print("Error: missing 'to' parameter and no EMAIL_RECIPIENT configured", file=sys.stderr)
        sys.exit(1)

    # Save draft
    timestamp = int(time.time())
    outbox = os.path.join(workspace, "outbox")
    os.makedirs(outbox, exist_ok=True)
    draft = {"to": to, "subject": subject, "body": body, "timestamp": timestamp}
    if attachment:
        draft["attachment"] = attachment
    filename = f"email_{timestamp}.json"
    draft_path = os.path.join(outbox, filename)
    with open(draft_path, "w") as f:
        json.dump(draft, f, indent=2)

    # Send via SMTP
    draft_rel_path = f"outbox/{filename}"

    if not sender or not password:
        print(json.dumps({
            "status": "draft_saved",
            "path": draft_rel_path,
            "to": to,
            "subject": subject,
        }))
        return

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attachment:
        full_path = os.path.join(workspace, attachment) if not os.path.isabs(attachment) else attachment
        if os.path.isfile(full_path):
            with open(full_path, "rb") as af:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(af.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(full_path)}")
            msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    # Mark draft as sent
    draft["status"] = "sent"
    with open(draft_path, "w") as f:
        json.dump(draft, f, indent=2)

    print(json.dumps({
        "status": "sent",
        "path": draft_rel_path,
        "to": to,
        "subject": subject,
    }))

if __name__ == "__main__":
    main()
