{
  "name": "research",
  "desc": "Workflow for research tasks triggered by vocab research_needed. Step 1: identify reputable sources. Step 2: conduct surface-level research using only those sources. Step 3: summarize findings and cite sources. Structure is composable and extensible.",
  "trigger": "manual",
  "refs": {
    "await": "3ed381ca80b9",
    "commit": "7ce6d9001162",
    "hash_edit": "70772dd86cf9",
    "reason": "684dc74c7a74",
    "reprogramme": "63334a75ecba"
  },
  "artifact": {
    "kind": "hybrid",
    "protected_kind": "action",
    "lineage": "research",
    "version_strategy": "hash_pinned"
  },
  "constraints": {
    "must_follow_chain_spec": true,
    "must_embed_existing_st_by_hash": true,
    "must_build_layers_back_to_front": true,
    "vocab_trigger": "research_needed",
    "source_quality": "only reputable sources"
  },
  "scope": "General research tasks requiring reputable sources. Extensible for future research domains or deeper investigation steps.",
  "root": "phase_identify_sources",
  "phases": [
    {
      "id": "phase_identify_sources",
      "desc": "Identify reputable sources relevant to the research topic.",
      "steps": [
        {
          "desc": "Determine the research topic from the triggering context.",
          "vocab": "hash_resolve_needed",
          "relevance": 1.0,
          "confidence": 1.0,
          "post_diff": false
        },
        {
          "desc": "List reputable sources for this topic (e.g., academic journals, government sites, established news outlets).",
          "vocab": "external_context",
          "relevance": 1.0,
          "confidence": 1.0,
          "post_diff": false
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
        "on_done": "phase_surface_research"
      }
    },
    {
      "id": "phase_surface_research",
      "desc": "Conduct surface-level research using only the identified reputable sources.",
      "steps": [
        {
          "desc": "Perform initial research using the listed reputable sources.",
          "vocab": "pattern_needed",
          "relevance": 1.0,
          "confidence": 1.0,
          "post_diff": false
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
        "on_done": "phase_summarize_and_cite"
      }
    },
    {
      "id": "phase_summarize_and_cite",
      "desc": "Summarize findings and cite all sources used.",
      "steps": [
        {
          "desc": "Summarize the key findings from the research.",
          "vocab": "external_context",
          "relevance": 1.0,
          "confidence": 1.0,
          "post_diff": false
        },
        {
          "desc": "Cite all reputable sources referenced in the research.",
          "vocab": "external_context",
          "relevance": 1.0,
          "confidence": 1.0,
          "post_diff": false
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
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_summarize_and_cite",
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
  },
  "identity": {
    "purpose": "Defines the canonical structure and rules for constructing commitment chains as semantic trees, ensuring all planning, refinement, manifestation, and persistence steps are composable, auditable, and hash-native."
  }
}