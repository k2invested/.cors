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
  -> trajectory.json / chains.json / git objects
```

## Core Split

- [step.py](/Users/k2invested/Desktop/cors/step.py)
  - runtime objects and tree renders
- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
  - lawful frontier sequencing
- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
  - per-gap execution and routing
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
  - package rendering and activation
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
  - outer turn orchestration

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
  - deciding which step type should handle the work
- `tool_needed`
  - tool-tree authoring under `tools/`
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
```

## Tool Layer

The public tool surface is derived from [tools/tool_registry.py](/Users/k2invested/Desktop/cors/tools/tool_registry.py).

The two core file primitives are:

- [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)

Specialized handlers behind those two primitives stay internal in [tools/hash_registry.py](/Users/k2invested/Desktop/cors/tools/hash_registry.py).

## Observe / Mutate Rhythm

The implemented execution model is:

- observations surface relevant next gaps
- mutations do not directly expand the ledger
- successful mutations trigger post-observation

That is the main simplification behind the current architecture.
