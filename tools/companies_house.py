#!/usr/bin/env python3
"""companies_house — UK Companies House company search and filings.

Input JSON:
  {"search": "Acme Property Ltd"}           — company name search
  {"company": "12345678"}                    — company profile by number
  {"company": "12345678", "officers": true} — company officers
  {"company": "12345678", "filings": true}  — recent filings
  {"search": "property investment", "location": "manchester"} — filtered search

Output: JSON with company details, officers, filings.

Uses Companies House API (free, requires API key from developer.company-information.service.gov.uk).
Env: COMPANIES_HOUSE_API_KEY
"""
TOOL_DESC = 'UK Companies House company search and filings.'
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

CH_BASE = "https://api.company-information.service.gov.uk"


def _request(path: str) -> dict:
    """Make authenticated Companies House API request."""
    api_key = os.environ.get("COMPANIES_HOUSE_API_KEY", "")
    if not api_key:
        return {"error": "COMPANIES_HOUSE_API_KEY not set — register free at developer.company-information.service.gov.uk"}

    url = CH_BASE + path
    auth = base64.b64encode(f"{api_key}:".encode()).decode()
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Basic {auth}",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def search_companies(query: str, location: str = None, limit: int = 20) -> dict:
    """Search for companies by name."""
    params = {"q": query, "items_per_page": str(limit)}
    if location:
        params["location"] = location
    path = "/search/companies?" + urllib.parse.urlencode(params)
    data = _request(path)
    if "error" in data:
        return data

    results = []
    for item in data.get("items", []):
        results.append({
            "company_number": item.get("company_number"),
            "title": item.get("title"),
            "company_status": item.get("company_status"),
            "company_type": item.get("company_type"),
            "date_of_creation": item.get("date_of_creation"),
            "address": item.get("address_snippet", ""),
            "sic_codes": item.get("sic_codes", []),
        })
    return {"count": len(results), "results": results}


def get_company_profile(company_number: str) -> dict:
    """Get full company profile."""
    data = _request(f"/company/{company_number}")
    if "error" in data:
        return data
    return {
        "company_number": data.get("company_number"),
        "company_name": data.get("company_name"),
        "status": data.get("company_status"),
        "type": data.get("type"),
        "created": data.get("date_of_creation"),
        "address": data.get("registered_office_address", {}),
        "sic_codes": data.get("sic_codes", []),
        "accounts_next_due": data.get("accounts", {}).get("next_due"),
        "confirmation_next_due": data.get("confirmation_statement", {}).get("next_due"),
        "has_charges": data.get("has_charges"),
        "has_insolvency": data.get("has_insolvency_history"),
    }


def get_officers(company_number: str) -> dict:
    """Get company officers (directors, secretaries)."""
    data = _request(f"/company/{company_number}/officers")
    if "error" in data:
        return data
    officers = []
    for item in data.get("items", []):
        officers.append({
            "name": item.get("name"),
            "role": item.get("officer_role"),
            "appointed": item.get("appointed_on"),
            "resigned": item.get("resigned_on"),
            "nationality": item.get("nationality"),
            "occupation": item.get("occupation"),
        })
    return {"count": len(officers), "officers": officers}


def get_filings(company_number: str, limit: int = 10) -> dict:
    """Get recent company filings."""
    data = _request(f"/company/{company_number}/filing-history?items_per_page={limit}")
    if "error" in data:
        return data
    filings = []
    for item in data.get("items", []):
        filings.append({
            "date": item.get("date"),
            "type": item.get("type"),
            "description": item.get("description"),
            "category": item.get("category"),
        })
    return {"count": len(filings), "filings": filings}


def main():
    params = json.load(sys.stdin)

    if params.get("search"):
        result = search_companies(
            params["search"],
            location=params.get("location"),
            limit=params.get("limit", 20),
        )
    elif params.get("company"):
        cn = params["company"]
        if params.get("officers"):
            result = get_officers(cn)
        elif params.get("filings"):
            result = get_filings(cn, params.get("limit", 10))
        else:
            result = get_company_profile(cn)
    else:
        result = {"error": "provide 'search' or 'company' number"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
