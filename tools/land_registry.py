#!/usr/bin/env python3
"""land_registry — fetch UK Land Registry Price Paid data.

Input JSON:
  {"postcode": "M1", "months": 12}          — sold prices in postcode district, last N months
  {"postcode": "M1 1AA", "months": 24}      — specific postcode sector
  {"address": "10 Downing Street", "months": 12}  — specific address search

Output: JSON array of sale records with price, date, property type, address.

Uses the Land Registry SPARQL endpoint (free, no API key needed).
"""
TOOL_DESC = 'fetch UK Land Registry Price Paid data.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


SPARQL_ENDPOINT = "http://landregistry.data.gov.uk/app/root/qonsole/query"
LINKED_DATA_API = "https://landregistry.data.gov.uk/data/ppi/transaction-record.json"


def fetch_by_postcode(postcode: str, months: int = 12) -> list:
    """Fetch sold prices by postcode prefix using the Linked Data API."""
    cutoff = datetime.now() - timedelta(days=months * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # Clean postcode — support district (M1) or full (M1 1AA)
    pc = postcode.strip().upper()

    # Use the Linked Data API with filters
    params = {
        "min-date": cutoff_str,
        "_pageSize": "200",
        "_sort": "-date",
    }

    # Match by postcode prefix
    if len(pc) <= 4:
        # District level (e.g., "M1" matches "M1 *")
        params["propertyAddress.postcode"] = pc + "*"
    else:
        params["propertyAddress.postcode"] = pc

    url = LINKED_DATA_API + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [{"error": f"API request failed: {e}"}]

    results = []
    items = data.get("result", {}).get("items", [])
    for item in items:
        addr = item.get("propertyAddress", {})
        record = {
            "price": item.get("pricePaid"),
            "date": item.get("transactionDate"),
            "property_type": item.get("propertyType", {}).get("prefLabel", ["unknown"])[0] if isinstance(item.get("propertyType", {}), dict) else str(item.get("propertyType", "")),
            "new_build": item.get("newBuild", {}).get("prefLabel", ["unknown"])[0] if isinstance(item.get("newBuild", {}), dict) else str(item.get("newBuild", "")),
            "address": {
                "street": addr.get("street", ""),
                "town": addr.get("town", ""),
                "postcode": addr.get("postcode", ""),
                "paon": addr.get("paon", ""),
                "saon": addr.get("saon", ""),
            },
        }
        results.append(record)

    return results


def fetch_by_address(address: str, months: int = 12) -> list:
    """Fetch sold prices by address keyword search."""
    cutoff = datetime.now() - timedelta(days=months * 30)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    params = {
        "min-date": cutoff_str,
        "_pageSize": "50",
        "_sort": "-date",
        "propertyAddress.street": address,
    }

    url = LINKED_DATA_API + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return [{"error": f"API request failed: {e}"}]

    results = []
    for item in data.get("result", {}).get("items", []):
        addr = item.get("propertyAddress", {})
        results.append({
            "price": item.get("pricePaid"),
            "date": item.get("transactionDate"),
            "property_type": str(item.get("propertyType", "")),
            "address": {
                "street": addr.get("street", ""),
                "town": addr.get("town", ""),
                "postcode": addr.get("postcode", ""),
            },
        })

    return results


def main():
    params = json.load(sys.stdin)
    postcode = params.get("postcode", "")
    address = params.get("address", "")
    months = params.get("months", 12)

    if postcode:
        results = fetch_by_postcode(postcode, months)
    elif address:
        results = fetch_by_address(address, months)
    else:
        print(json.dumps({"error": "provide 'postcode' or 'address'"}))
        sys.exit(1)

    print(json.dumps({"count": len(results), "records": results}, indent=2))


if __name__ == "__main__":
    main()
