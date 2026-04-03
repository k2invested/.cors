# step.py

[step.py](/Users/k2invested/Desktop/cors/step.py) is the runtime object model. Everything else in the kernel assumes its hash graph.

## Core Objects

The file defines:

- `Epistemic`
- `Gap`
- `Step`
- `Chain`
- `Trajectory`

It also owns the main semantic renderers the loop injects into the model.

## Gap

`Gap` is the unresolved frontier primitive.

Current operational fields:

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
- `carry_forward`
- `route_mode`

Two newer fields matter:

- `carry_forward`
  - explicit cross-turn persistence marker
- `route_mode`
  - deterministic execution hint such as `entity_editor`; low-level action-editor coercion still exists, but action-tree ownership now belongs to `reason_needed`

## Step

`Step` is the persistent runtime event.

Current fields include:

- `hash`
- `step_refs`
- `content_refs`
- `desc`
- `gaps`
- `commit`
- `chain_id`
- `parent`
- `assessment`
- rogue metadata such as:
  - `rogue`
  - `rogue_kind`
  - `failure_source`
  - `failure_detail`

That means a step can now represent:

- ordinary observation
- mutation
- clarify frontier
- postcondition assessment
- rogue failure with diagnosis handoff

## Hash Layers

The separation still holds:

- `step_refs` = causal lineage
- `content_refs` = resolved evidence or package/data refs

The current architecture depends on that distinction more than ever because `.st` package hashes now live in `content_refs`, while prior runtime reasoning continues to live in `step_refs`.

## Chain

`Chain` groups steps under one origin gap.

Current fields:

- `hash`
- `origin_gap`
- `steps`
- `desc`
- `resolved`
- `extracted`

Chains are still runtime units rather than a replacement ontology. They can also persist unresolved across turns as passive chains.

## Trajectory

`Trajectory` owns:

- `steps`
- `order`
- `chains`
- `gap_index`

Important behaviors:

- `append(step)` indexes all gaps, including dormant ones
- `resolve(...)` and `resolve_gap(...)` provide hash lookup
- `find_passive_chains(...)` and `append_to_passive_chain(...)` support cross-turn structural continuation
- `extract_chains(...)` writes long resolved chains out to disk

## Clarify And Carry

Clarify and carry-forward are now reflected directly in the runtime graph rather than only in loop logic.

Examples:

- a merged clarification prompt is one explicit `Step`
- a forced-synth carry-forward packet is one explicit `Step`

## Contract Visibility

The live chain render now exposes compact contract tags when a runtime step is backed by a canonical foundation contract.

Examples:

- `gap=hash_edit_needed`
- `embed=named_default`
- `omo=observe->mutate`

The semantic-tree render also exposes a fuller `effective_contract` payload. This keeps default/public activation and hash-embedded specialization visible in the same runtime surface the model reasons from.
- future turns can reason over those steps by hash

## Rendering

The render surface is still compact tree language rather than raw JSON.

The main renderers are:

- `Trajectory.render_recent(...)`
- `Trajectory.render_chain(...)`

Those renders now need to make newer step types legible:

- ordinary steps
- rogue steps
- assessment-bearing postcondition steps
- clarify frontier steps

So `step.py` is no longer just the base object model. It is also the readability layer that lets the model inspect its own runtime structure.
