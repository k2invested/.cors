{
  "name": "reason",
  "desc": "Start codon — parent reasoning context for background reason_needed activations. It conditions the reasoning agent the way admin.st conditions the main agent, but it is not itself the target workflow being activated. reason_needed is always a background delegation boundary. Two primary outputs: (1) AUTHOR: submit one validator-passing skeleton.v1 when a new reusable action/workflow package must be created. (2) ACTIVATE: select an existing workflow/package by hash and delegate it in background. It also remains the persistence-judgment layer, reorientation checkpoint, and heartbeat parent context.",
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
      "desc": "choose exactly one path for this reason activation: submit_skeleton or activate_existing_workflow. use submit_skeleton for new reusable workflow origination. use activate_existing_workflow when an existing package should handle the task. both paths are background delegation outputs.",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "author_or_delegate",
      "desc": "if authoring: return one valid skeleton.v1. if activating: select an existing workflow by hash and provide the task prompt/payload. embedded activations belong inside authored current-turn workflows; workflow delegation selected by reason is background work.",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "verify_selected_path",
      "desc": "verify that the selected path fits the task: new reusable workflows must leave reason as skeleton.v1 submissions, existing workflows activate by hash, and reason itself never manifests as inline current-turn work.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
