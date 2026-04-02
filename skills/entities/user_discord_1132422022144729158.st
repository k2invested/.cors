{
  "name": "Courtney",
  "desc": "Semantic entity profile for Courtney (discord:1132422022144729158), tracking identity, preferences, and professional context for ongoing interaction. Includes known information and placeholders for future profile enrichment.",
  "trigger": "on_contact:discord:1132422022144729158",
  "refs": {},
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "user_discord_1132422022144729158",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "external_id": "discord:1132422022144729158",
    "username": "discord:1132422022144729158",
    "source": "inbound_contact",
    "context": "Auto-bootstrapped from a first inbound message. Minimal identity only until init is completed.",
    "name": "Courtney",
    "age": null,
    "target_role": "Video editor / edit assistant"
  },
  "preferences": {
    "onboarding": {
      "deterministic_reprogramme_mode": "bootstrap_only",
      "get_to_know_entity": true,
      "ask_concise_questions": true,
      "question_strategy": "Ask a small number of concise get-to-know-you questions when useful, rather than interrogating every turn.",
      "profile_update_mode": "Passively surface explicit reprogramme_needed gaps when stable traits, preferences, or user-corrected context should be persisted.",
      "passive_reprogramme_optional": true,
      "passive_reprogramme_removal": "The user may later ask to remove passive profile-maintenance behavior from this entity.",
      "completion_rule": "Once enough stable profile is known, update this entity and set init.status to complete."
    }
  },
  "constraints": {},
  "sources": [],
  "scope": "Professional and onboarding context for Courtney as a video editor / edit assistant. Additional background, skills, and achievements to be added as provided.",
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface identity context for Courtney",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_preferences",
      "desc": "surface preferences context for Courtney",
      "resolve": [
        "preferences"
      ],
      "post_diff": false
    },
    {
      "action": "load_scope",
      "desc": "surface scope context for Courtney",
      "resolve": [
        "scope"
      ],
      "post_diff": false
    }
  ],
  "init": {
    "status": "pending",
    "mode": "first_contact",
    "ask_profile_questions": true,
    "seed_message": "Could you pattern me a better cv",
    "next_action": "Ask a small number of concise onboarding questions when useful. When enough stable profile is known, reprogramme this entity to set init.status to complete."
  },
  "access_rules": {
    "observe": true,
    "reprogramme": true,
    "compile": false,
    "activate_existing": false,
    "mutate": false
  }
}