{
  "name": "architect",
  "desc": "Architecture analysis. Resolves source, principles, docs, and tests, then reasons about drift and may activate hash_edit for the files that actually need syncing.",
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
      "goal": "resolve PRINCIPLES.md so architectural judgment stays grounded in the current system philosophy and laws",
      "action": "resolve_principles",
      "gap_template": {
        "desc": "resolve PRINCIPLES.md so architectural judgment stays grounded in the current system philosophy and laws",
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
      "goal": "resolve ARCHITECTURE.md and the module docs that may have drifted from source",
      "action": "resolve_docs",
      "gap_template": {
        "desc": "resolve ARCHITECTURE.md and the module docs that may have drifted from source",
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
      "goal": "analyse architectural drift, identify which docs or tests actually need syncing, consider dependencies, failure modes, and mitigations, and if edits are warranted activate hash_edit with those exact file refs; default to inline activation with await_needed=false, and select await_needed=true only when true isolation or deferred synchronization is necessary",
      "action": "analyse_and_handoff_fix",
      "gap_template": {
        "desc": "analyse architectural drift, identify which docs or tests actually need syncing, consider dependencies, failure modes, and mitigations, and if edits are warranted activate hash_edit with those exact file refs; default to inline activation with await_needed=false, and select await_needed=true only when true isolation or deferred synchronization is necessary",
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
      "desc": "resolve PRINCIPLES.md so architectural judgment stays grounded in the current system philosophy and laws",
      "vocab": "hash_resolve_needed",
      "post_diff": false,
      "resolve": [
        "docs/PRINCIPLES.md"
      ]
    },
    {
      "action": "resolve_docs",
      "desc": "resolve ARCHITECTURE.md and the module docs that may have drifted from source",
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
      "desc": "analyse architectural drift, identify which docs or tests actually need syncing, consider dependencies, failure modes, and mitigations, and if edits are warranted activate hash_edit with those exact file refs; default to inline activation with await_needed=false, and select await_needed=true only when true isolation or deferred synchronization is necessary",
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
