"""control_surface — runtime-owned operator and system inventory renders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from system.tool_registry import render_public_tool_registry
from vocab_registry import CONFIGURABLE_VOCABS, FOUNDATIONAL_BRIDGES


def render_admin_surface(skill: Any, *, cors_root: Path) -> str:
    data = skill.payload or {}
    lines = [f"## Identity: {skill.display_name}:{skill.hash}"]
    try:
        rel_source = Path(skill.source).resolve().relative_to(cors_root)
        lines.append(f"  source: {rel_source}")
    except ValueError:
        lines.append(f"  source: {skill.source}")

    identity = data.get("identity", {}) or {}
    for k, v in identity.items():
        lines.append(f"  {k}: {v}")

    preferences = data.get("preferences", {}) or {}
    if preferences:
        lines.append("## Mutable Preferences Surface")
        for category, prefs in preferences.items():
            lines.append(f"  {category}:")
            if isinstance(prefs, dict):
                for k, v in prefs.items():
                    lines.append(f"    {k}: {v}")
            else:
                lines.append(f"    {prefs}")

    access_rules = data.get("access_rules", {}) or {}
    if access_rules:
        lines.append("## Access Rules")
        for k, v in access_rules.items():
            lines.append(f"  {k}: {v}")

    init = data.get("init", {}) or {}
    if init:
        lines.append("## Init")
        for k, v in init.items():
            lines.append(f"  {k}: {v}")

    return "\n".join(lines)


def _sorted_entities(registry: Any) -> list[Any]:
    entities = [
        s for s in registry.all_skills()
        if Path(s.source).name == "admin.st" or "entities" in Path(s.source).parts or s.artifact_kind == "entity"
    ]
    return sorted(entities, key=lambda s: (s.display_name.lower(), s.hash))


def _sorted_workflows(registry: Any) -> list[Any]:
    workflows = [
        s for s in registry.by_hash.values()
        if "actions" in Path(s.source).parts or getattr(s, "is_command", False)
    ]
    return sorted(workflows, key=lambda s: (s.name.lower(), s.hash))


def render_system_control_surface(
    registry: Any,
    *,
    cors_root: Path,
    title: str = "## System Control Surface",
    sections: set[str] | None = None,
) -> str:
    selected = sections or {"entities", "workflows", "vocab"}
    lines = [title]

    if "entities" in selected:
        lines.append("## Available Entities")
        entities = _sorted_entities(registry)
        if entities:
            for entity in entities:
                lines.append(f"  - {entity.display_name}:{entity.hash} ({Path(entity.source).name}) — {entity.desc}")
        else:
            lines.append("  - none")

    if "workflows" in selected:
        lines.append("## Available Workflows")
        workflows = _sorted_workflows(registry)
        if workflows:
            for workflow in workflows:
                lines.append(f"  - {workflow.name}:{workflow.hash} — {workflow.desc}")
        else:
            lines.append("  - none")

    if "vocab" in selected:
        lines.append("## Vocab Map")
        for name, spec in sorted(CONFIGURABLE_VOCABS.items()):
            target = spec.target_ref or spec.target_kind or "internal"
            lines.append(f"  - {name} -> {target}")
        for name in sorted(FOUNDATIONAL_BRIDGES):
            lines.append(f"  - {name} -> bridge")

    if "tools" in selected:
        lines.append(render_public_tool_registry(cors_root))

    return "\n".join(lines)

