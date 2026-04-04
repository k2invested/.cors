{
  "name": "trigger",
  "desc": "Activation codon for workflow starts and background launches. This is the system activation surface that opens a package or background branch and hands execution into its emitted gaps. It is internal-only and should not be treated as a public classifiable workflow.",
  "trigger": "manual",
  "author": "system",
  "steps": [
    {
      "action": "activate_workflow",
      "desc": "activate the selected workflow or background branch and hand execution into its emitted gaps.",
      "relevance": 1.0,
      "post_diff": false
    }
  ]
}
