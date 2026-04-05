{
  "name": "reprogramme",
  "desc": "Persist codon — semantic write primitive for entity/admin state. Reprogramme performs the write after the system has already decided persistence is warranted. It does not own the judgment layer, activation, or workflow construction.",
  "trigger": "on_vocab:reprogramme_needed",
  "author": "system",
  "steps": [
    {
      "action": "load_principles_and_registry",
      "desc": "inject PRINCIPLES.md and the current skill/command registry before persisting semantic state.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "edit_semantic_frame",
      "desc": "surface an editable semantic frame for the target entity/admin package. update semantic state in place; do not originate workflow structure here.",
      "vocab": "hash_edit_needed",
      "relevance": 0.9,
      "post_diff": false
    },
    {
      "action": "commit_and_register",
      "desc": "auto-commit the new or updated .st file so the persisted semantic state becomes part of the next-turn registry and hash resolution surface.",
      "relevance": 0.8,
      "post_diff": false
    }
  ]
}
