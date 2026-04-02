{
  "name": "user_discord_784778107013431296",
  "desc": "Bootstrap entity for inbound contact discord:784778107013431296",
  "trigger": "on_contact:discord:784778107013431296",
  "author": "system",
  "refs": {},
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface who this inbound contact appears to be from current known metadata",
      "post_diff": false,
      "resolve": [
        "identity"
      ]
    },
    {
      "action": "load_onboarding_preferences",
      "desc": "surface get-to-know instructions and passive profile-maintenance preferences for this contact",
      "post_diff": false,
      "resolve": [
        "preferences"
      ]
    },
    {
      "action": "load_access_rules",
      "desc": "surface current access and execution permissions for this contact",
      "post_diff": false,
      "resolve": [
        "access_rules"
      ]
    },
    {
      "action": "load_init_state",
      "desc": "surface onboarding and init state for this contact",
      "post_diff": false,
      "resolve": [
        "init"
      ]
    }
  ],
  "identity": {
    "external_id": "discord:784778107013431296",
    "username": "discord:784778107013431296",
    "source": "inbound_contact",
    "context": "Auto-bootstrapped from a first inbound message. Minimal identity only until init is completed."
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
  "access_rules": {
    "observe": true,
    "reprogramme": true,
    "compile": false,
    "activate_existing": false,
    "mutate": false
  },
  "init": {
    "status": "pending",
    "mode": "first_contact",
    "ask_profile_questions": true,
    "seed_message": "please remove the mirror then extend approach from my preferences",
    "next_action": "Ask a small number of concise onboarding questions when useful. When enough stable profile is known, reprogramme this entity to set init.status to complete."
  }
}