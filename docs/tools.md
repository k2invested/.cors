# tools

The `tools/` directory is the kernel’s execution surface. The loop does not import these as internal modules. It spawns them as subprocesses and treats them as bounded operators.

## Contract

The common pattern is:

- JSON goes in on stdin
- output comes back on stdout
- exit code communicates success or failure

That separation matters because it keeps the execution layer outside the core runtime object model.

## Tools The Loop Actually Routes To

The current `TOOL_MAP` in `loop.py` routes directly to:

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

`hash_resolve_needed` and `external_context` are handled inline by the kernel rather than by a subprocess.

## Important Core Tools

`hash_manifest.py`
The main mutation operator behind `hash_edit_needed`.

`st_builder.py`
The `.st` persistence builder used by `reprogramme_needed`.

`chain_to_st.py`
The chain extraction path for crystallizing resolved runtime structure into `.st`.

Those three are more architecturally important than most of the domain tools because they sit on the boundary between runtime reasoning and persisted structure.

## Domain And Utility Tools In The Repo

Beyond the directly routed tools, the repo contains a wider bench of utilities and domain operators, including:

- document tools such as `doc_read.py`, `doc_edit.py`, `pdf_read.py`, and `pdf_fill.py`
- web and research tools such as `web_search.py`, `research_web.py`, `url_fetch.py`, and `youtube_research.py`
- registry and property tools such as `land_registry.py`, `epc_lookup.py`, `flood_risk.py`, and `postcodes_io.py`
- context and indexing tools such as `repo_index.py`, `context_pack.py`, `recall.py`, and `scan_tree.py`
- media tools such as `runway_gen.py`, `video_generator.py`, and `generate_narration.py`

Not all of these are currently first-class vocab-routed tools in `loop.py`, but they are part of the repo’s operator surface.

## Routing And Policy

Two routing rules matter more than the individual tools.

First, `.st`-targeted mutation is not treated like ordinary file editing. The loop checks tree policy and reroutes `.st` mutation toward `reprogramme_needed`.

Second, codon mutation is not allowed. If a mutation touches `skills/codons/`, the commit is reverted and the system rejects into `reason_needed`.

So the tool layer is not a free-for-all. The kernel imposes architectural law over which operators may touch which surfaces.

## Current Drift

There are two important mismatches to keep in mind.

`st_builder.py` still infers legacy vocab terms that are not part of the compiler’s live runtime algebra.

`chain_to_st.py` presents itself as deterministic extraction, but its current implementation is only partially direct. It still derives some step properties heuristically from resolved chain shape.

That means both tools are useful, but neither should be treated as a perfect reflection of the current runtime semantics.
