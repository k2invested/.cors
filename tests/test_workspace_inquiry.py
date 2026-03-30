"""
Test: Workspace inquiry — does the system resolve in one step
or does it try to read everything?

The commit already contains the workspace tree. A question like
"what's in the workspace?" should close in a single step without
reading any files. The answer is already in the commit.
"""

import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM = """You are a perception engine. You observe the current state and produce structured steps.

A step has two phases:
- Pre-diff: which hashes from the context you attended to (your perception)
- Post-diff: gaps you identified (what needs to happen next)

If there are NO gaps (the answer is already available in the context), return empty gaps.
Empty gaps means the system will auto-synthesize a response — no further action needed.

You MUST respond with a valid JSON step in this exact format:
{
  "pre": {
    "chain": [{"hash": "<hash you attended to>", "parent": null}]
  },
  "post": {
    "gaps": []
  },
  "content": "<your reasoning about what you observed and why>"
}

Or if gaps exist:
{
  "pre": {
    "chain": [{"hash": "<hash you attended to>", "parent": null}]
  },
  "post": {
    "gaps": [
      {
        "desc": "<what needs to happen>",
        "refs": ["<hash that justifies this gap>"],
        "origin": "<hash where you noticed this>"
      }
    ]
  },
  "content": "<your reasoning about what you observed and why>"
}

Rules:
- Only reference hashes that appear in the context
- If the answer is already fully available in the context, return empty gaps
- Do NOT create gaps for things you can already answer from the context
- Gaps mean "I need external action to resolve this" — not "I notice something"
- Respond ONLY with the JSON, no other text"""


def run_test(name, message):
    context = f"""## Current State

Commit: ws_a1b2c3
Workspace tree:
  config.json    (last modified: 2026-03-28)
  main.py        (last modified: 2026-03-27)
  utils.py       (last modified: 2026-03-25)
  data/
    users.json   (last modified: 2026-03-20)

## Trajectory
(empty — this is the first turn)

## User Message
"{message}"
"""

    print(f"\n{'=' * 60}")
    print(f"TEST: {name}")
    print(f"User: \"{message}\"")
    print(f"{'=' * 60}")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": context},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    print(f"\nRaw output:\n{raw}")

    try:
        step = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\nFAIL: Invalid JSON — {e}")
        return

    pre_hashes = [link["hash"] for link in step.get("pre", {}).get("chain", [])]
    gaps = step.get("post", {}).get("gaps", [])
    content = step.get("content", "")

    print(f"\nPre refs: {pre_hashes}")
    print(f"Gaps: {len(gaps)}")
    for g in gaps:
        print(f"  - {g.get('desc')}")
    print(f"Content: {content[:200]}")

    return gaps


if __name__ == "__main__":
    # Test 1: Simple workspace inquiry — should be zero gaps
    gaps = run_test(
        "Simple workspace inquiry",
        "What files are in the workspace?"
    )
    if gaps is not None:
        print(f"\n→ {'PASS — auto-synth (no gaps)' if len(gaps) == 0 else 'FAIL — produced gaps when answer was in context'}")

    # Test 2: Greeting — should be zero gaps
    gaps = run_test(
        "Simple greeting",
        "Hello!"
    )
    if gaps is not None:
        print(f"\n→ {'PASS — auto-synth (no gaps)' if len(gaps) == 0 else 'FAIL — produced gaps for a greeting'}")

    # Test 3: Needs file content — should produce a gap
    gaps = run_test(
        "Needs file content (should gap)",
        "What's the API base URL in the config?"
    )
    if gaps is not None:
        print(f"\n→ {'PASS — produced gaps (needs to read file)' if len(gaps) > 0 else 'FAIL — no gaps but needs file content'}")

    # Test 4: Workspace structure question — should be zero gaps
    gaps = run_test(
        "Workspace structure",
        "How many files are in the data folder?"
    )
    if gaps is not None:
        print(f"\n→ {'PASS — auto-synth (no gaps)' if len(gaps) == 0 else 'CHECK — might need deeper scan'}")

    # Test 5: Ambiguous "yes" with no trajectory — should be zero gaps
    gaps = run_test(
        "Ambiguous yes (no trajectory)",
        "yes"
    )
    if gaps is not None:
        print(f"\n→ {'PASS — auto-synth (nothing to reference)' if len(gaps) == 0 else 'FAIL — produced gaps from nothing'}")
