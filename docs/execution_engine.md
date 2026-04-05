# execution_engine.py

[execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py) is the per-gap runtime executor.

## What It Owns

`execute_iteration(...)` takes one admitted gap and does:

```text
resolve refs
  -> apply tree policy
  -> route by vocab
  -> execute observation or mutation
  -> emit resulting step
  -> attach post-observe or reintegration consequences
```

## Main Objects

- `ExecutionHooks`
- `ExecutionConfig`
- `ExecutionOutcome`
- `execute_iteration(...)`

The module receives git, tool execution, parsing, isolated-runner, and policy hooks instead of owning those systems directly.

## Clarify

Clarification is still one bounded frontier step:

- collect current-turn clarify gaps
- dedupe them
- emit one clarify step
- stop iteration for the turn

## Observation Paths

Three observation modes remain:

- observation-only
  - inject result, no child-gap articulation
- deterministic observation
  - kernel resolves directly, then the model interprets
- normal observation
  - resolve, then parse a step plus any child gaps

## Mutation Paths

Mutation first passes through tree policy and target-path inference.

Current important reroutes:

- `tools/*` mutation -> `tool_needed`
- `skills/actions/*` mutation -> `reason_needed`
- entity/admin `.st` mutation -> `reprogramme_needed`
- `vocab_registry.py` mutation -> `vocab_reg_needed`

## reason_needed

`reason_needed` is the judgment and activation branch.

Its job is to:

- reduce ambiguity
- choose the next concrete move
- surface the next executable gap
- decide whether the work belongs to:
  - a normal tool-backed step
  - `tool_needed`
  - `vocab_reg_needed`
  - `reprogramme_needed`
  - later, `chain_needed`

It can also activate a child workflow directly with a minimal payload:

```json
{"activate_ref":"<workflow-hash>","prompt":"task for the child workflow","await_needed":true}
```

or the same shape with `await_needed=false`.

## Child Activation

When `reason_needed` emits that payload:

- `activate_ref`
  - the target child workflow hash
- `prompt`
  - the child task framing
- `await_needed=true`
  - parent gets an `await_needed` checkpoint before synthesis
- `await_needed=false`
  - parent gets post-synth `reason_needed` reintegration

The executor launches the child through the isolated workflow hook and records the activation on the parent chain.

## tool_needed And vocab_reg_needed

`tool_needed` is the tool-tree mutation branch.

It receives:

- the current request
- the public tool registry
- the tool builder scaffold path

It writes tools that already contain registry-derived contract metadata and reintegrates through `reason_needed`.

`vocab_reg_needed` is the semantic routing branch.

It receives:

- the current request
- the public tool registry
- the public chain registry
- the current configurable vocab registry

It updates configurable semantic routes in [vocab_registry.py](/Users/k2invested/Desktop/cors/vocab_registry.py) and also reintegrates through `reason_needed`.

## reprogramme_needed

`reprogramme_needed` remains the semantic persistence branch.

It injects:

- existing entity data
- [PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md)
- step network
- an editable semantic frame

Then it persists entity/admin state through [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py).

It is not the owner of workflow origination.

## Rogue Handling

Failures that matter become explicit rogue steps with diagnostic metadata instead of disappearing into raw tool output.

That includes:

- `rogue_kind`
- `failure_source`
- `failure_detail`
- `assessment`

## Post-Observe Rhythm

The mutation rhythm is:

```text
execute
  -> auto_commit()
  -> attach assessment
  -> create post-observe gap
  -> continue iteration
```

For ordinary mutations, post-observe usually re-enters through `hash_resolve_needed`.

For foundational bridge writers:

- `tool_needed -> reason_needed`
- `vocab_reg_needed -> reason_needed`
