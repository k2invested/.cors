{
  "name": "admin",
  "desc": "Kenny — system architect, step kernel builder, primary admin user",
  "trigger": "on_contact:admin",
  "refs": {
    "identity": null,
    "principles": null,
    "recent_chains": null,
    "commitments": null
  },
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
    }
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface who Kenny is, how he thinks, how he works",
      "resolve": ["identity"],
      "post_diff": false
    },
    {
      "action": "load_principles",
      "desc": "surface system principles Kenny defined — step primitive, OMO, hash layers",
      "resolve": ["principles"],
      "post_diff": false
    },
    {
      "action": "load_recent",
      "desc": "surface recent reasoning chains from prior interactions",
      "resolve": ["recent_chains"],
      "post_diff": false
    },
    {
      "action": "load_commitments",
      "desc": "surface active commitments and tracked work",
      "resolve": ["commitments"],
      "post_diff": false
    }
  ]
}
