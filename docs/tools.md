# tools

The executable layer is split between public tools in [tools/](/Users/k2invested/Desktop/cors/tools) and immutable support infrastructure in [system/](/Users/k2invested/Desktop/cors/system).

## Public Tool Surface

The public tool registry is derived from the tool tree itself through [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py).

Each public tool script must declare:

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

Specialized readers and mutators behind them are implementation detail:

- internal handlers live under [tools/hash](/Users/k2invested/Desktop/cors/tools/hash)
- routing lives in [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py)

## Public Routing

The main routed public tools are now:

- `hash_resolve_needed` -> [tools/hash_resolve.py](/Users/k2invested/Desktop/cors/tools/hash_resolve.py)
- `hash_edit_needed` -> [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
- `content_needed` -> [tools/hash_manifest.py](/Users/k2invested/Desktop/cors/tools/hash_manifest.py)
- `command_needed` -> [tools/code_exec.py](/Users/k2invested/Desktop/cors/tools/code_exec.py)
- `email_needed` -> [tools/email_send.py](/Users/k2invested/Desktop/cors/tools/email_send.py)
- `git_revert_needed` -> [tools/git_ops.py](/Users/k2invested/Desktop/cors/tools/git_ops.py)

Other external or domain-specific tools remain separate public tools until vocab maps them.

## Tool Writer

`tool_needed` owns tool-tree authoring.

Current behavior:

- any mutation under `tools/` is rerouted by tree policy to `tool_needed`
- `tool_needed` sees the public tool registry before it writes
- [system/tool_builder.py](/Users/k2invested/Desktop/cors/system/tool_builder.py) scaffolds the script
- [system/validate_tool_contract.py](/Users/k2invested/Desktop/cors/system/validate_tool_contract.py) validates the required metadata
- successful reintegration returns to `reason_needed`

## Vocab Routing Writer

`vocab_reg_needed` owns configurable semantic routing.

Current behavior:

- mutation of [vocab_registry.py](/Users/k2invested/Desktop/cors/vocab_registry.py) is rerouted to `vocab_reg_needed`
- it sees:
  - the public tool registry
  - the public chain registry
  - the current configurable vocab registry
- [system/vocab_builder.py](/Users/k2invested/Desktop/cors/system/vocab_builder.py) writes hash-native vocab routes
- successful reintegration also returns to `reason_needed`

## Registry Split

Use the registries like this:

- [system/tool_registry.py](/Users/k2invested/Desktop/cors/system/tool_registry.py)
  - public selectable tools
- [system/chain_registry.py](/Users/k2invested/Desktop/cors/system/chain_registry.py)
  - public selectable chains
- [system/hash_registry.py](/Users/k2invested/Desktop/cors/system/hash_registry.py)
  - internal file-type routing behind the hash primitives
- [system/tool_contract.py](/Users/k2invested/Desktop/cors/system/tool_contract.py)
  - deterministic script-level contract parsing

Chain composition should reference the public tool or chain surface, not the hidden handlers behind the hash primitives.
