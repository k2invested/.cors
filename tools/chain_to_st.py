"""chain_to_st — deterministic extraction of a resolved chain into a .st file.

A fully resolved commitment chain already contains everything a .st file needs:
  - Each step has desc → .st step action/desc
  - Each step has vocab → .st step vocab
  - Each step has relevance → .st step relevance
  - Each step has post_diff → .st step post_diff
  - Each step has content_refs → .st step refs (embeddable .st hashes)
  - The chain has an origin gap desc → .st name/desc
  - The chain has entity refs → .st refs

If the chain-building agents write their commitment chains within the guided
specification (each step as {action, desc, vocab, relevance, post_diff, refs}),
then extraction is pure serialization. No LLM needed.

This is the discovery → crystallization pipeline:
  Commitment chain (semantic tree on trajectory)    ← runtime
    ↓ deterministic extraction
  .st file (JSON in skills/)                         ← crystallized
    ↓ future invocation
  Gaps on ledger (same shape as original chain)      ← re-instantiated

Usage:
  echo '{"chain_hash": "abc123", "name": "my_workflow", "trigger": "manual"}' | python3 tools/chain_to_st.py

Input JSON:
  chain_hash:  hash of the resolved chain to extract
  name:        name for the .st file (required)
  desc:        description (optional — defaults to chain desc)
  trigger:     trigger mode (optional — defaults to "manual")
  refs:        entity refs to include (optional — dict of name:hash)
  output_path: where to write (optional — defaults to skills/{name}.st)

Output: the generated .st file content (JSON)
"""

import json
import sys
from pathlib import Path

CORS_ROOT = Path(__file__).parent.parent
TRAJ_FILE = CORS_ROOT / "trajectory.json"
CHAINS_FILE = CORS_ROOT / "chains.json"


def load_chain_data(chain_hash: str) -> dict | None:
    """Load a chain and its steps from trajectory + chains index."""
    # Load chains index
    try:
        with open(CHAINS_FILE) as f:
            chains = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        chains = []

    # Find chain
    chain = None
    for c in chains:
        if c.get("hash") == chain_hash:
            chain = c
            break

    if not chain:
        return None

    # Load trajectory to get step data
    try:
        with open(TRAJ_FILE) as f:
            traj_steps = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        traj_steps = []

    step_lookup = {s["hash"]: s for s in traj_steps}

    # Also check extracted chain files
    chain_file = CORS_ROOT / "chains" / f"{chain_hash}.json"
    if chain_file.exists():
        try:
            with open(chain_file) as f:
                extracted = json.load(f)
            for s in extracted.get("steps", []):
                step_lookup[s["hash"]] = s
        except (json.JSONDecodeError, KeyError):
            pass

    # Resolve steps in order
    resolved_steps = []
    for step_hash in chain.get("steps", []):
        step = step_lookup.get(step_hash)
        if step:
            resolved_steps.append(step)

    chain["resolved_steps"] = resolved_steps
    return chain


def extract_st_steps(chain_data: dict) -> list[dict]:
    """Extract .st-compatible steps from a resolved chain.

    Each step maps:
      step.desc → st_step.action + st_step.desc
      step.gaps[0].vocab → st_step.vocab
      step.gaps[0].scores.relevance → st_step.relevance (or position-derived)
      step.gaps[0].post_diff (if encoded) → st_step.post_diff
      step.gaps[0].content_refs → embeddable .st hashes
      step.gaps[0].step_refs → causal chain refs

    Steps without gaps (blob steps) become deterministic steps with no vocab.
    """
    st_steps = []
    resolved = chain_data.get("resolved_steps", [])
    total = len(resolved)

    for i, step in enumerate(resolved):
        # Derive action name from desc (first few words, snake_case)
        desc = step.get("desc", "step")
        action = _desc_to_action(desc)

        # Try to extract gap configuration from the step's gaps
        gaps = step.get("gaps", [])
        active_gaps = [g for g in gaps if not g.get("dormant") and not g.get("resolved")]

        if active_gaps:
            gap = active_gaps[0]  # primary gap drives the step config
            st_step = {
                "action": action,
                "desc": desc,
            }

            # Vocab
            vocab = gap.get("vocab")
            if vocab:
                st_step["vocab"] = vocab

            # Relevance: from gap scores or position-derived (1.0 descending)
            scores = gap.get("scores", {})
            relevance = scores.get("relevance", 0.0)
            if relevance > 0:
                st_step["relevance"] = round(relevance, 2)
            else:
                # Position-derived: 1.0 for first step, descending by 0.1
                st_step["relevance"] = round(max(0.1, 1.0 - (i * 0.1)), 2)

            # Post-diff: check if step produced child gaps (branching = true)
            has_children = len(active_gaps) > 1 or any(
                g.get("step_refs") for g in active_gaps
            )
            st_step["post_diff"] = has_children or step.get("commit") is not None

            # Content refs as embeddings
            content_refs = gap.get("content_refs", [])
            if content_refs:
                st_step["content_refs"] = content_refs

        else:
            # Blob step (no active gaps) — deterministic, no branching
            st_step = {
                "action": action,
                "desc": desc,
                "relevance": round(max(0.1, 1.0 - (i * 0.1)), 2),
                "post_diff": False,
            }

            # Include content refs if present
            if step.get("content_refs"):
                st_step["content_refs"] = step["content_refs"]

        st_steps.append(st_step)

    return st_steps


def _desc_to_action(desc: str) -> str:
    """Convert a natural language desc to a snake_case action name."""
    # Take first 4 words, lowercase, join with underscore
    words = desc.lower().split()[:4]
    # Remove non-alphanumeric
    clean = []
    for w in words:
        cleaned = "".join(c for c in w if c.isalnum())
        if cleaned:
            clean.append(cleaned)
    return "_".join(clean) if clean else "step"


def chain_to_st(chain_hash: str, name: str, desc: str = None,
                trigger: str = "manual", refs: dict = None,
                output_path: str = None) -> dict:
    """Extract a resolved chain into a .st file.

    Returns the .st dict. Also writes to output_path if specified.
    """
    chain_data = load_chain_data(chain_hash)
    if not chain_data:
        return {"error": f"chain not found: {chain_hash}"}

    st_steps = extract_st_steps(chain_data)
    if not st_steps:
        return {"error": f"no extractable steps in chain {chain_hash}"}

    # Build .st structure
    st = {
        "name": name,
        "desc": desc or chain_data.get("desc", f"extracted from chain {chain_hash}"),
        "trigger": trigger,
        "author": "chain_extract",
        "source_chain": chain_hash,
    }

    if refs:
        st["refs"] = refs

    st["steps"] = st_steps

    # Write if output path specified
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(st, f, indent=2)
        return {"status": "ok", "path": str(out), "st": st}

    return {"status": "ok", "st": st}


def main():
    """CLI entry point — reads JSON from stdin."""
    try:
        params = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON input: {e}"}))
        sys.exit(1)

    chain_hash = params.get("chain_hash")
    name = params.get("name")

    if not chain_hash or not name:
        print(json.dumps({"error": "chain_hash and name are required"}))
        sys.exit(1)

    result = chain_to_st(
        chain_hash=chain_hash,
        name=name,
        desc=params.get("desc"),
        trigger=params.get("trigger", "manual"),
        refs=params.get("refs"),
        output_path=params.get("output_path"),
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") == "ok" else 1)


if __name__ == "__main__":
    main()
