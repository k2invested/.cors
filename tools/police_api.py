#!/usr/bin/env python3
"""police_api — fetch UK crime data from data.police.uk.

Input JSON:
  {"lat": 53.4808, "lng": -2.2426, "months": 6}  — crimes near coordinates
  {"postcode": "M1 1AA", "months": 6}              — crimes near postcode (geocoded)

Output: JSON with crime counts by category and monthly trend.

Uses the data.police.uk API (free, no API key needed).
"""
TOOL_DESC = 'fetch UK crime data from data.police.uk.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import Counter


POLICE_API = "https://data.police.uk/api"


def geocode_postcode(postcode: str) -> tuple:
    """Convert UK postcode to lat/lng via postcodes.io."""
    pc = postcode.strip().replace(" ", "%20")
    url = f"https://api.postcodes.io/postcodes/{pc}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            result = data.get("result", {})
            return result.get("latitude"), result.get("longitude")
    except Exception:
        return None, None


def fetch_crimes(lat: float, lng: float, months: int = 6) -> dict:
    """Fetch street-level crimes near a location."""
    all_crimes = []
    monthly_counts = []

    now = datetime.now()
    for i in range(months):
        dt = now - timedelta(days=30 * i)
        date_str = dt.strftime("%Y-%m")

        params = urllib.parse.urlencode({
            "lat": lat,
            "lng": lng,
            "date": date_str,
        })
        url = f"{POLICE_API}/crimes-street/all-crime?{params}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                crimes = json.loads(resp.read().decode())
                all_crimes.extend(crimes)
                monthly_counts.append({"month": date_str, "count": len(crimes)})
        except Exception as e:
            monthly_counts.append({"month": date_str, "error": str(e)})

    # Aggregate by category
    categories = Counter(c.get("category", "unknown") for c in all_crimes)

    return {
        "location": {"lat": lat, "lng": lng},
        "total_crimes": len(all_crimes),
        "months_covered": months,
        "by_category": dict(categories.most_common()),
        "monthly_trend": monthly_counts,
    }


def main():
    params = json.load(sys.stdin)
    lat = params.get("lat")
    lng = params.get("lng")
    months = params.get("months", 6)

    if not lat or not lng:
        postcode = params.get("postcode", "")
        if postcode:
            lat, lng = geocode_postcode(postcode)
            if not lat:
                print(json.dumps({"error": f"Could not geocode postcode: {postcode}"}))
                sys.exit(1)
        else:
            print(json.dumps({"error": "provide 'lat'+'lng' or 'postcode'"}))
            sys.exit(1)

    results = fetch_crimes(lat, lng, months)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
