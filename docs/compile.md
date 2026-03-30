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
2. **Admission**: only gaps with combined score ≥ ADMISSION_THRESHOLD enter the ledger. Below DORMANT_THRESHOLD → stored as dormant on trajectory.
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

### Ledger

The stack-based ordered frontier.

| Method | Purpose |
|--------|---------|
| `push_origin(gap, chain_id)` | Push origin gap, create new chain |
| `push_child(gap, chain_id, parent_gap, depth)` | Push child gap on top (depth-first) |
| `peek() → LedgerEntry?` | Look at top without removing |
| `pop() → LedgerEntry?` | Pop top entry — next gap to address |
| `resolve_gap(hash)` | Mark gap as resolved |
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
| `emit_origin_gaps(step)` | Same but creates new chains per gap (initial pre-diff) |
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

## Vocab Sets

Three disjoint sets:

**OBSERVE_VOCAB** (hash resolution / read):
scan_needed, pattern_needed, hash_resolve_needed, research_needed, email_needed, url_needed, registry_needed, external_context

**MUTATE_VOCAB** (execution / write):
content_needed, script_edit_needed, command_needed, message_needed, json_patch_needed, git_revert_needed

**BRIDGE_VOCAB** (internal bridges):
judgment_needed, task_needed, commitment_needed, profile_needed, task_status_needed

Helper functions: `is_observe(vocab)`, `is_mutate(vocab)`

## Constants

| Name | Value | Purpose |
|------|-------|---------|
| ADMISSION_THRESHOLD | 0.4 | Min combined score (0.6*rel + 0.4*gr) to enter ledger |
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
- Admission requires combined score ≥ 0.4
- Dormant gaps stored but never enter ledger
- Force-close at MAX_CHAIN_DEPTH
- OBSERVE_VOCAB ∩ MUTATE_VOCAB = ∅
