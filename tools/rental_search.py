#!/usr/bin/env python3
"""rental_search — search rental listings via web search.

Input JSON:
  {"area": "Manchester M1", "bedrooms": 2, "max_rent": 1200}
  {"area": "Leeds LS1", "property_type": "flat"}

Output: JSON array of rental listing summaries found via web search.
Uses web_search tool internally for data, then structures results.

Note: This is a web-search-based approach, not a direct API scraper.
For more structured data, use dedicated rental APIs when available.
"""
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


def search_rentals(area: str, bedrooms: int = None, max_rent: int = None,
                   property_type: str = None) -> dict:
    """Search for rental listings using web search."""
    # Build search query
    parts = [area, "rent"]
    if bedrooms:
        parts.append(f"{bedrooms} bed")
    if property_type:
        parts.append(property_type)
    if max_rent:
        parts.append(f"under £{max_rent}")
    parts.append("per month site:openrent.com OR site:spareroom.co.uk OR site:rightmove.co.uk")

    query = " ".join(parts)

    # Use web_search tool
    search_params = json.dumps({"query": query, "num_results": 20})
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(TOOLS_DIR, "web_search.py")],
            input=search_params,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"error": f"web search failed: {result.stderr[:200]}"}

        search_results = json.loads(result.stdout) if result.stdout.strip() else {"results": []}
    except Exception as e:
        return {"error": f"search error: {e}"}

    # Structure results
    listings = []
    raw_results = search_results.get("results", [])
    if isinstance(raw_results, list):
        for r in raw_results:
            listings.append({
                "title": r.get("title", ""),
                "url": r.get("url", r.get("link", "")),
                "snippet": r.get("snippet", r.get("description", "")),
                "source": _extract_source(r.get("url", r.get("link", ""))),
            })

    return {
        "query": query,
        "area": area,
        "count": len(listings),
        "listings": listings,
    }


def _extract_source(url: str) -> str:
    """Extract source name from URL."""
    if "openrent" in url:
        return "OpenRent"
    elif "spareroom" in url:
        return "SpareRoom"
    elif "rightmove" in url:
        return "Rightmove"
    elif "zoopla" in url:
        return "Zoopla"
    return "other"


def main():
    params = json.load(sys.stdin)
    results = search_rentals(
        area=params.get("area", ""),
        bedrooms=params.get("bedrooms"),
        max_rent=params.get("max_rent"),
        property_type=params.get("property_type"),
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
