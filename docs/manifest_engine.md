# manifest_engine.py

[manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py) is the package manifestation layer. It renders and activates saved package structure without replacing the step-gap runtime primitive.

## What It Owns

- stable hashing for persisted chain packages
- persistence/loading of compiled `stepchain.v1`
- readable package rendering
- step-network rendering
- activation of `.st` packages and saved chain packages back into first-generation runtime gaps

## Stable Package Identity

The main identity helpers are:

- `stable_doc_hash(doc)`
- `chain_package_path(...)`
- `persist_chain_package(...)`

Compiled chain packages are persisted under `chains/<hash>.json`.

## Package Rendering

The package renderer is not raw JSON dump by default. It renders structural shape:

- package name
- root
- trigger
- phase order
- compact node signatures

That keeps package context legible to the model in the same general visual language family as trajectory trees.

## Step Network

`render_step_network(...)` is now more important than older docs suggested because the skill tree is explicitly split.

The step network includes:

- [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st)
- entity packages from `skills/entities/`
- action packages from `skills/actions/`
- codons from `skills/codons/`
- saved compiled `stepchain.v1` packages
- `/command` entrypoints

This is the package ecology injected into `reason_needed` and `reprogramme_needed`.

For action authoring, the manifest layer now also supports a hash-native Action Foundations view:

- action/codon packages by committed skill hash
- extracted chains by committed chain hash
- tool scripts by committed blob hash

Each foundation carries:

- `activation`
- `default_gap`
- `surface`
- `omo_role`

## Activation

The current activation surfaces are:

- `activate_skill_package(...)`
- `activate_stepchain_package(...)`
- `activate_chain_reference(...)`

Activation is now contract-aware rather than just package-shape-aware:

- public/name activation uses a block's canonical default gap contract
- hash embedding may specialize manifestation only through explicit override
- runtime nodes render `effective_contract` so the active chain shows what will actually execute

The important boundary is unchanged:

- activation turns packages into runtime gaps and activation steps
- activation does not introduce a separate scheduler or ontology

## Entity Versus Action Packages

The manifest layer sits beside a now-explicit runtime law:

- entity packages are usually resolved for semantic injection
- action packages are package/read surfaces unless explicitly activated
- workflow activation is explicit, not the default meaning of hash resolution

That makes the manifest engine the package bridge, not a generic “everything resolves into execution” layer.
