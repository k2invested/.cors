#!/usr/bin/env python3
"""json_query — JSONPath query against agent memory stores.

Input JSON: {"query": "<JSONPath or text search>", "filter": "<optional text filter>"}
Env: SELF_JSON_PATH — path to the self.json memory store.
"""
import json, os, sys

MAX_RESULTS = 50
MAX_OUTPUT = 32_000


def _simple_query(data, query, text_filter=None):
    """Simple dot-notation query fallback when jsonpath_ng is unavailable.

    Supports:
      $             — return all entries
      $[-N:]        — last N entries
      $[N]          — entry at index N
      $..key        — recursive descent for key
    """
    results = []

    if not isinstance(data, list):
        data = [data]

    # $[-N:] — last N entries
    if query.startswith("$[") and ":" in query:
        try:
            n = int(query.split("[")[1].split(":")[0])
            results = data[n:]
        except (ValueError, IndexError):
            results = data
    # $[N] — specific index
    elif query.startswith("$[") and "]" in query:
        try:
            n = int(query.split("[")[1].split("]")[0])
            results = [data[n]] if abs(n) < len(data) else []
        except (ValueError, IndexError):
            results = []
    # $..key — recursive descent
    elif query.startswith("$.."):
        key = query[3:]
        def extract(obj):
            found = []
            if isinstance(obj, dict):
                if key in obj:
                    found.append(obj[key])
                for v in obj.values():
                    found.extend(extract(v))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(extract(item))
            return found
        results = extract(data)
    # $ — all entries
    elif query.strip() == "$":
        results = data
    else:
        # Try as text search across assessments
        results = data

    # Apply text filter
    if text_filter:
        text_filter_lower = text_filter.lower()
        filtered = []
        for item in results:
            s = json.dumps(item) if not isinstance(item, str) else item
            if text_filter_lower in s.lower():
                filtered.append(item)
        results = filtered

    return results[:MAX_RESULTS]


def main():
    params = json.load(sys.stdin)
    query = params.get("query", "$")
    text_filter = params.get("filter", None)

    json_path = os.environ.get("SELF_JSON_PATH", "")
    if not json_path or not os.path.exists(json_path):
        print(f"Error: SELF_JSON_PATH not set or file not found ({json_path})")
        sys.exit(1)

    try:
        with open(json_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading {json_path}: {e}")
        sys.exit(1)

    # Try jsonpath_ng first, fall back to simple query
    try:
        from jsonpath_ng.ext import parse as jp_parse
        expr = jp_parse(query)
        matches = [m.value for m in expr.find(data)]
        if text_filter:
            text_filter_lower = text_filter.lower()
            matches = [
                m for m in matches
                if text_filter_lower in (json.dumps(m) if not isinstance(m, str) else m).lower()
            ]
        results = matches[:MAX_RESULTS]
    except ImportError:
        results = _simple_query(data, query, text_filter)
    except Exception:
        # JSONPath parse error — fall back to simple query
        results = _simple_query(data, query, text_filter)

    # Auto-fallback: if complex query returned empty, retry as text search
    # using query keywords against last 20 entries
    if not results and query not in ("$", "$[-") and not query.startswith("$["):
        # Extract keywords from the query for text search
        keywords = text_filter or query
        # Strip JSONPath syntax to get meaningful words
        for ch in "$..*[]?@(){}|=!<>,;:'\"":
            keywords = keywords.replace(ch, " ")
        keywords = " ".join(w for w in keywords.split() if len(w) > 2).strip()
        if keywords and isinstance(data, list):
            fallback = _simple_query(data, "$[-20:]", keywords)
            if fallback:
                results = fallback
                query = f"$[-20:] (auto-fallback, filter='{keywords}')"

    if not results:
        print(f"No results for query '{query}'" + (f" with filter '{text_filter}'" if text_filter else ""))
    else:
        output = json.dumps(results, indent=1, default=str)
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + f"\n... (truncated, {len(results)} total results)"
        print(output)


if __name__ == "__main__":
    main()
