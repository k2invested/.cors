{
  "name": "admin",
  "desc": "Canonical admin identity, preferences, and init script for Kenny.",
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
          "entity": "clinton:7d5e36e7721b",
          "name": "Clinton"
        }
      ]
    }
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
      "surface_reprogramme_on_new_preference": true
    },
    "entity_aliases": {
      "my business": {
        "refers_to": "top rate estates ltd:0c106388cfe2",
        "desc": "Whenever I refer to 'my business', interpret it as referring to the entity Top Rate Estates LTD."
      }
    }
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface who Kenny is, how he thinks, how he works",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_principles",
      "desc": "surface system principles Kenny defined \u2014 step primitive, OMO, hash layers",
      "resolve": [
        "principles"
      ],
      "post_diff": false
    },
    {
      "action": "load_recent",
      "desc": "surface recent reasoning chains from prior interactions",
      "resolve": [
        "recent_chains"
      ],
      "post_diff": false
    },
    {
      "action": "load_commitments",
      "desc": "surface active commitments and tracked work",
      "resolve": [
        "commitments"
      ],
      "post_diff": false
    }
  ],
  "reasoning": {
    "surface_reason_needed_for_open_decisions": true,
    "reason_needed_scope": [
      "open decisions",
      "planning",
      "judgment under uncertainty or complexity"
    ],
    "resolve_ambiguity_via_context": true,
    "context_resolution_methods": [
      "traverse available context",
      "review history",
      "inspect semantic trees",
      "analyze workflow structure"
    ],
    "clarify_needed_only_when": [
      "missing info is genuinely only available from user",
      "multiple plausible paths would waste effort or create real risk"
    ],
    "do_not_ask_for_clarification_without_reasoning_first": true
  }
}