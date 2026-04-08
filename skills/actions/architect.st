{
  "name": "architect",
  "desc": "Architecture analysis. Treats source as the canonical system surface, resolves principles for grounding, audits spec/docs against source, and may activate hash_edit only for stale documentation files.",
  "trigger": "on_vocab:architect_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "architect",
    "version_strategy": "hash_pinned"
  },
  "root": "phase_resolve_source_1",
  "phases": [
    {
      "id": "phase_resolve_source_1",
      "kind": "observe",
      "goal": "resolve the source files relevant to architecture, runtime, registries, and execution flow",
      "action": "resolve_source",
      "gap_template": {
        "desc": "resolve the source files relevant to architecture, runtime, registries, and execution flow",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "hash_resolve_needed"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_resolve_principles_2"
      }
    },
    {
      "id": "phase_resolve_principles_2",
      "kind": "observe",
      "goal": "resolve PRINCIPLES.md as architectural grounding context only; do not treat it as part of the editable synchronization surface for this workflow",
      "action": "resolve_principles",
      "gap_template": {
        "desc": "resolve PRINCIPLES.md as architectural grounding context only; do not treat it as part of the editable synchronization surface for this workflow",
        "content_refs": [
          "docs/PRINCIPLES.md"
        ],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "hash_resolve_needed"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_resolve_docs_3"
      }
    },
    {
      "id": "phase_resolve_docs_3",
      "kind": "observe",
      "goal": "resolve ARCHITECTURE.md and the module docs that form the editable spec/documentation surface that should stay in sync with source",
      "action": "resolve_docs",
      "gap_template": {
        "desc": "resolve ARCHITECTURE.md and the module docs that form the editable spec/documentation surface that should stay in sync with source",
        "content_refs": [
          "docs/ARCHITECTURE.md",
          "docs/step.md",
          "docs/compile.md",
          "docs/loop.md",
          "docs/skills.md",
          "docs/tools.md"
        ],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "hash_resolve_needed"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_resolve_tests_4"
      }
    },
    {
      "id": "phase_resolve_tests_4",
      "kind": "observe",
      "goal": "resolve the tests that should reflect the current architectural and documentation surface",
      "action": "resolve_tests",
      "gap_template": {
        "desc": "resolve the tests that should reflect the current architectural and documentation surface",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "observe",
        "dispersal": "context",
        "execution_mode": "runtime_vocab",
        "runtime_vocab": "hash_resolve_needed"
      },
      "generation": {
        "spawn_mode": "none",
        "spawn_trigger": "none",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "hash_resolve_needed"
      ],
      "post_diff": false,
      "transitions": {
        "on_done": "phase_analyse_and_handoff_fix_5"
      }
    },
    {
      "id": "phase_analyse_and_handoff_fix_5",
      "kind": "higher_order",
      "goal": "treat the resolved source code as the canonical source of truth and use PRINCIPLES.md only as architectural grounding. Audit the editable documentation/spec surface against that source and grounding. This phase has only two lawful outcomes: 1. if no documentation edits are needed, emit no activation and close the workflow; 2. if documentation edits are needed, emit only a reason activation JSON for hash_edit using the hash_edit workflow ref, include only the concrete stale documentation/spec file refs that require mutation, and set await_needed=false by default. Do not activate architect again. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless the task explicitly changes entity state.",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "treat the resolved source code as the canonical source of truth and use PRINCIPLES.md only as architectural grounding. Audit only the editable documentation/spec surface against that source and grounding. Only two outputs are lawful here: emit nothing if no documentation edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale documentation/spec file refs that need mutation, and set await_needed=false by default. Do not reactivate architect. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
        "content_refs": [],
        "step_refs": []
      },
      "manifestation": {
        "kernel_class": "bridge",
        "dispersal": "mixed",
        "execution_mode": "inline"
      },
      "generation": {
        "spawn_mode": "mixed",
        "spawn_trigger": "conditional",
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition"
      },
      "allowed_vocab": [
        "reason_needed"
      ],
      "post_diff": true,
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
      "action": "resolve_source",
      "desc": "resolve the source files relevant to architecture, runtime, registries, and execution flow",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "resolve_principles",
      "desc": "resolve PRINCIPLES.md as architectural grounding context only; do not treat it as part of the editable synchronization surface for this workflow",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/PRINCIPLES.md"
      ]
    },
    {
      "action": "resolve_docs",
      "desc": "resolve ARCHITECTURE.md and the module docs that form the editable spec/documentation surface that should stay in sync with source",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/ARCHITECTURE.md",
        "docs/step.md",
        "docs/compile.md",
        "docs/loop.md",
        "docs/skills.md",
        "docs/tools.md"
      ]
    },
    {
      "action": "resolve_tests",
      "desc": "resolve the tests that should reflect the current architectural and documentation surface",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "treat the resolved source code as the canonical source of truth and use PRINCIPLES.md only as architectural grounding. Audit only the editable documentation/spec surface against that source and grounding. Only two outputs are lawful here: emit nothing if no documentation edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale documentation/spec file refs that need mutation, and set await_needed=false by default. Do not reactivate architect. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
      "post_diff": true
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
