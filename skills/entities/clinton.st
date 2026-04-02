{
  "name": "clinton",
  "desc": "Cyber security developer who worked with admin (kenny) on v3. Previously based in Lagos, now lives in London and is currently staying in Northampton while studying. Prefers async communication.",
  "trigger": "on_contact:admin | manual",
  "refs": {
    "admin": "72b1d5ffc964"
  },
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "clinton",
    "version_strategy": "hash_pinned"
  },
  "identity": {
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
  "preferences": {
    "communication": {
      "style": "async",
      "timezone": "Europe/London"
    }
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface identity context for clinton",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_preferences",
      "desc": "surface preferences context for clinton",
      "resolve": [
        "preferences"
      ],
      "post_diff": false
    }
  ]
}