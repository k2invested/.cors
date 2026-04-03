{
  "name": "research",
  "desc": "Composable research workflow triggered by research_needed. Accepts queries, depth, and max_results. Integrates with research_web.py to return structured findings.",
  "trigger": "on_vocab:research_needed",
  "refs": {
    "research_web": "tools/research_web.py"
  },
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "research",
    "version_strategy": "hash_pinned"
  },
  "input_schema": {
    "queries": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "desc": "List of research queries"
    },
    "depth": {
      "type": "string",
      "enum": [
        "shallow",
        "deep"
      ],
      "default": "shallow",
      "desc": "Research depth: shallow (titles/snippets) or deep (fetch top URLs)"
    },
    "max_results": {
      "type": "integer",
      "default": 10,
      "desc": "Maximum results per query"
    }
  },
  "output_schema": {
    "query_count": {
      "type": "integer"
    },
    "depth": {
      "type": "string"
    },
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string"
          },
          "sources": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "title": {
                  "type": "string"
                },
                "url": {
                  "type": "string"
                },
                "snippet": {
                  "type": "string"
                },
                "full_content": {
                  "type": "string"
                }
              },
              "required": [
                "title",
                "url",
                "snippet"
              ]
            }
          },
          "source_count": {
            "type": "integer"
          }
        },
        "required": [
          "query",
          "sources",
          "source_count"
        ]
      }
    }
  },
  "root": "phase_root",
  "phases": [
    {
      "id": "phase_root",
      "desc": "Accept research parameters and invoke research_web.py to collect findings.",
      "steps": [
        {
          "kind": "observe",
          "desc": "Receive research parameters: queries, depth, max_results.",
          "gap": {
            "class": "clarify",
            "desc": "If queries are missing, request them from the user.",
            "vocab": "clarify_needed"
          }
        },
        {
          "kind": "mutate",
          "desc": "Invoke research_web.py with provided parameters.",
          "gap": {
            "class": "mutate",
            "desc": "Execute research_web.py and collect findings.",
            "vocab": "command_needed",
            "content_refs": [
              "tools/research_web.py"
            ]
          }
        },
        {
          "kind": "observe",
          "desc": "Return structured findings to the caller.",
          "gap": {
            "class": "observe",
            "desc": "Surface research findings as output.",
            "vocab": "external_context"
          }
        }
      ],
      "closure": {
        "success": {
          "requires_terminal": true,
          "requires_no_active_gaps": true
        }
      },
      "action": "step_1",
      "goal": "step_1",
      "kind": "higher_order",
      "gap_template": {
        "desc": "step_1",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "bridge",
        "dispersal": "mixed",
        "execution_mode": "inline"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "reason_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_close": "phase_done"
      }
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
      "desc": "step_1",
      "post_diff": false
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_root",
      "requires_no_active_gaps": true
    },
    "failure": {
      "allow_force_close": true,
      "allow_clarify_terminal": true
    },
    "limits": {
      "max_chain_depth": 10,
      "max_redirects": 2
    }
  }
}