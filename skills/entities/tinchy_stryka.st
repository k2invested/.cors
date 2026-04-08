{
  "name": "tinchy.stryka",
  "desc": "Discord entity for Clinton (tinchystricker). Canonical info and identity mapping from clinton:bfa1a96aea7c.",
  "trigger": "on_contact:discord:719157451496357949",
  "refs": {
    "clinton": "bfa1a96aea7c"
  },
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "tinchy.stryka",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "external_id": "discord:719157451496357949",
    "username": "tinchystricker",
    "discord_user_id": "719157451496357949",
    "name": "Clinton",
    "source": "identity mapping from clinton:bfa1a96aea7c",
    "context": "Auto-bootstrapped from a first inbound message. Minimal identity only until init is completed.",
    "role": "cyber security developer",
    "location": "London",
    "current_stay": "Northampton",
    "current_status": "studying",
    "specialty": "backend systems",
    "previous_location": "Lagos",
    "collaborated_with": [
      "72b1d5ffc964"
    ],
    "project_history": [
      "v3"
    ]
  },
  "init": {
    "status": "pending",
    "mode": "first_contact",
    "ask_profile_questions": true,
    "seed_message": "hi",
    "next_action": "Ask a small number of concise onboarding questions when useful. When enough stable profile is known, reprogramme this entity to set init.status to complete."
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
    },
    "interests": {
      "sports": [
        "football"
      ],
      "favourite_team": "Tottenham",
      "football_engagement": [
        "play",
        "watch"
      ],
      "football_attendance": "never_attended_in_person"
    },
    "communication": {
      "style": "async",
      "timezone": "Europe/London"
    }
  },
  "access_rules": {
    "observe": true,
    "reprogramme": true,
    "compile": false,
    "activate_existing": false,
    "mutate": false
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface identity context for tinchy.stryka",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_preferences",
      "desc": "surface preferences context for tinchy.stryka",
      "resolve": [
        "preferences"
      ],
      "post_diff": false
    },
    {
      "action": "load_access_rules",
      "desc": "surface access_rules context for tinchy.stryka",
      "resolve": [
        "access_rules"
      ],
      "post_diff": false
    },
    {
      "action": "load_init",
      "desc": "surface init context for tinchy.stryka",
      "resolve": [
        "init"
      ],
      "post_diff": false
    }
  ]
}