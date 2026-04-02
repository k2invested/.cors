{
  "name": "admin",
  "desc": "Kenny's identity and preferences for system orchestration, communication, architecture, and workflow. Includes explicit preferences for reasoning and clarification handling.",
  "trigger": "on_contact:discord:784778107013431296",
  "author": "agent",
  "refs": {
    "commitment_chain_construction_spec": "eefcf9ff7e17",
    "clinton": "e4ac2f28e8bc",
    "cors_ui": "052eee58c273"
  },
  "steps": [],
  "identity": {
    "name": "Kenny",
    "role": "architect",
    "username": "k2authorized",
    "discord_user_id": "784778107013431296",
    "email": "krepchequesupply@gmail.com",
    "context": "Built this system from scratch. Thinks in primitives and recursive structures. Prefers composable solutions over constructions. Will push back hard on overengineering. Speaks fast, thinks in analogies."
  },
  "preferences": {
    "communication": {
      "style": "direct, concise, no filler",
      "mirror_then_extend": true,
      "mirror_communication_style": true,
      "match_energy": true,
      "no_trailing_summaries": true,
      "plain_text_only": true,
      "mobile_first": true
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
}