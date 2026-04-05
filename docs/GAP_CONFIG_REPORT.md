# Gap Config Report

Generated from `vocab_registry.VOCABS` and `action_foundations.list_action_foundations(...)`.

## Kernel Vocab Config
| Vocab | Category | Priority | Deterministic | Observation only | Post-gap emission | Tool | Post-observe | Description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hash_resolve_needed | observe | 20 | yes | no | yes |  |  | Resolve hashes and observe the resulting context. |
| pattern_needed | observe | 20 | no | no | yes | tools/file_grep.py |  | Search for a deterministic pattern in workspace content. |
| email_needed | observe | 20 | no | no | yes | tools/email_check.py |  | Inspect email context or mailbox state. |
| external_context | observe | 20 | no | yes | no |  |  | Inject external context as passive observation only. |
| clarify_needed | observe | 20 | no | no | yes |  |  | Request missing user-only information. |
| hash_edit_needed | mutate | 40 | no | no | yes | tools/hash_manifest.py |  | Patch or rewrite a workspace file. |
| stitch_needed | mutate | 40 | no | no | yes | tools/stitch_generate.py | ui_output/ | Generate stitched UI output artifacts. |
| content_needed | mutate | 40 | no | no | yes | tools/hash_manifest.py |  | Write new content into the workspace through the hash manifest primitive. |
| script_edit_needed | mutate | 40 | no | no | yes | tools/hash_manifest.py |  | Edit script content in-place through the hash manifest primitive. |
| command_needed | mutate | 40 | no | no | yes | tools/code_exec.py | bot.log | Execute a shell command to mutate state. |
| message_needed | mutate | 40 | no | no | yes | tools/email_send.py |  | Send a message or email. |
| tool_needed | mutate | 40 | no | no | yes | tools/tool_builder.py |  | Author a validated tool script with explicit runtime contract metadata. |
| json_patch_needed | mutate | 40 | no | no | yes | tools/json_patch.py |  | Apply a structured JSON patch. |
| git_revert_needed | mutate | 40 | no | no | yes | tools/git_ops.py |  | Revert git state. |
| reason_needed | bridge | 90 | no | no | yes |  |  | Stateful inline judgment and routing. |
| await_needed | bridge | 95 | no | no | yes |  |  | Pause and rejoin with synchronized background work. |
| commit_needed | bridge | 98 | no | no | yes |  |  | Terminal commitment codon. |
| reprogramme_needed | bridge | 99 | no | no | yes |  |  | Stateless semantic persistence primitive. |

## Tool Foundations
| Blob ref | Source | Activation | Default gap | OMO role | Description |
| --- | --- | --- | --- | --- | --- |
| 07b03e0aee2c | tools/trace_tree_build.py | internal_only | internal_only | observe | derive trace_tree.v1 from step-shaped sources. |
| 0843d292032a | tools/google_trends.py | internal_only | internal_only | observe | search interest over time via Google Trends. |
| 11250aa28c3e | tools/validate_tool_contract.py | internal_only | internal_only | observe | validate required tool contract fields. |
| 15c966dffbca | tools/land_registry.py | internal_only | internal_only | observe | fetch UK Land Registry Price Paid data. |
| 1f7b03d34f35 | tools/research_web.py | internal_only | internal_only | observe | structured web research for qualitative data collection. |
| 22bce686e476 | tools/ons_demographics.py | internal_only | internal_only | observe | UK ONS area demographics and deprivation data. |
| 38654a603b7c | tools/police_api.py | internal_only | internal_only | observe | fetch UK crime data from data.police.uk. |
| 3d1f79b2e987 | tools/email_send.py | name:message_needed | message_needed | mutate | compose email draft AND send via SMTP. |
| 42d7730c168d | tools/validate_chain.py | internal_only | internal_only | observe | Law 9 compliance validator for semantic tree compositions. |
| 4302d1eea931 | tools/video_generator.py | internal_only | internal_only | mutate | YouTube Shorts video generator with narration, captions, and simple editing. |
| 4b9e0e742e6f | tools/skeleton_compile.py | internal_only | internal_only | observe | deterministic skeleton.v1 -> stepchain.v1 compiler. |
| 4d499536ed64 | tools/tool_builder.py | name:tool_needed | tool_needed | mutate | write validated tool script scaffolds for tool_needed. |
| 526c94548db2 | tools/scraper.py | internal_only | internal_only | mutate | runs independently of the kernel. |
| 528f0edf0fa5 | tools/chain_to_st.py | internal_only | internal_only | mutate | deterministic extraction of a resolved chain into a .st file. |
| 52f151625add | tools/code_exec.py | name:command_needed | command_needed | mutate | execute shell commands sandboxed to workspace. |
| 533639db50a2 | tools/stitch_generate.py | name:stitch_needed | stitch_needed | mutate | Generate UI designs via Google Stitch SDK. |
| 59d82e9965e0 | tools/runway_gen.py | internal_only | internal_only | mutate | generate video clips using Runway Gen-4/4.5. |
| 5ba932ed9d8a | tools/hash_manifest.py | name:content_needed | content_needed | mutate | universal file I/O by hash reference. |
| 60272d5a2196 | tools/epc_lookup.py | internal_only | internal_only | observe | fetch UK Energy Performance Certificate data. |
| 713c144ec4be | tools/generate_narration.py | internal_only | internal_only | mutate | generate TTS narration audio via OpenAI. |
| 83f8074e2a82 | tools/flood_risk.py | internal_only | internal_only | observe | UK Environment Agency flood risk assessment. |
| 844a0483ef40 | tools/companies_house.py | internal_only | internal_only | observe | UK Companies House company search and filings. |
| 89823347aea9 | tools/security_compile.py | internal_only | internal_only | observe | unified structural security compiler for step-shaped artifacts. |
| 89ba533e83d9 | tools/git_ops.py | name:git_revert_needed | git_revert_needed | mutate | version control operations on the project repository. |
| 93533f7d7518 | tools/postcodes_io.py | internal_only | internal_only | observe | UK postcode geocoding and area metadata. |
| 96613644c7c1 | tools/generate_scenes.py | internal_only | internal_only | mutate | batch generate video clips via Runway Gen-4/4.5. |
| 9af3aa27639d | tools/read_logs.py | internal_only | internal_only | observe | read runtime logs from system instances. |
| a62cb56c33b5 | tools/json_query.py | internal_only | internal_only | observe | JSONPath query against agent memory stores. |
| ab9d50a105f5 | tools/pdf_check_fields.py | internal_only | internal_only | observe | Check if a PDF has fillable form fields. |
| b1d2eb431f5b | tools/semantic_skeleton_compile.py | internal_only | internal_only | observe | unified semantic_skeleton.v1 compiler. |
| b5734b922cbd | tools/url_fetch.py | internal_only | internal_only | observe | fetch and read the full content of a specific URL. |
| cceb17e3a894 | tools/scan_tree.py | internal_only | internal_only | observe | scan directory tree (listing only) or read a single file. |
| d58156396f0a | tools/email_check.py | name:email_needed | email_needed | observe | read-only email observation: outbox status, SMTP config. |
| d5b8c72f9e8c | tools/file_grep.py | name:pattern_needed | pattern_needed | observe | regex grep across files. |
| dbcb40f918cb | tools/pdf_extract_pymupdf.py | internal_only | internal_only | observe | rich PDF extraction via the imported pymupdf helper. |
| dd0648a9ee2c | tools/web_search.py | internal_only | internal_only | observe | search via SerpAPI or DuckDuckGo fallback. |
| df65fa0cb8db | tools/rental_search.py | internal_only | internal_only | observe | search rental listings via web search. |
| e56398c9e996 | tools/youtube_research.py | internal_only | internal_only | observe | search YouTube Shorts and extract transcripts. |
| f4f6e4bf8d15 | tools/hash_resolve.py | internal_only | internal_only | observe | resolve blob hashes from trajectory. |
| f8121693acf4 | tools/principles.py | internal_only | internal_only | mutate | CRUD for the admin dev agent's architectural knowledge store. |
| fe02e27d0794 | tools/youtube_transcript.py | internal_only | internal_only | observe | fetch a YouTube transcript through the imported helper. |
