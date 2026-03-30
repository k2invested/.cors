#!/usr/bin/env python3
"""postcodes_io — UK postcode geocoding and area metadata.

Input JSON:
  {"postcode": "M1 1AA"}                    — single postcode lookup
  {"postcodes": ["M1 1AA", "LS1 1BA"]}     — bulk lookup (max 100)
  {"lat": 53.4808, "lng": -2.2426}         — reverse geocode
  {"postcode": "M1 1AA", "nearest": true}  — nearest postcodes

Output: JSON with lat/lng, ward, district, council, region, constituency,
        LSOA, MSOA, and admin codes.

Uses postcodes.io (free, no API key needed, no rate limits).
"""
import json
import sys
import urllib.request
import urllib.parse


BASE = "https://api.postcodes.io"


def lookup_postcode(postcode: str) -> dict:
    """Look up a single postcode."""
    pc = urllib.parse.quote(postcode.strip())
    url = f"{BASE}/postcodes/{pc}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == 200:
                r = data["result"]
                return {
                    "postcode": r.get("postcode"),
                    "lat": r.get("latitude"),
                    "lng": r.get("longitude"),
                    "ward": r.get("admin_ward"),
                    "district": r.get("admin_district"),
                    "county": r.get("admin_county"),
                    "region": r.get("region"),
                    "country": r.get("country"),
                    "constituency": r.get("parliamentary_constituency"),
                    "lsoa": r.get("lsoa"),
                    "msoa": r.get("msoa"),
                    "parish": r.get("parish"),
                    "outcode": r.get("outcode"),
                    "incode": r.get("incode"),
                }
            return {"error": f"postcode not found: {postcode}"}
    except Exception as e:
        return {"error": str(e)}


def bulk_lookup(postcodes: list) -> list:
    """Look up multiple postcodes (max 100)."""
    url = f"{BASE}/postcodes"
    payload = json.dumps({"postcodes": postcodes[:100]}).encode()
    try:
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            results = []
            for item in data.get("result", []):
                r = item.get("result")
                if r:
                    results.append({
                        "postcode": r.get("postcode"),
                        "lat": r.get("latitude"),
                        "lng": r.get("longitude"),
                        "district": r.get("admin_district"),
                        "region": r.get("region"),
                        "lsoa": r.get("lsoa"),
                    })
                else:
                    results.append({"postcode": item.get("query"), "error": "not found"})
            return results
    except Exception as e:
        return [{"error": str(e)}]


def reverse_geocode(lat: float, lng: float) -> dict:
    """Reverse geocode lat/lng to postcode."""
    url = f"{BASE}/postcodes?lon={lng}&lat={lat}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("result", [])
            if results:
                r = results[0]
                return {
                    "postcode": r.get("postcode"),
                    "lat": r.get("latitude"),
                    "lng": r.get("longitude"),
                    "district": r.get("admin_district"),
                    "distance": r.get("distance"),
                }
            return {"error": "no postcode found near coordinates"}
    except Exception as e:
        return {"error": str(e)}


def nearest_postcodes(postcode: str) -> list:
    """Find nearest postcodes to a given postcode."""
    pc = urllib.parse.quote(postcode.strip())
    url = f"{BASE}/postcodes/{pc}/nearest"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = []
            for r in data.get("result", []):
                results.append({
                    "postcode": r.get("postcode"),
                    "distance": r.get("distance"),
                    "lat": r.get("latitude"),
                    "lng": r.get("longitude"),
                })
            return results
    except Exception as e:
        return [{"error": str(e)}]


def main():
    params = json.load(sys.stdin)

    if params.get("postcodes"):
        results = bulk_lookup(params["postcodes"])
        print(json.dumps({"count": len(results), "results": results}, indent=2))
    elif params.get("lat") and params.get("lng"):
        result = reverse_geocode(params["lat"], params["lng"])
        print(json.dumps(result, indent=2))
    elif params.get("postcode"):
        if params.get("nearest"):
            results = nearest_postcodes(params["postcode"])
            print(json.dumps({"count": len(results), "results": results}, indent=2))
        else:
            result = lookup_postcode(params["postcode"])
            print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"error": "provide 'postcode', 'postcodes', or 'lat'+'lng'"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
