{
  "name": "Top Rate Estates LTD",
  "desc": "Core identity and mission for Top Rate Estates LTD, a property management and investment company developing AI agent and ML automation capabilities.",
  "trigger": "manual",
  "refs": {},
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "top_rate_estates_ltd",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "legal_name": "Top Rate Estates LTD",
    "type": "business",
    "domain": "property management and investment",
    "location": "UK",
    "status": "starting",
    "specialization": "AI agents and ML solutions for property operations and investment workflows"
  },
  "preferences": {
    "mission": "Build a modern property management and investment company that uses AI agents and ML-driven automations to improve operations, insight, and service quality.",
    "focus_areas": [
      "property management",
      "property investment",
      "AI agents",
      "ML solutions",
      "workflow automation",
      "operational intelligence"
    ],
    "automation_targets": [
      "tenant and landlord communications",
      "deal and property workflow tracking",
      "document processing",
      "market research support",
      "internal operations"
    ],
    "values": [
      "integrity",
      "professionalism",
      "clarity",
      "leverage through automation"
    ]
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface identity context for Top Rate Estates LTD",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_preferences",
      "desc": "surface preferences context for Top Rate Estates LTD",
      "resolve": [
        "preferences"
      ],
      "post_diff": false
    }
  ]
}
