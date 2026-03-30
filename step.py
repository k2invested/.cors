"""Step — the single primitive.

A step is meaningful movement. Two-phase transition:

  Phase 1 — Pre-diff (perception):
    LLM follows step hashes through trajectory, articulates each chain,
    references blobs/trees/commits as content hashes. Produces gap
    articulations grounded in referred context.

  Phase 2 — Post-diff (gap scoring):
    LLM scores each gap against system vocab. Governor routes by
    popping the stack. Kernel resolves hash data. OMO rhythm enforces
    observe-mutate-observe.

Two hash layers (never mixed):
  Layer 1 — Step hashes:   reasoning trajectory. Steps reference steps.
  Layer 2 — Content hashes: blobs, trees, commits. Gaps reference content.

Storage:
  Atomic steps:       trajectory.json (accumulated, sequential)
  Predefined steps:   skills/*.st (authored, hash-addressed)
  Extracted chains:   chains/*.json (long chains promoted from trajectory)
  Content:            .git/ (blobs, trees, commits — resolved on demand)

The trajectory is a closed hash graph. Raw data never touches it.
Only hash references and semantic descriptions.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional


# ── Hash computation ──────────────────────────────────────────────────────

def blob_hash(content: str) -> str:
    """Content-addressed hash. 12-char hex from SHA-256."""
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def chain_hash(step_hashes: list[str]) -> str:
    """Hash a sequence of step hashes into a chain hash."""
    combined = ":".join(step_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


# ── Epistemic ─────────────────────────────────────────────────────────────

@dataclass
class Epistemic:
    """Epistemic signal — derived from chain structure by the governor."""
    relevance:  float = 0.0   # hash co-occurrence frequency
    confidence: float = 0.0   # chain depth + convergence
    grounded:   float = 0.0   # commit-anchored chain termination

    def as_vector(self) -> list[float]:
        return [self.relevance, self.confidence, self.grounded]

    def distance_to(self, other: "Epistemic") -> float:
        """Euclidean distance between two epistemic states."""
        return sum((a - b) ** 2 for a, b in
                   zip(self.as_vector(), other.as_vector())) ** 0.5

    def magnitude(self) -> float:
        return sum(v ** 2 for v in self.as_vector()) ** 0.5


# ── Gap ───────────────────────────────────────────────────────────────────

@dataclass
class Gap:
    """A gap articulation — the LLM's assessment of a causal chain.

    Every gap gets hashed and stored on the trajectory, whether acted on
    or not. Dormant gaps (below threshold) are peripheral vision —
    addressable by hash, trackable across turns, promotable if recurring.
    """
    hash:        str                    # content-addressed from desc + refs
    desc:        str                    # semantic articulation of the gap
    content_refs: list[str] = field(default_factory=list)  # layer 2: blobs/trees/commits
    step_refs:   list[str] = field(default_factory=list)   # layer 1: reasoning chain followed
    origin:      Optional[str] = None   # step hash that surfaced this gap
    scores:      Epistemic = field(default_factory=Epistemic)
    vocab:       Optional[str] = None   # mapped precondition (scan_needed, script_edit_needed, etc.)
    vocab_score: float = 0.0            # confidence in the vocab mapping
    resolved:    bool = False           # True when chain closed this gap
    dormant:     bool = False           # True if below threshold, stored but not acted on

    @staticmethod
    def create(desc: str,
               content_refs: list[str] = None,
               step_refs: list[str] = None,
               origin: str = None) -> "Gap":
        refs = content_refs or []
        srefs = step_refs or []
        h = blob_hash(f"{desc}:{':'.join(refs)}:{':'.join(srefs)}")
        return Gap(
            hash=h,
            desc=desc,
            content_refs=refs,
            step_refs=srefs,
            origin=origin,
        )

    def to_dict(self) -> dict:
        d = {
            "hash": self.hash,
            "desc": self.desc,
            "content_refs": self.content_refs,
            "step_refs": self.step_refs,
            "scores": {
                "relevance": self.scores.relevance,
                "confidence": self.scores.confidence,
                "grounded": self.scores.grounded,
            },
        }
        if self.origin:
            d["origin"] = self.origin
        if self.vocab:
            d["vocab"] = self.vocab
            d["vocab_score"] = self.vocab_score
        if self.resolved:
            d["resolved"] = True
        if self.dormant:
            d["dormant"] = True
        return d


# ── Step ──────────────────────────────────────────────────────────────────

@dataclass
class Step:
    """The single primitive. Every state transition produces one.

    Pre-diff:  step_refs (reasoning chain the LLM followed)
               + content_refs (blobs/commits referenced)
               + desc (semantic articulation of the transitions)

    Post-diff: gaps (one per causal chain, with vocab mapping + scores)
               + commit (git SHA if mutation occurred)
    """
    # ── Identity ──
    hash:         str

    # ── Pre-diff (LLM's perception) ──
    step_refs:    list[str]             # layer 1: step hashes followed
    content_refs: list[str]             # layer 2: blobs/trees/commits referenced
    desc:         str                   # semantic articulation of the causal chain

    # ── Post-diff (gaps + action result) ──
    gaps:         list[Gap]             # one per causal chain, with vocab + scores
    commit:       Optional[str] = None  # git commit SHA if mutation occurred

    # ── Metadata ──
    t:            float = 0.0
    chain_id:     Optional[str] = None  # which reasoning chain this step belongs to
    parent:       Optional[str] = None  # step hash that spawned this step (child gap)

    @staticmethod
    def create(desc: str,
               step_refs: list[str] = None,
               content_refs: list[str] = None,
               gaps: list[Gap] = None,
               commit: str = None,
               chain_id: str = None,
               parent: str = None) -> "Step":
        t = time.time()
        srefs = step_refs or []
        crefs = content_refs or []
        h = blob_hash(f"{desc}:{t}:{':'.join(srefs)}:{':'.join(crefs)}")
        return Step(
            hash=h,
            step_refs=srefs,
            content_refs=crefs,
            desc=desc,
            gaps=gaps or [],
            commit=commit,
            t=t,
            chain_id=chain_id,
            parent=parent,
        )

    def is_mutation(self) -> bool:
        return self.commit is not None

    def is_observation(self) -> bool:
        return self.commit is None

    def has_gaps(self) -> bool:
        return any(not g.resolved and not g.dormant for g in self.gaps)

    def active_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if not g.resolved and not g.dormant]

    def dormant_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if g.dormant]

    def all_refs(self) -> list[str]:
        """All hashes this step touches (both layers)."""
        refs = list(self.step_refs) + list(self.content_refs)
        for g in self.gaps:
            refs.extend(g.content_refs)
            refs.extend(g.step_refs)
        return refs

    def to_dict(self) -> dict:
        d = {
            "hash": self.hash,
            "step_refs": self.step_refs,
            "content_refs": self.content_refs,
            "desc": self.desc,
            "gaps": [g.to_dict() for g in self.gaps],
            "t": self.t,
        }
        if self.commit:
            d["commit"] = self.commit
        if self.chain_id:
            d["chain_id"] = self.chain_id
        if self.parent:
            d["parent"] = self.parent
        return d

    @staticmethod
    def from_dict(d: dict) -> "Step":
        gaps = []
        for g in d.get("gaps", []):
            gap = Gap(
                hash=g["hash"],
                desc=g["desc"],
                content_refs=g.get("content_refs", []),
                step_refs=g.get("step_refs", []),
                origin=g.get("origin"),
                scores=Epistemic(
                    relevance=g.get("scores", {}).get("relevance", 0.0),
                    confidence=g.get("scores", {}).get("confidence", 0.0),
                    grounded=g.get("scores", {}).get("grounded", 0.0),
                ),
                vocab=g.get("vocab"),
                vocab_score=g.get("vocab_score", 0.0),
                resolved=g.get("resolved", False),
                dormant=g.get("dormant", False),
            )
            gaps.append(gap)

        return Step(
            hash=d["hash"],
            step_refs=d.get("step_refs", []),
            content_refs=d.get("content_refs", []),
            desc=d.get("desc", ""),
            gaps=gaps,
            commit=d.get("commit"),
            t=d.get("t", 0.0),
            chain_id=d.get("chain_id"),
            parent=d.get("parent"),
        )


# ── Chain ─────────────────────────────────────────────────────────────────

@dataclass
class Chain:
    """A reasoning chain — sequence of steps originating from one gap.

    A chain IS a reasoning step at a higher level. It has its own hash
    (derived from member step hashes). Chains that exceed a length
    threshold get extracted to chains/*.json.

    Chains are the units that render shows. Not individual atoms.
    """
    hash:       str
    origin_gap: str               # the gap hash that started this chain
    steps:      list[str]         # step hashes in execution order
    desc:       str = ""          # semantic summary (set when chain completes)
    resolved:   bool = False
    extracted:  bool = False      # True if saved to chains/*.json

    @staticmethod
    def create(origin_gap: str, first_step: str) -> "Chain":
        h = chain_hash([origin_gap, first_step])
        return Chain(
            hash=h,
            origin_gap=origin_gap,
            steps=[first_step],
        )

    def add_step(self, step_hash: str):
        self.steps.append(step_hash)
        # Rehash with new member
        self.hash = chain_hash([self.origin_gap] + self.steps)

    def length(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "origin_gap": self.origin_gap,
            "steps": self.steps,
            "desc": self.desc,
            "resolved": self.resolved,
        }

    @staticmethod
    def from_dict(d: dict) -> "Chain":
        return Chain(
            hash=d["hash"],
            origin_gap=d["origin_gap"],
            steps=d.get("steps", []),
            desc=d.get("desc", ""),
            resolved=d.get("resolved", False),
            extracted=d.get("extracted", False),
        )


# ── Trajectory ────────────────────────────────────────────────────────────

class Trajectory:
    """The reasoning trajectory — a hash map of steps.

    Storage: trajectory.json (flat list of step dicts).
    Access: by hash (O(1) lookup) or sequential (ordered by time).

    The trajectory is the closed hash graph. Only steps go on it.
    Content (blobs/commits) is referenced but never stored here.
    """

    def __init__(self):
        self.steps: dict[str, Step] = {}      # hash → Step
        self.order: list[str] = []            # step hashes in chronological order
        self.chains: dict[str, Chain] = {}    # chain_hash → Chain
        self.gap_index: dict[str, Gap] = {}   # gap_hash → Gap (all gaps, including dormant)

    def append(self, step: Step):
        """Add a step to the trajectory."""
        self.steps[step.hash] = step
        self.order.append(step.hash)
        # Index all gaps (active + dormant)
        for gap in step.gaps:
            self.gap_index[gap.hash] = gap

    def resolve(self, hash: str) -> Optional[Step]:
        """Resolve a step hash to its data."""
        return self.steps.get(hash)

    def resolve_gap(self, hash: str) -> Optional[Gap]:
        """Resolve a gap hash."""
        return self.gap_index.get(hash)

    def recent(self, n: int = 10) -> list[Step]:
        """Last N steps in chronological order."""
        hashes = self.order[-n:]
        return [self.steps[h] for h in hashes if h in self.steps]

    def recent_chains(self, n: int = 5) -> list[Chain]:
        """Last N completed or active chains."""
        chains = sorted(self.chains.values(),
                       key=lambda c: c.steps[-1] if c.steps else "",
                       reverse=True)
        return chains[:n]

    def add_chain(self, chain: Chain):
        self.chains[chain.hash] = chain

    def find_chain(self, origin_gap_hash: str) -> Optional[Chain]:
        """Find chain by its origin gap."""
        for c in self.chains.values():
            if c.origin_gap == origin_gap_hash:
                return c
        return None

    def co_occurrence(self, hash: str) -> int:
        """How many steps reference this hash (either layer)."""
        count = 0
        for step in self.steps.values():
            if hash in step.all_refs():
                count += 1
        return count

    def is_commit(self, hash: str) -> bool:
        """Is this hash a commit (mutation step)?"""
        step = self.steps.get(hash)
        return step is not None and step.is_mutation()

    def dormant_gaps(self) -> list[Gap]:
        """All dormant gaps across the trajectory."""
        return [g for g in self.gap_index.values() if g.dormant]

    def recurring_dormant(self, min_count: int = 3) -> list[str]:
        """Dormant gap descriptions that appear multiple times."""
        from collections import Counter
        descs = [g.desc for g in self.gap_index.values() if g.dormant]
        counts = Counter(descs)
        return [desc for desc, count in counts.items() if count >= min_count]

    # ── Persistence ──

    def save(self, path: str):
        """Save trajectory to JSON file."""
        data = [self.steps[h].to_dict() for h in self.order if h in self.steps]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def save_chains(self, path: str):
        """Save chains index to JSON file."""
        data = [c.to_dict() for c in self.chains.values()]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path: str) -> "Trajectory":
        """Load trajectory from JSON file."""
        traj = Trajectory()
        try:
            with open(path) as f:
                data = json.load(f)
            for d in data:
                step = Step.from_dict(d)
                traj.append(step)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return traj

    @staticmethod
    def load_chains(path: str, traj: "Trajectory") -> None:
        """Load chains index and attach to trajectory."""
        try:
            with open(path) as f:
                data = json.load(f)
            for d in data:
                chain = Chain.from_dict(d)
                traj.chains[chain.hash] = chain
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # ── Render ──

    def _tag_ref(self, ref: str, layer: str, registry=None) -> str:
        """Tag a hash reference with its type prefix.

        Resolves named entities from the skill registry:
          72b1d5ffc964 → admin:72b1d5ffc964
          a72c3c4dec0c → research:a72c3c4dec0c

        Falls back to layer prefix:
          step refs  → step:<hash>
          content refs → <hash> (bare — could be blob, tree, or commit)
        """
        # Check skill registry first — named hashes take priority
        if registry is not None:
            name = registry.resolve_name(ref)
            if name:
                return f"{name}:{ref}"
        # Check if it's a known step on the trajectory
        if layer == "step":
            return f"step:{ref}"
        # Bare content hash (blob/tree/commit — resolved on demand)
        return ref

    def _render_refs(self, step_refs: list[str], content_refs: list[str], registry=None) -> str:
        """Render a refs list with named tags."""
        refs = []
        for r in step_refs:
            refs.append(self._tag_ref(r, "step", registry))
        for r in content_refs:
            refs.append(self._tag_ref(r, "content", registry))
        return f" → refs:[{', '.join(refs)}]" if refs else ""

    def render_recent(self, n: int = 5, registry=None) -> str:
        """Render trajectory as a traversable hash tree.

        The LLM sees the same shape everywhere — git trees, trajectory,
        resolved content. Every node is a hash. Unresolved hashes are
        leaves the LLM can request resolution for.

        Known skill hashes render with their name prefix:
          refs:[admin:72b1d5ffc964, commit:aa8b921]

        When a skill evolves, the hash changes but the name stays:
          refs:[admin:a1b2c3d4e5f6]  ← identity updated

        Structure:
          chain:<hash>  "summary" (status)
            origin: <gap_hash> "gap description"
            ├─ step:<hash> "desc" → refs:[admin:<hash>, commit:<sha>]
            │   ├─ gap:<hash> "what needs doing" [vocab] → refs:[<hash>]
            │   └─ gap:<hash> (dormant, score:0.15)
            ├─ step:<hash> "desc" → commit:<sha>
            │   └─ (resolved)
            └─ ...
        """
        chains = self.recent_chains(n)

        if not chains:
            # No chains yet — render steps as a flat tree
            steps = self.recent(n)
            if not steps:
                return "(empty trajectory)"
            return self._render_steps_as_tree(steps, registry)

        lines = []
        for chain in chains:
            # Chain header
            status = "resolved" if chain.resolved else f"active, {chain.length()} steps"
            desc = chain.desc or "in progress"
            lines.append(f"chain:{chain.hash}  \"{desc}\" ({status})")
            lines.append(f"  origin: {chain.origin_gap}")

            # Render each step as a branch
            for i, step_hash in enumerate(chain.steps):
                step = self.steps.get(step_hash)
                if not step:
                    lines.append(f"  {'├' if i < len(chain.steps)-1 else '└'}─ step:{step_hash} (unresolved)")
                    continue

                is_last_step = (i == len(chain.steps) - 1)
                branch = "└" if is_last_step else "├"
                cont = " " if is_last_step else "│"

                # Step line — desc + refs
                ref_str = self._render_refs(step.step_refs, step.content_refs, registry)
                commit_str = f" → commit:{step.commit}" if step.commit else ""
                lines.append(f"  {branch}─ step:{step.hash} \"{step.desc}\"{ref_str}{commit_str}")

                # Step's gaps as sub-branches
                active = [g for g in step.gaps if not g.dormant and not g.resolved]
                resolved = [g for g in step.gaps if g.resolved]
                dormant = [g for g in step.gaps if g.dormant]
                all_gaps = active + resolved + dormant

                for j, gap in enumerate(all_gaps):
                    is_last_gap = (j == len(all_gaps) - 1)
                    gbranch = "└" if is_last_gap else "├"

                    if gap.dormant:
                        score = gap.scores.magnitude()
                        lines.append(f"  {cont}   {gbranch}─ gap:{gap.hash} (dormant, score:{score:.2f})")
                    elif gap.resolved:
                        lines.append(f"  {cont}   {gbranch}─ gap:{gap.hash} (resolved)")
                    else:
                        # Active gap — show desc, vocab, refs
                        gref_str = self._render_refs(gap.step_refs, gap.content_refs, registry)
                        vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
                        lines.append(f"  {cont}   {gbranch}─ gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}")

        return "\n".join(lines)

    def _render_steps_as_tree(self, steps: list["Step"], registry=None) -> str:
        """Render loose steps (no chains yet) as a flat hash tree."""
        lines = []
        for i, step in enumerate(steps):
            is_last = (i == len(steps) - 1)
            branch = "└" if is_last else "├"
            cont = " " if is_last else "│"

            ref_str = self._render_refs(step.step_refs, step.content_refs, registry)
            commit_str = f" → commit:{step.commit}" if step.commit else ""
            lines.append(f"{branch}─ step:{step.hash} \"{step.desc}\"{ref_str}{commit_str}")

            for j, gap in enumerate(step.gaps):
                is_last_gap = (j == len(step.gaps) - 1)
                gbranch = "└" if is_last_gap else "├"

                if gap.dormant:
                    lines.append(f"{cont}   {gbranch}─ gap:{gap.hash} (dormant)")
                elif gap.resolved:
                    lines.append(f"{cont}   {gbranch}─ gap:{gap.hash} (resolved)")
                else:
                    gref_str = self._render_refs(gap.step_refs, gap.content_refs, registry)
                    vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
                    lines.append(f"{cont}   {gbranch}─ gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}")

        return "\n".join(lines)
