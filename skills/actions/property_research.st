{
  "name": "property_research",
  "desc": "Property market research pipeline. Resolve the target brief, run the property observation tools by blob hash, then synthesize everything into one written report.",
  "trigger": "command:property_research",
  "author": "developer",
  "steps": [
    {
      "action": "resolve_property_brief",
      "desc": "resolve the canonical property brief entity, target address and postcode fields, and any files already present under property_research/",
      "vocab": "hash_resolve_needed",
      "resolve": [
        "skills/entities/property_brief.st",
        "property_research/"
      ],
      "relevance": 1.0,
      "post_diff": false
    },
    {
      "action": "lookup_postcode_context",
      "desc": "use postcodes_io to look up the target postcode and return the canonical postcode, lat/lng, district, region, lsoa, and nearby postcode context from the resolved property brief",
      "tool_ref": "93533f7d7518",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.99,
      "post_diff": false
    },
    {
      "action": "lookup_sale_comparables",
      "desc": "use land_registry to fetch recent sold-price comparables for the target postcode or address, defaulting to the last 24 months unless the resolved brief specifies another window",
      "tool_ref": "15c966dffbca",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.97,
      "post_diff": false
    },
    {
      "action": "lookup_epc_records",
      "desc": "use epc_lookup to fetch EPC records for the target postcode, address, or uprn from the resolved brief and return the best matching certificate set",
      "tool_ref": "60272d5a2196",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.96,
      "post_diff": false
    },
    {
      "action": "assess_flood_risk",
      "desc": "use flood_risk with the resolved postcode or coordinates to assess the property's flood exposure, nearby flood areas, warnings, and monitoring stations",
      "tool_ref": "83f8074e2a82",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.94,
      "post_diff": false
    },
    {
      "action": "assess_crime_context",
      "desc": "use police_api with the resolved postcode or coordinates to summarise nearby crime totals, categories, and recent monthly trend data for the property area",
      "tool_ref": "38654a603b7c",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.93,
      "post_diff": false
    },
    {
      "action": "assess_demographics_context",
      "desc": "use ons_demographics with the resolved postcode, lsoa, or district to gather deprivation, housing, and area demographic context for the property location",
      "tool_ref": "22bce686e476",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.92,
      "post_diff": false
    },
    {
      "action": "research_company_context",
      "desc": "use companies_house to research any owner, landlord, developer, or management company named in the resolved property brief and return profile, officers, or filings context when available",
      "tool_ref": "844a0483ef40",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.9,
      "post_diff": false
    },
    {
      "action": "research_rental_market",
      "desc": "use rental_search to gather nearby rental listings for the property's area, matching bedrooms or property type from the resolved brief when available",
      "tool_ref": "df65fa0cb8db",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.89,
      "post_diff": false
    },
    {
      "action": "research_market_interest",
      "desc": "use google_trends to compare UK search interest for the local area and property-market keywords implied by the resolved brief, such as the town or postcode plus rent, house prices, or buy to let",
      "tool_ref": "0843d292032a",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.88,
      "post_diff": false
    },
    {
      "action": "search_market_sources",
      "desc": "use web_search to find fresh market sources, news, and local supply-demand signals relevant to the target property area and strategy described in the resolved brief",
      "tool_ref": "dd0648a9ee2c",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.87,
      "post_diff": false
    },
    {
      "action": "research_market_sources_deeply",
      "desc": "use research_web to run shallow or deep qualitative research across the target property area, local development pipeline, rental demand, and comparable-sale context surfaced earlier in the chain",
      "tool_ref": "1f7b03d34f35",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.86,
      "post_diff": false
    },
    {
      "action": "fetch_key_source_url",
      "desc": "use url_fetch to read the most relevant market or property-specific URL surfaced earlier in the chain when a single source needs closer inspection for the final report",
      "tool_ref": "b5734b922cbd",
      "resolve": [
        "skills/entities/property_brief.st"
      ],
      "relevance": 0.84,
      "post_diff": false
    },
    {
      "action": "write_property_research_report",
      "desc": "use content_needed to write one consolidated markdown report to property_research/property_market_report.md that synthesizes the resolved property brief and every preceding observation into a single property market research dossier with sections for target summary, area context, sales comparables, rental market, risk factors, and overall investment view",
      "vocab": "content_needed",
      "resolve": [
        "skills/entities/property_brief.st",
        "property_research/"
      ],
      "relevance": 0.82,
      "post_diff": true
    }
  ]
}
