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

from step import Step, Gap, Epistemic, Trajectory, TREE_LANGUAGE_KEY
from compile import (
    Compiler, GovernorSignal,
    is_observe, is_mutate, is_bridge,
)
from skills.loader import load_all, SkillRegistry, Skill
import manifest_engine as me


# ── Configuration ────────────────────────────────────────────────────────

CORS_ROOT    = Path(__file__).parent
SKILLS_DIR   = CORS_ROOT / "skills"
TRAJ_FILE    = CORS_ROOT / "trajectory.json"
CHAINS_FILE  = CORS_ROOT / "chains.json"
CHAINS_DIR   = CORS_ROOT / "chains"
MAX_ITERATIONS = 30
TRAJECTORY_WINDOW = 10   # how many recent chains to render for LLM
_turn_counter = 0        # increments each turn — used for cross-turn gap threshold


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


# ── Tree Policy ──────────────────────────────────────────────────────────
# Per-path mutation policy. Configurable via tree_policy.json.
# Loaded at startup — the UI can edit this file to change protection rules.
#
# Policy types:
#   {"immutable": true}              — auto-revert if mutated
#   {"on_mutate": "vocab_needed"}    — reroute mutation to specified vocab
#   (no entry)                       — normal mutation allowed
#
TREE_POLICY_FILE = CORS_ROOT / "tree_policy.json"
DEFAULT_TREE_POLICY = {
    "skills/codons/":   {"immutable": True, "on_reject": "reason_needed"},
    "skills/":          {"on_mutate": "reprogramme_needed"},
    "ui_output/":       {"on_mutate": "stitch_needed"},
    "logs/":            {"immutable": True},
    "store/":           {"immutable": True},
    "step.py":          {"immutable": True},
    "compile.py":       {"immutable": True},
    "loop.py":          {"immutable": True},
    "skills/loader.py": {"immutable": True},
    "trajectory.json":  {"immutable": True},
    "chains.json":      {"immutable": True},
}


def _load_tree_policy() -> dict:
    """Load tree policy from JSON file, falling back to defaults."""
    try:
        with open(TREE_POLICY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_TREE_POLICY


def _match_policy(path: str, policy: dict) -> dict | None:
    """Find the policy that applies to a given path.
    Checks exact match first, then prefix match (longest wins)."""
    # Exact match
    if path in policy:
        return policy[path]
    # Prefix match — longest prefix wins
    best = None
    best_len = 0
    for prefix, rule in policy.items():
        if prefix.endswith("/") and path.startswith(prefix) and len(prefix) > best_len:
            best = rule
            best_len = len(prefix)
    return best


def _check_protected(commit_sha: str, pre_commit_sha: str) -> tuple[list[str], str | None]:
    """Check if any immutable paths were modified between two commits.

    Returns (violations, on_reject_vocab):
      - violations: list of violated immutable paths
      - on_reject_vocab: if set in policy, the vocab to emit on rejection
        (e.g. 'reason_needed' for codon immutability violations)
    """
    policy = _load_tree_policy()
    diff_output = git(["diff", "--name-only", pre_commit_sha, commit_sha])
    if not diff_output:
        return [], None
    changed = diff_output.strip().split("\n")
    violations = []
    on_reject = None
    for path in changed:
        rule = _match_policy(path, policy)
        if rule and rule.get("immutable"):
            violations.append(path)
            # Check for on_reject vocab (codon immutability → reason_needed)
            if rule.get("on_reject") and on_reject is None:
                on_reject = rule["on_reject"]
    return violations, on_reject


def auto_commit(message: str) -> tuple[str | None, str | None]:
    """Stage all changes and commit. Returns (SHA, on_reject_vocab).

    After committing, checks for protected path violations. If the LLM
    mutated a protected file, auto-reverts to the previous commit and
    returns (None, on_reject_vocab) (the mutation is rejected).
    """
    status = git(["status", "--porcelain"])
    if not status:
        return None, None

    pre_sha = git_head()
    git(["add", "-A"])
    git(["commit", "-m", message])
    post_sha = git_head()

    # Check integrity — did the agent mutate protected paths?
    violations, on_reject = _check_protected(post_sha, pre_sha)
    if violations:
        print(f"  ⚠ PROTECTED PATH VIOLATION: {violations}")
        if on_reject:
            print(f"  → on_reject: {on_reject} (codon immutability)")
        print(f"  → auto-reverting to {pre_sha}")
        git(["revert", "--no-commit", "HEAD"])
        git(["commit", "-m", f"auto-revert: protected path violation ({', '.join(violations)})"])
        return None, on_reject  # mutation rejected, with optional rejection vocab

    return post_sha, None


# ── Hash resolution ──────────────────────────────────────────────────────

_skill_registry: SkillRegistry | None = None  # set by run_turn for resolve_hash access
ENTITY_MANIFEST_FIELDS = {
    "identity", "preferences", "constraints", "sources", "scope",
    "schema", "access_rules", "principles", "boundaries", "domain_knowledge",
}

def resolve_hash(ref: str, trajectory: Trajectory) -> str | None:
    """Resolve any hash to its content as a semantic tree.

    Resolution order:
      1. Skill hash → .st step package render (entity-like packages usually inject semantic state)
      2. Step hash → semantic tree branch (follows step_refs recursively)
      3. Gap hash → gap data with scores
      4. Git object → git show (blob/tree/commit)

    Step hashes render as the same tree shape the LLM sees in render_recent.
    The causal ancestry is visible — step_refs trace backward, gaps branch forward.
    """
    # Try skill registry first — entity .st files
    if _skill_registry:
        skill = _skill_registry.resolve(ref)
        if skill:
            return _render_entity(skill)

    # Try trajectory step — render as semantic tree branch
    step = trajectory.resolve(ref)
    if step:
        return _render_step_tree(step, trajectory, depth=0, max_depth=5)

    # Try trajectory gap
    gap = trajectory.resolve_gap(ref)
    if gap:
        return _render_gap_tree(gap, trajectory)

    package = me.load_chain_package(CHAINS_DIR, ref, trajectory)
    if package:
        return me.render_chain_package(package, ref)

    # Try git object
    content = git_show(ref)
    if not content.startswith("(unresolvable"):
        return content

    return None


def _render_step_tree(step, trajectory: Trajectory, depth: int = 0,
                      max_depth: int = 5) -> str:
    """Render a step as a semantic tree branch.

    Follows step_refs backward (causal ancestry) up to max_depth.
    Shows gaps as child branches. Same shape as render_recent.
    """
    indent = "  " * depth
    registry = _skill_registry

    # Step line with refs
    refs = []
    for r in step.step_refs:
        refs.append(trajectory._tag_ref(r, "step", registry) if hasattr(trajectory, '_tag_ref') else f"step:{r}")
    for r in step.content_refs:
        refs.append(trajectory._tag_ref(r, "content", registry) if hasattr(trajectory, '_tag_ref') else r)

    from step import absolute_time
    ref_str = f" → refs:[{', '.join(refs)}]" if refs else ""
    commit_str = f" → commit:{step.commit}" if step.commit else ""
    time_tag = f" ({absolute_time(step.t)})" if step.t > 0 else ""
    step_sig = trajectory._step_signature(step) if hasattr(trajectory, "_step_signature") else ""
    sig_prefix = f"{step_sig} " if step_sig else ""
    lines = [f"{indent}{sig_prefix}step:{step.hash} \"{step.desc}\"{ref_str}{commit_str}{time_tag}"]

    # Gaps as child branches
    for gap in step.gaps:
        gap_sig = trajectory._gap_signature(gap) if hasattr(trajectory, "_gap_signature") else ""
        gap_prefix = f"{gap_sig} " if gap_sig else ""
        if gap.dormant:
            lines.append(
                f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\" "
                f"(dormant, score:{gap.scores.magnitude():.2f})"
            )
        elif gap.resolved:
            lines.append(f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\" (resolved)")
        else:
            grefs = []
            for r in gap.step_refs:
                grefs.append(f"step:{r}")
            for r in gap.content_refs:
                grefs.append(r)
            gref_str = f" → refs:[{', '.join(grefs)}]" if grefs else ""
            vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
            lines.append(f"{indent}  └─ {gap_prefix}gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}")

    # Follow step_refs backward (causal ancestry)
    if depth < max_depth:
        for parent_hash in step.step_refs:
            parent = trajectory.resolve(parent_hash)
            if parent:
                lines.append(f"{indent}  ── ancestor:")
                lines.append(_render_step_tree(parent, trajectory, depth + 1, max_depth))

    return "\n".join(lines)


def _render_gap_tree(gap, _trajectory: Trajectory = None) -> str:
    """Render a gap with its full context."""
    gap_sig = _trajectory._gap_signature(gap) if _trajectory and hasattr(_trajectory, "_gap_signature") else ""
    sig_suffix = f" {gap_sig}" if gap_sig else ""
    lines = [f"gap:{gap.hash}{sig_suffix} \"{gap.desc}\""]
    if gap.content_refs:
        lines.append(f"  content_refs[{len(gap.content_refs)}]: {gap.content_refs}")
    if gap.step_refs:
        lines.append(f"  step_refs[{len(gap.step_refs)}]: {gap.step_refs}")
    lines.append(f"  scores: rel={gap.scores.relevance:.2f} conf={gap.scores.confidence:.2f} gr={gap.scores.grounded:.2f}")
    if gap.vocab:
        lines.append(f"  vocab: {gap.vocab}")
    if gap.dormant:
        lines.append(f"  status: dormant")
    elif gap.resolved:
        lines.append(f"  status: resolved")
    else:
        lines.append(f"  status: active")
    return "\n".join(lines)


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


def _emit_reason_skill(reason_skill: Skill, gap: Gap, origin_step: Step,
                       entry_chain_id: str) -> Step:
    reason_step = Step.create(
        desc=f"reason activated: {gap.desc}",
        step_refs=[origin_step.hash],
        content_refs=[reason_skill.hash] + gap.content_refs,
        chain_id=entry_chain_id,
    )
    for st_step in reason_skill.steps:
        child_gap = Gap.create(
            desc=st_step.desc,
            content_refs=gap.content_refs,
        )
        child_gap.scores = Epistemic(
            relevance=st_step.__dict__.get("relevance", 0.8),
            confidence=0.8,
            grounded=0.0,
        )
        child_gap.vocab = st_step.vocab
        child_gap.turn_id = _turn_counter
        reason_step.gaps.append(child_gap)
    return reason_step


# ── Tool execution ───────────────────────────────────────────────────────

TOOL_MAP = {
    # Observation tools (deterministic — kernel resolves, no LLM needed)
    # Format: {"tool": path, "post_observe": target_path_or_None}
    "hash_resolve_needed":  {"tool": None},
    "pattern_needed":       {"tool": "tools/file_grep.py"},
    "email_needed":         {"tool": "tools/email_check.py"},
    "external_context":     {"tool": None},

    # Mutation tools (composed — 5.4 writes the command)
    # post_observe: None = resolve commit tree, path = resolve specific dir/file from commit
    "hash_edit_needed":     {"tool": "tools/hash_manifest.py"},
    "stitch_needed":        {"tool": "tools/stitch_generate.py", "post_observe": "ui_output/"},
    "content_needed":       {"tool": "tools/file_write.py"},
    "script_edit_needed":   {"tool": "tools/file_edit.py"},
    "command_needed":       {"tool": "tools/code_exec.py"},
    "message_needed":       {"tool": "tools/email_send.py"},
    "json_patch_needed":    {"tool": "tools/json_patch.py"},
    "git_revert_needed":    {"tool": "tools/git_ops.py"},
}

# Deterministic vocabs — kernel resolves without LLM
DETERMINISTIC_VOCAB = {
    "hash_resolve_needed",
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

Every gap carries three scores. You provide two; the kernel computes the third:

- relevance (0-1) [YOU SCORE]: how much does resolving this advance the trajectory toward the shared goal?
  1.0 = critical path — resolving this directly addresses what was asked.
  0.0 = does not advance the goal at all.
  Evaluative form: "If this gap were resolved, would it move the system closer to what the user needs?"
  This is the PRIMARY driver of admission. Be honest — not everything you notice is relevant to the goal.

- confidence (0-1) [YOU SCORE]: how safe and trustworthy is this to act on?
  1.0 = safe to trust and proceed. 0.0 = unsafe, uncertain, or unverifiable.
  Evaluative form: "Do I have enough evidence to act on this, or am I assuming?"

- grounded (0-1) [KERNEL COMPUTES — do not score this]: measured deterministically by hash co-occurrence frequency on the trajectory. How often the gap's referenced hashes have appeared before. You cannot influence this — it is a structural measurement. To be well-grounded, reference hashes that actually exist on the trajectory.

Admission formula: 0.8 * relevance + 0.2 * grounded. Relevance dominates — extremely relevant gaps can enter even with no prior hash references. But low-relevance gaps need strong grounding (frequently referenced hashes) to survive.

Low-scoring gaps become dormant — stored on the trajectory as peripheral vision, not acted on unless they recur.

## Gap discipline

One gap per entity. If you need context about a person, concept, or workflow — emit ONE gap with hash_resolve_needed and put the entity's hash in content_refs. The kernel checks the skill registry and renders the full .st file data automatically. Do not decompose an entity into sub-gaps ("need their role", "need their history", "need their preferences"). The .st file surfaces everything in one resolution.

Entity resolution has no special vocab — it's just hash_resolve_needed where the hash happens to be a .st file. The kernel resolves it the same way it resolves any other hash.

## Hash references (two layers, never mixed)

When you articulate a gap, ground it in hashes:

- step_refs: reasoning steps you followed to reach this gap (Layer 1 — the causal chain)
- content_refs: data you need resolved — blobs, trees, commits, skill hashes (Layer 2 — the evidence)

The kernel resolves content_refs for you. If you reference a hash, the kernel will inject its content into your context. If you don't reference hashes, you are reasoning from assumption — which means grounded = 0.

## Vocab mapping

Each gap maps to a vocab term that tells the kernel HOW to resolve it:

OBSERVE (kernel resolves, you receive data):
  pattern_needed — search file contents by pattern
  hash_resolve_needed — resolve step/gap/blob hashes from trajectory
  email_needed — check email
  external_context — surface from current context
  clarify_needed — you cannot proceed without user input. USE THIS when:
    - The user's intent is ambiguous and you'd be guessing
    - Multiple interpretations exist and the wrong one wastes effort
    - You need a specific piece of information only the user has
    The desc field becomes your question. This halts the iteration loop.
    The gap persists on the trajectory — next turn, the LLM sees it and
    can resume the chain with the user's clarification as new context.
  (workspace files visible via HEAD commit tree. URLs and web research are steps inside workflow .st files, not standalone vocab.)

MUTATE (you compose a command, kernel executes):
  hash_edit_needed — edit any file (universal: read by hash → compose edit → execute via hash_manifest)
  stitch_needed — generate UI via Google Stitch (prompt → HTML + Tailwind CSS)
  content_needed — write a new file
  script_edit_needed — edit an existing file
  command_needed — execute a shell command
  message_needed — send an email/message
  json_patch_needed — surgical JSON edit
  git_revert_needed — git revert/checkout

BRIDGE_VOCAB_PLACEHOLDER

If no action is needed, emit no gaps.

## Your context

You receive:
- A trajectory rendered as a traversable hash tree (chains → steps → gaps → refs)
- The current HEAD commit hash (workspace state)
- A user message
- Identity (who you're talking to — loaded as a skill hash)

## Reading the trajectory tree

The trajectory is rendered as a tree you can explore — the same shape as a git commit tree. Every node is a hash. Every branch is traversable.

It also carries a compact tree language so structural dimensions stay visible without blowing up the render:
- step{kindflowN}: kind=o observe, m mutate; flow=+ open, ~ dormant-only, = closed; N is active child-gap count when present
- gap{statusclassrcg/s:c}: status=? active, = resolved, ~ dormant; class=o observe, m mutate, b bridge, c clarify, _ unknown; rcg are relevance/confidence/grounded bands (0-9); s:c are step_refs:content_refs counts

```
chain:0d71abb30b86  "resolved missing config" (active, 3 steps)
  origin: fdd2834ace0b
  ├─ {o+2} step:7146246b7b7b "observed workspace" → refs:[commit:aa8b921]
  │   ├─ {?o862/1:2} gap:fdd2834ace0b "config missing" [hash_resolve_needed] → refs:[aa8b921:config.json]
  │   └─ {~_110/0:1} gap:00342afc4b05 "weak side-branch" (dormant, score:0.17)
  ├─ {o+1} step:f13bf0dc5db0 "resolved config" → refs:[step:7146246b7b7b, blob:e4f1...]
  │   └─ {?m781/1:1} gap:61ad761e524e "needs database section" [content_needed] → refs:[blob:e4f1...]
  └─ {m=} step:53a20c80cf58 "wrote config" → refs:[step:f13bf0dc5db0] → commit:bb9c032
```

How to navigate it:
- Chains are the top-level units. Each chain traces one line of reasoning from an origin gap to resolution.
- Steps branch from chains. Each step shows what was observed or done, and what hashes were referenced.
- Gaps branch from steps. Active gaps show what still needs resolving. Dormant gaps are peripheral vision. Resolved gaps are closed.
- refs:[] on each node are the hashes that ground it. You can request any hash resolved.
- Named hashes like kenny:72b1d5ffc964 or research:a72c3c4dec0c are skill/identity files — they evolve over time but the name stays constant.
- commit:<sha> means the system mutated the workspace at that point. You can diff between commits to see exactly what changed.

How to trace causality:
- Follow step_refs backward to see WHY something happened (the reasoning chain that led here)
- Follow content_refs to see WHAT was observed or acted on (the evidence)
- Follow commit hashes to see WHAT CHANGED (the mutation diff)
- A chain of steps compresses into a single chain hash — you can reference the whole chain by one hash
- Dormant gaps that recur across turns may indicate something the system keeps noticing but hasn't addressed

You can reverse-engineer any state by tracing its chain backward: the current step references prior steps, which reference their prior steps, all the way back to the origin gap. Every link in the chain is a hash you can resolve.

If the trajectory is empty, you are starting fresh — the only hash available is the HEAD commit.

## Identity and the user hash

When an identity .st file loads (e.g. kenny:72b1d5ffc964), that hash is an entity — just like any other step. A person, a workflow, an idea — they are all entities you reason about. The only difference with the identity entity is that you are currently in conversation with them.

Their .st file is your mental model of who they are. Their context, their role, how they think, what they care about, what they've done with you before. Use it to reason about them the way you reason about any entity — by following their hash through the trajectory, tracing chains they were part of, understanding what they've built, asked, committed to, and left unfinished.

Every chain they have been part of traces back through their identity hash. How far you follow depends on relevance to the current input — a question about workspace files doesn't need their full history, but a question about a commitment they made last week does.

The identity hash evolves. When their preferences or context change, the hash changes. Steps referencing the old hash trace to who they were. Steps referencing the new hash trace to who they are now.

Their preferences are not instructions on how to speak. They are part of your model of this person — how they communicate, how they think, what frustrates them, what they value. You use that model the way you use any referred context: to reason better, respond appropriately, and anticipate what matters to them.

## How to respond

Do not explain internal systems, hashes, or trajectory mechanics to the user unless they ask. They see a conversation, not a hash graph.

When the user asks a question answerable from your current context — answer it directly, no gaps needed. When they ask for something that requires action — articulate the gap, grounded in the specific hashes you would need resolved.

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
      "confidence": 0.0
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

    global _turn_counter, _skill_registry
    _turn_counter += 1
    current_turn = _turn_counter

    trajectory = Trajectory.load(str(TRAJ_FILE))
    Trajectory.load_chains(str(CHAINS_FILE), trajectory)
    registry = load_all(str(SKILLS_DIR))
    _skill_registry = registry
    head = git_head()
    head_tree = git_tree()

    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))

    # Build dynamic system prompt with actual available entities
    entity_list_lines = "\n".join(
        f"    {s.display_name}:{s.hash} — {s.desc[:60]}"
        for s in registry.all_skills()
    )
    dynamic_bridge = (
        "BRIDGE (four codons):\n"
        "  reason_needed — START CODON. Stateful structural abstraction. USE THIS when:\n"
        "    - A decision requires deeper analysis than one step\n"
        "    - Long-term planning or judgment is needed\n"
        "    - You need to traverse the trajectory tree or entity space to build understanding\n"
        "    - Executable step flow or chain structure needs to be derived or refined\n"
        "    - A commitment needs activation, reintegration, or reorientation\n"
        "    Reasons over semantic trees, entity space, and executable structure.\n\n"
        "  await_needed — PAUSE CODON. Synchronization checkpoint.\n"
        "    Use this when background work must explicitly rejoin the parent chain.\n"
        "    Suspends the parent flow until the sub-agent or background branch is ready.\n\n"
        "  commit_needed — END CODON. Do NOT emit this directly. It is injected automatically\n"
        "    by reason.st when a commitment is manifested. It sits at lowest relevance behind\n"
        "    all commitment gaps — fires last, reintegrates the full commitment tree into\n"
        "    main context, then closes or continues the chain. Compiler laws maintained.\n\n"
        "  reprogramme_needed — PERSIST CODON. Stateless semantic state update. USE THIS when:\n"
        "    - User corrects or clarifies a preference\n"
        "    - User mentions a new person, concept, or domain to track\n"
        "    - User says 'remember', 'update', 'track', or corrects your understanding\n"
        "    - Semantic state must persist beyond the current turn or horizon\n"
        "    Persists long-horizon internal state so the system stays informed.\n\n"
        "  .st resolution has no dedicated entity vocab — it still enters through hash resolution.\n"
        "  When you reference a .st hash in content_refs, the kernel resolves the step package.\n"
        "  Entity-like packages usually manifest as semantic/context injection.\n"
        "  Action-like packages may be activated structurally through curated workflows.\n\n"
        "  Known entities (reference by hash in content_refs):\n"
        f"{entity_list_lines}"
    )
    system_prompt = PRE_DIFF_SYSTEM.replace("BRIDGE_VOCAB_PLACEHOLDER", dynamic_bridge)
    session.set_system(system_prompt)

    print(f"\n{'='*60}")
    print(f"TURN: \"{user_message}\" (contact: {contact_id})")
    print(f"HEAD: {head} | Trajectory: {len(trajectory.order)} steps")
    print(f"{'='*60}")

    # ── 1b. RESUME CHECK ──────────────────────────────────────────────
    #
    # Check for unresolved gaps from prior turns (clarify_needed, interrupted).
    # Surface them in the trajectory so the LLM can see what was left dangling.
    # The LLM selects which are still relevant — non-selection = dropped.

    dangling = _find_dangling_gaps(trajectory)
    if dangling:
        print(f"\n── RESUME: {len(dangling)} unresolved gap(s) from prior turn ──")
        for dg in dangling:
            print(f"  gap:{dg.hash[:8]} \"{dg.desc}\"")

    # ── 2. FIRST STEP (origin) ───────────────────────────────────────
    #
    # The LLM sees: trajectory tree + HEAD + user message
    # It produces: pre-diff reasoning + gap articulations (post-diff)
    # This is the origin step — the root of this turn's causal chain

    traj_tree = trajectory.render_recent(TRAJECTORY_WINDOW, registry=registry)

    first_input = f"""## Tree Language
{TREE_LANGUAGE_KEY}

## Trajectory
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

    compiler = Compiler(trajectory, current_turn=current_turn)

    # Tag origin gaps with current turn
    for g in origin_gaps:
        g.turn_id = current_turn

    # Re-admit dangling cross-turn gaps (higher threshold: 0.6)
    if dangling:
        readmitted = compiler.readmit_cross_turn(dangling, origin_step.hash)
        if readmitted:
            print(f"  → {readmitted} cross-turn gap(s) re-admitted")

    if not origin_gaps and not dangling:
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
        session.inject(
            "## Active Chain Tree\n"
            f"{trajectory.render_chain(entry.chain_id, registry=registry, highlight_gap=gap.hash)}"
        )

        # ── Governor signals ──

        if signal == GovernorSignal.REVERT:
            print("  → REVERT: divergence detected, skipping")
            compiler.resolve_current_gap(gap.hash)
            continue

        # ── Clarify: halt iteration, synthesize as question ──

        if gap.vocab == "clarify_needed":
            print(f"  → clarify needed: halting iteration")
            # Record the clarification gap on trajectory — persists across turns
            clarify_step = Step.create(
                desc=f"clarification needed: {gap.desc}",
                step_refs=[origin_step.hash],
                content_refs=gap.content_refs,
                gaps=[gap],  # preserve the gap for resume
                chain_id=entry.chain_id,
            )
            trajectory.append(clarify_step)
            # Don't resolve — leave gap open for next turn's resume
            break

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

            tool_conf = TOOL_MAP.get(vocab, {})
            tool_path = tool_conf.get("tool") if isinstance(tool_conf, dict) else tool_conf
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
            # ── Policy-driven auto-route ──
            # Check tree_policy for on_mutate rules. If a content_ref or desc
            # matches a path with an on_mutate policy, reroute to that vocab.
            policy = _load_tree_policy()
            reroute_vocab = None
            for ref in gap.content_refs:
                rule = _match_policy(ref, policy)
                if rule and rule.get("on_mutate") and rule["on_mutate"] != vocab:
                    reroute_vocab = rule["on_mutate"]
                    break
            # Also check desc for path hints
            if not reroute_vocab:
                for path_prefix, rule in policy.items():
                    if rule.get("on_mutate") and path_prefix.rstrip("/") in gap.desc.lower():
                        if rule["on_mutate"] != vocab:
                            reroute_vocab = rule["on_mutate"]
                            break
            # Also catch .st files by extension (registry check)
            if not reroute_vocab and vocab != "reprogramme_needed":
                if any(ref.endswith(".st") or registry.resolve(ref) is not None for ref in gap.content_refs):
                    reroute_vocab = "reprogramme_needed"
                elif ".st" in gap.desc.lower():
                    reroute_vocab = "reprogramme_needed"

            if reroute_vocab:
                print(f"  → policy auto-route: {vocab} → {reroute_vocab}")
                gap.vocab = reroute_vocab
                compiler.ledger.stack.append(entry)
                continue

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

            # 5.4 composes the action
            if vocab == "hash_edit_needed":
                # Route through hash_manifest.py — JSON params, not shell command
                compose_prompt = (
                    f"Compose a file edit to resolve this gap:\n"
                    f"  gap:{gap.hash} \"{gap.desc}\"\n\n"
                    f"Respond with JSON params for hash_manifest.py:\n"
                    f'{{"action": "patch", "path": "relative/file/path", '
                    f'"patch": {{"old": "exact text to replace", "new": "replacement text"}}}}\n\n'
                    f"Or for a full rewrite:\n"
                    f'{{"action": "write", "path": "relative/file/path", "content": "full file content"}}\n\n'
                    f"Use the EXACT current file content for the 'old' field. Do not guess."
                )
            else:
                compose_prompt = (
                    f"Compose a shell command to resolve this gap:\n"
                    f"  gap:{gap.hash} \"{gap.desc}\"\n"
                    f"  vocab: {vocab}\n\n"
                    f"This is macOS. Use python3 one-liners for JSON edits, not sed.\n"
                    f"Respond with JSON: {{\"command\": \"...\", \"reasoning\": \"...\"}}"
                )

            raw = session.call(compose_prompt)
            print(f"  LLM compose: {raw[:150]}...")

            # Execute based on vocab type
            executed = False
            exec_failed = False
            output = ""

            if vocab == "hash_edit_needed":
                intent = _extract_json(raw)
                if intent:
                    output, code = execute_tool("tools/hash_manifest.py", intent)
                    print(f"  → hash_manifest: {output[:100]}")
                    executed = True
                    exec_failed = code != 0
                else:
                    print("  → no valid params extracted")
            else:
                command = _extract_command(raw)
                if command:
                    print(f"  → executing: {command[:100]}")
                    result = subprocess.run(
                        command, shell=True, cwd=str(CORS_ROOT),
                        capture_output=True, text=True, timeout=30,
                    )
                    output = result.stdout[:500] or result.stderr[:500] or "(no output)"
                    print(f"  → output: {output[:100]}")
                    executed = True
                    exec_failed = result.returncode != 0
                    if exec_failed:
                        print(f"  → FAILED (exit {result.returncode})")
                else:
                    print("  → no command extracted")

            # If execution failed, record failure on trajectory, don't commit
            if exec_failed:
                print(f"  → execution failed, recording on trajectory")
                session.inject(f"## EXECUTION FAILED for gap:{gap.hash}\n{output}")
                step_result = Step.create(
                    desc=f"FAILED: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                # Don't resolve — let the LLM see the failure and re-articulate
                trajectory.append(step_result)
                compiler.add_step_to_chain(step_result.hash)
                continue

            # Auto-commit if mutation succeeded
            if executed:
                commit_result = auto_commit(f"step: {gap.desc[:50]}")
                commit_sha = commit_result[0] if isinstance(commit_result, tuple) else commit_result
                on_reject = commit_result[1] if isinstance(commit_result, tuple) else None
                if commit_sha:
                    print(f"  → committed: {commit_sha}")

                    step_result = Step.create(
                        desc=f"executed: {gap.desc}",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        commit=commit_sha,
                        chain_id=entry.chain_id,
                    )
                    compiler.record_execution(vocab, True)

                    # Universal postcondition: auto-commit → hash_resolve_needed
                    # post_observe config determines what to resolve from the commit
                    tool_conf = TOOL_MAP.get(vocab, {})
                    post_observe = tool_conf.get("post_observe") if isinstance(tool_conf, dict) else None

                    if post_observe:
                        # Targeted: resolve specific path from commit tree
                        tree_files = git(["ls-tree", "-r", "--name-only", commit_sha, post_observe])
                        targeted_refs = [f"{commit_sha}:{f}" for f in tree_files.split("\n") if f.strip()]
                        postcond_refs = targeted_refs or [commit_sha]
                        postcond_desc = f"observe {post_observe}: {', '.join(postcond_refs)}"
                    else:
                        # Default: resolve commit tree
                        postcond_refs = [commit_sha]
                        postcond_desc = f"observe commit:{commit_sha}"

                    postcond = Gap.create(
                        desc=postcond_desc,
                        content_refs=postcond_refs,
                        step_refs=[step_result.hash],
                    )
                    postcond.scores = Epistemic(relevance=1.0, confidence=1.0, grounded=0.0)
                    postcond.vocab = "hash_resolve_needed"
                    postcond_step = Step.create(
                        desc=f"postcondition: {gap.desc}",
                        step_refs=[step_result.hash],
                        content_refs=postcond_refs,
                        gaps=[postcond],
                        chain_id=entry.chain_id,
                    )
                    trajectory.append(postcond_step)
                    compiler.emit(postcond_step)
                    compiler.resolve_current_gap(gap.hash)
                    print(f"  → postcondition gap injected: hash_resolve_needed → {postcond_refs}")
                else:
                    # No commit — either nothing changed or protected path violation
                    # Check if it was a revert by looking at git log
                    last_msg = git(["log", "--oneline", "-1"])
                    if "auto-revert: protected path violation" in last_msg:
                        # Protected path violation — warn the LLM
                        if on_reject:
                            # Codon immutability: fallback to reason_needed for recalibration
                            print(f"  → codon immutability → {on_reject}")
                            session.inject(
                                f"## CODON IMMUTABILITY VIOLATION\n"
                                f"You tried to modify an immutable codon file. "
                                f"Codons are primitives — they cannot be changed. "
                                f"The change was auto-reverted. Recalibrate your approach."
                            )
                            reject_gap = Gap.create(
                                desc=f"reorientation needed: attempted to modify immutable codon — {gap.desc}",
                                step_refs=[origin_step.hash],
                                content_refs=gap.content_refs,
                            )
                            reject_gap.scores = Epistemic(relevance=1.0, confidence=0.8, grounded=0.0)
                            reject_gap.vocab = on_reject  # reason_needed
                            reject_gap.turn_id = current_turn
                            reject_step = Step.create(
                                desc=f"REVERTED: {gap.desc} (codon immutability → {on_reject})",
                                step_refs=[origin_step.hash],
                                content_refs=gap.content_refs,
                                gaps=[reject_gap],
                                chain_id=entry.chain_id,
                            )
                            trajectory.append(reject_step)
                            compiler.emit(reject_step)
                            compiler.resolve_current_gap(gap.hash)
                            step_result = reject_step
                        else:
                            # Standard protected path violation — warn, don't resolve
                            session.inject(
                                f"## PROTECTED PATH VIOLATION\n"
                                f"Your command tried to modify a protected system file. "
                                f"The change was auto-reverted. Recompose your command to "
                                f"only modify files in the workspace, not system files.\n"
                                f"Command output was:\n{output}"
                            )
                            step_result = Step.create(
                                desc=f"REVERTED: {gap.desc} (protected path violation)",
                                step_refs=[origin_step.hash],
                                content_refs=gap.content_refs,
                                chain_id=entry.chain_id,
                            )
                            # Don't resolve — let LLM recompose
                            trajectory.append(step_result)
                            compiler.add_step_to_chain(step_result.hash)
                            continue
                    else:
                        # Genuinely no changes
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
                # Nothing executed — resolve and move on
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

            tool_conf = TOOL_MAP.get(vocab, {})
            tool_path = tool_conf.get("tool") if isinstance(tool_conf, dict) else tool_conf
            if tool_path:
                params = {"refs": gap.content_refs, "desc": gap.desc}
                output, _ = execute_tool(tool_path, params)
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

        elif vocab == "commit_needed":
            # ── Bridge codon: commitment reintegration (end codon) ──
            # Renders the commitment chain as a semantic tree and reintegrates
            # into the main agent's context. Closes or continues the chain.
            print(f"  → commit (end codon)")

            commit_skill = registry.resolve_by_name("commit")
            if commit_skill:
                session.inject(f"## Commitment reintegration: {gap.desc}")
                if resolved_data:
                    session.inject(f"## Commitment chain data\n{resolved_data}")

                commit_step = Step.create(
                    desc=f"commitment reintegrated: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=[commit_skill.hash] + gap.content_refs,
                    chain_id=entry.chain_id,
                )
                for st_step in commit_skill.steps:
                    child_gap = Gap.create(
                        desc=st_step.desc,
                        content_refs=gap.content_refs,
                    )
                    child_gap.scores = Epistemic(
                        relevance=st_step.__dict__.get("relevance", 0.8),
                        confidence=0.8, grounded=0.0,
                    )
                    child_gap.vocab = st_step.vocab
                    child_gap.turn_id = _turn_counter
                    commit_step.gaps.append(child_gap)

                trajectory.append(commit_step)
                compiler.emit(commit_step)
                compiler.resolve_current_gap(gap.hash)
                step_result = commit_step
            else:
                # No commit.st — resolve normally
                if resolved_data:
                    session.inject(f"## Context\n{resolved_data}")
                raw = session.call(f"Reintegrate commitment: gap:{gap.hash} \"{gap.desc}\".")
                step_result, child_gaps = _parse_step_output(
                    raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                if child_gaps:
                    compiler.emit(step_result)
                else:
                    compiler.resolve_current_gap(gap.hash)

        elif vocab == "reason_needed":
            # ── Bridge codon: stateful structural reasoning (start codon) ──
            # reason.st activates higher-order flow reasoning over semantic trees,
            # entity space, and executable structure. Its steps disperse depth-first.
            print(f"  → reason (start codon)")

            reason_skill = registry.resolve_by_name("reason")
            if reason_skill:
                session.inject(f"## Reasoning activation: {gap.desc}")
                if resolved_data:
                    session.inject(f"## Existing context\n{resolved_data}")
                session.inject(f"## Step Network\n{_render_step_network(registry)}")

                raw = session.call(
                    "Choose one manifestation for this reason_needed activation.\n"
                    "Return JSON only.\n\n"
                    "1. Emit the native reason codon:\n"
                    '{"mode":"emit_reason_codon"}\n\n'
                    "2. Submit a workflow skeleton for deterministic compilation:\n"
                    '{"mode":"submit_skeleton","activation":"none|current_turn|background","skeleton":{...skeleton.v1...}}\n\n'
                    "3. Activate an existing chain package by hash (.st skill hash or saved stepchain .json hash):\n"
                    '{"mode":"activate_existing_chain","chain_ref":"hash","activation":"current_turn|background"}\n\n'
                    "Use submit_skeleton when you are constructing a new action/workflow chain.\n"
                    "Use activate_existing_chain when reusing an existing package.\n"
                    "Use emit_reason_codon when you need the native reason.st toolset.\n"
                    "If you activate background work, it will return through heartbeat reason_needed.\n"
                    "If you submit a skeleton, it must be valid skeleton.v1."
                )
                intent = _extract_json(raw) or {"mode": "emit_reason_codon"}
                mode = intent.get("mode", "emit_reason_codon")

                if mode == "submit_skeleton":
                    skeleton = intent.get("skeleton")
                    if isinstance(skeleton, dict) and skeleton.get("version") == "skeleton.v1":
                        output, code = execute_tool("tools/skeleton_compile.py", skeleton)
                        if code == 0:
                            compile_result = json.loads(output)
                            stepchain = compile_result["stepchain"]
                            package_hash = me.persist_chain_package(CHAINS_DIR, stepchain)
                            activation = intent.get("activation", "none")
                            session.inject(
                                "## Compiled chain package\n"
                                f"{me.render_chain_package(stepchain, package_hash)}"
                            )
                            if activation in {"current_turn", "background"}:
                                step_result = me.activate_chain_reference(
                                    CHAINS_DIR,
                                    package_hash,
                                    activation,
                                    gap,
                                    origin_step,
                                    entry.chain_id,
                                    registry,
                                    compiler,
                                    trajectory,
                                    _turn_counter,
                                )
                            else:
                                step_result = Step.create(
                                    desc=f"compiled chain package:{package_hash} for {gap.desc}",
                                    step_refs=[origin_step.hash],
                                    content_refs=[package_hash] + gap.content_refs,
                                    chain_id=entry.chain_id,
                                )
                        else:
                            session.inject(f"## Skeleton compile errors\n{output}")
                            step_result = _emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                            trajectory.append(step_result)
                            compiler.emit(step_result)
                            compiler.add_step_to_chain(step_result.hash)
                            compiler.resolve_current_gap(gap.hash)
                            step_result = None
                    else:
                        step_result = _emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                        trajectory.append(step_result)
                        compiler.emit(step_result)
                        compiler.add_step_to_chain(step_result.hash)
                        compiler.resolve_current_gap(gap.hash)
                        step_result = None
                elif mode == "activate_existing_chain":
                    chain_ref = intent.get("chain_ref")
                    activation = intent.get("activation", "current_turn")
                    if isinstance(chain_ref, str):
                        step_result = me.activate_chain_reference(
                            CHAINS_DIR,
                            chain_ref,
                            activation,
                            gap,
                            origin_step,
                            entry.chain_id,
                            registry,
                            compiler,
                            trajectory,
                            _turn_counter,
                        )
                    if not step_result:
                        fallback = _emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                        trajectory.append(fallback)
                        compiler.emit(fallback)
                        compiler.add_step_to_chain(fallback.hash)
                        compiler.resolve_current_gap(gap.hash)
                        step_result = None
                else:
                    step_result = _emit_reason_skill(reason_skill, gap, origin_step, entry.chain_id)
                    trajectory.append(step_result)
                    compiler.emit(step_result)
                    compiler.add_step_to_chain(step_result.hash)
                    compiler.resolve_current_gap(gap.hash)
                    step_result = None

                if step_result:
                    if step_result.gaps:
                        trajectory.append(step_result)
                        compiler.emit(step_result)
                    compiler.resolve_current_gap(gap.hash)
            else:
                # No reason.st — fall through to normal reasoning
                if resolved_data:
                    session.inject(f"## Context\n{resolved_data}")
                raw = session.call(f"Reason about: gap:{gap.hash} \"{gap.desc}\". Articulate your reasoning chain.")
                step_result, child_gaps = _parse_step_output(
                    raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                if child_gaps:
                    compiler.emit(step_result)
                else:
                    compiler.resolve_current_gap(gap.hash)

        elif vocab == "await_needed":
            # ── Bridge codon: synchronization checkpoint (pause codon) ──
            # Suspends parent chain until referenced sub-agent completes.
            # If sub-agent already done → render tree → inspect → resume.
            # If still running → persist as dangling gap → heartbeat picks up next turn.
            print(f"  → await (pause codon)")

            # Record that this chain set a manual await
            compiler.record_await(entry.chain_id)

            # Resolve the sub-agent's chain (if available)
            await_skill = registry.resolve_by_name("await")
            if await_skill:
                session.inject(f"## Await checkpoint: {gap.desc}")
                if resolved_data:
                    session.inject(f"## Sub-agent context\n{resolved_data}")

                # Create step carrying await.st's gaps
                await_step = Step.create(
                    desc=f"await checkpoint: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=[await_skill.hash] + gap.content_refs,
                    chain_id=entry.chain_id,
                )
                for st_step in await_skill.steps:
                    child_gap = Gap.create(
                        desc=st_step.desc,
                        content_refs=gap.content_refs,
                    )
                    child_gap.scores = Epistemic(
                        relevance=st_step.__dict__.get("relevance", 0.8),
                        confidence=0.8, grounded=0.0,
                    )
                    child_gap.vocab = st_step.vocab
                    child_gap.turn_id = current_turn
                    await_step.gaps.append(child_gap)

                trajectory.append(await_step)
                compiler.emit(await_step)
                compiler.resolve_current_gap(gap.hash)
                step_result = await_step
            else:
                # No await.st — resolve as observation
                if resolved_data:
                    session.inject(f"## Context\n{resolved_data}")
                raw = session.call(f"Await checkpoint: gap:{gap.hash} \"{gap.desc}\". Inspect sub-agent results.")
                step_result, child_gaps = _parse_step_output(
                    raw, step_refs=[origin_step.hash], content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                if child_gaps:
                    compiler.emit(step_result)
                else:
                    compiler.resolve_current_gap(gap.hash)

        elif vocab == "reprogramme_needed":
            # ── Bridge codon: stateless semantic state update ──
            # The LLM needs to persist or recalibrate long-horizon semantic state.
            # Current implementation routes this through st_builder.
            print(f"  → reprogramme ({vocab})")

            # Resolve any existing entity data for context
            entity_data = _resolve_entity(gap.content_refs, registry, trajectory)
            if entity_data:
                session.inject(f"## Existing entity data\n{entity_data}")
            elif resolved_data:
                session.inject(f"## Context\n{resolved_data}")

            # Inject PRINCIPLES.md + GAP_CONFIG.md — the constitution + gap specification
            # The reprogramme agent needs both to build architecturally consistent .st files
            principles_path = CORS_ROOT / "docs" / "PRINCIPLES.md"
            if principles_path.exists():
                with open(principles_path) as f:
                    principles_content = f.read()
                session.inject(
                    f"## System Principles (PRINCIPLES.md)\n"
                    f"Every .st file you create must be consistent with these principles.\n"
                    f"This is the architectural constitution.\n\n"
                    f"{principles_content}"
                )

            # GAP_CONFIG.md is a working draft — will be merged into PRINCIPLES.md
            # when the formal gap definitions are finalized

            # Inject available entities with descriptions + steps as building blocks
            entity_lines = []
            for s in registry.all_skills():
                steps_summary = " → ".join(st.action for st in s.steps) if s.steps else "(pure entity)"
                entity_lines.append(
                    f"  {s.display_name}:{s.hash} ({s.name}.st) — {s.desc[:80]}\n"
                    f"    steps: {steps_summary}"
                )
            entity_list = "\n".join(entity_lines)

            # Also inject command skills
            cmd_lines = []
            for name, s in registry.commands.items():
                steps_summary = " → ".join(st.action for st in s.steps) if s.steps else "(pure entity)"
                cmd_lines.append(
                    f"  /{name} ({s.name}.st) — {s.desc[:80]}\n"
                    f"    steps: {steps_summary}"
                )
            cmd_list = "\n".join(cmd_lines) if cmd_lines else "  (none)"
            session.inject(f"## Step Network\n{_render_step_network(registry)}")

            raw = session.call(
                f"You need to reprogramme your knowledge: gap:{gap.hash} \"{gap.desc}\"\n\n"
                "## Known entities (reference by hash, use as building blocks)\n"
                f"{entity_list}\n\n"
                "## Available /command workflows\n"
                f"{cmd_list}\n\n"
                "## Compose semantic state for a .st package\n\n"
                "Treat .st as step manifestation, not as plain file content.\n"
                "Your job here is to persist semantic state that keeps the system informed over time.\n\n"
                "### Structural distinction\n"
                "- entity.st: manifests primarily as semantic/context injection.\n"
                "- action.st: manifests primarily as executable step flow.\n"
                "- In this branch you may create or update entity state directly.\n"
                "- You may only edit an existing action package if the user explicitly asked.\n"
                "- You may not originate a new action workflow here.\n\n"
                "### What reprogramme is for\n"
                "Use this branch to persist:\n"
                "- people, identities, preferences, communication style\n"
                "- concepts, domains, constraints, sources, scope\n"
                "- long-horizon tracked entities and background concerns\n"
                "- corrections to the system's internal model\n\n"
                "### Manifestation fields\n"
                "Include only fields relevant to the semantic state being persisted:\n"
                "- People: identity + preferences\n"
                "- Domain/compliance: constraints + sources + scope\n"
                "- Concepts: refs linking to related entity or chain hashes\n"
                "- Existing action updates: preserve explicit steps and refs; do not invent new workflow vocab\n\n"
                "### Composition rule\n"
                "Compose from existing entities and workflows first. Reuse known hashes where possible.\n"
                "If you need executable structure, reference an existing action or chain package by hash.\n"
                "Only include steps when updating an already existing executable package.\n\n"
                "### Runtime note\n"
                "Entity-like packages usually manifest as semantic injection when resolved.\n"
                "Action-like packages belong to the structural workflow side of the system.\n"
                "Current persistence path still writes JSON .st files through st_builder.\n\n"
                "### Entity references\n"
                "Reference other entities by hash, not name.\n"
                "Use refs to map names to hashes: {\"admin\": \"72b1d5ffc964\"}\n\n"
                "### Triggers\n"
                "- manual: only when explicitly invoked\n"
                "- on_contact:X: fires when user X messages\n"
                "- command:X: hidden from LLM, triggered via /X command only\n\n"
                "```json\n"
                '{"artifact_kind": "entity | action_update | hybrid_update",\n'
                ' "name": "entity_name", "desc": "what this semantic package is",\n'
                ' "trigger": "manual | on_contact:X | command:X",\n'
                ' "refs": {"entity_name": "entity_hash", "chain_name": "chain_hash"},\n'
                ' "existing_ref": "required only for action_update/hybrid_update",\n'
                ' "steps": [\n'
                '   {"action": "step_name", "desc": "what this existing step does",\n'
                '    "vocab": "hash_resolve_needed", "post_diff": false, "resolve": ["hash"]}\n'
                ' ],\n'
                ' "identity": {}, "preferences": {}, "constraints": {}, "sources": [], "scope": ""}\n'
                "```\n"
                "Only include fields relevant to this semantic package. Omit empty fields.\n"
                "Do not invent new action workflows here. For executable updates, include existing_ref."
            )
            print(f"  LLM compose: {raw[:150]}...")

            # Execute st_builder
            intent = _extract_json(raw)
            if intent:
                output, code = execute_tool("tools/st_builder.py", intent)
                print(f"  st_builder: {output[:150]}")

                reprg_result = auto_commit(f"reprogramme: {gap.desc[:50]}")
                commit_sha = reprg_result[0] if isinstance(reprg_result, tuple) else reprg_result
                if commit_sha:
                    # Record background trigger for heartbeat mechanism
                    compiler.record_background_trigger(entry.chain_id)
                    print(f"  → committed: {commit_sha}")

                    step_result = Step.create(
                        desc=f"reprogrammed: {gap.desc}",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        commit=commit_sha,
                        chain_id=entry.chain_id,
                    )
                    # No post-diff. The commit hash IS the record.
                    compiler.resolve_current_gap(gap.hash)
                else:
                    step_result = Step.create(
                        desc=f"reprogramme failed: {gap.desc}",
                        step_refs=[origin_step.hash],
                        content_refs=gap.content_refs,
                        chain_id=entry.chain_id,
                    )
                    compiler.resolve_current_gap(gap.hash)
            else:
                print("  → no intent extracted")
                step_result = Step.create(
                    desc=f"reprogramme skipped: {gap.desc}",
                    step_refs=[origin_step.hash],
                    content_refs=gap.content_refs,
                    chain_id=entry.chain_id,
                )
                compiler.resolve_current_gap(gap.hash)

        else:
            # ── Unknown vocab ──
            print(f"  → unknown ({vocab})")
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
            # Check for passive chain match — append to existing chain
            # if this step's content_refs overlap with an active chain's entity
            passive_appended = False
            for ref in step_result.content_refs:
                passive_chains = trajectory.find_passive_chains(ref)
                for pc in passive_chains:
                    if pc.hash != (entry.chain_id if entry else None):
                        trajectory.append_to_passive_chain(pc.hash, step_result)
                        passive_appended = True
                        print(f"  → appended to passive chain:{pc.hash[:8]}")
                        break
                if passive_appended:
                    break

            if not passive_appended:
                trajectory.append(step_result)
            compiler.add_step_to_chain(step_result.hash)
            print(f"  step:{step_result.hash}" +
                  (f" commit:{step_result.commit}" if step_result.commit else ""))

        # Check if done
        if compiler.is_done():
            print(f"\n  ALL GAPS RESOLVED (iteration {iteration + 1})")
            break

    # ── 6. REPROGRAMME PASS ─────────────────────────────────────────
    #
    # Automatic, pre-synthesis. The agent reviews the turn and updates
    # any .st files that need it. Not a gap — housekeeping.
    # The commit hash lands on trajectory so synthesis can see it.

    reprogramme_step = _reprogramme_pass(session, registry, trajectory)
    if reprogramme_step:
        trajectory.append(reprogramme_step)

    # ── 7. SYNTHESIS ─────────────────────────────────────────────────

    print("\n── SYNTHESIS ──")
    response = _synthesize(session, user_message)

    # ── 8. HEARTBEAT ─────────────────────────────────────────────────
    #
    # Law 9: the loop always closes.
    #
    # If any background trigger fired without a manual await, persist
    # an automatic reason_needed as a dangling gap. Next turn, this
    # heartbeat fires — the agent renders the sub-agent's tree,
    # inspects results, and either closes, revisits, or refines.
    #
    # The heartbeat is recursive: if the inspection triggers further
    # background work, another heartbeat persists. The loop closes
    # when all background chains are resolved.

    if compiler.needs_heartbeat():
        print("\n── HEARTBEAT: persisting reason_needed for background sub-agent ──")
        heartbeat_refs = compiler.background_refs()
        heartbeat_gap = Gap.create(
            desc="heartbeat: background sub-agent in progress — inspect results, close or revisit",
            step_refs=[origin_step.hash],
            content_refs=heartbeat_refs,
        )
        heartbeat_gap.scores = Epistemic(relevance=0.9, confidence=0.8, grounded=0.0)
        heartbeat_gap.vocab = "reason_needed"
        heartbeat_gap.turn_id = current_turn
        # Don't resolve — persist as dangling for next turn's resume
        heartbeat_step = Step.create(
            desc="heartbeat: automatic post-synth reason_needed for background workflow",
            step_refs=[origin_step.hash],
            gaps=[heartbeat_gap],
        )
        trajectory.append(heartbeat_step)
        print(f"  → heartbeat gap:{heartbeat_gap.hash[:8]} persisted for next turn")

    # ── 9. SAVE ──────────────────────────────────────────────────────

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
                    grounded=0.0,  # kernel computes from co-occurrence at admission
                )
                gap.vocab = g.get("vocab")
                if gap.vocab:
                    gap.vocab_score = 0.8
                gap.turn_id = _turn_counter
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


def _extract_json(raw: str) -> dict | None:
    """Extract a JSON object from LLM output."""
    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(raw[json_start:json_end])
    except (json.JSONDecodeError, KeyError):
        pass
    return None


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


def _resolve_entity(content_refs: list[str], registry: SkillRegistry,
                    trajectory: Trajectory) -> str | None:
    """Resolve entity .st files referenced in content_refs.

    Checks each ref against the skill registry. If it matches a known
    .st file (person, task, commitment, skill), render its full data.
    Falls back to trajectory resolution for non-.st hashes.
    """
    blocks = []
    for ref in content_refs:
        # Check if this hash is a known skill/entity
        skill = registry.resolve(ref)
        if skill:
            blocks.append(_render_entity(skill))
            continue
        # Try trajectory
        data = resolve_hash(ref, trajectory)
        if data:
            blocks.append(f"── {ref} ──\n{data}")
    return "\n\n".join(blocks) if blocks else None


def _skill_payload(skill: Skill) -> dict | None:
    return skill.payload or None


def _is_entity_skill(skill: Skill) -> bool:
    if skill.artifact_kind == "codon":
        return False
    if skill.artifact_kind in {"entity", "hybrid"}:
        return True
    payload = _skill_payload(skill) or {}
    return len(payload.get("steps", [])) == 0


def _render_entity_tree(registry: SkillRegistry) -> str:
    """Render entity-like .st files as a compact semantic tree."""
    entity_skills = [skill for skill in registry.all_skills() if _is_entity_skill(skill)]
    if not entity_skills:
        return "(no entity .st files)"

    lines = ["entity_tree"]
    sorted_skills = sorted(entity_skills, key=lambda skill: skill.display_name)
    for i, skill in enumerate(sorted_skills):
        payload = _skill_payload(skill) or {}
        branch = "└" if i == len(sorted_skills) - 1 else "├"
        cont = " " if i == len(sorted_skills) - 1 else "│"
        lines.append(
            f"{branch}─ {skill.display_name}:{skill.hash} ({Path(skill.source).name}, trigger:{skill.trigger})"
        )

        fields = [field for field in ENTITY_MANIFEST_FIELDS if field in payload]
        if fields:
            lines.append(f"{cont}  ├─ semantics: {', '.join(sorted(fields))}")

        refs = payload.get("refs", {})
        if refs:
            lines.append(f"{cont}  ├─ refs: {', '.join(sorted(refs.keys()))}")

        steps = payload.get("steps", [])
        if steps:
            step_names = " → ".join(step.get("action", "?") for step in steps[:4])
            more = " ..." if len(steps) > 4 else ""
            lines.append(f"{cont}  └─ steps: {step_names}{more}")
        else:
            lines.append(f"{cont}  └─ steps: (pure entity)")

    return "\n".join(lines)


def _render_step_network(registry: SkillRegistry) -> str:
    return me.render_step_network(CHAINS_DIR, registry, _is_entity_skill, _skill_payload)


def _render_entity(skill: Skill) -> str:
    """Render a .st entity's full data for session injection."""
    data = skill.payload
    if not data:
        return f"## {skill.display_name}:{skill.hash}\n(unreadable)"

    lines = [f"## Entity: {skill.display_name}:{skill.hash}"]
    lines.append(f"  name: {skill.name}")
    lines.append(f"  desc: {skill.desc}")
    lines.append(f"  trigger: {skill.trigger}")

    # Identity fields (for people)
    identity = data.get("identity", {})
    if identity:
        lines.append("  identity:")
        for k, v in identity.items():
            lines.append(f"    {k}: {v}")

    # Preferences
    preferences = data.get("preferences", {})
    if preferences:
        lines.append("  preferences:")
        for category, prefs in preferences.items():
            lines.append(f"    {category}:")
            if isinstance(prefs, dict):
                for k, v in prefs.items():
                    lines.append(f"      {k}: {v}")
            else:
                lines.append(f"      {prefs}")

    # Refs
    refs = data.get("refs", {})
    if refs:
        lines.append("  refs:")
        for k, v in refs.items():
            lines.append(f"    {k}: {v}")

    # Steps summary
    lines.append(f"  steps: {' → '.join(s.action for s in skill.steps)}")

    return "\n".join(lines)


def _reprogramme_pass(session: Session, registry: SkillRegistry,
                      trajectory: Trajectory) -> Step | None:  # noqa: ARG001
    """Automatic pre-synthesis reprogramme pass.

    The agent reviews the turn and decides if any .st files need updating.
    Not a gap — silent housekeeping. The commit hash lands on trajectory
    so synthesis can reference it.

    Returns a blob step with commit hash, or None if nothing to update.
    """
    entity_list = "\n".join(
        f"  {s.display_name}:{s.hash} ({s.name}.st)"
        for s in registry.all_skills()
    )

    raw = session.call(
        "## Pre-synthesis reprogramme check\n"
        "Review this turn. Did you learn anything new about any entity that should be persisted?\n"
        "- A preference correction or clarification\n"
        "- A new person, concept, or domain mentioned\n"
        "- Updated context about a known entity\n\n"
        f"Known entities:\n{entity_list}\n\n"
        "If YES: respond with a JSON intent for st_builder.\n"
        "Prefer pure entity updates. Do not invent new action workflows here.\n"
        "If NO: respond with exactly: NO_UPDATE"
    )

    if "NO_UPDATE" in raw:
        print("  reprogramme: no updates needed")
        return None

    print(f"\n── REPROGRAMME ──")
    print(f"  LLM: {raw[:150]}...")

    intent = _extract_json(raw)
    if not intent:
        print("  reprogramme: no valid intent extracted")
        return None

    output, code = execute_tool("tools/st_builder.py", intent)
    print(f"  st_builder: {output[:150]}")

    commit_sha, _on_reject = auto_commit(f"reprogramme: {intent.get('name', 'unknown')}")
    if commit_sha:
        print(f"  → committed: {commit_sha}")
        step = Step.create(
            desc=f"reprogrammed: {intent.get('name', 'unknown')}",
            content_refs=[commit_sha],
            commit=commit_sha,
        )
        return step

    return None


def _find_dangling_gaps(trajectory: Trajectory) -> list[Gap]:
    """Find unresolved gaps from prior turns.

    Scans the trajectory for gaps that were never resolved — either from
    clarify_needed halts or interrupted turns. These are candidates for
    resume. The LLM sees them in the trajectory tree and selects which
    to carry forward by referencing them in its pre-diff.
    """
    dangling = []
    for step_hash in trajectory.order:
        step = trajectory.resolve(step_hash)
        if step:
            for gap in step.gaps:
                if not gap.resolved and not gap.dormant:
                    dangling.append(gap)
    return dangling


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
    """Persist trajectory, chains, and extract long chains to files."""
    trajectory.save(str(TRAJ_FILE))
    trajectory.save_chains(str(CHAINS_FILE))
    # Extract long resolved chains to individual files
    chains_dir = str(CORS_ROOT / "chains")
    trajectory.extract_chains(chains_dir)
    extracted = sum(1 for c in trajectory.chains.values() if c.extracted)
    print(f"  Saved: {len(trajectory.order)} steps, {len(trajectory.chains)} chains"
          + (f" ({extracted} extracted)" if extracted else ""))


# ── Main ─────────────────────────────────────────────────────────────────

def run_command(cmd_name: str, args: str = "") -> str:
    """Run a /command .st file directly. Bypasses LLM gap routing."""
    registry = load_all(str(SKILLS_DIR))
    skill = registry.resolve_command(cmd_name)
    if not skill:
        return f"Unknown command: /{cmd_name}"

    trajectory = Trajectory.load(str(TRAJ_FILE))
    Trajectory.load_chains(str(CHAINS_FILE), trajectory)

    print(f"\n── COMMAND: /{cmd_name} ({skill.display_name}:{skill.hash}) ──")

    session = Session(model=os.environ.get("KERNEL_COMPOSE_MODEL", "gpt-4.1"))
    session.set_system(PRE_DIFF_SYSTEM)

    # Inject entity data
    entity_data = _render_entity(skill)
    session.inject(entity_data)
    if args:
        session.inject(f"## Command args\n{args}")

    # Create origin step for the command
    origin = Step.create(
        desc=f"command: /{cmd_name}",
        content_refs=[skill.hash],
    )
    trajectory.append(origin)

    # Inject skill steps as gaps onto compiler
    compiler = Compiler(trajectory)
    for st_step in skill.steps:
        gap = Gap.create(
            desc=st_step.desc,
            content_refs=[skill.hash],
        )
        gap.scores = Epistemic(relevance=0.9, confidence=0.8, grounded=0.0)
        gap.vocab = st_step.vocab
        origin.gaps.append(gap)

    compiler.emit_origin_gaps(origin)
    print(compiler.render_ledger())

    # Run iteration loop (same as run_turn)
    for iteration in range(MAX_ITERATIONS):
        entry, signal = compiler.next()
        if entry is None or signal == GovernorSignal.HALT:
            break

        gap = entry.gap
        print(f"  [{iteration+1}] gap:{gap.hash[:8]} \"{gap.desc}\" [{gap.vocab}]")

        # Resolve and execute (simplified — uses same tool routing)
        resolved = resolve_all_refs(gap.step_refs, gap.content_refs, trajectory)
        if resolved:
            session.inject(f"## Resolved\n{resolved}")

        raw = session.call(f"Execute step: \"{gap.desc}\". Articulate any new gaps.")
        step_result, child_gaps = _parse_step_output(
            raw, step_refs=[origin.hash], content_refs=gap.content_refs,
            chain_id=entry.chain_id,
        )
        trajectory.append(step_result)
        compiler.add_step_to_chain(step_result.hash)

        if child_gaps:
            compiler.emit(step_result)
        else:
            compiler.resolve_current_gap(gap.hash)

        if compiler.is_done():
            break

    # Synthesize
    response = _synthesize(session, f"/{cmd_name}")
    _save_turn(trajectory)
    return response


if __name__ == "__main__":
    print("v5 Step Kernel — cors")
    print("Type /quit to exit, /wipe to reset, /cmd to run a command\n")

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

        # /policy — view or edit tree policy
        if user_input.startswith("/policy"):
            parts = user_input.split(" ", 2)
            if len(parts) == 1:
                # /policy — show current policy
                policy = _load_tree_policy()
                print("\n── Tree Policy ──")
                for path, rule in sorted(policy.items()):
                    if rule.get("immutable"):
                        print(f"  {path:30s} immutable")
                    elif rule.get("on_mutate"):
                        print(f"  {path:30s} on_mutate → {rule['on_mutate']}")
                print()
            elif len(parts) == 3:
                # /policy path rule  (e.g. /policy media/ stitch_needed)
                path = parts[1]
                rule_str = parts[2]
                policy = _load_tree_policy()
                if rule_str == "immutable":
                    policy[path] = {"immutable": True}
                elif rule_str == "remove":
                    policy.pop(path, None)
                else:
                    policy[path] = {"on_mutate": rule_str}
                with open(TREE_POLICY_FILE, "w") as f:
                    json.dump(policy, f, indent=2)
                print(f"  policy updated: {path} → {rule_str}")
            else:
                print("  usage: /policy [path rule]")
                print("  examples:")
                print("    /policy                        — show all")
                print("    /policy media/ stitch_needed   — add on_mutate rule")
                print("    /policy data/ immutable        — add immutable rule")
                print("    /policy media/ remove          — remove rule")
            continue

        # /command routing
        if user_input.startswith("/"):
            parts = user_input[1:].split(" ", 1)
            cmd_name = parts[0]
            cmd_args = parts[1] if len(parts) > 1 else ""
            response = run_command(cmd_name, cmd_args)
            print(f"\nv5> {response}\n")
            continue

        response = run_turn(user_input)
        print(f"\nv5> {response}\n")
