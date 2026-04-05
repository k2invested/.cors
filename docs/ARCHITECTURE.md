# Architecture

[PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md) remains the design source of truth. This file describes the implemented boundaries now.

## Runtime Stack

```text
input
  -> loop.py
     -> step.py
     -> compile.py
     -> execution_engine.py
     -> manifest_engine.py
     -> skills/loader.py
     -> tools/*
     -> system/*
  -> trajectory.json / chains.json / trajectory_store/* / git objects
```

## Core Split

- [step.py](/Users/k2invested/Desktop/cors/step.py)
  - runtime objects, semantic trees, extracted-chain storage
- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
  - lawful frontier sequencing and background bookkeeping
- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
  - per-gap execution, routing, and child activation
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
  - package rendering and semantic-tree projection
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
  - outer turn orchestration and state persistence
- [system/](/Users/k2invested/Desktop/cors/system)
  - immutable registry, builder, and compiler infrastructure

## Skill Tree

```text
skills/
├─ admin.st
├─ actions/
├─ entities/
└─ codons/
```

Meaning:

- `admin.st` is the canonical operator entity
- `skills/entities/` stores semantic state
- `skills/actions/` stores executable workflows
- `skills/codons/` stores protected primitives and immutable specs

## Current Runtime Ownership

- `reason_needed`
  - judgment
  - routing
  - child-workflow activation
- `tool_needed`
  - tool-tree authoring under `tools/`
- `vocab_reg_needed`
  - configurable semantic routing in `vocab_registry.py`
- `reprogramme_needed`
  - entity/admin persistence

Chain construction is intentionally not owned by `reason_needed` anymore. A dedicated `chain_needed` path is the next planned layer, but it is not the implemented runtime yet.

## Deterministic Tree Policy

```text
skills/admin.st    -> reprogramme_needed
skills/entities/*  -> reprogramme_needed
skills/actions/*   -> reason_needed
skills/codons/*    -> immutable -> reason_needed on reject
tools/*            -> tool_needed
vocab_registry.py  -> vocab_reg_needed
system/*           -> immutable -> reason_needed on reject
```

## Tool And Chain Layers

The public tool surface is derived from [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py).

The public chain surface is derived from [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py).

The two core file primitives are:

- [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)

Specialized handlers behind those two primitives stay internal in [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py).

## Background Activation

Child workflows are reason-led and minimal:

- `reason_needed` may emit:
  - `activate_ref`
  - `prompt`
  - `await_needed`
- `await_needed=true`
  - parent gets an `await_needed` checkpoint before synthesis
- `await_needed=false`
  - parent gets a post-synth `reason_needed` reintegration point
- isolated child stores live under:
  - `trajectory_store/command`
  - `trajectory_store/subagent`
  - `trajectory_store/background_agent`

## Observe / Mutate Rhythm

The implemented execution model is:

- observations surface relevant next gaps
- mutations do not directly expand the ledger
- successful mutations trigger post-observation

That is the main simplification behind the current architecture.
