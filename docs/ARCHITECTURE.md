# Architecture

[PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md) is the design source of truth. This file is narrower: it records the architecture that is actually implemented in source now, the module boundaries that currently exist, and the places where the implementation is still only partially aligned with the design.

## The Implemented Shape

The architecture is still built from one primitive: the step. A step records semantic movement, the refs that grounded that movement, any emitted gaps, and optionally a commit. Gaps are admitted by the compiler onto a lawful frontier, addressed by the loop, and recorded back into the trajectory. Chains, `.st` packages, compiled stepchains, and extracted artifacts are all higher-order structures, but none of them replace the step-gap primitive. They all eventually re-enter the runtime as step-and-gap dispersal.

The implemented layering is:

- Layer 0: [step.py](/Users/k2invested/Desktop/cors/step.py)
- Layer 1: [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- Layer 2: [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- Layer 3: [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- Layer 4: [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- Package and subprocess boundary: [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) and [tools/](/Users/k2invested/Desktop/cors/tools)

This separation is now real in the code. `step.py` owns the runtime graph and semantic renders. `compile.py` owns admission, ledger sequencing, and branch law. `manifest_engine.py` owns hash-addressed package persistence, rendering, and activation. `execution_engine.py` owns per-gap execution. `loop.py` owns turn assembly and orchestration. Tool scripts remain outside the kernel and are executed as subprocess operators.

Git remains the external content store. The trajectory stores semantic structure. Blobs, trees, and commits remain in `.git` and are resolved on demand.

## Runtime Surfaces

There are five core runtime surfaces, plus the package layer they work over.

[step.py](/Users/k2invested/Desktop/cors/step.py) is the runtime object model. It defines `Gap`, `Step`, `Chain`, and `Trajectory`, plus the semantic tree renders used by the loop.

[compile.py](/Users/k2invested/Desktop/cors/compile.py) is the lawful sequencer. It admits gaps, places them on the ledger, tracks chain lifecycle, enforces the runtime OMO grammar, and keeps the small amount of background bookkeeping needed for heartbeat closure.

[manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py) is the package manifestation layer. It persists compiled `stepchain.v1` packages, resolves them by hash, renders them back into context, lists current package references, renders the step network, and activates both `.st` packages and compiled `.json` stepchains back into first-generation runtime gaps.

[execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py) is the live execution core. It takes one admitted ledger entry and runs the branch machinery: resolve refs, route by vocab, enforce tree policy, compose and execute mutations, expand codons, inject postconditions, and record the resulting step back into trajectory and chain state.

[loop.py](/Users/k2invested/Desktop/cors/loop.py) is the live turn orchestrator. It loads state, forms the origin step, injects identity and semantic context, creates the compiler, injects the active chain tree, hands each admitted gap to `execution_engine.py`, runs the pre-synthesis reprogramme pass, schedules heartbeat work, synthesizes the user answer, and persists state.

The package layer sits under those modules:

- loaded `.st` files from [skills/](/Users/k2invested/Desktop/cors/skills)
- compiled stepchains in `chains/*.json`
- extracted long runtime chains in `chains/*.json`

## Context Model

The model does not reason over raw `trajectory.json`. The session is built from rendered semantic surfaces.

The main ones in the current runtime are:

- a salient trajectory window from [`Trajectory.render_recent()` in step.py](/Users/k2invested/Desktop/cors/step.py#L563)
- an active branch render from [`Trajectory.render_chain()` in step.py](/Users/k2invested/Desktop/cors/step.py#L601)
- resolved hash renders from [`resolve_hash()` in loop.py](/Users/k2invested/Desktop/cors/loop.py#L212)
- identity and entity renders from `loop.py`
- the package ecology render from [`render_step_network()` in manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py#L131)

That gives the runtime three distinct semantic views at once:

- trajectory memory: salient prior reasoning and action
- active chain tree: the current causal branch being worked
- step network: the current package and entity ecology the system can build into

## Package Story

The package story is now broader than a single `.st` path.

Author-time planning surfaces:

- [schemas/skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/skeleton.v1.json)
- [schemas/semantic_skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/semantic_skeleton.v1.json)

Deterministic compilers:

- [tools/skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/skeleton_compile.py)
- [tools/semantic_skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/semantic_skeleton_compile.py)

Runtime manifestation surfaces:

- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- hash-addressed `.st` packages loaded through [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py)
- compiled and extracted chain packages in `chains/*.json`

Legacy or heuristic crystallizers:

- [tools/chain_to_st.py](/Users/k2invested/Desktop/cors/tools/chain_to_st.py)
- [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)

So the repo does not currently have one packaging path. It has deterministic workflow compilation, semantic persistence, and heuristic extraction living side by side.

## Reason And Reprogramme

The code now makes a sharper distinction between `reason_needed` and `reprogramme_needed`.

`reason_needed` is the structural side. In the current runtime it can:

- emit native `reason.st`
- submit `skeleton.v1` for deterministic compilation
- activate an existing `.st` or compiled `.json` chain package by hash
- schedule package activation as background work and rely on heartbeat reintegration

`reprogramme_needed` is the semantic persistence side. In the current runtime it:

- still composes through [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)
- receives the step network as part of its context
- updates semantic `.st` state rather than originating deterministic action structure

That gives the architecture a real split between structural derivation and semantic persistence, even though the persistence path is still looser and more legacy than the workflow side.

## Tree Policy

[loop.py](/Users/k2invested/Desktop/cors/loop.py) enforces a real ontological boundary through tree policy.

- `skills/codons/` is immutable and rejects into `reason_needed`
- `skills/` reroutes mutation toward `reprogramme_needed`
- `ui_output/` reroutes mutation toward `stitch_needed`
- core kernel and persistence files are immutable

This is one of the clearest implemented distinctions in the repo: codons, packaged `.st` state, and ordinary workspace files are not treated as the same kind of thing.

## Important Current Partials

Several architectural distinctions are now real, but a few important paths are still partial.

[skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) now preserves full package payload plus a normalized runtime projection. It carries package-level `artifact_kind`, refs, semantic fields, and raw payload, and it carries richer step structure such as `resolve`, `condition`, `inject`, `relevance`, manifestation blocks, and generation blocks into runtime objects.

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) is now narrower: it curates semantic `.st` state and supports explicit updates to existing executable packages, but it no longer originates new action workflows and no longer guesses legacy workflow vocab from natural language.

[tools/chain_to_st.py](/Users/k2invested/Desktop/cors/tools/chain_to_st.py) remains heuristic rather than lossless. It is useful as a crystallizer, but it is not the deterministic workflow compiler.

Compiled `stepchain.v1` packages are now real runtime artifacts, but they currently manifest by activation into first-generation gaps rather than by replacing the step-gap primitive. That is consistent with the architecture and should be described that way.

## Summary

The current system is no longer just `step.py + compile.py + loop.py`. It now includes a real package manifestation layer, deterministic skeleton compilers, an active-chain context model, and a clearer separation between structural derivation and semantic persistence.

The important thing to preserve is simple: none of these higher-order layers replace the foundational primitive. They all still fold back into step and gap structure.
