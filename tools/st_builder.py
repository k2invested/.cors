#!/usr/bin/env python3
"""st_builder — curate semantic `.st` files for reprogramme.

This tool is no longer a general workflow builder. It is the semantic
curation path for:
  - new or updated entity `.st` files
  - updates to existing executable `.st` packages

It is NOT the deterministic compiler for `skeleton.v1`. New action
structure belongs to `tools/skeleton_compile.py`.

The builder preserves explicit semantic structure and explicit step
configuration. It does not infer workflow vocab from natural language.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compile import OBSERVE_VOCAB, MUTATE_VOCAB, BRIDGE_VOCAB
from skills.loader import compute_skill_hash

SKILLS_DIR = str(ROOT / "skills")

VALID_RUNTIME_VOCAB = set(OBSERVE_VOCAB) | set(MUTATE_VOCAB) | set(BRIDGE_VOCAB)
VALID_ARTIFACT_KINDS = {"entity", "action_update", "hybrid_update"}
SEMANTIC_FIELDS = {
    "identity",
    "preferences",
    "constraints",
    "sources",
    "scope",
    "schema",
    "access_rules",
    "principles",
    "boundaries",
    "domain_knowledge",
    "entity_refs",
    "init",
}
HEX_REF_RE = re.compile(r"^[0-9a-f]{12}$")
PRESERVED_MERGE_FIELDS = {
    *SEMANTIC_FIELDS,
    "reasoning",
}
ENTITY_STEP_FIELDS = [
    "identity",
    "preferences",
    "constraints",
    "sources",
    "scope",
    "schema",
    "access_rules",
    "principles",
    "boundaries",
    "domain_knowledge",
    "entity_refs",
    "init",
]


def slugify(text: str) -> str:
    """Turn a description into an action name."""
    words = re.sub(r'[^a-z0-9\s]', '', text.lower()).split()
    return '_'.join(words[:4])


def normalize_existing_ref(existing_ref: str | None) -> str | None:
    if not isinstance(existing_ref, str):
        return None
    candidate = existing_ref.strip()
    if not candidate:
        return None
    if HEX_REF_RE.fullmatch(candidate):
        return candidate
    if ":" in candidate:
        suffix = candidate.rsplit(":", 1)[1].strip()
        if HEX_REF_RE.fullmatch(suffix):
            return suffix
    return candidate


def _deep_merge_dict(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge_dict(base[key], value)
        else:
            merged[key] = value
    return merged


def default_entity_steps(data: dict) -> list[dict]:
    steps: list[dict] = []
    name = data.get("name", "entity")
    for field in ENTITY_STEP_FIELDS:
        if field not in data:
            continue
        value = data.get(field)
        if value in ({}, [], "", None):
            continue
        steps.append(
            {
                "action": f"load_{field}",
                "desc": f"surface {field} context for {name}",
                "resolve": [field],
                "post_diff": False,
            }
        )
    return steps


def has_entity_semantics(data: dict) -> bool:
    return any(
        field in data and data.get(field) not in ({}, [], "", None)
        for field in ENTITY_STEP_FIELDS
    )


# ── Schema validation ────────────────────────────────────────────────────

VALID_TRIGGERS = {"manual", "every_turn", "on_mention"}
VALID_TRIGGER_PREFIXES = {"on_contact:", "on_vocab:", "scheduled:", "command:"}

REQUIRED_STEP_FIELDS = {"action", "desc"}


def validate_st(data: dict,
                artifact_kind: str = "entity",
                existing_ref: str | None = None,
                output_dir: str | None = None) -> list[str]:
    """Validate a .st structure. Returns list of errors (empty = valid)."""
    errors = []
    existing_ref = normalize_existing_ref(existing_ref)

    if "name" not in data:
        errors.append("missing 'name'")
    if "desc" not in data:
        errors.append("missing 'desc'")
    if "steps" not in data:
        data["steps"] = []  # pure entity — no workflow steps
    elif not isinstance(data["steps"], list):
        errors.append("'steps' must be a list")
    else:
        for i, step in enumerate(data["steps"]):
            for field in REQUIRED_STEP_FIELDS:
                if field not in step:
                    errors.append(f"step {i}: missing '{field}'")
            vocab = step.get("vocab")
            if vocab is not None and vocab not in VALID_RUNTIME_VOCAB:
                errors.append(f"step {i}: invalid runtime vocab '{vocab}'")
            if "post_diff" in step and not isinstance(step["post_diff"], bool):
                errors.append(f"step {i}: 'post_diff' must be true or false")
            if "resolve" in step and not isinstance(step["resolve"], list):
                errors.append(f"step {i}: 'resolve' must be a list")

    trigger = data.get("trigger", "manual")
    if trigger not in VALID_TRIGGERS:
        if not any(trigger.startswith(p) for p in VALID_TRIGGER_PREFIXES):
            errors.append(f"invalid trigger: {trigger}")

    if artifact_kind not in VALID_ARTIFACT_KINDS:
        errors.append(f"invalid artifact_kind: {artifact_kind}")

    if artifact_kind in {"action_update", "hybrid_update"} and not existing_ref:
        errors.append(f"{artifact_kind} requires 'existing_ref' or 'existing_action_ref'")

    if artifact_kind == "entity" and has_entity_semantics(data) and not data.get("steps"):
        errors.append("entity packages with semantic content require deterministic context-injection steps")

    if output_dir and existing_ref and not find_existing_skill_path(existing_ref, output_dir):
        errors.append(f"existing_ref not found: {existing_ref}")

    return errors


def looks_like_skeleton(data: dict) -> bool:
    """Detect skeleton.v1/compiler-style input so it can be routed elsewhere."""
    if data.get("version") == "skeleton.v1":
        return True
    return {"root", "phases", "closure"}.issubset(set(data))


def looks_like_semantic_skeleton(data: dict) -> bool:
    return data.get("version") == "semantic_skeleton.v1" and isinstance(data.get("artifact"), dict)


def looks_like_new_action_request(data: dict) -> bool:
    artifact_kind = data.get("artifact_kind")
    if artifact_kind in {"action", "hybrid"}:
        return True
    return False


def normalize_step(raw_step: dict) -> dict:
    """Normalize one step without inventing workflow semantics."""
    desc = raw_step.get("desc") or raw_step.get("do", "")
    step = {
        "action": raw_step.get("action") or slugify(desc or "step"),
        "desc": desc,
    }

    if "vocab" in raw_step:
        step["vocab"] = raw_step["vocab"]

    if "post_diff" in raw_step:
        step["post_diff"] = raw_step["post_diff"]
    elif raw_step.get("mutate", False):
        step["post_diff"] = False
    elif raw_step.get("observe", False):
        step["post_diff"] = True

    refs = raw_step.get("resolve")
    if refs is None:
        refs = raw_step.get("refs")
    if refs:
        step["resolve"] = refs

    if "condition" in raw_step:
        step["condition"] = raw_step["condition"]

    if "inject" in raw_step:
        step["inject"] = raw_step["inject"]

    return step


def normalize_steps(intent: dict) -> list[dict]:
    if "steps" in intent:
        return [normalize_step(step) for step in intent.get("steps", [])]
    return [normalize_step(action) for action in intent.get("actions", [])]


def _flow_phase_id(action: str, index: int) -> str:
    ident = re.sub(r"[^a-z0-9_]+", "_", action.lower()).strip("_") or f"step_{index + 1}"
    return f"phase_{ident}_{index + 1}"


def _default_generation(kind: str, post_diff: bool) -> dict:
    if kind == "mutate":
        spawn_mode = "action" if post_diff else "none"
        spawn_trigger = "on_post_diff" if post_diff else "none"
    elif kind in {"reason", "higher_order", "await"}:
        spawn_mode = "mixed" if post_diff else "none"
        spawn_trigger = "conditional" if post_diff else "none"
    else:
        spawn_mode = "none"
        spawn_trigger = "none"
    return {
        "spawn_mode": spawn_mode,
        "spawn_trigger": spawn_trigger,
        "branch_policy": "depth_first_to_parent",
        "sibling_policy": "after_descendants",
        "return_policy": "resume_transition",
    }


def _phase_kind_for_step(step: dict) -> str:
    vocab = step.get("vocab")
    refs = step.get("resolve", []) or []
    if vocab == "clarify_needed":
        return "clarify"
    if vocab == "reason_needed":
        return "reason"
    if vocab == "await_needed":
        return "await"
    if vocab in {"commit_needed", "reprogramme_needed"}:
        return "higher_order"
    if vocab in MUTATE_VOCAB:
        return "mutate"
    if vocab in OBSERVE_VOCAB:
        return "observe"
    if refs:
        return "observe"
    return "higher_order"


def _manifestation_for_phase(kind: str, step: dict) -> dict:
    vocab = step.get("vocab")
    if kind == "clarify":
        return {
            "kernel_class": "clarify",
            "dispersal": "context",
            "execution_mode": "runtime_vocab",
            "runtime_vocab": "clarify_needed",
        }
    if vocab:
        if kind in {"observe", "verify"}:
            kernel_class = "observe"
            dispersal = "context"
        elif kind == "mutate":
            kernel_class = "mutate"
            dispersal = "action"
        else:
            kernel_class = "bridge"
            dispersal = "mixed"
        return {
            "kernel_class": kernel_class,
            "dispersal": dispersal,
            "execution_mode": "runtime_vocab",
            "runtime_vocab": vocab,
        }
    if kind in {"observe", "verify"}:
        return {
            "kernel_class": "observe",
            "dispersal": "context",
            "execution_mode": "inline",
        }
    return {
        "kernel_class": "bridge",
        "dispersal": "mixed",
        "execution_mode": "inline",
    }


def _allowed_vocab_for_phase(kind: str, step: dict) -> list[str]:
    vocab = step.get("vocab")
    if vocab:
        return [vocab]
    if kind == "clarify":
        return ["clarify_needed"]
    if kind == "await":
        return ["await_needed"]
    if kind in {"observe", "verify"}:
        return ["hash_resolve_needed"]
    return ["reason_needed"]


def _step_to_phase(step: dict, index: int, total: int) -> dict:
    action = step.get("action") or slugify(step.get("desc", "") or f"step {index + 1}")
    kind = _phase_kind_for_step(step)
    desc = step.get("desc", action)
    phase = {
        "id": _flow_phase_id(action, index),
        "kind": kind,
        "goal": desc,
        "action": action,
        "gap_template": {
            "desc": desc,
            "content_refs": list(step.get("resolve", []) or []),
            "step_refs": [],
        },
        "manifestation": _manifestation_for_phase(kind, step),
        "generation": _default_generation(kind, bool(step.get("post_diff", False))),
        "allowed_vocab": _allowed_vocab_for_phase(kind, step),
        "post_diff": bool(step.get("post_diff", False)),
    }
    if "inject" in step:
        phase["inject"] = step["inject"]
    if kind == "clarify":
        phase["terminal"] = True
        return phase
    return phase


def _default_closure() -> dict:
    return {
        "success": {
            "requires_terminal": "phase_done",
            "requires_no_active_gaps": True,
        },
        "failure": {
            "allow_force_close": True,
            "allow_clarify_terminal": True,
        },
        "limits": {
            "max_chain_depth": 15,
            "max_redirects": 4,
        },
    }


def _build_flow_from_steps(steps: list[dict]) -> tuple[str, list[dict], dict] | tuple[None, list, None]:
    if not steps:
        return None, [], None
    phases = [_step_to_phase(step, idx, len(steps)) for idx, step in enumerate(steps)]
    for idx, phase in enumerate(phases):
        if phase.get("kind") == "clarify":
            continue
        if idx < len(phases) - 1:
            phase["transitions"] = {"on_done": phases[idx + 1]["id"]}
        else:
            phase["transitions"] = {"on_close": "phase_done"}
    phases.append(
        {
            "id": "phase_done",
            "kind": "terminal",
            "goal": "done",
            "action": "close_loop",
            "terminal": True,
        }
    )
    return phases[0]["id"], phases, _default_closure()


def _resolve_symbolic_ref(ref: str, refs: dict[str, str]) -> str | None:
    if ref.startswith("@"):
        return refs.get(ref[1:], ref)
    if ref.startswith("$"):
        return None
    return ref


def _phase_to_step(phase: dict, refs: dict[str, str]) -> dict | None:
    if phase.get("kind") == "terminal":
        return None
    step = {
        "action": phase.get("action") or slugify(phase.get("goal", "")),
        "desc": phase.get("gap_template", {}).get("desc") or phase.get("goal", ""),
    }
    manifestation = phase.get("manifestation", {}) or {}
    if manifestation.get("execution_mode") == "runtime_vocab" and manifestation.get("runtime_vocab"):
        step["vocab"] = manifestation["runtime_vocab"]
    if "post_diff" in phase:
        step["post_diff"] = phase["post_diff"]
    refs_list = [
        resolved
        for ref in phase.get("gap_template", {}).get("content_refs", []) or []
        for resolved in [_resolve_symbolic_ref(ref, refs)]
        if resolved
    ]
    if refs_list:
        step["resolve"] = refs_list
    if "inject" in phase:
        step["inject"] = phase["inject"]
    return step


def _semantics_from_st(data: dict) -> dict:
    semantics = {}
    for field in SEMANTIC_FIELDS:
        if field in data:
            semantics[field] = data[field]
    return semantics


def _artifact_kind_from_st(data: dict) -> str:
    if isinstance(data.get("artifact"), dict) and data["artifact"].get("kind") in {"entity", "action", "hybrid"}:
        return data["artifact"]["kind"]
    has_flow = bool(data.get("root") and data.get("phases") and data.get("closure")) or bool(data.get("steps"))
    has_semantics = bool(_semantics_from_st(data))
    if has_flow and has_semantics:
        return "hybrid"
    if has_flow:
        return "action"
    return "entity"


def semantic_skeleton_from_st(
    data: dict,
    *,
    existing_ref: str | None = None,
) -> dict:
    artifact_kind = _artifact_kind_from_st(data)
    artifact = dict(data.get("artifact", {}))
    artifact.setdefault("kind", artifact_kind)
    artifact.setdefault("protected_kind", "entity" if artifact_kind == "entity" else "action")
    artifact.setdefault("lineage", data.get("name", "untitled"))
    artifact.setdefault("version_strategy", "hash_pinned")

    doc = {
        "version": "semantic_skeleton.v1",
        "artifact": artifact,
        "name": data.get("name", "untitled"),
        "desc": data.get("desc", ""),
        "trigger": data.get("trigger", "manual"),
        "refs": dict(data.get("refs", {})),
    }
    if existing_ref:
        doc["existing_ref"] = existing_ref

    semantics = _semantics_from_st(data)
    if semantics or artifact_kind == "entity":
        doc["semantics"] = semantics

    root = data.get("root")
    phases = data.get("phases")
    closure = data.get("closure")
    if root and isinstance(phases, list) and isinstance(closure, dict):
        doc["root"] = root
        doc["phases"] = phases
        doc["closure"] = closure
    elif data.get("steps"):
        root, phases, closure = _build_flow_from_steps(normalize_steps({"steps": data.get("steps", [])}))
        if root and phases and closure:
            doc["root"] = root
            doc["phases"] = phases
            doc["closure"] = closure

    return doc


def blank_semantic_skeleton(
    *,
    name: str = "entity_name",
    desc: str = "what this semantic package is",
    trigger: str = "manual",
    artifact_kind: str = "entity",
) -> dict:
    doc = {
        "version": "semantic_skeleton.v1",
        "artifact": {
            "kind": artifact_kind,
            "protected_kind": "entity" if artifact_kind == "entity" else "action",
            "lineage": name,
            "version_strategy": "hash_pinned",
        },
        "name": name,
        "desc": desc,
        "trigger": trigger,
        "refs": {},
        "semantics": {},
    }
    if artifact_kind in {"action", "hybrid"}:
        doc["root"] = "phase_root"
        doc["phases"] = []
        doc["closure"] = _default_closure()
    return doc


def lower_semantic_skeleton(intent: dict) -> tuple[dict, str, str | None]:
    artifact = dict(intent.get("artifact", {}))
    artifact_kind = artifact.get("kind", "entity")
    existing_ref = normalize_existing_ref(intent.get("existing_ref"))

    if artifact_kind == "entity":
        lowered_kind = "entity"
    elif artifact_kind == "action":
        lowered_kind = "action_update"
    else:
        lowered_kind = "hybrid_update"

    st: dict = {
        "name": intent.get("name", "untitled"),
        "desc": intent.get("desc", ""),
        "trigger": intent.get("trigger", "manual"),
        "refs": dict(intent.get("refs", {})),
        "artifact": artifact,
    }
    semantics = dict(intent.get("semantics", {}))
    for field, value in semantics.items():
        st[field] = value

    root = intent.get("root")
    phases = intent.get("phases")
    closure = intent.get("closure")
    if root is not None:
        st["root"] = root
    if phases is not None:
        st["phases"] = phases
        st["steps"] = [step for phase in phases if (step := _phase_to_step(phase, st["refs"])) is not None]
    else:
        st["steps"] = []
    if closure is not None:
        st["closure"] = closure
    if artifact_kind == "entity" and not st["steps"]:
        st["steps"] = default_entity_steps(st)

    return st, lowered_kind, existing_ref


def find_existing_skill_path(existing_ref: str, output_dir: str) -> str | None:
    output_root = Path(output_dir)
    if not output_root.exists():
        return None
    for path in output_root.rglob("*.st"):
        try:
            raw = path.read_text()
        except OSError:
            continue
        if compute_skill_hash(raw) == existing_ref:
            return str(path)
    return None


def find_existing_contact_path(trigger: str, output_dir: str) -> str | None:
    output_root = Path(output_dir)
    if not output_root.exists():
        return None

    matches: list[tuple[int, int, str]] = []
    for path in output_root.rglob("*.st"):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("trigger") != trigger:
            continue
        steps = data.get("steps", [])
        name = str(data.get("name", "")).lower()
        matches.append((
            len(steps) if isinstance(steps, list) else 0,
            1 if name == "admin" else 0,
            str(path),
        ))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][2]


# ── Builder ──────────────────────────────────────────────────────────────

def build_st(intent: dict) -> dict:
    """Build a valid `.st` structure from semantic intent."""

    name = intent.get("name", "untitled")
    desc = intent.get("desc", "")
    trigger = intent.get("trigger", "manual")
    author = intent.get("author", "agent")
    refs = intent.get("refs", {})
    steps = normalize_steps(intent)

    st = {
        "name": name,
        "desc": desc,
        "trigger": trigger,
        "author": author,
        "refs": refs,
        "steps": steps,
    }

    # Forward all non-base fields from intent — these are the manifestation config.
    # What's present shapes how the entity manifests:
    #   identity + preferences → person
    #   constraints + sources + scope → compliance/regulation domain
    #   schema + access_rules → business database
    #   principles + boundaries → domain expertise
    # The fields don't explain — they distinguish.
    BASE_FIELDS = {
        "name", "desc", "trigger", "author", "refs",
        "actions", "steps", "artifact_kind", "existing_ref", "existing_action_ref",
    }
    for key, value in intent.items():
        if key not in BASE_FIELDS:
            st[key] = value

    if intent.get("artifact_kind", "entity") == "entity" and not st["steps"]:
        st["steps"] = default_entity_steps(st)

    return st


def write_st(st: dict, output_dir: str = None, existing_ref: str | None = None) -> str:
    """Write a .st file and return its path."""
    output_dir = output_dir or SKILLS_DIR
    os.makedirs(output_dir, exist_ok=True)
    existing_ref = normalize_existing_ref(existing_ref)

    existing_path = find_existing_skill_path(existing_ref, output_dir) if existing_ref else None
    if existing_ref and not existing_path:
        raise FileNotFoundError(f"existing_ref not found: {existing_ref}")
    if not existing_path:
        trigger = st.get("trigger", "")
        if isinstance(trigger, str) and trigger.startswith("on_contact:"):
            existing_path = find_existing_contact_path(trigger, output_dir)

    if existing_path:
        path = existing_path
        try:
            existing_data = json.loads(Path(existing_path).read_text())
        except (OSError, json.JSONDecodeError):
            existing_data = {}
        is_canonical_admin = Path(existing_path).name == "admin.st" or existing_data.get("name") == "admin"

        if isinstance(existing_data.get("steps"), list) and existing_data.get("steps") and (is_canonical_admin or not st.get("steps")):
            st["steps"] = existing_data["steps"]
        if isinstance(existing_data.get("refs"), dict):
            merged_refs = dict(existing_data.get("refs", {}))
            merged_refs.update(st.get("refs", {}) or {})
            st["refs"] = merged_refs
        for key in ("artifact", "root", "phases", "closure"):
            if key in existing_data and key not in st:
                st[key] = existing_data[key]
        for key in PRESERVED_MERGE_FIELDS:
            if key in existing_data and key in st and isinstance(existing_data[key], dict) and isinstance(st[key], dict):
                st[key] = _deep_merge_dict(existing_data[key], st[key])
            elif key in existing_data and key not in st:
                st[key] = existing_data[key]
        if is_canonical_admin:
            st["name"] = "admin"
            if "trigger" in existing_data:
                st["trigger"] = existing_data["trigger"]
            if "desc" in existing_data:
                st["desc"] = existing_data["desc"]
    else:
        name = st.get("name", "untitled")
        filename = re.sub(r'[^a-z0-9_]', '_', name.lower()) + ".st"
        path = os.path.join(output_dir, filename)

    with open(path, "w") as f:
        json.dump(st, f, indent=2)

    return path


# ── Main (tool interface) ────────────────────────────────────────────────

def main():
    """Read intent from stdin, build .st, validate, write."""
    try:
        intent = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON input — {e}")
        return

    if looks_like_skeleton(intent):
        print(
            "Error: skeleton.v1 input should be compiled with tools/skeleton_compile.py, "
            "not built through st_builder."
        )
        raise SystemExit(1)

    if looks_like_semantic_skeleton(intent):
        st, artifact_kind, existing_ref = lower_semantic_skeleton(intent)
    else:
        if looks_like_new_action_request(intent):
            print(
                "Error: new action or hybrid workflow origination belongs to skeleton.v1 "
                "compilation, not st_builder."
            )
            raise SystemExit(1)

        artifact_kind = intent.get("artifact_kind", "entity")
        existing_ref = normalize_existing_ref(intent.get("existing_ref") or intent.get("existing_action_ref"))

        # Build .st from intent
        st = build_st(intent)

    # Validate
    errors = validate_st(st, artifact_kind=artifact_kind, existing_ref=existing_ref, output_dir=SKILLS_DIR)
    if errors:
        print(f"Validation errors:\n" + "\n".join(f"  - {e}" for e in errors))
        print(f"\nGenerated (invalid):\n{json.dumps(st, indent=2)}")
        raise SystemExit(1)

    # Write
    path = write_st(st, existing_ref=existing_ref)

    # Report
    print(f"Written: {path}")
    print(f"Name: {st['name']}")
    print(f"Artifact kind: {artifact_kind}")
    print(f"Steps: {len(st['steps'])}")
    print(f"Trigger: {st['trigger']}")
    for i, step in enumerate(st["steps"]):
        mode = "flexible" if step.get("post_diff", True) else "deterministic"
        vocab = step.get("vocab", "—")
        refs = step.get("resolve", [])
        ref_tag = f" refs:{refs}" if refs else ""
        print(f"  {i+1}. [{mode}] {step['desc'][:60]} → {vocab}{ref_tag}")


if __name__ == "__main__":
    main()
