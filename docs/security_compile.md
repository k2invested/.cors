# security_compile.v1

`security_compile.v1` is the contract for the OS security compiler.

This is not just a schema validator. Its job is to take any step-shaped artifact, normalize it into the same security model the kernel uses, project its recursive execution pattern, and decide whether it is lawful and healthy enough to admit into the system.

## What It Checks

The security compiler operates across all structural layers:

- atomic `Step`
- emitted `Gap`
- `.st` package
- `skeleton.v1`
- `semantic_skeleton.v1`
- `stepchain.v1`
- realized runtime chain

The checker should answer three questions for any candidate:

1. Is it lawful?
2. Is it safe for the OS?
3. What recursive execution pattern will it introduce?

## Check Domains

The contract defines five domains.

`structural_law`
Checks shape, closure, refs, transitions, post-diff legality, OMO coherence, and basic compiler-law requirements.

`manifestation_law`
Checks whether the artifact behaves like what it claims to be. This is where entity, action, hybrid, and codon distinctions are protected.

`protected_surfaces`
Checks for interaction with protected paths or structural primitives, such as codon mutation, kernel mutation, unsafe `.st` editing, or action updates without revalidation.

`recursive_execution_risk`
Checks whether the artifact creates recursive patterns that are unhealthy even if they are formally legal, such as runaway bridge cascades, post-diff loops, unbounded fan-out, or missing reintegration points.

`semantic_integrity`
Checks whether the artifact preserves inspectability and semantic continuity, for example preserving causal meaning, coherent refs, and interpretable package structure.

## Input

The input side identifies:

- what kind of artifact is being checked
- the candidate object itself
- any surrounding context needed for the judgment

The schema supports these artifact types:

- `atomic_step`
- `gap`
- `st_package`
- `skeleton`
- `semantic_skeleton`
- `stepchain`
- `realized_chain`

`mode` tells the checker when it is being called, for example `pre_persist`, `pre_activation`, or `retrospective_audit`.

## Result

The result has four main sections:

`status`
One of `accepted`, `accepted_with_warnings`, or `rejected`.

`checks`
One verdict per domain: `pass`, `warn`, or `fail`.

`violations` and `risks`
Hard failures go in `violations`. Health or security concerns that are not hard blockers go in `risks`.

`projection`
This is the recursive execution forecast. It tells the OS what the candidate will do if admitted:

- spawn depth
- branch points
- bridge count
- mutation count
- post-diff re-entry points
- whether background reintegration is required
- whether await or commit consumption is required
- whether protected surfaces are touched

## Why This Exists

The current kernel already has local protections, such as tree policy and codon immutability. `security_compile.v1` is the generalized version of that idea.

It moves the system from scattered special-case safety checks to a unified structural security layer that understands the recursive nature of step-gap execution.

That is why it is best thought of as a security compiler for the OS, not merely a validator.
