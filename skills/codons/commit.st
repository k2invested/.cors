{
  "name": "commit",
  "desc": "End codon for reasoning commitments. Reintegrates the commitment chain's full trajectory as a semantic tree into the main agent's context. Closes the reasoning chain.",
  "trigger": "on_vocab:commit_needed",
  "author": "developer",
  "steps": [
    {
      "action": "render_commitment_tree",
      "desc": "resolve and render the full commitment chain as a semantic tree — every step, gap, and decision visible to the main agent",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "reintegrate",
      "desc": "inject the rendered commitment tree into the main trajectory context. the main agent now has full visibility into everything the commitment chain produced.",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "close_or_continue",
      "desc": "assess: is the commitment resolved? if yes, close the chain — hash compresses. if no, articulate remaining gaps for the next activation cycle.",
      "relevance": 0.8,
      "post_diff": true
    }
  ]
}
