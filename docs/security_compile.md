# security_compile.v1

`security_compile.v1` is the structural security compiler contract.

Its job is to inspect a candidate artifact and answer:

1. is it lawful
2. is it safe
3. what recursive execution pattern would it introduce

## Artifact Types

The compiler may inspect:

- atomic runtime steps
- gaps
- `.st` packages
- chain-like package artifacts
- realized chains

## Check Domains

The main domains are:

- structural law
- manifestation law
- protected surfaces
- recursive execution risk
- semantic integrity

## Purpose

This is the general safety layer behind tree policy, protected surfaces, and recursive execution health. It is not tied to the old reason-authoring controller design.
