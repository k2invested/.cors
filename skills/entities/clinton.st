{
  "name": "clinton",
  "desc": "Cyber security developer based in the UK, previously in Lagos. Backend specialist, worked with admin (kenny) on v3. Prefers async communication.",
  "trigger": "on_contact:admin | manual",
  "refs": {
    "admin": "72b1d5ffc964"
  },
  "artifact": {
    "kind": "hybrid",
    "protected_kind": "action",
    "lineage": "clinton",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "role": "cyber security developer",
    "location": "UK",
    "specialty": "backend systems",
    "collaborated_with": [
      "72b1d5ffc964"
    ],
    "project_history": [
      "v3"
    ]
  },
  "preferences": {
    "communication": {
      "style": "async",
      "timezone": "Europe/London"
    }
  },
  "root": "phase_entity_update_1",
  "phases": [
    {
      "id": "phase_entity_update_1",
      "kind": "higher_order",
      "goal": "knowledge updated from conversation",
      "action": "entity_update",
      "gap_template": {
        "desc": "knowledge updated from conversation",
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
      "action": "entity_update",
      "desc": "knowledge updated from conversation",
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