# Principles v5 — Step Kernel

## 1. The Primitive: Step

A step is meaningful movement. It is the only primitive.

A step is a transition — not a snapshot, not a state, but the movement between states. Every behaviour in the system is expressible as a step. Every mechanism is step operating at a different scale.

### Two-phase transition

**Phase 1 — Pre-diff (perception)**: the LLM follows step hashes through the trajectory, articulates causal chains, and references content hashes (blobs/trees/commits). Each articulation IS a gap — grounded in referred context, encoding an ideal state that vocab can map onto.

**Phase 2 — Post-diff (gap scoring)**: the LLM scores each gap against system vocab. The compiler admits gaps above threshold onto the ledger. The kernel resolves hash data. OMO rhythm enforces observe-mutate-observe.

```
input/event arrives
  → LLM perceives within trajectory (pre-diff: articulated gaps with hash refs)
  → LLM scores gaps against vocab (post-diff: vocab mapping + scores)
  → compiler admits, places, and sequences gaps on the ledger
  → kernel resolves hashes, executes tools, commits mutations
  → the pair (pre, post) IS the step
```

### Two hash layers (never mixed)

- **Step hashes** (Layer 1): reasoning trajectory. Steps reference steps.
- **Content hashes** (Layer 2): blobs, trees, commits. Gaps reference content.

The trajectory is a closed hash graph. Raw data never touches it. Only hash references and semantic descriptions. Entities are identified by hash, not path.

## 2. The LLM as Attention Mechanism

The LLM is an attention mechanism that produces qualitative semantic judgment over structured transition states and content hashes. It does not control, execute, or route. It attends to structure and produces meaning.

```
Kernel: structure, execution, deterministic routing
LLM:    attention, semantics, qualitative judgment
```

The LLM reads structure → produces meaning.
The kernel reads meaning → produces structure.

### Single persistent session

One persistent 5.4 session per turn. The LLM iterates pre→post→pre→post within one context window. No separate mini. The same LLM does perception, gap scoring, and command composition — all in one continuous stream.

The trajectory is rendered as a traversable hash tree (same shape as git commit trees) via render_recent(). Known skill hashes render with named prefixes (e.g. kenny:72b1d5ffc964, research:a72c3c4dec0c).

Coherence comes from the persistent session. The trajectory provides structural grounding. The context window holds only new content — everything previously observed exists as hash references on the trajectory.

### Pre-diff is emergent

The pre-diff is emergent from the LLM's attention. The trajectory is shown with hashes embedded. Whichever hashes the LLM references in its output ARE the pre-diff. The act of selecting which hashes to mention IS the perception.

## 3. Commits and Reverts

### Commits are deterministic

Every mutation automatically produces a git commit. This is a kernel operation, not an LLM decision. The SHA becomes the step's commit field.

### Reverts as mistake recovery

When the system detects a mistake (confidence drop, error), it reverts to a prior commit. A revert is itself a mutation — it produces its own commit. The trajectory shows: "committed, detected mistake, reverted." The revert count within a chain is a signal the system reasons about.

## 4. Reasoning Chains as Higher-Order Steps

A chain is a sequence of steps originating from one gap. The first step is the root, everything that follows is the chain. Chains that branch (origin gap → child steps → deeper children) are reasoning steps — stored as units with their own hash.

A gap that resolves in one step is just an atom — not a chain. Chains form only when resolution requires multiple steps before the next origin gap can be addressed.

```
[chain_abc] "config investigation" (4 steps, origin: gap_A)
  gap_A → step_1 → step_2 → step_3 → resolved

[atom_def] "main.py check" (1 step, origin: gap_B)
  gap_B → step_4 → resolved
```

Render shows chains as units. The trajectory stores both the chain hash and the individual step hashes within it. Chain hashes compress arbitrarily complex history into one addressable reference.

Three abstraction levels (all steps):
```
Level 0: atomic step       — one observation, references content hashes
Level 1: reasoning chain   — traces causal path across atomic steps
Level 2: higher reasoning  — traces patterns across chains
```

## 5. Navigation, Not Search

The LLM navigates the trajectory — it follows hashes through a transition state space. Each hash is a waypoint. Each step is a path between waypoints.

From any position:
- **Read the trajectory**: the path taken to get here
- **Follow roots downward**: where did this come from? (convergent)
- **Follow branches forward**: what did this lead to? (divergent)
- **Jump to co-occurring hashes**: what else connects to this entity?

The step sits at the junction: many → one (convergence at perception) and one → many (divergence at action).

## 6. One LLM, One Governor

One persistent 5.4 session per turn. The governor is the only external control — deterministic, operating on epistemic vectors.

The LLM's output is "reasoned intent" — always grounded in referred content (specific entities, values, commits), never in system state (gaps, confidence, convergence).

## 7. The Governor: Deterministic Linear Algebra

The governor monitors convergence via linear algebra on epistemic vectors. It is a deterministic mirror of the LLM — computing attention over numbers the same way a transformer computes attention over embeddings.

### Gap-width computation

The governor measures the distance between pre-articulation scores and action mapping scores per gap. The widest gap is the most urgent.

### Governor signals

| Signal | Trigger |
|--------|---------|
| Allow | gap is converging, continue |
| Constrain | chain depth exceeded |
| Redirect | stagnation — no movement in N steps |
| Revert | divergence — confidence dropped after action |
| Halt | all gaps resolved or pathological |

### Confidence convergence

The system's universal goal: address all gaps with sufficient confidence.

```
goal = all gaps above confidence threshold
```

The governor measures distance to this goal. The LLM navigates toward it. The governor decides when to allow, constrain, or halt.

## 8. Predefined Step Hashes (.st files)

Domain knowledge encoded as hash-addressable step scripts. A predefined hash resolves to a sequence of atomic steps the system must follow. `.st` files are JSON, loaded at startup, hashed, and registered.

```
skills/research.st     → decompose → search → verify → extract → store
skills/hash_edit.st    → resolve target (O) → compose edit (flexible) → execute edit (M)
skills/admin.st        → load identity → load principles → load recent chains → load commitments
```

Each atomic step is configurable via `post_diff` (see §18). Workflows are scripts where most steps are deterministic. Flexible tasks have post_diff: true on key steps.

Predefined steps are composable, reusable, and self-improving. Discovery hardens into knowledge: atomic steps unfold → pattern recurs → crystallize as .st file → LLM references instead of rediscovering.

## 9. Ledger as Stack

The ledger is the ordered unresolved frontier — a recursively rewritten ordered agenda. Not history. Not a log. The active execution surface.

**Three-part gap lifecycle:**
- **Emission**: a step produces candidate gaps
- **Admission**: gaps scored by 0.8 * relevance + 0.2 * grounded, where relevance is LLM-assessed and grounded is computed deterministically by the kernel from hash co-occurrence frequency on the trajectory. Only gaps above ADMISSION_THRESHOLD (0.4) enter the ledger.
- **Placement**: admitted gaps insert at lawful position (depth-first, not append)

The ledger is a stack. Origin gaps enter first. Child gaps push on top. The compiler pops from the top — deepest child first. LIFO. Depth-first per origin gap.

One chain at a time — follow gap_A all the way down before touching gap_B. The compiler's job: pop top of stack, route by vocab.

## 10. OMO Rhythm

Observe-Mutate-Observe is the transition grammar. Every chain self-organises as OMOMOMO. Enforced by vocab mapping + automatic postconditions:

- **O**: vocab routes to hash resolution (hash_resolve_needed, pattern_needed)
- **M**: vocab routes to execution (hash_edit_needed, script_edit_needed, content_needed) → auto-commit
- **O**: universal postcondition auto-fires → hash_resolve_needed targeting commit SHA → verify result

O M O is the atomic unit. The compiler enforces it — no mutation without preceding observation, no mutation without following observation. The sequence isn't planned — it emerges from the structure.

## 11. Dormant Gaps

Every gap articulation gets hashed and stored on the trajectory, whether acted on or not. Gaps below threshold are dormant blobs — the system's peripheral vision.

Dormant gaps are addressable by hash, trackable across turns, and promotable if recurring. The trajectory captures everything the LLM noticed, not just what it did.

## 12. Recursive Convergence

Chain hashes compress arbitrarily complex history into one reference. A 500-step project is one hash. Unfoldable downward to any depth. Buildable upward to any abstraction.

Forward: resolve(hash) → what is it. Backward: trace(hash) → how did it get here. Every blob has a birth story. The graph is bidirectional, complete, and self-verifying.

## 13. Closed Hash Graph

The trajectory is a closed system. Raw data never touches it. External data enters only through the kernel's hash-and-step pipeline. Hallucinated hashes don't resolve. The reasoning graph cannot be contaminated.

## 14. Vocab as Deterministic Bridge

The LLM maps gaps to vocab. The kernel maps vocab to tools or `.st` files.

- **LLM controls**: WHAT needs doing (vocab selection + score)
- **Kernel controls**: HOW it gets done (tool/.st routing + execution)

Three vocab sets:
- **OBSERVE_VOCAB** (5 terms): pattern_needed, hash_resolve_needed, email_needed, external_context, clarify_needed
- **MUTATE_VOCAB** (7 terms): hash_edit_needed, content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed
- **BRIDGE_VOCAB** (1 term): {reprogramme_needed} — the single bridge primitive. No dynamic registration. Entity .st files resolve through hash_resolve_needed automatically (resolve_hash checks skill registry first).

Priority ordering via `vocab_priority()`: observe (20) → mutate (40) → reprogramme (99). The ledger sorts origin gaps by priority so observations run first and reprogramme runs last.

Some vocab maps to a single tool. Some maps to a `.st` file that expands into child gaps on the ledger. The compiler doesn't distinguish — it pops the stack and routes.

## 15. No Micro Loop

The chain IS the micro loop. Chains naturally follow depth-first resolution with OMO rhythm — as deep as needed. The chain length self-adjusts to model intelligence. Same compiler, same stack — different depths. The architecture provides structure. The model provides intelligence.

## 16. post_diff as Universal Configuration

The `post_diff` flag exists on every gap that enters the ledger. It controls whether the LLM reasons after execution:

- **true** → execute → LLM reasons → gaps may surface → chain may branch
- **false** → execute → move on → no reasoning, no branching

A single turn can mix strict pipeline steps and open exploration on the same ledger. This is the strictness dial: from pure deterministic workflow (all false) to fully autonomous exploration (all true), with any mix in between.

## 17. .st as Manifestation

A `.st` file doesn't just steer the LLM — it manifests a specialized agent from the base model. When resolved, it brings into existence a particular mode of thinking — complete with context, constraints, persona, and capabilities.

Same model. Different manifestations. Each `.st` file is a blueprint. When the chain closes, the manifestation dissolves. Manifestations can nest.

`.st` files can carry an `inject` field for scoped prompt control — the kernel modifies the LLM's context for the chain's duration. Structural, scoped, deterministic.

`.st` files allow stepless definitions (pure entities) — a .st with identity/preferences/constraints but no workflow steps. The fields present determine what the entity IS: people have identity + preferences, compliance domains have constraints + sources + scope, databases have schema + access_rules. The builder (`st_builder.py`) forwards all non-base fields as manifestation config.

The step primitive doesn't just track what the system does. It manifests what the system becomes.

## 18. Identity as .st

Users, contacts, and agents are `.st` files. `admin.st` fires on every message from the matching contact, injecting identity, preferences, principles, and recent context — all as deterministic hash-resolved steps.

The user's hash appears on every step they trigger. Identity evolves — the agent updates the `.st` file, git commits, hash changes, future interactions use the latest version.

The identity .st fires AFTER the first step, not before — so user preferences land mid-context where they're most useful. The identity hash is an entity the agent reasons about, not instructions it follows. The agent uses it as a mental model of who the user is — their context, role, thinking style, and history.

`reprogramme_needed` operates in two modes: classifiable mid-turn (the LLM can emit it as a gap) and automatic pre-synthesis (the `_reprogramme_pass()` runs between iteration loop and synthesis as silent housekeeping). Either way, new knowledge is persisted via st_builder, committed, and the commit hash lands on the trajectory.

## 19. HEAD as Workspace State

Every turn: `git rev-parse HEAD` is injected as hash data — the commit tree showing top-level files as blob hashes and directories as tree hashes. Deeper content resolved on demand.

```
[commit_abc123] HEAD
  [tree_aaa] skills/
  [tree_bbb] tools/
  [blob_f1a] config.json
```

No pre-commit ceremony. HEAD always exists. Commits only on mutation.

## 20. No Modules

Pure Python + JSON + .st + git:

```
cors/
  step.py      ← step primitive, gap, chain, trajectory
  compile.py   ← compiler: ledger stack, admission, OMO, chain lifecycle, vocab_priority
  loop.py      ← turn loop: persistent LLM, pre/post, reprogramme pass, synthesis
  skills/      ← .st files (admin, hash_edit, research, entities) + loader
  tools/       ← tool scripts: hash_manifest (universal I/O), st_builder, file_grep, etc.
  .git/        ← content storage
```
