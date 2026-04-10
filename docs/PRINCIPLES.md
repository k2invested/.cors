# Principles — cors v5

## Constraint Orchestration Reasoning System

This document is the architectural source of truth for cors.

cors is a hash-native reasoning agent built on one recursive primitive: `step()`.
The LLM produces meaning. The kernel produces structure. The LLM does not own sequencing. The kernel does not own semantics. The system works only because those roles stay separate.

Every mechanism below is current runtime truth unless explicitly marked as future-facing.

The document is intentionally layered. It unwraps the system from the smallest primitive outward:

```text
step
  -> gap
  -> chain
  -> manifestation
  -> registry/routing
  -> execution law
  -> reintegration
  -> persistent system shape
```

The purpose of the principles is not to list components in isolation. It is to show how those mechanisms compound into one operating system.

## §1. The Step Primitive

A step is meaningful movement.

It is not a snapshot, not a state, and not a message. It is the transition between states. Every behavior in cors is expressed as a step at some scale:

- observation
- mutation
- reasoning
- semantic persistence
- workflow activation
- reintegration

So the first layer is:

```text
step
  -> can observe
  -> can mutate
  -> can judge
  -> can persist
  -> can activate other structure
```

Every later mechanism in the system is just a structured consequence of that primitive.

### Two-phase transition

Every step has two layers:

1. semantic articulation
   - what the LLM thinks is missing or should happen next
2. structural actualization
   - how the kernel admits, sequences, and persists that articulation

The system does not execute free text directly. It executes step-shaped structure.

### Two hash layers

Hashes are the primary persistent identity surface.

- content hashes
  - identify skill files, tools, extracted chains, and artifacts
- runtime hashes
  - identify steps, gaps, and active structural objects

Paths are convenience surfaces. Hashes are canonical.

### The single persistent session

cors has one persistent trajectory.

That trajectory contains:

- turn history
- step history
- extracted chain references
- unresolved carry-forward work

There is no separate “memory subsystem” for execution concerns. The trajectory is the memory substrate.

### Step notes are first-class semantic state

Every step may carry an explicit `StepNote`.

That note is not cosmetic metadata. It is the persisted semantic comparison surface the runtime uses so later reasoning can understand what an artifact, entity, or judgment step actually contained without always reopening the full resolved source.

The current runtime split is:

- observation steps
  - may receive stateless rich artifact/entity notes
- reasoning steps
  - should persist explicit judgment notes

So a step is no longer just:

- desc
- refs
- emitted gaps

It is also:

- a durable semantic note
- a compare/contrast record
- a local drift and mutation assessment

### Mechanism tree

```text
step primitive
├─ semantic articulation
│  ├─ user-facing intent
│  ├─ model judgment
│  ├─ proposed next movement
│  └─ persisted step note
├─ structural actualization
│  ├─ step hash
│  ├─ refs
│  ├─ timestamps
│  └─ persisted trajectory entry
└─ persistence substrate
   ├─ trajectory.json
   ├─ chains.json
   ├─ extracted chain stores
   └─ note-rich semantic history
```

### Code mechanisms

- [step.py](/Users/k2invested/Desktop/cors/step.py)
- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)

## §2. Gap Emission and Manifestation

A gap is the system’s unit of unfinished work.

A gap is emitted when the model identifies a missing observation, a required mutation, a needed semantic persistence step, or a judgment branch.

This is the first compounding layer:

```text
step
  -> emits gap
  -> gap creates unresolved structure
  -> unresolved structure becomes a chain if descendants form
```

### Lifecycle

```text
LLM perceives missing work
  -> emits gap
  -> compiler scores and admits it
  -> execution_engine actualizes it
  -> resulting step may emit child gaps
  -> chain resolves or persists
```

### Passive chain building

Chains are not manually maintained ledgers. They emerge from admitted gaps and their descendants.

That means:

- a task is a currently active chain
- a resolved concern is a closed chain
- a long concern that survives turns is a persisted chain reference plus unresolved frontier

So the second layer is:

```text
step
  -> gap
  -> gap admitted by compiler
  -> admitted gaps compound into chains
```

### Mechanism tree

```text
gap emission
├─ source
│  ├─ observation result
│  ├─ user request
│  ├─ reasoning branch
│  └─ semantic persistence need
├─ gap object
│  ├─ vocab
│  ├─ desc
│  ├─ relevance/confidence
│  ├─ step refs
│  ├─ content refs
│  └─ carry-forward eligibility
├─ compiler admission
│  ├─ score
│  ├─ priority
│  ├─ stack placement
│  └─ dormancy or activation
└─ chain formation
   ├─ child gaps
   ├─ depth-first branch
   ├─ persistent concern
   └─ note-bearing step lineage
```

### Code mechanisms

- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- [step.py](/Users/k2invested/Desktop/cors/step.py)

## §3. The Manifestation Engine

The manifestation engine turns authored packages and admitted gaps into runtime-visible structure.

This is where the raw chain becomes differentiated mechanism.

### `.st` classes

There are three important `.st` classes:

- entity packages
  - `skills/admin.st`
  - `skills/entities/*`
- action packages
  - `skills/actions/*`
- codons
  - `skills/codons/*`

These share storage format but not runtime meaning.

### Ownership split

The current ownership model is:

- `reason_needed`
  - stateful judgment
  - routing
  - child-workflow activation
- `tool_needed`
  - tool authoring
- `vocab_reg_needed`
  - semantic routing configuration
- `reprogramme_needed`
  - semantic persistence for entity/admin state

`chain_needed` is planned but not implemented yet.

The note layer cuts across that ownership split:

- `hash_resolve_needed`
  - resolves artifacts/entities and may attach rich observation notes
- `reason_needed`
  - reasons over the semantic tree and persists explicit judgment notes

This layer matters because not every step-shaped thing should be handled by the same branch:

```text
step
  -> gap
  -> chain
  -> manifestation selects the correct owner
     -> reason
     -> tool writer
     -> vocab writer
     -> semantic persistence
```

### Current kernel vocab

#### Observe

| Vocab | Priority | Meaning |
| --- | --- | --- |
| `hash_resolve_needed` | 20 | Resolve hash/path/git refs into observable context. |
| `pattern_needed` | 20 | Search workspace content deterministically. |
| `mailbox_needed` | 20 | Read email-related state. |
| `external_context` | 20 | Passive external-context injection only. |

#### Mutate

| Vocab | Priority | Meaning |
| --- | --- | --- |
| `hash_edit_needed` | 40 | Workspace mutation through the hash primitive. |
| `content_needed` | 40 | New workspace content through the hash primitive. |
| `stitch_needed` | 40 | UI artifact generation. |
| `bash_needed` | 40 | Shell mutation. |
| `email_needed` | 40 | Email/message send. |
| `json_patch_needed` | 40 | Structured JSON mutation via hash manifest. |
| `git_revert_needed` | 40 | Git revert operations. |

#### Foundational bridges

| Vocab | Priority | Meaning |
| --- | --- | --- |
| `clarify_needed` | 20 | User-only clarification frontier. |
| `reason_needed` | 90 | Judgment, routing, and child activation. |
| `tool_needed` | 92 | Tool authoring branch. |
| `vocab_reg_needed` | 93 | Configurable vocab routing branch. |
| `await_needed` | 95 | Optional synchronization checkpoint. |
| `reprogramme_needed` | 99 | Semantic persistence branch. |

### Deterministic auto-routes

| Target matches | Reroutes to | Meaning |
| --- | --- | --- |
| `skills/admin.st` | `reprogramme_needed` | Canonical semantic persistence path. |
| `skills/entities/*` | `reprogramme_needed` | Entity persistence path. |
| `skills/actions/*` | `reason_needed` | Structural workflow work belongs to reason first. |
| `tools/*` | `tool_needed` | Tool-tree mutation is diverted into the tool writer path. |
| `vocab_registry.py` | `vocab_reg_needed` | Configurable semantic routing is isolated. |
| `system/*` | immutable -> `reason_needed` on reject | Infrastructure is protected. |

### Universal post-observation

The mutation law is:

```text
mutate
  -> auto-commit
  -> attach assessment
  -> post-observe
```

For ordinary mutation tools, post-observe usually re-enters through `hash_resolve_needed`.

For foundational bridge writers:

- `tool_needed -> reason_needed`
- `vocab_reg_needed -> reason_needed`

This is the point where the mechanisms start interacting as one system:

```text
tree policy
  -> constrains where mutation may land
registry
  -> constrains what is public and selectable
post-observe law
  -> constrains how successful mutation re-enters
```

### Mechanism tree

```text
manifestation layer
├─ vocab
│  ├─ observe
│  │  ├─ hash_resolve_needed
│  │  ├─ pattern_needed
│  │  ├─ mailbox_needed
│  │  └─ external_context
│  ├─ mutate
│  │  ├─ hash_edit_needed
│  │  ├─ content_needed
│  │  ├─ stitch_needed
│  │  ├─ bash_needed
│  │  ├─ email_needed
│  │  ├─ json_patch_needed
│  │  └─ git_revert_needed
│  └─ foundational bridges
│     ├─ clarify_needed
│     ├─ reason_needed
│     ├─ tool_needed
│     ├─ vocab_reg_needed
│     ├─ await_needed
│     └─ reprogramme_needed
└─ note layer
   ├─ observation notes
   │  └─ stateless artifact/entity note generation
   └─ reasoning notes
      └─ explicit judgment notes persisted by reason_needed
```

### Registry tree

```text
system/tool_registry.py
├─ public tool contracts by blob hash
├─ public tool paths
└─ post-observe/artifact contract derivation

system/chain_registry.py
├─ public action-chain contracts by blob hash
├─ activation/default-gap/OMO derivation
├─ activation payload defaults
│  ├─ activate_ref
│  ├─ prompt
│  ├─ content refs
│  └─ step refs
└─ embedded public tool refs

system/hash_registry.py
├─ internal file-type routing behind hash_resolve/hash_manifest
└─ hidden handlers under tools/hash/*
```

### Code mechanisms

- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py)
- [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py)
- [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py)
- [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py)
- [vocab_registry.py](/Users/k2invested/Desktop/cors/vocab_registry.py)

## §4. Formal Gap Configuration

Gap configuration is now thinner than older versions of cors.

The system no longer treats authored gap config as the main source of execution truth. Execution truth now lives primarily on tools, chains, and runtime laws.

That means the system now composes from three layers instead of overloading one:

```text
gap
  -> says what is missing
registry target
  -> says what executable thing exists
runtime law
  -> says how that thing re-enters and compounds
```

### Configuration axes

The remaining meaningful axes are:

- vocab
- relevance
- confidence
- content refs
- step refs
- carry-forward eligibility

The system does not need authored mutation internals like:

- tool-specific post-observe rules
- artifact routing on vocab
- deep manifestation metadata on every gap

Those are derived elsewhere.

### Admission thresholds

The current admission scores remain:

- fresh gaps: `0.4`
- cross-turn gaps: `0.6`
- dormant promotion: `0.7`
- dormant boundary: `0.2`

### Invariant

A gap is immutable after creation.

The kernel may admit, defer, suspend, or close it, but it does not retroactively rewrite the gap’s identity.

### Mechanism tree

```text
gap configuration
├─ authored fields
│  ├─ vocab
│  ├─ step refs
│  ├─ content refs
│  ├─ scores
│  └─ carry-forward signal
├─ derived execution truth
│  ├─ tool contract
│  ├─ chain contract
│  ├─ tree-policy route
│  └─ carried content expansion through cited steps
└─ compiler controls
   ├─ admission threshold
   ├─ dormancy
   ├─ suspension
   └─ closure
```

### Code mechanisms

- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- [step.py](/Users/k2invested/Desktop/cors/step.py)

## §5. Reprogramme: The Semantic State Engine

`reprogramme_needed` is the semantic persistence primitive.

It is not tool creation, not chain construction, and not general background workflow activation.

This section exists to keep one layer narrow so the higher-order layers stay clean.

### What it owns

It owns persistence of:

- admin preferences
- entity state
- semantic identity surfaces
- stable domain scope or constraints

### Structural relation to reason

`reason_needed` decides whether semantic persistence is warranted.

`reprogramme_needed` performs the persistence once that judgment is already made.

### State update cycle

```text
user/input/context implies semantic state change
  -> reason_needed decides persistence is warranted
  -> reprogramme_needed actualizes the state write
  -> updated entity/admin package becomes future context
```

### Mechanism tree

```text
semantic persistence
├─ reason judgment
│  └─ decides persistence is warranted
├─ reprogramme_needed
│  ├─ admin/entity targeting
│  ├─ semantic frame
│  └─ persistence request
├─ st_builder actualization
│  ├─ validate package
│  ├─ write .st
│  └─ preserve structure
└─ future context injection
   ├─ admin.st
   └─ skills/entities/*
```

### Code mechanisms

- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)
- [skills/admin.st](/Users/k2invested/Desktop/cors/skills/admin.st)

## §6. Standardized Definitions and Referred Context

### Referred context is hashes

Referred context should be carried by hashes whenever possible.

Examples:

- tool refs
- chain refs
- step refs
- gap refs
- skill refs
- extracted chain refs

Paths may still be accepted at resolution time, but they are not the preferred persistent identity surface.

### Step refs carry content forward

`step_refs` are not just citations to earlier reasoning. They are also a lawful way to carry forward the observable content already grounded by those cited steps.

At resolution time the runtime now:

- resolves the cited step lineage
- expands `content_refs` from the referenced steps
- merges and deduplicates those carried refs with the current `content_refs`

So referred context is now two-layered:

- direct cited execution lineage through `step_refs`
- direct and carried observable artifacts through `content_refs`

This matters because later reasoning can follow the semantic lineage of a prior step and still inherit the concrete artifact surface that step was grounded in.

### Citation rule

Every nontrivial step should be grounded in one or more of:

- prior step refs
- content refs
- carried content refs inherited from cited steps
- persisted step notes
- resolved observable state
- direct user input

The system should not mutate from an ungrounded void.

### Mechanism tree

```text
referred context
├─ hash-native references
│  ├─ tool refs
│  ├─ chain refs
│  ├─ skill refs
│  ├─ step refs
│  └─ gap refs
├─ resolution surfaces
│  ├─ hash_resolve
│  ├─ carried content expansion from step refs
│  ├─ manifest lookup
│  └─ git/path convenience inputs
└─ grounding rule
   ├─ prior execution
   ├─ resolved content
   ├─ persisted step notes
   ├─ user input
   └─ cited semantic state
```

### Code mechanisms

- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)

## §7. Post-Observation and Re-Entry

Post-observation is what keeps mutation lawful under OMO.

This is where observe and mutate stop being independent categories and become a loop.

### Current law

```text
observation may emit child gaps
mutation may not directly expand the ledger
successful mutation yields a post-observe surface
that surface may emit child gaps
observation and reasoning steps persist notes that become the next semantic surface
```

### Where `post_diff` still matters

`post_diff` still matters as a runtime consequence marker inside authored workflows and compiler lowering, but it is no longer the main authored execution contract.

The stronger execution contract now lives on:

- tool scripts
- chain contracts
- kernel laws

So the compounding rhythm is:

```text
observe
  -> mutate
  -> post-observe
  -> new relevant gap or closure
```

### Mechanism tree

```text
post-observation loop
├─ observation
│  ├─ resolve
│  ├─ inspect
│  ├─ persist rich observation note
│  └─ emit child gaps if needed
├─ mutation
│  ├─ execute
│  ├─ auto-commit
│  └─ assessment
├─ post-observe surface
│  ├─ hash_resolve_needed
│  ├─ explicit artifact/log override
│  ├─ reason reintegration for bridge writers
│  └─ note-rich semantic state for follow-on comparison
└─ closure or renewed frontier
   ├─ new observe gap
   ├─ new bridge gap
   └─ resolved branch
```

### Code mechanisms

- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- [compile.py](/Users/k2invested/Desktop/cors/compile.py)

## §8. Compiler Laws and Recursive Fluidity

The compiler is the lawful sequencer.

The compiler is the layer that turns all prior mechanisms into a stable operating rhythm.

### The nine laws

**1. LIFO**  
The ledger is a stack. Deepest child pops first.

**2. Depth-first**  
One chain resolves downwards before siblings take over.

**3. OMO**  
No consecutive mutations without observation between them.

**4. Admission**  
Only sufficiently grounded and relevant gaps are admitted.

**5. Priority ordering**  
Observe before mutate before foundational bridge work.

**6. Force-close**  
Chains exceeding max depth are force-closed.

**7. Immutability**  
Gaps do not change identity after emission.

**8. Post-observation**  
Successful mutation always yields a verification surface.

**9. Loop always closes**  
Every activated workflow must close back into the parent trajectory through lawful reintegration.

### Refined Law 9

The current primary model is:

- `reason_needed` activates child work by emitting:
  - `activate_ref`
  - `prompt`
  - `await_needed`
- if `await_needed=true`
  - child work runs in isolated/background runtime
  - parent gets an `await_needed` checkpoint before synthesis
- if `await_needed=false`
  - child work runs inline as a real child chain
  - the activation handoff becomes the first step of that child chain
  - when the child chain closes, the parent receives a post-observe `reason_needed` review gap
- child workflow outcome re-enters as structure, not just as final prose
- parent inspects the child semantic tree and decides what to do next

Legacy `reprogramme_needed` background closure still exists in compatibility paths, but it is not the preferred activation model anymore.

So the reintegration layer now unwraps like this:

```text
reason step
  -> emits child activation
  -> child runs inline or isolated depending on await_needed
  -> child closes as a lawful chain
  -> parent resumes through await_needed checkpoint or post-observe reason review
```

### Workflow validation

[tools/validate_chain.py](/Users/k2invested/Desktop/cors/tools/validate_chain.py) now validates Law 9 against:

- current `reason_needed` activations with `activate_ref` / `activation_ref`
- legacy `reprogramme_needed`
- optional downstream `await_needed`

### Recursive embedding

Embedded workflows remain lawful only if they preserve:

- hash-native references
- public tool/chain boundaries
- OMO legality
- reintegration closure

### Mechanism tree

```text
compiler law layer
├─ stack laws
│  ├─ LIFO
│  ├─ depth-first
│  └─ priority ordering
├─ safety laws
│  ├─ OMO
│  ├─ admission
│  ├─ immutability
│  └─ force-close
├─ reintegration law
│  ├─ await checkpoint
│  ├─ inline child-chain closure
│  ├─ parent-side post-observe reason review
│  └─ resolved child tree folded into parent turn render
└─ validator surface
   ├─ validate_chain.py
   └─ compiler bookkeeping
```

### Code mechanisms

- [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- [tools/validate_chain.py](/Users/k2invested/Desktop/cors/tools/validate_chain.py)

## §9. Step Blobs, Chains, and Extraction

There are three important structural levels:

- steps
- active chains
- extracted chains

This is the persistence layer of the same system, not a separate mechanism family.

### Chain lifecycle

The runtime now separates two identities that older versions of cors collapsed together:

- stable chain identity
  - the runtime lineage id of the chain
- chain signature
  - the evolving derived signature of the chain contents as steps accumulate

This matters because execution lineage must stay stable while the chain grows.

When chains exceed `CHAIN_EXTRACT_LENGTH`, the full resolved chain is extracted from the hot trajectory into dedicated storage.

Current storage model:

- `chains.json`
  - chain index / metadata
- `trajectory_store/command/{hash}.json`
  - extracted command-flow chains
- `trajectory_store/subagent/{hash}.json`
  - extracted subagent chains
- `trajectory_store/background_agent/{hash}.json`
  - extracted background chains

The parent trajectory carries the hash reference. The full chain body moves to extracted storage.

### Mechanism tree

```text
chain extraction
├─ hot runtime chain
│  ├─ stable chain id
│  ├─ open
│  ├─ active
│  ├─ suspended
│  └─ closed
├─ derived chain signature
│  └─ updated as steps accumulate
├─ note-bearing steps
│  ├─ observation notes
│  └─ reasoning notes
├─ extraction threshold
│  └─ CHAIN_EXTRACT_LENGTH
├─ index layer
│  └─ chains.json
└─ extracted stores
   ├─ trajectory_store/command
   ├─ trajectory_store/subagent
   └─ trajectory_store/background_agent
```

### Code mechanisms

- [step.py](/Users/k2invested/Desktop/cors/step.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)

## §10. Step Chain Activation and Reintegration

### `reason_needed` is now the activation primitive

For complex work, `reason_needed` does not try to build every lower layer directly.

It decides whether to:

- observe
- mutate
- clarify
- persist semantic state
- author a tool
- author semantic routing
- activate child workflow

This is the section where the system becomes visibly recursive:

```text
reason step
  -> may emit ordinary executable gap
  -> may emit structural authoring gap
  -> may activate another workflow as a child chain
```

### Minimal activation payload

The current child-activation contract is:

```json
{
  "activate_ref": "<workflow-hash>",
  "prompt": "task for the child workflow",
  "await_needed": true,
  "content_refs": ["relevant content hash or path"],
  "step_refs": ["relevant step hash"]
}
```

or the same with `await_needed=false`.

### Runtime distinction

`await_needed` now determines whether child work is isolated or inline.

- `await_needed=false`
  - activate workflow inline
  - create a real child chain under the parent reasoning chain
  - when the child closes, emit a parent-side post-observe `reason_needed` review
- `await_needed=true`
  - activate workflow in isolated/background runtime
  - parent gets an explicit await checkpoint before synthesis

So `await_needed` is no longer just a sync marker. It is also the runtime split between inline and isolated child work.

### Child-chain origin

The activation handoff step is the first step of the child chain.

This matters because phases injected by the activated workflow are not unrelated origin gaps. They belong to the same child chain lineage, and that lineage branches off the activating reason step.

That means:

- one activation
  - one child chain
- later phases in that workflow
  - stay in that child chain
- child workflows of child workflows
  - become grandchildren in the same family tree

The system compounds trajectories, not just outputs.

### Parent-side review

Inline child closure now reintegrates through a parent-side post-observe `reason_needed` review.

That review point is where the parent:

- inspect child tree
- synthesize if complete
- reopen if needed
- trigger further work if needed

The review gap now carries:

- the child workflow ref
- the resolved child chain hash
- the full child step lineage in `step_refs`

So parent review is grounded in the actual completed child branch, not just a thin completion marker.

Background/isolated child work still reintegrates through explicit await checkpoints.

### Storage separation

Isolated child flows use:

- [trajectory_store/command](/Users/k2invested/Desktop/cors/trajectory_store/command)
- [trajectory_store/subagent](/Users/k2invested/Desktop/cors/trajectory_store/subagent)
- [trajectory_store/background_agent](/Users/k2invested/Desktop/cors/trajectory_store/background_agent)

Execution storage may remain separate while the semantic render does not. Resolved inline child workflows now fold back into the parent turn tree render once the child closes.

### Mechanism tree

```text
reason_needed
├─ emits normal executable gap
├─ emits tool_needed
├─ emits vocab_reg_needed
├─ emits reprogramme_needed
├─ persists explicit reasoning note
└─ emits child activation
   ├─ activate_ref
   ├─ prompt
   ├─ content refs
   ├─ step refs
   └─ await_needed
      ├─ true
      │  ├─ isolated/background runtime
      │  └─ await_needed checkpoint before synthesis
      └─ false
         ├─ inline child chain
         └─ parent-side post-observe reason review

child workflow lineage
├─ activation handoff step
├─ child chain phases
└─ child closure
   ├─ semantic tree exposed back to parent review
   └─ resolved subtree folded into parent turn render
```

### Code mechanisms

- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- [compile.py](/Users/k2invested/Desktop/cors/compile.py)

## §11. Temporal Signatures and Semantic Trees

The semantic tree is the main readable structural surface for the model.

This is the readable compression layer for all the mechanisms above.

### Current render law

The compact render uses:

- step headers with:
  - `o`
  - `m`
  - `b`
  - `c`
- frontier shape:
  - `+n`
  - `~n`
  - `=`
- explicit state when runtime-derived
- inline refs
- inline timestamps when realized
- explicit persisted `StepNote` fields where available
- resolved child-chain inlining in parent turn history once closure occurs

### Purpose

The tree should show:

- structure
- state
- refs
- causality
- reintegration points
- child-chain branching
- stable runtime lineage
- step notes rich enough to stand in for reopening raw source
- carried context inherited through cited steps

without reintroducing verbose legacy gap config noise.

So the semantic tree is not just a renderer. It is the compressed interface where:

- gap state
- chain structure
- activation
- reintegration
- temporal progress
- parent/child workflow family shape
- persisted comparison notes
- carried observable context

all become simultaneously legible.

### Mechanism tree

```text
semantic tree surface
├─ identity
│  ├─ stable chain/package ref
│  ├─ derived signature
│  ├─ step ids
│  └─ gap ids
├─ compact structure
│  ├─ o/m/b/c
│  ├─ +n/~n/=
│  └─ branch nesting
├─ runtime signals
│  ├─ state
│  ├─ refs
│  ├─ note fields
│  ├─ timestamps
│  ├─ reintegration markers
│  ├─ parent/child chain lineage
│  └─ carried content provenance
└─ render consumers
   ├─ main agent context
   ├─ await/reason review
   ├─ trace/security comparison
   └─ post-closure parent turn render
```

### Code mechanisms

- [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- [step.py](/Users/k2invested/Desktop/cors/step.py)

## §12. Supporting Infrastructure

These mechanisms are not principles themselves, but they enforce the principles.

They matter because the core principles only become real when the infrastructure keeps the layers separate.

### Turn lifecycle

```text
user input
  -> origin step
  -> context injection
  -> semantic tree and note-rich history render
  -> compiler admission
  -> execution iteration
  -> note persistence
  -> synthesis
  -> persistence
```

### Hash resolution infrastructure

Public file observation stays unified:

- [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)

Specialized handlers stay internal:

- [tools/hash](/Users/k2invested/Desktop/cors/tools/hash)
- [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py)

Semantic note enrichment for observation steps lives in:

- [note_engine.py](/Users/k2invested/Desktop/cors/note_engine.py)

### Infrastructure split

Executable public tools live in:

- [tools/](/Users/k2invested/Desktop/cors/tools)

Immutable support infrastructure lives in:

- [system/](/Users/k2invested/Desktop/cors/system)

That includes:

- registry modules
- builder modules
- validator/compile infrastructure

### Mechanism tree

```text
support infrastructure
├─ outer runtime
│  ├─ loop.py
│  ├─ execution_engine.py
│  ├─ env_loader.py
│  ├─ discord_bot.py
│  └─ note_engine.py
├─ immutable system core
│  ├─ registries
│  ├─ builders
│  ├─ validators
│  └─ compilers
├─ executable tool surface
│  ├─ workspace tools
│  ├─ external tools
│  └─ hash primitives
├─ semantic support layer
│  ├─ step-note persistence
│  ├─ carried ref expansion
│  ├─ semantic tree rendering
│  └─ resolved child-chain inlining
└─ schemas and tests
   ├─ schema json files
   └─ principle/runtime test suite
```

## §13. Composition Over Construction

cors should prefer composition over ad hoc workflow construction.

This is the outermost layer of the same unwrapping:

```text
step
  -> gap
  -> chain
  -> manifestation
  -> lawful execution
  -> reintegration
  -> reusable compounds
```

### Tool-first bias

The primary atoms are tools.

Chains are compounds built over tools. Embedded chain reuse is strategic, not default.

That means:

- use public tools first
- reuse public chains when clearly stronger than rebuilding from tools
- keep hidden hash handlers out of public composition

### Current chain-building status

The current runtime supports:

- public action chains in `skills/actions/*.st`
- public chain contracts in [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py)

`chain_needed` and the final chain-plan authoring flow are still future-facing.

So the core architectural shape is:

```text
public tools
  -> executable atoms
public chains
  -> reusable compounds
vocab
  -> semantic exposure over those assets
reason
  -> decides how to combine them lawfully
```

### Mechanism tree

```text
composition surface
├─ public tools (atoms)
│  └─ registry: system/tool_registry.py
├─ public action chains (compounds)
│  └─ registry: system/chain_registry.py
├─ semantic routing
│  └─ vocab_registry.py + vocab_reg_needed
└─ hidden implementation
   ├─ system/*
   └─ tools/hash/*
```

## File Map

```text
cors/
├─ step.py
├─ compile.py
├─ loop.py
├─ execution_engine.py
├─ note_engine.py
├─ manifest_engine.py
├─ vocab_registry.py
├─ trajectory.json
├─ chains.json
├─ trajectory_store/
│  ├─ command/
│  ├─ subagent/
│  └─ background_agent/
├─ system/
│  ├─ tool_registry.py
│  ├─ chain_registry.py
│  ├─ hash_registry.py
│  ├─ tool_contract.py
│  ├─ tool_builder.py
│  ├─ vocab_builder.py
│  ├─ validate_tool_contract.py
│  ├─ security_compile.py
│  ├─ skeleton_compile.py
│  ├─ semantic_skeleton_compile.py
│  └─ trace_tree_build.py
├─ tools/
│  ├─ hash_resolve.py
│  ├─ hash_manifest.py
│  ├─ code_exec.py
│  ├─ email_send.py
│  ├─ email_check.py
│  ├─ git_ops.py
│  ├─ file_grep.py
│  └─ hash/
├─ skills/
│  ├─ admin.st
│  ├─ entities/
│  ├─ actions/
│  └─ codons/
│     ├─ await.st
│     ├─ commit.st
│     ├─ reprogramme.st
│     └─ commitment_chain_construction_spec.st
└─ docs/
```

> Every mechanism is step. Every persistent identity is a hash. Every lawful mutation re-enters through observation or reasoned reintegration.

## Module Coverage Map

Every live module in the current system surface belongs to one of the principle layers above.

### Core runtime modules

- §1 / §2 / §8 / §9
  - [step.py](/Users/k2invested/Desktop/cors/step.py)
  - [compile.py](/Users/k2invested/Desktop/cors/compile.py)
- §3 / §7 / §10 / §12
  - [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
  - [loop.py](/Users/k2invested/Desktop/cors/loop.py)
  - [note_engine.py](/Users/k2invested/Desktop/cors/note_engine.py)
  - [manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py)
- §12
  - [env_loader.py](/Users/k2invested/Desktop/cors/env_loader.py)
  - [discord_bot.py](/Users/k2invested/Desktop/cors/discord_bot.py)
  - [action_foundations.py](/Users/k2invested/Desktop/cors/action_foundations.py)

### Registry and system modules

- §3 / §12 / §13
  - [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py)
  - [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py)
  - [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py)
  - [system/tool_contract.py](/Users/k2invested/Desktop/cors/system/tool_contract.py)
  - [system/tool_builder.py](/Users/k2invested/Desktop/cors/system/tool_builder.py)
  - [system/vocab_builder.py](/Users/k2invested/Desktop/cors/system/vocab_builder.py)
  - [system/validate_tool_contract.py](/Users/k2invested/Desktop/cors/system/validate_tool_contract.py)
  - [system/gap_config_report.py](/Users/k2invested/Desktop/cors/system/gap_config_report.py)
- §8 / §11 / §12
  - [system/security_compile.py](/Users/k2invested/Desktop/cors/system/security_compile.py)
  - [system/skeleton_compile.py](/Users/k2invested/Desktop/cors/system/skeleton_compile.py)
  - [system/semantic_skeleton_compile.py](/Users/k2invested/Desktop/cors/system/semantic_skeleton_compile.py)
  - [system/trace_tree_build.py](/Users/k2invested/Desktop/cors/system/trace_tree_build.py)

### Skill and vocab modules

- §3 / §5 / §10 / §13
  - [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py)
  - [skills/admin.st](/Users/k2invested/Desktop/cors/skills/admin.st)
  - `skills/actions/*.st`
  - `skills/entities/*.st`
  - `skills/codons/*.st`
  - [vocab_registry.py](/Users/k2invested/Desktop/cors/vocab_registry.py)
  - [tree_policy.json](/Users/k2invested/Desktop/cors/tree_policy.json)

### Tool modules

- §3 / §7 / §12 / §13
  - hash primitives:
    - [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
    - [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
  - workspace/action tools:
    - [tools/code_exec.py](/Users/k2invested/Desktop/cors/tools/code_exec.py)
    - [tools/file_grep.py](/Users/k2invested/Desktop/cors/tools/file_grep.py)
    - [tools/git_ops.py](/Users/k2invested/Desktop/cors/tools/git_ops.py)
    - [tools/json_patch.py](/Users/k2invested/Desktop/cors/tools/json_patch.py)
    - [tools/principles.py](/Users/k2invested/Desktop/cors/tools/principles.py)
    - [tools/scan_tree.py](/Users/k2invested/Desktop/cors/tools/scan_tree.py)
    - [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)
    - [tools/stitch_generate.py](/Users/k2invested/Desktop/cors/tools/stitch_generate.py)
    - [tools/validate_chain.py](/Users/k2invested/Desktop/cors/tools/validate_chain.py)
    - [tools/video_generator.py](/Users/k2invested/Desktop/cors/tools/video_generator.py)
  - email/message tools:
    - [tools/email_check.py](/Users/k2invested/Desktop/cors/tools/email_check.py)
    - [tools/email_send.py](/Users/k2invested/Desktop/cors/tools/email_send.py)
    - [tools/read_logs.py](/Users/k2invested/Desktop/cors/tools/read_logs.py)
  - web/research/domain tools:
    - [tools/companies_house.py](/Users/k2invested/Desktop/cors/tools/companies_house.py)
    - [tools/epc_lookup.py](/Users/k2invested/Desktop/cors/tools/epc_lookup.py)
    - [tools/flood_risk.py](/Users/k2invested/Desktop/cors/tools/flood_risk.py)
    - [tools/generate_narration.py](/Users/k2invested/Desktop/cors/tools/generate_narration.py)
    - [tools/generate_scenes.py](/Users/k2invested/Desktop/cors/tools/generate_scenes.py)
    - [tools/google_trends.py](/Users/k2invested/Desktop/cors/tools/google_trends.py)
    - [tools/land_registry.py](/Users/k2invested/Desktop/cors/tools/land_registry.py)
    - [tools/ons_demographics.py](/Users/k2invested/Desktop/cors/tools/ons_demographics.py)
    - [tools/police_api.py](/Users/k2invested/Desktop/cors/tools/police_api.py)
    - [tools/postcodes_io.py](/Users/k2invested/Desktop/cors/tools/postcodes_io.py)
    - [tools/rental_search.py](/Users/k2invested/Desktop/cors/tools/rental_search.py)
    - [tools/research_web.py](/Users/k2invested/Desktop/cors/tools/research_web.py)
    - [tools/runway_gen.py](/Users/k2invested/Desktop/cors/tools/runway_gen.py)
    - [tools/scraper.py](/Users/k2invested/Desktop/cors/tools/scraper.py)
    - [tools/url_fetch.py](/Users/k2invested/Desktop/cors/tools/url_fetch.py)
    - [tools/web_search.py](/Users/k2invested/Desktop/cors/tools/web_search.py)
    - [tools/youtube_research.py](/Users/k2invested/Desktop/cors/tools/youtube_research.py)
    - [tools/youtube_transcript.py](/Users/k2invested/Desktop/cors/tools/youtube_transcript.py)
  - internal hash handlers:
    - `tools/hash/*`

### Schema and persistence modules

- §4 / §8 / §11 / §12
  - [schemas/security_compile.v1.json](/Users/k2invested/Desktop/cors/schemas/security_compile.v1.json)
  - [schemas/semantic_skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/semantic_skeleton.v1.json)
  - [schemas/skeleton.v1.json](/Users/k2invested/Desktop/cors/schemas/skeleton.v1.json)
  - [schemas/trace_tree.v1.json](/Users/k2invested/Desktop/cors/schemas/trace_tree.v1.json)
  - [trajectory.json](/Users/k2invested/Desktop/cors/trajectory.json)
  - [chains.json](/Users/k2invested/Desktop/cors/chains.json)
  - [tools/tasks.json](/Users/k2invested/Desktop/cors/tools/tasks.json)

This coverage map is the check: every live module belongs to a principle layer, and every principle section now has an explicit mechanism tree.
