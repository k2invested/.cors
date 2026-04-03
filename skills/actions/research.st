{
  "name": "research",
  "desc": "Composable research workflow triggered by research_needed. Accepts a research query, supports pluggable strategies (web search, document scan), and emits structured results. Designed for extension and deterministic invocation.",
  "trigger": "on_vocab:research_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "research",
    "version_strategy": "hash_pinned"
  },
  "input": {
    "query": "string (topic, question, or pattern to research)",
    "strategies": "optional list of strategy names (default: all available)"
  },
  "output": {
    "findings": [
      {
        "summary": "string",
        "source": "string (URL, file, or reference)",
        "tags": "optional list of strings"
      }
    ]
  },
  "root": "phase_select_strategies",
  "phases": [
    {
      "id": "phase_select_strategies",
      "desc": "Parse input and select strategies.",
      "steps": [
        {
          "kind": "branch",
          "desc": "For each selected strategy, invoke corresponding research phase.",
          "branches": [
            {
              "strategy": "web_search",
              "step": "phase_web_search"
            },
            {
              "strategy": "doc_scan",
              "step": "phase_doc_scan"
            }
          ]
        }
      ],
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
        "on_done": "phase_web_search"
      }
    },
    {
      "id": "phase_web_search",
      "desc": "Perform web search for the query.",
      "steps": [
        {
          "kind": "action",
          "action": "tools/web_search.py",
          "input": {
            "query": "{{query}}"
          },
          "output": "findings_web"
        }
      ],
      "action": "step_2",
      "goal": "step_2",
      "kind": "higher_order",
      "gap_template": {
        "desc": "step_2",
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
        "on_done": "phase_doc_scan"
      }
    },
    {
      "id": "phase_doc_scan",
      "desc": "Scan local documents for the query.",
      "steps": [
        {
          "kind": "action",
          "action": "tools/doc_read.py",
          "input": {
            "pattern": "{{query}}"
          },
          "output": "findings_doc"
        }
      ],
      "action": "step_3",
      "goal": "step_3",
      "kind": "higher_order",
      "gap_template": {
        "desc": "step_3",
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
        "on_done": "phase_aggregate_results"
      }
    },
    {
      "id": "phase_aggregate_results",
      "desc": "Aggregate findings and emit structured results.",
      "steps": [
        {
          "kind": "aggregate",
          "inputs": [
            "findings_web",
            "findings_doc"
          ],
          "output": "findings"
        }
      ],
      "action": "step_4",
      "goal": "step_4",
      "kind": "higher_order",
      "gap_template": {
        "desc": "step_4",
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
    },
    {
      "action": "step_2",
      "desc": "step_2",
      "post_diff": false
    },
    {
      "action": "step_3",
      "desc": "step_3",
      "post_diff": false
    },
    {
      "action": "step_4",
      "desc": "step_4",
      "post_diff": false
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_aggregate_results",
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