{
  "name": "reprogramme",
  "desc": "Persist codon — world-building engine. Creates or updates .st entities and /command workflows. Manifestation is always background: fire, commit, move on. No post_diff — reprogramme does not branch or stagnate. If the reprogramme triggers a long-scope background workflow, the heartbeat mechanism (automatic post-synth reason_needed) guarantees reintegration.",
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
      "action": "compose_st",
      "desc": "compose the .st file from semantic intent. reuse existing entities before building new. for entities: identity, preferences, constraints, sources, scope. for workflows: steps with action/desc/vocab/relevance/post_diff. for /commands: trigger command:name. the compose is guided by PRINCIPLES.md — composition over construction.",
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
