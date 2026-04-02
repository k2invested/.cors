{
  "name": "reason",
  "desc": "Start codon — parent reasoning context for reason_needed activations. It conditions the reasoning agent the way admin.st conditions the main agent, but it is not itself the target workflow being activated. Three primary outputs: (1) CONTINUE: proceed with better-formed next gaps or an explicit justified decision using current context. (2) AUTHOR: submit one validator-passing skeleton.v1 when a new reusable action/workflow package must be created. (3) ACTIVATE: select an existing workflow/package by hash and delegate it current_turn or background. It also remains the persistence-judgment layer, reorientation checkpoint, and heartbeat parent context.",
  "trigger": "on_vocab:reason_needed",
  "author": "system",
  "steps": [
    {
      "action": "load_reason_context",
      "desc": "inject deterministic reasoning posture for the live origin gap. render the current step network, relevant semantic trees, and available packages. reason.st is parent context for this activation, not the workflow being activated.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "choose_reason_path",
      "desc": "choose exactly one path for this reason activation: continue_with_gaps, submit_skeleton, or activate_existing_workflow. use continue when judgment or better clarity is enough. use submit_skeleton for new reusable workflow origination. use activate_existing_workflow when an existing package should handle the task.",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "author_or_delegate",
      "desc": "if continuing: articulate the next lawful gap(s) or an explicit justified decision directly so later steps can rely on it by step hash. if authoring: return one valid skeleton.v1. if activating: select an existing workflow by hash and provide the task prompt/payload. embedded activations stay current_turn; background is only for delegated autonomous work.",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "verify_selected_path",
      "desc": "verify that the selected path fits the task: new reusable workflows must leave reason as skeleton.v1 submissions, existing workflows activate by hash, embedded activations remain current_turn, and delegated autonomous work is the only background case.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
