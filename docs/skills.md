# skills and `.st` files

This repo uses `.st` as a shared file format for several different kinds of packaged structure. [PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md) gives the design interpretation. This file records what the current code actually does with `.st` files.

## What `.st` Means In The Current Runtime

Right now a `.st` file can play at least three roles:

- an executable action package
- an entity-style persistent state object
- a codon package

The format is shared, but the runtime meaning depends on where the file sits and how the loop and manifest engine use it.

Action-like `.st` files are used as executable structure.

Entity-like `.st` files are used as persistent represented state and are commonly surfaced through hash resolution.

Codon `.st` files are packaged structure too, but tree policy treats them as protected law rather than normal editable state.

## The Loader Contract

[skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) is narrower than the raw `.st` format.

At the step level it keeps only:

- `action`
- `desc`
- `vocab`
- `post_diff`

At the package level it keeps:

- `hash`
- `name`
- `desc`
- `steps`
- `source`
- `display_name`
- `trigger`
- `is_command`

So the executable runtime does not currently preserve fields such as:

- `resolve`
- `condition`
- `inject`
- step-level `relevance`
- richer manifestation metadata

Those fields may still exist in the raw file and may still matter for prompts or future tooling, but they are not first-class on the loaded `SkillStep`.

## Triggers

The loader and surrounding runtime currently recognize these trigger styles:

- `manual`
- `every_turn`
- `on_mention`
- `on_contact:<id>`
- `on_vocab:<vocab>`
- `scheduled:<value>`
- `command:<name>`

`command:` packages are kept out of the normal prompt-facing registry and are accessed through explicit command execution paths.

## Registry Behavior

`SkillRegistry` maintains three main lookup surfaces:

- `by_hash`
- `by_name`
- `commands`

Display names come from `identity.name` when present, otherwise from `name`. That is why a rendered ref can appear as `kenny:<hash>` rather than `admin:<hash>`.

The prompt-facing skill list excludes `/command` packages.

## Codons

The codons live in [skills/codons/](/Users/k2invested/Desktop/cors/skills/codons) and are loaded with the same loader as any other `.st` file:

- `reason.st`
- `await.st`
- `commit.st`
- `reprogramme.st`

They are special because tree policy marks the codon directory as immutable and rejects attempted mutation into `reason_needed`. So although the file format is shared, codons occupy a different ontological role from ordinary `.st` packages.

## Entity And Action `.st`

The runtime is already leaning toward a real distinction between entity-like and action-like `.st` files.

Action `.st` represents executable workflow structure. These packages are typically invoked by vocab, step hash, or command surface and are part of the step manifestation layer.

Entity `.st` represents persisted state about a person, concept, domain, or other durable object. These packages are the natural target of `reprogramme_needed` and are commonly rendered into context by hash resolution.

This distinction is not yet enforced by separate runtime schemas, but the system already behaves as if it matters:

- `.st` mutation is rerouted to `reprogramme_needed`
- codon mutation is blocked
- entity-like packages surface through hash resolution rather than a separate entity vocab

## Builder Reality

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) now acts as a narrower semantic curator. It writes valid JSON `.st` files, forwards non-base semantic fields, supports pure entities, and can update an existing executable package by explicit hash reference.

It no longer tries to originate new action workflows, and it no longer infers workflow vocab from natural language. Any executable step vocab it writes must be supplied explicitly and must already belong to the live runtime vocab algebra in [compile.py](/Users/k2invested/Desktop/cors/compile.py).

## `.st` And The Newer Package Surfaces

There are now two related but distinct packaging directions in the repo.

[tools/chain_to_st.py](/Users/k2invested/Desktop/cors/tools/chain_to_st.py) extracts a resolved runtime chain into `.st`, but that extraction is still heuristic.

[schemas/skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/skeleton.v1.json) and [schemas/semantic_skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/semantic_skeleton.v1.json) define author-time planning and semantic envelopes intended for deterministic compilation.

That means the loader-side `.st` contract is currently narrower than the newer author-time planning surfaces.

## Practical Reading Of The System Today

The short version is simple.

`.st` is the repo’s shared packaging format, but not every `.st` field is first-class at runtime.

The live kernel currently treats `.st` files as:

- executable package definitions when loaded into `SkillStep`
- rendered semantic state when resolved by hash
- protected structural primitives when they are codons

That is the accurate current picture until the loader, compilers, builders, and manifestation engine converge further.
