"""gap_config_report — render the current kernel vocab and tool foundation config."""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import action_foundations as foundations
from skills.loader import load_all
from vocab_registry import VOCABS, TOOL_MAP


def _git(args: list[str], _stdin: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


def _md_row(values: list[str]) -> str:
    safe = [str(v).replace("|", "\\|").replace("\n", " ") for v in values]
    return "| " + " | ".join(safe) + " |"


def _render_vocab_table() -> list[str]:
    lines = ["## Kernel Vocab Config", _md_row([
        "Vocab",
        "Category",
        "Priority",
        "Deterministic",
        "Observation only",
        "Post-gap emission",
        "Tool",
        "Post-observe",
        "Description",
    ]), _md_row(["---"] * 9)]
    for name, spec in VOCABS.items():
        lines.append(_md_row([
            name,
            spec.category,
            str(spec.priority),
            _bool_text(spec.deterministic),
            _bool_text(spec.observation_only),
            _bool_text(spec.allows_post_gap_emission),
            spec.tool or "",
            spec.post_observe or "",
            spec.desc,
        ]))
    return lines


def _render_tool_table() -> list[str]:
    chains_dir = ROOT / "state" / "chains"
    with contextlib.redirect_stdout(io.StringIO()):
        registry = load_all(str(ROOT / "skills"))
    tool_specs = [
        spec for spec in foundations.list_action_foundations(
            registry=registry,
            chains_dir=chains_dir,
            cors_root=ROOT,
            tool_map=TOOL_MAP,
            git=_git,
        )
        if spec.kind == "tool_blob"
    ]
    lines = ["## Tool Foundations", _md_row([
        "Blob ref",
        "Source",
        "Activation",
        "Default gap",
        "OMO role",
        "Description",
    ]), _md_row(["---"] * 6)]
    for spec in tool_specs:
        lines.append(_md_row([
            spec.ref,
            spec.source,
            spec.activation,
            spec.default_gap,
            spec.omo_role,
            spec.desc,
        ]))
    return lines


def render_report() -> str:
    lines = [
        "# Gap Config Report",
        "",
        "Generated from `vocab_registry.VOCABS` and `action_foundations.list_action_foundations(...)`.",
        "",
    ]
    lines.extend(_render_vocab_table())
    lines.append("")
    lines.extend(_render_tool_table())
    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.write(render_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
