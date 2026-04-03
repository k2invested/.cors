{
  "name": "research",
  "desc": "Composable research workflow. Triggered by vocab: research_needed. Accepts a research query and classifies the research type. Prepares for downstream research actions (web, document, or domain-specific).",
  "trigger": "on_vocab:research_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "research",
    "version_strategy": "hash_pinned"
  },
  "input": {
    "query": {
      "desc": "The research question or topic to investigate.",
      "required": true,
      "type": "string"
    }
  },
  "output": {
    "classification": {
      "desc": "Type of research: web, document, or domain-specific.",
      "type": "string",
      "enum": [
        "web",
        "document",
        "domain"
      ]
    },
    "rationale": {
      "desc": "Reasoning for the classification.",
      "type": "string"
    }
  },
  "root": "phase_classify",
  "phases": [
    {
      "id": "phase_classify",
      "name": "phase_classify",
      "desc": "Classify the research query as web, document, or domain-specific. Output classification and rationale.",
      "gap_template": {
        "desc": "Determine if the query is best suited for web search, document analysis, or domain-specific research. Output classification and rationale.",
        "axes": {
          "relevance": 1.0,
          "confidence": 0.9,
          "grounded": 0.0,
          "clarity": 1.0,
          "composability": 1.0,
          "persistence": 0.0,
          "bridge": 0.0
        },
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "bridge",
        "dispersal": "mixed",
        "execution_mode": "inline"
      },
      "allowed_vocab": [
        "reason_needed"
      ],
      "transitions": {
        "on_close": "phase_done"
      },
      "action": "step_1",
      "goal": "Determine if the query is best suited for web search, document analysis, or domain-specific research. Output classification and rationale.",
      "kind": "higher_order",
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "post_diff": false
    },
    {
      "id": "phase_done",
      "kind": "terminal",
      "goal": "done",
      "action": "close_loop",
      "terminal": true
    }
  ],
  "steps": [
    {
      "action": "step_1",
      "desc": "Determine if the query is best suited for web search, document analysis, or domain-specific research. Output classification and rationale.",
      "post_diff": false
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_done",
      "requires_no_active_gaps": true
    },
    "failure": {
      "allow_force_close": true,
      "allow_clarify_terminal": true
    },
    "limits": {
      "max_chain_depth": 15,
      "max_redirects": 4
    }
  }
}