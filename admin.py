#!/usr/bin/env python3
"""Admin Dev Agent — terminal-based development harness.

Same kernel, different vocab. Workspace is the source code.
Runs on dev branch. Reads architecture docs as system context.

Usage:
  cd v4.5/self && python3 admin.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import logging
logging.getLogger("dotenv.main").setLevel(logging.ERROR)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", verbose=False)

from chat2 import (
    run_turn, llm_call, llm_call_cached, AgentMemory,
    HAIKU, OPUS, SONNET, CLASSIFY_VOCAB,
    _register_from_preconditions,
)

# ── Configuration ──────────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent.parent  # KernelAgent/
WORKSPACE = str(BASE)  # Source code IS the workspace
MEM_DIR = str(BASE / "mem_admin")  # Separate memory from user agent
AGENT_ID = "admin_dev"
MAIN_SELF_JSON = str(BASE / "mem" / "agents" / "step_kernel" / "self.json")


def notify_main_agent(message: str):
    """Append a system event onto the main agent's trajectory."""
    import time
    atom = {
        "role": "user",
        "content": f"[admin] {message}",
        "_channel": "external",
        "_track": "admin_event",
        "_t": time.time(),
    }
    if os.path.isfile(MAIN_SELF_JSON):
        store = json.load(open(MAIN_SELF_JSON))
    else:
        store = []
    store.append(atom)
    json.dump(store, open(MAIN_SELF_JSON, "w"), indent=2, ensure_ascii=False)


# ── Admin Vocab ────────────────────────────────────────────────────────

# Admin vocab: full main vocab + admin-only tools
ADMIN_VOCAB = CLASSIFY_VOCAB + """

### Admin-only
- principles_update_needed: create, update, or retire principles in the Principles Store — \
fires when new principles are established or existing principles contradict the source code \
infrastructure and need updating/retiring. The Principles Store is ALWAYS VISIBLE above — \
you do NOT need to read it. Use this when: \
(1) you discover a NEW architectural fact not in the store, \
(2) you verify an existing principle is WRONG or outdated, \
(3) you discover a fact that CORRECTS or refines an existing principle. \
SCORING: if you read code and find something structurally important that contradicts or \
is missing from the Principles Store, score rel > 0.8. \
If user asks to update principles or ensure principles is current or up to date \
("update principles", "make sure principles is accurate", "sync principles with code"), score rel > 0.9
- tele_log_needed: read the Telegram bot logs from the VPS. Use to checking deployment \
status or diagnose issues on the production Telegram instance. \
SCORING: if user asks "is telegram running", "check the VPS", "is the bot online", \
"check telegram status", or any query about the telegram/VPS agent, score rel > 0.9
- discord_log_needed: read the Discord bot logs from the local instance. Use to checking \
deployment status or when diagnosing issues on the local Discord bot. \
SCORING: if user asks "is discord running", "check discord", "is the bot active", \
"check discord status", or any query about the discord/main agent, score rel > 0.9"""


# ── Principles Manager ────────────────────────────────────────────────

PRINCIPLES_MANAGER_SYSTEM = """\
You are the principles manager for a compile-driven agent architecture.

## What principles represent

Each principle is a MECHANISM — not a fact, not a description, not a code comment. \
A mechanism is a piece of the system's recursive architecture where every behavior \
composes from the same primitive: step(state, signal) -> (state', delta).

The principles store is the system's mental model of itself. It enables:
- Epistemic honesty through structure — every claim is verifiable against source
- Security in execution — the step primitive enforces observe-before-mutate at every scale
- Full visibility in reasoning — all LLMs see principles in context, ensuring coherent decisions
- No drift — principles are maintained against source code, not assumptions

## The recursion

Every principle must reflect how it embodies the step primitive at its scale:
- Pre-snapshot (observe state before action)
- State mutation (the change)
- Post-snapshot (observe result after action)
- Delta (what changed)

If a mechanism doesn't fit this shape, it's either a utility detail (don't store it) \
or you haven't found the right framing yet (think harder).

## Principle format

Each principle entry has:
- title: mechanism name (short, specific)
- fact: dense description covering what it is, key code locations, how it works, \
key thresholds/invariants. One paragraph, no newlines. Must include file:line references.
- source: primary code locations (file:line)
- category: architecture | pattern | invariant | threshold

## How this works

You run in a mini-loop. Each round you receive:
1. The CURRENT Principles Store (all active entries — refreshed after each action)
2. The full trajectory from this turn (everything the agent read and verified)
3. A round counter

Each round, you do ONE of:
- Output a single action (create, update, or retire) to fix ONE discrepancy
- Output {"action": "done"} when the store is consistent with the trajectory

You will be called again with the UPDATED store after each action. \
So fix one thing per round. The loop handles iteration.

## Actions — exact JSON format

Create: {"action": "create", "title": "Mechanism Name", "fact": "Dense description with file:line refs", "source": "file.rs:123", "category": "architecture"}
Update: {"action": "update", "principle_id": "exact_id_from_store", "fact": "Corrected fact with file:line refs", "source": "file.rs:456"}
Retire: {"action": "retire", "principle_id": "exact_id_from_store", "reason": "Why it is no longer true"}
Done: {"action": "done"}

## CRITICAL rules
- Output ONLY the JSON object. No markdown, no explanation, no backticks.
- All string values must be on ONE LINE. No newlines inside strings.
- Use the exact principle_id from the store for update/retire.
- Do NOT count items (tests, preconditions, files) — counts from batch scans are unreliable.
- Do NOT update a principle unless the SOURCE FILE it references was actually read in the trajectory.
- Do NOT retire a principle because its source file was not read — that means you need to read it, not retire it.
- Do NOT create principles for implementation details (variable names, utility functions, config values). \
Only create principles for MECHANISMS — things that embody the step primitive at some scale.
- Do NOT re-update a principle you already updated this session if the store already reflects your change.

## What to look for
Compare the trajectory (source code that was actually read) against the store:
- Missing mechanism: a behavioral pattern visible in code but absent from store → create
- Wrong fact: a principle's fact contradicts what the source code shows → update
- Outdated: a principle references something removed or renamed → update (not retire, unless mechanism is truly gone)
- Imprecise source: vague reference ("kernel.rs") when code shows exact line → update source field"""


def scan_source_tree(workspace: str) -> str:
    """Build a compact source tree listing for context injection."""
    skip = {"__pycache__", ".git", "mem", "mem_admin", "data", "node_modules", "target"}
    lines = ["## Source Tree\n"]
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in sorted(dirs) if d not in skip]
        depth = root.replace(workspace, "").count(os.sep)
        indent = "  " * depth
        dirname = os.path.basename(root) or os.path.basename(workspace)
        lines.append(f"{indent}{dirname}/")
        for f in sorted(files):
            if f.startswith(".") or f.endswith((".pyc", ".so", ".dylib")):
                continue
            if f == "principles.json":
                continue  # already in Principles Store context
            lines.append(f"{indent}  {f}")

    # Repo root files (outside workspace — design philosophy, contracts)
    repo_root = Path(workspace).parent.parent
    repo_files = {
        "CLAUDE.md": "design philosophy — core principles and change methodology",
        "contracts/change_gate.md": "mandatory pre-implementation gate for all code changes",
        "contracts/repo_map.md": "module map, entry points, state objects",
        "contracts/primitive_inventory.md": "all primitives mapped to code",
        "contracts/gaps.md": "known deployment/architecture/testing gaps",
    }
    lines.append("")
    lines.append("## Repo Root (outside workspace — use scan_needed with path ../../<file>)")
    for fpath, desc in repo_files.items():
        full = repo_root / fpath
        if full.exists():
            lines.append(f"  {fpath}  ({desc})")

    # Agent memory stores
    lines.append("")
    lines.append("## Agent Memory Stores")

    # Main agent (read-only from admin)
    main_mem = os.path.join(workspace, "mem", "agents", "step_kernel")
    if os.path.isdir(main_mem):
        lines.append("")
        lines.append("### Main Agent (read-only — use scan_needed with path mem/agents/step_kernel/<file>)")
        lines.append("Instance: Discord local + Telegram VPS | agent_id: step_kernel")
        lines.append("Path: mem/agents/step_kernel/")
        for f in sorted(os.listdir(main_mem)):
            if os.path.isfile(os.path.join(main_mem, f)):
                lines.append(f"  {f}")
        streams_dir = os.path.join(main_mem, "streams")
        if os.path.isdir(streams_dir):
            lines.append("  streams/")
            for f in sorted(os.listdir(streams_dir)):
                lines.append(f"    {f}")

    # Admin agent (own memory)
    admin_mem = os.path.join(workspace, "mem_admin", "agents", AGENT_ID)
    if os.path.isdir(admin_mem):
        lines.append("")
        lines.append(f"### Admin Dev Agent (own memory)")
        lines.append(f"Instance: Admin terminal | agent_id: {AGENT_ID}")
        lines.append(f"Path: mem_admin/agents/{AGENT_ID}/")
        for f in sorted(os.listdir(admin_mem)):
            if os.path.isfile(os.path.join(admin_mem, f)):
                lines.append(f"  {f}")
        admin_streams = os.path.join(admin_mem, "streams")
        if os.path.isdir(admin_streams):
            lines.append("  streams/")
            for f in sorted(os.listdir(admin_streams)):
                lines.append(f"    {f}")

    # Delegate stores (background task delegates)
    delegates_dir = os.path.join(workspace, "mem", "agents")
    if os.path.isdir(delegates_dir):
        delegate_dirs = [d for d in sorted(os.listdir(delegates_dir))
                        if d.startswith("delegate_") and os.path.isdir(os.path.join(delegates_dir, d))]
        if delegate_dirs:
            lines.append("")
            lines.append("### Task Delegates (background — keyed by commitment_id)")
            for d in delegate_dirs:
                cid = d.replace("delegate_", "")
                dpath = os.path.join(delegates_dir, d)
                files = [f for f in os.listdir(dpath) if os.path.isfile(os.path.join(dpath, f))]
                lines.append(f"  {d}/ (commitment: {cid}) — {len(files)} files")

    # Debug agent
    debug_mem = os.path.join(workspace, "mem", "agents", "self_debug")
    if os.path.isdir(debug_mem):
        lines.append("")
        lines.append("### Self-Debug Agent")
        lines.append("Path: mem/agents/self_debug/")
        for f in sorted(os.listdir(debug_mem)):
            if os.path.isfile(os.path.join(debug_mem, f)):
                lines.append(f"  {f}")

    # Debug reports
    debug_reports = os.path.join(workspace, "mem", "debug_reports")
    if os.path.isdir(debug_reports):
        reports = sorted(os.listdir(debug_reports))
        if reports:
            lines.append("")
            lines.append(f"### Debug Reports ({len(reports)} reports)")
            lines.append("Path: mem/debug_reports/")
            for f in reports[-5:]:  # show last 5
                lines.append(f"  {f}")
            if len(reports) > 5:
                lines.append(f"  ... and {len(reports) - 5} more")

    return "\n".join(lines)


def load_principles(workspace: str) -> str:
    """Load principles store and format for context injection."""
    path = os.path.join(workspace, "principles.json")
    if not os.path.isfile(path):
        return "(No principles stored yet)"
    store = json.load(open(path))
    active = [p for p in store if p.get("status") != "retired"]
    if not active:
        return "(No active principles)"
    lines = [f"## Principles Store ({len(active)} active)\n"]
    for p in active:
        lines.append(f"**[{p['principle_id']}]** {p['title']}")
        lines.append(f"  {p['fact']}")
        lines.append(f"  source: {p.get('source', '?')} | category: {p.get('category', '?')}")
        lines.append("")
    return "\n".join(lines)


# ── Admin REPL ─────────────────────────────────────────────────────────

ADMIN_BANNER = """
╔═══════════════════════════════════════════════════╗
║  Admin Dev Agent — Step Kernel Maintenance        ║
║  Workspace: source code (v4.5/self/)              ║
║  Branch: dev                                      ║
║  /quit /status /build /test /deploy /discord /kill /ps /commit  ║
╚═══════════════════════════════════════════════════╝
"""


def cmd_status():
    """Show current git and system status."""
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    ).stdout.strip()
    print(f"  Branch: {branch}")
    if diff:
        print(f"  Changes:\n{diff}")
    else:
        print("  No uncommitted changes")


def cmd_build():
    """Build the Rust crate locally."""
    print("  Building kernel_step...")
    result = subprocess.run(
        ["sh", "-c", "PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop"],
        cwd=str(BASE / "kernel_step"),
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  Build successful")
    else:
        print(f"  Build failed:\n{result.stderr[-500:]}")


def cmd_test():
    """Run the test suite."""
    print("  Running tests...")
    result = subprocess.run(
        ["sh", "-c", "PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test --no-default-features"],
        cwd=str(BASE / "kernel_step"),
        capture_output=True, text=True,
    )
    # Show last few lines (test summary)
    lines = result.stdout.strip().split("\n")
    for line in lines[-5:]:
        print(f"  {line}")
    if result.returncode != 0:
        print(f"  STDERR:\n{result.stderr[-300:]}")


def cmd_deploy():
    """Deploy to VPS (with confirmation)."""
    confirm = input("  Deploy to VPS? (y/n): ").strip().lower()
    if confirm != "y":
        print("  Cancelled")
        return

    print("  Deploying...")
    files = [
        ("kernel_step/src/kernel.rs", "v3/self/kernel_step/src/kernel.rs"),
        ("kernel_step/src/compile.rs", "v3/self/kernel_step/src/compile.rs"),
        ("kernel_step/src/quadrant.rs", "v3/self/kernel_step/src/quadrant.rs"),
        ("kernel_step/src/ledger.rs", "v3/self/kernel_step/src/ledger.rs"),
        ("kernel_step/src/memory.rs", "v3/self/kernel_step/src/memory.rs"),
        ("kernel_step/src/delta.rs", "v3/self/kernel_step/src/delta.rs"),
        ("kernel_step/src/render.rs", "v3/self/kernel_step/src/render.rs"),
        ("chat2.py", "v3/self/chat2.py"),
        ("preconditions.json", "v3/self/preconditions.json"),
    ]
    for local, remote in files:
        local_path = str(BASE / local)
        if os.path.exists(local_path):
            result = subprocess.run(
                ["scp", "-i", os.path.expanduser("~/.ssh/hetzner"),
                 local_path, f"root@89.167.61.222:/home/botuser/bot/{remote}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(f"  ✓ {local}")
            else:
                print(f"  ✗ {local}: {result.stderr[:100]}")

    # Build on VPS
    print("  Building on VPS...")
    result = subprocess.run(
        ["ssh", "-i", os.path.expanduser("~/.ssh/hetzner"),
         "root@89.167.61.222",
         "cd /home/botuser/bot/v3/self/kernel_step && "
         "export PATH='/root/.cargo/bin:/usr/bin:/usr/local/bin:$PATH' && "
         "export VIRTUAL_ENV='/home/botuser/bot/venv' && "
         "PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop 2>&1 | tail -3 && "
         "cp /home/botuser/bot/v3/self/chat2.py /home/botuser/bot/v3/self/data/principle/chat2.py && "
         "cp /home/botuser/bot/v3/self/preconditions.json /home/botuser/bot/v3/self/data/principle/preconditions.json && "
         "systemctl restart telegram-bot"],
        capture_output=True, text=True,
    )
    print(f"  {result.stdout.strip()[-200:]}")
    if result.returncode == 0:
        notify_main_agent("VPS deploy completed — Telegram bot restarted")
        print("  Deploy complete")
    else:
        print(f"  Deploy failed: {result.stderr[:200]}")


def cmd_ps():
    """Show running agent instances."""
    agents = {
        "discord_bot.py": "Discord Bot (local)",
        "telegram_bot2.py": "Telegram Bot (local)",
        "chat2.py": "Chat REPL",
        "scraper.py": "YouTube Scraper",
        "admin.py": "Admin Dev Agent",
    }
    result = subprocess.run(
        ["ps", "aux"], capture_output=True, text=True
    )
    found = []
    for line in result.stdout.splitlines():
        for script, label in agents.items():
            if script in line and "grep" not in line and "/ps" not in line:
                parts = line.split()
                pid = parts[1]
                found.append((label, script, pid))
    # Check VPS telegram bot
    vps = subprocess.run(
        ["ssh", "-i", os.path.expanduser("~/.ssh/hetzner"),
         "-o", "ConnectTimeout=3",
         "root@89.167.61.222",
         "systemctl is-active telegram-bot 2>/dev/null"],
        capture_output=True, text=True,
    )
    vps_status = vps.stdout.strip() if vps.returncode == 0 else "unreachable"

    if found:
        print("  Local instances:")
        for label, script, pid in found:
            print(f"    {label:<25} pid={pid}")
    else:
        print("  No local agent instances running")
    print(f"  VPS Telegram Bot:        {vps_status}")


def cmd_commit(message: str = ""):
    """Commit changes to dev branch."""
    if not message:
        message = input("  Commit message: ").strip()
    if not message:
        print("  Cancelled")
        return
    subprocess.run(["git", "add", "-A"], cwd=str(REPO_ROOT))
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    print(f"  {result.stdout.strip()[:200]}")
    # Push to dev
    subprocess.run(
        ["git", "push", "origin", "dev"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    print("  Pushed to origin/dev")


def repl():
    """Admin Dev REPL."""
    print(ADMIN_BANNER)

    # Load principles store
    principles_text = load_principles(WORKSPACE)
    p_count = principles_text.count("[") - 1 if "active" in principles_text else 0
    print(f"  Principles loaded ({p_count} active)")

    # Check git branch
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    ).stdout.strip()
    print(f"  Git branch: {branch}")
    if branch != "dev":
        print(f"  WARNING: Not on dev branch! Switch with: git checkout dev")
    print()

    # Create admin memory (separate from user agent)
    os.makedirs(MEM_DIR, exist_ok=True)
    os.makedirs(os.path.join(MEM_DIR, "agents", AGENT_ID), exist_ok=True)
    os.makedirs(os.path.join(MEM_DIR, "units"), exist_ok=True)
    # Seed empty registry if needed
    reg_path = os.path.join(MEM_DIR, "agents", AGENT_ID, "registry.json")
    if not os.path.exists(reg_path):
        open(reg_path, "w").write("[]")
    memory = AgentMemory(AGENT_ID, MEM_DIR, "registry.json")
    child_procs = []  # track launched subprocesses — killed on exit

    def cleanup_children():
        for name, proc in child_procs:
            if proc.poll() is None:  # still running
                print(f"  Stopping {name} (pid={proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                notify_main_agent(f"{name} stopped (admin exit)")

    while True:
        try:
            user_input = input("admin> ").strip()
        except (EOFError, KeyboardInterrupt):
            cleanup_children()
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        # Built-in commands
        if user_input == "/quit":
            cleanup_children()
            print("Goodbye.")
            break
        elif user_input == "/status":
            cmd_status()
            continue
        elif user_input == "/build":
            cmd_build()
            continue
        elif user_input == "/test":
            cmd_test()
            continue
        elif user_input == "/deploy":
            cmd_deploy()
            continue
        elif user_input == "/discord":
            print("  Starting Discord bot...")
            proc = subprocess.Popen(
                ["python3", "-u", "discord_bot.py"],
                cwd=str(BASE),
                stdout=open(str(BASE / "bot.log"), "a"),
                stderr=subprocess.STDOUT,
            )
            child_procs.append(("discord_bot.py", proc))
            notify_main_agent("Discord bot launched (local)")
            print(f"  Discord bot launched (pid={proc.pid}, logs: bot.log)")
            continue
        elif user_input.startswith("/kill"):
            target = user_input[5:].strip()
            if not target:
                print("  Usage: /kill <discord|scraper>")
                continue
            scripts = {"discord": "discord_bot.py", "scraper": "scraper.py"}
            script = scripts.get(target, target)
            result = subprocess.run(
                ["pkill", "-f", script], capture_output=True, text=True
            )
            if result.returncode == 0:
                notify_main_agent(f"{script} stopped")
                print(f"  Killed {script}")
            else:
                print(f"  No process found for {script}")
            continue
        elif user_input == "/ps":
            cmd_ps()
            continue
        elif user_input.startswith("/commit"):
            msg = user_input[7:].strip()
            cmd_commit(msg)
            continue

        # Agent turn — override workspace + vocab + principles hook + dedicated manager
        import chat2
        original_workspace = chat2.WORKSPACE
        original_vocab = chat2.CLASSIFY_VOCAB
        original_hook = chat2.POST_PRELOAD_HOOK
        original_iter_hook = chat2.ITER_HOOK
        original_managers = chat2.DEDICATED_MANAGERS.copy()
        original_inline = chat2.INLINE_TASK_RESOLVE

        def inject_admin_context(turn, memory):
            """Build admin context: identity + commitments + principles + source tree."""
            parts = [
                "## Identity\n"
                "You are the Admin Dev Agent — a development instance of the Step Kernel. "
                "You are maintaining and developing YOURSELF. The source code in your workspace "
                "IS the system you are running on. Your user is the developer who built you. "
                "Respond in a terminal, not Telegram — no TTS, no chat bubbles. "
                "Be technical, direct, and precise. Reference files, lines, and functions by name.\n\n"
                "## Synthesis Discipline\n"
                "When composing your response, review the trajectory from this turn against "
                "the Principles below. If anything in the execution path violated a principle "
                "(wrong tool routing, ceiling breach, skipped observation, stale data used as "
                "evidence, gap re-creation loop, or any other deviation), flag it briefly at "
                "the end of your response. Format: '[principle-check] <observation>'. "
                "If nothing seems off, do not mention it."
            ]

            # Active commitments from admin's registry
            commitments = memory.active_commitments_native()

            if commitments:
                summary = f"{len(commitments)} active commitment(s):\n"
                for c in commitments:
                    title = c.get("title", "?")
                    cid = c.get("commitment_id", "")
                    status = c.get("status", "open")
                    summary += f"- [{status}] {title} (id: {cid})\n"
                    for r in c.get("requirements", []):
                        summary += f"  req: {r}\n"
                parts.append(summary)

            # Principles store
            parts.append(load_principles(WORKSPACE))

            # Source tree
            parts.append(scan_source_tree(WORKSPACE))

            turn.set_commitments_summary("\n\n".join(parts))
            # Populate known_files for bare filename resolution
            turn.set_workspace_tree(chat2.scan_workspace_tree(WORKSPACE))
            turn.set_git_log(chat2.scan_git_log())

        chat2.WORKSPACE = WORKSPACE  # Source code as workspace
        chat2.CLASSIFY_VOCAB = ADMIN_VOCAB  # Admin vocab with principles_needed
        chat2.POST_PRELOAD_HOOK = inject_admin_context  # Commitments + principles + source tree
        chat2.ITER_HOOK = inject_admin_context  # Per-iteration refresh (source tree + principles)
        chat2.DEDICATED_MANAGERS["principles_update_needed"] = PRINCIPLES_MANAGER_SYSTEM
        chat2.INLINE_TASK_RESOLVE = True  # Disperse tasks into current turn, no background delegate
        try:
            turn, response = run_turn(user_input, memory, contact_id=AGENT_ID)
            print(f"\n{response}\n")

        except Exception as e:
            print(f"\nError: {e}\n")
            import traceback
            traceback.print_exc()
        finally:
            chat2.WORKSPACE = original_workspace
            chat2.CLASSIFY_VOCAB = original_vocab
            chat2.POST_PRELOAD_HOOK = original_hook
            chat2.ITER_HOOK = original_iter_hook
            chat2.DEDICATED_MANAGERS = original_managers
            chat2.INLINE_TASK_RESOLVE = original_inline


if __name__ == "__main__":
    repl()
