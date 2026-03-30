#!/usr/bin/env python3
"""repo_index.py — Build a structured JSON index/synopsis of a directory.

Args (JSON on stdin or as --params):
  root              : relative directory path (default '.')
  mode              : full | structure | summaries | reading_plan (default 'structure')
  max_files         : max files to include in index (default 50)
  max_bytes_per_file: max bytes to read per file for summaries (default 2000)
  include_glob      : optional glob pattern to restrict files (e.g. '*.py')
  exclude_globs     : list of glob patterns to exclude (e.g. ['*.pyc', '__pycache__'])

Output (JSON on stdout):
  root              : resolved root path
  mode              : mode used
  total_files       : total files found before max_files cap
  files             : list of {path, size_bytes, lines, ext} for all indexed files
  high_value_files  : ranked list of {path, score, reasons[]} — files most worth reading
  hotspots          : files with highest line counts (likely core logic)
  reading_plan      : ordered list of {path, rationale} suggesting read order
  summaries         : (mode=full|summaries) {path: first N bytes} excerpts
  errors            : list of any non-fatal errors encountered
"""

import fnmatch
import json
import os
import sys
from pathlib import Path

# ── Default parameters ─────────────────────────────────────────────────

DEFAULT_EXCLUDE_GLOBS = [
    "*.pyc", "__pycache__", "*.egg-info", ".git", ".git/*",
    "node_modules", "node_modules/*", "*.so", "*.o", "*.a",
    ".DS_Store", "*.swp", "*.swo",
]

# Extensions considered high-signal for code/config
HIGH_VALUE_EXTENSIONS = {
    ".py": 10, ".rs": 10, ".go": 10, ".ts": 9, ".js": 8,
    ".json": 7, ".toml": 7, ".yaml": 6, ".yml": 6,
    ".md": 5, ".txt": 3, ".sh": 6, ".c": 8, ".cpp": 8, ".h": 6,
    ".html": 4, ".css": 3, ".sql": 6,
}

# Filename patterns that strongly suggest important files
HIGH_VALUE_NAMES = [
    "main", "lib", "core", "kernel", "index", "app", "server",
    "client", "config", "settings", "schema", "model", "api",
    "router", "handler", "manager", "registry", "chat", "agent",
    "README", "Makefile", "Cargo", "pyproject", "setup",
]


def parse_params() -> dict:
    """Read JSON params from stdin or --params CLI arg."""
    raw = ""
    if len(sys.argv) >= 3 and sys.argv[1] == "--params":
        raw = sys.argv[2]
    else:
        raw = sys.stdin.read().strip()

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from fenced block
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except Exception:
                    pass
        return {}


def matches_any_glob(name: str, rel_path: str, patterns: list) -> bool:
    """Return True if name or rel_path matches any glob pattern."""
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
        if fnmatch.fnmatch(rel_path, pat):
            return True
    return False


def count_lines(path: str) -> int:
    """Count lines in a file, returning 0 on binary/error."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def read_head(path: str, max_bytes: int) -> str:
    """Read the first max_bytes of a file as text."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except Exception as e:
        return f"[read error: {e}]"


def score_file(rel_path: str, size_bytes: int, lines: int) -> tuple:
    """Compute a heuristic importance score and list of reasons."""
    score = 0
    reasons = []

    path_obj = Path(rel_path)
    ext = path_obj.suffix.lower()
    stem = path_obj.stem.lower()
    name = path_obj.name
    depth = len(path_obj.parts) - 1  # 0 = top-level

    # Extension score
    ext_score = HIGH_VALUE_EXTENSIONS.get(ext, 1)
    score += ext_score
    if ext_score >= 8:
        reasons.append(f"high-value extension ({ext})")

    # Name match
    for hv in HIGH_VALUE_NAMES:
        if hv.lower() in stem:
            score += 5
            reasons.append(f"name matches '{hv}'")
            break

    # Top-level files get a boost
    if depth == 0:
        score += 3
        reasons.append("top-level file")
    elif depth == 1:
        score += 1

    # Large files likely contain more logic
    if lines > 500:
        score += 4
        reasons.append(f"large file ({lines} lines)")
    elif lines > 200:
        score += 2
        reasons.append(f"medium file ({lines} lines)")
    elif lines > 50:
        score += 1

    # Penalise test files slightly (still useful but lower priority)
    if "test" in stem or "spec" in stem:
        score -= 2
        reasons.append("test/spec file (lower priority)")

    return score, reasons


def build_index(params: dict) -> dict:
    """Core logic — walk root, build index, rank files."""
    errors = []

    # Resolve parameters
    root_raw = params.get("root", ".")
    mode = params.get("mode", "structure")
    max_files = int(params.get("max_files", 50))
    max_bytes_per_file = int(params.get("max_bytes_per_file", 2000))
    include_glob = params.get("include_glob", None)
    exclude_globs = list(params.get("exclude_globs", [])) + DEFAULT_EXCLUDE_GLOBS

    # Resolve root relative to WORKSPACE
    workspace = os.environ.get("WORKSPACE", ".")
    root = (Path(workspace) / root_raw).resolve()
    if not root.exists():
        return {"error": f"root path does not exist: {root_raw}", "errors": [f"root not found: {root_raw}"]}
    if not root.is_dir():
        return {"error": f"root is not a directory: {root_raw}", "errors": [f"not a directory: {root_raw}"]}

    # Walk the directory tree
    all_files = []
    for dirpath, dirnames, filenames in os.walk(str(root), topdown=True):
        rel_dir = os.path.relpath(dirpath, str(root))
        if rel_dir == ".":
            rel_dir = ""

        # Prune excluded directories in-place
        dirnames[:] = [
            d for d in dirnames
            if not matches_any_glob(d, os.path.join(rel_dir, d).lstrip("./"), exclude_globs)
        ]
        dirnames.sort()

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname).lstrip("./")
            if rel_path == "":
                rel_path = fname

            # Apply exclusion
            if matches_any_glob(fname, rel_path, exclude_globs):
                continue

            # Apply inclusion filter (supports comma-separated patterns)
            if include_glob:
                patterns = [p.strip() for p in include_glob.split(",")]
                if not any(fnmatch.fnmatch(fname, p) for p in patterns):
                    continue

            abs_path = os.path.join(dirpath, fname)
            try:
                size_bytes = os.path.getsize(abs_path)
            except OSError as e:
                errors.append(f"stat error {rel_path}: {e}")
                size_bytes = 0

            all_files.append({
                "rel_path": rel_path,
                "abs_path": abs_path,
                "size_bytes": size_bytes,
            })

    total_files = len(all_files)

    # Cap to max_files (keep largest files when trimming — they carry more signal)
    if len(all_files) > max_files:
        all_files.sort(key=lambda f: f["size_bytes"], reverse=True)
        all_files = all_files[:max_files]
        # Re-sort alphabetically for output
        all_files.sort(key=lambda f: f["rel_path"])

    # Compute line counts
    file_records = []
    for f in all_files:
        lines = count_lines(f["abs_path"])
        ext = Path(f["rel_path"]).suffix.lower()
        file_records.append({
            "path": f["rel_path"],
            "size_bytes": f["size_bytes"],
            "lines": lines,
            "ext": ext,
            "_abs": f["abs_path"],
        })

    # Score all files
    scored = []
    for rec in file_records:
        score, reasons = score_file(rec["path"], rec["size_bytes"], rec["lines"])
        scored.append((score, reasons, rec))

    scored.sort(key=lambda x: x[0], reverse=True)

    # high_value_files — top scored
    high_value_files = [
        {"path": rec["path"], "score": score, "reasons": reasons}
        for score, reasons, rec in scored[:15]
    ]

    # hotspots — highest line count
    hotspots = sorted(
        [{"path": rec["path"], "lines": rec["lines"]} for rec in file_records],
        key=lambda x: x["lines"],
        reverse=True,
    )[:10]

    # reading_plan — ordered suggestion for how to read the codebase
    reading_plan = _build_reading_plan(scored, file_records)

    # summaries — head of each file (only for mode=full or mode=summaries)
    summaries = {}
    if mode in ("full", "summaries"):
        for rec in file_records:
            summaries[rec["path"]] = read_head(rec["_abs"], max_bytes_per_file)

    # Clean output records (drop internal _abs key)
    files_out = [
        {"path": r["path"], "size_bytes": r["size_bytes"], "lines": r["lines"], "ext": r["ext"]}
        for r in file_records
    ]

    result = {
        "root": str(root),
        "mode": mode,
        "total_files": total_files,
        "indexed_files": len(files_out),
        "files": files_out,
        "high_value_files": high_value_files,
        "hotspots": hotspots,
        "reading_plan": reading_plan,
        "errors": errors,
    }

    if summaries:
        result["summaries"] = summaries

    return result


def _build_reading_plan(scored: list, file_records: list) -> list:
    """Produce an ordered reading plan from scored files."""
    plan = []
    seen = set()

    # Tier 1: config/manifest files first (understand project shape)
    for score, reasons, rec in scored:
        p = rec["path"]
        name = Path(p).name.lower()
        if any(kw in name for kw in ("readme", "cargo.toml", "pyproject", "package.json",
                                     "makefile", "setup.py", "setup.cfg", ".toml", ".yaml", ".yml", ".json")):
            if p not in seen:
                plan.append({"path": p, "rationale": "project manifest / config — read first for orientation"})
                seen.add(p)
                if len(plan) >= 3:
                    break

    # Tier 2: entry-points and core modules
    for score, reasons, rec in scored:
        p = rec["path"]
        stem = Path(p).stem.lower()
        if p in seen:
            continue
        if any(kw in stem for kw in ("main", "app", "server", "chat", "kernel", "core", "lib", "index")):
            plan.append({"path": p, "rationale": f"likely entry-point or core module (score={score})"})
            seen.add(p)
            if sum(1 for x in plan if "entry" in x["rationale"]) >= 4:
                break

    # Tier 3: highest-scored files not yet in plan
    for score, reasons, rec in scored:
        p = rec["path"]
        if p in seen:
            continue
        plan.append({"path": p, "rationale": f"high importance (score={score}): {'; '.join(reasons[:2])}"})
        seen.add(p)
        if len(plan) >= 12:
            break

    return plan


def main():
    params = parse_params()
    try:
        result = build_index(params)
    except Exception as e:
        result = {"error": str(e), "errors": [str(e)]}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
