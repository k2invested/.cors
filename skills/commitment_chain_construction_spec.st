{
  "name": "commitment_chain_construction_spec",
  "desc": "Semantic state for the commitment chain construction specification: when planning, write the commitment chain as a semantic tree following this spec. Each step encodes full gap configuration. Embed existing .st files by hash in content_refs. Build layers back-to-front: leaf chains first, then mid-level, then top-level orchestration. Resulting tree is directly extractable to .st via chain_to_st.",
  "trigger": "manual",
  "author": "agent",
  "refs": {
    "await": "3ed381ca80b9",
    "commit": "7ce6d9001162",
    "hash_edit": "70772dd86cf9",
    "reason": "c95818926b3c",
    "reprogramme": "b5a141611567"
  },
  "steps": []
}