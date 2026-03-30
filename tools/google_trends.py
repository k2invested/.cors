#!/usr/bin/env python3
"""google_trends — search interest over time via Google Trends.

Input JSON:
  {"keywords": ["buy to let", "house prices"]}              — compare keywords
  {"keywords": ["manchester property"], "timeframe": "today 12-m"}  — custom timeframe
  {"keywords": ["BTL mortgage"], "geo": "GB"}               — UK only

Output: JSON with interest over time data and related queries.

Uses pytrends library (unofficial Google Trends API). Free, no API key.
pip install pytrends
"""
import json
import sys


def get_trends(keywords: list, timeframe: str = "today 12-m", geo: str = "GB") -> dict:
    """Fetch Google Trends data for keywords."""
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"error": "pytrends not installed — run: pip install pytrends"}

    try:
        pytrends = TrendReq(hl='en-GB', tz=0)
        pytrends.build_payload(keywords[:5], cat=0, timeframe=timeframe, geo=geo)

        # Interest over time
        iot = pytrends.interest_over_time()
        timeline = []
        if not iot.empty:
            for date, row in iot.iterrows():
                entry = {"date": date.strftime("%Y-%m-%d")}
                for kw in keywords[:5]:
                    if kw in row:
                        entry[kw] = int(row[kw])
                timeline.append(entry)

        # Related queries
        related = {}
        try:
            rq = pytrends.related_queries()
            for kw in keywords[:5]:
                if kw in rq and rq[kw].get("rising") is not None:
                    rising = rq[kw]["rising"]
                    if rising is not None and not rising.empty:
                        related[kw] = {
                            "rising": rising.head(10).to_dict("records"),
                        }
                    top = rq[kw].get("top")
                    if top is not None and not top.empty:
                        if kw not in related:
                            related[kw] = {}
                        related[kw]["top"] = top.head(10).to_dict("records")
        except Exception:
            pass  # Related queries sometimes fail

        return {
            "keywords": keywords[:5],
            "timeframe": timeframe,
            "geo": geo,
            "data_points": len(timeline),
            "timeline": timeline[-12:] if len(timeline) > 12 else timeline,
            "related_queries": related,
        }

    except Exception as e:
        return {"error": str(e)}


def main():
    params = json.load(sys.stdin)
    keywords = params.get("keywords", [])
    if not keywords:
        print(json.dumps({"error": "provide 'keywords' array"}))
        sys.exit(1)

    result = get_trends(
        keywords,
        timeframe=params.get("timeframe", "today 12-m"),
        geo=params.get("geo", "GB"),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
