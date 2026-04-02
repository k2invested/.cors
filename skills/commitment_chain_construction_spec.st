{
  "name": "commitment_chain_construction_spec",
  "desc": "Semantic state for the commitment chain construction specification: when planning, write the commitment chain as a semantic tree following the chain construction spec. Each step encodes full gap configuration. Embed existing .st files by placing their hash in a step's content_refs. Embed await_needed after any background trigger. Write new .st embeddings inline as steps with all 7 gap axes specified. Build layers back-to-front: leaf chains first, then mid-level chains that adopt them, then top-level orchestration. The resulting tree is directly extractable to .st via chain_to_st. If refining: hash_edit updates the reasoning chain. If manifesting: compose agent trigger + inject commitment gaps + trailing commit_needed. If judging persistence: articulate whether the semantic update is stable enough to persist and surface reprogramme_needed only when warranted. If heartbeat: emit close/revisit/refine gaps. If reorienting: reconstruct the rejected chain with corrections.",
  "trigger": "manual",
  "refs": {
    "await": "3ed381ca80b9",
    "commit": "7ce6d9001162",
    "hash_edit": "70772dd86cf9",
    "reason": "684dc74c7a74",
    "reprogramme": "63334a75ecba"
  },
  "artifact": {
    "kind": "hybrid",
    "protected_kind": "action",
    "lineage": "commitment_chain_construction_spec",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "purpose": "Defines the canonical structure and rules for constructing commitment chains as semantic trees, ensuring all planning, refinement, manifestation, and persistence steps are composable, auditable, and hash-native."
  },
  "constraints": {
    "must_follow_chain_spec": true,
    "must_embed_existing_st_by_hash": true,
    "must_build_layers_back_to_front": true
  },
  "scope": "All planning, refinement, manifestation, and persistence flows that require commitment chain construction or semantic tree extraction.",
  "steps": []
}