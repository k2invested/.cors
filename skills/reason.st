{
  "name": "reason",
  "desc": "Observation bridge + agency codon. Renders reasoning chains as semantic trees. Can manifest commitment agents. When manifesting, commit_needed is injected as last step behind all commitment gaps.",
  "trigger": "on_vocab:reason_needed",
  "author": "developer",
  "steps": [
    {
      "action": "render_reasoning_trees",
      "desc": "resolve and render all naturally formed reasoning step chains as fully bloomed semantic trees — same shape as trajectory render. pure observation, no mutation.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "assess_and_route",
      "desc": "study the rendered trees. three paths: (1) observe only — gain clarity, may surface clarify_needed. (2) refine — update a mutable reasoning commitment. (3) manifest — reference a commitment hash + compose a prompt to activate an agent. if manifest, the commitment's gaps are injected with commit_needed as the final step (lowest relevance, reintegrates after all commitment gaps resolve).",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "refine_or_manifest",
      "desc": "if refine: update the reasoning commitment chain via hash_edit. if manifest: compose agent trigger and inject commitment gaps + trailing commit_needed. if neither: resolve.",
      "vocab": "hash_edit_needed",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "post_reason_check",
      "desc": "after refinement or manifestation, re-render affected reasoning trees to verify coherence.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
