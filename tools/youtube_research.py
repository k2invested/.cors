#!/usr/bin/env python3
"""youtube_research — search YouTube Shorts and extract transcripts.

Input JSON:
  {"action": "search", "query": "<search terms>", "count": 10}
    → Search for top Shorts, return metadata sorted by views.

  {"action": "transcript", "video_id": "<YouTube video ID>"}
    → Fetch transcript for a single video.

  {"action": "research", "query": "<search terms>", "count": 5}
    → Search top Shorts + fetch transcripts for each. Combined output.

Env:
  YOUTUBE_API_KEY — YouTube Data API v3 key (required for search).
"""
TOOL_DESC = 'search YouTube Shorts and extract transcripts.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'external'
TOOL_POST_OBSERVE = 'none'

import json
import os
import re as _re
import sys


def parse_duration(iso_duration: str) -> int:
    """Parse ISO 8601 duration (PT1M30S) to seconds."""
    m = _re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration or "")
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = int(m.group(3) or 0)
    return hours * 3600 + mins * 60 + secs


def search_shorts(query: str, count: int = 10, min_duration: int = 0,
                  max_duration: int = 0, min_views: int = 0,
                  published_after: str = "") -> list[dict]:
    """Search YouTube for top Shorts by view count.

    Args:
        min_duration: minimum video length in seconds (0 = no filter)
        max_duration: maximum video length in seconds (0 = no filter)
        min_views: minimum view count (0 = no filter)
        published_after: ISO date string e.g. "2025-01-01T00:00:00Z" (empty = no filter)
    """
    from googleapiclient.discovery import build

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return [{"error": "YOUTUBE_API_KEY not set"}]

    youtube = build("youtube", "v3", developerKey=api_key)

    # Fetch more than needed to account for filtering
    fetch_count = min(count * 3, 50) if (min_duration or max_duration or min_views) else min(count, 50)

    # Build search params
    search_params = dict(
        q=query,
        part="snippet",
        type="video",
        videoDuration="short",
        order="viewCount",
        maxResults=fetch_count,
        relevanceLanguage="en",
    )
    if published_after:
        search_params["publishedAfter"] = published_after

    request = youtube.search().list(**search_params)
    response = request.execute()

    video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
    if not video_ids:
        return []

    # Fetch statistics for each video
    stats_request = youtube.videos().list(
        id=",".join(video_ids),
        part="statistics,contentDetails,snippet",
    )
    stats_response = stats_request.execute()

    results = []
    for item in stats_response.get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        duration_iso = item.get("contentDetails", {}).get("duration", "")
        duration_secs = parse_duration(duration_iso)
        views = int(stats.get("viewCount", 0))

        # Apply filters
        if min_duration and duration_secs < min_duration:
            continue
        if max_duration and duration_secs > max_duration:
            continue
        if min_views and views < min_views:
            continue

        results.append({
            "video_id": item["id"],
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "views": views,
            "likes": int(stats.get("likeCount", 0)),
            "duration": duration_iso,
            "duration_secs": duration_secs,
            "published": snippet.get("publishedAt", ""),
        })

    # Sort by views descending
    results.sort(key=lambda x: x["views"], reverse=True)
    return results


def fetch_transcript(video_id: str) -> dict:
    """Fetch transcript for a YouTube video. Tries English first, then any language."""
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        api = YouTubeTranscriptApi()
        # Try English first
        try:
            result = api.fetch(video_id, languages=["en"])
        except Exception:
            # Fall back to any available language
            result = api.fetch(video_id)

        full_text = " ".join(s.text for s in result.snippets)

        # Skip non-Latin transcripts (likely not English)
        latin_chars = sum(1 for c in full_text if c.isascii() and c.isalpha())
        total_chars = sum(1 for c in full_text if c.isalpha())
        if total_chars > 0 and latin_chars / total_chars < 0.5:
            return {"video_id": video_id, "error": "non-English transcript"}

        timestamps = [
            {"t": round(s.start, 1), "text": s.text}
            for s in result.snippets
        ]
        return {
            "video_id": video_id,
            "text": full_text,
            "timestamps": timestamps,
            "word_count": len(full_text.split()),
        }

    except Exception as e:
        return {"video_id": video_id, "error": str(e)}


def research(query: str, count: int = 5) -> dict:
    """Search top Shorts + fetch transcripts. Combined research output."""
    videos = search_shorts(query, count)
    if not videos:
        return {"query": query, "videos": [], "error": "no results"}

    for video in videos:
        if "error" in video:
            continue
        transcript = fetch_transcript(video["video_id"])
        video["transcript"] = transcript.get("text", "")
        video["word_count"] = transcript.get("word_count", 0)
        if "error" in transcript:
            video["transcript_error"] = transcript["error"]

    # Summary stats
    with_transcripts = [v for v in videos if v.get("transcript")]
    return {
        "query": query,
        "total_results": len(videos),
        "with_transcripts": len(with_transcripts),
        "videos": videos,
    }


def main():
    params = json.load(sys.stdin)
    action = params.get("action", "search")

    if action == "search":
        query = params.get("query", "")
        count = params.get("count", 10)
        if not query:
            print("Error: missing 'query' parameter", file=sys.stderr)
            sys.exit(1)
        results = search_shorts(query, count)
        for r in results:
            views = f"{r['views']:,}" if isinstance(r.get('views'), int) else "?"
            print(f"- {r.get('title', '?')} ({views} views)")
            print(f"  https://youtube.com/shorts/{r.get('video_id', '?')}")
            print(f"  Channel: {r.get('channel', '?')} | Duration: {r.get('duration', '?')}")
            print()

    elif action == "transcript":
        video_id = params.get("video_id", "")
        if not video_id:
            print("Error: missing 'video_id' parameter", file=sys.stderr)
            sys.exit(1)
        result = fetch_transcript(video_id)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Transcript ({result['word_count']} words):")
            print(result["text"])

    elif action == "research":
        query = params.get("query", "")
        count = params.get("count", 5)
        if not query:
            print("Error: missing 'query' parameter", file=sys.stderr)
            sys.exit(1)
        result = research(query, count)
        print(f"## Research: {result['query']}")
        print(f"Found {result['total_results']} videos, {result['with_transcripts']} with transcripts\n")
        for v in result["videos"]:
            views = f"{v['views']:,}" if isinstance(v.get('views'), int) else "?"
            print(f"### {v.get('title', '?')} ({views} views)")
            print(f"https://youtube.com/shorts/{v.get('video_id', '?')}")
            print(f"Channel: {v.get('channel', '?')} | Duration: {v.get('duration', '?')}")
            if v.get("transcript"):
                print(f"Transcript ({v.get('word_count', 0)} words):")
                print(v["transcript"][:500])
                if len(v.get("transcript", "")) > 500:
                    print("...")
            elif v.get("transcript_error"):
                print(f"Transcript: {v['transcript_error']}")
            print()

    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
