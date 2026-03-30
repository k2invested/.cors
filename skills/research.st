{
  "name": "research",
  "desc": "Research pipeline — decompose query, search, verify sources, extract findings, store",
  "steps": [
    {
      "action": "decompose",
      "desc": "break research query into subtopics",
      "vocab": "hash_resolve_needed",
      "post_diff": true
    },
    {
      "action": "search",
      "desc": "web search per subtopic",
      "vocab": "research_needed",
      "post_diff": true
    },
    {
      "action": "verify_sources",
      "desc": "grade source reliability against referred context",
      "vocab": null,
      "post_diff": false
    },
    {
      "action": "extract",
      "desc": "extract key findings from verified sources",
      "vocab": null,
      "post_diff": false
    },
    {
      "action": "store",
      "desc": "commit findings as blob to trajectory",
      "vocab": "content_needed",
      "post_diff": true
    }
  ]
}
