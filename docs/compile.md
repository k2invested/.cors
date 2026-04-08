# compile.py

[compile.py](/Users/k2invested/Desktop/cors/compile.py) is the lawful sequencer. It owns frontier admission, chain lifecycle, governor signals, OMO state, and background bookkeeping.

## What It Owns

- the ledger
- admission scoring
- chain open/active/suspended/closed state
- OMO validation
- governor signals
- background-trigger bookkeeping

It does not own prompt composition, tree policy, package rendering, or `.st` persistence.

## Ledger

The ledger is the active unresolved frontier, not history.

```text
origin gaps
  -> push as roots
child gaps
  -> push on top of active chain
next()
  -> pop one active frontier entry
```

Origin roots are sorted by vocab priority. Child gaps preserve depth-first stack behavior.

## Vocab Algebra

The compiler’s live algebra remains authoritative.

Observe:

- `pattern_needed`
- `hash_resolve_needed`
- `mailbox_needed`
- `external_context`

Mutate:

- `hash_edit_needed`
- `stitch_needed`
- `content_needed`
- `command_needed`
- `email_needed`
- `json_patch_needed`
- `git_revert_needed`

Bridge:

- `reason_needed`
- `tool_needed`
- `vocab_reg_needed`
- `await_needed`
- `reprogramme_needed`

`clarify_needed` is still treated as a bounded clarification frontier, not an ordinary mutate/observe tool route.

## Admission

Admission score is still:

```text
0.8 * relevance + 0.2 * grounded
```

Grounded is recomputed deterministically from trajectory co-occurrence.

Thresholds:

- `ADMISSION_THRESHOLD = 0.4`
- `CROSS_TURN_THRESHOLD = 0.6`
- `DORMANT_PROMOTE_THRESHOLD = 0.7`
- `DORMANT_THRESHOLD = 0.2`

Cross-turn carry is now conceptually narrower than older docs suggested:

- the compiler can readmit old gaps
- the loop decides which gaps are even eligible for cross-turn readmission
- clarify carry is blocked before re-admission

## Chain Lifecycle

Current chain states:

- `OPEN`
- `ACTIVE`
- `SUSPENDED`
- `CLOSED`

The compiler still owns:

- `emit_origin_gaps(...)`
- `emit(...)`
- `next(...)`
- `resolve_current_gap(...)`
- `force_close_chain(...)`
- `skip_chain(...)`

The important runtime truth is that chains are still the compiler’s depth-first work units, even though package activation and passive chains now sit around them.

## OMO

The compiler still enforces observe-mutate-observe legality.

It currently does three things:

- blocks consecutive mutation without observation
- records whether the last executed branch mutated
- reports whether a postcondition observation is required

The postcondition itself is materialized by the loop and execution engine, not by the compiler.

## Governor

The governor is still a structural health gate, not a planner.

Signals:

- `ALLOW`
- `CONSTRAIN`
- `REDIRECT`
- `REVERT`
- `ACT`
- `HALT`

It is used for:

- max-depth constraint
- divergence revert
- oscillation/stagnation redirect
- grounded mutation upgrade to `ACT`

## Background Tracking

The background surface is live and now reason-led:

- `_background_triggers`
- `_awaited_chains`
- `_background_trigger_refs`

Exposed helpers:

- `record_background_trigger(...)`
- `record_await(...)`
- `needs_heartbeat()`
- `background_refs()`
- `manual_await_refs()`

Background triggers now include:

- current form:
  - `reason_needed` activation with `activation_ref`
- legacy compatibility:
  - `reprogramme_needed`

This is what lets the loop persist explicit await checkpoints or async heartbeats without relying on prompt memory.

## What It Does Not Own

Still outside [compile.py](/Users/k2invested/Desktop/cors/compile.py):

- `.st` tree policy
- clarify frontier merging
- route-mode coercion
- package persistence
- tool/vocab registry writes
- Discord diff notifications

So the accurate summary is unchanged in spirit: `compile.py` is the lawful sequencer, not the planner and not the persistence layer.
