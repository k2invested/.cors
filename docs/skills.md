# skills and `.st` files

This repo uses `.st` as a shared file format for several different kinds of packaged structure. `PRINCIPLES.md` gives the philosophical model. This file explains what the current code actually does with `.st` files.

## What `.st` Means In The Current System

Right now a `.st` file can play at least three roles:

- an executable action package
- an entity-style persistent state object
- a codon package

The format is shared, but the runtime meaning depends on where the file sits and how the loop uses it.

That distinction matters.

An action-like `.st` is being used as executable structure.

An entity-like `.st` is being used as persistent represented state.

A codon `.st` is treated as protected structural law and is not allowed to mutate directly.

## Current Runtime Loader

`skills/loader.py` is much narrower than the raw `.st` format might suggest.

When it loads a skill step, it keeps only:

- `action`
- `desc`
- `vocab`
- `post_diff`

At the `Skill` level it keeps:

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

Those fields may still exist in the raw file and may still matter when the file is rendered back into context, but they are not part of the loaded `SkillStep` contract.

## Triggers

The loader and surrounding tools currently recognize these trigger styles:

- `manual`
- `every_turn`
- `on_mention`
- `on_contact:<id>`
- `on_vocab:<vocab>`
- `scheduled:<value>`
- `command:<name>`

`command:` files are hidden from the main LLM-facing registry and are only available through `run_command()`.

## Current Registry Behavior

`SkillRegistry` maintains three lookup surfaces:

- `by_hash`
- `by_name`
- `commands`

Display names come from `identity.name` when present, otherwise from `name`. That is why rendered refs can appear as `kenny:<hash>` rather than `admin:<hash>`.

The prompt-facing skill list excludes `/command` skills.

## Codons

The codons live in `skills/codons/` and are loaded with the same loader as other `.st` files:

- `reason.st`
- `await.st`
- `commit.st`
- `reprogramme.st`

They are special because tree policy marks the codon directory as immutable and rejects attempted mutation into `reason_needed`.

That gives codons a different ontological role from ordinary skills even though the loader format is shared.

## Entity vs Action `.st`

The codebase is already moving toward a real distinction between entity-like and action-like `.st` files.

Action `.st`
Represents executable workflow structure. These are typically invoked by vocab or used as reusable procedural packages.

Entity `.st`
Represents persisted state about a person, concept, domain, or other durable object. These are often surfaced via hash resolution and are the natural target of `reprogramme_needed`.

This distinction is not yet enforced by separate schemas, but the runtime already leans that way:

- `.st` mutation is rerouted to `reprogramme_needed`
- codon mutation is blocked
- entity resolution happens through hash resolution rather than a separate entity vocab

## Builder Reality

`tools/st_builder.py` writes valid JSON `.st` files, forwards non-base manifestation fields, and supports stepless entities.

But it is important to be clear about its current drift.

Its vocab inference still emits legacy terms such as:

- `scan_needed`
- `research_needed`
- `url_needed`

Those are not part of the executable vocab algebra defined in `compile.py`.

That means `st_builder.py` is still useful as a persistence tool, but it should not be treated as perfectly aligned with the live runtime vocab model.

## Existing Repo Drift

The current repo already contains `.st` files that reflect earlier runtime assumptions. For example, `skills/research.st` still contains `research_needed`, which is not part of the compiler’s active vocab sets.

So the right way to read the ecosystem today is:

- some `.st` files are fully aligned with the live kernel
- some still encode older vocabulary or richer intended structure than the loader currently executes

## Extraction And Skeletons

There are now two related but distinct packaging ideas in the repo.

`tools/chain_to_st.py`
Extracts a resolved chain into `.st`, but the extraction is heuristic. It derives actions from descriptions and infers properties from step shape.

`schemas/skeleton.v1.json`
Defines an author-time semantic tree skeleton intended for deterministic compilation into executable packages.

That is the better place to look if you want a planning-side contract. The runtime `.st` loader is still narrower than the author-time planning surface.

## Practical Reading Of The System Today

If you need the short version, it is this:

`.st` is the repo’s shared packaging format, but not every `.st` field is first-class at runtime.

The live kernel currently treats `.st` files as:

- executable package definitions when loaded into `SkillStep`
- rendered entity data when resolved by hash
- protected structural primitives when they are codons

That is the shape the docs need to respect until the loader, compiler, builder, and skeleton compiler all converge further.
