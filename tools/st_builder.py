#!/usr/bin/env python3
"""st_builder — build .st step files from semantic intent.

The agent describes what it wants in natural language.
The builder handles structure, format, and validation.

Input (stdin JSON):
{
  "name": "task name",
  "desc": "what this task/skill does",
  "trigger": "manual | on_contact:X | on_vocab:X | every_turn | on_mention",
  "author": "agent | developer",
  "refs": {
    "target_file": "blob_abc123",
    "prior_work": "chain_def456"
  },
  "actions": [
    {
      "do": "read the current config file",
      "refs": ["blob_abc123"],
      "observe": true
    },
    {
      "do": "update model_id to claude-sonnet-4-6",
      "refs": ["blob_abc123"],
      "mutate": true
    },
    {
      "do": "verify the edit landed correctly",
      "refs": [],
      "observe": true
    }
  ]
}

The builder:
  - Generates action names from descriptions
  - Maps observe/mutate to post_diff and infers vocab
  - Preserves hash refs on each step
  - Validates schema
  - Writes the .st file

Output: path to the written .st file, or error message.
"""

import json
import os
import re
import sys
from pathlib import Path

SKILLS_DIR = str(Path(__file__).resolve().parent.parent / "skills")

# ── Vocab inference from action description ──────────────────────────────

OBSERVE_PATTERNS = {
    r"read|scan|check|look|inspect|verify|view|see|resolve": "scan_needed",
    r"search|research|find|discover|investigate|look.?up": "research_needed",
    r"trace|follow|recall|remember|history|prior": "hash_resolve_needed",
    r"grep|pattern|find.?in|search.?for|locate": "pattern_needed",
    r"email|inbox|mail": "email_needed",
    r"url|fetch|download|http": "url_needed",
}

MUTATE_PATTERNS = {
    r"write|create|produce|generate|new.?file": "content_needed",
    r"edit|update|change|modify|fix|patch|replace": "script_edit_needed",
    r"run|execute|command|build|test|deploy|install": "command_needed",
    r"send|email|notify|message|alert": "message_needed",
    r"revert|undo|rollback|restore": "git_revert_needed",
}


def infer_vocab(desc: str, is_mutate: bool) -> str | None:
    """Infer vocab from action description."""
    desc_lower = desc.lower()
    patterns = MUTATE_PATTERNS if is_mutate else OBSERVE_PATTERNS
    for pattern, vocab in patterns.items():
        if re.search(pattern, desc_lower):
            return vocab
    # Fallback
    if is_mutate:
        return "command_needed"
    return "scan_needed"


def slugify(text: str) -> str:
    """Turn a description into an action name."""
    words = re.sub(r'[^a-z0-9\s]', '', text.lower()).split()
    return '_'.join(words[:4])


# ── Schema validation ────────────────────────────────────────────────────

VALID_TRIGGERS = {"manual", "every_turn", "on_mention"}
VALID_TRIGGER_PREFIXES = {"on_contact:", "on_vocab:", "scheduled:", "command:"}

REQUIRED_STEP_FIELDS = {"action", "desc"}


def validate_st(data: dict) -> list[str]:
    """Validate a .st structure. Returns list of errors (empty = valid)."""
    errors = []

    if "name" not in data:
        errors.append("missing 'name'")
    if "desc" not in data:
        errors.append("missing 'desc'")
    if "steps" not in data:
        errors.append("missing 'steps'")
    elif not isinstance(data["steps"], list):
        errors.append("'steps' must be a list")
    elif len(data["steps"]) == 0:
        errors.append("'steps' must have at least one step")
    else:
        for i, step in enumerate(data["steps"]):
            for field in REQUIRED_STEP_FIELDS:
                if field not in step:
                    errors.append(f"step {i}: missing '{field}'")

    trigger = data.get("trigger", "manual")
    if trigger not in VALID_TRIGGERS:
        if not any(trigger.startswith(p) for p in VALID_TRIGGER_PREFIXES):
            errors.append(f"invalid trigger: {trigger}")

    return errors


# ── Builder ──────────────────────────────────────────────────────────────

def build_st(intent: dict) -> dict:
    """Build a valid .st structure from semantic intent."""

    name = intent.get("name", "untitled")
    desc = intent.get("desc", "")
    trigger = intent.get("trigger", "manual")
    author = intent.get("author", "agent")
    refs = intent.get("refs", {})
    actions = intent.get("actions", [])

    steps = []
    for action in actions:
        do_desc = action.get("do", "")
        is_mutate = action.get("mutate", False)
        is_observe = action.get("observe", not is_mutate)
        action_refs = action.get("refs", [])
        condition = action.get("condition", None)

        step = {
            "action": slugify(do_desc),
            "desc": do_desc,
            "vocab": infer_vocab(do_desc, is_mutate),
            "post_diff": is_observe,
        }

        if action_refs:
            step["resolve"] = action_refs

        if condition:
            step["condition"] = condition

        steps.append(step)

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
    BASE_FIELDS = {"name", "desc", "trigger", "author", "refs", "actions"}
    for key, value in intent.items():
        if key not in BASE_FIELDS:
            st[key] = value

    return st


def write_st(st: dict, output_dir: str = None) -> str:
    """Write a .st file and return its path."""
    output_dir = output_dir or SKILLS_DIR
    os.makedirs(output_dir, exist_ok=True)

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

    # Build .st from intent
    st = build_st(intent)

    # Validate
    errors = validate_st(st)
    if errors:
        print(f"Validation errors:\n" + "\n".join(f"  - {e}" for e in errors))
        print(f"\nGenerated (invalid):\n{json.dumps(st, indent=2)}")
        return

    # Write
    path = write_st(st)

    # Report
    print(f"Written: {path}")
    print(f"Name: {st['name']}")
    print(f"Steps: {len(st['steps'])}")
    print(f"Trigger: {st['trigger']}")
    for i, step in enumerate(st["steps"]):
        mode = "observe" if step.get("post_diff", True) else "execute"
        vocab = step.get("vocab", "—")
        refs = step.get("resolve", [])
        ref_tag = f" refs:{refs}" if refs else ""
        print(f"  {i+1}. [{mode}] {step['desc'][:60]} → {vocab}{ref_tag}")


if __name__ == "__main__":
    main()
