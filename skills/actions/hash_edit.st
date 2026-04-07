{
  "name": "hash_edit",
  "desc": "Universal file editing workflow. Receives task instructions plus carried refs, resolves concrete mutation targets, composes the edit, and executes it via hash_manifest.",
  "trigger": "on_vocab:hash_edit_needed",
  "author": "developer",
  "refs": {},
  "steps": [
    {
      "action": "resolve_target",
      "desc": "observe the concrete workspace file targets from carried refs; treat workflow or entity .st refs as context unless the task explicitly asks to edit them",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "compose_edit",
      "desc": "compose the exact workspace edit from the carried task and refs; prefer concrete non-.st workspace files, and only edit workflow/entity .st files if the task explicitly demands that",
      "vocab": null,
      "post_diff": true
    },
    {
      "action": "execute_edit",
      "desc": "execute the edit via hash_manifest",
      "vocab": "hash_edit_needed",
      "post_diff": false
    }
  ]
}
