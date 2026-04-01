# loop.py

`loop.py` is the live kernel. It is where the runtime architecture becomes concrete.

## What The Loop Owns

The loop owns one complete turn:

- loading state
- creating the origin step
- loading identity
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

The file uses a persistent `Session` object backed by the OpenAI chat completions API. The model defaults to:

- `KERNEL_COMPOSE_MODEL`
- or `gpt-4.1` if unset

The session accumulates:

- system prompt
- injected context
- the model’s own prior outputs

This means the loop is stateful within a turn even when individual tools are not.

## Turn Lifecycle

The current `run_turn()` flow is:

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

That is the actual control loop today.

## Hash Resolution

`resolve_hash()` currently resolves in this order:

1. skill registry
2. trajectory step
3. trajectory gap
4. Git object

Two consequences follow from that:

Entity-style `.st` files are resolved through the same hash-resolution surface as everything else.

Step hashes resolve as semantic tree branches, not as flat blobs. The loop renders ancestry and child gaps when injecting a step reference back into context.

## Execution Branches

The runtime branch selection is driven by vocab.

Observation-only:

- `hash_resolve_needed`
- `external_context`

These inject data and record a blob-like step with no post-diff branching.

Deterministic:

- currently only `hash_resolve_needed`

This path resolves data directly and then asks the model to articulate any resulting child gaps.

Observation:

- any `is_observe(vocab)` term not handled as observation-only

The loop executes a tool if needed, injects the result, and asks the model what it observed.

Mutation:

- any `is_mutate(vocab)` term

The loop checks policy, validates OMO, asks the model to compose an action, executes it, commits if successful, and injects a universal postcondition gap targeting the resulting commit or post-observe path.

Bridge codons:

- `commit_needed`
- `reason_needed`
- `await_needed`
- `reprogramme_needed`

These each have dedicated handling and may disperse child gaps from the corresponding codon `.st`.

## Tree Policy

Tree policy is enforced before a mutation is accepted as real state change.

Current behavior:

- protected immutable paths are auto-reverted
- codon mutations reject into `reason_needed`
- ordinary `skills/` mutations reroute to `reprogramme_needed`
- UI output reroutes to `stitch_needed`

This is one of the most important architectural protections in the codebase. It already distinguishes codons from general `.st` files and `.st` files from ordinary workspace mutation.

## Auto-Commit

`auto_commit()` now returns a tuple:

- `(commit_sha, on_reject_vocab)`

After commit it immediately checks whether protected paths were modified. If so, it auto-reverts and may hand back an `on_reject` vocab such as `reason_needed`.

Successful mutations trigger a universal postcondition:

- create a `hash_resolve_needed` gap
- target the commit or configured post-observe path
- emit it back into the compiler

That postcondition is one of the clearest operational realizations of OMO in the current system.

## Codon Handling

The bridge codons are partly hardcoded and partly package-driven.

`reason_needed`
Loads `reason.st` if available and disperses its steps as child gaps. If not, the loop falls back to inline reasoning.

`commit_needed`
Loads `commit.st` if available and reintegrates commitment structure. Otherwise it falls back to inline reasoning.

`await_needed`
Loads `await.st` if available and records a manual await on the chain. Otherwise it falls back to inline reasoning.

`reprogramme_needed`
Loads current entity context, injects principles and registry context, asks the model for `.st` intent, routes that intent through `tools/st_builder.py`, and commits the result.

In other words, codons are both runtime cases and packaged step systems.

## Reprogramme Pass And Heartbeat

Two behaviors in `loop.py` make the architecture more recursive than the old docs implied.

`_reprogramme_pass()`
Runs automatically before synthesis and asks whether any entity-style `.st` state should be updated from the conversation.

Heartbeat
If the compiler saw background triggers without a corresponding await, the loop persists an automatic dangling `reason_needed` gap for the next turn.

These are important because they mean loop closure is not only “all current gaps resolved.” The system also preserves unfinished higher-order work across turns.

## Important Current Drift

Some of the prompt language is broader than the runtime actually supports.

For example, `reprogramme_needed` prompt text still talks about composing richer `.st` structures than `skills/loader.py` currently preserves as first-class executable fields.

There is also residual legacy vocab drift in the loop.
The OMO violation path still records `"scan_needed"` even though `scan_needed` is not part of the current executable vocab algebra.

So `loop.py` is the best place to understand what the kernel really does today, but it also exposes where the surrounding prompt and builder ecology has not fully converged on the current runtime law.
