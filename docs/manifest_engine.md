# manifest_engine.py

[manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py) is the package manifestation layer of the runtime. It sits between deterministic package compilation and live ledger execution.

## What It Owns

The module owns five closely related responsibilities:

- stable hashing for persisted package documents
- persistence and loading of compiled chain packages
- semantic rendering of persisted packages back into context
- rendering of the current step network
- activation of `.st` packages and compiled `.json` stepchains back into first-generation runtime gaps

This module is not the compiler and not the turn loop. It is the package surface that makes compiled or packaged structure usable by the live kernel.

## Stable Package Identity

`stable_doc_hash(doc)` computes a deterministic hash over a JSON document using sorted keys and compact separators.

That hash is then used by:

- `chain_package_path(chains_dir, ref)`
- `persist_chain_package(chains_dir, doc)`

So a compiled `stepchain.v1` document can be turned into a stable hash-addressed package under `chains/<hash>.json`.

## Package Loading

`load_chain_package(chains_dir, ref, trajectory=None)` resolves a package reference in two ways.

First, it checks `chains/<ref>.json` and loads the document if it exists.

Second, if no persisted package is found and a `Trajectory` is provided, it can synthesize a package-like render surface from an existing runtime chain in memory.

That means the manifest engine can work with both persisted compiled packages and extracted historical runtime chains.

## Package Rendering

`render_chain_package(package, ref)` renders a package into a readable semantic form for the model.

If the package is `stepchain.v1`, it renders:

- package name
- root
- trigger
- phase order
- each node’s compact structural signature
- node kind
- activation key or execution mode
- first visible transition target when present

If the package is an extracted historical chain, it renders:

- origin gap
- resolution state
- a short step listing

So the model sees structure, not just raw JSON.

The package renderer now speaks the same compact visual language family as the trajectory trees. Stepchain nodes render as:

- `node{kindspawnflowmode/s:c}`

where:

- `kind` is `o` observe, `m` mutate, `b` bridge/reason, `v` verify, `a` await, `e` embed, `c` clarify
- `spawn` is `0` none, `c` context, `a` action, `x` mixed, `e` embed
- `flow` is `+` re-openable / `post_diff:true`, `=` closed / `post_diff:false`
- `mode` is `v` runtime-vocab activation, `h` curated-step-hash activation, `i` inline
- `s:c` is `step_refs:content_refs` count from the node’s gap template

So a node like `{bx+h/0:1}` means: bridge/reason node, mixed spawn, open re-entry, hash-addressed activation, zero step refs, one content ref in its local template.

## Step Network Render

`render_step_network(chains_dir, registry, is_entity_skill, load_payload)` builds the current package ecology as one semantic surface.

It includes:

- entity `.st` files as semantic-state nodes
- executable `.st` packages, including codons
- compiled `stepchain.v1` JSON packages
- `/command` entrypoints

This is the render injected into both `reason_needed` and `reprogramme_needed` as `## Step Network`.

It is not trajectory history. It is the current package network the system can build into.

## Activation

The module exposes three activation paths.

`activate_skill_package(...)` takes a loaded `.st` package and turns its steps into the first generation of runtime gaps for the current chain context.

`activate_stepchain_package(...)` takes a compiled `stepchain.v1` package and turns its nodes into the first generation of runtime gaps for the current chain context.

`activate_chain_reference(...)` is the public dispatcher. It resolves a reference against:

- the skill registry
- the compiled chain package store

and then activates the matching package.

This is how `reason_needed` can now activate either an existing `.st` package or a compiled `.json` stepchain by hash.

## Runtime Semantics

The important architectural point is that package activation does not replace the step-gap primitive.

When a package is activated, the manifest engine does not introduce a foreign runtime object into the ledger. It turns the package into first-generation runtime gaps and a package-activation step. The package is therefore a manifestation artifact, not a replacement ontology.

That is why this module belongs between package compilation and live execution.

## Current Limits

The manifest engine is real and useful, but a few limits should be stated clearly.

Compiled `stepchain.v1` packages are activated back into runtime gaps. They are not executed by a separate package-native scheduler.

The activation mapping from stepchain node shape to runtime vocab is still simplified and partly derived from `manifestation.kernel_class` or fallback vocab rules.

The module renders the current package network structurally, but it does not yet present a full explicit package-to-package dependency graph.

Even with those limits, `manifest_engine.py` is now a real runtime boundary. It is the part of the system that makes compiled and packaged structure concretely usable by the live kernel.
