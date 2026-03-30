#!/usr/bin/env python3
"""ons_demographics — UK ONS area demographics and deprivation data.

Input JSON:
  {"postcode": "M1 1AA"}                    — demographics for postcode's LSOA
  {"lsoa": "Manchester 001A"}               — direct LSOA lookup
  {"district": "Manchester"}                — district-level summary

Output: JSON with deprivation indices, population, housing data.

Uses ONS Open Geography API and IoD (Indices of Deprivation) datasets.
Free, no API key needed.
"""
import json
import sys
import urllib.request
import urllib.parse


ONS_API = "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services"
POSTCODES_API = "https://api.postcodes.io"


def get_lsoa_from_postcode(postcode: str) -> dict:
    """Get LSOA and area metadata from postcode."""
    pc = urllib.parse.quote(postcode.strip())
    url = f"{POSTCODES_API}/postcodes/{pc}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == 200:
                r = data["result"]
                return {
                    "lsoa": r.get("lsoa"),
                    "msoa": r.get("msoa"),
                    "district": r.get("admin_district"),
                    "ward": r.get("admin_ward"),
                    "region": r.get("region"),
                    "lat": r.get("latitude"),
                    "lng": r.get("longitude"),
                    "postcode": r.get("postcode"),
                }
            return {"error": f"postcode not found: {postcode}"}
    except Exception as e:
        return {"error": str(e)}


def get_deprivation_data(lsoa_name: str) -> dict:
    """Fetch Index of Multiple Deprivation data for an LSOA.
    Uses the IoD 2019 dataset via ONS ArcGIS."""
    # Search for LSOA in IoD dataset
    encoded = urllib.parse.quote(lsoa_name)
    url = (f"{ONS_API}/IMD_2019/FeatureServer/0/query?"
           f"where=lsoa11nm%20LIKE%20%27%25{encoded}%25%27&"
           f"outFields=*&f=json&resultRecordCount=5")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            features = data.get("features", [])
            if not features:
                return {"lsoa": lsoa_name, "error": "no deprivation data found"}

            attrs = features[0].get("attributes", {})
            return {
                "lsoa": lsoa_name,
                "imd_rank": attrs.get("IMDRank"),
                "imd_decile": attrs.get("IMDDec0"),
                "income_rank": attrs.get("IncRank"),
                "income_decile": attrs.get("IncDec"),
                "employment_rank": attrs.get("EmpRank"),
                "employment_decile": attrs.get("EmpDec"),
                "education_rank": attrs.get("EduRank"),
                "education_decile": attrs.get("EduDec"),
                "health_rank": attrs.get("HDDRank"),
                "health_decile": attrs.get("HDDDec"),
                "crime_rank": attrs.get("CriRank"),
                "crime_decile": attrs.get("CriDec"),
                "housing_rank": attrs.get("BHSRank"),
                "housing_decile": attrs.get("BHSDec"),
                "environment_rank": attrs.get("EnvRank"),
                "environment_decile": attrs.get("EnvDec"),
                "note": "Decile 1 = most deprived 10%, Decile 10 = least deprived 10%",
            }
    except Exception as e:
        return {"lsoa": lsoa_name, "error": str(e)}


def get_district_summary(district: str) -> dict:
    """Get summary demographics for a district using postcodes.io outcodes."""
    # Get a representative postcode for the district
    url = f"{POSTCODES_API}/places?q={urllib.parse.quote(district)}&limit=1"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("result", [])
            if not results:
                return {"district": district, "error": "district not found"}

            place = results[0]
            return {
                "district": district,
                "name": place.get("name_1", ""),
                "county": place.get("county_unitary", ""),
                "region": place.get("region", ""),
                "country": place.get("country", ""),
                "type": place.get("local_type", ""),
                "lat": place.get("latitude"),
                "lng": place.get("longitude"),
            }
    except Exception as e:
        return {"district": district, "error": str(e)}


def main():
    params = json.load(sys.stdin)

    if params.get("postcode"):
        # Get LSOA from postcode, then fetch deprivation
        area = get_lsoa_from_postcode(params["postcode"])
        if "error" in area:
            print(json.dumps(area, indent=2))
            sys.exit(1)

        lsoa = area.get("lsoa", "")
        if lsoa:
            deprivation = get_deprivation_data(lsoa)
            area["deprivation"] = deprivation
        print(json.dumps(area, indent=2))

    elif params.get("lsoa"):
        result = get_deprivation_data(params["lsoa"])
        print(json.dumps(result, indent=2))

    elif params.get("district"):
        result = get_district_summary(params["district"])
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({"error": "provide 'postcode', 'lsoa', or 'district'"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
