"""
Test: Can an LLM produce a well-formed v5 step?

Simulates the first perception loop iteration.
The LLM receives a workspace commit + user message + step schema.
We check if it produces a step with correct hash references and gaps.
"""

import json
import os
import pytest
from openai import OpenAI

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="requires OPENAI_API_KEY",
)


def get_client():
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = """You are a perception engine. You observe the current state and produce structured steps.

A step has two phases:
- Pre-diff: which hashes from the context you attended to (your perception)
- Post-diff: gaps you identified (what needs to happen next)

You MUST respond with a valid JSON step in this exact format:
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
- Only reference hashes that appear in the context below
- Your content should explain your reasoning in natural language
- Gaps should be specific and actionable
- refs in gaps should point to the hashes that justify the gap
- Respond ONLY with the JSON, no other text"""

# Simulate: fresh workspace, initial commit, user message
CONTEXT = """## Current State

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
"The config has the wrong model ID, can you fix it?"
"""

def test_first_step():
    print("=" * 60)
    print("TEST: First step on fresh workspace")
    print("=" * 60)
    print(f"\nContext:\n{CONTEXT}")
    print("-" * 60)

    response = get_client().chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": CONTEXT},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    print(f"\nRaw LLM output:\n{raw}")
    print("-" * 60)

    # Validate structure
    try:
        step = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\nFAIL: Invalid JSON — {e}")
        return

    # Check pre-diff references the commit hash
    pre_hashes = [link["hash"] for link in step.get("pre", {}).get("chain", [])]
    refs_commit = "ws_a1b2c3" in pre_hashes
    print(f"\nPre-diff references commit hash: {'YES' if refs_commit else 'NO'}")
    print(f"  Chain: {pre_hashes}")

    # Check post-diff has gaps
    gaps = step.get("post", {}).get("gaps", [])
    print(f"\nGaps produced: {len(gaps)}")
    for i, gap in enumerate(gaps):
        print(f"  Gap {i+1}: {gap.get('desc', '???')}")
        print(f"    refs: {gap.get('refs', [])}")
        print(f"    origin: {gap.get('origin', None)}")
        gap_refs_commit = "ws_a1b2c3" in gap.get("refs", [])
        print(f"    References commit: {'YES' if gap_refs_commit else 'NO'}")

    # Check content
    content = step.get("content", "")
    print(f"\nContent: {content[:200]}...")

    # Summary
    print("\n" + "=" * 60)
    has_pre = len(pre_hashes) > 0
    has_gaps = len(gaps) > 0
    has_content = len(content) > 10
    gaps_grounded = any("ws_a1b2c3" in g.get("refs", []) for g in gaps)

    print(f"Pre-diff has refs:      {'PASS' if has_pre else 'FAIL'}")
    print(f"Post-diff has gaps:     {'PASS' if has_gaps else 'FAIL'}")
    print(f"Content is meaningful:  {'PASS' if has_content else 'FAIL'}")
    print(f"Gaps reference commit:  {'PASS' if gaps_grounded else 'FAIL'}")
    print(f"Pre refs commit:        {'PASS' if refs_commit else 'FAIL'}")
    all_pass = all([has_pre, has_gaps, has_content, gaps_grounded, refs_commit])
    print(f"\nOverall: {'ALL PASS — architecture validated' if all_pass else 'ISSUES FOUND'}")


def test_second_step():
    """Simulate second iteration — after reading config.json"""
    print("\n\n" + "=" * 60)
    print("TEST: Second step — after observing config.json")
    print("=" * 60)

    context_2 = """## Current State

Commit: ws_a1b2c3
Workspace tree:
  config.json    (last modified: 2026-03-28)
  main.py        (last modified: 2026-03-27)
  utils.py       (last modified: 2026-03-25)
  data/
    users.json   (last modified: 2026-03-20)

## Trajectory

[step_d4e5f6] attending: [ws_a1b2c3]
  "User wants config model ID fixed. Need to read config.json to see current state."
  gaps: [{ desc: "need to read config.json", refs: [ws_a1b2c3] }]

## Observation Result (from reading config.json)

File: config.json (referenced by ws_a1b2c3)
Contents:
{
  "model_id": "gpt-4o-2024-08-06",
  "temperature": 0.7,
  "max_tokens": 4096,
  "api_base": "https://api.openai.com/v1"
}

## User Message
"The config has the wrong model ID, can you fix it?"
"""

    print(f"\nContext:\n{context_2}")
    print("-" * 60)

    response = get_client().chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": context_2},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    print(f"\nRaw LLM output:\n{raw}")
    print("-" * 60)

    try:
        step = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"\nFAIL: Invalid JSON — {e}")
        return

    pre_hashes = [link["hash"] for link in step.get("pre", {}).get("chain", [])]
    print(f"\nPre-diff chain: {pre_hashes}")
    print(f"  References prior step (step_d4e5f6): {'YES' if 'step_d4e5f6' in pre_hashes else 'NO'}")
    print(f"  References commit (ws_a1b2c3): {'YES' if 'ws_a1b2c3' in pre_hashes else 'NO'}")

    gaps = step.get("post", {}).get("gaps", [])
    print(f"\nGaps produced: {len(gaps)}")
    for i, gap in enumerate(gaps):
        print(f"  Gap {i+1}: {gap.get('desc', '???')}")
        print(f"    refs: {gap.get('refs', [])}")

    content = step.get("content", "")
    print(f"\nContent: {content[:300]}...")

    # Check if the LLM identified the specific model ID issue
    mentions_model = "gpt-4o" in content.lower() or "model" in content.lower()
    has_edit_gap = any("edit" in g.get("desc", "").lower() or "fix" in g.get("desc", "").lower() or "update" in g.get("desc", "").lower() for g in gaps)
    chains_prior = "step_d4e5f6" in pre_hashes

    print(f"\n{'=' * 60}")
    print(f"Identifies model ID issue: {'PASS' if mentions_model else 'FAIL'}")
    print(f"Produces edit/fix gap:     {'PASS' if has_edit_gap else 'FAIL'}")
    print(f"Chains to prior step:      {'PASS' if chains_prior else 'FAIL'}")
    all_pass = all([mentions_model, has_edit_gap, chains_prior])
    print(f"\nOverall: {'ALL PASS — chain builds correctly' if all_pass else 'ISSUES FOUND'}")


if __name__ == "__main__":
    test_first_step()
    test_second_step()
