{
  "name": "principles_edit",
  "desc": "Dedicated PRINCIPLES.md editing workflow. Resolves the target document, composes a structure-preserving edit brief, and executes the edit via hash_manifest.",
  "trigger": "manual",
  "author": "developer",
  "refs": {},
  "steps": [
    {
      "action": "resolve_target",
      "desc": "resolve docs/PRINCIPLES.md as the sole mutation target for this workflow; treat all other carried refs as grounding context only",
      "vocab": "hash_resolve_needed",
      "resolve": [
        "docs/PRINCIPLES.md"
      ],
      "post_diff": false
    },
    {
      "action": "compose_edit",
      "desc": "compose the exact edit for docs/PRINCIPLES.md from the carried task and refs. Retain the governing structure unless the task explicitly says otherwise: keep PRINCIPLES.md as a layered narrative that unwraps from the step/gap primitive outward, keep mechanism composition explicit, preserve a mechanism tree for each top-level principle section, and do not flatten it into ARCHITECTURE-style specification. Apply targeted adds, removals, rewrites, or drift corrections without disturbing sections that should remain stable.",
      "vocab": null,
      "post_diff": true
    },
    {
      "action": "execute_edit",
      "desc": "execute the PRINCIPLES.md edit via hash_manifest",
      "vocab": "hash_edit_needed",
      "post_diff": false
    }
  ]
}
