# Architecture

`docs/PRINCIPLES.md` is the source of truth for the design. This file is narrower: it describes the architecture that is actually implemented in the current codebase, and it calls out where that implementation is still catching up to the principles.

## Core Shape

The kernel is built around one runtime primitive: the step. A step records what was followed, what was looked at, what was concluded, and whether a mutation produced a commit. Gaps are emitted from steps, the compiler admits and sequences those gaps, and the turn loop resolves or executes them.

The current layers are:

- Layer 0: `step.py`, `skills/loader.py`, `tools/`
- Layer 1: `compile.py`
- Layer 2: `loop.py`

The dependency direction is still clean in practice:

- `step.py` defines the runtime objects.
- `compile.py` depends on `step.py`.
- `loop.py` depends on both and orchestrates execution.
- tools are executed as subprocesses rather than imported into the kernel.

Git remains the external content store. The trajectory stores step and gap structure, while blobs, trees, and commits stay in `.git` and are resolved on demand.

## Runtime Model

The running system has four main surfaces.

`step.py`
Defines `Gap`, `Step`, `Chain`, and `Trajectory`. This is the closed hash graph the model reasons over.

`compile.py`
Turns emitted gaps into executable order. It owns the ledger, admission thresholds, OMO enforcement, chain lifecycle, and the deterministic governor.

`loop.py`
Runs a turn end to end. It loads trajectory and skills, creates the origin step, routes gaps by vocab, executes tools, commits mutations, injects postconditions, and synthesizes the user response.

`skills/*.st`
Provides hash-addressable packaged structure. In practice these currently play two roles:

- executable action packages
- persistent entity-style state

That distinction is important architecturally even though the current loader still treats both through the same raw file format.

## Execution Flow

At runtime the flow is:

1. Load trajectory, chains, skills, and HEAD.
2. Ask the model for the origin step.
3. Inject identity if a contact-triggered `.st` exists.
4. Admit origin gaps into the compiler ledger.
5. Iterate depth-first over ledger entries.
6. Resolve, observe, mutate, or bridge based on vocab.
7. Auto-commit successful mutations and inject a `hash_resolve_needed` postcondition.
8. Run the pre-synthesis reprogramme pass.
9. Synthesize the user-facing response.
10. Persist trajectory and extracted chains.

The loop is not a planner in the traditional sense. Planning emerges from step emission, compiler ordering, and the codon workflows loaded from `skills/codons/`.

## Vocab Surface

The executable runtime vocab is defined in `compile.py`.

Observe:

- `pattern_needed`
- `hash_resolve_needed`
- `email_needed`
- `external_context`
- `clarify_needed`

Mutate:

- `hash_edit_needed`
- `stitch_needed`
- `content_needed`
- `script_edit_needed`
- `command_needed`
- `message_needed`
- `json_patch_needed`
- `git_revert_needed`

Bridge codons:

- `reason_needed`
- `await_needed`
- `commit_needed`
- `reprogramme_needed`

This is wider than the older docs implied. The current system is no longer a single-bridge runtime. It has four bridge codons and explicit priority ordering for them.

## Tree Policy

`loop.py` enforces a tree policy before accepting mutations.

Current default policy:

- `skills/codons/` is immutable and rejects into `reason_needed`
- `skills/` reroutes mutation toward `reprogramme_needed`
- `ui_output/` reroutes mutation toward `stitch_needed`
- core kernel files and persistence files are immutable

This is one of the clearest architectural distinctions in the codebase. It already treats codons, executable `.st` files, and ordinary workspace files differently.

## Codons

The codons in `skills/codons/` are not just labels. They are real packaged workflows:

- `reason.st`
- `await.st`
- `commit.st`
- `reprogramme.st`

`loop.py` expands these by loading the corresponding `.st` and dispersing its steps as child gaps. In other words, codons are executable step packages, not hardcoded switch cases alone.

## Semantic Tree, Skeleton, and Extraction

The current runtime semantic tree is the realized trajectory: steps, gaps, refs, chains, and commits.

Alongside that, the repo now has `schemas/skeleton.v1.json`. That schema is not the runtime tree. It is an author-time planning skeleton intended for deterministic compilation into executable packages.

That gives the architecture three distinct levels:

- runtime trajectory: realized semantic tree
- long-chain extraction: `chains/*.json`
- author-time skeleton: `schemas/skeleton.v1.json`

This separation matches the code better than the older docs did. The runtime tree is what happened. The skeleton is what can be formalized and lowered.

## Important Drift To Keep In Mind

Several mechanisms still lag the principles or each other.

The `.st` runtime is lossy.
`skills/loader.py` only keeps `action`, `desc`, `vocab`, and `post_diff` as first-class executable step data. Fields such as `resolve`, `condition`, `inject`, and richer manifestation fields remain present in raw files but are not preserved in the loaded `SkillStep`.

The builder and some existing skills still use legacy vocabs.
`tools/st_builder.py` infers `scan_needed`, `research_needed`, and `url_needed`, and some current `.st` files still contain them. Those terms are not part of the executable vocab algebra in `compile.py`.

`chain_to_st.py` is heuristic, not a perfect round-trip.
It derives action names from descriptions and infers some step properties from resolved chain structure. It is useful, but it is not a lossless serialization of runtime structure.

Some prompts still describe the older worldview.
`loop.py` includes prompt language around `.st` composition and manifestation that is broader than what the loader and compiler currently treat as executable first-class structure.

## What This Means

The architecture is stronger than the stale docs suggested. The code already distinguishes:

- primitive runtime structure
- sequencing law
- higher-order codon workflows
- protected persistence surfaces
- author-time planning skeletons

The main documentation problem was not that the system lacked architecture. It was that the docs flattened several real distinctions that already exist in the code.
