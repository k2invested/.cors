# manifest_engine.py

[manifest_engine.py](/Users/k2invested/Desktop/cors/manifest_engine.py) is the package manifestation and rendering layer.

## What It Owns

- stable hashing for persisted chain packages
- semantic-tree rendering for packages and realized chains
- package activation back into runtime gaps
- step-network rendering

## Semantic Tree Render

The standardized compact render now looks like:

```text
semantic_tree:realized_chain:<hash>
chain:<hash> "<desc>" (active, N steps) [timestamp]
origin: <gap>
legend: step{o/m/b/c + frontier}; gap{status + surface + ref-counts}
├─ {o=} step:<id> "<desc>" -> refs:[...]
│  └─ {resolved:o} gap:<id> [hash_resolve_needed] -> refs:[...]
└─ {m+1} step:<id> "<desc>" -> refs:[...]
   └─ {active:m} gap:<id> [hash_edit_needed] -> refs:[...]
```

Embedded packages or chains render as:

```text
@embed:<ref> [activation_mode]
```

## Activation

Activation remains explicit:

- package hashes can be rendered or resolved as structure
- package execution only starts when an activation path turns them back into runtime gaps

That keeps package storage separate from live execution.

## Step Network

The step network render still shows the live package ecology:

- admin/entity packages
- action packages
- codons
- extracted chains
- public command entrypoints

This is the readable package inventory the runtime injects into the model.
