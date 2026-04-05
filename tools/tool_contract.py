"""tool_contract — parse and validate tool metadata for registry derivation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

VALID_MODES = {"observe", "mutate"}
VALID_SCOPES = {"workspace", "external"}
VALID_POST_OBSERVE = {"none", "log", "artifacts"}


@dataclass(frozen=True)
class ToolContract:
    desc: str
    mode: str
    scope: str
    post_observe: str
    default_artifacts: tuple[str, ...] = ()
    runtime_artifacts: bool = False


def _literal_assignments(path: Path) -> dict[str, object]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    values: dict[str, object] = {}
    for node in module.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                continue
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            try:
                values[node.target.id] = ast.literal_eval(node.value)
            except Exception:
                continue
    doc = ast.get_docstring(module) or ""
    values["__doc_first_line__"] = doc.strip().splitlines()[0] if doc.strip() else ""
    return values


def validate_contract_fields(values: dict[str, object]) -> list[str]:
    errors: list[str] = []
    desc = values.get("TOOL_DESC")
    mode = values.get("TOOL_MODE")
    scope = values.get("TOOL_SCOPE")
    post_observe = values.get("TOOL_POST_OBSERVE")
    default_artifacts = values.get("TOOL_DEFAULT_ARTIFACTS", [])
    runtime_artifacts = bool(values.get("TOOL_RUNTIME_ARTIFACTS", False))

    if not values.get("__doc_first_line__"):
        errors.append("missing module docstring summary")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("TOOL_DESC must be a non-empty string")
    if mode not in VALID_MODES:
        errors.append(f"TOOL_MODE must be one of {sorted(VALID_MODES)}")
    if scope not in VALID_SCOPES:
        errors.append(f"TOOL_SCOPE must be one of {sorted(VALID_SCOPES)}")
    if post_observe not in VALID_POST_OBSERVE:
        errors.append(f"TOOL_POST_OBSERVE must be one of {sorted(VALID_POST_OBSERVE)}")
    if errors:
        return errors

    if mode == "observe":
        if post_observe != "none":
            errors.append("observe tools must use TOOL_POST_OBSERVE = 'none'")
        if default_artifacts:
            errors.append("observe tools cannot declare TOOL_DEFAULT_ARTIFACTS")
        if runtime_artifacts:
            errors.append("observe tools cannot declare TOOL_RUNTIME_ARTIFACTS")
        return errors

    if scope == "workspace" and post_observe != "artifacts":
        errors.append("workspace mutate tools must use TOOL_POST_OBSERVE = 'artifacts'")
    if post_observe == "none":
        errors.append("mutate tools must not use TOOL_POST_OBSERVE = 'none'")
    if post_observe == "log":
        if default_artifacts:
            errors.append("log post-observe tools cannot declare TOOL_DEFAULT_ARTIFACTS")
        if runtime_artifacts:
            errors.append("log post-observe tools cannot declare TOOL_RUNTIME_ARTIFACTS")
    if post_observe == "artifacts":
        valid_defaults = isinstance(default_artifacts, list) and all(isinstance(item, str) and item for item in default_artifacts)
        if not valid_defaults and not runtime_artifacts:
            errors.append("artifact post-observe tools must declare TOOL_DEFAULT_ARTIFACTS or TOOL_RUNTIME_ARTIFACTS = True")

    return errors


def load_tool_contract(path: str | Path) -> ToolContract | None:
    tool_path = Path(path)
    if not tool_path.exists():
        return None
    values = _literal_assignments(tool_path)
    errors = validate_contract_fields(values)
    if errors:
        return None
    return ToolContract(
        desc=str(values["TOOL_DESC"]).strip(),
        mode=str(values["TOOL_MODE"]),
        scope=str(values["TOOL_SCOPE"]),
        post_observe=str(values["TOOL_POST_OBSERVE"]),
        default_artifacts=tuple(values.get("TOOL_DEFAULT_ARTIFACTS", []) or []),
        runtime_artifacts=bool(values.get("TOOL_RUNTIME_ARTIFACTS", False)),
    )


def validate_tool_file(path: str | Path) -> list[str]:
    tool_path = Path(path)
    if not tool_path.exists():
        return [f"missing tool file: {tool_path}"]
    try:
        values = _literal_assignments(tool_path)
    except SyntaxError as e:
        return [f"invalid python syntax: {e.msg}"]
    return validate_contract_fields(values)
