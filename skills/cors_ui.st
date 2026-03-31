{
  "name": "cors_ui",
  "desc": "Constraint Orchestration Reasoning System. Not related to web UI or cybersecurity CORS standards.",
  "trigger": "manual",
  "author": "agent",
  "refs": {},
  "steps": [
    {
      "action": "entity_update",
      "desc": "knowledge updated from conversation"
    }
  ],
  "constraints": {
    "not_web_ui": true,
    "not_cybersecurity_cors": true
  }
}