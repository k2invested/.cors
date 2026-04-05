#!/usr/bin/env python3
"""research_web — structured web research for qualitative data collection.

Input JSON:
  {"queries": ["topic 1", "topic 2"], "depth": "shallow|deep", "max_results": 10}

shallow: web search only — titles, snippets, URLs
deep: web search + fetch top 3 URLs per query for full content extraction

Output: JSON with structured findings per query.
"""
TOOL_DESC = 'structured web research for qualitative data collection.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json
import os
import sys
import subprocess
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def web_search(query: str, num_results: int = 10) -> list:
    """Run a web search and return results."""
    params = json.dumps({"query": query, "num_results": num_results})
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "web_search.py")],
            input=params, text=True, capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            return [{"error": f"search failed: {result.stderr[:200]}"}]
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        return data.get("results", [])
    except Exception as e:
        return [{"error": str(e)}]


def fetch_url(url: str) -> str:
    """Fetch full page content from a URL."""
    params = json.dumps({"url": url})
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "url_fetch.py")],
            input=params, text=True, capture_output=True, timeout=30,
        )
        if result.returncode != 0:
            return f"[fetch error: {result.stderr[:200]}]"
        return result.stdout[:8000]  # Cap at 8K chars
    except Exception as e:
        return f"[fetch error: {e}]"


def research_query(query: str, depth: str = "shallow", max_results: int = 10) -> dict:
    """Research a single query."""
    results = web_search(query, max_results)

    findings = {
        "query": query,
        "sources": [],
    }

    for r in results:
        source = {
            "title": r.get("title", ""),
            "url": r.get("url", r.get("link", "")),
            "snippet": r.get("snippet", r.get("description", "")),
        }
        findings["sources"].append(source)

    # Deep mode: fetch top 3 URLs for full content
    if depth == "deep":
        for source in findings["sources"][:3]:
            url = source.get("url", "")
            if url:
                print(f"  [deep] fetching {url[:80]}...", file=sys.stderr)
                content = fetch_url(url)
                source["full_content"] = content

    findings["source_count"] = len(findings["sources"])
    return findings


def main():
    params = json.load(sys.stdin)
    queries = params.get("queries", [])
    depth = params.get("depth", "shallow")
    max_results = params.get("max_results", 10)

    if not queries:
        print(json.dumps({"error": "provide 'queries' array"}))
        sys.exit(1)

    all_findings = []
    for q in queries:
        print(f"[research] {q}", file=sys.stderr)
        finding = research_query(q, depth, max_results)
        all_findings.append(finding)

    print(json.dumps({
        "query_count": len(all_findings),
        "depth": depth,
        "findings": all_findings,
    }, indent=2))


if __name__ == "__main__":
    main()
