# loop.py — The Turn Loop

**Layer**: 2 (depends on step.py, compile.py, skills/loader.py)
**Principles**: §2, §3, §5, §6, §19, §20

## Purpose

Orchestrates one turn from user input to synthesis. Manages the persistent 5.4 session, feeds pre/post iterations, invokes the compiler, resolves hashes via git, executes tools, and produces the final response.

## Status: TO BE WRITTEN

The current loop.py is from the early minimal prototype. It needs a full rewrite based on the finalized architecture.

## Turn Flow

```
1. INIT
   - Load trajectory from trajectory.json
   - Load skills from skills/
   - Resolve git HEAD → inject workspace state as hash data

2. IDENTITY
   - Match contact_id → find .st file with trigger on_contact:X
   - Resolve identity .st → inject deterministic gaps (load prefs, principles, recent)
   - Execute identity gaps (all post_diff: false → instant)

3. PRE-DIFF (persistent 5.4)
   - Inject: trajectory (recent chain hashes) + HEAD tree + user message
   - LLM reads trajectory, follows step hashes, articulates causal chains
   - Each articulation IS a gap — references content hashes + step hashes
   - Output: multiple gap articulations with hash refs

4. POST-DIFF SKELETON (same 5.4)
   - LLM scores each gap against system vocab
   - Direct mapping + score per gap
   - Output: vocab + score per gap

5. COMPILER
   - Admit gaps above threshold onto ledger
   - Dormant gaps stored on trajectory (not on ledger)
   - Pop top of stack → governor signal

6. ITERATION LOOP
   a. Kernel resolves all hashes referenced in selected gap
   b. Injects resolved data into 5.4 session
   c. 5.4 produces new perception (pre-diff):
      - If gap needs observation → LLM reasons over resolved data → may surface child gaps
      - If gap needs mutation → LLM composes command
   d. Kernel executes if mutation → auto-commit
   e. Postcondition fires: resolve new commit blob (automatic observation)
   f. Compiler emits child gaps from step → push onto stack
   g. Pop next → governor signal → repeat

7. SYNTHESIS
   - Compiler.is_done() → all gaps resolved
   - Synthesize response from session context
   - Save step to trajectory
   - Commit trajectory.json if changed

## Key Responsibilities

| Component | Role |
|-----------|------|
| Persistent 5.4 | Reads structure, produces meaning (pre-diff, post-diff, commands, synthesis) |
| Compiler | Sequences gaps via stack, enforces OMO, manages chains |
| Kernel (loop.py) | Resolves hashes via git, executes tools, auto-commits, manages session |
| Governor (in compile.py) | Monitors epistemic vectors, gates action |
| Skills (loader.py) | Resolves .st files, injects child gaps into ledger |

## Context Window Management

The persistent session accumulates only:
- New content (freshly resolved hash data)
- LLM's own reasoning (pre-diff, post-diff outputs)
- User message

Everything previously observed exists as hash references on the trajectory. Never re-injected. The context window is a workspace, not a warehouse.

## Hash Resolution

When a gap references content hashes, the kernel resolves them before injection:

```python
for ref in gap.content_refs:
    data = git_resolve(ref)  # blob → file content, tree → listing, commit → diff
    inject_into_session(ref, data)
```

Resolution methods:
- `git show <hash>` — blob content
- `git ls-tree <hash>` — tree listing
- `git diff <hash1>..<hash2>` — commit diff
- Trajectory lookup — step hash → Step object

## Tool Execution

When vocab maps to a tool:
```
vocab → tool script path (from preconditions or .st)
→ kernel spawns subprocess
→ pipes params to stdin
→ captures stdout/stderr
→ if mutation: git add + commit → SHA recorded
→ result fed back into session
```

When vocab maps to a .st file:
```
vocab → .st file resolved
→ child gaps injected into ledger
→ compiler addresses them depth-first
→ each child gap follows its own vocab routing
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| OPENAI_API_KEY | LLM API access |
| FILE_WORKSPACE | Working directory (default: repo root) |
