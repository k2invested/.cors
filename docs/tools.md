# tools/ — Execution Scripts

**Layer**: 0 (standalone, no module imports)
**Principles**: §3, §13, §14

## Purpose

Standalone Python scripts executed by the kernel as subprocesses. Each tool reads params from stdin (JSON), executes, and writes results to stdout. Tools never import from step.py or compile.py — they are isolated execution units.

## Hash-Native Tools (v5)

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| hash_resolve.py | Resolve blob hashes from trajectory | `{"hashes": [...], "depth": N}` | Resolved step data with content, refs, assessment |
| st_builder.py | Build .st files from semantic intent | `{"name": ..., "actions": [...]}` | Valid .st file written to skills/ |

## Observation Tools (resolve hash → data)

| Tool | Vocab | Purpose |
|------|-------|---------|
| scan_tree.py | scan_needed | Scan workspace directory / read file content |
| file_grep.py | pattern_needed | Search file contents by pattern |
| file_read.py | scan_needed | Read specific file |
| email_check.py | email_needed | Check email |
| url_fetch.py | url_needed | Fetch URL content |
| web_search.py | research_needed | Web search |
| research_web.py | research_needed | Deep web research |
| registry_query.py | registry_needed | Query agent registry |
| recall.py | hash_resolve_needed | Legacy recall (being replaced by hash_resolve) |

## Mutation Tools (execute → commit)

| Tool | Vocab | Purpose |
|------|-------|---------|
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

After a mutation tool:
1. Kernel runs `git add -A && git commit` → captures SHA
2. SHA recorded on the step's commit field
3. Postcondition fires: resolve new commit blob as observation
