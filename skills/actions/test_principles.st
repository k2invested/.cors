{
  "name": "test_principles",
  "desc": "Embedded corroborating test audit. Resolves a fixed architecture test surface, treats the already supplied source, principles, and documentation refs as grounding context, and may activate hash_edit only for stale test files.",
  "trigger": "on_vocab:test_principles_needed",
  "refs": {},
  "artifact": {
    "kind": "action",
    "protected_kind": "action",
    "lineage": "test_principles",
    "version_strategy": "hash_pinned"
  },
  "root": "phase_resolve_tests_1",
  "phases": [
    {
      "id": "phase_resolve_tests_1",
      "kind": "observe",
      "goal": "resolve the fixed corroborating architecture test surface",
      "action": "resolve_tests",
      "gap_template": {
        "desc": "resolve the fixed corroborating architecture test surface: tests/test_principles.py, tests/test_semantic_runtime.py, tests/test_law9.py, tests/test_security_compile.py, and tests/test_trace_tree_build.py. Treat any supplied source, principles, and documentation refs as grounding context, but do not expand this phase into an open-ended test search.",
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
        "on_done": "phase_analyse_and_handoff_fix_2"
      }
    },
    {
      "id": "phase_analyse_and_handoff_fix_2",
      "kind": "higher_order",
      "goal": "treat the supplied source, principles, and documentation refs as the grounding audit context and audit only the fixed corroborating test surface against that evidence. This phase has only two lawful outcomes: 1. if no test edits are needed, emit no activation and close the workflow; 2. if test edits are needed, emit only a reason activation JSON for hash_edit using the hash_edit workflow ref, include only the concrete stale test file refs from the fixed test surface that require mutation, and set await_needed=false by default. Do not activate architect or any workflow other than hash_edit. Do not include source-code files, documentation, or PRINCIPLES.md in the edit set for this workflow. If the supplied source, principles, documentation, or test evidence is missing or unresolved, surface continuing work instead of claiming reconciliation.",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "treat the supplied source, principles, and documentation refs as the grounding audit context and audit only the fixed corroborating test surface against that evidence. Only two outputs are lawful here: emit nothing if no test edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale test file refs from the fixed test surface that need mutation, and set await_needed=false by default. Do not activate architect or any workflow other than hash_edit. Do not include source-code files, documentation, or PRINCIPLES.md in the edit set for this workflow. If the supplied source, principles, documentation, or test evidence is missing or unresolved, surface continuing work instead of claiming reconciliation.",
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
      "action": "resolve_tests",
      "desc": "resolve the fixed corroborating architecture test surface: tests/test_principles.py, tests/test_semantic_runtime.py, tests/test_law9.py, tests/test_security_compile.py, and tests/test_trace_tree_build.py. Treat any supplied source, principles, and documentation refs as grounding context, but do not expand this phase into an open-ended test search.",
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
      "desc": "treat the supplied source, principles, and documentation refs as the grounding audit context and audit only the fixed corroborating test surface against that evidence. Only two outputs are lawful here: emit nothing if no test edits are needed, or emit only a reason activation JSON for hash_edit. If activating hash_edit, use the hash_edit workflow ref, include only the exact stale test file refs from the fixed test surface that need mutation, and set await_needed=false by default. Do not activate architect or any workflow other than hash_edit. Do not include source-code files, documentation, or PRINCIPLES.md in the edit set for this workflow. If the supplied source, principles, documentation, or test evidence is missing or unresolved, surface continuing work instead of claiming reconciliation.",
      "vocab": "reason_needed",
      "post_diff": true
    }
  ],
  "closure": {
    "success": {
      "requires_terminal": "phase_done",
      "requires_no_active_gaps": true
    }
  }
}
