"""validate_chain.py — Law 9 compliance validator for semantic tree compositions.

Law 9: The loop always closes.

Every background trigger (reprogramme_needed gap) must have a reintegration path:
  1. MANUAL AWAIT: a downstream await_needed step in the same .st (synchronous, same-turn)
  2. HEARTBEAT:    no await, but the heartbeat mechanism fires post-synthesis (asynchronous,
                   next turn). This is structurally guaranteed by the kernel — not a failure.

The validator distinguishes these paths and flags actual violations.

Per-skill outcomes:
  CLOSED     — reprogramme_needed + downstream await_needed. Explicit sync closure. Ideal.
  HEARTBEAT  — reprogramme_needed, no downstream await. Async closure via heartbeat. Valid.
  CLEAN      — no background trigger. Nothing to close. Fine.
  ORPHAN     — await_needed with no upstream reprogramme_needed. Suspicious (warn).
  MISORDERED — await_needed appears BEFORE its reprogramme_needed. Ordering violation (fail).

Recursive: if a step embeds a known skill hash in content_refs, that skill is also validated.
The validator reports the full tree with indent.

Usage:
  python3 tools/validate_chain.py                    # validate all skills/
  python3 tools/validate_chain.py skills/my.st       # single file
  python3 tools/validate_chain.py skills/            # directory
  python3 tools/validate_chain.py --json             # machine-readable output

Exit codes:
  0 — fully compliant (CLOSED, HEARTBEAT, CLEAN only)
  1 — violations found (ORPHAN or MISORDERED)
  2 — parse / IO error
"""
TOOL_DESC = 'Law 9 compliance validator for semantic tree compositions.'
TOOL_MODE = 'observe'
TOOL_SCOPE = 'workspace'
TOOL_POST_OBSERVE = 'none'


import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

CORS_ROOT = Path(__file__).parent.parent
SKILLS_DIR = CORS_ROOT / "skills"

BACKGROUND_VOCAB = "reprogramme_needed"
AWAIT_VOCAB = "await_needed"


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    """One Law 9 observation within a skill's step sequence."""
    kind: str          # CLOSED | HEARTBEAT | ORPHAN | MISORDERED
    trigger_idx: int   # step index of reprogramme_needed (-1 = N/A)
    await_idx: int     # step index of await_needed (-1 = N/A)
    message: str

    @property
    def is_violation(self) -> bool:
        return self.kind in ("ORPHAN", "MISORDERED")

    @property
    def is_warn(self) -> bool:
        return self.kind == "HEARTBEAT"

    @property
    def symbol(self) -> str:
        return {
            "CLOSED":     "[CLOSED]   ",
            "HEARTBEAT":  "[HEARTBEAT]",
            "ORPHAN":     "[ORPHAN]   ",
            "MISORDERED": "[MISORDERED]",
            "CLEAN":      "[CLEAN]    ",
        }.get(self.kind, f"[{self.kind}]")


@dataclass
class ValidationResult:
    """Validation outcome for a single .st file."""
    file: str                             # path relative to CORS_ROOT
    skill_name: str
    step_count: int
    findings: list[Finding] = field(default_factory=list)
    embedded: list["ValidationResult"] = field(default_factory=list)
    error: str | None = None

    @property
    def has_violations(self) -> bool:
        if any(f.is_violation for f in self.findings):
            return True
        return any(e.has_violations for e in self.embedded)

    @property
    def has_warnings(self) -> bool:
        if any(f.is_warn for f in self.findings):
            return True
        return any(e.has_warnings for e in self.embedded)

    @property
    def law9_status(self) -> str:
        if self.error:
            return "ERROR"
        if self.has_violations:
            return "FAIL"
        if self.has_warnings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "skill_name": self.skill_name,
            "step_count": self.step_count,
            "law9_status": self.law9_status,
            "findings": [
                {
                    "kind": f.kind,
                    "trigger_idx": f.trigger_idx,
                    "await_idx": f.await_idx,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "embedded": [e.to_dict() for e in self.embedded],
            "error": self.error,
        }


# ── Step Checker ──────────────────────────────────────────────────────────────

def check_steps(steps: list[dict]) -> list[Finding]:
    """Analyse a flat step sequence for Law 9 compliance.

    Rules:
      1. Every reprogramme_needed at index i must have a downstream await_needed
         at index j > i → CLOSED. If no downstream await → HEARTBEAT (valid).
      2. Every await_needed at index j must have an upstream reprogramme_needed
         at index i < j → otherwise ORPHAN (warn).
      3. If await appears before reprogramme in the same pair → MISORDERED (fail).
    """
    findings: list[Finding] = []

    # Collect positions
    bg_positions = [i for i, s in enumerate(steps) if s.get("vocab") == BACKGROUND_VOCAB]
    aw_positions = [i for i, s in enumerate(steps) if s.get("vocab") == AWAIT_VOCAB]

    if not bg_positions and not aw_positions:
        # Pure observation/mutation chain — nothing to close
        return []

    # Check every background trigger
    matched_awaits: set[int] = set()
    for bg_idx in bg_positions:
        # Downstream await: any await_needed at index > bg_idx
        downstream = [j for j in aw_positions if j > bg_idx]
        if downstream:
            aw_idx = downstream[0]   # closest downstream await
            matched_awaits.add(aw_idx)
            findings.append(Finding(
                kind="CLOSED",
                trigger_idx=bg_idx,
                await_idx=aw_idx,
                message=(
                    f"step[{bg_idx}] reprogramme_needed → "
                    f"step[{aw_idx}] await_needed "
                    f"(explicit sync closure)"
                ),
            ))
        else:
            # No downstream await — heartbeat takes over
            findings.append(Finding(
                kind="HEARTBEAT",
                trigger_idx=bg_idx,
                await_idx=-1,
                message=(
                    f"step[{bg_idx}] reprogramme_needed, no downstream await_needed "
                    f"(heartbeat fires post-synthesis — async closure)"
                ),
            ))

    # Check every await for upstream trigger
    for aw_idx in aw_positions:
        upstream = [i for i in bg_positions if i < aw_idx]
        if not upstream:
            # Check if there's a downstream trigger (misordering)
            downstream_bg = [i for i in bg_positions if i > aw_idx]
            if downstream_bg:
                bg_idx = downstream_bg[0]
                findings.append(Finding(
                    kind="MISORDERED",
                    trigger_idx=bg_idx,
                    await_idx=aw_idx,
                    message=(
                        f"step[{aw_idx}] await_needed appears BEFORE "
                        f"step[{bg_idx}] reprogramme_needed — "
                        f"checkpoint must follow its trigger"
                    ),
                ))
            else:
                # Await with no trigger anywhere
                findings.append(Finding(
                    kind="ORPHAN",
                    trigger_idx=-1,
                    await_idx=aw_idx,
                    message=(
                        f"step[{aw_idx}] await_needed has no upstream "
                        f"reprogramme_needed — orphaned checkpoint"
                    ),
                ))

    return findings


# ── Content-Ref Resolver ──────────────────────────────────────────────────────

def load_skill_registry() -> dict[str, Path]:
    """Build a hash→path index for all .st files in skills/.

    Uses the same hash function as loader.py (SHA-256[:12] of raw content).
    """
    import hashlib

    registry: dict[str, Path] = {}
    for root, _dirs, files in os.walk(SKILLS_DIR):
        for fname in sorted(files):
            if not fname.endswith(".st"):
                continue
            path = Path(root) / fname
            try:
                raw = path.read_text()
                h = hashlib.sha256(raw.encode()).hexdigest()[:12]
                registry[h] = path
            except OSError:
                pass
    return registry


def resolve_content_refs(refs: list, registry: dict[str, Path]) -> list[Path]:
    """Resolve content_refs to .st file paths where possible.

    Refs can be: step hashes ("step:xxxx"), HEAD, git refs, or skill hashes.
    We only attempt to resolve strings that look like 12-char hex (skill hashes).
    """
    resolved = []
    for ref in refs:
        if not isinstance(ref, str):
            continue
        ref = ref.strip()
        # Skip known non-skill refs
        if ref.upper() == "HEAD" or ref.startswith("step:"):
            continue
        # 12-char hex is a potential skill hash
        if len(ref) == 12 and all(c in "0123456789abcdef" for c in ref):
            path = registry.get(ref)
            if path:
                resolved.append(path)
    return resolved


# ── File Validator ─────────────────────────────────────────────────────────────

def validate_file(
    path: Path,
    registry: dict[str, Path],
    visited: set[str] | None = None,
    depth: int = 0,
) -> ValidationResult:
    """Validate a single .st file for Law 9 compliance.

    Recursively validates embedded skills referenced via content_refs.
    The `visited` set prevents infinite recursion on cyclic refs.
    """
    if visited is None:
        visited = set()

    try:
        rel_path = str(path.relative_to(CORS_ROOT))
    except ValueError:
        rel_path = str(path)

    if rel_path in visited:
        # Cycle detected — skip
        return ValidationResult(
            file=rel_path,
            skill_name="<cycle>",
            step_count=0,
            error="cycle detected — already visited in this tree",
        )
    visited = visited | {rel_path}

    try:
        raw = path.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        return ValidationResult(
            file=rel_path,
            skill_name=path.stem,
            step_count=0,
            error=str(e),
        )

    steps: list[dict] = data.get("steps", [])
    findings = check_steps(steps)

    # Recurse into embedded skills
    embedded_results: list[ValidationResult] = []
    for step in steps:
        refs = step.get("content_refs", [])
        if not refs:
            continue
        for embed_path in resolve_content_refs(refs, registry):
            try:
                e_rel = str(embed_path.relative_to(CORS_ROOT))
            except ValueError:
                e_rel = str(embed_path)
            if e_rel in visited:
                continue
            result = validate_file(embed_path, registry, visited, depth + 1)
            embedded_results.append(result)
            # Add embed path to visited so siblings don't re-validate
            visited = visited | {e_rel, str(embed_path)}

    return ValidationResult(
        file=rel_path,
        skill_name=data.get("name", path.stem),
        step_count=len(steps),
        findings=findings,
        embedded=embedded_results,
    )


# ── Directory Validator ────────────────────────────────────────────────────────

def validate_directory(dir_path: Path, registry: dict[str, Path]) -> list[ValidationResult]:
    """Validate all .st files in a directory (non-recursive — one level)."""
    results = []
    for p in sorted(dir_path.glob("*.st")):
        results.append(validate_file(p, registry))
    return results


def validate_all(registry: dict[str, Path]) -> list[ValidationResult]:
    """Validate every .st file in skills/ including codons/ subdirectory."""
    results = []
    for root, _dirs, files in os.walk(SKILLS_DIR):
        for fname in sorted(files):
            if not fname.endswith(".st"):
                continue
            p = Path(root) / fname
            results.append(validate_file(p, registry))
    return results


# ── Renderer ──────────────────────────────────────────────────────────────────

def _render_result(r: ValidationResult, indent: int = 0) -> list[str]:
    """Render a ValidationResult as human-readable lines."""
    pad = "  " * indent
    lines = []

    # Header
    status_mark = {"PASS": "✓", "WARN": "~", "FAIL": "✗", "ERROR": "!"}.get(
        r.law9_status, "?"
    )
    lines.append(f"{pad}{status_mark} {r.file}  [{r.skill_name}]  steps:{r.step_count}  → {r.law9_status}")

    if r.error:
        lines.append(f"{pad}  ERROR: {r.error}")
        return lines

    # No findings and no embedded = CLEAN
    if not r.findings and not r.embedded:
        lines.append(f"{pad}  [CLEAN]     no background triggers — nothing to close")
        return lines

    for f in r.findings:
        lines.append(f"{pad}  {f.symbol} {f.message}")

    for e in r.embedded:
        lines.append(f"{pad}  └─ embedded:")
        lines.extend(_render_result(e, indent + 2))

    return lines


def render_report(results: list[ValidationResult]) -> str:
    """Render the full validation report as a string."""
    lines = [
        "",
        "══════════════════════════════════════════════════",
        "  validate_chain — Law 9 compliance report",
        "══════════════════════════════════════════════════",
        "",
    ]

    total = 0
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERROR": 0}

    for r in results:
        lines.extend(_render_result(r))
        lines.append("")
        total += 1
        counts[r.law9_status] = counts.get(r.law9_status, 0) + 1

    # Summary
    lines.append("──────────────────────────────────────────────────")
    lines.append(
        f"  {total} skills  "
        f"✓ {counts['PASS']} PASS  "
        f"~ {counts['WARN']} WARN  "
        f"✗ {counts['FAIL']} FAIL  "
        f"! {counts['ERROR']} ERROR"
    )
    lines.append("")

    overall_fail = counts["FAIL"] > 0 or counts["ERROR"] > 0
    overall_warn = counts["WARN"] > 0

    if overall_fail:
        lines.append("  Law 9: NON-COMPLIANT — violations found (see FAIL above)")
    elif overall_warn:
        lines.append(
            "  Law 9: COMPLIANT (heartbeat paths present — async closure guaranteed)"
        )
    else:
        lines.append("  Law 9: FULLY COMPLIANT — all loops explicitly closed or clean")

    lines.append("══════════════════════════════════════════════════")
    lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate semantic tree compositions for Law 9 (loop-closing) compliance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to .st file or directory. Omit to validate all skills/.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of human report.",
    )
    args = parser.parse_args()

    # Build skill registry (hash → path) for content_ref resolution
    registry = load_skill_registry()

    # Determine what to validate
    if args.target is None:
        results = validate_all(registry)
    else:
        target = Path(args.target)
        if not target.is_absolute():
            target = CORS_ROOT / target
        if target.is_dir():
            results = validate_directory(target, registry)
        elif target.is_file():
            results = [validate_file(target, registry)]
        else:
            print(f"error: {target} not found", file=sys.stderr)
            sys.exit(2)

    if not results:
        print("No .st files found.")
        sys.exit(0)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(render_report(results))

    # Exit with failure if any violations
    has_failures = any(r.has_violations for r in results)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
