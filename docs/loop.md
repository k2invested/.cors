# loop.py — The Turn Loop

**Layer**: 2 (depends on step.py, compile.py, skills/loader.py)
**Principles**: §2, §3, §5, §6, §17, §18, §19, §20

## Purpose

Orchestrates one turn from user input to synthesis. Manages a persistent LLM session, produces the first step (origin), fires identity .st, invokes the compiler, resolves hashes, executes tools, and synthesizes the response.

## Status: IMPLEMENTED

## Turn Flow

1. INIT — Load trajectory from trajectory.json, load chains from chains.json, load skills from skills/, register_bridge_vocab(), resolve git HEAD. Build dynamic system prompt (BRIDGE_VOCAB_PLACEHOLDER replaced with actual entity list from registry).
2. FIRST STEP (origin) — Inject trajectory (hash tree via render_recent) + HEAD tree + user message into persistent session. LLM produces first atomic step with gap articulations. This is the origin of the turn's causal chain.
3. IDENTITY — Fire contact's .st file (e.g. admin.st) AFTER the first step, not before. Identity loads mid-context where it won't be pushed out. Identity step references the skill hash (kenny:72b1d5ffc964).
4. COMPILER — Admit origin gaps onto ledger, sort by priority (internal& first, reprogramme last). If no gaps → auto-synthesize.
5. ITERATION LOOP (max 30 rounds):
   a. Pop top gap → governor signal
   b. Resolve hash references (trajectory step → trajectory gap → git object)
   c. Execute by vocab:
      - Observation-only (hash_resolve_needed, external_context): resolve + inject, blob step, no post-diff
      - Deterministic (hash_resolve_needed): kernel resolves directly, LLM reasons over result
      - Observation (pattern_needed, email_needed): tool executes, LLM reasons
      - Mutation (hash_edit_needed, content_needed, script_edit_needed, etc.): .st auto-route check first (mutations targeting .st files rerouted to reprogramme_needed), then 5.4 composes command, kernel executes, auto-commit, universal postcondition fires (hash_resolve_needed → commit SHA)
      - Reprogramme (reprogramme_needed): compose .st intent via LLM → execute st_builder → auto-commit
      - Entity bridge ({entity}_needed): resolve existing .st into context (internal &, no mutation), LLM reasons
      - Unknown: LLM addresses directly
   d. Record step on trajectory + chain
   e. If compiler.is_done() → break
6. REPROGRAMME PASS — Automatic pre-synthesis housekeeping. Agent reviews turn, updates .st files if needed via st_builder. Commit hash lands on trajectory.
7. SYNTHESIS — Inject SYNTH_SYSTEM, LLM synthesizes response
8. SAVE — Persist trajectory.json and chains.json

## Key Types

### Session
Persistent LLM session for one turn. Accumulates messages — the LLM's own outputs stay in context. New data injected as user messages.

| Method | Purpose |
|--------|---------|
| set_system(content) | Set system message once at turn start |
| inject(content, role) | Inject content into session (default role: user) |
| call(user_content) → str | Call LLM, optionally inject user content first |
| message_count() → int | Number of messages in session |

## System Prompts

### PRE_DIFF_SYSTEM
Teaches the LLM:
- What a step is (universal primitive — people, workflows, ideas, events, tasks are all steps)
- What a gap is (verifiable discrepancy: observational or misalignment)
- Epistemic triad scoring (relevance + confidence scored by LLM, grounded computed by kernel)
- Gap discipline (one gap per entity, entity bridges have no post-diff, no hash refs needed on entity gaps)
- Hash tree navigation (how to read the trajectory tree, trace causality, reverse-engineer state)
- Identity as entity (user hash is a mental model to reason about, not instructions to follow)
- Vocab mapping (observe/mutate terms + dynamic bridge section)
- Output format: natural reasoning with embedded JSON block containing gaps

The prompt is dynamic: BRIDGE_VOCAB_PLACEHOLDER is replaced at runtime with the actual entity list from the skill registry, showing available entities to resolve and reprogramme_needed for knowledge persistence.

### COMPOSE_SYSTEM
Command composition for mutation gaps. LLM produces JSON with `command` and `reasoning` fields. Prefers python3 one-liners over sed for macOS compatibility.

### SYNTH_SYSTEM
Final response synthesis — concise, conversational, no internal details. Do not mention hashes, trajectory, or internal systems.

## Hash Resolution

resolve_hash(ref, trajectory) tries three sources in order:
1. Trajectory step — step hash → full step data (desc, refs, gaps, commit)
2. Trajectory gap — gap hash → gap data with scores (relevance, confidence, grounded)
3. Git object — git show → blob/tree/commit content

resolve_all_refs(step_refs, content_refs, trajectory) resolves all references and formats as labeled injection blocks (`── resolved step:<hash> ──` and `── resolved <hash> ──`).

## Tool Execution

TOOL_MAP maps vocab → tool script path:

| Vocab | Tool Script |
|-------|-------------|
| hash_resolve_needed | (inline — resolve_hash) |
| pattern_needed | tools/file_grep.py |
| email_needed | tools/email_check.py |
| external_context | (inline — LLM surfaces from context) |
| hash_edit_needed | tools/hash_manifest.py |
| content_needed | tools/file_write.py |
| script_edit_needed | tools/file_edit.py |
| command_needed | tools/code_exec.py |
| message_needed | tools/email_send.py |
| json_patch_needed | tools/json_patch.py |
| git_revert_needed | tools/git_ops.py |

Execution modes:
- DETERMINISTIC_VOCAB: {hash_resolve_needed} — kernel resolves directly, LLM reasons over injected result, may produce child gaps
- OBSERVATION_ONLY_VOCAB: {hash_resolve_needed, external_context} — resolve into context, blob step (no post-diff, no child gaps)
- Observation vocab (is_observe): tool executes as subprocess, LLM reasons over result, may produce child gaps
- Mutation vocab (is_mutate): .st auto-route check first (script_edit_needed/content_needed/json_patch_needed targeting .st files rerouted to reprogramme_needed), then OMO validation, 5.4 composes command via JSON, kernel executes via shell, auto-commits if changes detected, universal postcondition fires (hash_resolve_needed gap targeting commit SHA injected onto ledger)
- Reprogramme (reprogramme_needed): compose .st intent via LLM → execute st_builder → auto-commit. No post-diff.
- Entity bridge ({entity}_needed via is_bridge): resolve existing .st into context (internal &, no mutation), LLM reasons, may produce child gaps

Tools execute as subprocesses: stdin receives JSON params, stdout returns result. Timeout: 30 seconds. Working directory: CORS_ROOT.

## Key Functions

| Function | Purpose |
|----------|---------|
| run_turn(message, contact_id) → str | Complete turn lifecycle, returns synthesis |
| run_command(cmd_name, args) → str | Run a /command .st file directly, bypasses LLM gap routing |
| resolve_hash(ref, trajectory) → str? | Resolve any hash (step/gap/git) |
| resolve_all_refs(step_refs, content_refs, trajectory) → str | Resolve + format all refs as injection blocks |
| execute_tool(tool_path, params) → (str, int) | Subprocess tool execution (stdin JSON → stdout) |
| auto_commit(message) → str? | Git add -A + commit, returns short SHA or None |
| git_head() → str | Current HEAD hash (short) |
| git_tree(commit) → str | File listing at commit (--name-only -r) |
| git_show(ref) → str | Resolve git object to content |
| git_diff(from_ref, to_ref) → str | Diff between two commits |
| git(cmd, cwd) → str | Run any git command, return stdout |

## Helper Functions

| Function | Purpose |
|----------|---------|
| _parse_step_output(raw, step_refs, content_refs, chain_id) → (Step, list[Gap]) | Parse LLM output → Step + gaps. Extracts JSON block from natural text. Sets gap.vocab and gap.scores from LLM-provided values. Grounded always 0.0 (kernel computes at admission). |
| _extract_json(raw) → dict? | Extract a JSON object from LLM output |
| _extract_command(raw) → str? | Extract `command` field from LLM JSON output |
| _find_identity_skill(contact_id, registry) → Skill? | Find .st file with `trigger: "on_contact:<contact_id>"` |
| _render_identity(skill) → str | Format identity + preferences from .st file for session injection |
| _resolve_entity(content_refs, registry, trajectory) → str? | Resolve entity .st files referenced in content_refs. Checks skill registry first, falls back to trajectory. |
| _render_entity(skill) → str | Render a .st entity's full data (name, desc, trigger, identity, preferences, refs, steps) for session injection |
| _reprogramme_pass(session, registry, trajectory) → Step? | Automatic pre-synthesis reprogramme pass. Agent reviews turn, decides if .st files need updating. Routes to st_builder. Returns blob step with commit hash, or None. |
| _synthesize(session, message) → str | Inject SYNTH_SYSTEM and produce final response |
| _save_turn(trajectory) | Persist trajectory.json and chains.json |

## Configuration

| Constant | Value | Purpose |
|----------|-------|---------|
| CORS_ROOT | Path(__file__).parent | Root directory for all paths |
| SKILLS_DIR | CORS_ROOT / "skills" | Skills directory |
| TRAJ_FILE | CORS_ROOT / "trajectory.json" | Trajectory persistence |
| CHAINS_FILE | CORS_ROOT / "chains.json" | Chain persistence |
| MAX_ITERATIONS | 30 | Max iteration loop rounds |
| TRAJECTORY_WINDOW | 10 | Recent chains to render for LLM |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| OPENAI_API_KEY | LLM API access (OpenAI client) |
| KERNEL_COMPOSE_MODEL | LLM model for session (default: gpt-4.1) |

## Key Responsibilities

| Component | Role |
|-----------|------|
| Persistent LLM (Session) | Reads structure, produces meaning (gap articulations, commands, synthesis) |
| Compiler | Sequences gaps via stack (priority-sorted), enforces OMO, manages chains |
| Kernel (loop.py) | Resolves hashes, executes tools, auto-commits with universal postcondition, manages session, runs reprogramme pass |
| Governor (in compile.py) | Monitors epistemic vectors, gates action (HALT, REVERT signals) |
| Skills (loader.py) | Resolves .st files, provides named hash resolution, separates bridge vs command visibility |

## Context Window Management

The persistent session accumulates only:
- Trajectory hash tree (initial seed via render_recent)
- HEAD workspace state
- User message + identity
- Freshly resolved hash data (per iteration)
- LLM's own reasoning

Everything previously observed exists as hash references on the trajectory. Never re-injected. The context window is a workspace, not a warehouse.

## REPL

The module includes a `__main__` block that runs an interactive REPL:
- `you>` prompt accepts user input
- `/quit` exits
- `/wipe` deletes trajectory.json and chains.json (reset)
- Each input runs `run_turn()` and prints the synthesis
