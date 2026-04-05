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
│   ├─ .turn_id        — which turn created this gap (for cross-turn threshold)
│   ├─ .carry_forward  — explicit cross-turn persistence marker
│   └─ .route_mode     — deterministic routing hint (for example entity_editor; action coercion remains a low-level frame, not the public ownership law)
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
│   ├─ .assessment     — validator/projection lines attached to realized or rogue steps
│   ├─ .rogue          — failure marker for reverted/rejected manifestations
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
│       └─ re-admits only explicitly carried gaps as fresh lawful roots
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
├─ _find_dangling_gaps(trajectory) → unresolved carry_forward gaps only (clarify excluded)
└─ _persist_forced_synth_frontier(...) → clones unresolved frontier into one carry-forward step
```

---

## §3. The Step Manifestation Engine

The kernel is a step manifestation engine. A gap is the universal primitive, but a gap is never just a sentence. A gap is a structural seed that can manifest as context injection, ledger dispersal, mutation, reintegration, or persistence depending on its configuration.

The important separation is not merely WHAT versus HOW. It is:

- **Gap** = the measured discrepancy
- **Manifestation config** = the structural law of how that discrepancy should unfold
- **Activation identity** = which exact curated step package, if any, should fire

Primitive kernel vocab still matters, but only as the stable execution algebra for the kernel's native mechanisms. For curated workflows, exact activation can be carried by step-file hash while priority, grouping, routing, and analytics remain derivable from gap structure itself. The hash does not need to carry semantic meaning. It only needs to identify the exact package to manifest.

The current runtime makes one further distinction explicit:

- **Name/vocab activation** uses the block's canonical public contract
- **Hash embedding** preserves identity but may specialize manifestation only through explicit embedding configuration

So the same committed block can have one public/default activation surface and many lawful contextualized embeddings without losing identity.

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

### Current ownership split

The runtime is simpler than the earlier structural-authoring design.

- **`reason_needed`** is the stateful judgment and activation primitive. It decides what kind of work should happen next: direct observation, direct mutation, `tool_needed`, `reprogramme_needed`, clarification, or later `chain_needed`.
- **`tool_needed`** is the tool-authoring primitive. It owns `tools/*.py` creation under tree policy and writes scripts that already express their own runtime contract metadata.
- **`reprogramme_needed`** is the semantic persistence primitive. It updates entity/admin state after judgment has already established that persistence is warranted.

So the live split is:

- `reason_needed` manages activation and structural judgment
- `tool_needed` manages new tool creation
- `reprogramme_needed` manages semantic state persistence

Executable chain construction is intentionally not the live job of `reason_needed` anymore. That is a future dedicated layer.

### Tier 1: Observe (external &, priority 20)

The kernel resolves data. The LLM receives it. No mutation. These are the system's sensory organs — they bring information into the context window without changing the world.

| Vocab | Manifestation | Post-diff |
|-------|--------------|-----------|
| `hash_resolve_needed` | Kernel resolves hash → step/gap/skill/.st/git blob. If hash is a .st entity, full entity data injected. | Deterministic — blob step, no branching |
| `pattern_needed` | Kernel runs file_grep → results injected | LLM reasons over results, may branch |
| `email_needed` | Kernel checks email → results injected | LLM reasons over results, may branch |
| `external_context` | LLM surfaces from current context — no tool | Blob step, no branching |
| `clarify_needed` | Halts iteration. Current-turn clarify gaps merge into one clarification frontier step and one user-facing question packet. | No post-diff — the turn ends |

### Tier 2: Mutate (external &mut, priority 40)

The LLM composes. The kernel executes. Auto-commit. Post-observation fires. These are the system's effectors — they change the world and then immediately verify the result.

| Vocab | Manifestation | Compose mode | Post-observe |
|-------|--------------|-------------|--------------|
| `hash_edit_needed` | hash_manifest.py — unified file mutation through the hash primitive. Routes by file type internally. | LLM composes JSON params | Derived from commit/artifact/tool contract |
| `stitch_needed` | stitch_generate.py — prompt → HTML + Tailwind CSS | LLM composes UI prompt | `ui_output/` (screenshot blob) |
| `content_needed` | hash_manifest.py — write new file through hash primitive | LLM composes content | Commit tree |
| `script_edit_needed` | hash_manifest.py — edit existing file through hash primitive | LLM composes edit intent | Commit tree |
| `tool_needed` | tool_builder.py — scaffold a validated public tool script with explicit runtime contract metadata | LLM composes tool spec | Commit tree |
| `command_needed` | code_exec.py — execute shell command. Output and logs become post-observe surface. | LLM composes command | `bot.log` or returned artifacts |
| `message_needed` | email_send.py — send email/message | LLM composes message | Commit tree |
| `json_patch_needed` | json_patch.py — surgical JSON mutation | LLM composes patch | Commit tree |
| `git_revert_needed` | git_ops.py — revert/checkout | LLM composes git command | Commit tree |

All mutations follow the same rhythm: **compose → execute → auto-commit → post-observe**. Mutations do not directly explode the ledger. The follow-on observation is where the system verifies the change and decides what new gaps, if any, deserve admission.

### Tier 3: Bridge primitives (internal, priority 90-99)

Four bridge primitives govern the reasoning lifecycle. Three are backed by protected codon packages in `skills/codons/`. `reason_needed` is the live bridge primitive for judgment and activation, not a mutable authored workflow package.

| Vocab | Codon | Priority | Manifestation |
|-------|-------|----------|--------------|
| `reason_needed` | **START** | 90 | Stateful judgment and activation. Uses semantic trees, entity space, recent trajectory, and workspace context to decide the next concrete move. |
| `await_needed` | **PAUSE** | 95 | Synchronization checkpoint. Suspends parent chain until referenced sub-agent completes. Renders sub-agent's full semantic tree → parent inspects → accept/correct/reactivate. If turn ends before sub-agent finishes, persists as dangling gap — heartbeat picks up next turn. |
| `commit_needed` | **END** | 98 | Reintegration and closure for commitment-like branches. |
| `reprogramme_needed` | **PERSIST** | 99 | Semantic state update for entity/admin packages once judgment has already decided to persist. |

**Codon priority ordering:** reason (90) → await (95) → commit (98) → reprogramme (99). Within the bridge tier, planning fires first, checkpoints fire after inline work, reintegration fires after commitment gaps resolve, and persistence fires last.

Mid-turn commitment activation follows the compiler laws exactly: reason_needed fires → commitment gaps disperse onto ledger → commit_needed sits at bottom → commitment resolves depth-first → commit reintegrates → main chain resumes. The compiler doesn't know it's processing a commitment. It just sees gaps at various depths. Same laws, same stack.

**Law 9 guarantee:** Background triggers (reprogramme_needed) always close the loop. If the main agent sets a manual `await_needed`, the parent chain suspends and resumes when the sub-agent finishes. If no manual await is set, an automatic `reason_needed` heartbeat persists after synthesis — next turn, the agent inspects the sub-agent's semantic tree and either closes, revisits, or refines. The loop is always closed.

### Tier 4: `.st` Resolution (internal &, no dedicated entity vocab)

Entity-style and action-style `.st` files do not require separate top-level vocab names just to exist. They are still addressable through hash resolution. But what they MANIFEST into is structural, not textual.

When a `.st` hash is resolved, the system should treat it as a step package, not as dead data. Its manifestation mode is derivable from its structure:

| `.st` structural shape | Manifestation | What happens |
|------------------------|---------------|-------------|
| Pure entity semantics | Context injection | Semantic state is injected: identity, preferences, scope, constraints, domain knowledge |
| Action workflow | Read-only package resolution | Structure is surfaced as a package/workflow description. Activation still comes from vocab, not from hash resolution itself. |
| Hybrid | Mixed manifestation | Semantic context injects first, action structure remains inspectable until explicitly activated |

So the principle is not “the system reads `.st` files.” The principle is “the system resolves step packages, and their structure determines manifestation.”

### Auto-routes (policy-driven)

Mutations targeting protected paths are intercepted before execution — the tree policy acts as a membrane around sensitive regions of the codebase:

| Target matches | Reroutes to | Mechanism |
|---------------|-------------|-----------|
| `skills/admin.st` | `reprogramme_needed` (`entity_editor`) | Canonical admin primitive — semantic persistence only |
| `skills/entities/*` or entity hash | `reprogramme_needed` (`entity_editor`) | Entity packages persist through semantic entity editor |
| `skills/actions/*` or existing action hash | `reason_needed` | Action/workflow activation and structural judgment stay under reason first |
| `tools/*` | `tool_needed` | Tool-tree mutation is diverted into the tool writer path |
| `ui_output/` or screenshots | `stitch_needed` | Generated assets regenerated, not manually edited |
| Immutable paths (codons, system code, stores, logs) | Auto-revert + warning | Protected path violation |

All driven by `tree_policy.json` — configurable, no hardcoded paths.

### Universal post-observation

Every successful mutation produces follow-on observation. The exact surface is derived from the runtime contract:

- explicit `post_observe` on the public vocab/tool when needed
- returned or declared artifact paths when the tool produces artifacts
- otherwise the realized commit or changed workspace surface

This is the system verifying its own work. No blind mutations.

### Code mechanisms

```
vocab_registry.py
├─ VOCABS
│   ├─ observe  → {hash_resolve_needed, pattern_needed, email_needed, external_context, clarify_needed}
│   ├─ mutate   → {hash_edit_needed, stitch_needed, content_needed, script_edit_needed, tool_needed, command_needed, message_needed, json_patch_needed, git_revert_needed}
│   └─ bridge   → {reason_needed, await_needed, commit_needed, reprogramme_needed}
├─ DETERMINISTIC_VOCAB = {hash_resolve_needed}
├─ OBSERVATION_ONLY_VOCAB = {external_context}
└─ tool bindings and post_observe overrides live on the public vocab surface

tools/tool_registry.py
├─ public tool inventory only
├─ includes the two hash primitives as public tools
└─ excludes the internal handlers behind them

tools/hash_registry.py
├─ internal file-type routing for hash_resolve/hash_manifest
├─ resolve handlers
└─ manifest handlers

tools/tool_contract.py
├─ reads tool metadata directly from each public script
├─ TOOL_DESC
├─ TOOL_MODE
├─ TOOL_SCOPE
├─ TOOL_POST_OBSERVE
└─ optional artifact declarations

vocab_registry.py
└─ validate_tree_policy_targets(policy)
    └─ prevents stale or unknown reroute targets

compile.py
├─ imports canonical vocab families from vocab_registry.py
├─ is_observe(vocab) / is_mutate(vocab) / is_bridge(vocab)
└─ vocab_priority(vocab)
    ├─ observe → 20
    ├─ mutate  → 40
    ├─ unknown → 50
    ├─ reason_needed → 90
    ├─ await_needed → 95
    ├─ commit_needed → 98
    └─ reprogramme_needed → 99

loop.py
├─ PRE_DIFF_SYSTEM
│   ├─ reason before clarify is explicit bridge law when available context can narrow ambiguity
│   ├─ trigger vocab is derived automatically from loaded on_vocab: skills
│   └─ final public on_vocab trigger belongs to the highest-order completed workflow
├─ dynamic bridge injection
│   ├─ Available Trigger Vocab
│   └─ Canonical Trigger Owners
├─ resolve_hash(ref, trajectory)
│   ├─ entity/admin/chain-spec package hash → entity-style deterministic injection
│   ├─ action package hash → read-only package render
│   ├─ trajectory step hash → semantic tree branch render
│   ├─ trajectory gap hash → gap tree render
│   └─ git object → git show (blob/tree/commit)
├─ tree policy
│   ├─ skills/admin.st → reprogramme_needed + entity_editor
│   ├─ skills/entities/* → reprogramme_needed + entity_editor
│   ├─ skills/actions/* → reason_needed
│   ├─ skills/codons/* → immutable + on_reject: reason_needed
│   ├─ tools/* → tool_needed
│   └─ ui_output/* / immutable code / logs / stores → policy enforcement
├─ auto_commit(message)
│   ├─ git add -A → commit
│   ├─ protected-surface check
│   └─ hand back the realized commit/artifact surface for post-observation
├─ _find_dangling_gaps(trajectory)
│   └─ only explicit carry_forward gaps resume; clarify never auto-carries
└─ _persist_forced_synth_frontier(...)
    └─ unresolved forced-synth frontier cloned forward as fresh carryable gaps

execution_engine.py
├─ execute_iteration(...)
│   ├─ merges current-turn clarify gaps into one frontier step
│   ├─ applies deterministic route_mode hints before execution
│   ├─ keeps action-tree creation and repair under reason_needed
│   ├─ diverts tool-tree writes to tool_needed
│   ├─ limits reprogramme_needed to entity/admin persistence
│   └─ emits rogue steps with reason_needed diagnosis when execution fails
├─ _collect_clarify_frontier(...)
│   └─ current-turn bounded, deduped clarify frontier
├─ tool_needed branch
│   ├─ injects Public Tool Registry
│   ├─ uses tool_builder scaffold
│   └─ validates script contract metadata
└─ _reprogramme_mode_for_source(path)
    └─ derives deterministic semantic persistence frame for entity-like targets

tree_policy.json
├─ "skills/admin.st"  → {on_mutate: "reprogramme_needed", reprogramme_mode: "entity_editor"}
├─ "skills/entities/" → {on_mutate: "reprogramme_needed", reprogramme_mode: "entity_editor"}
├─ "skills/actions/"  → {on_mutate: "reason_needed", reprogramme_mode: "action_editor"}
├─ "skills/codons/"   → {immutable: true, on_reject: "reason_needed"}
├─ "tools/"           → {on_mutate: "tool_needed"}
├─ "ui_output/"       → {on_mutate: "stitch_needed"}
├─ "logs/"            → {immutable: true}
└─ core runtime files → {immutable: true}

tools/st_builder.py
├─ validates `.st` structure before persistence
├─ creates or updates entity/action packages when explicitly asked
└─ actualizes lawful semantic action/entity writes
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
│   ├─ injects current step network + registry + protected editing law
│   ├─ preserves admin as canonical root entity primitive
│   └─ routes through deterministic entity_editor mode for entity-like persistence
│
├─ _reprogramme_pass() → automatic pre-synthesis safety net
│   └─ reviews turn for knowledge updates, fires if needed
│
└─ Entity rendering
    ├─ _render_entity(skill) → full entity/spec `.st` data formatted for injection
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
│   ├─ .artifact_kind → entity / action / hybrid / codon
│   └─ .hash → content hash of .st file
│
└─ load_all(skills_dir) → SkillRegistry
    ├─ loads skills/admin.st as canonical root entity
    ├─ loads skills/entities/* as entity/spec injection packages
    ├─ loads skills/actions/* as executable packages
    └─ loads skills/codons/* as protected primitive codons

tools/st_builder.py
├─ Builds valid `.st` from semantic intent
├─ Validates entity/action/hybrid persistence frame
├─ Entity semantics require deterministic context-injection steps
├─ entity_editor
│   ├─ preserves pure entity shape
│   ├─ strips root/phases/closure
│   └─ writes to skills/entities/ (or skills/admin.st when editing admin)
├─ action/entity structure validation
│   ├─ persistence frame checks
│   ├─ public-trigger ownership checks
│   └─ explicit structural contract checks
└─ Forwards semantic fields (identity, constraints, scope, refs, preferences, etc.)
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

## §7. Post-Observation and Re-Entry

The live kernel is simpler than the earlier `post_diff`-centric design.

The dominant runtime rule is:

- observations may surface next gaps
- mutations do not directly expand the ledger
- successful mutations trigger post-observation

So the primary re-entry primitive is no longer “any step with `post_diff: true`”. It is the observe/mutate rhythm itself.

### Current law

- **observe**
  - inspect context
  - resolve data
  - surface relevant next gaps
- **mutate**
  - act on the world
  - auto-commit when applicable
  - produce a post-observation surface
  - let later observation decide whether any next work is warranted

This keeps mutation from directly exploding the ledger while still allowing iterative multi-step progress.

### Where `post_diff` still matters

`post_diff` still exists in authored package structure and validators, but it is no longer the dominant kernel law. It remains package metadata about where a designed workflow intends to reopen or stay linear. The live runtime, however, is governed primarily by:

- observe vs mutate
- automatic post-observation after mutation
- compiler sequencing laws

So `post_diff` is now secondary to the simpler O-M-O rhythm.

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

**8. Post-observation** — Every successful mutation auto-commits and yields a follow-on observation surface. No mutation without verification. This is Law 3 (OMO) enforced structurally — even if an authored package omits an explicit verification step, the runtime still produces one.

**9. Loop always closes** — Every background trigger must eventually reintegrate with the parent trajectory. Either the flow-builder agent sets a manual `await_needed` checkpoint (synchronous — parent chain suspends, resumes when sub-agent finishes) or the kernel inserts an automatic `reason_needed` heartbeat after synthesis (asynchronous — next turn, agent inspects sub-agent's semantic tree). The heartbeat is recursive: if inspection triggers further background work, another heartbeat persists. The loop closes when all background chains are resolved. This is not a constraint on the flow-builder — it is a guarantee by the kernel.

### Workflow validation

Because the compiler is part of the manifestation engine, every authored workflow/package structure should be statically checkable before execution or activation.

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

The compiler sees: observe gap (priority 20), then unknown gap (50), then two mutate gaps (40). After priority sorting, the observe fires first. The null-vocab gap lets the LLM reason freely. Then mutations fire with automatic post-observation between them (OMO preserved).

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
│   ├─ mutation tracking → successful mutation requires follow-on observation (Law 8)
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
├─ Universal post-observation (Law 8)
│   └─ after auto_commit: observe the realized commit or declared artifact surface
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

### `reason_needed`: activation and judgment

`reason_needed` is now the activation primitive, not the live workflow-authoring controller.

Its roles are:

**Role 1: Planning and judgment** — For complex tasks, the main agent emits `reason_needed` to reduce ambiguity and decide the next concrete move. It reasons over semantic trees, entity space, workspace state, and recent trajectory, then chooses whether the next step should be observation, mutation, `tool_needed`, `reprogramme_needed`, clarification, or later `chain_needed`.

**Role 2: Reorientation checkpoint** — When tree policy, compiler law, or protected-surface rules reject the current move, the fallback is still `reason_needed`. The agent re-renders current context and chooses a safer next path.

**Role 3: Heartbeat trigger** — Background work can still reintegrate through persisted `reason_needed` frontiers after synthesis when no explicit await has closed the loop.

### The activation cycle

```
reason_needed surfaces
  → observe current trajectory, active chain, semantic trees, and workspace context
  → assess what kind of move is actually needed
  → choose one of:
      - direct observation gap
      - direct mutation gap
      - tool_needed
      - reprogramme_needed
      - clarify_needed
      - no gap
  → later runtime branches handle the chosen path
```

### The end codon: commit.st

`commit_needed` is the reintegration mechanism. It is NOT directly classifiable — the LLM should never emit it as a gap. It sits behind commitment-like child work and fires last, reintegrating the full commitment tree into the main agent's context before closure or continuation.

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

### Deterministic package derivation

The system still supports crystallizing reusable packages, but the live ownership is now cleaner:

- tool authoring belongs to `tool_needed`
- entity/admin persistence belongs to `reprogramme_needed`
- action/workflow activation and judgment belong to `reason_needed`
- dedicated chain construction is future-facing, not the live `reason_needed` loop

### What this replaces

| Old system | cors equivalent |
|------------|----------------|
| Commitments | Passive chains — accumulate evidence across turns |
| Task delegation | `reason_needed` activation — choose the correct runtime branch |
| Background agents | Heartbeat mechanism — automatic reason_needed monitors sub-agents |
| Judgment resolution | `reason_needed` — LLM reasons over existing runtime state |
| Reclassify | `reason_needed` reorientation — compiler rejection falls back to reason |
| Reminders | Scheduled .st trigger (future — trigger: "scheduled:Xh") |

### The key principle

No extra mechanism. The trajectory is still the memory substrate. Chains are still the runtime grouping unit. The compiler sequences them. The governor monitors convergence. Cross-turn thresholds handle resumption. The heartbeat guarantees reintegration. `reason_needed` activates what should happen next; it no longer tries to own every lower-level construction mechanism itself.

### Code mechanisms

```
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
├─ step 1: load laws, registry, route frame (observe, rel=1.0, post_diff=false)
├─ step 2: compose semantic frame in deterministic route_mode (rel=0.9, post_diff=false)
└─ step 3: persist + auto-commit + post-observe assessment (rel=0.8, post_diff=false)

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
    └─ re-scores only explicit carry-forward gaps at CROSS_TURN_THRESHOLD (0.6)

execution_engine.py
├─ reason_needed execution
│   ├─ injects live runtime context
│   ├─ performs plain judgment and routing
│   └─ chooses the next concrete step type
├─ tool_needed execution
│   ├─ injects Public Tool Registry
│   ├─ uses tool_builder scaffold
│   └─ validates per-script runtime contract metadata
├─ reprogramme_needed execution
│   ├─ entity_editor → semantic entity persistence
│   ├─ action origination/update is not the owner path
│   └─ successful write → assessment-bearing post-observation step before synth
└─ clarify frontier
    └─ current-turn clarify gaps merge into one canonical clarification step hash

loop.py
├─ _find_dangling_gaps(trajectory) → only non-clarify carry_forward gaps resume
├─ find_passive_chains() checked before creating new chain
├─ Heartbeat: after synthesis, if compiler.needs_heartbeat()
│   └─ persist reason_needed gap as carryable frontier → next turn's resume picks it up
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
│   │   └─ _find_dangling_gaps(trajectory) → surface only explicit carry-forward frontier gaps
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
│   │   ├─ REVERT → skip divergent branch / emit rogue diagnostics
│   │   ├─ Route by vocab:
│   │   │   ├─ DETERMINISTIC → kernel resolves directly
│   │   │   ├─ OBSERVATION_ONLY → resolve + inject (blob step)
│   │   │   ├─ is_observe → tool executes, LLM reasons
│   │   │   ├─ is_mutate → compose → execute → auto_commit → post-observe
│   │   │   ├─ clarify_needed → merge current-turn clarify frontier → halt
│   │   │   ├─ reason_needed → judgment / activation / reroute
│   │   │   ├─ reprogramme_needed → route_mode frame + registry + Step Network → compose
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
├─ vocab_registry.TOOL_MAP → vocab → {tool: path, post_observe: target}
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
├─ Reprogramme prompt: reuse existing packages, preserve tree class, route by target tree
├─ Entity registry injection → reason/reprogramme see entity/spec packages by hash
├─ Command registry injection → executable packages remain discoverable separately
└─ `.st` package refs resolve as entity injection or action read based on source tree

skills/
├─ admin.st → canonical operator primitive at root
├─ entities/* → context/spec injection packages
├─ actions/* → executable workflow packages
└─ codons/* → immutable bridge primitives and chain construction spec
```

---

## File Map

```
cors/
├─ step.py          ← Layer 0: step primitive, gap, chain, trajectory, render
├─ compile.py       ← Layer 1: compiler, ledger, governor, vocab, admission
├─ execution_engine.py ← Layer 2a: per-gap execution, clarify frontier, route_mode dispatch
├─ loop.py          ← Layer 2b: turn loop, persistent LLM, hash resolution, git, policy
├─ manifest_engine.py ← manifestation helpers for `.st` package inspection / activation
├─ skills/          ← structured semantic trees
│   ├─ codons/      ← protected codons and immutable specs
│   │   ├─ await.st       ← PAUSE codon: synchronization checkpoint
│   │   ├─ commit.st      ← END codon: semantic tree injection + reintegration
│   │   ├─ reprogramme.st ← PERSIST codon: semantic persistence
│   │   └─ commitment_chain_construction_spec.st ← dormant future chain-building spec
│   ├─ actions/     ← executable workflows / mutable action packages
│   ├─ entities/    ← semantic entities and passive spec packages
│   ├─ loader.py    ← skill registry: load (walks subdirs), resolve, display names
│   └─ admin.st     ← only root skill, preserved as canonical operator entity
├─ tools/           ← tool scripts
│   ├─ hash_resolve.py   ← file observation primitive
│   ├─ hash_manifest.py  ← file mutation primitive
│   ├─ tool_registry.py  ← public tool registry
│   ├─ hash_registry.py  ← internal hash handler routing
│   ├─ tool_builder.py   ← tool_needed scaffold writer
│   └─ ...               ← external/data/media/domain tools
├─ tree_policy.json ← per-path mutation policy (codons/ immutable + on_reject)
├─ trajectory.json  ← persisted trajectory (step dicts in chronological order)
├─ chains.json      ← persisted chain index
└─ chains/          ← extracted long chains (>= 8 steps)
```

---

> The system is complete when there is nothing left to remove.
> Every mechanism is step. Every address is a hash. Every gap is a measurement.
> The kernel provides structure. The LLM provides meaning. Neither controls the other.
