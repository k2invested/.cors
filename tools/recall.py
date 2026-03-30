#!/usr/bin/env python3
"""recall.py — Natural-language recall over all persisted agent memory.

Searches across all memory stores:
  - mem/agents/{id}/self.json      (reasoning steps — agent identity)
  - mem/agents/{id}/registry.json  (commitments, profiles, tasks — shared registry)
  - mem/agents/{id}/streams/*.json (conversations, judgments, artifacts)
  - mem/units/*.json               (per-turn snapshots)

Input (JSON on stdin):
  {
    "query": "<required natural-language query>",
    "scope": "<optional: self|registry|streams|units|all, default all>",
    "contact_id": "<optional stream/contact id filter>",
    "max_results": 5,
    "max_chars": 4000
  }

Output (stdout): human-readable ranked results with citations.

Env: SELF_JSON_PATH — used to derive mem root path.
     REGISTRY_PATH — path to commitments.json (optional).
"""

import json
import os
import re
import sys
from pathlib import Path

VALID_SCOPES = {"self", "registry", "streams", "units", "all"}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def tokenize(text: str):
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if t]


def coerce_int(value, default, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def mem_root():
    env_self = os.environ.get("SELF_JSON_PATH", "").strip()
    if env_self:
        p = Path(env_self).resolve()
        if p.name == "self.json":
            # .../mem/agents/<agent>/self.json -> .../mem
            try:
                return p.parents[2]
            except IndexError:
                pass
    return Path(__file__).resolve().parent.parent / "mem"


def self_json_path():
    env = os.environ.get("SELF_JSON_PATH", "").strip()
    if env:
        return Path(env)
    return mem_root() / "agents" / "step_kernel" / "self.json"


def registry_path():
    env = os.environ.get("REGISTRY_PATH", "").strip()
    if env:
        return Path(env)
    return mem_root() / "agents" / "step_kernel" / "registry.json"


def extract_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(extract_text(v) for v in value)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if str(k).startswith("_"):
                continue
            parts.append(extract_text(v))
        return " ".join(p for p in parts if p)
    return str(value)


def pick_timestamp(obj):
    if not isinstance(obj, dict):
        return ""
    for key in ("_t", "t", "_created", "created_at", "updated_at"):
        val = obj.get(key)
        if val and str(val):
            return str(val)
    added = obj.get("added")
    if isinstance(added, dict):
        for key in ("_linked_at", "_created"):
            val = added.get(key)
            if val and str(val):
                return str(val)
    return ""


def score_entry(text, terms, timestamp, source_kind):
    text_l = text.lower()
    overlap = sum(1 for t in terms if t in text_l)
    if overlap == 0:
        return 0.0
    density = overlap / max(len(terms), 1)
    recency_bonus = 0.15 if timestamp else 0.0
    kind_bonus = {"self": 0.1, "commitment": 0.1, "stream": 0.05, "unit": 0.0}
    return overlap + density + recency_bonus + kind_bonus.get(source_kind, 0.0)


def snippet(text, terms, limit=220):
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    lower = clean.lower()
    pos = min((lower.find(t) for t in terms if lower.find(t) >= 0), default=-1)
    if pos < 0:
        return clean[:limit - 3] + "..."
    start = max(0, pos - 60)
    end = min(len(clean), start + limit)
    out = clean[start:end]
    if start > 0:
        out = "..." + out
    if end < len(clean):
        out = out + "..."
    return out


# ── Store scanners ────────────────────────────────────────────────────

def scan_self(terms, max_results):
    """Search self.json — reasoning steps (agent identity)."""
    results = []
    path = self_json_path()
    data = load_json(path)
    if not isinstance(data, list):
        return results
    # Search individual reasoning steps (most recent first)
    for i, item in enumerate(reversed(data)):
        text = extract_text(item)
        ts = pick_timestamp(item)
        sc = score_entry(text, terms, ts, "self")
        if sc <= 0:
            continue
        role = item.get("_role", "") if isinstance(item, dict) else ""
        step_id = item.get("_step_id", "") if isinstance(item, dict) else ""
        results.append({
            "score": sc,
            "kind": "self",
            "id": f"step_{step_id}" if step_id else f"entry_{len(data)-1-i}",
            "role": role,
            "timestamp": ts,
            "text": text,
        })
        if len(results) >= max_results * 3:
            break
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results * 3]


def scan_registry(terms, max_results):
    """Search registry.json — commitments, profiles, tasks."""
    results = []
    path = registry_path()
    data = load_json(path)
    if not isinstance(data, list):
        return results
    for item in data:
        if not isinstance(item, dict):
            continue
        rtype = item.get("_type", "unknown")
        text = extract_text(item)
        ts = pick_timestamp(item)
        sc = score_entry(text, terms, ts, rtype)
        if sc <= 0:
            continue
        rid = (item.get("commitment_id") or item.get("contact_id")
               or item.get("task_id") or "?")
        results.append({
            "score": sc,
            "kind": rtype,
            "id": rid,
            "timestamp": ts,
            "text": text,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results * 3]


def scan_units(root, terms, max_results):
    """Search units/*.json — per-turn snapshots."""
    results = []
    units_dir = root / "units"
    if not units_dir.exists():
        return results
    files = sorted(units_dir.glob("*.json"), reverse=True)
    for path in files:
        data = load_json(path)
        if not isinstance(data, list):
            continue
        unit_id = path.stem
        combined = " ".join(extract_text(item) for item in data)
        ts = ""
        for item in data:
            ts = pick_timestamp(item)
            if ts:
                break
        sc = score_entry(combined, terms, ts, "unit")
        if sc <= 0:
            continue
        results.append({
            "score": sc,
            "kind": "unit",
            "id": unit_id,
            "timestamp": ts,
            "text": combined,
        })
    results.sort(key=lambda r: (r["score"], r["timestamp"]), reverse=True)
    return results[:max_results * 3]


def scan_streams(root, terms, contact_id, max_results):
    """Search streams/*.json — conversations, judgments, artifacts."""
    results = []
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return results
    for agent_dir in sorted(agents_dir.iterdir()):
        streams_dir = agent_dir / "streams"
        if not streams_dir.exists() or not streams_dir.is_dir():
            continue
        for path in sorted(streams_dir.glob("*.json")):
            stream_name = path.stem
            if contact_id and stream_name != contact_id:
                continue
            data = load_json(path)
            if not isinstance(data, list):
                continue
            # Score individual entries for better granularity
            for j, item in enumerate(reversed(data)):
                text = extract_text(item)
                ts = pick_timestamp(item)
                sc = score_entry(text, terms, ts, "stream")
                if sc <= 0:
                    continue
                results.append({
                    "score": sc,
                    "kind": "stream",
                    "id": stream_name,
                    "agent": agent_dir.name,
                    "timestamp": ts,
                    "text": text,
                })
                if len(results) >= max_results * 5:
                    break
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results * 3]


# ── Render ────────────────────────────────────────────────────────────

def render(query, results, max_chars):
    if not results:
        return f"No recall results for: {query}"
    lines = [f"Recall results for: {query}"]
    for i, item in enumerate(results, 1):
        kind = item["kind"]
        if kind == "self":
            role = item.get("role", "")
            header = f"{i}. [self/{item['id']}]"
            if role:
                header += f" role={role}"
        elif kind == "commitment":
            header = f"{i}. [commitment {item['id']}]"
        elif kind == "unit":
            header = f"{i}. [unit {item['id']}]"
        else:
            header = f"{i}. [stream {item['id']}]"
            if item.get("agent"):
                header += f" agent={item['agent']}"
        if item.get("timestamp"):
            header += f" t={item['timestamp']}"
        lines.append(header)
        lines.append(f"   {snippet(item['text'], tokenize(query))}")
    out = "\n".join(lines)
    if len(out) > max_chars:
        return out[:max_chars - 16] + "\n...[truncated]"
    return out


# ── Main ──────────────────────────────────────────────────────────────

def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: no input", file=sys.stderr)
        sys.exit(1)
    try:
        params = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    query = str(params.get("query", "")).strip()
    if not query:
        print("Error: query is required", file=sys.stderr)
        sys.exit(1)

    terms = tokenize(query)
    if not terms:
        print("Error: query must contain searchable terms", file=sys.stderr)
        sys.exit(1)

    scope = str(params.get("scope", "all")).strip().lower()
    if scope not in VALID_SCOPES:
        scope = "all"
    contact_id = str(params.get("contact_id", "")).strip()
    max_results = coerce_int(params.get("max_results", 5), 5, 1, 20)
    max_chars = coerce_int(params.get("max_chars", 4000), 4000, 500, 20000)

    root = mem_root()
    candidates = []
    if scope in {"self", "all"}:
        candidates.extend(scan_self(terms, max_results))
    if scope in {"registry", "all"}:
        candidates.extend(scan_registry(terms, max_results))
    if scope in {"units", "all"}:
        candidates.extend(scan_units(root, terms, max_results))
    if scope in {"streams", "all"}:
        candidates.extend(scan_streams(root, terms, contact_id, max_results))

    candidates.sort(key=lambda r: (r["score"], r.get("timestamp", "")), reverse=True)
    top = candidates[:max_results]
    print(render(query, top, max_chars))


if __name__ == "__main__":
    main()
