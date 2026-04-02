{
  "name": "commitment_chain_construction_spec",
  "desc": "Semantic state for the commitment chain construction specification: when planning, write the commitment chain as a semantic tree following the chain construction spec. Each step encodes full gap configuration (action, desc, vocab, relevance, post_diff, content_refs, step_refs). Embed existing .st files by placing their hash in a step's content_refs so their gaps disperse depth-first when resolved. Embed await_needed after any background trigger. Write new .st embeddings inline as steps with all 7 gap axes specified. Build layers back-to-front: leaf chains first, then mid-level chains that adopt them, then top-level orchestration. The resulting tree is directly extractable to .st via chain_to_st. If refining, hash_edit updates the reasoning chain. If manifesting, compose agent trigger and inject commitment gaps with trailing commit_needed. If heartbeat, emit close/revisit/refine gaps. If reorienting, reconstruct the rejected chain with corrections.",
  "trigger": "manual",
  "author": "agent",
  "refs": {
    "reason": "c95818926b3c",
    "commit": "7ce6d9001162",
    "hash_edit": "70772dd86cf9",
    "reprogramme": "b5a141611567",
    "await": "3ed381ca80b9"
  },
  "steps": []
}