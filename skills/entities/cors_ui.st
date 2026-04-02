{
  "name": "cors_ui",
  "desc": "Constraint Orchestration Reasoning System. Not related to web UI or cybersecurity CORS standards.",
  "trigger": "manual",
  "author": "agent",
  "refs": {},
  "constraints": {
    "not_web_ui": true,
    "not_cybersecurity_cors": true
  },
  "steps": [
    {
      "action": "load_constraints",
      "desc": "surface constraints context for cors_ui",
      "resolve": [
        "constraints"
      ],
      "post_diff": false
    }
  ]
}
