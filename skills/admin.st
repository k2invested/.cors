{
  "name": "admin",
  "desc": "Canonical admin identity and operator control surface for Kenny. Splits mutable preferences from immutable environment/workflow/vocab context.",
  "trigger": "on_contact:discord:784778107013431296",
  "refs": {
    "identity": null,
    "principles": null,
    "recent_chains": null,
    "commitments": null,
    "commitment_chain_construction_spec": "eefcf9ff7e17",
    "top_rate_estates_ltd": "0c106388cfe2",
    "clinton": "7d5e36e7721b"
  },
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "admin",
    "version_strategy": "hash_pinned"
  },
  "preferences": {
    "communication": {
      "style": "direct, concise, no filler",
      "mirror_then_extend": true,
      "mirror_communication_style": true,
      "match_energy": true,
      "no_trailing_summaries": true,
      "plain_text_only": true,
      "mobile_first": true,
      "discord_tts_friendly": {
        "enabled": true,
        "desc": "When responding on Discord, shape replies for listening (TTS): use natural spoken phrasing, short sentences, smooth cadence, minimal formatting, and avoid robotic or overly formal language."
      }
    },
    "architecture": {
      "compose_not_construct": true,
      "foundational_over_edge_case": true,
      "ask_before_assuming": true,
      "max_construction_lines": 30,
      "bridge_first": true
    },
    "workflow": {
      "dictates_design": true,
      "iterates_rapidly": true,
      "loses_patience_with_overexplanation": true,
      "values_deterministic_control": true,
      "prefers_single_bundled_pr": true
    },
    "meta": {
      "surface_reprogramme_on_new_preference": true,
      "truth_and_causality_model": {
        "trajectory_is_source_of_truth": true,
        "step_hashes_are_causal_memory": true,
        "content_hashes_are_evidence": true,
        "follow_step_hashes_to_reconstruct_how_state_came_to_be": true,
        "use_commit_hashes_and_postconditions_to_distinguish_planned_from_actualized": true,
        "do_not_treat_reasoned_or_planned_state_as_existing_without_resolution_or_commit": true
      }
    },
    "entity_aliases": {
      "my business": {
        "refers_to": "top rate estates ltd:0c106388cfe2",
        "desc": "Whenever I refer to 'my business', interpret it as referring to the entity Top Rate Estates LTD."
      }
    }
  },
  "identity": {
    "name": "Kenny",
    "role": "architect",
    "username": "k2authorized",
    "discord_user_id": "784778107013431296",
    "email": "krepchequesupply@gmail.com",
    "context": "Built this system from scratch. Thinks in primitives and recursive structures. Prefers composable solutions over constructions. Will push back hard on overengineering. Speaks fast, thinks in analogies.",
    "relationships": {
      "blood_brother": [
        {
          "entity": "skills/entities/clinton.st",
          "entity_hash": "clinton:bfa1a96aea7c",
          "name": "Clinton"
        }
      ]
    }
  },
  "steps": [
    {
      "action": "load_preferences",
      "desc": "surface Kenny's mutable communication, workflow, and operator preferences",
      "resolve": [
        "preferences"
      ],
      "post_diff": false
    },
    {
      "action": "load_environment",
      "desc": "surface immutable operator identity plus entity, workflow, vocab, and system-environment control context",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    }
  ]
}
