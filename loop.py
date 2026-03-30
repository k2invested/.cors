"""Minimal v5 turn loop.

One turn: perception → governor → action → synth.

Components:
  - Persistent 5.4 (pre-diff): reads trajectory, emits comments with hash refs
  - Mini (post-diff): scores perception, builds gaps
  - Governor: monitors convergence, gates action
  - 5.4 (action): composes commands when governor says ACT
  - Kernel: resolves hashes, executes commands, auto-commits
"""

import json
import os
import subprocess
import time
from openai import OpenAI
from step import Step, PreDiff, PostDiff, Gap, ChainLink, Epistemic, blob_hash

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── Storage ──────────────────────────────────────────────────────────────

SANDBOX = os.path.join(os.path.dirname(__file__), "sandbox")
TRAJECTORY_FILE = os.path.join(SANDBOX, "trajectory.json")


def init_sandbox():
    """Initialize sandbox as a git repo with initial commit."""
    os.makedirs(SANDBOX, exist_ok=True)
    if not os.path.exists(os.path.join(SANDBOX, ".git")):
        subprocess.run(["git", "init"], cwd=SANDBOX, capture_output=True)
        subprocess.run(["git", "config", "user.email", "kernel@step.v5"], cwd=SANDBOX, capture_output=True)
        subprocess.run(["git", "config", "user.name", "StepKernel"], cwd=SANDBOX, capture_output=True)
    # Ensure trajectory file exists
    if not os.path.exists(TRAJECTORY_FILE):
        with open(TRAJECTORY_FILE, "w") as f:
            json.dump([], f)
    # Initial commit if none exists
    result = subprocess.run(["git", "log", "--oneline", "-1"], cwd=SANDBOX, capture_output=True, text=True)
    if not result.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=SANDBOX, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial state", "--allow-empty"], cwd=SANDBOX, capture_output=True)


def get_workspace_tree() -> str:
    """Get the current workspace file listing."""
    result = subprocess.run(
        ["find", ".", "-not", "-path", "./.git/*", "-not", "-name", ".git", "-type", "f"],
        cwd=SANDBOX, capture_output=True, text=True
    )
    files = sorted(result.stdout.strip().split("\n")) if result.stdout.strip() else []
    return "\n".join(f"  {f}" for f in files)


def get_current_commit() -> str:
    """Get the current HEAD commit hash."""
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=SANDBOX, capture_output=True, text=True)
    return result.stdout.strip()


def load_trajectory() -> list[dict]:
    """Load trajectory from disk."""
    with open(TRAJECTORY_FILE) as f:
        return json.load(f)


def save_step(step: Step):
    """Append step to trajectory."""
    trajectory = load_trajectory()
    trajectory.append(step.to_dict())
    with open(TRAJECTORY_FILE, "w") as f:
        json.dump(trajectory, f, indent=2)


def auto_commit(message: str) -> str:
    """Git add + commit, return SHA."""
    subprocess.run(["git", "add", "-A"], cwd=SANDBOX, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=SANDBOX, capture_output=True)
    return get_current_commit()


def read_file(path: str) -> str | None:
    """Read a file from the sandbox."""
    full = os.path.join(SANDBOX, path)
    if os.path.exists(full):
        with open(full) as f:
            return f.read()
    return None


# ── Hash store ───────────────────────────────────────────────────────────

hash_store: dict[str, dict] = {}  # hash → resolved data


def register_commit(commit_sha: str, workspace_tree: str):
    """Register a commit hash with its workspace data."""
    hash_store[commit_sha] = {
        "type": "commit",
        "workspace_tree": workspace_tree,
        "sha": commit_sha,
    }


def register_step(step: Step):
    """Register a step's blob hash."""
    hash_store[step.hash] = {
        "type": "step",
        "content": step.content,
        "pre_refs": step.pre.refs(),
        "gaps": [{"desc": g.desc, "refs": g.refs} for g in step.post.gaps],
        "commit": step.post.commit,
    }


def resolve_hash(h: str) -> dict | None:
    """Resolve a hash to its data."""
    return hash_store.get(h)


# ── LLM calls ────────────────────────────────────────────────────────────

PERCEPTION_SYSTEM = """You are a perception engine. You observe the current state and reason about it.

You receive:
- The current workspace commit (hash + file tree)
- The trajectory (prior steps with hashes)
- A user message

Your job: produce a JSON response with your reasoning and which hashes you attended to.

If you need to see a file's contents, describe what you need in your reasoning.
If you can answer from what's visible, say so.

Respond with JSON:
{
  "chain": ["<hashes you attended to from the context>"],
  "content": "<your reasoning — what you observed, what you think, what you need>",
  "needs_file": "<filename if you need to read a file, null otherwise>"
}

Respond ONLY with JSON."""

POST_SYSTEM = """You are a gap assessment engine. You read the perception output and determine what gaps remain.

You receive the perception engine's reasoning and the context it saw.

Your job: produce structured gaps that need to be resolved, or empty gaps if nothing more is needed.

CRITICAL DISTINCTION:
- If the user ASKED A QUESTION and the perception has the answer → NO gaps (auto-synth)
- If the user REQUESTED A CHANGE/ACTION and it hasn't been done yet → GAP (action needed)
- Knowing what needs to change is NOT the same as having changed it
- A file edit, command execution, or any mutation that hasn't happened yet = gap

Each gap needs:
- desc: what needs to happen
- refs: which hashes justify this gap
- confidence: 0.0-1.0 how confident you are about what action to take (high = clear action, low = unclear)

Respond with JSON:
{
  "gaps": [
    {"desc": "...", "refs": ["..."], "confidence": 0.8}
  ]
}

Respond ONLY with JSON."""

ACTION_SYSTEM = """You are a command composer. You write shell commands to resolve gaps.

You receive: the gap to resolve, the workspace tree, and any file contents available.

Write a single shell command that resolves the gap. The command runs in the sandbox directory.
This is macOS — use POSIX-compatible commands.

For file edits, use python3 one-liners:
  python3 -c "import json; d=json.load(open('file.json')); d['key']='value'; json.dump(d,open('file.json','w'),indent=2)"

Do NOT use sed -i (macOS incompatible). Use python3 for JSON edits. Use cat/echo for simple writes.

Respond with JSON:
{
  "command": "<the shell command>",
  "reasoning": "<why this resolves the gap>"
}

Respond ONLY with JSON."""

SYNTH_SYSTEM = """You are the response synthesizer. You read the full trajectory of a turn and produce a natural response to the user.

Keep it concise and conversational. Do not mention internal systems, hashes, or technical details.
Just answer the user's question or confirm what was done.

Respond with plain text, not JSON."""


def call_llm(system: str, user_content: str, model: str = "gpt-4.1-mini") -> str:
    """Single LLM call."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


# ── Turn loop ─────────────────────────────────────────────────────────────

def render_context(commit_sha: str, trajectory: list[dict], user_message: str, extra: str = "") -> str:
    """Render the context for LLM injection."""
    workspace_tree = get_workspace_tree()
    traj_str = ""
    if trajectory:
        for s in trajectory[-10:]:  # last 10 steps
            refs = s.get("pre", {}).get("chain", [])
            ref_hashes = [r["hash"] for r in refs]
            gaps = s.get("post", {}).get("gaps", [])
            gap_strs = [g["desc"] for g in gaps]
            traj_str += f"\n[{s['hash']}] attending: {ref_hashes}\n"
            traj_str += f"  \"{s['content'][:150]}\"\n"
            if gaps:
                traj_str += f"  gaps: {gap_strs}\n"
            if s.get("post", {}).get("commit"):
                traj_str += f"  commit: {s['post']['commit']}\n"
    else:
        traj_str = "(empty — first turn)"

    ctx = f"""## Current State

Commit: {commit_sha}
Workspace tree:
{workspace_tree}

## Trajectory
{traj_str}

## User Message
"{user_message}"
"""
    if extra:
        ctx += f"\n## Additional Context\n{extra}\n"
    return ctx


def run_turn(user_message: str) -> str:
    """Run one turn. Returns the synthesis response."""

    init_sandbox()
    commit_sha = get_current_commit()
    register_commit(commit_sha, get_workspace_tree())
    trajectory = load_trajectory()

    print(f"\n{'='*60}")
    print(f"TURN: \"{user_message}\"")
    print(f"Commit: {commit_sha}")
    print(f"{'='*60}")

    # ── Phase 1: Perception ──────────────────────────────────────────

    print("\n── PERCEPTION ──")
    context = render_context(commit_sha, trajectory, user_message)
    perception_raw = call_llm(PERCEPTION_SYSTEM, context)
    print(f"Raw: {perception_raw[:300]}")

    try:
        perception = json.loads(perception_raw)
    except json.JSONDecodeError:
        perception = {"chain": [commit_sha], "content": perception_raw, "needs_file": None}

    # Build pre-diff from perception
    chain = [ChainLink(hash=h, parent=None) for h in perception.get("chain", [])]
    pre = PreDiff(chain=chain)

    # If perception needs a file, resolve it and re-perceive
    extra = ""
    if perception.get("needs_file"):
        fname = perception["needs_file"]
        file_content = read_file(fname)
        if file_content:
            extra = f"File: {fname}\nContents:\n{file_content}"
            print(f"  → Resolved file: {fname}")
            context = render_context(commit_sha, trajectory, user_message, extra)
            perception_raw = call_llm(PERCEPTION_SYSTEM, context)
            print(f"  → Re-perception: {perception_raw[:200]}")
            try:
                perception = json.loads(perception_raw)
            except json.JSONDecodeError:
                perception = {"chain": [commit_sha], "content": perception_raw, "needs_file": None}
            chain = [ChainLink(hash=h, parent=None) for h in perception.get("chain", [])]
            pre = PreDiff(chain=chain)

    # ── Phase 2: Post-diff (gap assessment) ──────────────────────────

    print("\n── GAP ASSESSMENT ──")
    post_context = f"""Perception output:
{json.dumps(perception, indent=2)}

Context seen:
{context}"""

    post_raw = call_llm(POST_SYSTEM, post_context)
    print(f"Raw: {post_raw[:300]}")

    try:
        post_data = json.loads(post_raw)
    except json.JSONDecodeError:
        post_data = {"gaps": []}

    gaps = [
        Gap(
            desc=g["desc"],
            refs=g.get("refs", []),
            origin=commit_sha,
            confidence=g.get("confidence", 0.5),
        )
        for g in post_data.get("gaps", [])
    ]

    post = PostDiff(gaps=gaps)

    # Record perception step
    step = Step.new(
        content=perception.get("content", ""),
        pre=pre,
        post=post,
    )
    save_step(step)
    register_step(step)
    print(f"Step: {step.hash} | chain depth: {pre.depth()} | gaps: {len(gaps)}")

    # ── Phase 3: Governor ────────────────────────────────────────────

    print("\n── GOVERNOR ──")
    if not gaps:
        print("No gaps → auto-synth")
    else:
        for g in gaps:
            print(f"  Gap: {g.desc} (confidence: {g.confidence})")

        # ── Phase 4: Action loop ─────────────────────────────────────
        max_actions = 5
        for action_i in range(max_actions):
            print(f"\n── ACTION {action_i + 1} ──")

            # Select widest gap
            target = min(gaps, key=lambda g: g.confidence)
            print(f"Target: {target.desc}")

            # Compose command
            action_context = f"""Gap to resolve: {target.desc}
Evidence refs: {target.refs}

Workspace tree:
{get_workspace_tree()}

{extra}"""
            action_raw = call_llm(ACTION_SYSTEM, action_context, model="gpt-4.1-mini")
            print(f"Action: {action_raw[:200]}")

            try:
                action = json.loads(action_raw)
            except json.JSONDecodeError:
                print("  → Failed to parse action, skipping")
                break

            command = action.get("command", "")
            if not command:
                break

            # Execute
            print(f"  → Executing: {command}")
            result = subprocess.run(
                command, shell=True, cwd=SANDBOX,
                capture_output=True, text=True, timeout=10,
            )
            stdout = result.stdout[:500] if result.stdout else ""
            stderr = result.stderr[:500] if result.stderr else ""
            print(f"  → stdout: {stdout[:100]}")
            if stderr:
                print(f"  → stderr: {stderr[:100]}")

            # Check for errors
            if result.returncode != 0:
                print(f"  → Command failed (exit {result.returncode})")
                action_step = Step.new(
                    content=f"FAILED: {command}\nError: {stderr[:200]}",
                    pre=PreDiff(chain=[ChainLink(hash=step.hash, parent=None)]),
                    post=PostDiff(),
                )
                save_step(action_step)
                register_step(action_step)
                extra = f"Command failed:\n{stderr}"
                continue

            # Auto-commit if files changed
            diff_result = subprocess.run(["git", "diff", "--stat"], cwd=SANDBOX, capture_output=True, text=True)
            untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=SANDBOX, capture_output=True, text=True)
            has_changes = bool(diff_result.stdout.strip() or untracked.stdout.strip())

            if has_changes:
                new_commit = auto_commit(f"action: {target.desc[:50]}")
                print(f"  → Committed: {new_commit}")

                # Verify mutation — read back the changed file
                git_diff = subprocess.run(
                    ["git", "diff", "HEAD~1", "--", "."], cwd=SANDBOX,
                    capture_output=True, text=True
                )
                diff_output = git_diff.stdout[:500] if git_diff.stdout else "(no diff)"
                print(f"  → Verified diff: {diff_output[:100]}")

                action_step = Step.new(
                    content=f"Executed: {command}\nResult: {stdout[:200]}\nDiff: {diff_output[:200]}",
                    pre=PreDiff(chain=[ChainLink(hash=step.hash, parent=None)]),
                    post=PostDiff(commit=new_commit),
                )
                save_step(action_step)
                register_step(action_step)
                extra = f"Command output:\n{stdout}\nVerified diff:\n{diff_output}"
            else:
                print("  → No file changes detected — command may have failed silently")
                action_step = Step.new(
                    content=f"Observed: {command}\nResult: {stdout[:200]}\nNote: no file changes detected",
                    pre=PreDiff(chain=[ChainLink(hash=step.hash, parent=None)]),
                    post=PostDiff(),
                )
                save_step(action_step)
                register_step(action_step)
                extra = f"Observation result:\n{stdout}\n(no file changes)"

            # Re-assess gaps
            trajectory = load_trajectory()
            reassess_context = render_context(get_current_commit(), trajectory, user_message, extra)
            post_raw = call_llm(POST_SYSTEM, f"Perception output:\n{json.dumps({'content': action_step.content, 'chain': action_step.pre.refs()}, indent=2)}\n\nContext:\n{reassess_context}")
            try:
                post_data = json.loads(post_raw)
            except json.JSONDecodeError:
                post_data = {"gaps": []}

            gaps = [
                Gap(desc=g["desc"], refs=g.get("refs", []), confidence=g.get("confidence", 0.5))
                for g in post_data.get("gaps", [])
            ]

            if not gaps:
                print("All gaps closed")
                break

            open_gaps = [g for g in gaps if g.confidence < 0.8]
            if not open_gaps:
                print("All gaps above threshold")
                break

    # ── Phase 5: Synthesis ───────────────────────────────────────────

    print("\n── SYNTHESIS ──")
    trajectory = load_trajectory()
    synth_context = f"""Turn trajectory:
{json.dumps(trajectory[-5:], indent=2)}

User message: "{user_message}"
"""
    response = call_llm(SYNTH_SYSTEM, synth_context, model="gpt-4.1-mini")
    print(f"Response: {response}")

    return response


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Create a test file in the sandbox
    init_sandbox()
    config_path = os.path.join(SANDBOX, "config.json")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            json.dump({
                "model_id": "gpt-4o-2024-08-06",
                "temperature": 0.7,
                "max_tokens": 4096,
            }, f, indent=2)
        auto_commit("add config.json")

    print("v5 Step Kernel — REPL")
    print("Type /quit to exit, /wipe to reset sandbox\n")
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break
        if not user_input:
            continue
        if user_input == "/quit":
            break
        if user_input == "/wipe":
            import shutil
            if os.path.exists(SANDBOX):
                shutil.rmtree(SANDBOX)
            hash_store.clear()
            init_sandbox()
            print("sandbox wiped")
            continue
        response = run_turn(user_input)
        print(f"\nv5> {response}\n")
