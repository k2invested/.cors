# tools/ — Execution Scripts

**Layer**: 0 (standalone, no module imports)
**Principles**: §3, §13, §14

## Purpose

Standalone Python scripts executed by the kernel as subprocesses. Each tool reads params from stdin (JSON), executes, and writes results to stdout. Tools never import from step.py or compile.py — they are isolated execution units.

## Hash-Native Tools (v5)

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| hash_manifest.py | Universal file I/O by hash reference. Read, write, patch, diff. Routes mutations by file type (.st→st_builder, .json→json_patch, .docx→doc_edit, .pdf→pdf_fill). | `{"action": "read\|write\|patch\|diff", "path": "...", "content": "...", "patch": {"old":"..","new":".."}, "ref": "sha"}` | File content, diff, or confirmation |
| st_builder.py | Build .st files from semantic intent. Supports stepless pure entities. Forwards all non-base fields as manifestation config. | `{"name": ..., "actions": [...], "identity": {}, ...}` | Valid .st file written to skills/ |

## Observation Tools (resolve hash → data)

| Tool | Vocab | Purpose |
|------|-------|---------|
| file_grep.py | pattern_needed | Search file contents by pattern |
| email_check.py | email_needed | Check email |
| (inline resolve_hash) | hash_resolve_needed | Resolve step/gap/git hashes from trajectory (no tool script — handled in loop.py) |
| (inline) | external_context | LLM surfaces from current context (no tool script) |

## Mutation Tools (execute → commit)

| Tool | Vocab | Purpose |
|------|-------|---------|
| hash_manifest.py | hash_edit_needed | Universal file editing — routes by file type to specialized tools |
| code_exec.py | command_needed | Execute shell commands |
| file_write.py | content_needed | Write new files |
| file_edit.py | script_edit_needed | Edit existing files |
| json_patch.py | json_patch_needed | Surgical JSON mutation |
| email_send.py | message_needed | Send email |
| git_ops.py | git_revert_needed | Git operations (revert, etc.) |

## Domain Tools

| Tool | Purpose |
|------|---------|
| land_registry.py | Query land registry API |
| epc_lookup.py | Fetch energy performance certificates |
| flood_risk.py | Check flood risk zones |
| police_api.py | Query police API |
| postcodes_io.py | Postcode lookups |
| ons_demographics.py | ONS demographic data |
| companies_house.py | Companies House queries |
| google_trends.py | Google Trends data |
| rental_search.py | Rental market search |

## Media Tools

| Tool | Purpose |
|------|---------|
| runway_gen.py | Generate video via Runway |
| video_generator.py | Video generation pipeline |
| generate_scenes.py | Scene planning |
| generate_narration.py | TTS narration |
| scraper.py | YouTube transcript scraper |
| youtube_research.py | YouTube research |

## Document Tools

| Tool | Purpose |
|------|---------|
| doc_read.py | Read .docx/.pdf documents |
| doc_edit.py | Edit .docx documents |
| doc_edit_batch.py | Batch .docx edits |
| pdf_read.py | Read PDF files |
| pdf_fill.py | Fill PDF forms |
| pdf_check_fields.py | Check PDF form fields |

## Tool Interface

All tools follow the same interface:

```
stdin  → JSON params
stdout → result text (or JSON)
stderr → error messages
exit 0 → success
exit 1 → error
```

The kernel spawns tools as subprocesses. No shared state. No imports from the core system. Tools are hot-swappable — replace a script, the system uses the new version next execution.

## Post-execution

After a mutation tool (universal postcondition):
1. Kernel runs `auto_commit(message)` → `git add -A && git commit` → captures SHA
2. SHA recorded on the step's commit field
3. Universal postcondition: every auto_commit injects a `hash_resolve_needed` gap targeting the commit SHA onto the ledger. This is structural — not per-tool. The gap enters as a child (depth-first, pops next) so the system observes the mutation result before proceeding.

### File type routing (hash_manifest.py)

When hash_edit_needed fires, hash_manifest routes mutations by file extension:

| Extension | Delegated tool |
|-----------|---------------|
| .st | st_builder.py |
| .json | json_patch.py |
| .docx | doc_edit.py |
| .pdf | pdf_fill.py |
| (other) | Direct read/write/patch |

### .st auto-route

Any script_edit_needed, content_needed, json_patch_needed, or hash_edit_needed gap targeting a .st file is automatically rerouted to reprogramme_needed by loop.py. This ensures .st files always go through the st_builder for schema validation.
