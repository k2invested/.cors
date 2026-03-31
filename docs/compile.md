# compile.py — The Compiler

**Layer**: 1 (depends on step.py)
**Principles**: §7, §9, §10, §14, §15, §16

## Purpose

Structures execution from semantic emissions. The compiler is a sequencer that admits gaps, places them into lawful order, preserves OMO rhythm, manages chain boundaries, and monitors epistemic convergence. It is NOT a planner or search algorithm.

## Core Concept: The Ledger

The ledger is the ordered unresolved frontier — a recursively rewritten ordered agenda. Not history. Not a log. The active execution surface.

It is a **stack** (LIFO). Origin gaps enter first. Child gaps push on top. The compiler pops from the top — deepest child first. Depth-first per origin gap. One chain at a time.

### Three-part gap lifecycle

1. **Emission**: a step produces candidate gaps (LLM pre-diff output)
2. **Admission**: only gaps with admission score (0.8 * relevance + 0.2 * grounded) ≥ ADMISSION_THRESHOLD enter the ledger. Grounded is computed deterministically by the kernel from hash co-occurrence, not LLM-assessed. Below DORMANT_THRESHOLD → stored as dormant on trajectory.
3. **Placement**: admitted gaps push onto the stack at lawful position (top for children, bottom for origin gaps)

## Types

### LedgerEntry

A gap on the ledger with placement metadata.

| Field | Type | Meaning |
|-------|------|---------|
| gap | Gap | The gap being tracked |
| chain_id | str | Which chain this gap belongs to |
| depth | int | Depth in the chain (0 = origin) |
| parent_gap | str? | Gap hash that spawned this entry |
| priority | int | vocab_priority() value — lower = pops first (default 50) |

### Ledger

The stack-based ordered frontier.

| Method | Purpose |
|--------|---------|
| `push_origin(gap, chain_id)` | Push origin gap, create new chain. Sets priority from vocab_priority(). |
| `push_child(gap, chain_id, parent_gap, depth)` | Push child gap on top (depth-first). Sets priority from vocab_priority(). |
| `peek() → LedgerEntry?` | Look at top without removing |
| `pop() → LedgerEntry?` | Pop top entry — next gap to address |
| `resolve_gap(hash)` | Mark gap as resolved |
| `sort_by_priority()` | Sort stack so highest priority gaps pop first. Origins sorted by priority (internal& at top, reprogramme at bottom). Children stay on top for depth-first. |
| `chain_is_complete(chain_id) → bool` | Are all gaps in this chain resolved? |
| `is_empty() → bool` | Ledger empty = turn done |

### ChainState

Enum tracking chain lifecycle:

| State | Meaning |
|-------|---------|
| OPEN | Origin gap entered, chain created |
| ACTIVE | Currently being addressed |
| SUSPENDED | Waiting for child chain to resolve |
| CLOSED | All gaps resolved |

### GovernorSignal

| Signal | Trigger | Effect |
|--------|---------|--------|
| ALLOW | Gap is converging | Continue addressing |
| CONSTRAIN | Chain depth > MAX_CHAIN_DEPTH | Force-close chain |
| REDIRECT | Stagnation detected | Skip to next origin gap |
| REVERT | Divergence detected | Undo last mutation |
| ACT | Observe vocab with sufficient scores | Execute mutation |
| HALT | All gaps resolved or pathological | End turn |

### GovernorState

Tracks epistemic vectors across steps for convergence detection.

| Method | Purpose |
|--------|---------|
| `record(epistemic)` | Append vector to history |
| `information_gain() → float` | Delta magnitude between last two vectors |
| `is_stagnating() → bool` | No movement in STAGNATION_WINDOW steps |
| `is_diverging() → bool` | Confidence dropped > 0.15 |
| `is_oscillating() → bool` | Confidence alternating up/down |

### Compiler

The main sequencer. Owns the ledger, governor state, and chain tracking.

| Method | Purpose |
|--------|---------|
| `emit(step)` | Three-part lifecycle: emission → admission → placement |
| `emit_origin_gaps(step)` | Same but creates new chains per gap (initial pre-diff). Sorts by priority after emission: internal& first, reprogramme last. |
| `next() → (LedgerEntry?, GovernorSignal)` | Pop + govern — returns what to do next |
| `validate_omo(vocab) → bool` | Check O-M-O transition grammar |
| `record_execution(vocab, produced_commit)` | Track OMO state |
| `needs_postcondition() → bool` | True after mutation (observation must follow) |
| `resolve_current_gap(hash)` | Mark resolved, check chain completion |
| `add_step_to_chain(hash)` | Record step in active chain |
| `force_close_chain(chain_id)` | Force-close (too deep / pathological) |
| `skip_chain(chain_id)` | Move chain to bottom of stack (stagnation) |
| `is_done() → bool` | Ledger empty |
| `render_ledger() → str` | Debug view of current stack |
| `_compute_grounded(gap) → float` | Deterministic grounded score from hash co-occurrence on trajectory. Normalizes: 1 occurrence = 0.3, 3+ = 0.8+, capped at 1.0 |
| `_admission_score(gap) → float` | Compute admission: 0.8 * relevance + 0.2 * grounded. Overwrites LLM's grounded with deterministic value. Relevance-dominant — extreme relevance can enter with zero co-occurrence |

## Vocab Sets

Three disjoint sets:

**OBSERVE_VOCAB** (hash resolution / read — 4 terms):
pattern_needed, hash_resolve_needed, email_needed, external_context

**MUTATE_VOCAB** (execution / write — 7 terms):
hash_edit_needed, content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed

**BRIDGE_VOCAB** (dynamic — built from .st registry at load time):
Starts with `{"reprogramme_needed"}`. Each .st file's name becomes a valid vocab term via `register_bridge_vocab()`: admin.st -> admin_needed, research.st -> research_needed. Two types of bridge resolution: reprogramme_needed (create/update .st, internal &mut) and {entity}_needed (resolve existing .st, internal &, context injection).

Helper functions: `is_observe(vocab)`, `is_mutate(vocab)`, `is_bridge(vocab)`

### vocab_priority(vocab)

Priority ordering for the ledger. Lower number = pops first (top of stack).

| Priority | Category | Vocab |
|----------|----------|-------|
| 10 | Internal & (context bridges) | {entity}_needed (admin_needed, research_needed, etc.) |
| 20 | External & (observe) | pattern_needed, hash_resolve_needed, email_needed, external_context |
| 40 | External &mut (mutate) | hash_edit_needed, content_needed, script_edit_needed, etc. |
| 50 | Unknown | unrecognized vocab |
| 99 | Reprogramme | reprogramme_needed — runs last |

### register_bridge_vocab(skill_names)

Called by the loop after loading skills. Each .st file's name becomes a valid vocab term. Display names (kenny, clinton) are for tree rendering only — not vocab. Vocab is role-based (admin_needed), not person-based.

## Constants

| Name | Value | Purpose |
|------|-------|---------|
| ADMISSION_THRESHOLD | 0.4 | Min admission score (0.8*rel + 0.2*grounded) to enter ledger |
| CONFIDENCE_THRESHOLD | 0.8 | Gap resolved when confidence exceeds this |
| DORMANT_THRESHOLD | 0.2 | Below this → dormant (stored, not acted on) |
| MAX_CHAIN_DEPTH | 15 | Force-close beyond this |
| SATURATION_THRESHOLD | 0.05 | Info gain below this = stagnation |
| STAGNATION_WINDOW | 3 | N steps with no movement |
| CHAIN_EXTRACT_LENGTH | 8 | Chains longer than this extracted to file |

## OMO Enforcement

The compiler enforces Observe-Mutate-Observe as a transition grammar:
- Mutation requires preceding observation (`last_was_mutation` must be False)
- After mutation, postcondition must fire (automatic observation)
- Observations can follow observations (OOO is valid)

The sequence isn't planned — it emerges from vocab mapping + postcondition rules.

## Invariants

- Ledger is LIFO — deepest child popped first
- One chain at a time — depth-first per origin gap
- No consecutive mutations without observation between
- Admission requires score ≥ 0.4 (0.8*rel + 0.2*grounded; grounded is deterministic)
- Dormant gaps stored but never enter ledger
- Force-close at MAX_CHAIN_DEPTH
- OBSERVE_VOCAB ∩ MUTATE_VOCAB = ∅
- Origin gaps sorted by priority after initial emission
- BRIDGE_VOCAB is dynamic — built from .st registry, not hardcoded
