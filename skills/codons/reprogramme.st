{
  "name": "reprogramme",
  "desc": "Persist codon — stateless semantic write primitive. Creates or updates .st entities and existing packages after the system has already determined persistence is warranted. Reprogramme performs the write; it does not own the judgment layer. No post_diff — reprogramme does not branch or stagnate.",
  "trigger": "on_vocab:reprogramme_needed",
  "author": "system",
  "steps": [
    {
      "action": "load_principles_and_registry",
      "desc": "inject PRINCIPLES.md and the full entity registry (all .st files with step summaries, all /commands) into session. the reprogramme agent must see the ecosystem before building.",
      "vocab": "hash_resolve_needed",
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "edit_semantic_skeleton",
      "desc": "surface an editable semantic_skeleton.v1 frame. if an entity or workflow already exists, edit that frame in place; otherwise fill a bootstrap frame. use the same primitive flow shape as reason-built chains (root, phases, closure) so reprogramme can update semantics and existing flows without collapsing structure.",
      "vocab": "hash_edit_needed",
      "relevance": 0.9,
      "post_diff": false
    },
    {
      "action": "commit_and_register",
      "desc": "auto-commit the new or updated .st file. the commit hash lands on the trajectory. the skill registry reloads on next turn. the entity is now part of the ecosystem — resolvable by hash, surfaceable by relevance.",
      "relevance": 0.8,
      "post_diff": false
    }
  ]
}
