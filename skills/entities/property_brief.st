{
  "name": "property_brief",
  "desc": "Persistent property research brief template. Holds the canonical target-property context that the property market research workflow resolves before running its observation tools.",
  "trigger": "manual",
  "author": "developer",
  "artifact": {
    "kind": "entity",
    "protected_kind": "entity",
    "lineage": "property_brief",
    "version_strategy": "hash_pinned"
  },
  "identity": {
    "kind": "property_research_brief",
    "status": "template",
    "desc": "Canonical semantic brief for one target property or property opportunity."
  },
  "scope": {
    "objective": "Gather property market research context, then synthesize one written dossier.",
    "output_path": "property_research/property_market_report.md",
    "workspace_root": "property_research/"
  },
  "schema": {
    "target_property": {
      "address": "",
      "postcode": "",
      "uprn": "",
      "lat": null,
      "lng": null,
      "property_type": "",
      "bedrooms": null
    },
    "commercial_context": {
      "owner_or_vendor": "",
      "company_name": "",
      "strategy": "",
      "max_budget": null,
      "target_rent": null
    },
    "research_focus": {
      "comparables_window_months": 24,
      "crime_window_months": 6,
      "keywords": [],
      "priority_questions": []
    }
  },
  "sources": {
    "workspace_artifacts": [
      "property_research/"
    ],
    "expected_observation_surfaces": [
      "postcodes_io",
      "land_registry",
      "epc_lookup",
      "flood_risk",
      "police_api",
      "ons_demographics",
      "companies_house",
      "rental_search",
      "google_trends",
      "web_search",
      "research_web",
      "url_fetch"
    ]
  },
  "constraints": {
    "research_mode": "observation_first_then_single_synthesis",
    "report_format": "single markdown dossier",
    "report_sections": [
      "target summary",
      "area context",
      "sales comparables",
      "rental market",
      "risk factors",
      "investment view"
    ]
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface the canonical property brief identity and status",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_scope",
      "desc": "surface the research objective and output target for the property dossier",
      "resolve": [
        "scope"
      ],
      "post_diff": false
    },
    {
      "action": "load_schema",
      "desc": "surface the target property fields and research parameters used to compose tool inputs",
      "resolve": [
        "schema"
      ],
      "post_diff": false
    },
    {
      "action": "load_sources",
      "desc": "surface the expected property research sources and workspace artifact roots",
      "resolve": [
        "sources"
      ],
      "post_diff": false
    },
    {
      "action": "load_constraints",
      "desc": "surface the constraints for the final property market report",
      "resolve": [
        "constraints"
      ],
      "post_diff": false
    }
  ]
}
