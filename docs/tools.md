# tools

The [tools/](/Users/k2invested/Desktop/cors/tools) directory is the subprocess operator bench. The kernel reasons over their outputs, but the tools themselves remain outside the core runtime graph.

## Contract

The common operator pattern is still:

- JSON in on stdin
- structured result on stdout
- exit code signals success or failure

That boundary matters because the runtime can inspect tool effects without turning every operator into an in-process kernel primitive.

## Directly Routed Tools

The current `TOOL_MAP` in [loop.py](/Users/k2invested/Desktop/cors/loop.py) routes directly to:

- `tools/file_grep.py`
- `tools/email_check.py`
- `tools/hash_manifest.py`
- `tools/stitch_generate.py`
- `tools/file_write.py`
- `tools/file_edit.py`
- `tools/code_exec.py`
- `tools/email_send.py`
- `tools/json_patch.py`
- `tools/git_ops.py`

Observation-only hash resolution remains inline in the kernel.

## Architecturally Important Tools

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py)

- semantic `.st` persistence curator
- restores or requires deterministic entity context-injection steps
- writes new entities into `skills/entities/`
- writes new actions into `skills/actions/`
- can update existing action packages explicitly
- does not own new workflow origination

[tools/skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/skeleton_compile.py)

- deterministic workflow compiler
- validates `skeleton.v1`
- produces `stepchain.v1`
- enforces structural coherence

[tools/semantic_skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/semantic_skeleton_compile.py)

- semantic envelope compiler
- lowers action-bearing structure through `skeleton_compile.py`

[tools/trace_tree_build.py](/Users/k2invested/Desktop/cors/tools/trace_tree_build.py)

- derives `trace_tree.v1`
- lowers realized chains, stepchains, and skeleton-based inputs into one replay grammar

[tools/validate_chain.py](/Users/k2invested/Desktop/cors/tools/validate_chain.py)

- validator surface used by the broader chain/workflow discipline
- part of the structure-checking bench around the principles

## Routing Law

The important routing rules are now:

```text
ordinary file mutation          -> normal mutate vocab/tool path
.st entity/admin mutation       -> reprogramme_needed (entity_editor)
.st action update               -> reprogramme_needed (action_editor)
new action/hybrid origination   -> reason_needed first
codon mutation                  -> reject / auto-revert / reason_needed
```

So the tool layer is subordinate to architectural law. The presence of a file-edit tool does not mean every tree is editable the same way.

## Chain Construction Spec

[commitment_chain_construction_spec.st](/Users/k2invested/Desktop/cors/skills/codons/commitment_chain_construction_spec.st) is now part of the effective tooling story even though it is not a Python script.

It is:

- immutable by tree location
- resolved as a spec/context package
- selectively injected into `reason_needed`
- injected into `reprogramme_needed` for action-editor workflow persistence

That makes it part of the authoring/tool bench for chain construction.

## Practical Split

The clean split is now:

- `reason_needed`
  - structural authoring
  - chain design
  - skeleton compilation
- `reprogramme_needed`
  - semantic persistence
  - entity calibration
  - bounded updates to existing action packages

The tool layer serves both sides, but it no longer erases the distinction between them.
