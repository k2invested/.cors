{
  "name": "reason",
  "desc": "You are reasoning inline within the current turn. Do not use clarify_needed by default. Use reason_needed for stateful judgment and current-turn reasoning, not as a passive deferral. For new skills/actions/*.st origination, author through the semantic_skeleton path and hand off concrete reprogramme actualization instead of restating a generic file-write request. Keep the handoff concise. In synthesis, report clearly what was completed, what was not completed, and what remains unresolved.",
  "trigger": "on_vocab:reason_needed",
  "author": "system",
  "steps": [
    {
      "action": "apply_reason_policy",
      "desc": "apply inline current-turn reasoning policy to the live task and available context.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    }
  ]
}
