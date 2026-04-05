# Principles Audit

This file audits [PRINCIPLES.md](/Users/k2invested/Desktop/cors/docs/PRINCIPLES.md) against the current source code.

Status terms:

- `validated`: the principle is materially implemented in source
- `partial`: the direction is correct, but the runtime still contains important limits

## Section Status

| Principle | Status | Notes |
|---|---|---|
| `§1 The Step Primitive` | `validated` | `Gap`, `Step`, `Chain`, `Trajectory`, and the two hash layers are real and central. |
| `§2 Gap Emission and Admission` | `validated` | Admission thresholds, dormancy, grounding overwrite, and depth-first placement are implemented. |
| `§3 Vocab And Manifestation` | `validated` | Vocab families, tree policy, entity/action/admin split, and deterministic reprogramme routing are real. |
| `§4 Formal Gap Configuration` | `validated` | Gap fields, threshold constants, `carry_forward`, and `route_mode` are represented in the runtime model. |
| `§5 Semantic Persistence And Registry` | `validated` | Loader projection, explicit skill tree, entity context-injection steps, and admin primacy are implemented. |
| `§6 Referred Context` | `validated` | Hash resolution order, entity injection, action package rendering, and referred grounding are implemented. |
| `§7 Post-Diff` | `partial` | Deterministic/flexible package surfaces are real, but `post_diff` is still stronger on package/runtime-shape law than as a universal kernel branch dial. |
| `§8 Compiler Laws` | `validated` | OMO, LIFO, governor signals, heartbeat bookkeeping, and carry-forward discipline are implemented. |
| `§9 Chains And Trajectory` | `validated` | Chain lifecycle, passive chains, extraction, rogue steps, and assessment-bearing steps are implemented. |
| `§10 Activation And Codons` | `validated` | Codon activation, package activation, trigger ownership, and the current reason/tool/reprogramme split are materially implemented in source. |
| `§11 Temporal Signatures` | `validated` | Absolute timestamp rendering and relative time helpers are implemented in the live render surface. |
| `§12 Supporting Infrastructure` | `validated` | Clarify frontier merge, turn-bounded clarify, forced-synth carry, Discord diff routing, and bootstrap identity are implemented. |
| `§13 Curation` | `validated` | Tree organization, immutable codons, curated package split, and principle-anchored regression coverage are all materially present. |

## Main Current Strengths

### 1. The skill tree is now ontological, not cosmetic

The runtime now materially distinguishes:

```text
skills/admin.st
skills/entities/*
skills/actions/*
skills/codons/*
```

This is enforced by:

- [skills/loader.py](/Users/k2invested/Desktop/cors/skills/loader.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- [tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)
- [tree_policy.json](/Users/k2invested/Desktop/cors/tree_policy.json)

### 2. Clarify is now a bounded frontier rather than a stale resume queue

The runtime now:

- merges current-turn clarify gaps
- materializes one clarification frontier step
- does not auto-carry clarify across turns

That is implemented in:

- [execution_engine.py](/Users/k2invested/Desktop/cors/execution_engine.py)
- [loop.py](/Users/k2invested/Desktop/cors/loop.py)
- [step.py](/Users/k2invested/Desktop/cors/step.py)

### 3. Reprogramme has a real post-observation consequence

Successful semantic persistence now produces:

```text
write
  -> auto_commit
  -> assessment
  -> postcondition step
  -> hash_resolve_needed
```

So the model can reason over the realized diff before synthesis.

### 4. New action origination is no longer treated like entity persistence

The deterministic rule now is:

- new entity => `reprogramme_needed`
- existing entity update => `reprogramme_needed`
- action-tree creation, repair, and update => `reason_needed`
- public trigger ownership => highest-order completed workflow only

That is the correct separation between semantic persistence and structural design.

### 5. Tool and package composition are cleaner than before

The runtime now cleanly separates:

- public tool registry
- internal hash handlers
- package activation
- semantic persistence

That split reduces the old overload on `reason_needed`.

## Main Remaining Partial

### `post_diff` is still partly package law rather than a fully generic kernel law

`post_diff` is real in:

- authored `.st` files
- loader projection
- rendered package structure
- validator/assessment vocabulary

But the runtime still routes most live execution through:

- vocab handling
- compiler law
- codon expansion
- route-mode policy

rather than a single universal “branch solely on `post_diff`” kernel switch.

That does not make the principle wrong. It means the implementation is converging toward it from several aligned mechanisms rather than from one master branch statement.

## Practical Read

The system is now strong on:

- state integrity
- ontological tree split
- explicit persistence law
- clarify lifecycle
- postcondition visibility
- principle-backed regression structure

The live frontier is no longer basic runtime integrity. It is higher-order composition quality when `reason_needed` has to decide which committed blocks to build next and how rich a top-level workflow should become.
