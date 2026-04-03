{
  "name": "hash_edit",
  "desc": "Universal file editing workflow. Observe target → compose edit → execute via hash_manifest. Postcondition auto-fires on commit.",
  "trigger": "on_vocab:hash_edit_needed",
  "author": "developer",
  "refs": {},
  "steps": [
    {
      "action": "resolve_target",
      "desc": "observe current state of target file by hash",
      "vocab": "hash_resolve_needed",
      "post_diff": false
    },
    {
      "action": "compose_edit",
      "desc": "compose the edit — what to change and why",
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
