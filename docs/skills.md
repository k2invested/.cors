# skills and `.st` files

This repo now uses a real `.st` tree split. The format is shared, but runtime meaning is determined by tree location, loader projection, and tree policy.

## Current Skill Tree

```text
skills/
├─ admin.st
├─ actions/
├─ entities/
└─ codons/
```

The operative distinction is:

- root: only [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st)
- `skills/actions/`: executable action and workflow packages
- `skills/entities/`: semantic state packages
- `skills/codons/`: immutable codons and immutable planning spec

## Loader Contract

[skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) is no longer the narrow projection older docs described.

It now preserves:

- package payload
- package refs
- package semantics
- `artifact_kind`
- authored step fields including:
  - `relevance`
  - `resolve`
  - `condition`
  - `inject`
  - `content_refs`
  - `step_refs`
  - `kind`
  - `goal`
  - `allowed_vocab`
  - `manifestation`
  - `generation`
  - `transitions`
  - `terminal`
  - `requires_postcondition`
  - `activation_key`

It still exposes a normalized runtime projection, but it no longer throws away most authored manifestation structure.

## Artifact Kind

Artifact kind is now inferred deterministically from payload and tree membership.

The current rules are:

- `admin.st` => `entity`
- `commitment_chain_construction_spec.st` => `entity`
- `skills/codons/*` => `codon`
- `skills/entities/*` => `entity`
- `skills/actions/*` => `action`
- semantic payload + steps outside the tree rules => `hybrid`

That means tree organization is now part of the ontology rather than just file hygiene.

## Admin Primitive

[admin.st](/Users/k2invested/Desktop/cors/skills/admin.st) is special.

It is:

- the canonical operator entity
- the only root skill
- the preferred identity resolution target for the local operator

It is not just “another entity in `skills/entities/`”.

## Chain Construction Spec

[commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st) has a special role.

It lives in `skills/codons/` so the agent cannot mutate it casually, but the loader and resolver treat it as an entity-like spec package:

- immutable by tree policy
- resolved as context injection
- selectively injected into `reason_needed`
- also injected into `reprogramme_needed` for action-editor workflow persistence

## Entity Packages

Entity packages are context-injection packages, not freeform notes.

They must carry deterministic context-injection steps derived from semantic sections such as:

- `identity`
- `preferences`
- `constraints`
- `sources`
- `scope`

Examples:

- `load_identity`
- `load_preferences`
- `load_constraints`

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) now restores or requires those steps when semantic entity payload exists.

## Action Packages

Action packages live in [skills/actions](/Users/k2invested/Desktop/cors/skills/actions) and represent executable workflow structure.

Important current law:

- updates to existing action packages can use `reprogramme_needed` in `action_editor`
- new action or hybrid origination must go through `reason_needed` first

So action `.st` persistence is no longer treated as just another file write.

## Codons

The codon tree currently contains:

- [await.st](/Users/k2invested/Desktop/cors/skills/codons/await.st)
- [commit.st](/Users/k2invested/Desktop/cors/skills/codons/commit.st)
- [reason.st](/Users/k2invested/Desktop/cors/skills/codons/reason.st)
- [reprogramme.st](/Users/k2invested/Desktop/cors/skills/codons/reprogramme.st)
- [commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st)

True codons are identified by `artifact_kind == "codon"`, not merely by directory print tags.

## Runtime Resolution

The current resolution law is:

- entity-like package hash in `content_refs` => semantic injection
- action package hash in `content_refs` => package render / read
- activation of action structure => explicit reason/package activation path

So the runtime no longer treats “all `.st` hashes” as the same kind of thing.

## Builder Reality

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) is now the semantic persistence curator.

It can:

- create entities
- update entities
- update existing action packages when explicitly targeted
- route new entity writes into `skills/entities/`
- route new action writes into `skills/actions/`

It does not own new workflow origination. New workflow structure belongs to the `reason_needed -> skeleton_compile` side first.
