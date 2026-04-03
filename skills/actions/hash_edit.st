{
  "name": "research",
  "desc": "General research workflow. Clarifies the research question, identifies sources, gathers data, synthesizes findings, and surfaces results. Triggered by vocab: research_needed.",
  "trigger": "on_vocab:research_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "research",
    "version_strategy": "hash_pinned"
  },
  "root": "phase_clarify_question_1",
  "phases": [
    {
      "id": "phase_clarify_question_1",
      "kind": "observe",
      "goal": "Clarify the research question or objective.",
      "action": "clarify_question",
      "gap_template": {
        "desc": "Clarify the research question or objective.",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "clarify_needed"
      },
      "allowed_vocab": [
        "clarify_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_identify_sources_2"
      }
    },
    {
      "id": "phase_identify_sources_2",
      "kind": "observe",
      "goal": "Identify relevant sources or domains for research.",
      "action": "identify_sources",
      "gap_template": {
        "desc": "Identify relevant sources or domains for research.",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "pattern_needed"
      },
      "allowed_vocab": [
        "pattern_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_gather_data_3"
      }
    },
    {
      "id": "phase_gather_data_3",
      "kind": "observe",
      "goal": "Gather data from identified sources.",
      "action": "gather_data",
      "gap_template": {
        "desc": "Gather data from identified sources.",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "hash_resolve_needed"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_synthesize_findings_4"
      }
    },
    {
      "id": "phase_synthesize_findings_4",
      "kind": "higher_order",
      "goal": "Synthesize findings and extract insights.",
      "action": "synthesize_findings",
      "gap_template": {
        "desc": "Synthesize findings and extract insights.",
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
      "post_diff": true,
      "transitions": {
        "on_done": "phase_surface_results_5"
      }
    },
    {
      "id": "phase_surface_results_5",
      "kind": "mutate",
      "goal": "Surface results in a concise, actionable format.",
      "action": "surface_results",
      "gap_template": {
        "desc": "Surface results in a concise, actionable format.",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "mutate",
        "dispersal": "action",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "content_needed"
      },
      "allowed_vocab": [
        "content_needed"
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
      "action": "clarify_question",
      "desc": "Clarify the research question or objective.",
      "vocab": "clarify_needed",
      "post_diff": false
    },
    {
      "action": "identify_sources",
      "desc": "Identify relevant sources or domains for research.",
      "vocab": "pattern_needed",
      "post_diff": false
    },
    {
      "action": "gather_data",
      "desc": "Gather data from identified sources.",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "synthesize_findings",
      "desc": "Synthesize findings and extract insights.",
      "post_diff": true
    },
    {
      "action": "surface_results",
      "desc": "Surface results in a concise, actionable format.",
      "vocab": "content_needed",
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