{
  "name": "complete_london_councils",
  "desc": "Complete borough-by-borough planning links for london_council_websites.md",
  "trigger": "manual",
  "author": "agent",
  "refs": {
    "target_file": "blob_f1a2b3",
    "prior_research": "chain_abc123"
  },
  "steps": [
    {
      "action": "read_current_state_of",
      "desc": "read current state of london_council_websites.md",
      "vocab": "scan_needed",
      "post_diff": true,
      "resolve": [
        "blob_f1a2b3"
      ]
    },
    {
      "action": "research_planning_portal_urls",
      "desc": "research planning portal URLs for all 33 London boroughs",
      "vocab": "research_needed",
      "post_diff": true,
      "resolve": [
        "chain_abc123"
      ]
    },
    {
      "action": "update_londoncouncilwebsitesmd_with_verified",
      "desc": "update london_council_websites.md with verified links",
      "vocab": "script_edit_needed",
      "post_diff": false,
      "resolve": [
        "blob_f1a2b3"
      ]
    },
    {
      "action": "verify_all_33_boroughs",
      "desc": "verify all 33 boroughs have entries",
      "vocab": "scan_needed",
      "post_diff": true,
      "resolve": [
        "blob_f1a2b3"
      ]
    }
  ]
}