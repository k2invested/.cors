# Architecture — Step Kernel v5 (cors)

## System Overview

A hash-native reasoning agent. One primitive (step), one LLM (persistent 5.4), one governor (deterministic linear algebra), one storage layer (git).

The trajectory is a closed hash graph of reasoning steps. Raw data lives in git as blobs/trees/commits. The LLM navigates the hash graph, articulates gaps, and composes commands. The compiler sequences execution via a stack-based ledger. The governor monitors epistemic convergence.

## Module Map

```
cors/
  step.py        (Layer 0)  — primitives
  compile.py     (Layer 1)  — sequencing + governor
  loop.py        (Layer 2)  — orchestration
  skills/        (Layer 0)  — step packages (.st files + loader)
  tools/         (Layer 0)  — execution scripts (standalone)
  docs/          —           — specs, architecture, principles
  tests/         —           — structural validation (95 tests)
  .git/          (Layer 0)  — content storage (blobs, trees, commits)
```

Strict layer ordering: Layer 0 has no internal dependencies. Layer 1 depends on Layer 0. Layer 2 depends on Layer 0 + 1. No circular dependencies.

---

## Module: step.py

**Purpose**: Defines the step primitive and all types that compose it. The foundation — every other module builds on these types.

**Mechanisms served**: §1 (Step), §2 (Hash layers), §4 (Chains), §11 (Dormant gaps), §12 (Recursive convergence), §13 (Closed hash graph)

### Public types

| Type | Purpose |
|------|---------|
| `Epistemic` | Epistemic signal vector (relevance, confidence, grounded). Supports vector math: `as_vector()`, `distance_to()`, `magnitude()`. |
| `Gap` | Gap articulation — desc + content_refs (Layer 2) + step_refs (Layer 1) + vocab mapping + scores + dormant flag. Every gap is hashed. |
| `Step` | The atom — pre-diff (step_refs + content_refs + desc) + post-diff (gaps + commit). Hash-addressed, immutable once created. |
| `Chain` | Reasoning chain — sequence of step hashes originating from one gap. Has its own hash. Tracked as a unit. |
| `Trajectory` | The closed hash graph — step index (hash→Step), gap index (hash→Gap), chain index, chronological order. Persistence via JSON. |

### Key functions

| Function | Signature | Purpose |
|----------|-----------|---------|
| `blob_hash(content)` | `str → str` | 12-char SHA-256 content hash |
| `chain_hash(step_hashes)` | `list[str] → str` | Hash a sequence of step hashes |
| `Step.create(...)` | `→ Step` | Factory with auto-hash and timestamp |
| `Gap.create(...)` | `→ Gap` | Factory with auto-hash from desc+refs |
| `Chain.create(origin_gap, first_step)` | `→ Chain` | Start a new chain |
| `Trajectory.render_recent(n)` | `→ str` | Render last N chains for LLM context |
| `Trajectory.save(path)` / `.load(path)` | | JSON persistence |

### Invariants

- Steps are immutable after creation (hash derived from content + timestamp)
- Gaps are immutable after creation (hash derived from desc + refs)
- Two hash layers never mixed: step_refs for Layer 1, content_refs for Layer 2
- Every gap stored in gap_index regardless of dormant status
- Trajectory only appends — never overwrites

---

## Module: compile.py

**Purpose**: The compiler — structures execution from semantic emissions. Manages the ledger (stack-based ordered frontier), enforces OMO rhythm, tracks chain lifecycle, and hosts the governor's convergence detection.

**Mechanisms served**: §7 (Governor), §9 (Ledger), §10 (OMO), §14 (Vocab bridge), §15 (No micro loop), §16 (post_diff config)

### Public types

| Type | Purpose |
|------|---------|
| `LedgerEntry` | A gap on the ledger with placement metadata (chain_id, depth, parent_gap) |
| `Ledger` | Stack-based ordered frontier. Push origin/child gaps, pop from top, track resolved/history. |
| `ChainState` | Enum: OPEN, ACTIVE, SUSPENDED, CLOSED |
| `GovernorSignal` | Enum: ALLOW, CONSTRAIN, REDIRECT, REVERT, ACT, HALT |
| `GovernorState` | Tracks epistemic vectors across steps for convergence/stagnation/divergence/oscillation detection |
| `Compiler` | The sequencer — emission→admission→placement, pop+route, OMO enforcement, chain management |

### Key functions

| Function | Purpose |
|----------|---------|
| `Compiler.emit(step)` | Three-part lifecycle: emission → admission (threshold) → placement (stack push) |
| `Compiler.emit_origin_gaps(step)` | Same but creates new chains per gap (for initial pre-diff) |
| `Compiler.next()` | Pop top of stack, get governor signal. Returns (entry, signal). |
| `Compiler.validate_omo(vocab)` | Check if proposed action respects O-M-O transition grammar |
| `Compiler.resolve_current_gap(hash)` | Mark gap resolved, check chain completion |
| `govern(entry, chain_length, state)` | Pure deterministic governor — measures vectors, returns signal |

### Constants

| Name | Value | Purpose |
|------|-------|---------|
| `ADMISSION_THRESHOLD` | 0.4 | Minimum combined score for gap to enter ledger |
| `CONFIDENCE_THRESHOLD` | 0.8 | Gap resolved when confidence exceeds this |
| `DORMANT_THRESHOLD` | 0.2 | Below this, gap stored as dormant |
| `MAX_CHAIN_DEPTH` | 15 | Force-close chain beyond this |
| `SATURATION_THRESHOLD` | 0.05 | Information gain below this = stagnation |
| `CHAIN_EXTRACT_LENGTH` | 8 | Chains longer than this extracted to file |

### Vocab sets

| Set | Members | Maps to |
|-----|---------|---------|
| `OBSERVE_VOCAB` | scan_needed, pattern_needed, hash_resolve_needed, research_needed, email_needed, url_needed, registry_needed, external_context | Hash resolution / read tools |
| `MUTATE_VOCAB` | content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed | Execution tools / .st scripts |
| `BRIDGE_VOCAB` | judgment_needed, task_needed, commitment_needed, profile_needed, task_status_needed | Internal bridges |

### Invariants

- Ledger is LIFO — deepest child popped first
- One chain at a time — depth-first per origin gap
- OMO enforced — no consecutive mutations without observation
- Admission requires combined score ≥ ADMISSION_THRESHOLD
- Dormant gaps stored on trajectory but never enter ledger
- Force-close at MAX_CHAIN_DEPTH

---

## Module: skills/loader.py

**Purpose**: Loads `.st` files from the skills directory, hashes them, and builds a resolvable registry. The LLM references skills by hash. The kernel resolves them to step sequences.

**Mechanisms served**: §8 (Predefined step hashes), §14 (Vocab bridge), §17 (.st as manifestation), §18 (Identity as .st)

### Public types

| Type | Purpose |
|------|---------|
| `SkillStep` | One atomic step within a skill: action, desc, vocab, post_diff |
| `Skill` | A complete skill: hash, name, desc, steps[], source path |
| `SkillRegistry` | Map of hash→Skill and name→Skill. Resolve by hash or name. |

### Key functions

| Function | Purpose |
|----------|---------|
| `load_skill(path)` | Load one .st file → Skill |
| `load_all(skills_dir)` | Load all .st files → SkillRegistry |
| `SkillRegistry.resolve(hash)` | Hash → Skill |
| `SkillRegistry.render_for_prompt()` | Render all skills as LLM context |

---

## Module: loop.py (to be written)

**Purpose**: The turn loop — orchestrates one turn from user input to synthesis. Manages the persistent 5.4 session, feeds pre/post iterations, invokes the compiler, resolves hashes, executes tools, and produces the final response.

**Mechanisms served**: §2 (LLM as attention), §3 (Commits), §5 (Navigation), §6 (One LLM one governor), §19 (HEAD injection)

### Turn flow

```
1. admin.st fires (identity injection)
2. HEAD commit injected (workspace state)
3. LLM reads trajectory + input → pre-diff (gap articulations with hash refs)
4. LLM scores gaps against vocab → post-diff skeleton
5. Compiler admits gaps → ledger populated
6. Compiler pops top gap → governor signal
7. Kernel resolves gap's hash refs → injects into LLM session
8. LLM reasons over resolved data → new gaps or command composition
9. Kernel executes if mutation → auto-commit
10. Postcondition fires (observe new commit)
11. Repeat from 6 until HALT
12. Synthesize response from session
```

---

## Module: tools/st_builder.py

**Purpose**: Builds valid `.st` files from semantic intent. The agent describes what it wants in natural language, the builder handles structure, format, and validation.

**Mechanisms served**: §8 (Predefined step hashes), §17 (.st as manifestation)

### Interface

Input (stdin JSON): semantic intent with name, desc, trigger, actions
Output: validated .st file written to skills/

---

## Module: tools/hash_resolve.py

**Purpose**: Resolves blob hashes from the trajectory. Reads step hashes from params, looks up in self.json/trajectory, returns full step data for each hash found. Follows refs up to depth N.

**Mechanisms served**: §5 (Navigation), §12 (Recursive convergence), §13 (Closed hash graph)

---

## Dependencies

```
step.py          → (no dependencies)
compile.py       → step.py
skills/loader.py → (no dependencies)
loop.py          → step.py, compile.py, skills/loader.py
tools/*          → (standalone scripts, no module imports)
```

Zero circular dependencies. Strict DAG.
