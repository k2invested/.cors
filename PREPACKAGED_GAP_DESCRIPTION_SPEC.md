# Prepackaged Gap Description Spec

This document defines the quality standard for gap descriptions inside prebuilt workflows such as `skills/actions/*.st` and codon-like packaged flows.

The purpose of a prepackaged gap description is not to be evocative. It is to make the lawful next move obvious.

## Standard

A high-quality prepackaged gap description should tell the agent:

- what context it should use
- what kind of output is lawful
- what surfaces are allowed
- what surfaces are forbidden
- when it should emit nothing
- what refs it must preserve or pass forward

If a packaged step already knows the intended execution surface, the description should name it explicitly. Do not rely on abstract prose when the system already knows the exact lawful move.

## Required Qualities

### 1. State The Decision Boundary

The description should make the branch point explicit.

Good:
- `If no edits are needed, emit nothing and close the workflow.`
- `If edits are needed, activate hash_edit with the exact file refs that require mutation.`

Bad:
- `Consider what to do next.`
- `Analyse and decide the best workflow.`

### 2. Name The Allowed Surface

If only one vocab, tool, or workflow is lawful, name it directly.

Good:
- `Emit only a reason activation JSON for hash_edit.`
- `Use hash_resolve_needed to load the requested files.`

Bad:
- `Trigger the appropriate workflow.`
- `Use the best available tool.`

### 3. Name Forbidden Surfaces

If a common misfire is known, ban it explicitly.

Good:
- `Do not reactivate architect.`
- `Do not emit reprogramme_needed from this phase.`
- `Do not edit workflow .st files unless the task explicitly asks for that.`

This matters because the model often treats nearby workflow refs as candidate targets unless forbidden clearly.

### 4. Specify Output Shape

If the step expects JSON, say so.

Good:
- `Emit only a reason activation JSON with activate_ref, prompt, await_needed, content_refs, and step_refs.`

If the step expects no new gap, say so.

Good:
- `Emit nothing if no action is required.`

### 5. Specify Ref Discipline

If the workflow depends on carried refs, say what must be passed.

Good:
- `Include only the concrete file refs that require mutation.`
- `Treat workflow/entity .st refs as context unless explicit editing is requested.`

Bad:
- `Use the context as needed.`

### 6. Prefer Concrete Over Abstract

Descriptions should prefer concrete execution law over abstract strategic advice.

Use:
- exact vocab names
- exact workflow names
- exact output constraints
- explicit no-op conditions

Only include abstract reasoning guidance if it changes execution quality materially.

## Pattern Templates

### Observe Step

Use this when the surface is fixed.

`Resolve the specified refs using hash_resolve_needed. Load them into context and emit no other workflow activation from this phase.`

### Reason Handoff Step

Use this when the workflow must either close or hand off to one exact child.

`Inspect the resolved context. Only two outputs are lawful here: emit nothing if no change is needed, or emit only a reason activation JSON for <workflow>. If activating <workflow>, include only the exact refs required for the child task. Do not activate any other workflow.`

### Mutation Compose Step

Use this when a packaged mutation should stay tightly targeted.

`Compose the edit for the concrete workspace files already carried in refs. Prefer non-.st workspace targets. Treat .st refs as context unless the task explicitly requires workflow or entity editing.`

## Anti-Patterns

Avoid these in prepackaged gaps:

- vague verbs like `consider`, `decide`, `use the best workflow`
- open-ended references to any public workflow when only one is intended
- asking for broad analysis without saying what lawful outputs exist
- omitting the no-op branch
- omitting ref discipline

## Design Rule

Prepackaged workflows exist to reduce ambiguity.

If a workflow author already knows:
- the likely next surface
- the allowed alternatives
- the common failure mode

then that information should be encoded in the gap description directly.

Packaged descriptions should be more explicit than ordinary ad hoc reasoning prompts, not less.
