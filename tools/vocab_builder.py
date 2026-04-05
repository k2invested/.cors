#!/usr/bin/env python3
"""vocab_builder — add or update configurable semantic vocab routes."""

from __future__ import annotations

TOOL_DESC = "add or update configurable semantic vocab routes."
TOOL_MODE = "mutate"
TOOL_SCOPE = "workspace"
TOOL_POST_OBSERVE = "artifacts"
TOOL_DEFAULT_ARTIFACTS = ["vocab_registry.py"]

import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.chain_registry import public_chain_paths
from tools.tool_registry import public_tool_paths
from vocab_registry import CONFIGURABLE_VOCABS, VocabSpec


CONFIG_START = "# BEGIN CONFIGURABLE_VOCABS"
CONFIG_END = "# END CONFIGURABLE_VOCABS"


def _render_entry(name: str, spec: VocabSpec) -> str:
    q = json.dumps
    lines = [
        f"    {q(name)}: VocabSpec(",
        f"        name={q(spec.name)},",
        f"        category={q(spec.category)},",
        f"        priority={spec.priority},",
    ]
    if spec.deterministic:
        lines.append(f"        deterministic={spec.deterministic!r},")
    if spec.observation_only:
        lines.append(f"        observation_only={spec.observation_only!r},")
    if spec.allows_post_gap_emission is not True:
        lines.append(f"        allows_post_gap_emission={spec.allows_post_gap_emission!r},")
    if spec.tool is not None:
        lines.append(f"        tool={q(spec.tool)},")
    if spec.post_observe is not None:
        lines.append(f"        post_observe={q(spec.post_observe)},")
    lines.append(f"        desc={q(spec.desc)},")
    if spec.target_kind is not None:
        lines.append(f"        target_kind={q(spec.target_kind)},")
    if spec.target_ref is not None:
        lines.append(f"        target_ref={q(spec.target_ref)},")
    if spec.prompt_hint:
        lines.append(f"        prompt_hint={q(spec.prompt_hint)},")
    lines.append("    ),")
    return "\n".join(lines)


def _render_configurable_block(entries: OrderedDict[str, VocabSpec]) -> str:
    body = "\n".join(_render_entry(name, spec) for name, spec in entries.items())
    return (
        f"{CONFIG_START}\n"
        "CONFIGURABLE_VOCABS: dict[str, VocabSpec] = {\n"
        f"{body}\n"
        "}\n"
        f"{CONFIG_END}"
    )


def _replace_configurable_block(source: str, new_block: str) -> str:
    pattern = re.compile(
        rf"{re.escape(CONFIG_START)}.*?{re.escape(CONFIG_END)}",
        re.DOTALL,
    )
    if not pattern.search(source):
        raise ValueError("configurable vocab markers not found in vocab_registry.py")
    return pattern.sub(new_block, source, count=1)


def _default_priority(classifiable: str) -> int:
    return 20 if classifiable == "observe" else 40


def _validate_target(*, target_kind: str, target_ref: str) -> None:
    if target_kind == "tool":
        if target_ref not in public_tool_paths(ROOT):
            raise ValueError(f"target_ref is not a public tool: {target_ref}")
        return
    if target_kind == "chain":
        if target_ref not in public_chain_paths(ROOT):
            raise ValueError(f"target_ref is not a public chain: {target_ref}")
        return
    raise ValueError("target_kind must be 'tool' or 'chain'")


def main() -> None:
    params = json.load(sys.stdin)
    name = str(params.get("name", "")).strip()
    classifiable = str(params.get("classifiable", "")).strip()
    target_kind = str(params.get("target_kind", "")).strip()
    target_ref = str(params.get("target_ref", "")).strip()
    desc = str(params.get("desc", "")).strip()
    prompt_hint = str(params.get("prompt_hint", "")).strip()
    operation = str(params.get("operation", "upsert")).strip() or "upsert"
    priority = int(params.get("priority", _default_priority(classifiable)))
    registry_path = str(params.get("registry_path", "vocab_registry.py")).strip() or "vocab_registry.py"

    if not name:
        print("Error: missing 'name' parameter", file=sys.stderr)
        sys.exit(1)
    if not classifiable:
        print("Error: missing 'classifiable' parameter", file=sys.stderr)
        sys.exit(1)
    if classifiable not in {"observe", "mutate"}:
        print("Error: classifiable must be 'observe' or 'mutate'", file=sys.stderr)
        sys.exit(1)
    if operation not in {"upsert", "delete"}:
        print("Error: operation must be 'upsert' or 'delete'", file=sys.stderr)
        sys.exit(1)

    registry_file = Path(registry_path)
    if not registry_file.is_absolute():
        registry_file = ROOT / registry_file
    if not registry_file.exists():
        print(f"Error: missing registry file: {registry_file}", file=sys.stderr)
        sys.exit(1)

    entries: OrderedDict[str, VocabSpec] = OrderedDict(
        (key, spec) for key, spec in CONFIGURABLE_VOCABS.items()
    )

    if operation == "delete":
        if name not in entries:
            print(f"Error: vocab does not exist: {name}", file=sys.stderr)
            sys.exit(1)
        del entries[name]
    else:
        if not target_kind:
            print("Error: missing 'target_kind' parameter", file=sys.stderr)
            sys.exit(1)
        if not target_ref:
            print("Error: missing 'target_ref' parameter", file=sys.stderr)
            sys.exit(1)
        if not desc:
            print("Error: missing 'desc' parameter", file=sys.stderr)
            sys.exit(1)
        _validate_target(target_kind=target_kind, target_ref=target_ref)
        tool = target_ref if target_kind == "tool" else None
        entries[name] = VocabSpec(
            name=name,
            category=classifiable,
            priority=priority,
            tool=tool,
            desc=desc,
            target_kind=target_kind,
            target_ref=target_ref,
            prompt_hint=prompt_hint,
        )

    source = registry_file.read_text(encoding="utf-8")
    updated = _replace_configurable_block(source, _render_configurable_block(entries))
    registry_file.write_text(updated, encoding="utf-8")
    rel = os.path.relpath(registry_file, ROOT)
    print(f"written: {rel}")


if __name__ == "__main__":
    main()
