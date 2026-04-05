# skills and `.st` files

The skill tree is split by meaning, not just by file format.

```text
skills/
├─ admin.st
├─ actions/
├─ entities/
└─ codons/
```

## Tree Roles

- [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st) is the canonical local operator entity.
- `skills/entities/` holds semantic state packages.
- `skills/actions/` holds executable workflow packages.
- `skills/codons/` holds protected system primitives and immutable specs.

## Current Ownership

- `reason_needed`
  - judgment
  - activation
  - deciding when a tool, vocab route, clarification, child workflow, or persistence step is needed
- `tool_needed`
  - creating new public tools under [tools/](/Users/k2invested/Desktop/cors/tools)
  - every tool script must express its own runtime contract metadata
- `vocab_reg_needed`
  - configuring semantic vocab routes over public tools and public chains
- `reprogramme_needed`
  - semantic persistence for entity/admin state
  - not workflow origination

Action-tree work under `skills/actions/*.st` still routes to `reason_needed` first.

## Loader Contract

[skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) preserves the authored package payload and projects it into runtime-friendly skill objects. It keeps:

- package metadata
- refs
- semantic sections
- authored step fields
- artifact kind inferred from tree location

That means the runtime can treat entity packages, action packages, and codons differently even though they share the same `.st` storage format.

## Artifact Kinds

Current deterministic rules:

- [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st) => `entity`
- `skills/entities/*` => `entity`
- `skills/actions/*` => `action`
- `skills/codons/*` => `codon`

## Entity Packages

Entity packages are semantic state surfaces. They are resolved for context injection and persisted through [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) after `reprogramme_needed` has already made the judgment.

Typical sections:

- `identity`
- `preferences`
- `constraints`
- `sources`
- `scope`

## Action Packages

Action packages are executable workflow packages. They are not ordinary file content. They are rendered as semantic trees and only become live execution when explicitly activated.

Current law:

- creation or repair of `skills/actions/*.st` belongs to `reason_needed`
- public activation stays with the final completed workflow
- embedded workflow reuse is allowed but still secondary to tool-backed construction

## Codons

Current codons:

- [await.st](/Users/k2invested/Desktop/cors/skills/codons/await.st)
- [commit.st](/Users/k2invested/Desktop/cors/skills/codons/commit.st)
- [reprogramme.st](/Users/k2invested/Desktop/cors/skills/codons/reprogramme.st)
- [commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st)

`reason_needed`, `tool_needed`, and `vocab_reg_needed` are runtime vocabs, not mutable authored codon packages.

## Child Workflow Reintegration

The current runtime model is:

- `reason_needed` may activate a child workflow by hash
- it may choose `await_needed=true` or `false`
- the child runs in isolated trajectory storage
- the child tree is reinjected into the parent on:
  - `await_needed`, if waiting synchronously
  - `reason_needed`, if reintegrating asynchronously

`commit.st` remains the reintegration codon at the end of child `.st` flows.

## Chain Construction Spec

[commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st) is a protected planning spec. It is not part of the live `reason_needed` path anymore. It exists as a future reference point for `chain_needed`.

## Builder Reality

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) is the `.st` persistence validator/actualizer. It can:

- create or update entity packages
- create or update action packages when explicitly asked
- validate semantic/tree structure before write
- route writes into the correct skill subtree

It does not own activation or workflow judgment.
