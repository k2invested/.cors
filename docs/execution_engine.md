# execution_engine.py

[execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py) is the per-gap execution core. It sits between the compiler’s lawful frontier and the turn loop’s orchestration.

## What It Owns

`execute_iteration(...)` owns one admitted ledger entry:

```text
gap
  -> resolve refs
  -> enforce tree policy
  -> route by vocab
  -> observe / mutate / codon handling
  -> commit if needed
  -> inject postcondition
  -> record resulting step
```

The loop does not inline this routing anymore.

## Main Runtime Objects

The module exports:

- `ExecutionHooks`
- `ExecutionConfig`
- `ExecutionOutcome`
- `execute_iteration(...)`

This keeps the execution core narrow. The module receives concrete hooks for git, tool execution, parsing, tree policy, and commit assessment rather than owning those subsystems itself.

## Clarify Frontier

Clarification now halts through one merged frontier step rather than a series of single-gap stops.

Implemented helpers:

- `_collect_clarify_frontier(...)`
- `_merged_clarify_desc(...)`
- `_build_clarify_frontier_step(...)`

Current law:

- only current-turn clarify gaps are merged
- duplicates are removed by hash
- one canonical clarification step is appended
- iteration halts immediately after that step

## Observation Paths

Observation splits into three forms:

- `observation_only_vocab`
  - inject resolved data
  - create a blob-like observation step
  - no child-gap articulation pass
- deterministic observation
  - resolve / tool run
  - ask the model what it observed
- normal observation
  - resolve / tool run
  - parse a new step and any emitted gaps

`pattern_needed` has a special deterministic helper:

- `_pattern_tool_params(...)`

It infers `file_grep.py` arguments from the gap description when the model gives a concrete quoted pattern.

## Mutation Routing

Mutation is not direct file editing anymore when `.st` surfaces are involved.

The current flow is:

```text
mutate gap
  -> tree policy lookup
  -> .st auto-reroute if relevant
  -> determine route_mode
  -> maybe reroute to reason_needed
  -> execute mutation branch
```

Key helpers:

- `_entity_target_for_reprogramme(...)`
- `_reprogramme_mode_for_source(...)`
- `_determine_reprogramme_mode(...)`
- `_new_action_origination_requires_reason(...)`

Deterministic route modes are:

- `entity_editor`
- `action_editor`

The important law is:

- entity writes can go straight to `reprogramme_needed`
- existing action updates can go to `reprogramme_needed` in `action_editor`
- new action or hybrid origination is rerouted to `reason_needed` first

## Reason Path

`reason_needed` is now a selective structural branch rather than a generic fallback.

It can:

- emit the native [reason.st](/Users/k2invested/Desktop/cors/skills/codons/reason.st) codon
- submit `skeleton.v1` for deterministic compilation
- activate an existing `.st` or compiled chain package by hash

When the gap smells like workflow planning, it also injects the immutable chain construction spec:

- `_should_inject_chain_spec_for_reason(...)`
- `_inject_chain_spec(...)`

This spec is not injected into every reasoning turn. It is scoped to planning, chain, workflow, manifest, skeleton, and research-like gaps.

## Reprogramme Path

`reprogramme_needed` now operates with explicit route guidance.

Implemented behaviors:

- inject existing entity data when present
- inject [PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md)
- inject step network
- inject chain construction spec for `action_editor`
- surface an editable semantic frame
- coerce returned frames to the route mode

The frame coercion helper is:

- `_coerce_semantic_frame_for_mode(...)`

For `entity_editor`, it hardens the returned frame to:

- `artifact.kind = entity`
- `artifact.protected_kind = entity`
- no `root`
- no `phases`
- no `closure`

That is the mechanism that prevents entity packages from drifting into accidental hybrid scaffolding.

## Rogue Handling

Persistence and execution failure no longer disappear into terminal output.

Implemented helpers:

- `_make_rogue_step(...)`
- `_emit_rogue_with_diagnosis(...)`
- `_extract_invalid_generated_json(...)`

A rogue step can carry:

- `rogue_kind`
- `failure_source`
- `failure_detail`
- `assessment`
- one follow-up `reason_needed` diagnosis gap

That diagnosis gap is one of the few places where `carry_forward=True` is still intentionally used.

## Commit And Postcondition

Mutation success now follows one standard rhythm:

```text
execute
  -> auto_commit()
  -> assessment lines
  -> postcondition step
  -> hash_resolve_needed observe gap
  -> compiler sees the consequence before synthesis
```

This matters most for `reprogramme_needed`, because semantic `.st` persistence is now visible on trajectory in time for the final answer.

## Assessment Vocabulary

The execution engine now depends on commit/step assessment hooks rather than freeform summaries.

These assessments are attached to:

- successful `.st` postconditions
- rogue persistence failures
- protected-surface rejections

The emitted family includes:

- `validator.status`
- `structure.*`
- `continuity.*`
- `projection.*`
- `grounding.*`
- `policy.*`
- `semantic.drift`
- `surface.*`
- `step_delta`

## Relationship To Other Modules

- [compile.py](/Users/k2invested/Desktop/cors/compile.py): chooses the active frontier
- [step.py](/Users/k2invested/Desktop/cors/step.py): defines the emitted runtime objects
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py): activates saved packages
- [loop.py](/Users/k2invested/Desktop/cors/loop.py): injects context, runs the outer turn, and persists state

The module’s job is narrower and sharper than older docs suggested: it is the lawful branch executor, not the planner and not the orchestrator.
