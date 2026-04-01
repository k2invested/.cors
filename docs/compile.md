# compile.py

[compile.py](/Users/k2invested/Desktop/cors/compile.py) is the lawful sequencer of the kernel. It does not plan and it does not author structure. It receives emitted gaps, decides which ones are admissible, places them on the ledger, tracks chain lifecycle, enforces the runtime OMO grammar, and carries the small amount of bookkeeping needed for heartbeat closure.

## What The Compiler Owns

The compiler owns six things:

- the ledger
- admission thresholds and grounded recomputation
- chain creation, suspension, and closure
- governor decisions over the active branch
- OMO state
- background-trigger bookkeeping

It does not own prompt composition, tool execution, codon expansion, package persistence, skeleton compilation, or semantic rendering.

## The Ledger

The ledger is the active unresolved frontier. It is not history.

`LedgerEntry` stores:

- `gap`
- `chain_id`
- `depth`
- `parent_gap`
- `priority`

`Ledger` stores:

- `stack`
- `chain_states`
- `resolved`
- `history`

The mechanics are explicit:

- origin gaps enter as chain roots
- child gaps are pushed on top
- `pop()` returns the next gap to address
- only origin gaps are re-sorted by priority
- children remain on top so depth-first behavior is preserved

That is the implemented LIFO surface the loop works over.

## Vocab Algebra

The compiler’s live vocab sets are still the authoritative execution algebra.

Observe:

- `pattern_needed`
- `hash_resolve_needed`
- `mailbox_needed`
- `external_context`
- `research_needed`

Mutate:

- `hash_edit_needed`
- `stitch_needed`
- `content_needed`
- `script_edit_needed`
- `command_needed`
- `email_needed`
- `json_patch_needed`
- `git_revert_needed`

Bridge:

- `reason_needed`
- `await_needed`
- `commit_needed`
- `reprogramme_needed`
- `clarify_needed`

`vocab_priority()` is the runtime sort key:

- `clarify_needed` -> `15`
- observe -> `20`
- mutate -> `40`
- unknown -> `50`
- `reason_needed` -> `90`
- `await_needed` -> `95`
- `commit_needed` -> `98`
- `reprogramme_needed` -> `99`

Because the ledger is LIFO, larger numbers sink lower and therefore fire later.

## Admission

Admission becomes deterministic once the model has supplied `relevance` and `confidence`.

Important constants:

- `ADMISSION_THRESHOLD = 0.4`
- `CROSS_TURN_THRESHOLD = 0.6`
- `DORMANT_PROMOTE_THRESHOLD = 0.7`
- `DORMANT_THRESHOLD = 0.2`
- `MAX_CHAIN_DEPTH = 15`
- `CHAIN_EXTRACT_LENGTH = 8`
- `SATURATION_THRESHOLD = 0.05`
- `STAGNATION_WINDOW = 3`
- `CONFIDENCE_THRESHOLD = 0.8`

Grounded is recomputed in the compiler from trajectory co-occurrence. The model’s self-assessed grounded value is not trusted.

Admission score is:

`0.8 * relevance + 0.2 * grounded`

Thresholds are tiered:

- fresh gaps use `ADMISSION_THRESHOLD`
- cross-turn dangling gaps use `CROSS_TURN_THRESHOLD`
- dormant re-promotions use `DORMANT_PROMOTE_THRESHOLD`

Anything below `DORMANT_THRESHOLD` is stored as dormant and never reaches the ledger.

The main admission paths are:

- `emit(step)` for child-gap admission
- `emit_origin_gaps(step)` for origin-gap admission
- `readmit_cross_turn(gaps, step_hash)` for dangling-gap resumption

One important accuracy note: cross-turn readmission creates fresh chain roots from the old gap. It does not restore exact previous ledger placement.

## Chains

The compiler’s chain lifecycle is represented by `ChainState`:

- `OPEN`
- `ACTIVE`
- `SUSPENDED`
- `CLOSED`

The active chain matters operationally. `emit()` pushes child gaps into the current chain, `next()` updates `self.active_chain` when a ledger entry is popped, `resolve_current_gap()` closes a chain when its remaining stack entries are gone, and `skip_chain()` or `force_close_chain()` provide structural escape hatches when the governor decides the branch should not continue normally.

This is the mechanical backbone for depth-first branch progression.

## Governor

The governor is intentionally narrow. It operates on epistemic vectors and emits:

- `ALLOW`
- `CONSTRAIN`
- `REDIRECT`
- `REVERT`
- `ACT`
- `HALT`

In the current implementation it mainly does four things:

- force-closes chains that exceed `MAX_CHAIN_DEPTH`
- reverts on divergence
- redirects on oscillation or stagnation
- upgrades mutate gaps to `ACT` when grounded and confidence are both at least `0.5`

It is not a planner. It is a structural health gate over the active branch.

## OMO

The compiler owns the runtime OMO grammar.

The relevant methods are:

- `validate_omo(vocab)`
- `record_execution(vocab, produced_commit)`
- `needs_postcondition()`

What it actually enforces:

- no consecutive mutations without an intervening observation
- mutation state persists through `last_was_mutation`
- the loop can ask whether a postcondition observation is required

What it does not do:

- inject the postcondition gap
- resolve the postcondition

Those still happen in [loop.py](/Users/k2invested/Desktop/cors/loop.py).

## Background Tracking

The compiler now has a more explicit background surface than older docs described.

It tracks:

- `_background_triggers`
- `_awaited_chains`
- `_background_trigger_refs`

And exposes:

- `record_background_trigger(chain_id, refs=None)`
- `record_await(chain_id)`
- `needs_heartbeat()`
- `background_refs()`

This lets the loop persist a heartbeat `reason_needed` gap after synthesis and attach unresolved background package refs that should be revisited next turn.

## What It Does Not Do

It is important not to overstate `compile.py`.

It does not:

- understand skeletons or semantic skeletons
- validate `skeleton.v1`
- compile packages
- resolve hashes
- render trees
- know `.st` file schemas

Those jobs live in:

- [tools/skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/skeleton_compile.py)
- [tools/semantic_skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/semantic_skeleton_compile.py)
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)

So `compile.py` is exactly what its name suggests: runtime sequencing law, not author-time planning.

Three limits are worth recording explicitly.

`CONFIDENCE_THRESHOLD` exists but is not the main resolution path. Actual gap closure happens through chain handling and loop routing, not a simple confidence-triggered resolution.

The vocab algebra is stricter than some older docs and helper surfaces. Legacy terms such as `scan_needed` and `url_needed` are outside the live compiler surface. `research_needed` is now part of the live observe surface, while deeper search/fetch terms remain package-scoped inside research workflows.

The governor is deliberately lightweight. If you want richer planning calculus or whole-workflow validation, that lives in the skeleton compilers, not here.
