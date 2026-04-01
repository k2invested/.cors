# tools

The [tools/](/Users/k2invested/Desktop/cors/tools) directory is the kernel’s subprocess execution surface. The loop does not treat these files as in-process kernel modules. It spawns them and treats them as bounded operators.

## Contract

The common pattern is:

- JSON goes in on stdin
- result comes back on stdout
- exit code communicates success or failure

That boundary matters because it keeps execution outside the core runtime graph. The kernel can reason about tool outputs without turning tools themselves into kernel primitives.

## Tools The Loop Routes To Directly

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

`hash_resolve_needed` and `external_context` are handled inline by the kernel rather than by a subprocess tool.

## Architecturally Important Tools

[tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py) is the main mutation operator behind `hash_edit_needed`.

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) is the semantic `.st` curator used by `reprogramme_needed`. It handles entity creation and update, plus explicit updates to existing executable packages. It is not the deterministic workflow compiler.

[tools/chain_to_st.py](/Users/k2invested/Desktop/cors/tools/chain_to_st.py) crystallizes resolved runtime chains into `.st`, but it still derives parts of the output heuristically from chain shape.

[tools/skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/skeleton_compile.py) is now the deterministic workflow compiler. It validates `skeleton.v1`, preserves manifestation and generation structure, and performs graph-level coherence checks such as reachability, terminal closure, mutate-to-observe closure, commit consumption, and await/background reintegration.

[tools/semantic_skeleton_compile.py](/Users/k2invested/Desktop/cors/tools/semantic_skeleton_compile.py) compiles the semantic envelope and lowers any action-bearing slice through `skeleton_compile.py`.

[tools/trace_tree_build.py](/Users/k2invested/Desktop/cors/tools/trace_tree_build.py) derives `trace_tree.v1` replay structures from realized chains, compiled `stepchain.v1`, and skeleton-based inputs. It is the bridge from stored execution/package structure into simulator-ready unfolding traces.

These files matter more than most other tools because they sit directly on the boundary between runtime reasoning and persisted structure.

## Broader Tool Surface

Beyond the directly routed tools, the repo contains a wider bench of operators and utilities, including:

- document tools such as `doc_read.py`, `doc_edit.py`, `pdf_read.py`, and `pdf_fill.py`
- web and research tools such as `web_search.py`, `research_web.py`, `url_fetch.py`, and `youtube_research.py`
- registry and property tools such as `land_registry.py`, `epc_lookup.py`, `flood_risk.py`, and `postcodes_io.py`
- indexing and context tools such as `repo_index.py`, `context_pack.py`, `recall.py`, and `scan_tree.py`
- media tools such as `runway_gen.py`, `video_generator.py`, and `generate_narration.py`

Not all of these are currently vocab-routed from `loop.py`, but they are part of the repo’s operator bench.

## Routing And Policy

Two routing rules matter more than the individual tools.

First, `.st`-targeted mutation is not treated like ordinary file editing. The loop applies tree policy and reroutes `.st` mutation toward `reprogramme_needed`.

Second, codon mutation is not allowed. If a mutation touches `skills/codons/`, the commit is reverted and the system rejects into `reason_needed`.

So the tool layer is not a free-for-all. The kernel imposes architectural law over which operators may touch which surfaces.

## Current Drift

Two mismatches still matter.

[tools/st_builder.py](/Users/k2invested/Desktop/cors/tools/st_builder.py) now refuses new action origination and only accepts explicit runtime vocab on steps. That keeps it aligned with the compiler, but it also means workflow origination must happen through the skeleton compiler path.

[tools/chain_to_st.py](/Users/k2invested/Desktop/cors/tools/chain_to_st.py) calls itself deterministic extraction, but the current implementation is still partly heuristic rather than lossless.

That means both tools are useful, but neither should be treated as a perfect reflection of the current runtime semantics.
