{
  "name": "architect",
  "desc": "Architecture analysis. Treats a fixed source audit set as the canonical system surface, resolves PRINCIPLES.md only for grounding, audits a fixed editable documentation/spec surface against that source and a fixed corroborating test surface, and may activate hash_edit only for stale documentation files.",
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
      "goal": "resolve the fixed source audit set for architecture, runtime, registries, execution flow, public registries, and validation surfaces",
      "action": "resolve_source",
      "gap_template": {
        "desc": "resolve the fixed source audit set for architecture analysis: step.py, compile.py, loop.py, execution_engine.py, manifest_engine.py, skills/loader.py, system/tool_registry.py, system/chain_registry.py, system/hash_registry.py, system/security_compile.py, system/trace_tree_build.py, tools/hash_resolve.py, tools/hash_manifest.py, and tools/validate_chain.py. Do not substitute other files or treat this phase as an open-ended source search.",
        "content_refs": [
          "step.py",
          "compile.py",
          "loop.py",
          "execution_engine.py",
          "manifest_engine.py",
          "skills/loader.py",
          "system/tool_registry.py",
          "system/chain_registry.py",
          "system/hash_registry.py",
          "system/security_compile.py",
          "system/trace_tree_build.py",
          "tools/hash_resolve.py",
          "tools/hash_manifest.py",
          "tools/validate_chain.py"
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
      "goal": "resolve the fixed editable documentation/spec surface that should stay in sync with the canonical source audit set",
      "action": "resolve_docs",
      "gap_template": {
        "desc": "resolve the fixed editable documentation/spec surface for architecture analysis: docs/ARCHITECTURE.md, docs/step.md, docs/compile.md, docs/loop.md, docs/execution_engine.md, docs/manifest_engine.md, docs/skills.md, docs/tools.md, docs/security_compile.md, and docs/trace_tree.md. Do not substitute other docs or treat PRINCIPLES.md as part of the editable synchronization surface.",
        "content_refs": [
          "docs/ARCHITECTURE.md",
          "docs/step.md",
          "docs/compile.md",
          "docs/loop.md",
          "docs/execution_engine.md",
          "docs/manifest_engine.md",
          "docs/skills.md",
          "docs/tools.md",
          "docs/security_compile.md",
          "docs/trace_tree.md"
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
      "goal": "resolve the fixed corroborating test surface for architecture, runtime, law-9, security, and trace-tree behavior",
      "action": "resolve_tests",
      "gap_template": {
        "desc": "resolve the fixed corroborating test surface for architecture analysis: tests/test_principles.py, tests/test_semantic_runtime.py, tests/test_law9.py, tests/test_security_compile.py, and tests/test_trace_tree_build.py. Do not treat this phase as an open-ended test search.",
        "content_refs": [
          "tests/test_principles.py",
          "tests/test_semantic_runtime.py",
          "tests/test_law9.py",
          "tests/test_security_compile.py",
          "tests/test_trace_tree_build.py"
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
        "on_done": "phase_analyse_and_handoff_fix_5"
      }
    },
    {
      "id": "phase_analyse_and_handoff_fix_5",
      "kind": "higher_order",
      "goal": "treat the fixed resolved source audit set as the canonical source of truth, use PRINCIPLES.md only as architectural grounding, and audit only the fixed editable documentation/spec surface against that source and the fixed corroborating test surface. This phase has only two lawful outcomes: 1. if no documentation edits are needed, emit no activation and close the workflow; 2. if documentation edits are needed, emit only a reason activation JSON for hash_edit using the hash_edit workflow ref, include only the concrete stale documentation/spec file refs from the fixed editable docs surface that require mutation, and set await_needed=false by default. Do not activate architect again. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. If the fixed source, docs, or test phases are missing evidence or remain unresolved, surface continuing work instead of claiming reconciliation. Do not emit reprogramme_needed from this phase unless the task explicitly changes entity state.",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "treat the fixed resolved source audit set as the canonical source of truth and use PRINCIPLES.md only as architectural grounding. Audit only the fixed editable documentation/spec surface against that source and the fixed corroborating test surface. Only two outputs are lawful here: emit nothing if no documentation edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale documentation/spec file refs from the fixed editable docs surface that need mutation, and set await_needed=false by default. Do not reactivate architect. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. If the fixed source, docs, or test phases are missing evidence or remain unresolved, surface continuing work instead of claiming reconciliation. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
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
      "desc": "resolve the fixed source audit set for architecture analysis: step.py, compile.py, loop.py, execution_engine.py, manifest_engine.py, skills/loader.py, system/tool_registry.py, system/chain_registry.py, system/hash_registry.py, system/security_compile.py, system/trace_tree_build.py, tools/hash_resolve.py, tools/hash_manifest.py, and tools/validate_chain.py. Do not substitute other files or treat this phase as an open-ended source search.",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "step.py",
        "compile.py",
        "loop.py",
        "execution_engine.py",
        "manifest_engine.py",
        "skills/loader.py",
        "system/tool_registry.py",
        "system/chain_registry.py",
        "system/hash_registry.py",
        "system/security_compile.py",
        "system/trace_tree_build.py",
        "tools/hash_resolve.py",
        "tools/hash_manifest.py",
        "tools/validate_chain.py"
      ]
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
      "desc": "resolve the fixed editable documentation/spec surface for architecture analysis: docs/ARCHITECTURE.md, docs/step.md, docs/compile.md, docs/loop.md, docs/execution_engine.md, docs/manifest_engine.md, docs/skills.md, docs/tools.md, docs/security_compile.md, and docs/trace_tree.md. Do not substitute other docs or treat PRINCIPLES.md as part of the editable synchronization surface.",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/ARCHITECTURE.md",
        "docs/step.md",
        "docs/compile.md",
        "docs/loop.md",
        "docs/execution_engine.md",
        "docs/manifest_engine.md",
        "docs/skills.md",
        "docs/tools.md",
        "docs/security_compile.md",
        "docs/trace_tree.md"
      ]
    },
    {
      "action": "resolve_tests",
      "desc": "resolve the fixed corroborating test surface for architecture analysis: tests/test_principles.py, tests/test_semantic_runtime.py, tests/test_law9.py, tests/test_security_compile.py, and tests/test_trace_tree_build.py. Do not treat this phase as an open-ended test search.",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "tests/test_principles.py",
        "tests/test_semantic_runtime.py",
        "tests/test_law9.py",
        "tests/test_security_compile.py",
        "tests/test_trace_tree_build.py"
      ]
    },
    {
      "action": "analyse_and_handoff_fix",
      "desc": "treat the fixed resolved source audit set as the canonical source of truth and use PRINCIPLES.md only as architectural grounding. Audit only the fixed editable documentation/spec surface against that source and the fixed corroborating test surface. Only two outputs are lawful here: emit nothing if no documentation edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale documentation/spec file refs from the fixed editable docs surface that need mutation, and set await_needed=false by default. Do not reactivate architect. Do not activate any workflow other than hash_edit. Do not include source-code files, tests, or PRINCIPLES.md in the edit set for this workflow. If the fixed source, docs, or test phases are missing evidence or remain unresolved, surface continuing work instead of claiming reconciliation. Do not emit reprogramme_needed from this phase unless entity state persistence is explicitly required.",
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
