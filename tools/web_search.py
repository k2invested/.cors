#!/usr/bin/env python3
"""web_search — search via SerpAPI or DuckDuckGo fallback.

Input JSON: {"query": "<search query>"}
Env: SERPAPI — API key (optional, falls back to DDG).
"""
TOOL_DESC = 'search via SerpAPI or DuckDuckGo fallback.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json, os, subprocess, sys, urllib.parse

def main():
    params = json.load(sys.stdin)
    query = params.get("query", "")

    if not query:
        print("Error: missing 'query' parameter", file=sys.stderr)
        sys.exit(1)

    encoded = urllib.parse.quote_plus(query)

    # Try SerpAPI
    api_key = os.environ.get("SERPAPI", "")
    if api_key:
        url = f"https://serpapi.com/search.json?q={encoded}&api_key={api_key}&num=5"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(result.stdout)
            results = []
            for r in data.get("organic_results", [])[:5]:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")
                results.append(f"- {title} ({link})\n  {snippet}")
            if results:
                print("\n\n".join(results))
                return
        except json.JSONDecodeError:
            pass
        print(result.stdout)
        return

    # DuckDuckGo fallback
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
    result = subprocess.run(
        ["curl", "-s", "--max-time", "10", url],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
        parts = []
        abstract_text = data.get("AbstractText", "")
        if abstract_text:
            parts.append(f"Summary: {abstract_text}")
        for topic in data.get("RelatedTopics", [])[:5]:
            text = topic.get("Text", "")
            if text:
                parts.append(f"- {text}")
        if parts:
            print("\n".join(parts))
            return
    except json.JSONDecodeError:
        pass

    print(f"No results found for: {query}")

if __name__ == "__main__":
    main()
