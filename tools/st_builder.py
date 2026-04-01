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

from vocab import OBSERVE_VOCAB, MUTATE_VOCAB, BRIDGE_VOCAB
from skills.loader import compute_skill_hash

SKILLS_DIR = str(ROOT / "skills")

VALID_RUNTIME_VOCAB = set(OBSERVE_VOCAB) | set(MUTATE_VOCAB) | set(BRIDGE_VOCAB)
VALID_ARTIFACT_KINDS = {"entity", "action_update", "hybrid_update"}


def slugify(text: str) -> str:
    """Turn a description into an action name."""
    words = re.sub(r'[^a-z0-9\s]', '', text.lower()).split()
    return '_'.join(words[:4])


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

    if output_dir and existing_ref and not find_existing_skill_path(existing_ref, output_dir):
        errors.append(f"existing_ref not found: {existing_ref}")

    return errors


def looks_like_skeleton(data: dict) -> bool:
    """Detect skeleton.v1/compiler-style input so it can be routed elsewhere."""
    if data.get("version") == "skeleton.v1":
        return True
    return {"root", "phases", "closure"}.issubset(set(data))


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

    return st


def write_st(st: dict, output_dir: str = None, existing_ref: str | None = None) -> str:
    """Write a .st file and return its path."""
    output_dir = output_dir or SKILLS_DIR
    os.makedirs(output_dir, exist_ok=True)

    existing_path = find_existing_skill_path(existing_ref, output_dir) if existing_ref else None
    if existing_ref and not existing_path:
        raise FileNotFoundError(f"existing_ref not found: {existing_ref}")

    if existing_path:
        path = existing_path
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

    if looks_like_new_action_request(intent):
        print(
            "Error: new action or hybrid workflow origination belongs to skeleton.v1 "
            "compilation, not st_builder."
        )
        raise SystemExit(1)

    artifact_kind = intent.get("artifact_kind", "entity")
    existing_ref = intent.get("existing_ref") or intent.get("existing_action_ref")

    # Build .st from intent
    st = build_st(intent)

    # Validate
    errors = validate_st(st, artifact_kind=artifact_kind, existing_ref=existing_ref, output_dir=SKILLS_DIR)
    if errors:
        print(f"Validation errors:\n" + "\n".join(f"  - {e}" for e in errors))
        print(f"\nGenerated (invalid):\n{json.dumps(st, indent=2)}")
        return

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
