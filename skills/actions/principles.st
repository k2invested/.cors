{
  "name": "principles",
  "desc": "Reason-activated principles maintenance. Resolves the current source/runtime surface first, then PRINCIPLES.md, then reasons about requested principle edits or principles drift and may activate principles_edit only for PRINCIPLES.md while preserving the layered principles structure.",
  "trigger": "on_vocab:principles_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "principles",
    "version_strategy": "hash_pinned"
  },
  "root": "phase_resolve_source_1",
  "phases": [
    {
      "id": "phase_resolve_source_1",
      "kind": "observe",
      "goal": "resolve the source files relevant to architecture, runtime, registries, compiler law, and semantic tree rendering so principle edits stay grounded in live mechanisms before PRINCIPLES.md is assessed",
      "action": "resolve_source",
      "gap_template": {
        "desc": "resolve the source files relevant to architecture, runtime, registries, compiler law, and semantic tree rendering so principle edits stay grounded in live mechanisms before PRINCIPLES.md is assessed",
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
      "goal": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and any activation instructions",
      "action": "resolve_principles",
      "gap_template": {
        "desc": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and any activation instructions",
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
        "on_done": "phase_analyse_and_handoff_fix_3"
      }
    },
    {
      "id": "phase_analyse_and_handoff_fix_3",
      "kind": "higher_order",
      "goal": "inspect the resolved source context, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the current system context carried into this workflow, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. When edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outcomes are lawful here: 1. if no principles edits are needed, emit no activation and close the workflow; 2. if principles edits are needed, emit only a reason activation JSON for principles_edit using the principles_edit workflow ref, include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless the task explicitly changes entity state.",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "inspect the resolved source context, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the current system context carried into this workflow, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. If edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outputs are lawful here: emit nothing if no principles edits are needed, or emit only a reason activation JSON for principles_edit. If activating principles_edit, use the principles_edit workflow ref, and prompt that child workflow to preserve the required principles structure while editing only docs/PRINCIPLES.md. Include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
        "content_refs": [
          "docs/PRINCIPLES.md"
        ],
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
      "desc": "resolve the source files relevant to architecture, runtime, registries, compiler law, and semantic tree rendering so principle edits stay grounded in live mechanisms before PRINCIPLES.md is assessed",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "resolve_principles",
      "desc": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and any activation instructions",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/PRINCIPLES.md"
      ]
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "inspect the resolved source context, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the current system context carried into this workflow, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. If edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outputs are lawful here: emit nothing if no principles edits are needed, or emit only a reason activation JSON for principles_edit. If activating principles_edit, use the principles_edit workflow ref, and prompt that child workflow to preserve the required principles structure while editing only docs/PRINCIPLES.md. Include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
      "post_diff": true,
      "resolve": [
        "docs/PRINCIPLES.md"
      ]
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