{
  "name": "tinchy.stryka",
  "desc": "Bootstrap entity for inbound contact discord:719157451496357949",
  "trigger": "on_contact:discord:719157451496357949",
  "refs": {},
  "artifact": {
    "kind": "hybrid",
    "protected_kind": "action",
    "lineage": "tinchy.stryka",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "external_id": "discord:719157451496357949",
    "username": "tinchy.stryka",
    "discord_user_id": "719157451496357949",
    "name": "tinchy.stryka",
    "source": "inbound_contact",
    "context": "Auto-bootstrapped from a first inbound message. Minimal identity only until init is completed."
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
      "favourite_team": "Tottenham"
    }
  },
  "access_rules": {
    "observe": true,
    "reprogramme": true,
    "compile": false,
    "activate_existing": false,
    "mutate": false
  },
  "root": "phase_initiate_entity_1",
  "phases": [
    {
      "id": "phase_initiate_entity_1",
      "kind": "observe",
      "goal": "This is a newly bound contact entity. Ask a small number of concise get-to-know-you questions when useful, learn stable facts and preferences over time, and surface reprogramme_needed when new durable knowledge should be written back to this entity.",
      "action": "initiate_entity",
      "gap_template": {
        "desc": "This is a newly bound contact entity. Ask a small number of concise get-to-know-you questions when useful, learn stable facts and preferences over time, and surface reprogramme_needed when new durable knowledge should be written back to this entity.",
        "content_refs": [
          "identity",
          "preferences",
          "access_rules",
          "init"
        ],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "inline"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_close": "phase_done"
      }
    },
    {
      "id": "phase_done",
      "kind": "terminal",
      "goal": "done",
      "action": "close_loop",
      "terminal": true
    }
  ],
  "steps": [
    {
      "action": "initiate_entity",
      "desc": "This is a newly bound contact entity. Ask a small number of concise get-to-know-you questions when useful, learn stable facts and preferences over time, and surface reprogramme_needed when new durable knowledge should be written back to this entity.",
      "post_diff": false,
      "resolve": [
        "identity",
        "preferences",
        "access_rules",
        "init"
      ]
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_done",
      "requires_no_active_gaps": true
    },
    "failure": {
      "allow_force_close": true,
      "allow_clarify_terminal": true
    },
    "limits": {
      "max_chain_depth": 15,
      "max_redirects": 4
    }
  }
}