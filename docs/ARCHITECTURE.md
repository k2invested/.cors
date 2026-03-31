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
| `Epistemic` | Epistemic signal vector (relevance, confidence, grounded). relevance and confidence are LLM-assessed. grounded is computed deterministically by the kernel from hash co-occurrence frequency. Supports vector math: `as_vector()`, `distance_to()`, `magnitude()`. |
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
| `Trajectory.render_recent(n, registry=None)` | `→ str` | Render trajectory as traversable hash tree with named skill references |
| `Trajectory._tag_ref()` | helper | Tag a hash reference with its type (step/gap/blob) |
| `Trajectory._render_refs()` | helper | Render a list of refs with their tags |
| `Trajectory._render_steps_as_tree()` | helper | Render steps as an indented hash tree structure |
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
| `_compute_grounded(gap)` | Compute grounded score deterministically from hash co-occurrence frequency |
| `_admission_score(gap)` | Compute admission score: 0.8*rel + 0.2*grounded (relevance-dominant, grounded deterministic) |
| `govern(entry, chain_length, state)` | Pure deterministic governor — measures vectors, returns signal |

### Constants

| Name | Value | Purpose |
|------|-------|---------|
| `ADMISSION_THRESHOLD` | 0.4 | Min admission score (0.8*rel + 0.2*grounded) to enter ledger |
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
- Admission requires 0.8*rel + 0.2*grounded ≥ ADMISSION_THRESHOLD (relevance-dominant, grounded deterministic)
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
| `Skill` | A complete skill: hash, name, display_name, desc, steps[], source path. display_name: extracted from identity.name or defaults to skill name — used in tree render |
| `SkillRegistry` | Map of hash→Skill and name→Skill. Resolve by hash or name. |

### Key functions

| Function | Purpose |
|----------|---------|
| `load_skill(path)` | Load one .st file → Skill |
| `load_all(skills_dir)` | Load all .st files → SkillRegistry |
| `SkillRegistry.resolve(hash)` | Hash → Skill |
| `SkillRegistry.resolve_name(hash)` | Hash → display name for tree rendering (kenny, research, etc.) |
| `SkillRegistry.render_for_prompt()` | Render all skills as LLM context |

---

## Module: loop.py

**Status**: IMPLEMENTED

**Purpose**: The turn loop — orchestrates one turn from user input to synthesis. Manages the persistent 5.4 session, feeds pre/post iterations, invokes the compiler, resolves hashes, executes tools, and produces the final response.

**Mechanisms served**: §2 (LLM as attention), §3 (Commits), §5 (Navigation), §6 (One LLM one governor), §19 (HEAD injection)

### Public types

| Type | Purpose |
|------|---------|
| `Session` | Persistent LLM session — accumulates messages, manages context window |

### System prompts

| Prompt | Purpose |
|--------|---------|
| `PRE_DIFF_SYSTEM` | Teaches gaps, epistemic triad, hash tree navigation, identity |
| `COMPOSE_SYSTEM` | Composition prompt for tool parameterization |
| `SYNTH_SYSTEM` | Synthesis prompt for final response generation |

### Execution modes

| Mode | Description |
|------|-------------|
| Deterministic | Kernel resolves — no LLM needed (e.g. scan, registry) |
| Composed | 5.4 writes command — LLM parameterizes tool execution |
| Observation-only | Blob step, no post-diff — data ingestion without gap emission |

### Key functions

| Function | Purpose |
|----------|---------|
| `resolve_hash()` | Tries trajectory step → trajectory gap → git object |
| `TOOL_MAP` | Vocab → tool script mapping |
| `DETERMINISTIC_VOCAB` | Vocab items resolved by kernel without LLM |
| `OBSERVATION_ONLY_VOCAB` | Vocab items that produce blob steps with no post-diff |

### Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required — LLM access |
| `KERNEL_COMPOSE_MODEL` | Compose/synthesis model |

### Turn flow

```
1. Message arrives
2. Load trajectory + skills + HEAD
3. First LLM pass → first atomic step (origin)
4. Identity .st fires AFTER first step
5. Compiler admits gaps
6. Iteration loop: pop → execute by vocab → inject → next step
7. HALT → synthesize
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
