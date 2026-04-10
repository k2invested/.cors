{
  "name": "principles",
  "desc": "Reason-activated principles maintenance. Resolves a fixed one-hash audit set of source/runtime artifacts first, then PRINCIPLES.md, then reasons about requested principle edits or principles drift and may activate principles_edit only for PRINCIPLES.md while preserving the layered principles structure.",
  "trigger": "on_vocab:principles_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "principles",
    "version_strategy": "hash_pinned"
  },
  "root": "phase_resolve_architecture_doc_1",
  "phases": [
    {
      "id": "phase_resolve_architecture_doc_1",
      "kind": "observe",
      "goal": "resolve docs/ARCHITECTURE.md as the first fixed audit artifact for principles context",
      "action": "resolve_architecture_doc",
      "gap_template": {
        "desc": "resolve docs/ARCHITECTURE.md as the first fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "docs/ARCHITECTURE.md"
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
        "on_done": "phase_resolve_step_runtime_2"
      }
    },
    {
      "id": "phase_resolve_step_runtime_2",
      "kind": "observe",
      "goal": "resolve step.py as the next fixed audit artifact for principles context",
      "action": "resolve_step_runtime",
      "gap_template": {
        "desc": "resolve step.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "step.py"
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
        "on_done": "phase_resolve_compile_runtime_3"
      }
    },
    {
      "id": "phase_resolve_compile_runtime_3",
      "kind": "observe",
      "goal": "resolve compile.py as the next fixed audit artifact for principles context",
      "action": "resolve_compile_runtime",
      "gap_template": {
        "desc": "resolve compile.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "compile.py"
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
        "on_done": "phase_resolve_execution_engine_4"
      }
    },
    {
      "id": "phase_resolve_execution_engine_4",
      "kind": "observe",
      "goal": "resolve execution_engine.py as the next fixed audit artifact for principles context",
      "action": "resolve_execution_engine",
      "gap_template": {
        "desc": "resolve execution_engine.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "execution_engine.py"
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
        "on_done": "phase_resolve_manifest_engine_5"
      }
    },
    {
      "id": "phase_resolve_manifest_engine_5",
      "kind": "observe",
      "goal": "resolve manifest_engine.py as the next fixed audit artifact for principles context",
      "action": "resolve_manifest_engine",
      "gap_template": {
        "desc": "resolve manifest_engine.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "manifest_engine.py"
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
        "on_done": "phase_resolve_skills_loader_6"
      }
    },
    {
      "id": "phase_resolve_skills_loader_6",
      "kind": "observe",
      "goal": "resolve skills/loader.py as the next fixed audit artifact for principles context",
      "action": "resolve_skills_loader",
      "gap_template": {
        "desc": "resolve skills/loader.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "skills/loader.py"
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
        "on_done": "phase_resolve_tool_registry_7"
      }
    },
    {
      "id": "phase_resolve_tool_registry_7",
      "kind": "observe",
      "goal": "resolve system/tool_registry.py as the next fixed audit artifact for principles context",
      "action": "resolve_tool_registry",
      "gap_template": {
        "desc": "resolve system/tool_registry.py as the next fixed audit artifact for principles context. Do not substitute another file or bundle multiple artifacts into this gap.",
        "content_refs": [
          "system/tool_registry.py"
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
        "on_done": "phase_resolve_principles_doc_8"
      }
    },
    {
      "id": "phase_resolve_principles_doc_8",
      "kind": "observe",
      "goal": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and activation instructions",
      "action": "resolve_principles_doc",
      "gap_template": {
        "desc": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and activation instructions",
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
        "on_done": "phase_analyse_and_handoff_fix_9"
      }
    },
    {
      "id": "phase_analyse_and_handoff_fix_9",
      "kind": "higher_order",
      "goal": "inspect the fixed per-artifact audit set, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. Compare PRINCIPLES.md against the individually resolved audit artifacts rather than treating source as one bulk surface. The audit set for this workflow is fixed: docs/ARCHITECTURE.md, step.py, compile.py, execution_engine.py, manifest_engine.py, skills/loader.py, and system/tool_registry.py. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the resolved audit set, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. When edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outcomes are lawful here: 1. if no principles edits are needed, emit no activation and close the workflow; 2. if principles edits are needed, emit only a reason activation JSON for principles_edit using the principles_edit workflow ref, include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless the task explicitly changes entity state.",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "inspect the fixed per-artifact audit set, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. Compare PRINCIPLES.md against the individually resolved audit artifacts rather than treating source as one bulk surface. The audit set for this workflow is fixed: docs/ARCHITECTURE.md, step.py, compile.py, execution_engine.py, manifest_engine.py, skills/loader.py, and system/tool_registry.py. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the resolved audit set, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. If edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outputs are lawful here: emit nothing if no principles edits are needed, or emit only a reason activation JSON for principles_edit. If activating principles_edit, use the principles_edit workflow ref, and prompt that child workflow to preserve the required principles structure while editing only docs/PRINCIPLES.md. Include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
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
      "action": "resolve_architecture_doc",
      "desc": "resolve docs/ARCHITECTURE.md as the first fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/ARCHITECTURE.md"
      ]
    },
    {
      "action": "resolve_step_runtime",
      "desc": "resolve step.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "step.py"
      ]
    },
    {
      "action": "resolve_compile_runtime",
      "desc": "resolve compile.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "compile.py"
      ]
    },
    {
      "action": "resolve_execution_engine",
      "desc": "resolve execution_engine.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "execution_engine.py"
      ]
    },
    {
      "action": "resolve_manifest_engine",
      "desc": "resolve manifest_engine.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "manifest_engine.py"
      ]
    },
    {
      "action": "resolve_skills_loader",
      "desc": "resolve skills/loader.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "skills/loader.py"
      ]
    },
    {
      "action": "resolve_tool_registry",
      "desc": "resolve system/tool_registry.py as the next fixed audit artifact for principles context",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "system/tool_registry.py"
      ]
    },
    {
      "action": "resolve_principles_doc",
      "desc": "resolve PRINCIPLES.md as the only editable surface for this workflow so principle edits stay grounded in the current file and activation instructions",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/PRINCIPLES.md"
      ]
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "inspect the fixed per-artifact audit set, the resolved PRINCIPLES.md, and the activation task. This workflow is used both for targeted user-directed principle maintenance and for general principles drift review. Compare PRINCIPLES.md against the individually resolved audit artifacts rather than treating source as one bulk surface. The audit set for this workflow is fixed: docs/ARCHITECTURE.md, step.py, compile.py, execution_engine.py, manifest_engine.py, skills/loader.py, and system/tool_registry.py. If the activation task specifies principles to add, remove, rewrite, or preserve, follow those instructions as the governing edit brief while grounding every change in the resolved live mechanisms. Otherwise, assess PRINCIPLES.md for drift against the resolved audit set, especially the layered narrative, mechanism trees, execution law, and runtime structure reflected in source. If edits are needed, preserve the governing structure of PRINCIPLES.md unless the activation task explicitly says otherwise: keep it as a layered narrative that unwraps from the step primitive outward; keep mechanism composition explicit; maintain a mechanism tree for each top-level principle section; keep ARCHITECTURE-style flattened specification out of this document. Only two outputs are lawful here: emit nothing if no principles edits are needed, or emit only a reason activation JSON for principles_edit. If activating principles_edit, use the principles_edit workflow ref, and prompt that child workflow to preserve the required principles structure while editing only docs/PRINCIPLES.md. Include only docs/PRINCIPLES.md in the edit set, and set await_needed=false by default. Do not activate architect. Do not activate any workflow other than principles_edit. Do not include source files, tests, or any other docs in the edit set for this workflow. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
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
