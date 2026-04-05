# loop.py

[loop.py](/Users/k2invested/Desktop/cors/loop.py) is the outer turn orchestrator.

## What It Owns

`run_turn()` does the outer work:

1. load trajectory, extracted chain index, skills, and HEAD
2. create the origin step
3. inject identity and recent runtime context
4. build the compiler
5. iterate admitted gaps through [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
6. synthesize the final reply
7. persist state

## Runtime Context

The loop injects the live surfaces the model reasons over:

- recent trajectory
- active chain tree
- resolved hash data
- identity/entity context
- step network
- trigger vocab ownership

The active chain render is the main structural context surface.

## Routing Rules

Current tree policy:

```text
skills/codons/   -> immutable, reject to reason_needed
skills/admin.st  -> reprogramme_needed, entity_editor
skills/entities/ -> reprogramme_needed, entity_editor
skills/actions/  -> reason_needed
tools/           -> tool_needed
vocab_registry.py -> vocab_reg_needed
system/          -> immutable, reject to reason_needed
ui_output/       -> stitch_needed
```

This means:

- `reason_needed` activates structural work
- `tool_needed` owns tool-tree writes
- `vocab_reg_needed` owns configurable semantic routing
- `reprogramme_needed` owns entity/admin persistence

## Observe / Mutate Rhythm

The live model is simpler now:

- observations surface relevant next gaps
- mutations do not directly expand the ledger
- successful mutations trigger post-observation

For file-backed work, the post-observation route usually lands back on hash resolution.

## Hash Resolution

The loop still owns the kernel-side `hash_resolve_needed` behavior. It resolves:

- skill/package hashes
- step hashes
- gap hashes
- chain/package refs
- git objects
- workspace paths

It also routes supported file types through specialized hash-resolve handlers while keeping the public surface unified under the hash primitive.

## Carry-Forward

Cross-turn persistence is explicit:

- only unresolved gaps with `carry_forward=True` are re-admitted
- `clarify_needed` does not automatically carry
- forced synthesis persists unresolved work as one explicit carry-forward step

## Auto-Commit

Successful mutation follows the same outer rhythm:

```text
execute mutation
  -> auto_commit()
  -> attach assessment
  -> emit post-observe gap
  -> continue iteration
```

That keeps the consequence visible to the model before synthesis.

## Isolated Child Workflows

The loop now owns isolated workflow execution:

- [trajectory_store/command](/Users/k2invested/Desktop/cors/trajectory_store/command)
  - extracted chains from the main command flow
- [trajectory_store/subagent](/Users/k2invested/Desktop/cors/trajectory_store/subagent)
  - isolated subagent flow storage
- [trajectory_store/background_agent](/Users/k2invested/Desktop/cors/trajectory_store/background_agent)
  - isolated background workflow storage

`run_isolated_workflow_ref(...)` executes a child workflow in one of those stores and persists an alias by `activation_ref` so the parent can resolve the child tree by hash.

## Await And Reintegration

The parent-side law is now:

- `reason_needed` chooses whether child activation sets `await_needed`
- `await_needed=true`
  - parent gets an explicit `await_needed` checkpoint before synthesis
- `await_needed=false`
  - parent gets a post-synth `reason_needed` heartbeat instead

In both cases, the child semantic tree is the reintegration surface.
