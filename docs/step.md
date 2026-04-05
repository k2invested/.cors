# step.py

[step.py](/Users/k2invested/Desktop/cors/step.py) defines the runtime object model and the main readable tree renders.

## Core Objects

- `Epistemic`
- `Gap`
- `Step`
- `Chain`
- `Trajectory`

## Gap

`Gap` is the unresolved frontier unit.

Important fields:

- `hash`
- `desc`
- `step_refs`
- `content_refs`
- `scores`
- `vocab`
- `resolved`
- `dormant`
- `turn_id`
- `carry_forward`
- `route_mode`

## Step

`Step` is the persistent runtime event.

Important fields:

- `hash`
- `desc`
- `step_refs`
- `content_refs`
- `gaps`
- `commit`
- `chain_id`
- `parent`
- `assessment`
- rogue metadata when relevant

## Chain

`Chain` is just a grouped runtime branch:

- `hash`
- `origin_gap`
- `steps`
- `desc`
- `resolved`
- `extracted`

There is no longer a special reason-loop controller chain model in the runtime object layer.

## Trajectory

`Trajectory` owns:

- ordered runtime steps
- chain lookup
- gap index
- hash resolution across steps and gaps
- compact semantic-tree rendering for recent runtime state

## Render Language

The render language is now the compact standardized form:

- `o` observe
- `m` mutate
- `b` bridge
- `c` clarify
- `+N` active child gaps
- `~N` dormant child gaps
- `=` locally closed

Gap rows show:

- status
- surface
- refs

The tree itself carries the parent-child relation. Step refs and gap refs remain visible as grounding, not as a replacement for the branch shape.
