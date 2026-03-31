# Principles — cors v5

## Constraint Orchestration Reasoning System

> The gap is the step primitive. Everything is built on what's missing.

This document is the architectural source of truth for cors — a hash-native reasoning agent built on one recursive primitive. Every mechanism described here is `step()` operating at a different scale. Every function referenced is grounded in source code. Every principle is inviolable.

The system does not plan, search, or optimize. It perceives gaps, admits them onto a stack, and closes them depth-first. Intelligence emerges from the interaction between a probabilistic attention mechanism (the LLM) and a deterministic structural engine (the kernel). The LLM produces meaning. The kernel produces structure. Neither controls the other. Both are necessary.

---

## §1. The Step Primitive

A step is meaningful movement. Not a snapshot, not a state, but the transition between states. It is the only primitive. Every behaviour in the system — observation, mutation, reasoning, identity, memory, agency — is expressible as a step. Every mechanism in this document is step operating at a different scale, the way a fractal repeats its shape at every zoom level.

The metaphor is **closing the loop**, **filling the hole**. Not "closing the lid" or "patching the error." The system doesn't suppress gaps or work around them — it facilitates and adapts to every gap no matter the shape or size. A gap is not a problem to fix. It is the driver of all movement. Without gaps, the system is inert. With gaps, it reasons.

### Two-phase transition

Every step is a pair: perception and scoring. The pair IS the step. Neither phase exists alone.

**Phase 1 — Pre-diff (perception):** The LLM follows step hashes through the trajectory, articulates causal chains, and references content hashes (blobs, trees, commits, .st entities). Each articulation IS a gap — grounded in referred context, encoding an ideal state that vocab can map onto. The pre-diff is emergent from the LLM's attention. The trajectory is shown with hashes embedded. Whichever hashes the LLM references in its output ARE the pre-diff. The act of selecting which hashes to mention IS the perception.

**Phase 2 — Post-diff (gap scoring):** The LLM scores each gap against system vocab. The compiler admits gaps above threshold onto the ledger. The kernel resolves hash data. The OMO rhythm enforces observe-mutate-observe.

```
input/event arrives
  → LLM perceives within trajectory (pre-diff: articulated gaps with hash refs)
  → LLM scores gaps against vocab (post-diff: vocab mapping + scores)
  → compiler admits, places, and sequences gaps on the ledger
  → kernel resolves hashes, executes tools, commits mutations
  → the pair (pre, post) IS the step
```

### Two hash layers (never mixed)

The trajectory operates on two distinct hash layers, the way DNA has coding sequences (genes) and regulatory sequences (promoters, enhancers) — both are nucleotides, but they serve fundamentally different roles and never substitute for each other.

- **Step hashes** (Layer 1): the reasoning trajectory. Steps reference steps. This is the causal graph — WHY things happened. Every step_ref is a waypoint on the reasoning path.
- **Content hashes** (Layer 2): blobs, trees, commits, .st entity files. Gaps reference content. This is the evidence graph — WHAT the system observed or acted on. Every content_ref is data the kernel can resolve.

The trajectory is a closed hash graph. Raw data never touches it. Only hash references and semantic descriptions. Hallucinated hashes don't resolve. The reasoning graph cannot be contaminated. This is the same integrity guarantee git provides for source code — but applied to reasoning itself.

### The single persistent session

One persistent LLM session per turn. The same model does perception, gap scoring, and command composition — all in one continuous stream. No separate mini-models for classification. No hand-off between specialists. Coherence comes from the persistent context window. The trajectory provides structural grounding. The context window holds only new content — everything previously observed exists as hash references on the trajectory, resolvable on demand.

The trajectory is rendered as a traversable hash tree (same shape as git commit trees) via `render_recent()`. Known skill hashes render with named prefixes — `kenny:72b1d5ffc964`, `research:a72c3c4dec0c`. When a skill evolves, the hash changes but the name stays. Steps referencing the old hash trace to what was. Steps referencing the new hash trace to what is.

### Code mechanisms

```
step.py
├─ Gap
│   ├─ .create(desc, content_refs, step_refs, origin)
│   │   └─ blob_hash(f"{desc}:{refs}:{srefs}") → 12-char SHA-256
│   ├─ .hash           — content-addressed identity
│   ├─ .desc           — semantic articulation of what's missing
│   ├─ .content_refs   — Layer 2: data hashes (blobs/trees/commits/.st)
│   ├─ .step_refs      — Layer 1: reasoning chain followed
│   ├─ .scores         → Epistemic(relevance, confidence, grounded)
│   ├─ .vocab          — mapped precondition (determines manifestation)
│   ├─ .dormant        — below threshold, stored but not acted on
│   └─ .turn_id        — which turn created this gap (for cross-turn threshold)
│
├─ Step
│   ├─ .create(desc, step_refs, content_refs, gaps, commit, chain_id, parent)
│   │   └─ blob_hash(f"{desc}:{t}:{srefs}:{crefs}") → 12-char SHA-256
│   ├─ .hash           — content-addressed identity
│   ├─ .step_refs      — Layer 1: step hashes followed (pre-diff perception)
│   ├─ .content_refs   — Layer 2: blobs/trees/commits referenced
│   ├─ .desc           — semantic articulation of the transition
│   ├─ .gaps           — post-diff: one per causal chain, with vocab + scores
│   ├─ .commit         — git SHA if mutation occurred (None if observation)
│   ├─ .t              — timestamp (set at creation via time.time())
│   ├─ .is_mutation()  → commit is not None
│   ├─ .is_observation() → commit is None
│   ├─ .active_gaps()  → [g for g in gaps if not resolved and not dormant]
│   └─ .all_refs()     → step_refs + content_refs + all gap refs
│
├─ Epistemic
│   ├─ .relevance      — LLM-scored: advances the goal?
│   ├─ .confidence     — LLM-scored: safe to act?
│   ├─ .grounded       — kernel-computed: hash co-occurrence frequency
│   ├─ .as_vector()    → [relevance, confidence, grounded]
│   ├─ .distance_to(other) → Euclidean distance
│   └─ .magnitude()    → vector magnitude
│
├─ blob_hash(content)  → hashlib.sha256[:12] — the universal hashing primitive
└─ chain_hash(step_hashes) → SHA-256 of joined step hashes
```

---

## §2. Gap Emission and Manifestation

A step encodes a gap naturally and manifests it as a hash. The LLM perceives the trajectory, articulates what's missing or misaligned, and each articulation IS a gap — hashed, stored, addressable. This is not extraction or classification. It is emission. The gap emerges from the LLM's attention the way a photon emerges from an excited electron — the energy was always there, the emission makes it observable.

A single step can emit many gaps. But only gaps that meet the admission threshold manifest into longer chains of reasoning. Below threshold, gaps become dormant — peripheral vision, stored on the trajectory, promotable if they recur, but never acted on. This is the system's way of noticing without committing. The LLM can attend to everything. Only what's relevant and grounded becomes structure.

### The lifecycle

```
step emits N gaps
  → gaps scored (relevance × LLM, grounded × kernel)
  → above threshold → manifest as chain origins → depth-first resolution
  → below threshold → dormant blobs → stored but silent
  → far below → not even stored
```

The loop facilitates this: the LLM generates steps, each step emits gaps, the compiler admits or rejects, and only manifested gaps drive further reasoning. The system self-prunes. The dormant gaps are not waste — they are the system's peripheral awareness. A dormant gap that recurs across three turns may indicate something the system keeps noticing but hasn't addressed. The `recurring_dormant()` function detects these patterns.

### Passive chain building

Passive chains accumulate steps across turns without fresh emission — steps that touch the same entity append to existing active chains. Reasoning commitments grow this way. The chain doesn't need to resolve in one turn. It builds as evidence arrives.

```
Turn 1: gap surfaces about London councils → chain starts
Turn 3: user mentions something relevant → step appends to the chain
Turn 7: enough evidence accumulated → chain resolves or promotes
```

This is the system's long-term memory mechanism. Not a separate store. Not a database query. The trajectory IS the memory. Chains that persist across turns are the system's ongoing concerns — and they persist structurally, not by configuration.

### Code mechanisms

```
compile.py
├─ Compiler
│   ├─ .emit(step)
│   │   ├─ for each gap in step.gaps:
│   │   │   ├─ _admission_score(gap) → 0.8 * relevance + 0.2 * grounded
│   │   │   ├─ _compute_grounded(gap) → co_occurrence(ref) / (len(refs) * 3), cap 1.0
│   │   │   ├─ score < DORMANT_THRESHOLD (0.2) → gap.dormant = True
│   │   │   ├─ score < _admission_threshold(gap) → gap.dormant = True
│   │   │   ├─ active_chain exists → Ledger.push_child (depth-first)
│   │   │   └─ no active chain → Chain.create + Ledger.push_origin
│   │   └─ grounded is OVERWRITTEN: gap.scores.grounded = kernel computation
│   │
│   ├─ .emit_origin_gaps(step)
│   │   ├─ each origin gap → Chain.create + Ledger.push_origin
│   │   └─ Ledger.sort_by_priority() → observe (20) first, reprogramme (99) last
│   │
│   └─ .readmit_cross_turn(gaps, step_hash)
│       ├─ re-scores against CROSS_TURN_THRESHOLD (0.6)
│       ├─ re-computes grounded from current trajectory
│       └─ preserves original metadata (chain_id, depth, priority)
│
step.py
├─ Trajectory
│   ├─ .append(step) → indexes all gaps in gap_index (active + dormant)
│   ├─ .co_occurrence(hash) → count of steps referencing this hash
│   ├─ .dormant_gaps() → all dormant gaps across trajectory
│   ├─ .recurring_dormant(min_count=3) → dormant descs appearing 3+ times
│   ├─ .find_passive_chains(content_ref) → active chains whose origin gap refs overlap
│   └─ .append_to_passive_chain(chain_hash, step) → append step to existing chain
│
loop.py
├─ _parse_step_output() → extracts gaps from LLM JSON, sets turn_id, grounded=0.0
└─ _find_dangling_gaps(trajectory) → unresolved gaps from prior turns
```

---

## §3. Vocab Determines Manifestation

How a gap manifests — what the system DOES with it — is entirely determined by the vocab tagged onto it. The gap is the universal primitive. The vocab is the configuration that shapes its execution. This is the separation between WHAT (the gap) and HOW (the vocab). The LLM decides what needs doing. The kernel decides how it gets done.

Think of vocab as the gap's type signature. Just as a type system routes values through different execution paths without changing the values themselves, vocab routes gaps through different resolution paths without changing the gaps themselves. The gap remains immutable. The vocab determines its fate.

### Tier 1: Observe (external &, priority 20)

The kernel resolves data. The LLM receives it. No mutation. These are the system's sensory organs — they bring information into the context window without changing the world.

| Vocab | Manifestation | Post-diff |
|-------|--------------|-----------|
| `hash_resolve_needed` | Kernel resolves hash → step/gap/skill/.st/git blob. If hash is a .st entity, full entity data injected. | Deterministic — blob step, no branching |
| `pattern_needed` | Kernel runs file_grep → results injected | LLM reasons over results, may branch |
| `email_needed` | Kernel checks email → results injected | LLM reasons over results, may branch |
| `external_context` | LLM surfaces from current context — no tool | Blob step, no branching |
| `clarify_needed` | Halts iteration. Gap desc becomes the question. Persists on trajectory for resume next turn. | No post-diff — the turn ends |

### Tier 2: Mutate (external &mut, priority 40)

The LLM composes. The kernel executes. Auto-commit. Postcondition fires. These are the system's effectors — they change the world and immediately verify the change.

| Vocab | Manifestation | Compose mode | Post-observe |
|-------|--------------|-------------|--------------|
| `hash_edit_needed` | hash_manifest.py — read/write/patch/diff by path. Routes by file type (.st→st_builder, .json→json_patch, .docx→doc_edit) | LLM composes JSON params | Per tree_policy.json |
| `stitch_needed` | stitch_generate.py — prompt → HTML + Tailwind CSS | LLM composes UI prompt | `ui_output/` (screenshot blob) |
| `content_needed` | file_write.py — write new file | LLM composes content | Commit tree |
| `script_edit_needed` | file_edit.py — edit existing file | LLM composes shell command | Commit tree |
| `command_needed` | code_exec.py — execute shell command. Output blob-hashed into git. | LLM composes command | `logs/` (output blob) |
| `message_needed` | email_send.py — send email/message | LLM composes message | Commit tree |
| `json_patch_needed` | json_patch.py — surgical JSON mutation | LLM composes patch | Commit tree |
| `git_revert_needed` | git_ops.py — revert/checkout | LLM composes git command | Commit tree |

All mutations follow the same rhythm: **compose → execute → auto-commit → postcondition** (hash_resolve_needed targeting post_observe path). No exceptions. The postcondition is the system verifying its own mutation — the same way a cell checks its DNA after replication.

### Tier 3: Bridge codons (internal &mut, priority 99)

Three codons govern the reasoning lifecycle. The biological analogy is precise: a codon is a three-nucleotide sequence that signals a specific instruction to the cellular machinery. These three vocab terms signal specific instructions to the kernel machinery.

| Vocab | Codon | Manifestation |
|-------|-------|--------------|
| `reason_needed` | **START** | Observation bridge + agency. Renders reasoning trees. Three outcomes: observe (clarity), refine (update chain), manifest (activate commitment agent with injected commit_needed as last step). |
| `commit_needed` | **END** | Reintegration. Renders full commitment tree into main context. Closes or continues chain. NOT directly classifiable — injected by reason.st at lowest relevance behind commitment gaps. |
| `reprogramme_needed` | **PERSIST** | World-building. st_builder composes .st from semantic intent. Injected with PRINCIPLES.md + entity registry. Also fires as pre-synthesis pass (safety net). |

Mid-turn commitment activation follows the compiler laws exactly: reason_needed fires → commitment gaps disperse onto ledger → commit_needed sits at bottom → commitment resolves depth-first → commit reintegrates → main chain resumes. The compiler doesn't know it's processing a commitment. It just sees gaps at various depths. Same laws, same stack.

### Tier 4: .st Resolution (internal &, no vocab)

Entity .st files have no dedicated vocab. They resolve through `hash_resolve_needed` when the LLM references their hash in content_refs. The kernel checks the skill registry — if the hash is a .st file, it renders entity data. This is elegant because it means entity resolution uses the exact same mechanism as any other hash resolution. No special routing. No entity-specific vocabulary. The .st file IS the entity. The hash IS the address. The vocab IS hash_resolve_needed. One mechanism, universal.

Two sub-modes determined by .st content:

| .st has steps? | Mode | What happens |
|---------------|------|-------------|
| No (pure entity) | Context injection | Data injected into LLM context. One blob step. No branching. |
| Yes (workflow) | Gap ledger mutation | Each step becomes a gap on the ledger. Chain plays out depth-first. |

### Auto-routes (policy-driven)

Mutations targeting protected paths are intercepted before execution — the tree policy acts as a membrane around sensitive regions of the codebase:

| Target matches | Reroutes to | Mechanism |
|---------------|-------------|-----------|
| `skills/*.st` or skill hash | `reprogramme_needed` | .st files have schema — must go through st_builder |
| `ui_output/` or screenshots | `stitch_needed` | Generated assets regenerated, not manually edited |
| Immutable paths (system code, stores, logs) | Auto-revert + warning | Protected path violation |

All driven by `tree_policy.json` — configurable, no hardcoded paths.

### Universal postcondition

Every `auto_commit()` injects a `hash_resolve_needed` gap targeting the commit. What gets resolved depends on `post_observe` in the TOOL_MAP config — either the commit tree (default) or a specific directory. This is the system verifying its own work. Every mutation produces an observation. No blind mutations.

### Code mechanisms

```
compile.py
├─ OBSERVE_VOCAB = {pattern_needed, hash_resolve_needed, email_needed, external_context, clarify_needed}
├─ MUTATE_VOCAB  = {hash_edit_needed, stitch_needed, content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed}
├─ BRIDGE_VOCAB  = {reason_needed, commit_needed, reprogramme_needed}
├─ is_observe(vocab) → vocab in OBSERVE_VOCAB
├─ is_mutate(vocab)  → vocab in MUTATE_VOCAB
├─ is_bridge(vocab)  → vocab in BRIDGE_VOCAB
└─ vocab_priority(vocab)
    ├─ observe → 20 (fires first)
    ├─ mutate  → 40
    ├─ bridge/reprogramme → 99 (fires last)
    └─ unknown → 50

loop.py
├─ TOOL_MAP
│   ├─ vocab → {tool: path, post_observe: target}
│   ├─ hash_resolve_needed → {tool: None} (kernel resolves directly)
│   ├─ pattern_needed → {tool: "tools/file_grep.py"}
│   ├─ hash_edit_needed → {tool: "tools/hash_manifest.py"}
│   ├─ stitch_needed → {tool: "tools/stitch_generate.py", post_observe: "ui_output/"}
│   └─ ... (full map in loop.py TOOL_MAP constant)
│
├─ DETERMINISTIC_VOCAB = {hash_resolve_needed} — kernel resolves, zero LLM cost
├─ OBSERVATION_ONLY_VOCAB = {hash_resolve_needed, external_context} — blob steps
│
├─ Iteration loop branches
│   ├─ if vocab in DETERMINISTIC_VOCAB → kernel resolves directly
│   ├─ if vocab in OBSERVATION_ONLY_VOCAB → resolve + inject, no post-diff
│   ├─ if is_observe(vocab) → tool executes, LLM reasons over results
│   ├─ if is_mutate(vocab) → compose → execute → auto_commit → postcondition
│   ├─ if vocab == "reprogramme_needed" → PRINCIPLES.md + registry injected → compose
│   └─ if vocab == "clarify_needed" → halt iteration, gap persists
│
├─ Policy auto-route
│   ├─ _load_tree_policy() → loads tree_policy.json
│   ├─ _match_policy(path, policy) → exact match, then longest prefix
│   └─ on_mutate → reroutes vocab before execution
│
├─ auto_commit(message) → git add -A → commit → _check_protected → revert on violation
│   └─ _check_protected(commit, pre_commit) → scans diff for immutable violations
│
├─ Universal postcondition
│   └─ after auto_commit: Gap.create(hash_resolve_needed, content_refs=[commit_sha])
│
└─ resolve_hash(ref, trajectory)
    ├─ 1. skill registry → .st entity data (_render_entity)
    ├─ 2. trajectory step → semantic tree branch (_render_step_tree)
    ├─ 3. trajectory gap → gap data with scores (_render_gap_tree)
    └─ 4. git object → git show (blob/tree/commit)

tree_policy.json
├─ "skills/"     → {on_mutate: "reprogramme_needed"}
├─ "ui_output/"  → {on_mutate: "stitch_needed"}
├─ "logs/"       → {immutable: true}
├─ "step.py"     → {immutable: true}
├─ "compile.py"  → {immutable: true}
└─ "loop.py"     → {immutable: true}

tools/
├─ hash_manifest.py   — universal file I/O: read/write/patch/diff + file-type routing
├─ st_builder.py      — .st constructor: validates schema, forwards manifestation fields
├─ stitch_generate.py — Google Stitch SDK: prompt → HTML + Tailwind CSS
├─ file_grep.py       — pattern search across workspace
├─ file_write.py      — write new file
├─ file_edit.py       — edit existing file
├─ code_exec.py       — execute shell command, output blob-hashed into git
├─ email_send.py      — send email/message
├─ json_patch.py      — surgical JSON mutation
└─ git_ops.py         — git revert/checkout
```

---

## §4. The Formal Gap Configuration

Parsing the symmetry across all tiers, a gap is fully defined by seven axes. This is not arbitrary — it is the minimum configuration that captures everything the system needs to route, sequence, verify, and resolve a gap. Remove any axis and the system loses a degree of freedom. Add any axis and it introduces redundancy.

```
Gap {
  desc:         str          — semantic articulation of what's missing/misaligned
  content_refs: [hash]       — Layer 2: data hashes that ground this gap
  step_refs:    [hash]       — Layer 1: reasoning steps that led to this gap
  vocab:        str | null   — determines HOW the gap manifests (tier + tool routing)
  relevance:    0.0-1.0      — LLM-assessed: how much does resolving this advance the goal?
  confidence:   0.0-1.0      — LLM-assessed: how safe is it to act on this?
  grounded:     0.0-1.0      — kernel-computed: hash co-occurrence frequency on trajectory
}
```

The seven axes form a complete coordinate system for gap routing. Three axes are set by the LLM (desc, relevance, confidence) — the probabilistic vector. Two axes are set by the LLM as hash selections (step_refs, content_refs). One axis is set by the LLM as classification (vocab). One axis is computed deterministically by the kernel (grounded) — the structural vector. The gap's size is measured as the distance between these two vectors: the LLM's probabilistic assessment versus the trajectory's deterministic evidence.

### Configuration axes

| Axis | Controls | Set by |
|------|----------|--------|
| **vocab** | What tier, what tool, what .st, what auto-route | LLM (maps gap to closest term) |
| **relevance** | Admission + ordering within priority bracket | LLM (0.0-1.0) |
| **confidence** | Governor routing (ACT vs ALLOW) | LLM (0.0-1.0) |
| **grounded** | Admission (weighted 0.2) | Kernel (hash co-occurrence) |
| **content_refs** | What data to resolve, which .st to inject, what to observe | LLM (hash selection) |
| **step_refs** | Causal chain — why this gap exists | LLM (hash selection) |
| **desc** | The gap itself — what's missing or misaligned | LLM (natural language) |

### Admission thresholds (deterministic)

The admission formula is always: `score = 0.8 * relevance + 0.2 * grounded`

Relevance dominates. Extremely relevant gaps can enter even with zero co-occurrence. But low-relevance gaps need strong grounding to survive. This is by design: the system trusts the LLM's sense of what matters, but verifies it against structural evidence. The weights (0.8/0.2) were calibrated empirically — earlier formulas (0.6/0.4) caused spiral loops where the LLM chased its own co-occurrence patterns.

The threshold varies by gap origin — gaps must justify themselves proportionally to how far they've travelled:

| Gap origin | Threshold | Rationale |
|------------|-----------|-----------|
| **Fresh** (current turn) | `score >= 0.4` | Standard — immediate context, LLM is reasoning live |
| **Cross-turn** (dangling from prior turn) | `score >= 0.6` | Higher bar — must justify carrying forward |
| **Dormant promotion** (was below threshold, now recurring) | `score >= 0.7` | Highest bar — was rejected, needs strong evidence |

These thresholds are deterministic. The kernel applies them based on gap origin — no LLM judgment in the gating. The LLM controls relevance (what it thinks matters). The kernel controls admission (what actually enters the ledger).

### Cross-turn gap re-admission

When dangling gaps from prior turns are re-admitted:

1. LLM re-ranks relevance based on new context (new message, new trajectory state)
2. Kernel re-computes grounded from current co-occurrence (trajectory may have grown)
3. Score must meet the cross-turn threshold (0.6)
4. If admitted, original metadata preserved: chain_id, depth, priority
5. Compiler inserts at lawful position — cross-turn gaps maintain original ordering
6. Fresh gaps from current turn interleave at their own priority level

Non-selection by the LLM (not referenced in pre-diff) = gap is not re-scored = not re-admitted = effectively dropped. No explicit deletion. **Silence IS the drop.**

### The invariant

A gap is ALWAYS:

- **Hashable** — content-addressed from desc + refs
- **Immutable** — once created, never modified (scores set at emission)
- **Traceable** — step_refs trace WHY, content_refs trace WHAT
- **Classifiable** — vocab maps it to a tier
- **Scoreable** — relevance + confidence (LLM) + grounded (kernel)
- **Admissible or dormant** — threshold determines if it enters the ledger
- **Resolvable** — by tool, by .st, by LLM reasoning, or by user clarification

Every gap follows this shape. No exceptions. The vocab configures the manifestation, but the gap primitive is universal.

### Code mechanisms

```
step.py
├─ Gap
│   ├─ .create(desc, content_refs, step_refs, origin)
│   │   └─ blob_hash(f"{desc}:{':'.join(refs)}:{':'.join(srefs)}") → immutable hash
│   ├─ .scores → Epistemic
│   │   ├─ .relevance   [LLM-scored, 0.0-1.0]
│   │   ├─ .confidence   [LLM-scored, 0.0-1.0]
│   │   └─ .grounded     [kernel-computed, overwritten at admission]
│   ├─ .turn_id → set at emission, compared against current_turn for threshold selection
│   └─ .dormant → True if below threshold, stored on trajectory but not acted on
│
compile.py
├─ _admission_score(gap) → 0.8 * relevance + 0.2 * grounded
├─ _compute_grounded(gap) → sum(co_occurrence(ref)) / (len(refs) * 3), cap 1.0
│   └─ gap.scores.grounded = computed value (OVERWRITES LLM self-assessment)
├─ _admission_threshold(gap)
│   ├─ gap.dormant → DORMANT_PROMOTE_THRESHOLD = 0.7
│   ├─ gap.turn_id < current_turn → CROSS_TURN_THRESHOLD = 0.6
│   └─ else → ADMISSION_THRESHOLD = 0.4
├─ DORMANT_THRESHOLD = 0.2 — below this, gap stored as dormant
├─ CONFIDENCE_THRESHOLD = 0.8 — gap resolved when confidence exceeds
├─ vocab_priority() → observe=20 < mutate=40 < bridge=99
├─ LedgerEntry.priority → set at push time from vocab_priority(gap.vocab)
├─ Ledger.sort_by_priority() → origins sorted (children stay on top for depth-first)
└─ Compiler.readmit_cross_turn(gaps, step_hash) → re-scores, preserves order

loop.py
├─ _turn_counter → increments each turn, passed to Compiler(current_turn)
├─ _parse_step_output() → sets gap.turn_id = _turn_counter, gap.scores.grounded = 0.0
└─ _find_dangling_gaps(trajectory) → unresolved gaps from prior turns for resume
```

---

## §5. Reprogramme: The Higher-Order Gap Rendering Engine

Reprogramme is the engine that creates and calibrates the .st ecosystem. While every other mechanism operates WITHIN the ecosystem, reprogramme BUILDS the ecosystem. It is the generalization engine — calibrating the system to its environment by rendering the gaps that no existing entity or workflow can fill.

The analogy is genetic engineering: the cell (kernel) operates on proteins (steps), but the genetic engineer (reprogramme) designs the DNA (.st files) that encodes the proteins. The cell doesn't know or care about the engineer. It just reads the genes and expresses them. But the engineer knows the cell intimately — and designs genes that compose with its machinery.

### On-demand rendering

The LLM explicitly surfaces `reprogramme_needed` — "this entity needs to be created or updated." The reprogramme agent composes a .st file from semantic intent, constrained by PRINCIPLES.md. This is deliberate world-building: the user says "track Clinton" or "build a video pipeline" and the system manifests a new entity.

### Natural rendering through semantic vocab triggering

Observe bridges (`hash_resolve_needed`) keep .st entities alive on the trajectory so long as they are salient. When the LLM references a .st hash in a gap's content_refs, the kernel resolves it automatically — the entity resurfaces if the gap is relevant enough to be admitted. No explicit "load entity" needed. The trajectory IS the memory. Relevance IS the recall trigger.

This means the .st ecosystem is self-sustaining:
- Entities referenced frequently → high co-occurrence → high grounded score → easier to admit
- Entities never referenced → zero co-occurrence → decay to dormancy
- Dormant entities can be revived if they recur — the hash is always resolvable
- The reprogramme agent creates new entities when gaps can't be filled by existing ones

### The rendering cycle

```
LLM perceives trajectory
  → articulates gap referencing .st hash
  → kernel resolves hash → entity data injected (context) or gaps dispersed (workflow)
  → LLM reasons with entity context
  → if knowledge is stale or missing → reprogramme_needed surfaces
  → reprogramme agent creates/updates .st
  → commit → hash evolves → trajectory tracks the evolution
  → next turn, the evolved entity is what gets resolved
```

Reprogramme operates in two modes: **classifiable mid-turn** (the LLM emits it as a gap) and **automatic pre-synthesis** (the `_reprogramme_pass()` runs between the iteration loop and synthesis as silent housekeeping). Either way, new knowledge is persisted via st_builder, committed, and the commit hash lands on the trajectory.

### Code mechanisms

```
loop.py
├─ Reprogramme branch (iteration loop)
│   ├─ if vocab == "reprogramme_needed"
│   ├─ reads PRINCIPLES.md → injects into session
│   ├─ injects entity registry (all skills + commands with descriptions)
│   ├─ compose prompt: "reuse existing .st before building new"
│   └─ teaches two modes: context injection vs gap ledger mutation
│
├─ _reprogramme_pass() → automatic pre-synthesis safety net
│   └─ reviews turn for knowledge updates, fires if needed
│
└─ Entity rendering
    ├─ _render_entity(skill) → full .st data formatted for injection
    └─ _render_identity(skill) → identity .st formatted for session

skills/loader.py
├─ SkillRegistry
│   ├─ .by_hash → {hash: Skill}
│   ├─ .by_name → {name: Skill}
│   ├─ .commands → {trigger: Skill} (hidden from LLM registry)
│   ├─ .resolve(ref) → Skill or None
│   ├─ .resolve_name(ref) → display name or None
│   └─ .all_skills() → all loaded skills
│
├─ Skill
│   ├─ .display_name → from identity.name or skill name
│   ├─ .is_command → trigger.startswith("command:")
│   └─ .hash → content hash of .st file
│
└─ load_all(skills_dir) → SkillRegistry (bridge + command separation)

tools/st_builder.py
├─ Builds valid .st from JSON intent
├─ Validates schema (name, desc, trigger, steps)
├─ steps[] can be empty → pure entity, no workflow
└─ Forwards all non-base fields (identity, constraints, sources, scope, etc.)
```

---

## §6. Standardised Definitions and Referred Context

### The gap definition

A gap is a verifiable discrepancy between the current state and its referred context — either as missing information or unmet alignment.

This definition is precise and non-negotiable. A gap is not a suggestion, not a plan, not a to-do item. It is a **measurement**. The LLM measures what is missing or misaligned, grounded in specific hashes. If the LLM cannot cite a hash, the gap is ungrounded — and the kernel's co-occurrence score will reflect that.

Two types (both diagnostic, never prescriptive):

- **Observational** — information is missing, inconsistent, or unverified. The system needs to SEE more.
- **Misalignment** — the current state does not satisfy the referred context. The system needs to ACT.

Articulation form:
```
Reference: [what the referred context requires]
Current: [what the evidence actually shows]
→ Emit as single concise statement
```

### The epistemic triad

Three scores on every gap. Two set by the LLM, one by the kernel. This separation is the system's epistemic hygiene — the LLM assesses meaning, the kernel assesses structure, and neither can overrule the other.

**relevance** (0-1) [LLM]: How much does resolving this advance the trajectory toward the shared goal? 1.0 = critical path. 0.0 = does not advance. Evaluative form: *"If this gap were resolved, would it move the system closer to what the user needs?"* This is the PRIMARY driver of admission. The LLM's sense of what matters carries 80% of the admission weight.

**confidence** (0-1) [LLM]: How safe and trustworthy is this to act on? 1.0 = safe to proceed. 0.0 = unsafe or unverifiable. Evaluative form: *"Do I have enough evidence to act, or am I assuming?"* The governor uses confidence for routing: high confidence + mutation vocab → ACT signal. Low confidence → ALLOW (gather more evidence first).

**grounded** (0-1) [KERNEL]: Hash co-occurrence frequency on the trajectory. Computed deterministically from how often the gap's referenced hashes have appeared before. The LLM **cannot influence this score** — it is a structural measurement. To be well-grounded, reference hashes that exist on the trajectory. A gap referencing hashes seen 3+ times scores ~0.8. A gap referencing hashes never seen scores 0.0. This is the trajectory's deterministic memory — it knows what it has seen, regardless of what the LLM claims.

### Referred context IS hashes

In this system, referred context is not prose or memory — it is hashes. Two layers, never mixed:

- **step_refs** (Layer 1): reasoning steps the LLM followed to reach this gap. These trace the causal chain — WHY this gap exists. Every step_ref is a step hash on the trajectory.
- **content_refs** (Layer 2): data the gap needs resolved. Blobs, trees, commits, .st entity hashes. These trace WHAT the gap needs to see. Every content_ref is a hash the kernel can resolve via git or the skill registry.

Everything referenceable is a hash:
- A person → `kenny:72b1d5ffc964` (their .st file hash)
- A workflow → `research:a72c3c4dec0c` (the .st file hash)
- An idea → a step hash on the trajectory where the idea was articulated
- A file → a git blob hash
- A directory → a git tree hash
- A commit → a git commit hash
- A prior task → the chain hash that compressed that task's steps

All are valid content_refs. All resolvable by the kernel. All traceable on the trajectory. The hash is the universal address. The trajectory is the universal directory.

### The citation rule

**Every gap MUST cite its sources.** This is not optional.

- step_refs: which steps did you follow to arrive at this gap? If you can't point to the reasoning chain, your gap is unfounded.
- content_refs: which hashes ground this gap? If you can't point to the data, your gap is ungrounded.

An unsourced gap has:
- step_refs = [] → no causal chain → the LLM is inventing, not reasoning
- content_refs = [] → no evidence → grounded score = 0.0

The kernel enforces this structurally: `_compute_grounded()` returns 0.0 for gaps with no refs. The admission formula weights grounded at 0.2 — so unsourced gaps need extreme relevance (>0.5) to enter the ledger. This is by design: the system tolerates unsourced gaps when they're genuinely important, but makes them work harder to be admitted.

The only exceptions:
- `clarify_needed` — no refs because the gap IS that information is missing
- `reprogramme_needed` — may have no prior refs when creating a brand new entity
- Entity context injection — content_refs point to the .st hash, no step_refs needed

### Code mechanisms

```
step.py
├─ Gap.create(desc, content_refs, step_refs)
│   └─ blob_hash(f"{desc}:{refs}") — the hash IS the citation
│
├─ Epistemic
│   ├─ .relevance   [LLM-scored] — 80% of admission weight
│   ├─ .confidence   [LLM-scored] — governor routing
│   ├─ .grounded     [kernel-computed] — 20% of admission weight
│   ├─ .as_vector()  → [rel, conf, gr] for governor linear algebra
│   └─ .distance_to(other) → Euclidean distance between states
│
├─ Step.step_refs    — Layer 1: reasoning (WHY)
├─ Step.content_refs — Layer 2: data (WHAT)
│   └─ never mixed: step hashes never appear in content_refs, vice versa
│
├─ Trajectory.co_occurrence(hash) → count of steps referencing this hash
│   └─ the primitive underlying grounded computation
│
└─ Trajectory.render_recent(n, registry)
    └─ _tag_ref(ref, layer, registry) → named refs: kenny:hash, step:hash

compile.py
├─ _compute_grounded(gap) → co_occurrence / (len(refs) * 3), cap 1.0
│   └─ returns 0.0 if no refs (unsourced gap penalty)
├─ _admission_score(gap) → 0.8 * relevance + 0.2 * grounded
│   └─ unsourced gaps need relevance > 0.5 to enter (0.8 * 0.5 = 0.4 = threshold)
└─ gap.scores.grounded = kernel computation (OVERWRITES LLM self-assessment)

loop.py
├─ _parse_step_output() → extracts step_refs + content_refs from LLM JSON
│   └─ grounded hardcoded to 0.0 (kernel computes at admission time)
└─ resolve_hash(ref, trajectory) → resolution order:
    ├─ 1. skill registry → .st entity data
    ├─ 2. trajectory step → semantic tree (follows step_refs recursively)
    ├─ 3. trajectory gap → gap data with scores
    └─ 4. git object → blob/tree/commit content
```

---

## §7. Post-Diff: The Fluidity Dial

The `post_diff` flag exists on every gap that enters the ledger. It is the system's fluidity control — a single boolean that determines whether reasoning continues after execution or whether execution is terminal.

- **post_diff: true** → execute → LLM reasons → gaps may surface → chain may branch
- **post_diff: false** → execute → move on → no reasoning, no branching

This is not a minor configuration detail. It is the mechanism that allows the same ledger, the same compiler, and the same OMO rhythm to express the full spectrum from pure deterministic workflow (all false) to fully autonomous exploration (all true), with any mix in between. A single turn can contain strict pipeline steps and open-ended reasoning on the same ledger. The fluidity is per-step, not per-turn or per-agent.

Think of post_diff as the difference between a reflex and a deliberation. A reflex (post_diff: false) fires and completes — the knee-jerk response, no contemplation. A deliberation (post_diff: true) fires and then reflects — did that work? what do I see now? should I branch? The system can mix reflexes and deliberations in any sequence. A workflow that needs precision uses false. A step that faces ambiguity uses true. The .st author chooses.

### What this means for .st composition

When an .st author designs a workflow, post_diff is the primary tool for controlling chain behaviour:

- **Deterministic pipeline**: all steps post_diff: false → execute in sequence, no branching, predictable step count
- **Guided exploration**: key decision points post_diff: true, execution steps post_diff: false → branches only where needed
- **Full autonomy**: all steps post_diff: true → the chain can branch at any point, step count is emergent

The .st author doesn't control the compiler. They control fluidity. The compiler enforces laws. The governor monitors convergence. But whether the chain CAN branch at a given point — that's the .st author's design decision, expressed as post_diff.

### Code mechanisms

```
skills/*.st
├─ Each step object has "post_diff": true|false
├─ true → after execution, LLM reasons → may emit child gaps → chain branches
└─ false → after execution, move to next gap → deterministic progression

loop.py
├─ Iteration loop
│   ├─ if post_diff is true → inject result → call LLM → parse new step → emit gaps
│   └─ if post_diff is false → inject result → create blob step → no LLM call
│
└─ The LLM never sees post_diff — it is a kernel-side control
    └─ The .st author controls fluidity, not the LLM
```

---

## §8. Compiler Laws and Recursive Fluidity

The compiler has laws. They are absolute. No gap, no .st file, no LLM output can violate them. They are the physics of this system — not guidelines, not best practices, not configurable parameters. They are inviolable constraints that make everything else possible, the way the laws of thermodynamics constrain but enable all of chemistry.

But the recursive nature of .st composition allows workflows to achieve fluidity WITHIN those laws — not by breaking them, but by structuring gaps so the laws work in their favour. This is the key insight: rigidity at the compiler level enables fluidity at the composition level.

### The eight laws

**1. LIFO** — The ledger is a stack. Deepest child pops first. No gap can jump the queue. This ensures depth-first resolution — you finish what you started before moving on.

**2. Depth-first** — One chain at a time. Follow gap_A all the way down before touching gap_B. This prevents the system from context-switching between unrelated chains, which would dilute the LLM's attention.

**3. OMO** — No consecutive mutations without observation between. The compiler rejects mutation after mutation. Every action must be preceded by perception and followed by verification. This is the heartbeat of the system: observe-mutate-observe, observe-mutate-observe.

**4. Admission** — Score must meet threshold. Fresh = 0.4, cross-turn = 0.6, dormant = 0.7. Gaps that don't meet the bar don't enter the ledger. The threshold is tiered by origin — the further a gap has travelled, the more it must justify its continued existence.

**5. Priority ordering** — Observe (20) before mutate (40) before bridge codons (99). Within same priority, higher relevance pops first. This ensures the system gathers information before acting, and acts before persisting.

**6. Force-close** — Chains exceeding MAX_CHAIN_DEPTH (15) are force-closed. No infinite loops. This is the circuit breaker — if a chain can't resolve in 15 steps, it's either pathological or needs to be broken into sub-chains.

**7. Immutability** — Gaps are immutable after creation. Scores set at emission, never modified. This ensures the trajectory is a faithful record of what the LLM actually perceived, not a retroactive revision.

**8. Postcondition** — Every mutation auto-commits and injects hash_resolve_needed. No mutation without verification. This is Law 3 (OMO) enforced structurally — even if the .st author forgets to add an observation step, the postcondition ensures one fires.

### How .st files compose within the laws

A .st file's steps are gaps. When they disperse onto the ledger, they follow every law. But the .st AUTHOR controls:

- **Relevance scores** — sequences execution order within the same priority bracket
- **Vocab selection** — determines which tier each step operates in
- **post_diff** — controls whether the chain can branch after each step

This means an .st file can structure a workflow that LOOKS like it bypasses rules but actually leverages them:

```
research.st:
  step 1: hash_resolve_needed (observe, rel=1.0, post_diff=false)  ← fires first, deterministic
  step 2: null vocab (flex, rel=0.9, post_diff=true)               ← LLM reasons, may branch
  step 3: hash_edit_needed (mutate, rel=0.8, post_diff=true)       ← can branch on failure
  step 4: command_needed (mutate, rel=0.7, post_diff=true)         ← verification
```

The compiler sees: observe gap (priority 20), then unknown gap (50), then two mutate gaps (40). After priority sorting, the observe fires first. The null-vocab gap lets the LLM reason freely. Then mutations fire with automatic postconditions between them (OMO preserved).

### Recursive .st embedding

The real power: a .st step's vocab can trigger ANOTHER .st file. When that happens, the child .st's gaps disperse onto the ledger AS CHILDREN of the current chain. Depth-first means they resolve before the parent resumes.

```
video_pipeline.st:
  step 1: hash_resolve_needed → resolve project context
  step 2: (triggers research.st) → research gaps disperse here, depth-first
  step 3: stitch_needed → generate UI
  step 4: (triggers hash_edit.st) → edit gaps disperse here
```

The compiler sees a flat stream of gaps — it doesn't know or care that some came from nested .st files. It just pops, routes, and enforces laws. The nesting is invisible to the compiler. The fluidity comes from the composition.

### Reasoning commitments follow the same laws

Reasoning commitments (reason_needed → commitment gaps → commit_needed) are not a special mechanism. The commitment chain nests inside the macro chain as child gaps. The compiler doesn't know it's a commitment — it just sees gaps at various depths. commit_needed sits at lowest relevance, fires last. The commitment is invisible infrastructure — the compiler pops, routes, enforces. Same laws, same stack.

### The separation

- **.st files** = what gaps to create, in what order, with what vocab
- **Compiler** = when to pop, what to route, when to halt
- **Governor** = whether to allow, constrain, redirect, or revert

The .st author composes intent. The compiler enforces structure. The governor enforces convergence. Three layers, one stack, absolute laws.

### Code mechanisms

```
compile.py
├─ Ledger
│   ├─ .push_origin(gap, chain_id) → bottom of stack (LIFO)
│   ├─ .push_child(gap, chain_id, parent, depth) → TOP of stack (depth-first)
│   ├─ .pop() → pops from top (Law 1: LIFO)
│   ├─ .sort_by_priority() → origins sorted, children stay on top (Law 5)
│   └─ .chain_is_complete(chain_id) → all gaps resolved?
│
├─ Compiler
│   ├─ .validate_omo(vocab) → rejects consecutive mutations (Law 3)
│   ├─ .last_was_mutation → tracks OMO state
│   ├─ .record_execution(vocab, produced_commit) → updates OMO tracking
│   ├─ .needs_postcondition() → True if last was mutation (Law 8)
│   ├─ .force_close_chain(chain_id) → removes all entries, marks closed (Law 6)
│   ├─ .skip_chain(chain_id) → moves entries to bottom (stagnation)
│   ├─ .resolve_current_gap(gap_hash) → marks resolved, checks chain completion
│   │   └─ if chain length >= CHAIN_EXTRACT_LENGTH (8) → mark for extraction
│   └─ .add_step_to_chain(step_hash) → records step in active chain
│
├─ Governor
│   ├─ govern(entry, chain_length, state) → GovernorSignal
│   │   ├─ chain_length > MAX_CHAIN_DEPTH (15) → CONSTRAIN (Law 6)
│   │   ├─ is_diverging() → REVERT
│   │   ├─ is_oscillating() → REDIRECT
│   │   ├─ is_stagnating() → REDIRECT
│   │   ├─ is_mutate + grounded >= 0.5 + confidence >= 0.5 → ACT
│   │   └─ else → ALLOW
│   │
│   └─ GovernorState
│       ├─ .record(epistemic) → append vector
│       ├─ .information_gain() → magnitude of delta between last two vectors
│       ├─ .is_stagnating() → STAGNATION_WINDOW (3) steps with gain < SATURATION_THRESHOLD (0.05)
│       ├─ .is_diverging() → confidence dropped > 0.15 from previous
│       └─ .is_oscillating() → confidence alternating up/down for 4+ steps
│
├─ ChainState → OPEN → ACTIVE → SUSPENDED → CLOSED
│
└─ Constants
    ├─ MAX_CHAIN_DEPTH = 15
    ├─ CHAIN_EXTRACT_LENGTH = 8
    ├─ STAGNATION_WINDOW = 3
    ├─ SATURATION_THRESHOLD = 0.05
    └─ CONFIDENCE_THRESHOLD = 0.8

loop.py
├─ Universal postcondition (Law 8)
│   └─ after auto_commit: Gap.create("hash_resolve_needed", content_refs=[commit_sha])
│
└─ .st gap dispersal → emit_origin_gaps(step) — .st steps become ledger entries
    └─ follows all 8 laws without exception
```

---

## §9. Step Blobs, Chains, and Reasoning Steps

Everything is a step, but steps manifest at different scales — the way a single cell, an organ, and an organism are all alive but at different levels of organization. The same primitive, recurring at every zoom level.

### Three levels of step

**Blob** — a terminal step. Has a hash but derives no gaps. No branching, no children. It is a leaf on the trajectory tree. Examples: an observation injected into context, a resolved entity, a command output log. A blob is the atomic fact. It is what it is.

**Chain** — a sequence of steps originating from one gap. The chain compresses into a single hash via `chain_hash()`. A 20-step investigation is one hash. Unfoldable downward to any depth. A chain IS a reasoning step at a higher scale — it traces the causal path from origin gap to resolution. The chain is the thought. The blob is the percept. The chain connects percepts into understanding.

**Reasoning step** — a chain that contains sub-chains. Chains can nest. A project is a reasoning step containing task chains, each containing atomic steps. This is where the fractal nature becomes visible: the same hash-addressed, gap-driven, trajectory-appended primitive at every level.

```
Level 0: atomic step (blob)   — one observation or mutation, no children
Level 1: chain                — traces causal path across atomic steps
Level 2: reasoning step       — traces patterns across chains
```

### Chain lifecycle

```
OPEN       → origin gap entered ledger, chain created
ACTIVE     → current step is addressing a gap in this chain
SUSPENDED  → chain's current gap spawned children, waiting for resolution
CLOSED     → all gaps resolved, chain compressed to one hash
```

Chains that exceed CHAIN_EXTRACT_LENGTH (8) get extracted to `chains/*.json` — the hash remains on the trajectory but the full step data moves to a file. This keeps the trajectory compact while preserving full resolution capability. The extracted chain is a module — self-contained, addressable, unfoldable on demand.

### Code mechanisms

```
step.py
├─ Chain
│   ├─ .create(origin_gap, first_step) → chain_hash([origin_gap, first_step])
│   ├─ .add_step(step_hash) → appends step, rehashes chain
│   ├─ .length() → number of steps
│   ├─ .hash → content-addressed from member step hashes
│   ├─ .origin_gap → the gap hash that started this chain
│   ├─ .resolved → True when all gaps closed
│   └─ .extracted → True when saved to chains/*.json
│
├─ Trajectory
│   ├─ .chains → {chain_hash: Chain}
│   ├─ .add_chain(chain) → registers in chain index
│   ├─ .recent_chains(n) → last N chains for rendering
│   ├─ .find_chain(origin_gap_hash) → find chain by origin
│   ├─ .extract_chains(chains_dir) → long resolved chains → individual files
│   └─ .save_chains(path) → saves chain index to JSON
│
compile.py
├─ ChainState → OPEN | ACTIVE | SUSPENDED | CLOSED
├─ Compiler.force_close_chain(chain_id) → terminates at MAX_CHAIN_DEPTH (15)
├─ Compiler.resolve_current_gap(gap_hash) → checks chain completion, marks extraction
│   └─ length >= CHAIN_EXTRACT_LENGTH (8) → chain.extracted = True
│
└─ Ledger.chain_states → {chain_id: ChainState}
    ├─ .close_chain(chain_id) → CLOSED
    └─ .suspend_chain(chain_id) → SUSPENDED
```

---

## §10. Step Chain Activation (Adaptive Reasoning)

### Replacing commitments

The old commitment system tracked promises as registry entries. In cors, reasoning chains replace commitments entirely. No separate mechanism — the same trajectory, same compiler, same .st files. A commitment is an unresolved chain. A task is an active chain. A memory is a resolved chain compressed to a hash. One primitive, multiple scales.

### The start codon: reason.st

`reason.st` is the observation bridge AND the agency codon. When it fires, it renders reasoning chains as semantic trees — the same shape the main agent sees its trajectory in. Everything the system has reasoned about becomes a navigable, fully bloomed tree. The LLM studies these trees and chooses one of three outcomes.

### Three outcomes

**1. Observe (clarity)** — the rendered trees are sufficient. The LLM gains understanding from studying the semantic structure. May surface `clarify_needed` if something is ambiguous. No mutation. Pure observation bridge. This is the system reflecting — studying its own reasoning history to build understanding.

**2. Refine (update)** — a reasoning commitment needs correction or extension. The user asked for it, or the system concluded from the trees that something is wrong. Routes to `hash_edit_needed` to update the mutable reasoning chain. The chain evolves — new hash, old hash still resolvable on the trajectory.

**3. Manifest (agency)** — the LLM references a reasoning commitment hash AND composes a prompt. This is the agency trigger — the system manifests an agent from the commitment's context. The commitment's .st defines the agent's identity (constraints, scope, domain). The prompt defines the goal. The chain plays out depth-first in its own context. Results stay on the main trajectory — no isolated stores. `commit_needed` is injected as the LAST step at LOWEST relevance, behind all commitment gaps — it fires only after the entire commitment resolves.

### The activation cycle

```
reason_needed surfaces
  → step 1: render reasoning trees (observe, rel=1.0, post_diff=false)
      all naturally formed chains rendered as semantic trees
      reasoning commitments shown as potential agency targets
  → step 2: assess and route (flex, rel=0.9, post_diff=true)
      LLM studies trees, picks outcome:
        - no gaps → observe only, done
        - correction gap → routes to refine
        - commitment + prompt → routes to manifest
        - confusion → clarify_needed
  → step 3: refine or manifest (flex, rel=0.8, post_diff=true)
      if refine: hash_edit updates the reasoning chain
      if manifest: compose agent trigger + inject commitment gaps + trailing commit_needed
      if neither: resolve
  → step 4: post-reason check (observe, rel=0.7, post_diff=true)
      re-render affected trees to verify coherence
      may surface further refinement or manifestation needs
```

### The end codon: commit.st

`commit_needed` is the reintegration mechanism. It is NOT directly classifiable — the LLM should never emit it as a gap. It is injected by `reason.st` when a commitment is manifested, sitting at lowest relevance behind all commitment gaps. It fires last, reintegrates the full commitment tree into the main agent's context, and closes or continues the chain.

```
commit_needed fires (after all commitment gaps resolve)
  → step 1: render commitment tree (observe, rel=1.0, post_diff=false)
      full commitment chain as semantic tree — every step, gap, decision visible
  → step 2: reintegrate (flex, rel=0.9, post_diff=true)
      inject rendered tree into main trajectory context
  → step 3: close or continue (flex, rel=0.8, post_diff=true)
      commitment resolved? → close chain, hash compresses
      not resolved? → articulate remaining gaps for next activation
```

### Passive chain building (cross-turn)

Reasoning chains don't need to resolve in one turn. They build passively — steps that touch the same entity accumulate on the same chain without explicit activation. The `find_passive_chains()` function detects when a gap's content_refs overlap with an existing chain's origin gap references. Instead of creating a new chain, the step appends to the existing one.

### What this replaces

| Old system | cors equivalent |
|------------|----------------|
| Commitments | Passive chains — accumulate evidence across turns |
| Task delegation | reason.st activation — compose goal, chain plays out |
| Background agents | Same trajectory, cross-turn chains — resume via dangling gap mechanism |
| Judgment resolution | reason.st assess step — LLM reasons over existing chain |
| Reminders | Scheduled .st trigger (future — trigger: "scheduled:Xh") |

### The key principle

No extra mechanism. The trajectory IS the agent's memory. Chains ARE the reasoning units. The compiler sequences them. The governor monitors convergence. Cross-turn thresholds handle resumption. reason.st is just the start codon — it activates what's already there.

### Code mechanisms

```
skills/reason.st
├─ trigger: "on_vocab:reason_needed"
├─ step 1: render_reasoning_trees
│   ├─ vocab: hash_resolve_needed (observe)
│   ├─ relevance: 1.0 (fires first)
│   └─ post_diff: false (deterministic — no branching)
├─ step 2: assess_and_route
│   ├─ relevance: 0.9
│   └─ post_diff: true (LLM chooses: observe / refine / manifest)
├─ step 3: refine_or_manifest
│   ├─ vocab: hash_edit_needed (if refine)
│   ├─ relevance: 0.8
│   └─ post_diff: true
└─ step 4: post_reason_check
    ├─ vocab: hash_resolve_needed (re-render trees)
    ├─ relevance: 0.7
    └─ post_diff: true

skills/commit.st
├─ trigger: "on_vocab:commit_needed"
├─ step 1: render_commitment_tree (observe, rel=1.0, post_diff=false)
├─ step 2: reintegrate (flex, rel=0.9, post_diff=true)
└─ step 3: close_or_continue (flex, rel=0.8, post_diff=true)

step.py
├─ Trajectory.find_passive_chains(content_ref)
│   └─ active chains whose origin gap references overlap with content_ref
├─ Trajectory.append_to_passive_chain(chain_hash, step)
│   └─ appends step to existing chain, returns True if found
└─ Trajectory.extract_chains(chains_dir)
    └─ long chains (>= 8 steps) → chains/{hash}.json

compile.py
├─ Compiler.resolve_current_gap(gap_hash)
│   └─ marks chain.extracted when length >= CHAIN_EXTRACT_LENGTH (8)
└─ Compiler.readmit_cross_turn(gaps, step_hash)
    └─ re-scores dangling gaps at CROSS_TURN_THRESHOLD (0.6)

loop.py
├─ _find_dangling_gaps(trajectory) → unresolved gaps from prior turns
├─ find_passive_chains() checked before creating new chain
└─ _save_turn() calls extract_chains()
```

---

## §11. Temporal Signatures

Every step carries a timestamp (`Step.t`). Time is a structural signal the agent is expected to reason over — not hidden metadata, not computed on demand. It is a leaf on the semantic tree — visible, always present, always absolute, always the same format.

### Rendering format

All renders use absolute timestamps: `(2026-03-31 14:33:56)`. One format, universal, no decay. The LLM computes temporal distance by reading the timestamps directly. No "3 minutes ago" that becomes meaningless in a different context. The absolute timestamp is the truth. The agent can subtract.

```
chain:0d71...  "resolved config" (active, 3 steps) [2026-03-31 14:33:56]
  ├─ step:7146... "observed workspace" (2026-03-31 14:33:51)
  ├─ step:f13b... "resolved config" (2026-03-31 14:33:54)
  └─ step:53a2... "wrote config" → commit:bb9c032 (2026-03-31 14:33:56)
```

### What the agent reasons over

- **Temporal gaps**: "this chain hasn't been touched in 3 days" — staleness signal
- **Burst detection**: "these 5 steps happened in the same second" — part of one operation
- **Causal ordering**: timestamps confirm which step came first when step_refs are ambiguous
- **Commitment tracking**: "this reasoning commitment was last updated yesterday" — urgency signal
- **Cross-turn continuity**: timestamps show when turns happened relative to each other

### Where timestamps appear

| Render mode | Location | Format |
|-------------|----------|--------|
| Trajectory tree (turn start) | Chain headers + every step | `(2026-03-31 14:33:56)` |
| Deep render (per-gap injection) | Every step in causal ancestry | `(2026-03-31 14:33:56)` |
| Flat step render (no chains) | Every step | `(2026-03-31 14:33:56)` |

### Code mechanisms

```
step.py
├─ Step.t → timestamp set at Step.create() via time.time()
├─ absolute_time(t) → datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
├─ relative_time(t) → "3m ago" format (available but NOT used in renders)
│
├─ Trajectory.render_recent(n, registry)
│   ├─ chain header → absolute_time(last_step.t) in [brackets]
│   └─ every step → absolute_time(step.t) in (parentheses)
│
└─ Trajectory._render_steps_as_tree(steps, registry)
    └─ every step → absolute_time(step.t)

loop.py
└─ _render_step_tree(step, trajectory, depth, max_depth)
    └─ every ancestor step → absolute_time(step.t)
```

---

## §12. Supporting Infrastructure

These mechanisms serve the principles above but aren't principles themselves. They are the plumbing that connects the primitives to the world. Referenced here for completeness and traceability.

### Turn lifecycle

```
loop.py
├─ run_turn(user_message, contact_id) → complete turn lifecycle
│   ├─ 1. INIT
│   │   ├─ increment _turn_counter
│   │   ├─ Trajectory.load(TRAJ_FILE) + load_chains(CHAINS_FILE)
│   │   ├─ load_all(SKILLS_DIR) → SkillRegistry
│   │   ├─ git_head() + git_tree() → workspace state
│   │   └─ Session(model) → persistent LLM session
│   │
│   ├─ 1b. RESUME CHECK
│   │   └─ _find_dangling_gaps(trajectory) → surface unresolved gaps from prior turns
│   │
│   ├─ 2. FIRST STEP (origin)
│   │   ├─ render trajectory tree + HEAD + user message
│   │   ├─ LLM call → pre-diff reasoning + gap articulations
│   │   └─ _parse_step_output() → Step + [Gap]
│   │
│   ├─ 3. IDENTITY (.st injection)
│   │   ├─ _find_identity_skill(contact_id, registry) → on_contact trigger match
│   │   ├─ _render_identity(skill) → formatted identity data
│   │   └─ identity step → content_refs=[skill.hash], step_refs=[origin.hash]
│   │
│   ├─ 4. COMPILER
│   │   ├─ Compiler(trajectory, current_turn)
│   │   ├─ tag origin gaps with turn_id
│   │   ├─ readmit_cross_turn(dangling, origin_step.hash)
│   │   └─ emit_origin_gaps(origin_step) → ledger populated + sorted
│   │
│   ├─ 5. ITERATION LOOP (max MAX_ITERATIONS = 30)
│   │   ├─ compiler.next() → (entry, GovernorSignal)
│   │   ├─ HALT/None → break
│   │   ├─ REVERT → git revert last commit
│   │   ├─ Route by vocab:
│   │   │   ├─ DETERMINISTIC → kernel resolves directly
│   │   │   ├─ OBSERVATION_ONLY → resolve + inject (blob step)
│   │   │   ├─ is_observe → tool executes, LLM reasons
│   │   │   ├─ is_mutate → compose → execute → auto_commit → postcondition
│   │   │   ├─ clarify_needed → halt, gap persists
│   │   │   ├─ reprogramme_needed → PRINCIPLES.md + registry → compose
│   │   │   └─ bridge codons → .st activation
│   │   └─ Policy auto-route check before each execution
│   │
│   ├─ 6. REPROGRAMME PASS
│   │   └─ _reprogramme_pass() → automatic pre-synthesis housekeeping
│   │
│   ├─ 7. SYNTHESIS
│   │   └─ _synthesize(session, user_message) → SYNTH_SYSTEM → natural response
│   │
│   └─ 8. SAVE
│       ├─ trajectory.save(TRAJ_FILE)
│       ├─ trajectory.save_chains(CHAINS_FILE)
│       └─ trajectory.extract_chains(chains_dir)
│
├─ Session
│   ├─ .set_system(content) → system message (once)
│   ├─ .inject(content, role) → add to context
│   └─ .call(user_content) → OpenAI API → accumulates response
│
└─ System prompts
    ├─ PRE_DIFF_SYSTEM → gap definitions, vocab, hash tree navigation, identity
    ├─ COMPOSE_SYSTEM → mutation command composition
    └─ SYNTH_SYSTEM → response synthesis (no internal details)
```

### Hash resolution infrastructure

```
loop.py
├─ resolve_hash(ref, trajectory) → master resolver
│   ├─ 1. _skill_registry.resolve(ref) → _render_entity(skill)
│   ├─ 2. trajectory.resolve(ref) → _render_step_tree(step, trajectory, depth=0, max=5)
│   ├─ 3. trajectory.resolve_gap(ref) → _render_gap_tree(gap)
│   └─ 4. git_show(ref) → blob/tree/commit content
│
├─ _render_step_tree(step, trajectory, depth, max_depth)
│   ├─ renders step as semantic tree branch
│   ├─ follows step_refs backward (causal ancestry) up to max_depth
│   ├─ shows gaps as child branches
│   └─ same shape as render_recent()
│
├─ _render_gap_tree(gap) → gap with full context (scores, vocab, status)
│
├─ resolve_all_refs(step_refs, content_refs, trajectory)
│   └─ resolves all hashes, formats as injection blocks
│
├─ _render_entity(skill) → full .st data formatted for injection
└─ _resolve_entity(content_refs, registry) → entity .st from content_refs
```

### Git operations

```
loop.py
├─ git(cmd, cwd) → subprocess: run git command, return stdout
├─ git_head() → current HEAD commit hash (short)
├─ git_tree(commit) → file listing at commit (workspace visibility)
├─ git_show(ref) → resolve git object to content
├─ git_diff(from_ref, to_ref) → diff between commits
│
├─ auto_commit(message)
│   ├─ git status --porcelain → anything to commit?
│   ├─ pre_sha = git_head()
│   ├─ git add -A → git commit -m message
│   ├─ post_sha = git_head()
│   ├─ _check_protected(post_sha, pre_sha) → scan for immutable violations
│   └─ violations? → git revert --no-commit HEAD → commit revert → return None
│
├─ _check_protected(commit_sha, pre_commit_sha)
│   ├─ git diff --name-only between commits
│   └─ for each changed file: _match_policy → immutable? → violation
│
├─ _load_tree_policy() → tree_policy.json or DEFAULT_TREE_POLICY
└─ _match_policy(path, policy) → exact match, then longest prefix match
```

### Tool execution

```
loop.py
├─ execute_tool(tool_path, params) → subprocess: python3 tool, stdin=JSON, stdout captured
├─ _extract_json(text) → extracts JSON object from LLM output
├─ _extract_command(text) → extracts shell command from LLM JSON
│
├─ TOOL_MAP → vocab → {tool: path, post_observe: target}
├─ MAX_ITERATIONS = 30 → safety limit on iteration loop
├─ TRAJECTORY_WINDOW = 10 → recent chains rendered at turn start
│
├─ run_command(command_name, registry) → /command REPL handler
│   └─ fires command .st files directly (trigger: "command:X")
│
└─ PRE_DIFF_SYSTEM → dynamic bridge section with entity list injected at runtime

compile.py
└─ Compiler.render_ledger() → debug view of current stack state

skills/loader.py
└─ load_all(skills_dir) → SkillRegistry (bridge + command separation)
```

---

## §13. Step Chain Curation — Composition Over Construction

Higher-order agents (reprogramme, reason) build workflows by composing existing .st files and reasoning chains. But composition is not obligation — efficiency is the ideal. A 3-step direct solution beats an 8-step composed solution that winds through three existing workflows. The goal is minimum steps to resolution, not maximum reuse.

### The curation principle

When building a new workflow:

1. **Survey** — what .st files and active chains already exist that relate to this goal?
2. **Evaluate** — does referencing an existing chain add value, or add noise? Does it shorten the path or lengthen it?
3. **Compose if efficient** — if an existing .st handles a step cleanly, reference it. Its gaps disperse onto the ledger. You get the full chain for free.
4. **Define if cleaner** — if composing existing chains would create a longer path than writing fresh steps, write fresh. Efficiency over elegance.

### The anti-pattern

```
BAD: video_pipeline.st references research.st → which references hash_edit.st → ...
     (7 nested .st files, 23 total gaps, 15 irrelevant to the actual goal)

GOOD: video_pipeline.st
     step 1: resolve project context (hash_resolve_needed)
     step 2: compose video brief (post_diff: true)
     step 3: generate via stitch (stitch_needed)
     (3 steps, all relevant, no nesting bloat)
```

### When to compose vs define

| Compose (reference existing .st) | Define (write fresh steps) |
|----------------------------------|---------------------------|
| Existing workflow does EXACTLY what this step needs | Existing workflow does 80% + 20% noise |
| Existing chain has been validated across turns | No existing chain covers this |
| Entity .st has context the agent needs | A simpler observation step would suffice |
| Step count stays flat or grows sub-linearly | Nesting would create depth > 8 |

### Recursive compounding

Chains can reference chains. Workflows can embed workflows. This is the power — but it must compound coherently:

- Each layer of nesting adds depth to the ledger
- MAX_CHAIN_DEPTH (15) applies to the TOTAL depth, not per .st
- Three nested .st files with 5 steps each = 15 deep = force-close territory
- The agent should estimate total depth before composing and prefer flat over deep

### Chain efficiency metric

An efficient chain resolves its goal in the minimum number of steps that maintain OMO rhythm:

```
Minimum: 1 step (blob — observation only)
Typical: 3-5 steps (observe → reason → act → observe → confirm)
Complex: 6-8 steps (with branching at decision points)
Overengineered: >8 steps (consider splitting or simplifying)
```

### Entity references as soft nudges

When building .st workflows, the agent should reference relevant entities by hash in the `refs` field — even if the workflow doesn't directly resolve them. This puts entities in the foreground:

```json
{
  "name": "video_review",
  "refs": {
    "admin": "72b1d5ffc964",
    "clinton": "e4ac2f28e8bc",
    "cors_ui": "58bda1f3fe63"
  },
  "steps": [...]
}
```

When this workflow activates, the kernel sees these hashes. The LLM may reference them in gap articulations. If relevant enough, they enter the ledger through normal admission. If not, they remain visible context — soft nudges, not hard dependencies.

This replaces the old tool-hints pattern. Instead of configuring hints per precondition, the .st file's refs field declares which entities MIGHT be relevant. The system decides — through the LLM's gap articulation and the kernel's admission scoring — whether to actually surface them. The refs field is a nudge, not a command.

### The curation hierarchy

1. **Single step** — if a gap resolves in one observation or mutation, don't wrap it in a workflow
2. **Inline steps** — if 2-3 steps suffice, write them directly in the .st
3. **Compose existing** — if an existing .st covers a complex sub-task cleanly, reference it
4. **Build new .st** — only when no existing primitive or composition handles the goal efficiently
5. **Build chain of .st** — only for multi-phase projects where each phase is genuinely distinct

At every level, consider which entities must be referenced. A video pipeline should ref the people involved. A compliance workflow should ref the regulation entity. A research chain should ref the domain knowledge .st. Hash references are how the system knows what's relevant — without them, the workflow operates blind.

### Code mechanisms

```
compile.py
├─ MAX_CHAIN_DEPTH = 15 → force-close applies to total nesting depth
├─ CHAIN_EXTRACT_LENGTH = 8 → chains beyond this extracted to files
├─ LedgerEntry.depth → tracks nesting depth across .st composition
├─ Compiler.force_close_chain() → terminates chains exceeding depth
└─ Compiler.emit_origin_gaps() → .st steps become ledger entries

loop.py
├─ Reprogramme prompt: "check existing workflows before building new"
├─ Entity registry injection → reprogramme agent sees all .st files
├─ Command registry injection → reprogramme agent sees all /command workflows
└─ .st gap dispersal → child .st gaps enter as children of current chain

skills/*.st
└─ Steps use relevance descending (1.0 → 0.9 → 0.8) to sequence execution
```

---

## File Map

```
cors/
├─ step.py         ← Layer 0: step primitive, gap, chain, trajectory, render
├─ compile.py      ← Layer 1: compiler, ledger, governor, vocab, admission
├─ loop.py         ← Layer 2: turn loop, persistent LLM, hash resolution, git, tools
├─ skills/         ← .st files: entities, workflows, codons (reason, commit, reprogramme)
│   └─ loader.py   ← skill registry: load, resolve, display names
├─ tools/          ← tool scripts: hash_manifest, st_builder, stitch, file_grep, etc.
├─ tree_policy.json ← per-path mutation policy (immutable, on_mutate routing)
├─ trajectory.json  ← persisted trajectory (step dicts in chronological order)
├─ chains.json      ← persisted chain index
└─ chains/          ← extracted long chains (>= 8 steps)
```

---

> The system is complete when there is nothing left to remove.
> Every mechanism is step. Every address is a hash. Every gap is a measurement.
> The kernel provides structure. The LLM provides meaning. Neither controls the other.
