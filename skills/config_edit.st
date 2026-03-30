{
  "name": "config_edit",
  "desc": "Edit a configuration file — resolve current state, identify key, compose edit, commit",
  "steps": [
    {
      "action": "resolve_current",
      "desc": "resolve blob hash of target config file",
      "vocab": "scan_needed",
      "post_diff": true
    },
    {
      "action": "compose_edit",
      "desc": "compose the edit command targeting specific key",
      "vocab": "script_edit_needed",
      "post_diff": false
    },
    {
      "action": "verify_result",
      "desc": "resolve new commit blob to verify edit landed",
      "vocab": "scan_needed",
      "post_diff": true
    }
  ]
}
