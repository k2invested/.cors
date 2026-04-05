#!/usr/bin/env python3
"""epc_lookup — fetch UK Energy Performance Certificate data.

Input JSON:
  {"postcode": "M1 1AA"}                    — all EPCs in postcode
  {"address": "10 Downing Street, London"}  — specific address
  {"uprn": "100023336956"}                  — by UPRN

Output: JSON array of EPC records with rating, floor area, property type.

Uses the Open EPC API (free, requires API key from opendatacommunities.org).
Env: EPC_API_KEY
"""
TOOL_DESC = 'fetch UK Energy Performance Certificate data.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json
import os
import sys
import urllib.request
import urllib.parse
import base64
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

EPC_BASE = "https://epc.opendatacommunities.org/api/v1/domestic/search"


def fetch_epc(params: dict) -> list:
    """Fetch EPC records from the Open EPC API."""
    api_key = os.environ.get("EPC_API_KEY", "")
    if not api_key:
        return [{"error": "EPC_API_KEY not set — register free at opendatacommunities.org"}]

    query = {}
    if params.get("postcode"):
        query["postcode"] = params["postcode"]
    elif params.get("address"):
        query["address"] = params["address"]
    elif params.get("uprn"):
        query["uprn"] = params["uprn"]
    else:
        return [{"error": "provide 'postcode', 'address', or 'uprn'"}]

    query["size"] = str(params.get("limit", 50))

    url = EPC_BASE + "?" + urllib.parse.urlencode(query)
    auth = base64.b64encode(f"{api_key}:".encode()).decode()

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Authorization": f"Basic {auth}",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [{"error": f"EPC API request failed: {e}"}]

    results = []
    for row in data.get("rows", []):
        results.append({
            "address": row.get("address", ""),
            "postcode": row.get("postcode", ""),
            "epc_rating": row.get("current-energy-rating", ""),
            "potential_rating": row.get("potential-energy-rating", ""),
            "floor_area": row.get("total-floor-area", ""),
            "property_type": row.get("property-type", ""),
            "built_form": row.get("built-form", ""),
            "inspection_date": row.get("inspection-date", ""),
            "transaction_type": row.get("transaction-type", ""),
            "tenure": row.get("tenure", ""),
            "lodgement_date": row.get("lodgement-date", ""),
        })

    return results


def main():
    params = json.load(sys.stdin)
    results = fetch_epc(params)
    print(json.dumps({"count": len(results), "records": results}, indent=2))


if __name__ == "__main__":
    main()
