# loop.py

[loop.py](/Users/k2invested/Desktop/cors/loop.py) is the live turn orchestrator. It is where the runtime architecture becomes operational at turn scope.

## What The Loop Owns

The loop owns one complete turn:

- loading state
- creating the origin step
- loading identity and package context
- invoking the compiler
- injecting semantic runtime surfaces
- delegating per-gap execution into the execution engine
- synthesizing the user response
- persisting trajectory and extracted chains

If `step.py` is the object model and `compile.py` is the sequencing law, `loop.py` is the turn-level orchestrator. The actual per-gap execution core now lives in [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py).

## Session Model

The file uses a persistent `Session` backed by the chat completions API. The default model is `KERNEL_COMPOSE_MODEL` if set, otherwise `gpt-4.1`.

The session accumulates:

- the system prompt
- injected semantic context
- the model’s own prior outputs

So the loop is stateful within a turn even when individual tools are not.

## Turn Lifecycle

The implemented `run_turn()` flow is:

1. Load trajectory, chains, skills, and HEAD.
2. Build the dynamic pre-diff prompt.
3. Find unresolved dangling gaps from earlier turns.
4. Ask for the origin step.
5. Append the origin step to the trajectory.
6. Inject identity if a contact-triggered `.st` exists.
7. Create a compiler for the current turn.
8. Re-admit qualifying cross-turn gaps.
9. Emit origin gaps onto the ledger.
10. Iterate up to `MAX_ITERATIONS`.
11. Run first-contact bootstrap if this `contact_id` has no existing `on_contact` entity.
12. Synthesize the user-facing answer.
13. Persist an automatic heartbeat if background work still needs reintegration.
14. Save trajectory and chains.

That is the actual control loop in source today.

## Context Injection

The loop no longer injects only a trajectory window.

During the turn it can inject:

- a salient recent trajectory render
- resolved hashes through `resolve_hash()`
- identity and entity context
- `## Active Chain Tree` for the current ledger chain
- `## Step Network` for the current package ecology

The `Active Chain Tree` is especially important. On each iteration the loop renders the chain identified by the current ledger entry’s `chain_id`, and marks the current gap with `[focus]`. That means the model sees the live causal branch it is currently inside, not just isolated nearby hashes.

The loop also injects a one-line tree-language legend before the initial trajectory render. That keeps the render itself thin while still making richer gap dimensions legible. The render surface stays mostly hashes, descriptions, and refs; the extra structure is compressed into fixed signatures on steps and gaps.

## Hash Resolution

`resolve_hash()` currently resolves in this order:

1. skill registry
2. trajectory step
3. trajectory gap
4. persisted chain package through the manifest engine
5. Git object

Two consequences matter.

Entity-style `.st` files and executable packages share the same hash-resolution surface.

Step hashes resolve as semantic tree branches, not flat blobs. The loop renders ancestry and child gaps when a step ref is brought back into context.

## Runtime Branches

Branch selection is driven by vocab, but the branch machinery no longer lives inline in the turn loop. [loop.py](/Users/k2invested/Desktop/cors/loop.py) now hands each admitted ledger entry to [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py), which owns:

- ref resolution
- vocab routing
- tree-policy reroutes
- tool and mutation execution
- codon expansion
- commit/postcondition injection
- step recording

The same execution engine is also used by `run_command()`, so `/command` packages and ordinary turn-time gaps now share one execution path.

Observation-only paths such as `hash_resolve_needed` and `external_context` inject data and record an observation step without a mutation commit.

Observation vocabs that require tooling run through `execute_tool()`, inject the result, and then ask the model what it observed.

Mutation vocabs run through tree policy and OMO checks, then ask the model to compose the operation, execute it, commit if successful, and emit a universal postcondition gap targeting the resulting commit or post-observe path.

Bridge codons are:

- `commit_needed`
- `reason_needed`
- `await_needed`
- `reprogramme_needed`

Each has dedicated handling and may disperse child gaps from the corresponding codon `.st`.

## Tree Policy

Tree policy is enforced before a mutation is accepted as real state change.

Current behavior:

- protected immutable paths are auto-reverted
- codon mutations reject into `reason_needed`
- ordinary `skills/` mutations reroute to `reprogramme_needed`
- UI output reroutes to `stitch_needed`

This is one of the strongest architectural protections in the runtime. It distinguishes codons, packaged `.st` state, and ordinary workspace mutation as different surfaces with different laws.

## Auto-Commit And Postconditions

`auto_commit()` now returns:

- `(commit_sha, on_reject_vocab)`

After commit it immediately checks whether protected paths were modified. If so, it auto-reverts and may return an `on_reject` vocab such as `reason_needed`.

Successful mutations trigger a universal postcondition:

- create a `hash_resolve_needed` gap
- target the commit or configured post-observe path
- emit it back into the compiler

That universal postcondition is the clearest operational realization of OMO in the current runtime.

## Codons

The bridge codons are partly hardcoded and partly package-driven.

`reason_needed` is now the most complex branch. In the current implementation it can:

- emit native `reason.st`
- ask the model for a `skeleton.v1` submission and compile it through `tools/skeleton_compile.py`
- activate an existing `.st` package or compiled `.json` stepchain by hash
- schedule existing or newly compiled packages as background work

`commit_needed` can load `commit.st` if present or fall back to inline commitment reasoning.

`await_needed` can load `await.st` if present or fall back to inline await handling, while also recording the chain as awaited.

`reprogramme_needed` injects principles, registry context, and the step network, asks the model for semantic `.st` intent, routes that intent through [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py), and commits the result.

So codons are both runtime cases and packaged step systems.

## Reprogramme Pass And Heartbeat

Two behaviors make the loop more recursive than older docs suggested.

`_reprogramme_pass()` runs automatically before synthesis and asks whether entity-style semantic state should be updated from the conversation.

It also now has a deterministic first-contact bootstrap path. If no `on_contact:<id>` entity exists for the inbound contact, the pass writes a thin bootstrap entity before synthesis. That bootstrap entity carries:

- minimal identity metadata
- default access rules
- an `init` block marking the entity as still unknown / onboarding-pending

That means the second turn can inject the entity honestly without pretending the system already knows the person well.

Heartbeat persists an automatic dangling `reason_needed` gap if the compiler saw background triggers without a corresponding await. The compiler’s `background_refs()` are attached so the next turn can see which packages or chains are waiting for reintegration.

This means loop closure is not only “all current gaps resolved.” The system can preserve unfinished higher-order work across turns.

## Important Current Drift

Some of the prompt language still reaches slightly beyond what the runtime strictly supports.

There is also residual legacy vocab drift. The OMO violation path still records `"scan_needed"` even though `scan_needed` is not part of the live compiler vocab algebra.

So [loop.py](/Users/k2invested/Desktop/cors/loop.py) is the best place to understand how one turn is assembled, while [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py) is the best place to understand how one admitted gap is actually executed. The main remaining drift is not loader lossiness anymore; it is prompt and vocab convergence around the newer structural package model.
