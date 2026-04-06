{
  "name": "debug",
  "desc": "Reason-activated debug analysis. Resolves principles, attached source, turn tree, and failed output log, then reasons about fixes and may activate hash_edit.",
  "trigger": "manual",
  "author": "developer",
  "steps": [
    {
      "action": "resolve_principles",
      "desc": "resolve PRINCIPLES.md before debugging so the analysis stays grounded in current system laws",
      "vocab": "hash_resolve_needed",
      "resolve": [
        "docs/PRINCIPLES.md"
      ],
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "resolve_source",
      "desc": "resolve the attached source code files implicated in the failure from activation content refs",
      "vocab": "hash_resolve_needed",
      "relevance": 0.95,
      "post_diff": false
    },
    {
      "action": "resolve_turn_tree",
      "desc": "resolve the attached turn semantic tree and nearby failing steps from activation step refs",
      "vocab": "hash_resolve_needed",
      "relevance": 0.9,
      "post_diff": false
    },
    {
      "action": "resolve_failed_log",
      "desc": "resolve the failed turn output log and any attached failure artifacts from activation content refs",
      "vocab": "hash_resolve_needed",
      "relevance": 0.85,
      "post_diff": false
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "analyse the failure, propose concrete solutions, and consider dependencies, failure modes, and mitigations; if a code change is warranted, activate hash_edit with the best fix prompt",
      "relevance": 0.8,
      "post_diff": true
    }
  ]
}
