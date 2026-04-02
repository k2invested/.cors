{
  "name": "reason",
  "desc": "Delegation operating preferences for background reason_needed work. Handle the live task directly. Return either a validator-passing skeleton.v1 for new workflow origination or a background activation of an existing workflow by hash. Own persistence judgment when semantic state must be judged before writing. Keep the handoff concise. Use available context before clarifying.",
  "trigger": "on_vocab:reason_needed",
  "author": "system",
  "steps": [
    {
      "action": "load_reason_context",
      "desc": "load delegation operating preferences, current step network, and relevant package context for the live task.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "choose_reason_path",
      "desc": "choose one path only: submit_skeleton for new reusable workflow origination, or activate_existing_workflow for existing-package delegation. both are background outputs.",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "author_or_delegate",
      "desc": "if authoring: return one valid skeleton.v1. if activating: select an existing workflow by hash and provide a concise task prompt.",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "verify_selected_path",
      "desc": "verify that the selected path fits the task and remains a background delegation output.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
