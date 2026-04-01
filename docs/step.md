# step.py

`step.py` is the runtime foundation of the kernel. Everything else assumes its object model.

## What A Step Is Here

A step is the unit of meaningful movement. In code, that means one object that carries:

- the reasoning ancestry that was followed
- the content hashes that grounded the move
- the semantic description of what happened
- any emitted gaps
- an optional commit if the move mutated the workspace

The design is still built around two hash layers and the code preserves that separation:

- `step_refs` are causal ancestry
- `content_refs` are evidence or acted-on artifacts

The two layers are never merged into one field.

## Hash Functions

The file exposes two basic hash helpers:

- `blob_hash(content)` for 12-character content hashes
- `chain_hash(step_hashes)` for chain identity

`Step.create()` includes the timestamp in its hash input, so steps are unique events rather than pure content-addressed values. `Gap.create()` hashes from description plus refs, so repeated identical gap articulations collapse more naturally.

## Epistemic

`Epistemic` is the score carrier used by the compiler and governor. It has three fields:

- `relevance`
- `confidence`
- `grounded`

The code comments in `step.py` are older and slightly misleading here. The runtime behavior in `compile.py` is the authority: relevance and confidence come from the model, while grounded is recomputed deterministically from trajectory co-occurrence when the compiler admits a gap.

## Gap

`Gap` is the kernel’s unit of unresolved discrepancy. Its important fields are:

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

Two details matter operationally:

Every gap is indexed on the trajectory whether it is active or dormant.

`turn_id` exists so the compiler can apply stricter readmission thresholds to old dangling gaps and dormant promotions.

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

Useful runtime helpers:

- `is_mutation()`
- `is_observation()`
- `has_gaps()`
- `active_gaps()`
- `dormant_gaps()`
- `all_refs()`

The post-diff surface is intentionally simple in the current runtime. The step itself does not store first-class `action`, `resolve`, `condition`, or `post_diff`. Those concepts currently live elsewhere or are inferred when extracting or loading `.st` files.

## Chain

`Chain` is how the system groups steps into a higher-order unit. A chain stores:

- its own hash
- the origin gap
- the ordered member step hashes
- a summary description
- `resolved`
- `extracted`

Chains are rehashed as new steps are appended. Long resolved chains can be written out to `chains/*.json`.

## Trajectory

`Trajectory` is the closed runtime graph. It owns:

- `steps`
- `order`
- `chains`
- `gap_index`

This gives the kernel fast lookup by hash while still preserving chronology.

Important behaviors in the current implementation:

- `append(step)` indexes both the step and all of its gaps
- `co_occurrence(hash)` drives deterministic grounding
- `dormant_gaps()` and `recurring_dormant()` make dormant memory visible
- `extract_chains()` writes long resolved chains to disk
- `find_passive_chains()` and `append_to_passive_chain()` support cross-turn accumulation against unresolved chains

That passive-chain behavior is easy to miss from the old docs, but it matters: the system is not limited to strictly local within-turn chains.

## Rendering

`Trajectory.render_recent()` is the main semantic-tree renderer the model sees.

It renders:

- chains
- origin gaps
- steps
- active, resolved, and dormant gaps
- refs with named `.st` hashes when the skill registry can resolve them
- commit hashes on mutation steps
- absolute timestamps

If there are no chains yet, the file falls back to rendering loose steps as a flat tree.

This rendering surface is important because `loop.py` reuses the same shape when resolving step hashes and gap hashes back into context.

## Persistence

The runtime persistence format is intentionally simple:

- `trajectory.json` stores ordered step dictionaries
- `chains.json` stores the chain index
- `chains/<hash>.json` stores extracted long resolved chains

There is no separate database layer. The trajectory is JSON and Git remains the external content store.

## Current Limits

The step runtime is strong, but it is not yet a fully lossless planning IR.

The main limitation is that several planning fields discussed elsewhere in the repo are not first-class on `Step` or `SkillStep`. That is why deterministic extraction and `.st` loading still involve heuristics or field loss in parts of the system.
