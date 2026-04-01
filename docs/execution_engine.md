# execution_engine.py

[execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py) is the per-gap execution core.

It sits between the lawful sequencer in [compile.py](/Users/k2invested/Desktop/cors/compile.py) and the turn orchestrator in [loop.py](/Users/k2invested/Desktop/cors/loop.py).

## What It Owns

The module owns the branch-level execution path for one admitted ledger entry:

- resolve refs for the current gap
- route by vocab
- enforce tree-policy reroutes
- run deterministic observation paths
- run mutation composition and execution
- expand bridge codons
- auto-commit and inject universal postconditions
- record the resulting step back into trajectory and chain state

So [loop.py](/Users/k2invested/Desktop/cors/loop.py) no longer needs to inline the whole vocab dispatch tree. It hands the current ledger entry to `execute_iteration(...)`.

## Main API

The module exposes three small dataclasses and one main function:

- `ExecutionHooks`
- `ExecutionConfig`
- `ExecutionOutcome`
- `execute_iteration(...)`

`ExecutionHooks` is the runtime boundary back into the rest of the kernel. It carries the concrete helpers the execution core needs without making the module itself own those other subsystems:

- ref resolution
- subprocess tool execution
- git-backed auto-commit
- step parsing
- JSON / command extraction
- tree policy helpers
- entity rendering
- step-network rendering
- native reason codon emission

`ExecutionConfig` carries the stable execution-time constants:

- repo paths
- tool map
- deterministic vocab set
- observation-only vocab set

That split keeps the execution core reusable. The same engine now serves ordinary turn-time gap execution and `/command` execution.

## Branch Categories

The module currently handles these major execution classes.

Observation-only:
- inject resolved data
- create a blob-like observation step
- no mutation commit

Deterministic observation:
- run a tool directly if configured
- inject the result
- ask the model to articulate the observation and any child gaps

Mutation:
- enforce tree policy
- enforce OMO
- ask the model to compose either a patch payload or command
- execute
- auto-commit on success
- inject a universal `hash_resolve_needed` postcondition

Bridge codons:
- `commit_needed`
- `reason_needed`
- `await_needed`
- `reprogramme_needed`

Unknown vocab:
- fall back to generic reasoning over the current gap

## Reason Path

`reason_needed` is the richest branch in the execution engine.

It can:

- emit native `reason.st`
- submit `skeleton.v1` to [tools/skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/skeleton_compile.py)
- persist the resulting `stepchain.v1` package through [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- activate an existing `.st` or compiled chain package by hash
- schedule the package for current-turn or background activation

That means the execution core is one of the places where the structural side of the OS is now directly expressed.

## Mutation And Protection

The execution core is also where the current runtime protections actually bite.

Before mutation proceeds, it checks:

- tree-policy reroutes
- `.st` auto-reroute toward `reprogramme_needed`
- OMO legality

After execution, it checks commit outcome through `auto_commit()`. If the resulting commit touched a protected surface and was auto-reverted, the execution core handles the reject path and may emit a reorientation gap such as `reason_needed`.

So `execution_engine.py` is not just a dispatcher. It is one of the main places where the OS enforces the difference between ordinary worktree mutation, semantic-state persistence, and protected structural law.

## Relationship To Other Modules

[step.py](/Users/k2invested/Desktop/cors/step.py) defines the runtime objects the engine emits and records.

[compile.py](/Users/k2invested/Desktop/cors/compile.py) decides which gap the engine is allowed to address next and whether the current chain is done.

[manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py) is used when execution needs to persist or reactivate compiled packages.

[loop.py](/Users/k2invested/Desktop/cors/loop.py) owns the larger turn lifecycle around the engine:

- first-step formation
- identity injection
- active-chain rendering
- pre-synthesis reprogramme
- heartbeat persistence
- final synthesis

That is the intended boundary: `loop.py` assembles the world for the turn, and `execution_engine.py` executes the current branch.
