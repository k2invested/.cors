# Gap Config Report

This report reflects the current runtime split:

- executable truth comes from:
  - [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py)
  - [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py)
- semantic routing comes from:
  - [vocab_registry.py](/Users/k2invested/Desktop/cors/vocab_registry.py)

## Configurable Vocab

| Vocab | Classifiable | Target kind | Target ref | Notes |
| --- | --- | --- | --- | --- |
| hash_resolve_needed | observe | tool | `f4f6e4bf8d15` | Public hash observation primitive. |
| pattern_needed | observe | tool | `d5b8c72f9e8c` | Regex grep over workspace files. |
| email_needed | observe | tool | `d58156396f0a` | Read-only email observation. |
| external_context | observe | none | `(none)` | Passive context injection only. |
| hash_edit_needed | mutate | tool | `da6ab1b8070b` | Public hash mutation primitive. |
| stitch_needed | mutate | tool | `533639db50a2` | Explicit post-observe to `ui_output/`. |
| content_needed | mutate | tool | `da6ab1b8070b` | New workspace content through hash manifest. |
| command_needed | mutate | tool | `52f151625add` | Explicit post-observe to `bot.log`. |
| message_needed | mutate | tool | `0aa81af568e8` | Email/message send with artifact-aware post-observe. |
| json_patch_needed | mutate | tool | `da6ab1b8070b` | Structured JSON mutation through hash manifest. |
| git_revert_needed | mutate | tool | `7320bac4d41b` | Git revert operations with commit-aware post-observe. |

## Foundational Bridges

These are not configurable public semantic routes.

| Vocab | Role | Post-observe |
| --- | --- | --- |
| clarify_needed | User-only clarification frontier. | `(none)` |
| reason_needed | Judgment, routing, and child activation. | `(none)` |
| tool_needed | Tool authoring bridge. | `reason_needed` |
| vocab_reg_needed | Semantic routing bridge. | `reason_needed` |
| await_needed | Optional synchronization checkpoint. | `(runtime)` |
| reprogramme_needed | Entity/admin semantic persistence. | `(runtime)` |

## Public Tool Surface

The public tool surface is hash-native and script-derived.

Key public primitives:

| Ref | Source | Mode | Scope | Post-observe |
| --- | --- | --- | --- | --- |
| `f4f6e4bf8d15` | [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py) | observe | workspace | none |
| `da6ab1b8070b` | [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py) | mutate | workspace | derived |
| `52f151625add` | [tools/code_exec.py](/Users/k2invested/Desktop/cors/tools/code_exec.py) | mutate | workspace | artifacts/log |
| `0aa81af568e8` | [tools/email_send.py](/Users/k2invested/Desktop/cors/tools/email_send.py) | mutate | external | artifacts |
| `d58156396f0a` | [tools/email_check.py](/Users/k2invested/Desktop/cors/tools/email_check.py) | observe | external | none |
| `d5b8c72f9e8c` | [tools/file_grep.py](/Users/k2invested/Desktop/cors/tools/file_grep.py) | observe | workspace | none |

Infrastructure that is no longer part of the public tool surface lives in [system/](/Users/k2invested/Desktop/cors/system) or behind [tools/hash](/Users/k2invested/Desktop/cors/tools/hash).

## Public Chain Surface

Current public action chains:

| Ref | Source | Activation | Default gap | OMO |
| --- | --- | --- | --- | --- |
| `69ff0998ff94` | [skills/actions/architect.st](/Users/k2invested/Desktop/cors/skills/actions/architect.st) | `command:architect` | `hash_resolve_needed` | `observe->mutate` |
| `b6375e567354` | [skills/actions/debug.st](/Users/k2invested/Desktop/cors/skills/actions/debug.st) | `command:debug` | `hash_resolve_needed` | `observe->bridge->mutate` |
| `a50c2200e337` | [skills/actions/hash_edit.st](/Users/k2invested/Desktop/cors/skills/actions/hash_edit.st) | `name:hash_edit_needed` | `hash_edit_needed` | `observe->bridge->mutate` |

No public chain-target vocab routes exist yet.
