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
| `LedgerEntry` | A gap on the ledger with placement metadata (chain_id, depth, parent_gap, priority) |
| `Ledger` | Stack-based ordered frontier. Push origin/child gaps, pop from top, sort by priority, track resolved/history. |
| `ChainState` | Enum: OPEN, ACTIVE, SUSPENDED, CLOSED |
| `GovernorSignal` | Enum: ALLOW, CONSTRAIN, REDIRECT, REVERT, ACT, HALT |
| `GovernorState` | Tracks epistemic vectors across steps for convergence/stagnation/divergence/oscillation detection |
| `Compiler` | The sequencer — emission→admission→placement, pop+route, OMO enforcement, chain management |

### Key functions

| Function | Purpose |
|----------|---------|
| `Compiler.emit(step)` | Three-part lifecycle: emission → admission (threshold) → placement (stack push) |
| `Compiler.emit_origin_gaps(step)` | Same but creates new chains per gap (for initial pre-diff). Sorts by priority after emission. |
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
| `STAGNATION_WINDOW` | 3 | N steps with no movement = stagnation |
| `CHAIN_EXTRACT_LENGTH` | 8 | Chains longer than this extracted to file |

### Vocab sets

| Set | Members | Maps to |
|-----|---------|---------|
| `OBSERVE_VOCAB` | pattern_needed, hash_resolve_needed, email_needed, external_context, clarify_needed | Hash resolution / read tools / clarification halt |
| `MUTATE_VOCAB` | hash_edit_needed, content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed | Execution tools / .st scripts |
| `BRIDGE_VOCAB` | reprogramme_needed | The single bridge primitive — create/update entity .st files |

### Key functions (vocab)

| Function | Purpose |
|----------|---------|
| `vocab_priority(vocab)` | Priority ordering for ledger: observe (20) → mutate (40) → reprogramme (99). Returns sort key. |
| `is_observe(vocab)` / `is_mutate(vocab)` / `is_bridge(vocab)` | Vocab set membership checks |

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
| `Skill` | A complete skill: hash, name, display_name, desc, steps[], source path, trigger, is_command. display_name: extracted from identity.name or defaults to skill name — used in tree render |
| `SkillRegistry` | Map of hash→Skill, name→Skill, and commands dict. Two visibility tiers: bridge skills (LLM-surfaceable) and command skills (hidden, /command only). |

### Key functions

| Function | Purpose |
|----------|---------|
| `load_skill(path)` | Load one .st file → Skill |
| `load_all(skills_dir)` | Load all .st files → SkillRegistry |
| `SkillRegistry.resolve(hash)` | Hash → Skill |
| `SkillRegistry.resolve_name(hash)` | Hash → display name for tree rendering (kenny, research, etc.) |
| `SkillRegistry.resolve_by_name(name)` | Name → Skill |
| `SkillRegistry.resolve_command(name)` | Resolve a /command by name. Command skills are hidden from LLM registry. |
| `SkillRegistry.all_commands()` | List all command skills |
| `SkillRegistry.render_for_prompt()` | Render all skills as LLM context (excludes command skills) |

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
| `PRE_DIFF_SYSTEM` | Teaches gaps, epistemic triad, hash tree navigation, identity, gap discipline, clarify_needed. Dynamic: BRIDGE_VOCAB_PLACEHOLDER replaced at runtime with entity list + explanation that entity resolution uses hash_resolve_needed (no separate vocab). |
| `COMPOSE_SYSTEM` | Composition prompt for tool parameterization |
| `SYNTH_SYSTEM` | Synthesis prompt for final response generation |

### Execution modes

| Mode | Description |
|------|-------------|
| Deterministic | Kernel resolves — no LLM needed (hash_resolve_needed) |
| Observation-only | Blob step, no post-diff — data ingestion without gap emission (hash_resolve_needed, external_context) |
| Observation | Tool executes, LLM reasons over result (pattern_needed, email_needed) |
| Clarify | clarify_needed halts iteration, gap persists on trajectory for next-turn resume |
| Mutation | 5.4 composes command, kernel executes, auto-commit, universal postcondition fires. Failed executions (non-zero exit) recorded as "FAILED: desc" on trajectory, not committed, gap left unresolved. |
| Reprogramme | Create/update entity .st via st_builder |
| .st auto-route | script_edit_needed/content_needed/json_patch_needed/hash_edit_needed targeting .st files rerouted to reprogramme_needed |

### Key functions

| Function | Purpose |
|----------|---------|
| `run_turn(message, contact_id)` | Complete turn lifecycle — returns synthesis |
| `run_command(cmd_name, args)` | Run a /command .st file directly, bypasses LLM gap routing |
| `resolve_hash()` | Tries skill registry (.st entity) → trajectory step → trajectory gap → git object |
| `_find_dangling_gaps()` | Find unresolved gaps from prior turns (clarify_needed, interrupted). Called at turn start for resume check. |
| `auto_commit(message)` | Git add -A + commit, returns SHA or None. Universal postcondition: every commit injects hash_resolve_needed gap targeting commit SHA onto ledger. |
| `TOOL_MAP` | Vocab → tool script mapping (includes hash_edit_needed → tools/hash_manifest.py) |
| `DETERMINISTIC_VOCAB` | {hash_resolve_needed} — kernel resolves without LLM |
| `OBSERVATION_ONLY_VOCAB` | {hash_resolve_needed, external_context} — blob steps with no post-diff |
| `_skill_registry` | Module-level variable set by run_turn. Used by resolve_hash to check if a hash is a .st file. |
| `_reprogramme_pass()` | Automatic pre-synthesis pass — agent reviews turn, updates .st files if needed. Runs between iteration loop and synthesis. |
| `_resolve_entity()` | Resolve entity .st files from content_refs via skill registry |
| `_render_entity()` | Render a .st entity's full data (identity, preferences, refs, steps) for session injection |

### Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required — LLM access |
| `KERNEL_COMPOSE_MODEL` | Compose/synthesis model |

### Turn flow

```
1. Message arrives
2. Load trajectory + skills + HEAD. Set _skill_registry for resolve_hash access.
3. Build dynamic system prompt (BRIDGE_VOCAB_PLACEHOLDER replaced with entity list + hash_resolve explanation)
4. Resume check: _find_dangling_gaps() surfaces unresolved gaps from prior turns
5. First LLM pass → first atomic step (origin)
6. Identity .st fires AFTER first step
7. Compiler admits gaps, sorts by priority
8. Iteration loop: pop → execute by vocab → inject → next step
   - clarify_needed: halt iteration, gap persists for next-turn resume
   - .st auto-route: mutations targeting .st files (incl. hash_edit_needed) rerouted to reprogramme_needed
   - Execution failure: non-zero exit recorded as "FAILED: desc", not committed, gap left unresolved
   - Universal postcondition: every auto_commit injects hash_resolve_needed → commit SHA
9. Reprogramme pass (automatic, pre-synthesis housekeeping)
10. HALT → synthesize
11. Save trajectory + chains
```

---

## Module: tools/st_builder.py

**Purpose**: Builds valid `.st` files from semantic intent. The agent describes what it wants in natural language, the builder handles structure, format, and validation.

**Mechanisms served**: §8 (Predefined step hashes), §17 (.st as manifestation)

### Interface

Input (stdin JSON): semantic intent with name, desc, trigger, actions
Output: validated .st file written to skills/

---

## Module: tools/hash_manifest.py

**Purpose**: Universal file I/O by hash reference. Single tool for all file mutations. Read by hash, write, patch, diff. Routes mutations by file type to specialized tools (.st → st_builder.py, .json → json_patch.py, .docx → doc_edit.py, .pdf → pdf_fill.py).

**Mechanisms served**: §3 (Commits), §13 (Closed hash graph), §14 (Vocab bridge)

### Interface

Input (stdin JSON): `{"action": "read|write|patch|diff", "path": "relative/path", "content": "...", "patch": {"old": "...", "new": "..."}, "ref": "commit_sha"}`

### File type routing (TOOL_ROUTES)

| Extension | Delegated tool |
|-----------|---------------|
| .st | st_builder.py |
| .json | json_patch.py |
| .docx | doc_edit.py |
| .pdf | pdf_fill.py |

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
