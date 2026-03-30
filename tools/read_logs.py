#!/usr/bin/env python3
"""read_logs — read runtime logs from system instances.

Input JSON:
  {"source": "telegram", "lines": 50}     — VPS telegram bot logs
  {"source": "discord", "lines": 50}      — local Discord bot log
  {"source": "vps", "command": "<cmd>"}    — run arbitrary command on VPS

Env: SSH key at ~/.ssh/hetzner, VPS at root@89.167.61.222
"""
import json
import os
import subprocess
import sys
from pathlib import Path


VPS_HOST = "root@89.167.61.222"
SSH_KEY = os.path.expanduser("~/.ssh/hetzner")
DISCORD_LOG = str(Path(__file__).resolve().parent.parent / "bot.log")


def read_telegram_logs(lines: int = 50) -> str:
    """Read telegram bot logs from VPS via journalctl."""
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, VPS_HOST,
         f"journalctl -u telegram-bot -n {lines} --no-pager"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


def read_discord_logs(lines: int = 50) -> str:
    """Read local Discord bot log file."""
    if not os.path.isfile(DISCORD_LOG):
        return "No Discord bot.log found"
    with open(DISCORD_LOG) as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])


def run_vps_command(command: str) -> str:
    """Run a command on VPS and return output."""
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, VPS_HOST, command],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"
    return output


def main():
    params = json.load(sys.stdin)
    source = params.get("source", "telegram")
    lines = params.get("lines", 50)

    if source == "telegram":
        print(read_telegram_logs(lines))
    elif source == "discord":
        print(read_discord_logs(lines))
    elif source == "vps":
        command = params.get("command", "echo 'no command'")
        print(run_vps_command(command))
    else:
        print(f"Error: unknown source '{source}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
