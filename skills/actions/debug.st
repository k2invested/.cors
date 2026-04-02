{
  "name": "debug",
  "desc": "Self-debug loop. Resolves source, trajectory, and logs — then diagnoses and fixes.",
  "trigger": "command:debug",
  "author": "developer",
  "steps": [
    {
      "action": "resolve_context",
      "desc": "resolve source code, trajectory render, and execution logs",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "diagnose",
      "desc": "identify the gap between intended and actual behavior",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "fix",
      "desc": "apply the fix",
      "vocab": "hash_edit_needed",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "verify",
      "desc": "run tests to verify the fix",
      "vocab": "command_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
