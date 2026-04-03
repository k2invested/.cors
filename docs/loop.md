# loop.py

[loop.py](/Users/k2invested/Desktop/cors/loop.py) is the turn orchestrator. It assembles one conversational turn, injects the live semantic surfaces, drives the compiler/execution cycle, and persists the result.

## What It Owns

`run_turn()` owns:

1. loading trajectory, chains, skills, and git HEAD
2. composing the first-step bridge prompt
3. creating the origin step
4. injecting identity and entity context
5. creating the compiler
6. re-admitting explicit carry-forward gaps
7. iterating the active frontier through [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
8. running the pre-synthesis reprogramme pass
9. synthesizing the user response
10. persisting heartbeat frontier when necessary
11. saving state

## Prompt Law

The pre-diff prompt is now stricter than older docs implied.

Two important runtime laws are encoded there:

- use `reason_needed` before `clarify_needed` when existing context, trajectory, semantic trees, or workflows can reduce ambiguity
- treat bridge codons as primitives rather than ordinary tool routing
- derive public trigger vocab from loaded `on_vocab:` skills rather than hand-editing `vocab_registry.py`
- reserve the final public `on_vocab:*` trigger for the highest-order completed workflow

This matters because first-step behavior is the main place where the runtime decides whether a vague request becomes:

- observation
- clarification
- structural reasoning
- semantic persistence

## Context Injection

The loop injects these live surfaces:

```text
## Recent Trajectory
## Active Chain Tree
## Resolved Hash Data
## Identity / Entity Context
## Step Network
## Available Trigger Vocab
## Canonical Trigger Owners
```

The current chain render is especially important. The LLM does not work a ledger entry blind; it sees the branch it is currently inside.

## Hash Resolution

`resolve_hash()` resolves in this order:

1. loaded skill/package hash
2. trajectory step hash
3. trajectory gap hash
4. manifest-engine chain package
5. git object

Entity-like `.st` packages are resolved differently from action packages:

- entity sources inject semantic content through [_render_entity()](/Users/k2invested/Desktop/cors/loop.py)
- action packages render as package payload

Entity-source detection now includes:

- `skills/entities/*`
- [admin.st](/Users/k2invested/Desktop/cors/skills/admin.st)
- [commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st)

## Tree Policy

The current default tree policy is:

```text
skills/codons/   -> immutable, reject to reason_needed
skills/admin.st  -> reprogramme_needed, entity_editor
skills/entities/ -> reprogramme_needed, entity_editor
skills/actions/  -> reason_needed, action tree ownership
ui_output/       -> stitch_needed
kernel files     -> immutable
```

[tree_policy.json](/Users/k2invested/Desktop/cors/tree_policy.json) is merged with defaults, not substituted wholesale, so local overrides do not erase newer policy fields such as `reprogramme_mode`.

## Dangling Gaps

Cross-turn resume is no longer “all unresolved gaps”.

The implemented rule is:

- only unresolved, non-dormant gaps with `carry_forward=True` are re-admitted
- `clarify_needed` is excluded from automatic carry
- resume is deduped by gap hash

That makes successful turns self-clearing by default.

## Forced Synthesis Frontier

When synthesis is forced while the ledger still contains unresolved work, the loop materializes one carry-forward step:

```text
forced synth: unresolved frontier persisted for next turn
```

The carried gaps are cloned and marked with `carry_forward=True`. This is the main cross-turn persistence path for unfinished structural work.

## Identity Bootstrap

If a first-contact turn has no existing `on_contact:<id>` identity, the reprogramme pass can write a thin bootstrap entity before synthesis.

That bootstrap entity includes:

- minimal identity metadata
- onboarding preferences
- access rules
- `init.status = pending`

The point is continuity without pretending the system already knows the person.

## Auto-Commit

`auto_commit()` stages and commits selected paths, then immediately checks for protected-surface violations.

Possible outcomes:

- clean commit: returns `(sha, None)`
- protected-surface violation: auto-reverts and returns `(None, on_reject_vocab)`

After successful mutation, the loop and execution engine now materialize a postcondition observe step with commit assessment before synthesis.

## Assessment Surfaces

The loop owns the commit-assessment builders used after semantic persistence:

- `_commit_assessment_for_commit(...)`
- `_step_assessment_for_docs(...)`

These emit the compact projection vocabulary now visible in trajectory and Discord diff notifications:

- structure
- continuity
- projection
- grounding
- policy
- semantic drift
- surface deltas

## Heartbeat

Heartbeat persists when background work was triggered without corresponding closure.

The heartbeat gap:

- is `reason_needed`
- carries `background_refs()`
- is marked `carry_forward=True`

So background reintegration is structurally visible rather than hidden in prompt memory.
