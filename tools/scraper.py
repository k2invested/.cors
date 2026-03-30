#!/usr/bin/env python3
"""YouTube Shorts scraper daemon — runs independently of the kernel.

Scrapes top Shorts transcripts on a schedule, stores to data/research/.
The kernel reads this data via scan_needed — the scraper never touches the kernel.

Usage:
  python3 scraper.py                    # run once
  python3 scraper.py --loop 3600        # run every hour
  python3 scraper.py --queries queries.json  # use custom query list

Config:
  data/research/queries.json — list of search queries + niches
  data/research/transcripts.json — accumulated transcript database

Env:
  YOUTUBE_API_KEY — required
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Load .env
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from youtube_research import search_shorts, fetch_transcript

# ── Config ─────────────────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent
RESEARCH_DIR = BASE / "data" / "research"
TRANSCRIPTS_DB = RESEARCH_DIR / "transcripts.json"
QUERIES_FILE = RESEARCH_DIR / "queries.json"

DEFAULT_QUERIES = [
    {"query": "reddit story time", "niche": "funny_shorts_viral", "count": 15, "min_duration": 30, "max_duration": 180, "min_views": 500000},
    {"query": "scary story narrated", "niche": "funny_shorts_viral", "count": 15, "min_duration": 30, "max_duration": 180, "min_views": 500000},
    {"query": "viral story shorts narrator voice", "niche": "funny_shorts_viral", "count": 15, "min_duration": 30, "max_duration": 180, "min_views": 500000},
]

# ── Database ───────────────────────────────────────────────────────────

def load_db() -> dict:
    """Load the transcript database."""
    if TRANSCRIPTS_DB.exists():
        return json.loads(TRANSCRIPTS_DB.read_text())
    return {"videos": {}, "scrape_log": [], "total_videos": 0, "total_with_transcripts": 0}


def save_db(db: dict):
    """Save the transcript database."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DB.write_text(json.dumps(db, indent=2, ensure_ascii=False))


def load_queries() -> list:
    """Load search queries from config or use defaults."""
    if QUERIES_FILE.exists():
        return json.loads(QUERIES_FILE.read_text())
    # Write defaults on first run
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    QUERIES_FILE.write_text(json.dumps(DEFAULT_QUERIES, indent=2))
    return DEFAULT_QUERIES


# ── Scrape ─────────────────────────────────────────────────────────────

def scrape_once(queries: list = None):
    """Run one scrape cycle across all queries."""
    if queries is None:
        queries = load_queries()

    db = load_db()
    timestamp = datetime.now(timezone.utc).isoformat()
    new_videos = 0
    new_transcripts = 0

    for q in queries:
        query = q.get("query", "")
        niche = q.get("niche", "unknown")
        count = q.get("count", 10)
        min_duration = q.get("min_duration", 0)
        max_duration = q.get("max_duration", 0)
        min_views = q.get("min_views", 0)
        published_after = q.get("published_after", "")

        print(f"[scraper] searching: {query} (niche={niche}, count={count}, dur={min_duration}-{max_duration}s, min_views={min_views:,})")

        try:
            videos = search_shorts(query, count, min_duration=min_duration,
                                   max_duration=max_duration, min_views=min_views,
                                   published_after=published_after)
        except Exception as e:
            print(f"[scraper] search error: {e}")
            continue

        for v in videos:
            vid = v.get("video_id", "")
            if not vid:
                continue

            # Skip if already in database
            if vid in db["videos"]:
                continue

            # Fetch transcript (with delay to avoid rate limiting)
            print(f"  [{vid}] {v.get('title', '?')[:60]} ({v.get('views', 0):,} views)")
            time.sleep(2)  # rate limit protection
            try:
                transcript = fetch_transcript(vid)
            except Exception as e:
                print(f"  [{vid}] transcript error: {e}")
                transcript = {"error": str(e)}

            # Calculate velocity (views per day since publish)
            views = v.get("views", 0)
            published = v.get("published", "")
            views_per_day = 0
            days_since_publish = 0
            if published:
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    days_since_publish = max((datetime.now(timezone.utc) - pub_dt).days, 1)
                    views_per_day = round(views / days_since_publish)
                except Exception:
                    pass

            # Store
            entry = {
                "video_id": vid,
                "title": v.get("title", ""),
                "channel": v.get("channel", ""),
                "views": views,
                "likes": v.get("likes", 0),
                "duration": v.get("duration", ""),
                "duration_secs": v.get("duration_secs", 0),
                "published": published,
                "days_since_publish": days_since_publish,
                "views_per_day": views_per_day,
                "niche": niche,
                "query": query,
                "scraped_at": timestamp,
            }

            if "error" not in transcript:
                entry["transcript"] = transcript.get("text", "")
                entry["word_count"] = transcript.get("word_count", 0)
                entry["timestamps"] = transcript.get("timestamps", [])
                new_transcripts += 1
            else:
                entry["transcript_error"] = transcript.get("error", "unknown")

            db["videos"][vid] = entry
            new_videos += 1

    # Sort by velocity (views_per_day) — highest first
    sorted_videos = dict(
        sorted(db["videos"].items(),
               key=lambda x: x[1].get("views_per_day", 0),
               reverse=True)
    )
    db["videos"] = sorted_videos

    # Update stats
    db["total_videos"] = len(db["videos"])
    db["total_with_transcripts"] = sum(
        1 for v in db["videos"].values() if v.get("transcript")
    )
    db["scrape_log"].append({
        "t": timestamp,
        "queries": len(queries),
        "new_videos": new_videos,
        "new_transcripts": new_transcripts,
    })

    save_db(db)
    print(f"[scraper] done: {new_videos} new videos, {new_transcripts} new transcripts")
    print(f"[scraper] database: {db['total_videos']} total, {db['total_with_transcripts']} with transcripts")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts transcript scraper")
    parser.add_argument("--loop", type=int, default=0,
                        help="Run every N seconds (0 = run once)")
    parser.add_argument("--queries", type=str, default=None,
                        help="Path to queries JSON file")
    args = parser.parse_args()

    if not os.environ.get("YOUTUBE_API_KEY"):
        print("Error: YOUTUBE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    queries = None
    if args.queries:
        queries = json.loads(Path(args.queries).read_text())

    if args.loop > 0:
        print(f"[scraper] starting loop (every {args.loop}s)")
        while True:
            try:
                scrape_once(queries)
            except Exception as e:
                print(f"[scraper] error: {e}")
            print(f"[scraper] sleeping {args.loop}s...")
            time.sleep(args.loop)
    else:
        scrape_once(queries)


if __name__ == "__main__":
    main()
