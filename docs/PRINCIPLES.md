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

One persistent LLM session per turn. The same model does perception, gap scoring, and command composition — all in one continuous stream. No separate mini-models for classification. No hand-off between specialists. Coherence comes from the persistent context window. The trajectory provides structural grounding. The context window does not preload all of `trajectory.json` raw; it carries a salient semantic render of prior trajectory state, and deeper structure remains hash-resolvable on demand.

The trajectory is rendered as a traversable hash tree (same shape as git commit trees) via `render_recent()`. Known skill hashes render with named prefixes — `kenny:72b1d5ffc964`, `debug:a72c3c4dec0c`. When a skill evolves, the hash changes but the name stays. Steps referencing the old hash trace to what was. Steps referencing the new hash trace to what is. During iteration, the currently addressed ledger chain is also rendered as its own semantic tree (`Active Chain Tree`), so the model sees the live causal branch it is inside while working the current gap.

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

## §3. The Step Manifestation Engine

The kernel is a step manifestation engine. A gap is the universal primitive, but a gap is never just a sentence. A gap is a structural seed that can manifest as context injection, ledger dispersal, mutation, reintegration, or persistence depending on its configuration.

The important separation is not merely WHAT versus HOW. It is:

- **Gap** = the measured discrepancy
- **Manifestation config** = the structural law of how that discrepancy should unfold
- **Activation identity** = which exact curated step package, if any, should fire

Primitive kernel vocab still matters, but only as the stable execution algebra for the kernel's native mechanisms. For curated workflows, exact activation can be carried by step-file hash while priority, grouping, routing, and analytics remain derivable from gap structure itself. The hash does not need to carry semantic meaning. It only needs to identify the exact package to manifest.

This is what makes `.st` structural rather than cosmetic. A `.st` file is not “a file the system reads.” It is a step primitive whose resolution manifests further structure.

### Structural distinction: `entity.st` vs `action.st`

The distinction between `entity.st` and `action.st` is not naming convention. It is derivable from manifestation shape.

- **`entity.st`** manifests primarily as context injection or semantic scope refinement. It sharpens the system's internal state model: identity, preferences, domain knowledge, constraints, boundaries, tracked entities, and long-horizon background concerns.
- **`action.st`** manifests primarily as ledger dispersal. Its steps become executable gaps or embeddings that the compiler can sequence depth-first under the normal laws.
- **Hybrid `.st`** can do both. It may inject semantic context first, then disperse action gaps, or mix context and action within one package.

The system should be able to derive this distinction from structure alone: the gap shape, manifestation mode, and skeleton contract reveal whether the artifact is entity-like, action-like, or hybrid.

### Two skeletons, one engine

The step manifestation engine has two authoring surfaces:

- the **workflow skeleton** — structural, deterministic, compiler-facing
- the **semantic skeleton** — entity/state-facing, persistence-facing, optionally hybrid

The workflow skeleton expresses lawful step flow. The semantic skeleton expresses what an entity IS, what semantic context it carries, and when it also owns executable flow.

They are not separate systems. They are two views of the same manifestation engine:

- one for executable structure
- one for persistent semantic state

### Two sides of the same coin

`reason_needed` and `reprogramme_needed` are complementary manifestations of the same OS-level mechanism.

- **`reason_needed`** is the more stateful, conscious, structural side. It reasons over step flows, chains, entity space, and executable packages. It constructs or refines structures the system can deterministically derive, execute, inspect, or crystallize.
- **`reprogramme_needed`** is the more stateless, subconscious, persistence side. It updates the system's long-horizon internal state model: entities, preferences, domain structures, and tracked background concerns. It keeps the operating context alive over long periods without forcing every update through explicit structural planning.

Together they form the operating system for the LLM:

- `reason_needed` manages structural execution intelligence
- `reprogramme_needed` manages persistent semantic calibration

One is conscious flow architecture. The other is subconscious state continuity. Both are step manifestation.

### Tier 1: Observe (external &, priority 20)

The kernel resolves data. The LLM receives it. No mutation. These are the system's sensory organs — they bring information into the context window without changing the world.

| Vocab | Manifestation | Post-diff |
|-------|--------------|-----------|
| `hash_resolve_needed` | Kernel resolves hash → step/gap/skill/.st/git blob. If hash is a .st entity, full entity data injected. | Deterministic — blob step, no branching |
| `pattern_needed` | Kernel runs file_grep → results injected | LLM reasons over results, may branch |
| `mailbox_needed` | Kernel checks mailbox state → results injected | LLM reasons over results, may branch |
| `external_context` | LLM surfaces from current context — no tool | Blob step, no branching |
| `research_needed` | Activates the controlled research workflow from a domain/entity/hash seed | Workflow-defined review, verification, and follow-up |

### Tier 2: Mutate (external &mut, priority 40)

The LLM composes. The kernel executes. Auto-commit. Postcondition fires. These are the system's effectors — they change the world and immediately verify the change.

| Vocab | Manifestation | Compose mode | Post-observe |
|-------|--------------|-------------|--------------|
| `hash_edit_needed` | hash_manifest.py — read/write/patch/diff by path. Routes by file type (.st→st_builder, .json→json_patch, .docx→doc_edit) | LLM composes JSON params | Per tree_policy.json |
| `stitch_needed` | stitch_generate.py — prompt → HTML + Tailwind CSS | LLM composes UI prompt | `ui_output/` (screenshot blob) |
| `content_needed` | file_write.py — write new file | LLM composes content | Commit tree |
| `script_edit_needed` | file_edit.py — edit existing file | LLM composes shell command | Commit tree |
| `command_needed` | code_exec.py — execute shell command. Output blob-hashed into git. | LLM composes command | `logs/` (output blob) |
| `email_needed` | email_send.py — send email/message | LLM composes message | mailbox |
| `json_patch_needed` | json_patch.py — surgical JSON mutation | LLM composes patch | Commit tree |
| `git_revert_needed` | git_ops.py — revert/checkout | LLM composes git command | Commit tree |

All mutations follow the same rhythm: **compose → execute → auto-commit → postcondition** (hash_resolve_needed targeting post_observe path). No exceptions. The postcondition is the system verifying its own mutation — the same way a cell checks its DNA after replication.

### Tier 3: Bridge codons (internal &mut, priority 90-99)

Four codons govern the reasoning lifecycle. The biological analogy is precise: a codon is a nucleotide sequence that signals a specific instruction to the cellular machinery. These four vocab terms signal specific instructions to the kernel machinery. They live in `skills/codons/` — immutable, protected by tree_policy with `on_reject: reason_needed`. Any attempt to mutate a codon file auto-reverts and falls back to reason_needed for recalibration.

| Vocab | Codon | Priority | Manifestation |
|-------|-------|----------|--------------|
| `reason_needed` | **START** | 90 | Stateful structural abstraction. Planning primitive + reorientation checkpoint + heartbeat trigger. Reasons over semantic trees, entity space, executable skeletons, and step-chain structure. |
| `await_needed` | **PAUSE** | 95 | Synchronization checkpoint. Suspends parent chain until referenced sub-agent completes. Renders sub-agent's full semantic tree → parent inspects → accept/correct/reactivate. If turn ends before sub-agent finishes, persists as dangling gap — heartbeat picks up next turn. |
| `commit_needed` | **END** | 98 | Reintegration. Renders full commitment tree into main context. Closes or continues chain. NOT directly classifiable — injected by reason.st at lowest relevance behind commitment gaps. |
| `reprogramme_needed` | **PERSIST** | 99 | Stateless semantic state update. World-building and long-horizon calibration. Persists entity and semantic-state changes so the system stays informed across turns and time horizons. |
| `clarify_needed` | **CROSS-TURN** | 15 | Forced user-boundary bridge. Halts iteration, turns the gap desc into the clarification question, persists unresolved state across turns, and resumes when the user replies. |

**Codon priority ordering:** clarify (15) surfaces before ordinary observation because it blocks lawful progress. Then reason (90) → await (95) → commit (98) → reprogramme (99). Within the bridge tier, planning fires first, checkpoints fire after inline work, reintegration fires after commitment gaps resolve, and persistence fires last.

Mid-turn commitment activation follows the compiler laws exactly: reason_needed fires → commitment gaps disperse onto ledger → commit_needed sits at bottom → commitment resolves depth-first → commit reintegrates → main chain resumes. The compiler doesn't know it's processing a commitment. It just sees gaps at various depths. Same laws, same stack.

**Law 9 guarantee:** Background triggers (reprogramme_needed) always close the loop. If the main agent sets a manual `await_needed`, the parent chain suspends and resumes when the sub-agent finishes. If no manual await is set, an automatic `reason_needed` heartbeat persists after synthesis — next turn, the agent inspects the sub-agent's semantic tree and either closes, revisits, or refines. The loop is always closed.

### Tier 4: `.st` Resolution (internal &, no dedicated entity vocab)

Entity-style and action-style `.st` files do not require separate top-level vocab names just to exist. They are still addressable through hash resolution. But what they MANIFEST into is structural, not textual.

When a `.st` hash is resolved, the system should treat it as a step package, not as dead data. Its manifestation mode is derivable from its structure:

| `.st` structural shape | Manifestation | What happens |
|------------------------|---------------|-------------|
| Pure entity semantics | Context injection | Semantic state is injected: identity, preferences, scope, constraints, domain knowledge |
| Action workflow | Ledger dispersal | Steps become executable gaps or deterministic package activations |
| Hybrid | Mixed manifestation | Semantic context injects first, action gaps or embeddings disperse after |

So the principle is not “the system reads `.st` files.” The principle is “the system resolves step packages, and their structure determines manifestation.”

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
├─ OBSERVE_VOCAB = {pattern_needed, hash_resolve_needed, mailbox_needed, external_context, research_needed}
├─ MUTATE_VOCAB  = {hash_edit_needed, stitch_needed, content_needed, script_edit_needed, command_needed, email_needed, json_patch_needed, git_revert_needed}
├─ BRIDGE_VOCAB  = {reason_needed, commit_needed, reprogramme_needed, await_needed, clarify_needed}
├─ is_observe(vocab) → vocab in OBSERVE_VOCAB
├─ is_mutate(vocab)  → vocab in MUTATE_VOCAB
├─ is_bridge(vocab)  → vocab in BRIDGE_VOCAB
└─ vocab_priority(vocab)
    ├─ clarify_needed → 15 (forced clarification boundary)
    ├─ observe → 20
    ├─ mutate  → 40
    ├─ unknown → 50
    ├─ reason_needed → 90 (planning/reorientation)
    ├─ await_needed → 95 (sync checkpoint)
    ├─ commit_needed → 98 (reintegration)
    └─ reprogramme_needed → 99 (fires last)

loop.py
├─ TOOL_MAP
│   ├─ vocab → {tool: path, post_observe: target}
│   ├─ hash_resolve_needed → {tool: None} (kernel resolves directly)
│   ├─ pattern_needed → {tool: "tools/file_grep.py"}
│   ├─ mailbox_needed → {tool: "tools/email_check.py"}
│   ├─ research_needed → {tool: "tools/research_web.py"}
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

## §5. Reprogramme: The Semantic State Engine

Reprogramme is the semantic state engine of the system. While reason operates on conscious structural flow, reprogramme maintains the subconscious internal state model that lets the system remain calibrated over long horizons. It creates and updates the semantic substrate the rest of the system reasons with.

The analogy is genetic engineering: the cell (kernel) operates on proteins (steps), but the genetic engineer (reprogramme) designs the DNA (.st files) that encodes the proteins. The cell doesn't know or care about the engineer. It just reads the genes and expresses them. But the engineer knows the cell intimately — and designs genes that compose with its machinery.

### On-demand semantic persistence

The LLM explicitly surfaces `reprogramme_needed` when semantic state must be created, updated, or stabilized. This is not primarily executable planning. It is persistence: the user corrects a preference, introduces a new person, extends domain scope, asks the system to remember something, or establishes a long-horizon background concern. Reprogramme carries those changes into the system's semantic substrate.

### Structural relation to reason

Reason and reprogramme are two sides of the same manifestation engine.

- Reason structures flow.
- Reprogramme structures state.

Reason is more stateful and conscious. Reprogramme is more stateless and subconscious. Reason asks: *what executable structure should exist or be activated?* Reprogramme asks: *what semantic state should persist so the system remains informed?*

This is why reprogramme is the mechanism that lets the user keep the system informed over long periods. It is the semantic continuity layer of the OS.

This means the .st ecosystem is self-sustaining:
- Entities referenced frequently → high co-occurrence → high grounded score → easier to admit
- Entities never referenced → zero co-occurrence → decay to dormancy
- Dormant entities can be revived if they recur — the hash is always resolvable
- The reprogramme agent creates new entities when gaps can't be filled by existing ones

### The state update cycle

```
LLM perceives trajectory
  → entity and semantic state resolve through step package manifestation
  → LLM reasons with current semantic state
  → if state is stale, missing, or corrected → reprogramme_needed surfaces
  → reprogramme persists semantic update
  → commit → hash evolves → trajectory tracks the evolution
  → next turn, the evolved semantic state is what resolves
```

Reprogramme operates in two modes: **classifiable mid-turn** and **automatic pre-synthesis**. Either way, it persists semantic state so the system remains calibrated beyond the current turn.

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
- A workflow → `debug:a72c3c4dec0c` (the .st file hash)
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

## §7. Post-Diff: The Re-Entry Primitive

`post_diff` is not just a fluidity dial. It is a workflow-management primitive of the manifestation engine.

The codons handle lifecycle boundaries:

- `reason_needed` → start / structural activation
- `await_needed` → wait / synchronization
- `commit_needed` → stop / reintegration

`post_diff` governs something different: whether execution **re-enters semantic measurement** after a step has manifested.

- **post_diff: false** → manifest → continue linearly. The step is treated as a closed expression unit.
- **post_diff: true** → manifest → re-enter measurement. The result is opened back up to reasoning, verification, branching, or further dispersal.

So `post_diff` is not a codon. It is the branch/re-entry primitive. In the biological analogy, it behaves more like a splice or translation-control site than a start or stop codon. It determines whether the manifestation engine continues as a straight sequence or re-opens the chain to semantic branching.

This matters because LIFO and OMO are not enough on their own to validate a workflow skeleton. A skeleton can satisfy start/wait/stop boundaries and still be incoherent if re-entry points are wrong. `post_diff` is what tells the system where reflection, branch emission, verification, or recursive manifestation are even allowed.

### What `post_diff` means structurally

When a workflow is compiled, every manifested step must declare one of two states:

- **closed expression** (`post_diff: false`)
  The step completes and the sequencer proceeds. Use for deterministic injection, fixed observation, fixed mutation, and non-branching persistence.

- **open expression** (`post_diff: true`)
  The step completes and the sequencer re-enters semantic measurement. Use for decision points, diagnosis, verification, reasoning, recursive embedding, and any step whose result may lawfully emit child gaps.

The important point is that this is a structural permission, not just a runtime mood. If a step is not marked open, the workflow should not branch there.

### What this means for workflow design

When designing a workflow skeleton or `.st` package:

- **Deterministic pipeline**: mostly `post_diff: false`
- **Guided branching**: `post_diff: true` only at explicit decision or verification points
- **Recursive structural reasoning**: `post_diff: true` at the points where the system is allowed to reopen the chain and emit new structure

So `post_diff` should be treated as a first-class workflow primitive alongside the codons, not as a minor step option.

### Code mechanisms

```
skills/*.st
├─ Each step object can carry "post_diff": true|false
└─ This expresses whether the step is structurally open or closed after manifestation

skills/loader.py
└─ SkillStep.post_diff → preserved on loaded step packages

schemas/skeleton.v1.json
├─ Every non-terminal phase requires post_diff
└─ post_diff is part of the structural contract submitted for compilation

tools/skeleton_compile.py
└─ Preserves post_diff into stepchain.v1 as manifestation-time structure

loop.py
└─ Current runtime still only partially enforces post_diff generically
   → the principle is ahead of the implementation here
```

---

## §8. Compiler Laws and Recursive Fluidity

The compiler has laws. They are absolute. No gap, no .st file, no LLM output can violate them. They are the physics of this system — not guidelines, not best practices, not configurable parameters. They are inviolable constraints that make everything else possible, the way the laws of thermodynamics constrain but enable all of chemistry.

But the recursive nature of .st composition allows workflows to achieve fluidity WITHIN those laws — not by breaking them, but by structuring gaps so the laws work in their favour. This is the key insight: rigidity at the compiler level enables fluidity at the composition level.

### The mRNA model

The manifestation engine should be understood as an mRNA model with the compiler integrated as the sequencer.

- **Layer 0 primitives** are the nucleotide alphabet: step, gap, refs, scores, manifestation config.
- **Skeletons** are the transcribed structural sequence: the authored description of what can lawfully manifest.
- **The compiler** is the sequencer or ribosome: it does not invent meaning, it translates lawful structure into executable order.
- **The ledger** is the translation surface: one active branch, deepest child first, return to branch root before next sibling.
- **The trajectory** is expressed structure: the realized chain, mutation record, and resolved semantic tree.
- **The session cache** is the salient semantic preload plus the current turn's accumulated renders.

In this model, the compiler does not sit outside manifestation. It is part of manifestation. A skeleton is not valid merely because it is well-formed JSON. It is only valid if it can be sequenced under the compiler's laws.

That means the manifestation engine must be able to reject workflow skeletons that cannot compile under:

- **LIFO** — every child branch must close before the next sibling proceeds
- **Depth-first** — branch descent must return to root before sibling continuation
- **OMO** — no mutation path may produce consecutive mutations without lawful observation/re-entry between
- **Postcondition** — every mutation path must admit verification
- **Loop closure** — background branches must rejoin by await or heartbeat
- **Post-diff coherence** — only open-expression steps may lawfully branch

So the compiler laws are not merely runtime safety checks. They are part of the static manifestation validity of the workflow itself.

### The eight laws

**1. LIFO** — The ledger is a stack. Deepest child pops first. No gap can jump the queue. This ensures depth-first resolution — you finish what you started before moving on.

**2. Depth-first** — One chain at a time. Follow gap_A all the way down before touching gap_B. This prevents the system from context-switching between unrelated chains, which would dilute the LLM's attention.

**3. OMO** — No consecutive mutations without observation between. The compiler rejects mutation after mutation. Every action must be preceded by perception and followed by verification. This is the heartbeat of the system: observe-mutate-observe, observe-mutate-observe.

**4. Admission** — Score must meet threshold. Fresh = 0.4, cross-turn = 0.6, dormant = 0.7. Gaps that don't meet the bar don't enter the ledger. The threshold is tiered by origin — the further a gap has travelled, the more it must justify its continued existence.

**5. Priority ordering** — Observe (20) before mutate (40) before bridge codons (99). Within same priority, higher relevance pops first. This ensures the system gathers information before acting, and acts before persisting.

**6. Force-close** — Chains exceeding MAX_CHAIN_DEPTH (15) are force-closed. No infinite loops. This is the circuit breaker — if a chain can't resolve in 15 steps, it's either pathological or needs to be broken into sub-chains.

**7. Immutability** — Gaps are immutable after creation. Scores set at emission, never modified. This ensures the trajectory is a faithful record of what the LLM actually perceived, not a retroactive revision.

**8. Postcondition** — Every mutation auto-commits and injects hash_resolve_needed. No mutation without verification. This is Law 3 (OMO) enforced structurally — even if the .st author forgets to add an observation step, the postcondition ensures one fires.

**9. Loop always closes** — Every background trigger must eventually reintegrate with the parent trajectory. Either the flow-builder agent sets a manual `await_needed` checkpoint (synchronous — parent chain suspends, resumes when sub-agent finishes) or the kernel inserts an automatic `reason_needed` heartbeat after synthesis (asynchronous — next turn, agent inspects sub-agent's semantic tree). The heartbeat is recursive: if inspection triggers further background work, another heartbeat persists. The loop closes when all background chains are resolved. This is not a constraint on the flow-builder — it is a guarantee by the kernel.

### Workflow validation

Because the compiler is part of the manifestation engine, every workflow skeleton submitted by `reason_needed` should be statically checkable before execution.

A valid workflow skeleton must answer:

- where does manifestation start?
- where may it suspend?
- where does it reintegrate?
- where may it reopen to semantic measurement?
- can every branch descend and return under LIFO?
- can every mutate path satisfy OMO without illegal sibling jumps?

This means a workflow checker should validate, at minimum:

- branch-root / child / sibling ordering is compatible with depth-first return
- every mutation path has lawful observation before and after
- `post_diff` is present and coherent at every branchable step
- await or heartbeat closure exists for every background branch
- no phase structure implies impossible sequencing under the ledger laws

### How `.st` files and skeletons compose within the laws

A `.st` file's steps, or a compiled workflow skeleton's phases, are still subject to the same laws. The author controls structural expression. The compiler controls lawful sequencing.

- **Relevance scores** — sequences execution order within the same priority bracket
- **Vocab selection** — determines which tier each step operates in
- **post_diff** — controls whether the chain may reopen after each step

This means a workflow can look fluid while still being mechanically lawful, because the manifestation engine is validating and sequencing it under one set of compiler laws.

```
debug.st:
  step 1: hash_resolve_needed (observe, rel=1.0, post_diff=false)  ← fires first, deterministic
  step 2: null vocab (flex, rel=0.9, post_diff=true)               ← LLM reasons, may branch
  step 3: hash_edit_needed (mutate, rel=0.8, post_diff=true)       ← can branch on failure
  step 4: command_needed (mutate, rel=0.7, post_diff=true)         ← verification
```

The compiler sees: observe gap (priority 20), then unknown gap (50), then two mutate gaps (40). After priority sorting, the observe fires first. The null-vocab gap lets the LLM reason freely. Then mutations fire with automatic postconditions between them (OMO preserved).

### Recursive .st embedding

The real power: a .st step's vocab can trigger ANOTHER .st file. When that happens, the child .st's gaps disperse onto the ledger AS CHILDREN of the current chain. Depth-first means they resolve before the parent resumes.

```
debug_orchestrator.st:
  step 1: hash_resolve_needed → resolve project context
  step 2: (triggers debug.st) → debug gaps disperse here, depth-first
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

### The start codon: reason.st — three roles

`reason.st` is the system's most versatile codon. It serves three distinct roles through the same mechanism:

**Role 1: Planning primitive** — For complex tasks, the main agent emits `reason_needed` to decompose and structure work as executable manifestation. The reason agent has semantic tree visibility and can build lawful step flow bottom-up: leaf chains first, then composed parents, then top-level orchestration. Its natural authoring surface is the workflow skeleton: a structural description the system can deterministically derive, compile, inspect, and execute. In the current runtime, `reason_needed` can either emit the native `reason.st` codon, submit a `skeleton.v1` for deterministic compilation, or activate an existing `.st` / compiled `.json` chain package by hash.

**Role 2: Reorientation checkpoint** — When the compiler rejects a chain (missing await, OMO violation, codon immutability), the fallback is `reason_needed`. The agent re-renders its semantic trees, sees what went wrong, and reconstructs its approach. This is the same role `reclassify` played in v4.5 but through an existing primitive rather than a separate mechanism. Any rejection resolves to reason.

**Role 3: Heartbeat trigger** — When background work is in progress without a manual await, the kernel persists an automatic `reason_needed` after synthesis. Next turn, this heartbeat fires — the agent renders the sub-agent's semantic tree, the active chain it is re-entering, and the package/entity network it depends on, then routes: close, revisit, or refine+reactivate. The heartbeat recurs until all background chains resolve.

### Six outcomes

The LLM's post-diff after viewing the rendered trees determines the path:

**1. Observe (clarity)** — the rendered trees are sufficient. The LLM gains understanding from studying the semantic structure. May surface `clarify_needed` if something is ambiguous. No mutation. Pure observation bridge.

**2. Refine (update)** — a reasoning commitment needs correction or extension. Routes to `hash_edit_needed` to update the mutable reasoning chain. The chain evolves — new hash, old hash still resolvable on the trajectory.

**3. Manifest (agency)** — the LLM references a reasoning commitment hash AND composes a prompt. This is the agency trigger — the system manifests an agent from the commitment's context. `commit_needed` is injected as the LAST step at LOWEST relevance, behind all commitment gaps — it fires only after the entire commitment resolves.

**4. Plan (decompose)** — for complex tasks, the agent writes executable structure as a workflow skeleton. Build layers back-to-front: leaf chains first, then parents that adopt them. The system can deterministically derive execution packages from that structure.

**5. Heartbeat (inspect)** — inspect background sub-agent's semantic tree. Three sub-paths: accept (close the loop, report), revisit (adjust the chain), refine+reactivate (trigger more work with its own heartbeat).

**6. Reorient (recalibrate)** — after compiler rejection or immutability violation, reconstruct the rejected chain with corrections.

### The activation cycle

```
reason_needed surfaces
  → step 1: render reasoning trees (observe, rel=1.0, post_diff=false)
      salient prior trajectory window rendered as semantic trees
      current ledger chain rendered as Active Chain Tree
      step network rendered as current package ecology
  → step 2: assess and route (flex, rel=0.9, post_diff=true)
      LLM studies trees, picks one of six outcomes:
        - no gaps → observe only, done
        - correction gap → routes to refine
        - commitment + prompt → routes to manifest
        - complex task → routes to plan (bottom-up chain construction)
        - background work done → routes to heartbeat (inspect sub-agent)
        - compiler rejection → routes to reorient (recalibrate)
        - confusion → clarify_needed
  → step 3: construct or act (flex, rel=0.8, post_diff=true)
      if planning: write executable structure as workflow skeleton
        - structural law lives in the skeleton
        - activation identity may point at exact curated step packages by hash
        - entity/action distinction is derivable from manifestation structure
        - embed await_needed after any background trigger
        - build back-to-front: leaf chains first, parents adopt them
        - resulting structure is deterministically compilable by the system
        - lawful compiled action packages crystallize into hash-addressable `.st` or `.json` artifacts
      if refining: hash_edit updates the reasoning chain
      if manifesting: compose agent trigger + inject commitment gaps + trailing commit_needed
      if heartbeat: render sub-agent tree → accept/revisit/refine
      if reorienting: reconstruct rejected chain with corrections
  → step 4: post-reason check (observe, rel=0.7, post_diff=true)
      verify coherence of constructed/modified trees:
        - await codons present after background triggers
        - leaf chains exist before parents reference them
        - relevance descending within each chain
        - post_diff correct (false for deterministic, true for decisions)
        - all 7 gap axes present on constructed steps
        - existing .st embeddings referenced by valid hash
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

### The pause codon: await.st

`await_needed` is the synchronization checkpoint. When the flow-builder agents construct chains that trigger background work (via reprogramme_needed), they embed `await_needed` at a strategic point — a barrier where the parent chain suspends and waits for the sub-agent to complete.

```
await_needed fires
  → step 1: suspend and wait (observe, rel=1.0, post_diff=false)
      if sub-agent done → proceed immediately
      if still running → persist as dangling gap → heartbeat next turn
  → step 2: render sub-agent tree (observe, rel=0.9, post_diff=false)
      full semantic tree injection — every step, gap, decision visible
  → step 3: inspect and route (flex, rel=0.8, post_diff=true)
      accept → close await, resume parent chain
      correct → emit refinement gaps
      reactivate → trigger further background work (with its own await/heartbeat)
```

The await codon reuses commit.st's semantic tree injection primitive. The difference is the trigger: commit fires when inline child gaps resolve (depth-first, automatic). Await fires when an external background chain closes (asynchronous, requires completion signal).

### The heartbeat mechanism

The heartbeat is the automatic safety net that guarantees Law 9 (loop always closes):

```
Turn N:   main agent triggers background work → no manual await set
          → kernel persists automatic reason_needed after synthesis
Turn N+1: heartbeat fires → render sub-agent tree → still running → reason persists again
Turn N+2: heartbeat fires → sub-agent done → assess tree → close / revisit / refine
Turn N+3: (if refined) → heartbeat fires → check refinement → close
```

Each heartbeat is a full reason cycle: render active branch + sub-agent/package context → assess → act. The agent is autonomously managing long-running workflows across turns. The heartbeat IS the autonomy mechanism — the system monitors its own background work, course-corrects, and reports when done.

### Deterministic package derivation from semantic trees

A fully resolved commitment chain already contains enough structure to crystallize into a reusable package. The important distinction is:

- executable flow should derive through the workflow skeleton and deterministic compilation
- semantic persistence should derive through the semantic skeleton and persistence tooling

```
Commitment chain / semantic tree on trajectory  ← runtime representation
  ↓ structural derivation
workflow skeleton / semantic skeleton          ← author-time crystallization
  ↓ deterministic compilation / persistence
action package / entity package                ← reusable manifestation
  ↓ future activation
same structural laws re-enter the ledger       ← re-instantiated manifestation
```

This is the discovery → crystallization pipeline. Reason owns executable structural derivation. Reprogramme owns semantic persistence and state continuity. They are different manifestations of the same OS-level machinery, not competing systems. New executable action structure should originate through reason → skeleton → compile. Reprogramme may update existing executable packages, but those updates must re-pass compilation before the package is treated as lawful action structure again.

### What this replaces

| Old system | cors equivalent |
|------------|----------------|
| Commitments | Passive chains — accumulate evidence across turns |
| Task delegation | reason.st activation — compose goal, chain plays out |
| Background agents | Heartbeat mechanism — automatic reason_needed monitors sub-agents |
| Judgment resolution | reason.st assess step — LLM reasons over existing chain |
| Reclassify | reason.st reorientation — compiler rejection falls back to reason |
| Reminders | Scheduled .st trigger (future — trigger: "scheduled:Xh") |

### The key principle

No extra mechanism. The trajectory IS the agent's memory. Chains ARE the reasoning units. The compiler sequences them. The governor monitors convergence. Cross-turn thresholds handle resumption. The heartbeat guarantees reintegration. reason.st is just the start codon — it activates what's already there.

### Code mechanisms

```
skills/codons/reason.st
├─ trigger: "on_vocab:reason_needed"
├─ step 1: render_reasoning_trees
│   ├─ vocab: hash_resolve_needed (observe)
│   ├─ relevance: 1.0 (fires first)
│   └─ post_diff: false (deterministic — no branching)
├─ step 2: assess_and_route
│   ├─ relevance: 0.9
│   └─ post_diff: true (LLM chooses: observe / refine / manifest / plan / heartbeat / reorient)
├─ step 3: construct_or_act
│   ├─ vocab: hash_edit_needed (if refine/plan)
│   ├─ relevance: 0.8
│   └─ post_diff: true (chain construction writes full gap config per step)
└─ step 4: post_reason_check
    ├─ vocab: hash_resolve_needed (verify coherence)
    ├─ relevance: 0.7
    └─ post_diff: true (validates await presence, layer ordering, gap axes)

skills/codons/await.st
├─ trigger: "on_vocab:await_needed"
├─ step 1: suspend_and_wait (observe, rel=1.0, post_diff=false)
├─ step 2: render_subagent_tree (observe, rel=0.9, post_diff=false)
└─ step 3: inspect_and_route (flex, rel=0.8, post_diff=true)

skills/codons/commit.st
├─ trigger: "on_vocab:commit_needed"
├─ step 1: render_commitment_tree (observe, rel=1.0, post_diff=false)
├─ step 2: reintegrate (flex, rel=0.9, post_diff=true)
└─ step 3: close_or_continue (flex, rel=0.8, post_diff=true)

skills/codons/reprogramme.st
├─ trigger: "on_vocab:reprogramme_needed"
├─ step 1: load_principles_and_registry (observe, rel=1.0, post_diff=false)
├─ step 2: compose_st (mutate, rel=0.9, post_diff=false — no branching)
└─ step 3: commit_and_register (rel=0.8, post_diff=false — fire and forget)

tools/chain_to_st.py
├─ chain_to_st(chain_hash, name, desc, trigger, refs, output_path)
│   ├─ load_chain_data(chain_hash) → chain + resolved steps
│   ├─ extract_st_steps(chain_data) → .st-compatible step list
│   │   ├─ maps step.desc → st_step.action + desc
│   │   ├─ maps gap.vocab → st_step.vocab
│   │   ├─ maps gap.scores.relevance → st_step.relevance (or position-derived)
│   │   ├─ maps gap.content_refs → st_step.content_refs (embeddable .st hashes)
│   │   └─ infers post_diff from branching structure
│   └─ writes JSON .st file (deterministic — no LLM needed)
│
└─ Discovery → crystallization pipeline:
    chain on trajectory → chain_to_st → .st file → future invocation → same gaps

step.py
├─ Trajectory.find_passive_chains(content_ref)
│   └─ active chains whose origin gap references overlap with content_ref
├─ Trajectory.append_to_passive_chain(chain_hash, step)
│   └─ appends step to existing chain, returns True if found
└─ Trajectory.extract_chains(chains_dir)
    └─ long chains (>= 8 steps) → chains/{hash}.json

compile.py
├─ Compiler.record_background_trigger(chain_id) → tracks background launches
├─ Compiler.record_await(chain_id) → tracks manual checkpoints
├─ Compiler.needs_heartbeat() → True if background trigger without manual await
├─ Compiler.resolve_current_gap(gap_hash)
│   └─ marks chain.extracted when length >= CHAIN_EXTRACT_LENGTH (8)
└─ Compiler.readmit_cross_turn(gaps, step_hash)
    └─ re-scores dangling gaps at CROSS_TURN_THRESHOLD (0.6)

loop.py
├─ _find_dangling_gaps(trajectory) → unresolved gaps from prior turns
├─ find_passive_chains() checked before creating new chain
├─ Heartbeat: after synthesis, if compiler.needs_heartbeat()
│   └─ persist reason_needed gap as dangling → next turn's resume picks it up
├─ Codon rejection: _check_protected returns on_reject vocab
│   └─ codon immutability → emit reason_needed (reorientation)
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
│   │   ├─ render salient trajectory tree + HEAD + user message
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
│   │   ├─ trajectory.render_chain(entry.chain_id, highlight_gap=gap.hash)
│   │   │   └─ inject Active Chain Tree for the currently addressed gap
│   │   ├─ HALT/None → break
│   │   ├─ REVERT → git revert last commit
│   │   ├─ Route by vocab:
│   │   │   ├─ DETERMINISTIC → kernel resolves directly
│   │   │   ├─ OBSERVATION_ONLY → resolve + inject (blob step)
│   │   │   ├─ is_observe → tool executes, LLM reasons
│   │   │   ├─ is_mutate → compose → execute → auto_commit → postcondition
│   │   │   ├─ clarify_needed → halt, gap persists
│   │   │   ├─ reason_needed → reason.st OR skeleton submission OR existing package activation
│   │   │   ├─ reprogramme_needed → PRINCIPLES.md + registry + Step Network → compose
│   │   │   └─ bridge codons → .st activation / package manifestation
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
BAD: debug_orchestrator.st references debug.st → which references hash_edit.st → ...
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
├─ step.py          ← Layer 0: step primitive, gap, chain, trajectory, render
├─ compile.py       ← Layer 1: compiler, ledger, governor, vocab, admission
├─ loop.py          ← Layer 2: turn loop, persistent LLM, hash resolution, git, tools
├─ skills/          ← .st files: entities, workflows
│   ├─ codons/      ← immutable primitive codons (protected by tree_policy)
│   │   ├─ reason.st      ← START codon: planning + reorientation + heartbeat
│   │   ├─ await.st       ← PAUSE codon: synchronization checkpoint
│   │   ├─ commit.st      ← END codon: semantic tree injection + reintegration
│   │   └─ reprogramme.st ← PERSIST codon: .st world-building (no post_diff)
│   ├─ loader.py    ← skill registry: load (walks subdirs), resolve, display names
│   └─ *.st         ← entity and workflow .st files (reprogrammable)
├─ tools/           ← tool scripts
│   ├─ chain_to_st.py    ← deterministic chain → .st extraction
│   ├─ hash_manifest.py  ← universal file I/O
│   ├─ st_builder.py     ← .st constructor from semantic intent
│   └─ ...               ← file_grep, stitch, code_exec, etc.
├─ tree_policy.json ← per-path mutation policy (codons/ immutable + on_reject)
├─ trajectory.json  ← persisted trajectory (step dicts in chronological order)
├─ chains.json      ← persisted chain index
└─ chains/          ← extracted long chains (>= 8 steps)
```

---

> The system is complete when there is nothing left to remove.
> Every mechanism is step. Every address is a hash. Every gap is a measurement.
> The kernel provides structure. The LLM provides meaning. Neither controls the other.
