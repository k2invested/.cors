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
| json_patch_needed | mutate | 40 | no | no | yes | tools/json_patch.py |  | Apply a structured JSON patch. |
| git_revert_needed | mutate | 40 | no | no | yes | tools/git_ops.py |  | Revert git state. |
| reason_needed | bridge | 90 | no | no | yes |  |  | Stateful inline judgment and routing. |
| await_needed | bridge | 95 | no | no | yes |  |  | Pause and rejoin with synchronized background work. |
| commit_needed | bridge | 98 | no | no | yes |  |  | Terminal commitment codon. |
| reprogramme_needed | bridge | 99 | no | no | yes |  |  | Stateless semantic persistence primitive. |

## Tool Foundations
| Blob ref | Source | Activation | Default gap | OMO role | Description |
| --- | --- | --- | --- | --- | --- |
| 157afdc8ffbb | tools/scraper.py | internal_only | internal_only | internal | YouTube Shorts scraper daemon — runs independently of the kernel. |
| 194aa1d2f406 | tools/generate_scenes.py | internal_only | internal_only | internal | generate_scenes — batch generate video clips via Runway Gen-4/4.5. |
| 1b7591af1d54 | tools/ons_demographics.py | internal_only | internal_only | internal | ons_demographics — UK ONS area demographics and deprivation data. |
| 1dfc26342092 | tools/chain_to_st.py | internal_only | internal_only | internal | chain_to_st — deterministic extraction of a resolved chain into a .st file. |
| 21e883fe2511 | tools/read_logs.py | internal_only | internal_only | internal | read_logs — read runtime logs from system instances. |
| 2bc9fd0267be | tools/validate_chain.py | internal_only | internal_only | internal | validate_chain.py — Law 9 compliance validator for semantic tree compositions. |
| 2f17e8455a8f | tools/principles.py | internal_only | internal_only | internal | principles — CRUD for the admin dev agent's architectural knowledge store. |
| 30f202798399 | tools/trace_tree_build.py | internal_only | internal_only | internal | trace_tree_build — derive trace_tree.v1 from step-shaped sources. |
| 53d629039116 | tools/epc_lookup.py | internal_only | internal_only | internal | epc_lookup — fetch UK Energy Performance Certificate data. |
| 5cfef5d1095c | tools/url_fetch.py | internal_only | internal_only | internal | url_fetch — fetch and read the full content of a specific URL. |
| 5e00a997ae45 | tools/hash_manifest.py | name:content_needed | content_needed | mutate | hash_manifest — universal file I/O by hash reference. |
| 61224842c73a | tools/json_query.py | internal_only | internal_only | internal | json_query — JSONPath query against agent memory stores. |
| 63cb1dc58202 | tools/rental_search.py | internal_only | internal_only | internal | rental_search — search rental listings via web search. |
| 645562f242e7 | tools/email_check.py | name:email_needed | email_needed | observe | email_check — read-only email observation: outbox status, SMTP config. |
| 68c8a7da6704 | tools/generate_narration.py | internal_only | internal_only | internal | generate_narration — generate TTS narration audio via OpenAI. |
| 6b7c4ca08fa2 | tools/file_grep.py | name:pattern_needed | pattern_needed | observe | file_grep — regex grep across files. |
| 7335d7e172e3 | tools/video_generator.py | internal_only | internal_only | internal | YouTube Shorts video generator with narration, captions, and simple editing. |
| 7fc13d75f218 | tools/stitch_generate.py | name:stitch_needed | stitch_needed | mutate | stitch_generate — Generate UI designs via Google Stitch SDK. |
| 80ce0dfb0aa6 | tools/pdf_fill.py | internal_only | internal_only | internal | pdf_fill — Fill fillable form fields in a PDF. |
| 824c69e7ec32 | tools/doc_read.py | internal_only | internal_only | internal | doc_read — extract text content from document files (.docx). |
| 85e980167bbd | tools/semantic_skeleton_compile.py | internal_only | internal_only | internal | semantic_skeleton_compile — unified semantic_skeleton.v1 compiler. |
| 88b5f33d05a8 | tools/docx_pack.py | internal_only | internal_only | internal | docx_pack — Pack a directory into a DOCX, PPTX, or XLSX file. |
| 89f52e612520 | tools/doc_edit.py | internal_only | internal_only | internal | doc_edit — modify document files (.docx) in place. |
| 8b9ee2c54d85 | tools/runway_gen.py | internal_only | internal_only | internal | runway_gen — generate video clips using Runway Gen-4/4.5. |
| 9107229de800 | tools/google_trends.py | internal_only | internal_only | internal | google_trends — search interest over time via Google Trends. |
| 96e96849a325 | tools/companies_house.py | internal_only | internal_only | internal | companies_house — UK Companies House company search and filings. |
| 9c5293005faf | tools/skeleton_compile.py | internal_only | internal_only | internal | skeleton_compile — deterministic skeleton.v1 -> stepchain.v1 compiler. |
| a503b5d73f10 | tools/email_send.py | name:message_needed | message_needed | mutate | email — compose email draft AND send via SMTP. |
| a86bbe09c6ab | tools/youtube_research.py | internal_only | internal_only | internal | youtube_research — search YouTube Shorts and extract transcripts. |
| ac49bdacda7d | tools/web_search.py | internal_only | internal_only | internal | web_search — search via SerpAPI or DuckDuckGo fallback. |
| b29983fd34af | tools/json_patch.py | name:json_patch_needed | json_patch_needed | mutate | json_patch — surgical in-place JSON mutation. |
| b8c6da8dc58d | tools/st_builder.py | internal_only | internal_only | internal | st_builder — curate semantic `.st` files for reprogramme. |
| c06abb141dca | tools/hash_resolve.py | internal_only | internal_only | internal | hash_resolve — resolve blob hashes from trajectory. |
| cb3acc73eb74 | tools/docx_unpack.py | internal_only | internal_only | internal | docx_unpack — Unpack Office files (DOCX, PPTX, XLSX) for editing. |
| cbebdc9c191c | tools/code_exec.py | name:command_needed | command_needed | mutate | code_exec — execute shell commands sandboxed to workspace. |
| d4029da7576c | tools/git_ops.py | name:git_revert_needed | git_revert_needed | mutate | git_ops — version control operations on the project repository. |
| dc78fb9affad | tools/police_api.py | internal_only | internal_only | internal | police_api — fetch UK crime data from data.police.uk. |
| dd7f01674f37 | tools/scan_tree.py | internal_only | internal_only | internal | scan_tree — scan directory tree (listing only) or read a single file. |
| dfc4fdfdfc53 | tools/research_web.py | internal_only | internal_only | internal | research_web — structured web research for qualitative data collection. |
| e71d22d7c7a9 | tools/flood_risk.py | internal_only | internal_only | internal | flood_risk — UK Environment Agency flood risk assessment. |
| e98132ec596d | tools/security_compile.py | internal_only | internal_only | internal | security_compile — unified structural security compiler for step-shaped artifacts. |
| ebbb239177f2 | tools/pdf_check_fields.py | internal_only | internal_only | internal | pdf_check_fields — Check if a PDF has fillable form fields. |
| ecdf7d815920 | tools/pdf_read.py | internal_only | internal_only | internal | pdf_read — extract text content from PDF files. |
| f00f05caca9f | tools/land_registry.py | internal_only | internal_only | internal | land_registry — fetch UK Land Registry Price Paid data. |
| fa5d050ceae6 | tools/postcodes_io.py | internal_only | internal_only | internal | postcodes_io — UK postcode geocoding and area metadata. |
