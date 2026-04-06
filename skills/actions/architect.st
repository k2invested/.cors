{
  "name": "architect",
  "desc": "Architecture analysis. Resolves source, principles, docs, and tests, then reasons about drift and may activate hash_edit for the files that actually need syncing.",
  "trigger": "on_vocab:architect_needed",
  "author": "developer",
  "steps": [
    {
      "action": "resolve_source",
      "desc": "resolve the source files relevant to architecture, runtime, registries, and execution flow",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "resolve_principles",
      "desc": "resolve PRINCIPLES.md so architectural judgment stays grounded in the current system philosophy and laws",
      "vocab": "hash_resolve_needed",
      "resolve": [
        "docs/PRINCIPLES.md"
      ],
      "relevance": 0.95,
      "post_diff": false
    },
    {
      "action": "resolve_docs",
      "desc": "resolve ARCHITECTURE.md and the module docs that may have drifted from source",
      "vocab": "hash_resolve_needed",
      "resolve": [
        "docs/ARCHITECTURE.md",
        "docs/step.md",
        "docs/compile.md",
        "docs/loop.md",
        "docs/skills.md",
        "docs/tools.md"
      ],
      "relevance": 0.85,
      "post_diff": false
    },
    {
      "action": "resolve_tests",
      "desc": "resolve the tests that should reflect the current architectural and documentation surface",
      "vocab": "hash_resolve_needed",
      "relevance": 0.8,
      "post_diff": false
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "analyse architectural drift, identify which docs or tests actually need syncing, consider dependencies, failure modes, and mitigations, and if edits are warranted activate hash_edit with those exact file refs and an explicit await_needed choice",
      "relevance": 0.75,
      "post_diff": true
    }
  ]
}
