# step.py

[step.py](/Users/k2invested/Desktop/cors/step.py) is the runtime foundation of the kernel. Every other layer assumes its object model.

## The Primitive

A step is the unit of meaningful movement. In the current code a step records:

- the causal ancestry that was followed
- the content hashes that grounded the move
- the semantic description of what happened
- any emitted gaps
- an optional commit if the move mutated the workspace

The file preserves the two-hash-layer distinction cleanly:

- `step_refs` are reasoning ancestry
- `content_refs` are evidence or acted-on artifacts

Those layers stay separate all the way through the runtime.

## Hashing

The file exposes two basic hash helpers:

- `blob_hash(content)` for 12-character SHA-derived content hashes
- `chain_hash(step_hashes)` for chain identity

`Step.create()` includes the timestamp in the hash input, so a step is treated as an event, not a pure content-addressed object. `Gap.create()` hashes from description plus refs, so repeated identical gap articulations collapse more naturally.

## Epistemic

`Epistemic` carries the runtime score vector:

- `relevance`
- `confidence`
- `grounded`

It also exposes `as_vector()`, `distance_to()`, and `magnitude()` so the governor can reason over convergence and stagnation. One important accuracy note: the comments in `step.py` are older than the live runtime. In practice, `compile.py` is authoritative for how these values are used. Relevance and confidence come from the model. Grounded is recomputed deterministically by the compiler from trajectory structure.

## Gap

`Gap` is the kernel’s unit of unresolved discrepancy. Its main fields are:

- `hash`
- `desc`
- `content_refs`
- `step_refs`
- `origin`
- `scores`
- `vocab`
- `vocab_score`
- `resolved`
- `dormant`
- `turn_id`

Two operational details matter.

Every gap is indexed on the trajectory, even if it never enters the ledger. Dormant gaps are still part of the semantic graph.

`turn_id` exists so the compiler can apply stricter readmission rules to old dangling gaps and dormant promotions across turns.

## Step

`Step` is the central runtime record. Its fields are:

- `hash`
- `step_refs`
- `content_refs`
- `desc`
- `gaps`
- `commit`
- `t`
- `chain_id`
- `parent`

The helper surface is small but important:

- `is_mutation()`
- `is_observation()`
- `has_gaps()`
- `active_gaps()`
- `dormant_gaps()`
- `all_refs()`

The file intentionally keeps the runtime step lean. It does not store first-class `action`, `resolve`, `condition`, or package-manifestation metadata. Those concepts live in `.st` files, skeletons, compilers, or extraction tools rather than on the runtime `Step` itself.

## Chain

`Chain` groups steps into a higher-order unit. In the current implementation it stores:

- `hash`
- `origin_gap`
- `steps`
- `desc`
- `resolved`
- `extracted`

Chains are rehashed as new steps are appended. Long resolved chains can be written out to `chains/*.json`, and unresolved passive chains can keep accumulating across turns.

## Trajectory

`Trajectory` is the closed runtime graph. It owns:

- `steps`
- `order`
- `chains`
- `gap_index`

This gives the kernel direct lookup by hash while preserving chronology.

Important behaviors in the current implementation:

- `append(step)` indexes both the step and all emitted gaps
- `co_occurrence(hash)` supports deterministic grounded scoring
- `dormant_gaps()` and `recurring_dormant()` expose dormant memory
- `extract_chains()` writes long resolved chains to disk
- `find_passive_chains()` and `append_to_passive_chain()` let unresolved chains continue across turns

That passive-chain behavior matters. The runtime is not limited to purely local within-turn chains.

## Rendering

`Trajectory.render_recent()` is the main salient trajectory renderer injected into the session. It renders chains, origin gaps, steps, gaps, refs, commits, and timestamps in a semantic-tree style.

The render now carries a compact tree language rather than spelling every structural dimension out in prose:

- `step{kindflowN}` means:
  `kind=o` observe or `m` mutate,
  `flow=+` open active child gaps, `~` dormant-only children, `=` closed,
  and `N` is the number of active child gaps when present.
- `gap{statusclassrcg/s:c}` means:
  `status=?` active, `=` resolved, `~` dormant;
  `class=o` observe, `m` mutate, `b` bridge, `c` clarify, `_` unknown;
  `rcg` are relevance/confidence/grounded score bands compressed to `0-9`;
  `s:c` are `step_refs:content_refs` counts.

So a line like `{?m781/1:1} gap:...` means “active mutate-class gap, relevance band 7, confidence band 8, grounded band 1, one step ref, one content ref”.

`Trajectory.render_chain()` is now the active-branch renderer. Given a `chain_id`, it renders the chain the current ledger entry belongs to and can mark the currently addressed gap with `[focus]`. This is what `loop.py` now injects as `## Active Chain Tree` while the system is working a gap.

These renders matter because they are the readable semantic surface the model actually reasons over. The trajectory is the store; the renders are the live working view.

## Persistence

The persistence layer remains intentionally simple:

- `trajectory.json` stores ordered step dictionaries
- `chains.json` stores the chain index
- `chains/<hash>.json` stores extracted long resolved chains

There is no separate database. The trajectory lives as JSON. Git remains the external content store for blobs, trees, and commits.

## Limits

`step.py` is a strong runtime graph, but it is not a full lossless planning IR. Richer planning and manifestation fields still live outside `Step` and `Gap`, which is why skeleton compilation, `.st` loading, and chain extraction still involve separate schemas or some amount of heuristic reconstruction.
