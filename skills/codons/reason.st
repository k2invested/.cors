{
  "name": "reason",
  "desc": "Start codon — planning primitive, reorientation checkpoint, and heartbeat trigger. Three roles: (1) PLAN: decompose complex tasks into commitment chains built bottom-up — lower layers first so higher layers can embed them. (2) REORIENT: when the compiler rejects a chain or an immutable path is violated, reason_needed fires as the recalibration checkpoint. (3) HEARTBEAT: automatic post-synth reason_needed persists as a dangling gap, causing the agent to inspect background sub-agent progress next turn — render tree, assess, close/revisit/refine.",
  "trigger": "on_vocab:reason_needed",
  "author": "system",
  "steps": [
    {
      "action": "render_reasoning_trees",
      "desc": "resolve and render all naturally formed reasoning step chains as fully bloomed semantic trees — same shape as trajectory render. pure observation, no mutation. for heartbeat: render the sub-agent's chain tree. for planning: render existing commitment chains + available .st files as embeddable components.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "assess_and_route",
      "desc": "study the rendered trees. six paths: (1) observe only — gain clarity, may surface clarify_needed. (2) refine — update a mutable reasoning commitment via hash_edit. (3) manifest — reference a commitment hash + compose a prompt to activate an agent. commit_needed injected as last step behind all commitment gaps. (4) plan — decompose a complex task into a semantic tree specification (see chain construction spec). consecutive reason_needed steps build layers bottom-up. (5) heartbeat — inspect background sub-agent tree, close/revisit/refine+reactivate. (6) reorient — after compiler rejection, recalibrate approach.",
      "relevance": 0.9,
      "post_diff": true
    },
    {
      "action": "construct_or_act",
      "desc": "if planning: write the commitment chain as a semantic tree following the chain construction specification. each step encodes full gap configuration {action, desc, vocab, relevance, post_diff, content_refs, step_refs}. embed existing .st files by placing their hash in a step's content_refs — their gaps will disperse depth-first when resolved. embed await_needed after any background trigger. write new .st embeddings inline as steps with all 7 gap axes specified. build layers back-to-front: leaf chains first (lowest layer), then mid-level chains that adopt them, then top-level orchestration. the resulting tree is directly extractable to .st via chain_to_st. if refining: hash_edit updates the reasoning chain. if manifesting: compose agent trigger + inject commitment gaps + trailing commit_needed. if heartbeat: emit close/revisit/refine gaps. if reorienting: reconstruct the rejected chain with corrections.",
      "vocab": "hash_edit_needed",
      "relevance": 0.8,
      "post_diff": true
    },
    {
      "action": "post_reason_check",
      "desc": "after construction, manifestation, or reorientation: re-render affected reasoning trees to verify coherence. check: (1) all await codons present after background triggers. (2) leaf chains exist before parent chains reference them. (3) relevance descending within each chain. (4) post_diff set correctly (false for deterministic steps, true for decision points). (5) all 7 gap axes present on constructed steps. (6) existing .st embeddings referenced by valid hash. if the constructed tree passes verification, it is ready for execution or crystallization to .st via chain_to_st.",
      "vocab": "hash_resolve_needed",
      "relevance": 0.7,
      "post_diff": true
    }
  ]
}
