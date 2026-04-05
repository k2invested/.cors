# tools

The tool layer is now split between:

- public first-class tools in [tools/tool_registry.py](/Users/k2invested/Desktop/cors/tools/tool_registry.py)
- internal hash handlers in [tools/hash/registry.py](/Users/k2invested/Desktop/cors/tools/hash/registry.py)

## Public Tool Surface

The public tool registry is derived from the tool tree itself. Each public tool script must declare:

- `TOOL_DESC`
- `TOOL_MODE`
- `TOOL_SCOPE`
- `TOOL_POST_OBSERVE`

Optional:

- `TOOL_DEFAULT_ARTIFACTS`
- `TOOL_ARTIFACT_PARAMS`
- `TOOL_RUNTIME_ARTIFACT_KEY`

The registry reads those fields directly from the script file.

## Hash Primitives

The two core file primitives are:

- [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)

These are the system eyes and hands for workspace-backed files.

Specialized readers and mutators behind them are implementation detail, not first-class public tools.

## Public Routing

The main routed public tools are now:

- `hash_resolve_needed` -> [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- `hash_edit_needed` -> [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
- `content_needed` -> [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
- `script_edit_needed` -> [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
- `tool_needed` -> [tools/tool_builder.py](/Users/k2invested/Desktop/cors/tools/tool_builder.py)

Other external or domain-specific tools remain separate public tools.

## Tool Writer

`tool_needed` now owns tool-tree authoring.

Current behavior:

- any mutation under `tools/` is rerouted by tree policy to `tool_needed`
- `tool_needed` sees the public tool registry before it writes
- [tools/tool_builder.py](/Users/k2invested/Desktop/cors/tools/tool_builder.py) scaffolds the script
- [tools/validate_tool_contract.py](/Users/k2invested/Desktop/cors/tools/validate_tool_contract.py) validates the required metadata

## Registry Split

Use the registries like this:

- [tools/tool_registry.py](/Users/k2invested/Desktop/cors/tools/tool_registry.py)
  - public selectable tools
- [tools/hash/registry.py](/Users/k2invested/Desktop/cors/tools/hash/registry.py)
  - internal file-type routing behind the hash primitives

Chain composition should reference the public tool surface, not the hidden handlers behind the hash primitives.
