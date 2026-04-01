# trace_tree.v1

`trace_tree.v1` is the canonical replay substrate for simulation and structural backtesting.

It is not a replacement for `trajectory.json`, and it is not a new runtime ontology. It is a derived trace layer that records how a gap configuration actually unfolded across generations, returns, sibling blocking, and reintegration.

The distinction is:

- `trajectory.json` stores execution truth
- `trace_tree.v1` stores unfolding truth

That makes `trace_tree.v1` the right object for:

- simulator replay
- compile/security backtesting
- learning natural transition grammar from real semantic trees
- showing the model how lawful multi-layer flows actually played out

## Why This Exists

Pairwise transition checking is not enough for cors.

A gap can be locally legal and still produce globally unhealthy structure once it:

- re-enters through `post_diff`
- emits child generations
- blocks siblings
- activates an embedded package
- awaits reintegration
- mutates and then fails to close under OMO

So the simulator needs a record of unfolding topology, not only adjacency.

`trace_tree.v1` is that record.

## Trace Unit

The fundamental unit is a `traceNode`.

A trace node means:

“this gap expression, when manifested in this context, unfolded with this shape and ended in this state.”

Every node has four parts:

- `gap`
- `manifestation`
- `topology`
- `outcome`

That keeps the contract aligned with the OS itself:

- the gap says what was missing
- manifestation says how it unfolded
- topology says where it sat in the branch structure
- outcome says how that local branch closed or redirected

## `gap`

The `gap` block preserves the expression that the simulator should learn from:

- `desc`
- `vocab`
- `status`
- ref counts and optionally explicit refs
- compressed score bands
- optional compact `signature`

This is not only for readability. It is the thing the simulator generalizes over.

Two trace nodes with similar `gap` expressions but different unfolding topologies are exactly the kind of evidence the simulator should compare.

## `manifestation`

This block captures what the gap did structurally.

It records:

- `kind`
- `spawn_mode`
- `spawn_trigger`
- `post_diff`
- `activation_mode`
- optional `activation_ref`
- optional `emitted_commit`
- optional `background`
- `return_policy`

This is the main bridge from gap config to execution grammar.

## `topology`

This is the part that ordinary chain storage does not express well enough.

It records:

- depth
- generation number
- child ids
- sibling position
- sibling policy
- which siblings were blocked behind this branch

This is how the simulator learns more than adjacency. It can see whether a branch unwrapped depth-first, how long siblings were deferred, and how multi-generation offspring formed before return.

## `outcome`

This captures how the local unfolding ended:

- `terminal_state`
- optional `return_target`
- optional `closure_reason`
- optional notes

This is what lets the simulator and security compiler reason about:

- clean closure
- redirection
- force-close
- await suspension
- reintegration

## Source Types

The same format can be derived from several places:

- `trajectory`
- `realized_chain`
- `stepchain`
- `skeleton`
- `semantic_skeleton`
- `manual_fixture`

That matters because the simulator should not need separate replay logic for authored structure and realized structure. They should both lower into the same trace grammar.

## Relationship To Semantic Trees

The semantic tree render is the readable surface.
`trace_tree.v1` is the machine-facing replay surface.

They should converge on the same grammar.

The semantic tree can stay thin for the model by using compact signatures.
The trace tree can stay richer for the simulator by storing the same meaning explicitly.

That means:

- the LLM reads compact tree signatures in context
- the simulator replays full trace nodes
- both are reasoning over the same structural language

## Relationship To The Security Compiler

`security_compile.v1` projects recursive execution risk from candidate structure.

`trace_tree.v1` is the right historical substrate to validate those projections.

In other words:

- `security_compile` says what is likely to happen
- `trace_tree` says what actually happened in comparable structures

That is the backtesting loop.

## Recommended Next Step

The next useful implementation is not yet a full simulator. It is a derivation tool:

- `tools/trace_tree_build.py`

That tool should be able to lower:

- a realized chain from trajectory
- a compiled `stepchain.v1`
- a skeleton via compilation

into `trace_tree.v1`.

Once that exists, the simulator can replay one canonical format instead of having to know every source form directly.
