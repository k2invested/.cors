# loop.py

[loop.py](/Users/k2invested/Desktop/cors/loop.py) is the live kernel. It is where the runtime architecture becomes operational.

## What The Loop Owns

The loop owns one complete turn:

- loading state
- creating the origin step
- loading identity and package context
- invoking the compiler
- resolving hashes
- running tools
- applying tree policy
- committing mutations
- injecting postconditions
- running codon workflows
- synthesizing the user response
- persisting trajectory and extracted chains

If `step.py` is the object model and `compile.py` is the sequencing law, `loop.py` is the operational world.

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
11. Run `_reprogramme_pass()`.
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

Branch selection is driven by vocab.

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

Heartbeat persists an automatic dangling `reason_needed` gap if the compiler saw background triggers without a corresponding await. The compiler’s `background_refs()` are attached so the next turn can see which packages or chains are waiting for reintegration.

This means loop closure is not only “all current gaps resolved.” The system can preserve unfinished higher-order work across turns.

## Important Current Drift

Some of the prompt language still reaches slightly beyond what the runtime strictly supports.

`reprogramme_needed` still talks about richer `.st` structure than [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py) preserves as first-class executable fields.

There is also residual legacy vocab drift. The OMO violation path still records `"scan_needed"` even though `scan_needed` is not part of the live compiler vocab algebra.

So `loop.py` is the best place to understand what the kernel really does now, but it also shows where the prompt and builder ecology have not fully converged on the runtime law yet.
