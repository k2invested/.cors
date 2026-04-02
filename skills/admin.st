{
  "name": "admin",
  "desc": "Kenny \u2014 system architect, step kernel builder, primary admin user. Communication style and energy are mirrored, not just words. System should surface reprogramme_needed gaps whenever new information about Kenny's preferences is learned.",
  "trigger": "on_contact:admin",
  "author": "agent",
  "refs": {
    "identity": "kenny:72b1d5ffc964"
  },
  "steps": [],
  "identity": {
    "name": "Kenny",
    "role": "architect",
    "username": "k2authorized",
    "email": "krepchequesupply@gmail.com",
    "context": "Built this system from scratch. Thinks in primitives and recursive structures. Prefers composable solutions over constructions. Will push back hard on overengineering. Speaks fast, thinks in analogies, needs mirror-then-extend before implementation."
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
    }
  }
}