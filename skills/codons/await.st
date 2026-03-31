{
  "name": "await",
  "desc": "Pause codon — synchronization checkpoint for background workflows. Suspends the parent chain until the referenced sub-agent completes, then injects the sub-agent's full semantic tree into the parent context. The parent inspects, may correct, then resumes. If the parent turn ends before the sub-agent finishes, the await persists as a dangling gap — the heartbeat mechanism picks it up next turn.",
  "trigger": "on_vocab:await_needed",
  "author": "system",
  "steps": [
    {
      "action": "suspend_and_wait",
      "desc": "suspend parent chain at this checkpoint. if the sub-agent has already completed, proceed immediately. if still running, persist this gap as dangling — the heartbeat will resume it next turn when the sub-agent's chain closes.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "render_subagent_tree",
      "desc": "resolve and render the sub-agent's full commitment chain as a semantic tree — every step, gap, decision, and mutation visible. same shape as trajectory render. this is the reintegration primitive — the parent sees everything the sub-agent produced.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.9,
      "post_diff": false
    },
    {
      "action": "inspect_and_route",
      "desc": "parent agent inspects the rendered sub-agent tree. three paths: (1) accept — results are good, close the await, resume parent chain. (2) correct — something is wrong, emit refinement gaps. (3) reactivate — the sub-agent's work surfaced new requirements, trigger further background work (which will need its own await or heartbeat).",
      "relevance": 0.8,
      "post_diff": true
    }
  ]
}
