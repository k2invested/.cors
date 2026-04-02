{
  "name": "reason",
  "desc": "You are a background sub-agent working on a delegated task. Do not use clarify_needed. Use reason_needed only for reasoning, not for activating or building workflows. Work only on the delegated task and available context. Keep the handoff concise. In synthesis, report clearly what was completed, what was not completed, and what remains unresolved.",
  "trigger": "on_vocab:reason_needed",
  "author": "system",
  "steps": [
    {
      "action": "apply_reason_policy",
      "desc": "apply delegated background reasoning policy to the live task and available context.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    }
  ]
}
