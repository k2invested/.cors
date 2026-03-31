# step.py — The Step Primitive

**Layer**: 0 (no dependencies)
**Principles**: §1, §2, §4, §5, §11, §12, §13

## Purpose

Defines the step primitive and all types that compose it. The foundation — every other module builds on these types. A step is meaningful movement: a two-phase transition (pre-diff + post-diff) with two hash layers (step refs for reasoning, content refs for data).

## Types

### Epistemic

Epistemic signal vector. Three dimensions derived from chain structure by the governor.

| Field | Type | Meaning |
|-------|------|---------|
| relevance | float | LLM-assessed: how much does resolving this advance the trajectory toward the shared goal? Primary admission driver. |
| confidence | float | LLM-assessed: how safe and trustworthy is this to act on? |
| grounded | float | Kernel-computed: deterministic hash co-occurrence frequency on the trajectory. NOT LLM-assessed — overwritten by compiler at admission. |

Methods:
- `as_vector() → [float, float, float]` — for governor linear algebra
- `distance_to(other) → float` — euclidean distance between two epistemic states
- `magnitude() → float` — vector magnitude

### Gap

A gap articulation — the LLM's assessment of what needs to happen. Every gap is hashed (content-addressed from desc + refs) and stored on the trajectory whether acted on or not.

| Field | Type | Meaning |
|-------|------|---------|
| hash | str | Content-addressed 12-char hex hash |
| desc | str | Semantic articulation of the gap |
| content_refs | list[str] | **Layer 2**: blobs/trees/commits referenced as evidence |
| step_refs | list[str] | **Layer 1**: reasoning steps in the causal chain |
| origin | str? | Step hash that surfaced this gap |
| scores | Epistemic | Epistemic signal for the governor |
| vocab | str? | Mapped precondition (scan_needed, script_edit_needed, etc.) |
| vocab_score | float | Confidence in the vocab mapping |
| resolved | bool | True when the chain closed this gap |
| dormant | bool | True if below threshold — stored but not acted on |

Factory: `Gap.create(desc, content_refs=[], step_refs=[]) → Gap`

### Step

The atom. Every state transition produces one. Two-phase: pre-diff (what was observed) + post-diff (what was concluded).

| Field | Type | Meaning |
|-------|------|---------|
| hash | str | Content-addressed from desc + timestamp |
| step_refs | list[str] | **Layer 1**: step hashes the LLM followed |
| content_refs | list[str] | **Layer 2**: blobs/trees/commits referenced |
| desc | str | Semantic articulation of the causal chain |
| gaps | list[Gap] | One per causal chain — with vocab + scores |
| commit | str? | Git commit SHA if mutation occurred |
| t | float | Timestamp |
| chain_id | str? | Which reasoning chain this step belongs to |
| parent | str? | Step hash that spawned this step (child gap) |

Factory: `Step.create(desc, step_refs=[], content_refs=[], gaps=[], commit=None) → Step`

Key methods:
- `is_mutation() → bool` — has commit
- `is_observation() → bool` — no commit
- `has_gaps() → bool` — has active (non-resolved, non-dormant) gaps
- `active_gaps() → list[Gap]`
- `dormant_gaps() → list[Gap]`
- `all_refs() → list[str]` — all hashes from both layers + gap refs

### Chain

A reasoning chain — sequence of steps originating from one gap. Has its own hash. Chains that branch are reasoning steps at a higher level.

| Field | Type | Meaning |
|-------|------|---------|
| hash | str | Derived from member step hashes |
| origin_gap | str | Gap hash that started this chain |
| steps | list[str] | Step hashes in execution order |
| desc | str | Summary (set when chain completes) |
| resolved | bool | All gaps resolved |
| extracted | bool | Saved to chains/*.json |

Factory: `Chain.create(origin_gap, first_step) → Chain`

### Trajectory

The closed hash graph. Steps go on it. Content (blobs/commits) is referenced but never stored here.

| Structure | Type | Purpose |
|-----------|------|---------|
| steps | dict[str, Step] | Hash → Step lookup (O(1)) |
| order | list[str] | Chronological step hash sequence |
| chains | dict[str, Chain] | Chain hash → Chain |
| gap_index | dict[str, Gap] | All gaps including dormant |

Key methods:
- `append(step)` — add step, index its gaps
- `resolve(hash) → Step?` — lookup by hash
- `resolve_gap(hash) → Gap?` — lookup gap by hash
- `recent(n) → list[Step]` — last N steps
- `recent_chains(n) → list[Chain]` — last N chains
- `co_occurrence(hash) → int` — how many steps reference this hash
- `is_commit(hash) → bool` — is this a mutation step
- `dormant_gaps() → list[Gap]` — all dormant gaps
- `recurring_dormant(min_count) → list[str]` — dormant descriptions appearing N+ times
- `render_recent(n, registry=None) → str` — Render trajectory as traversable hash tree with named skill references (e.g. kenny:72b1d5ffc964)
- `_tag_ref(ref, layer, registry) → str` — Tag hash with type prefix, resolves named entities from skill registry
- `_render_refs(step_refs, content_refs, registry) → str` — Render refs list with named tags
- `_render_steps_as_tree(steps, registry) → str` — Render loose steps as flat hash tree
- `save(path)` / `load(path)` — JSON persistence

## Hash Functions

| Function | Input | Output | Purpose |
|----------|-------|--------|---------|
| `blob_hash(content)` | str | 12-char hex | Content-addressed hash (SHA-256) |
| `chain_hash(step_hashes)` | list[str] | 12-char hex | Hash a sequence of step hashes |

## Invariants

- Steps are immutable after creation
- Gaps are immutable after creation
- Two hash layers never mixed on the same field
- Every gap stored in gap_index regardless of status
- Trajectory only appends, never overwrites
- Same content always produces the same hash
