#!/usr/bin/env python3
"""flood_risk — UK Environment Agency flood risk assessment.

Input JSON:
  {"lat": 53.4808, "lng": -2.2426}         — flood risk at coordinates
  {"postcode": "M1 1AA"}                    — flood risk by postcode (geocodes first)

Output: JSON with flood zone, risk level, and nearby flood areas.

Uses Environment Agency Flood API (free, no API key needed).
"""
import json
import sys
import urllib.request
import urllib.parse


FLOOD_API = "https://environment.data.gov.uk/flood-monitoring"


def geocode_postcode(postcode: str) -> tuple:
    """Convert UK postcode to lat/lng via postcodes.io."""
    pc = urllib.parse.quote(postcode.strip())
    url = f"https://api.postcodes.io/postcodes/{pc}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            r = data.get("result", {})
            return r.get("latitude"), r.get("longitude")
    except Exception:
        return None, None


def get_flood_areas(lat: float, lng: float, radius: int = 3000) -> list:
    """Get flood areas near coordinates."""
    url = f"{FLOOD_API}/id/floodAreas?lat={lat}&long={lng}&dist={radius}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            areas = []
            for item in data.get("items", []):
                areas.append({
                    "area_id": item.get("notation", ""),
                    "label": item.get("label", ""),
                    "description": item.get("description", ""),
                    "flood_type": item.get("floodWatchArea", {}).get("label", "") if isinstance(item.get("floodWatchArea"), dict) else "",
                    "river_sea": item.get("riverOrSea", ""),
                })
            return areas
    except Exception as e:
        return [{"error": str(e)}]


def get_flood_warnings(lat: float, lng: float) -> list:
    """Get active flood warnings near coordinates."""
    url = f"{FLOOD_API}/id/floods?lat={lat}&long={lng}&dist=5000"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            warnings = []
            for item in data.get("items", []):
                warnings.append({
                    "severity": item.get("severityLevel"),
                    "description": item.get("description", ""),
                    "area": item.get("floodArea", {}).get("label", "") if isinstance(item.get("floodArea"), dict) else "",
                    "time_raised": item.get("timeRaised", ""),
                    "message": item.get("message", "")[:200],
                })
            return warnings
    except Exception as e:
        return [{"error": str(e)}]


def get_flood_stations(lat: float, lng: float, radius: int = 3000) -> list:
    """Get nearby flood monitoring stations with latest readings."""
    url = f"{FLOOD_API}/id/stations?lat={lat}&long={lng}&dist={radius}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            stations = []
            for item in data.get("items", []):
                station = {
                    "label": item.get("label", ""),
                    "river": item.get("riverName", ""),
                    "town": item.get("town", ""),
                    "status": item.get("status", ""),
                }
                # Get latest reading if available
                measures = item.get("measures", [])
                if measures:
                    m = measures[0] if isinstance(measures, list) else measures
                    if isinstance(m, dict):
                        station["latest_value"] = m.get("latestReading", {}).get("value") if isinstance(m.get("latestReading"), dict) else None
                stations.append(station)
            return stations
    except Exception as e:
        return [{"error": str(e)}]


def assess_flood_risk(lat: float, lng: float) -> dict:
    """Full flood risk assessment for a location."""
    areas = get_flood_areas(lat, lng)
    warnings = get_flood_warnings(lat, lng)
    stations = get_flood_stations(lat, lng)

    # Determine risk level
    if warnings:
        risk = "HIGH — active flood warnings"
    elif len(areas) > 3:
        risk = "MEDIUM — multiple flood areas nearby"
    elif areas:
        risk = "LOW-MEDIUM — flood area nearby but no active warnings"
    else:
        risk = "LOW — no flood areas within 3km"

    return {
        "location": {"lat": lat, "lng": lng},
        "risk_level": risk,
        "flood_areas": areas,
        "active_warnings": warnings,
        "monitoring_stations": stations[:5],
    }


def main():
    params = json.load(sys.stdin)
    lat = params.get("lat")
    lng = params.get("lng")

    if not lat or not lng:
        postcode = params.get("postcode", "")
        if postcode:
            lat, lng = geocode_postcode(postcode)
            if not lat:
                print(json.dumps({"error": f"Could not geocode: {postcode}"}))
                sys.exit(1)
        else:
            print(json.dumps({"error": "provide 'lat'+'lng' or 'postcode'"}))
            sys.exit(1)

    result = assess_flood_risk(lat, lng)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
