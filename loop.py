"""loop.py — The Turn Loop (Layer 2)

One turn: message → first step → identity → iteration → synthesis.

The loop orchestrates a persistent LLM session (5.4) that iterates
with itself. The LLM's context accumulates:
  - Trajectory as a traversable hash tree (initial seed)
  - HEAD commit tree (workspace state)
  - User message
  - Freshly resolved hash data (per iteration)
  - Its own reasoning (pre-diff articulations, post-diff scores)

The kernel's job: resolve hashes, execute tools, auto-commit, inject
results back into the session. The LLM's job: navigate the hash tree,
articulate gaps, compose commands.

Turn flow:
  1. Message arrives
  2. Load trajectory + skills + HEAD
  3. First LLM pass → first atomic step (pre-diff + post-diff)
  4. Identity .st fires (admin.st surfaces user profile into context)
  5. Compiler admits gaps → ledger populated
  6. Loop: pop gap → execute by vocab → inject result → next step
     - Deterministic: kernel resolves directly (scan, hash_resolve)
     - Composed: 5.4 composes command (script_edit, command, content)
     - Observation-only: resolve + inject, no post-diff (blob step)
  7. Mutation → auto-commit → postcondition observation
  8. HALT → synthesize response from session

Mechanisms served: §2, §3, §5, §6, §17, §18, §19
"""

import json
import os
import subprocess
import time
from pathlib import Path

from step import Step, Gap, Epistemic, Trajectory
from compile import (
    Compiler, GovernorSignal,
    is_observe, is_mutate,
)
from skills.loader import load_all, SkillRegistry, Skill


# ── Configuration ────────────────────────────────────────────────────────

CORS_ROOT    = Path(__file__).parent
SKILLS_DIR   = CORS_ROOT / "skills"
TRAJ_FILE    = CORS_ROOT / "trajectory.json"
CHAINS_FILE  = CORS_ROOT / "chains.json"
MAX_ITERATIONS = 30
TRAJECTORY_WINDOW = 10   # how many recent chains to render for LLM


# ── Git operations ───────────────────────────────────────────────────────

def git(cmd: list[str], cwd: str = None) -> str:
    """Run a git command, return stdout."""
    result = subprocess.run(
        ["git"] + cmd,
        cwd=cwd or str(CORS_ROOT),
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def git_head() -> str:
    """Current HEAD commit hash (short)."""
    return git(["rev-parse", "--short", "HEAD"])


def git_tree(commit: str = "HEAD") -> str:
    """List files at a commit as a tree."""
    return git(["ls-tree", "--name-only", "-r", commit])


def git_show(ref: str) -> str:
    """Resolve a git object (blob, tree, commit) to its content."""
    result = subprocess.run(
        ["git", "show", ref],
        cwd=str(CORS_ROOT),
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return f"(unresolvable: {ref})"


def git_diff(from_ref: str, to_ref: str = "HEAD") -> str:
    """Diff between two commits."""
    return git(["diff", from_ref, to_ref])


def auto_commit(message: str) -> str | None:
    """Stage all changes and commit. Returns SHA or None if nothing to commit."""
    # Check for changes
    status = git(["status", "--porcelain"])
    if not status:
        return None
    git(["add", "-A"])
    git(["commit", "-m", message])
    return git_head()


# ── Hash resolution ──────────────────────────────────────────────────────

def resolve_hash(ref: str, trajectory: Trajectory) -> str | None:
    """Resolve any hash to its content.

    Resolution order:
      1. Step hash → step data from trajectory
      2. Gap hash → gap data from trajectory
      3. Git object → git show (blob/tree/commit)
    """
    # Try trajectory step
    step = trajectory.resolve(ref)
    if step:
        refs = step.step_refs + step.content_refs
        gaps = [f"  gap:{g.hash} \"{g.desc}\"" for g in step.gaps]
        lines = [f"step:{ref} \"{step.desc}\""]
        if refs:
            lines.append(f"  refs: {refs}")
        if gaps:
            lines.extend(gaps)
        if step.commit:
            lines.append(f"  commit: {step.commit}")
        return "\n".join(lines)

    # Try trajectory gap
    gap = trajectory.resolve_gap(ref)
    if gap:
        lines = [f"gap:{ref} \"{gap.desc}\""]
        if gap.content_refs:
            lines.append(f"  content_refs: {gap.content_refs}")
        if gap.step_refs:
            lines.append(f"  step_refs: {gap.step_refs}")
        lines.append(f"  scores: rel={gap.scores.relevance:.2f} conf={gap.scores.confidence:.2f} gr={gap.scores.grounded:.2f}")
        return "\n".join(lines)

    # Try git object
    content = git_show(ref)
    if not content.startswith("(unresolvable"):
        return content

    return None


def resolve_all_refs(step_refs: list[str], content_refs: list[str],
                     trajectory: Trajectory) -> str:
    """Resolve all hash references and format as injection block."""
    blocks = []
    for ref in step_refs:
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── resolved step:{ref} ──\n{data}")
    for ref in content_refs:
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── resolved {ref} ──\n{data}")
    return "\n\n".join(blocks) if blocks else ""


# ── Tool execution ───────────────────────────────────────────────────────

TOOL_MAP = {
    # Observation tools (deterministic — kernel resolves, no LLM needed)
    "scan_needed":          "tools/scan_tree.py",
    "hash_resolve_needed":  None,  # handled inline by resolve_hash
    "pattern_needed":       "tools/file_grep.py",
    "url_needed":           "tools/url_fetch.py",
    "email_needed":         "tools/email_check.py",
    "research_needed":      "tools/research_web.py",
    "registry_needed":      "tools/registry_query.py",
    "external_context":     None,  # LLM surfaces from context

    # Mutation tools (composed — 5.4 writes the command)
    "content_needed":       "tools/file_write.py",
    "script_edit_needed":   "tools/file_edit.py",
    "command_needed":       "tools/code_exec.py",
    "message_needed":       "tools/email_send.py",
    "json_patch_needed":    "tools/json_patch.py",
    "git_revert_needed":    "tools/git_ops.py",
}

# Deterministic vocabs — kernel resolves without LLM
DETERMINISTIC_VOCAB = {
    "scan_needed", "hash_resolve_needed", "registry_needed",
}

# Observation-only vocabs — resolve into context, no post-diff (blob step)
OBSERVATION_ONLY_VOCAB = {
    "hash_resolve_needed", "external_context",
}


def execute_tool(tool_path: str, params: dict) -> tuple[str, int]:
    """Execute a tool script as subprocess. Returns (output, exit_code)."""
    full_path = CORS_ROOT / tool_path
    if not full_path.exists():
        return f"(tool not found: {tool_path})", 1

    result = subprocess.run(
        ["python3", str(full_path)],
        input=json.dumps(params),
        capture_output=True, text=True,
        timeout=30,
        cwd=str(CORS_ROOT),
    )
    output = result.stdout or result.stderr or "(no output)"
    return output.strip(), result.returncode


# ── LLM session ──────────────────────────────────────────────────────────

class Session:
    """Persistent LLM session for one turn.

    Accumulates messages. The LLM's own outputs stay in context.
    New data gets injected as user messages (resolved hashes, tool output).
    """

    def __init__(self, model: str = "gpt-4.1"):
        self.model = model
        self.messages: list[dict] = []

    def set_system(self, content: str):
        """Set the system message (once, at turn start)."""
        self.messages = [{"role": "system", "content": content}]

    def inject(self, content: str, role: str = "user"):
        """Inject content into the session."""
        self.messages.append({"role": role, "content": content})

    def call(self, user_content: str = None) -> str:
        """Call the LLM. Optionally inject user content first."""
        if user_content:
            self.inject(user_content)

        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=0,
        )

        reply = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def message_count(self) -> int:
        return len(self.messages)


# ── System prompts ───────────────────────────────────────────────────────

PRE_DIFF_SYSTEM = """You are a hash-native reasoning agent. Everything you know, reference, and produce is a step — addressed by hash, connected by chains.

## What is a step?

A step is meaningful movement. It is the universal primitive. Everything is a step at different scales:
- A person is a step (identity hash — kenny:72b1d5ffc964)
- A workflow is a step (skill hash — research:a72c3c4dec0c)
- An idea is a step (reasoning articulation with hash refs)
- An event is a step (observation with commit hash)
- A task you did is a step (mutation with commit SHA)
- A task you plan to do is a step (gap articulation with vocab mapping)
- A file, a config, a conversation — all steps, all hashed, all chainable

Steps connect to other steps via hash references, forming chains. Chains compress into single hashes. Everything is traversable.

## What is a gap?

A gap is a verifiable discrepancy between the current state and its referred context — either as missing information or unmet alignment.

Two types (both diagnostic, never prescriptive):
- Observational gaps — information is missing, inconsistent, or unverified
- Misalignment gaps — the current state does not satisfy the referred context

Articulation form:
  Reference: [what the referred context requires]
  Current: [what the evidence actually shows]
  → Emit as single concise statement

A gap is NOT a suggestion. It is a measurement. You measure what is missing or misaligned, grounded in specific hash references.

If there are no gaps — nothing is missing, nothing is misaligned — emit empty gaps. The system will auto-synthesize.

## How to score gaps (the epistemic triad)

Every gap carries three scores:

- relevance (0-1): how much does resolving this advance the trajectory toward the shared goal?
  1.0 = critical path. 0.0 = does not advance.
  Evaluative form: "If this gap were resolved, would it move the system closer to the goal?"

- confidence (0-1): how safe and trustworthy is this to act on?
  1.0 = safe to trust and proceed. 0.0 = unsafe, uncertain, or unverifiable.
  Evaluative form: "Do I have enough evidence to act on this, or am I assuming?"

- grounded (0-1): is this consistent with verified constraints and observed evidence?
  1.0 = directly observed, references specific hashes. 0.0 = assumed or fabricated.
  Evaluative form: "Can I point to the exact hash that grounds this gap?"

Low-scoring gaps (all three below 0.2) become dormant — stored on the trajectory as peripheral vision, not acted on unless they recur.

## Hash references (two layers, never mixed)

When you articulate a gap, ground it in hashes:

- step_refs: reasoning steps you followed to reach this gap (Layer 1 — the causal chain)
- content_refs: data you need resolved — blobs, trees, commits, skill hashes (Layer 2 — the evidence)

The kernel resolves content_refs for you. If you reference a hash, the kernel will inject its content into your context. If you don't reference hashes, you are reasoning from assumption — which means grounded = 0.

## Vocab mapping

Each gap maps to a vocab term that tells the kernel HOW to resolve it:

OBSERVE (kernel resolves, you receive data):
  scan_needed — read workspace files
  pattern_needed — search file contents by pattern
  hash_resolve_needed — resolve step/gap/blob hashes from trajectory
  research_needed — web research
  email_needed — check email
  url_needed — fetch URL content
  registry_needed — query agent registry
  external_context — surface from current context

MUTATE (you compose a command, kernel executes):
  content_needed — write a new file
  script_edit_needed — edit an existing file
  command_needed — execute a shell command
  message_needed — send an email/message
  json_patch_needed — surgical JSON edit
  git_revert_needed — git revert/checkout

BRIDGE (internal routing):
  judgment_needed — requires judgment call
  task_needed — delegate to background task
  commitment_needed — track a commitment
  profile_needed — update contact profile
  task_status_needed — check task progress

If no action is needed, emit no gaps.

## Your context

You receive:
- A trajectory rendered as a traversable hash tree (chains → steps → gaps → refs)
- The current HEAD commit hash (workspace state)
- A user message
- Identity (who you're talking to — loaded as a skill hash)

## Output format

Reason naturally with embedded hash references. Then emit a JSON block:

```json
{
  "gaps": [
    {
      "desc": "concise gap articulation",
      "step_refs": ["step hashes you followed"],
      "content_refs": ["content hashes you need resolved"],
      "vocab": "closest_vocab_term",
      "relevance": 0.0,
      "confidence": 0.0,
      "grounded": 0.0
    }
  ]
}
```
"""

COMPOSE_SYSTEM = """You are composing a command to resolve a gap.

You receive the gap description, its hash references (now resolved), and the workspace context.

Produce a JSON response:

```json
{
  "command": "<shell command or tool params>",
  "reasoning": "<why this resolves the gap>"
}
```

For file edits, prefer python3 one-liners over sed (macOS compatible).
For JSON mutations, use the json_patch tool format.
"""

SYNTH_SYSTEM = """You are the response synthesizer. Read the full session and produce a natural response to the user.

Keep it concise and conversational. Do not mention internal systems, hashes, or trajectory.
Just answer the user's question or confirm what was done."""


# ── Turn loop ────────────────────────────────────────────────────────────

def run_turn(user_message: str, contact_id: str = "admin") -> str:
    """Run one complete turn. Returns the synthesis response.

    Flow:
      1. Load trajectory + skills + HEAD
      2. First LLM pass → first atomic step (pre-diff + post-diff)
      3. Identity .st fires (surfaces user profile)
      4. Compiler admits gaps → ledger populated
      5. Iteration loop: pop → execute → inject → next step
      6. HALT → synthesize
    """

    # ── 1. INIT ──────────────────────────────────────────────────────

    trajectory = Trajectory.load(str(TRAJ_FILE))
    Trajectory.load_chains(str(CHAINS_FILE), trajectory)
    registry = load_all(str(SKILLS_DIR))
    head = git_head()
    head_tree = git_tree()

    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))
    session.set_system(PRE_DIFF_SYSTEM)

    print(f"\n{'='*60}")
    print(f"TURN: \"{user_message}\" (contact: {contact_id})")
    print(f"HEAD: {head} | Trajectory: {len(trajectory.order)} steps")
    print(f"{'='*60}")

    # ── 2. FIRST STEP (origin) ───────────────────────────────────────
    #
    # The LLM sees: trajectory tree + HEAD + user message
    # It produces: pre-diff reasoning + gap articulations (post-diff)
    # This is the origin step — the root of this turn's causal chain

    traj_tree = trajectory.render_recent(TRAJECTORY_WINDOW, registry=registry)

    first_input = f"""## Trajectory
{traj_tree}

## HEAD: commit:{head}
{head_tree}

## Message from {contact_id}
"{user_message}"
"""

    print("\n── FIRST STEP (origin) ──")
    raw = session.call(first_input)
    print(f"  LLM: {raw[:200]}...")

    # Parse gaps from LLM output
    origin_step, origin_gaps = _parse_step_output(
        raw, step_refs=[], content_refs=[head]
    )
    trajectory.append(origin_step)

    print(f"  step:{origin_step.hash} | gaps: {len(origin_gaps)}")
    for g in origin_gaps:
        tag = f" [{g.vocab}]" if g.vocab else ""
        print(f"    gap:{g.hash} \"{g.desc}\"{tag}")

    # ── 3. IDENTITY (.st injection) ──────────────────────────────────
    #
    # Fire the contact's .st file. This surfaces identity, preferences,
    # principles into the LLM's context — positioned AFTER the first
    # step so it doesn't get pushed out of the context window.

    identity_skill = _find_identity_skill(contact_id, registry)
    if identity_skill:
        print(f"\n── IDENTITY: {identity_skill.display_name}:{identity_skill.hash} ──")
        identity_block = _render_identity(identity_skill)
        session.inject(identity_block)

        identity_step = Step.create(
            desc=f"identity loaded: {identity_skill.display_name}",
            content_refs=[identity_skill.hash],
            step_refs=[origin_step.hash],
        )
        trajectory.append(identity_step)
        print(f"  step:{identity_step.hash} → refs:[{identity_skill.display_name}:{identity_skill.hash}]")

    # ── 4. COMPILER ──────────────────────────────────────────────────
    #
    # Admit origin gaps onto the ledger. The compiler sequences them
    # via the stack (LIFO, depth-first).

    compiler = Compiler(trajectory)

    if not origin_gaps:
        # No gaps → auto-synthesize
        print("\n── AUTO-SYNTH (no gaps) ──")
        response = _synthesize(session, user_message)
        _save_turn(trajectory)
        return response

    # Emit origin gaps — each creates its own chain
    compiler.emit_origin_gaps(origin_step)

    print(f"\n── COMPILER ──")
    print(compiler.render_ledger())

    # ── 5. ITERATION LOOP ────────────────────────────────────────────
    #
    # Pop gap → resolve hashes → execute by vocab → inject result →
    # new step forms → compiler emits child gaps → repeat

    for iteration in range(MAX_ITERATIONS):
        entry, signal = compiler.next()

        if entry is None or signal == GovernorSignal.HALT:
            print(f"\n  HALT (iteration {iteration})")
            break

        gap = entry.gap
        print(f"\n── ITERATION {iteration + 1}: gap:{gap.hash[:8]} ──")
        print(f"  \"{gap.desc}\"")
        print(f"  signal: {signal.name} | vocab: {gap.vocab} | chain: {entry.chain_id[:8]}")

        # ── Governor signals ──

        if signal == GovernorSignal.REVERT:
            print("  → REVERT: divergence detected, skipping")
            compiler.resolve_current_gap(gap.hash)
            continue

        # ── Resolve hash references ──

        resolved_data = resolve_all_refs(gap.step_refs, gap.content_refs, trajectory)

        # ── Execute by vocab ──

        vocab = gap.vocab
        step_result = None

        if vocab in OBSERVATION_ONLY_VOCAB:
            # ── Observation-only: resolve hashes, inject, blob step (no post-diff) ──
            print(f"  → observation-only ({vocab})")

            if resolved_data:
                session.inject(f"## Resolved hash data for gap:{gap.hash}\n{resolved_data}")

            step_result = Step.create(
                desc=f"resolved: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            # Blob step — no gaps, no branching
            compiler.resolve_current_gap(gap.hash)

        elif vocab and vocab in DETERMINISTIC_VOCAB:
            # ── Deterministic: kernel resolves directly ──
            print(f"  → deterministic ({vocab})")

            tool_path = TOOL_MAP.get(vocab)
            if tool_path:
                params = {"refs": gap.content_refs, "desc": gap.desc}
                output, _ = execute_tool(tool_path, params)
                session.inject(f"## Tool output ({vocab})\n{output}")
            elif resolved_data:
                session.inject(f"## Resolved data\n{resolved_data}")

            # LLM reasons over resolved data → may produce child gaps
            raw = session.call(f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps.")
            print(f"  LLM: {raw[:150]}...")

            step_result, child_gaps = _parse_step_output(
                raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )

            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)

        elif vocab and is_mutate(vocab):
            # ── Mutation: 5.4 composes command, kernel executes ──
            print(f"  → mutation ({vocab})")

            # Check OMO
            if not compiler.validate_omo(vocab):
                print("  → OMO violation: need observation first")
                # Inject an observation step
                if resolved_data:
                    session.inject(f"## Context for gap:{gap.hash}\n{resolved_data}")
                compiler.record_execution("scan_needed", False)

            # Inject resolved context
            if resolved_data:
                session.inject(f"## Resolved context for mutation\n{resolved_data}")

            # 5.4 composes the command
            compose_prompt = f"""Compose a command to resolve this gap:
  gap:{gap.hash} "{gap.desc}"
  vocab: {vocab}

Respond with JSON: {{"command": "...", "reasoning": "..."}}"""

            raw = session.call(compose_prompt)
            print(f"  LLM compose: {raw[:150]}...")

            command = _extract_command(raw)
            if command:
                print(f"  → executing: {command[:100]}")
                result = subprocess.run(
                    command, shell=True, cwd=str(CORS_ROOT),
                    capture_output=True, text=True, timeout=30,
                )
                output = result.stdout[:500] or result.stderr[:500] or "(no output)"
                print(f"  → output: {output[:100]}")

                # Auto-commit if mutation
                commit_sha = auto_commit(f"step: {gap.desc[:50]}")
                if commit_sha:
                    print(f"  → committed: {commit_sha}")

                    # Postcondition: observe the commit
                    post_tree = git_tree(commit_sha)
                    session.inject(f"## Postcondition: commit:{commit_sha}\n{post_tree}\n\nCommand output:\n{output}")

                    step_result = Step.create(
                        desc=f"executed: {gap.desc}",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        commit=commit_sha,
                        chain_id=entry.chain_id,
                    )
                    compiler.record_execution(vocab, True)

                    # LLM observes postcondition → may produce new gaps
                    raw = session.call("Observe the commit result. Articulate any remaining gaps.")
                    print(f"  LLM postcondition: {raw[:150]}...")

                    post_step, child_gaps = _parse_step_output(
                        raw, step_refs=[step_result.hash], content_refs=[commit_sha],
                        chain_id=entry.chain_id,
                    )
                    trajectory.append(post_step)
                    compiler.record_execution("scan_needed", False)  # postcondition is observation

                    if child_gaps:
                        compiler.emit(post_step)
                    else:
                        compiler.resolve_current_gap(gap.hash)
                else:
                    # No changes — command was observation-like
                    session.inject(f"## Command output (no mutation)\n{output}")
                    step_result = Step.create(
                        desc=f"observed: {gap.desc}",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        chain_id=entry.chain_id,
                    )
                    compiler.record_execution(vocab, False)
                    compiler.resolve_current_gap(gap.hash)
            else:
                print("  → no command extracted, resolving gap")
                compiler.resolve_current_gap(gap.hash)
                step_result = Step.create(
                    desc=f"skipped: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )

        elif vocab and is_observe(vocab):
            # ── Observation: resolve + LLM reasons ──
            print(f"  → observation ({vocab})")

            tool_path = TOOL_MAP.get(vocab)
            if tool_path:
                params = {"refs": gap.content_refs, "desc": gap.desc}
                output, code = execute_tool(tool_path, params)
                session.inject(f"## Tool output ({vocab})\n{output}")
            elif resolved_data:
                session.inject(f"## Resolved data\n{resolved_data}")

            raw = session.call(f"You resolved gap:{gap.hash} \"{gap.desc}\". What do you observe? Articulate any new gaps.")
            print(f"  LLM: {raw[:150]}...")

            step_result, child_gaps = _parse_step_output(
                raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )
            compiler.record_execution(vocab, False)

            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)

        else:
            # ── Bridge or unknown vocab ──
            print(f"  → bridge/unknown ({vocab})")
            if resolved_data:
                session.inject(f"## Context\n{resolved_data}")

            raw = session.call(f"Address gap:{gap.hash} \"{gap.desc}\". What's needed?")
            step_result, child_gaps = _parse_step_output(
                raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                chain_id=entry.chain_id,
            )

            if child_gaps:
                compiler.emit(step_result)
            else:
                compiler.resolve_current_gap(gap.hash)

        # ── Record step ──

        if step_result:
            trajectory.append(step_result)
            compiler.add_step_to_chain(step_result.hash)
            print(f"  step:{step_result.hash}" +
                  (f" commit:{step_result.commit}" if step_result.commit else ""))

        # Check if done
        if compiler.is_done():
            print(f"\n  ALL GAPS RESOLVED (iteration {iteration + 1})")
            break

    # ── 6. SYNTHESIS ─────────────────────────────────────────────────

    print("\n── SYNTHESIS ──")
    response = _synthesize(session, user_message)

    # ── 7. SAVE ──────────────────────────────────────────────────────

    _save_turn(trajectory)

    return response


# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_step_output(raw: str, step_refs: list[str], content_refs: list[str],
                       chain_id: str = None) -> tuple[Step, list[Gap]]:
    """Parse LLM output into a Step with gaps.

    The LLM produces natural text with an embedded JSON block.
    Extract the gaps from the JSON, build a Step.
    """
    gaps = []
    try:
        # Find JSON block in output
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(raw[json_start:json_end])
            for g in data.get("gaps", []):
                gap = Gap.create(
                    desc=g.get("desc", ""),
                    content_refs=g.get("content_refs", []),
                    step_refs=g.get("step_refs", []),
                )
                gap.scores = Epistemic(
                    relevance=g.get("relevance", 0.5),
                    confidence=g.get("confidence", 0.5),
                    grounded=g.get("grounded", 0.5),
                )
                gap.vocab = g.get("vocab")
                if gap.vocab:
                    gap.vocab_score = 0.8
                gaps.append(gap)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # Extract desc from the natural text portion (before JSON)
    json_start = raw.find("{")
    desc = raw[:json_start].strip() if json_start > 0 else raw[:200].strip()
    # Trim to a reasonable length
    if len(desc) > 200:
        desc = desc[:200] + "..."

    step = Step.create(
        desc=desc,
        step_refs=step_refs,
        content_refs=content_refs,
        gaps=gaps,
        chain_id=chain_id,
    )

    return step, gaps


def _extract_command(raw: str) -> str | None:
    """Extract a command from LLM JSON output."""
    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(raw[json_start:json_end])
            return data.get("command")
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _find_identity_skill(contact_id: str, registry: SkillRegistry) -> Skill | None:
    """Find the .st file that triggers for this contact."""
    for skill in registry.all_skills():
        # Read the .st file to check trigger
        try:
            with open(skill.source) as f:
                data = json.load(f)
            trigger = data.get("trigger", "")
            if trigger == f"on_contact:{contact_id}":
                return skill
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    return None


def _render_identity(skill: Skill) -> str:
    """Render a skill's identity and preferences for session injection."""
    try:
        with open(skill.source) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return ""

    lines = [f"## Identity: {skill.display_name}:{skill.hash}"]

    identity = data.get("identity", {})
    if identity:
        for k, v in identity.items():
            lines.append(f"  {k}: {v}")

    preferences = data.get("preferences", {})
    if preferences:
        lines.append("## Preferences")
        for category, prefs in preferences.items():
            lines.append(f"  {category}:")
            if isinstance(prefs, dict):
                for k, v in prefs.items():
                    lines.append(f"    {k}: {v}")
            else:
                lines.append(f"    {prefs}")

    return "\n".join(lines)


def _synthesize(session: Session, user_message: str) -> str:
    """Produce the final response from the session."""
    session.inject(SYNTH_SYSTEM, role="system")
    response = session.call(f"Synthesize your response to: \"{user_message}\"")
    print(f"  Response: {response[:200]}")
    return response


def _save_turn(trajectory: Trajectory):
    """Persist trajectory and chains."""
    trajectory.save(str(TRAJ_FILE))
    trajectory.save_chains(str(CHAINS_FILE))
    print(f"  Saved: {len(trajectory.order)} steps, {len(trajectory.chains)} chains")


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("v5 Step Kernel — cors")
    print("Type /quit to exit, /wipe to reset trajectory\n")

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
            if TRAJ_FILE.exists():
                TRAJ_FILE.unlink()
            if CHAINS_FILE.exists():
                CHAINS_FILE.unlink()
            print("trajectory wiped")
            continue

        response = run_turn(user_input)
        print(f"\nv5> {response}\n")
