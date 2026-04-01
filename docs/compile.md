# compile.py

`compile.py` is the lawful sequencer of the kernel. It does not invent plans. It decides which emitted gaps are admissible, how they are ordered, when a chain should be redirected or force-closed, and how OMO is enforced.

## The Ledger

The ledger is the active unresolved frontier. It is not history.

The current implementation is explicitly stack-shaped:

- origin gaps are pushed as chain roots
- child gaps are pushed on top
- the compiler pops from the top

That gives you depth-first execution within a lawful ordered frontier.

`LedgerEntry` stores:

- the gap itself
- `chain_id`
- `depth`
- `parent_gap`
- `priority`

`Ledger` stores:

- `stack`
- `chain_states`
- `resolved`
- `history`

Only origin gaps are re-sorted by priority. Child gaps stay on top so depth-first behavior is preserved.

## Chain Lifecycle

The compiler tracks four chain states:

- `OPEN`
- `ACTIVE`
- `SUSPENDED`
- `CLOSED`

This is more than bookkeeping. `skip_chain()` suspends a chain when the governor redirects, and background tracking later uses chain identity when deciding whether a heartbeat is needed.

## Admission

Gap admission is deterministic once the model has emitted `relevance` and `confidence`.

Constants:

- `ADMISSION_THRESHOLD = 0.4`
- `CROSS_TURN_THRESHOLD = 0.6`
- `DORMANT_PROMOTE_THRESHOLD = 0.7`
- `CONFIDENCE_THRESHOLD = 0.8`
- `DORMANT_THRESHOLD = 0.2`
- `MAX_CHAIN_DEPTH = 15`
- `SATURATION_THRESHOLD = 0.05`
- `STAGNATION_WINDOW = 3`
- `CHAIN_EXTRACT_LENGTH = 8`

Admission score is:

`0.8 * relevance + 0.2 * grounded`

Grounded is recomputed from trajectory co-occurrence. The LLM does not control it.

Thresholds are tiered:

- fresh gaps use `ADMISSION_THRESHOLD`
- dangling cross-turn gaps use `CROSS_TURN_THRESHOLD`
- dormant promotions use `DORMANT_PROMOTE_THRESHOLD`

Anything below `DORMANT_THRESHOLD` is stored as dormant and never enters the ledger.

## Governor

The governor is deterministic and intentionally simple. It operates on epistemic vectors and emits one of:

- `ALLOW`
- `CONSTRAIN`
- `REDIRECT`
- `REVERT`
- `ACT`
- `HALT`

The logic currently does four main things:

- force-closes chains that exceed max depth
- reverts on divergence
- redirects on oscillation or stagnation
- upgrades mutate gaps to `ACT` when grounded and confidence are both at least `0.5`

This is not a search controller. It is closer to a structural gate over chain health.

## OMO

The compiler still enforces observe-mutate-observe rhythm.

In code that means:

- consecutive mutations are blocked by `validate_omo()`
- `record_execution()` tracks whether the last step produced a commit
- `needs_postcondition()` marks the requirement for observation after mutation

The actual postcondition injection is done in `loop.py`, but the grammar belongs to the compiler.

## Runtime Vocab Algebra

The executable vocab surface in the compiler is:

Observe:

- `pattern_needed`
- `hash_resolve_needed`
- `email_needed`
- `external_context`
- `clarify_needed`

Mutate:

- `hash_edit_needed`
- `stitch_needed`
- `content_needed`
- `script_edit_needed`
- `command_needed`
- `message_needed`
- `json_patch_needed`
- `git_revert_needed`

Bridge:

- `reprogramme_needed`
- `reason_needed`
- `commit_needed`
- `await_needed`

Priority ordering is currently:

- observe: `20`
- mutate: `40`
- unknown: `50`
- `reason_needed`: `90`
- `await_needed`: `95`
- `commit_needed`: `98`
- `reprogramme_needed`: `99`

That ordering matters because the stack is LIFO. Higher priority numbers sink lower and therefore fire later.

## Background Tracking

The current compiler also has a small but important background mechanism.

It tracks:

- `_background_triggers`
- `_awaited_chains`

From that it derives `needs_heartbeat()`, which is how `loop.py` decides whether to persist an automatic `reason_needed` dangling gap after synthesis.

This is one of the places where the actual architecture is richer than the older docs suggested. The system already has a structural notion of background work and reintegration.

## Where The Code Still Drifts

There are a few mismatches worth documenting plainly.

The compiler’s vocab algebra is stricter than parts of the surrounding system.
Some tools and `.st` files still reference legacy terms such as `scan_needed`, `research_needed`, and `url_needed`, but those are not part of `OBSERVE_VOCAB`, `MUTATE_VOCAB`, or `BRIDGE_VOCAB`.

`CONFIDENCE_THRESHOLD` exists but is not currently the main resolution path.
Most gap resolution in practice happens through chain handling in `loop.py`, not through a direct “confidence crossed threshold” transition.

The governor is intentionally lightweight.
If you read the principles as implying a more expressive planning calculus, that richer structure does not live here yet. `compile.py` is still the sequencing law, not the author-time planner.
