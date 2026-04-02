{
  "name": "architect",
  "desc": "Architecture sync. Audits source against docs, updates principles + specs, syncs tests.",
  "trigger": "command:architect",
  "author": "developer",
  "steps": [
    {
      "action": "resolve_source_and_docs",
      "desc": "resolve all source files and doc files to see current state",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "audit_and_update_principles",
      "desc": "compare source against PRINCIPLES.md — update stale/missing principles",
      "vocab": "hash_edit_needed",
      "relevance": 0.95,
      "post_diff": true
    },
    {
      "action": "update_module_docs",
      "desc": "sync module specs (step.md, compile.md, loop.md, skills.md, tools.md) with source",
      "vocab": "hash_edit_needed",
      "relevance": 0.85,
      "post_diff": true
    },
    {
      "action": "update_architecture",
      "desc": "sync ARCHITECTURE.md with current module map and vocab",
      "vocab": "hash_edit_needed",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "audit_and_update_tests",
      "desc": "compare tests against updated principles — fix stale tests, add missing coverage",
      "vocab": "hash_edit_needed",
      "relevance": 0.75,
      "post_diff": true
    },
    {
      "action": "run_tests",
      "desc": "run test suite and review results — branch on failures",
      "vocab": "command_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
