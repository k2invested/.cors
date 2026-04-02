# Architecture

[PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md) is the design source of truth. This file is narrower: it records the architecture that is implemented now and names the real module boundaries.

## Runtime Stack

The kernel is still built on one primitive: `step -> gap -> ledger -> step`.

```text
input / event
  -> loop.py
     -> step.py            runtime objects and renders
     -> compile.py         lawful frontier sequencing
     -> execution_engine.py per-gap execution
     -> manifest_engine.py package rendering and activation
     -> skills/loader.py   .st registry projection
     -> tools/*            subprocess operators and compilers
  -> trajectory.json / chains.json / git objects
```

The implemented layers are:

- Layer 0: [step.py](/Users/k2invested/Desktop/cors/step.py)
- Layer 1: [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- Layer 2: [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- Layer 3: [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- Layer 4: [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- Package projection: [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py)
- Operator bench: [tools/](/Users/k2invested/Desktop/cors/tools)

## Skill Tree

The `.st` ecology is now explicitly split by tree location:

```text
skills/
├─ admin.st                     canonical admin primitive
├─ actions/
│  ├─ architect.st
│  ├─ debug.st
│  └─ hash_edit.st
├─ entities/
│  ├─ clinton.st
│  ├─ cors_ui.st
│  └─ top_rate_estates_ltd.st
└─ codons/
   ├─ await.st
   ├─ commit.st
   ├─ commitment_chain_construction_spec.st
   ├─ reason.st
   └─ reprogramme.st
```

The important laws are:

- [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st) is the only root skill and the canonical operator primitive.
- `skills/entities/` is the semantic entity tree.
- `skills/actions/` is the executable workflow tree.
- `skills/codons/` is immutable.
- [commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st) lives in the codon tree for immutability, but the loader and resolver treat it as an entity-like spec package.

## Turn Flow

```text
run_turn()
  -> origin step
  -> admin / identity injection
  -> compiler creation
  -> explicit dangling-gap readmission
  -> ledger iteration
     -> execute_iteration()
     -> record step / emit child gaps / commit / postcondition
  -> optional reprogramme pass
  -> synthesis
  -> optional heartbeat persistence
  -> save trajectory and chains
```

Three runtime surfaces are injected repeatedly:

- recent trajectory render from [step.py](/Users/k2invested/Desktop/cors/step.py)
- active chain render from [step.py](/Users/k2invested/Desktop/cors/step.py)
- step network render from [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)

## Gap Lifecycle

The implemented lifecycle is:

```text
LLM emits gaps
  -> compile.py scores and admits them
  -> execution_engine.py resolves one admitted gap
  -> resulting step is appended to trajectory
  -> child gaps re-enter compiler
  -> successful mutations auto-commit and emit post-observe hash_resolve_needed
```

Cross-turn carry is now opt-in:

- only gaps with `carry_forward=True` are re-admitted
- `clarify_needed` does not carry across turns
- forced-synthesis persistence clones the active frontier into one explicit carry-forward step

## Clarify Frontier

Clarification is now a bounded one-turn frontier, not an always-resume queue.

```text
active clarify gaps in current turn
  -> merged by execution_engine.py
  -> one clarification frontier step
  -> one canonical step hash
  -> user answers on next turn
```

Historical clarify leaves are not automatically replayed.

## Deterministic Routing

Tree policy and target-path inference now deterministically choose reprogramme mode.

```text
skills/admin.st    -> reprogramme_needed (entity_editor)
skills/entities/*  -> reprogramme_needed (entity_editor)
skills/actions/*   -> reprogramme_needed (action_editor)
skills/codons/*    -> immutable -> reason_needed on reject
```

Action origination is split from entity persistence:

- entity creation and entity updates can go straight to `reprogramme_needed`
- existing action updates can go through `reprogramme_needed` in `action_editor` mode
- new action or hybrid workflow origination is rerouted to `reason_needed` first

## Reprogramme And Reason

The implemented split is:

- `reason_needed`
  - structural design
  - chain planning
  - `skeleton.v1` compilation
  - existing package activation
- `reprogramme_needed`
  - semantic persistence
  - entity updates
  - bounded edits to existing action packages

`reason_needed` and `reprogramme_needed` selectively inject the immutable chain construction spec when workflow structure matters.

## Commit Assessment

Successful `.st` writes now materialize a real post-observation step before synthesis.

```text
reprogramme write
  -> auto_commit()
  -> commit assessment
  -> postcondition step with assessment
  -> hash_resolve_needed observe gap
  -> synthesis sees realized change
```

The same assessment family is also attached to rogue diagnosis when persistence fails.

## Files And Stores

- [trajectory.json](/Users/k2invested/Desktop/cors/trajectory.json): ordered runtime steps
- [chains.json](/Users/k2invested/Desktop/cors/chains.json): chain index
- `chains/<hash>.json`: extracted or compiled packages
- git objects: external content store for blobs, trees, and commits

The architectural constant remains simple: packages, chains, entities, and commits all eventually re-enter the live system as steps and gaps.
