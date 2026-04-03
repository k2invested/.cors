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
import re
import time
from dataclasses import dataclass, field
from typing import Optional


TREE_LANGUAGE_KEY = (
    "tree_sig: step{kindflowN}=kind:o observe,m mutate,r rogue; flow:+ open,~ dormant,= closed. "
    "gap{statusclassrcg/s:c}=status:? active,= resolved,~ dormant; "
    "class:o observe,m mutate,b bridge,c clarify,_ unknown; "
    "rcg are rel/conf/gr bands 0-9; s:c are step_refs:content_refs counts. "
    "step refs are execution provenance; gap refs are gap-surfacing provenance."
)

OBSERVE_VOCABS = {
    "hash_resolve_needed", "external_context", "pattern_needed",
    "scan_needed", "research_needed", "url_needed",
}
MUTATE_VOCABS = {
    "hash_edit_needed", "content_needed", "script_edit_needed", "command_needed",
}
BRIDGE_VOCABS = {
    "reason_needed", "await_needed", "commit_needed", "reprogramme_needed", "stitch_needed",
}
CLARIFY_VOCABS = {"clarify_needed"}


# ── Time formatting ──────────────────────────────────────────────────────

def relative_time(t: float) -> str:
    """Format a timestamp as relative time from now. For deep renders (per-gap injection)."""
    if t <= 0:
        return ""
    delta = time.time() - t
    if delta < 2:
        return "just now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    days = int(delta / 86400)
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days}d ago"
    return f"{int(days / 30)}mo ago"


def absolute_time(t: float) -> str:
    """Format a timestamp as absolute datetime. Universal across all renders."""
    if t <= 0:
        return ""
    from datetime import datetime
    dt = datetime.fromtimestamp(t)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ── Hash computation ──────────────────────────────────────────────────────

def blob_hash(content: str) -> str:
    """Content-addressed hash. 12-char hex from SHA-256."""
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def chain_hash(step_hashes: list[str]) -> str:
    """Hash a sequence of step hashes into a chain hash."""
    combined = ":".join(step_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


def score_band(value: float) -> str:
    """Compress a 0-1 score into a single 0-9 band for tree rendering."""
    if value is None:
        value = 0.0
    return str(max(0, min(9, round(value * 9))))


def vocab_class(vocab: Optional[str]) -> str:
    """Compress runtime vocab into a one-character manifestation class."""
    if not vocab:
        return "_"
    if vocab in OBSERVE_VOCABS:
        return "o"
    if vocab in MUTATE_VOCABS:
        return "m"
    if vocab in BRIDGE_VOCABS:
        return "b"
    if vocab in CLARIFY_VOCABS:
        return "c"
    return "_"


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
    resolution_kind: Optional[str] = None  # how the gap closed: rogue_handoff, success, etc.
    dormant:     bool = False           # True if below threshold, stored but not acted on
    turn_id:     Optional[int] = None  # which turn created this gap (for cross-turn threshold)
    carry_forward: bool = False        # True when explicitly persisted for cross-turn resume
    route_mode: Optional[str] = None   # deterministic routing hint for execution branches

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
        if self.resolution_kind:
            d["resolution_kind"] = self.resolution_kind
        if self.dormant:
            d["dormant"] = True
        if self.turn_id is not None:
            d["turn_id"] = self.turn_id
        if self.carry_forward:
            d["carry_forward"] = True
        if self.route_mode:
            d["route_mode"] = self.route_mode
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
    rogue:        bool = False          # True when the step materialized as a policy/tool/schema failure
    rogue_kind:   Optional[str] = None  # policy_violation, codon_failure, compile_invalid, etc.
    failure_source: Optional[str] = None  # which tool/runtime path failed
    failure_detail: Optional[str] = None  # compact machine-visible failure summary
    assessment:   list[str] = field(default_factory=list)  # deterministic post-observation / commit assessment

    @staticmethod
    def create(desc: str,
               step_refs: list[str] = None,
               content_refs: list[str] = None,
               gaps: list[Gap] = None,
               commit: str = None,
               chain_id: str = None,
               parent: str = None,
               rogue: bool = False,
               rogue_kind: str | None = None,
               failure_source: str | None = None,
               failure_detail: str | None = None,
               assessment: list[str] | None = None) -> "Step":
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
            rogue=rogue,
            rogue_kind=rogue_kind,
            failure_source=failure_source,
            failure_detail=failure_detail,
            assessment=assessment or [],
        )

    def is_mutation(self) -> bool:
        return self.commit is not None

    def is_rogue(self) -> bool:
        return self.rogue

    def is_observation(self) -> bool:
        return self.commit is None and not self.rogue

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
        if self.rogue:
            d["rogue"] = True
        if self.rogue_kind:
            d["rogue_kind"] = self.rogue_kind
        if self.failure_source:
            d["failure_source"] = self.failure_source
        if self.failure_detail:
            d["failure_detail"] = self.failure_detail
        if self.assessment:
            d["assessment"] = self.assessment
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
                resolution_kind=g.get("resolution_kind"),
                dormant=g.get("dormant", False),
                turn_id=g.get("turn_id"),
                carry_forward=g.get("carry_forward", False),
                route_mode=g.get("route_mode"),
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
            rogue=d.get("rogue", False),
            rogue_kind=d.get("rogue_kind"),
            failure_source=d.get("failure_source"),
            failure_detail=d.get("failure_detail"),
            assessment=d.get("assessment", []),
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
            "extracted": self.extracted,
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

    def rogue_steps(self) -> list[Step]:
        """All rogue steps across the trajectory."""
        return [self.steps[h] for h in self.order if h in self.steps and self.steps[h].rogue]

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

    def extract_chains(self, chains_dir: str):
        """Extract long/resolved chains to individual files.

        Chains marked as extracted get their full step data saved to
        chains/{chain_hash}.json. The trajectory keeps the chain hash
        but the step data moves to the file — keeps trajectory compact.
        """
        import os
        os.makedirs(chains_dir, exist_ok=True)
        for chain in self.chains.values():
            if chain.extracted and chain.resolved:
                chain_path = os.path.join(chains_dir, f"{chain.hash}.json")
                if os.path.exists(chain_path):
                    continue  # already extracted
                chain_data = {
                    "hash": chain.hash,
                    "origin_gap": chain.origin_gap,
                    "desc": chain.desc,
                    "steps": [],
                }
                for step_hash in chain.steps:
                    step = self.steps.get(step_hash)
                    if step:
                        chain_data["steps"].append(step.to_dict())
                with open(chain_path, "w") as f:
                    json.dump(chain_data, f, indent=2)

    def append_to_passive_chain(self, chain_hash: str, step: "Step") -> bool:
        """Append a step to a passive (cross-turn) chain.

        Passive chains accumulate steps across turns — like commitments
        building evidence toward a goal. Returns True if the chain exists
        and the step was appended.
        """
        chain = self.chains.get(chain_hash)
        if chain and not chain.resolved:
            chain.add_step(step.hash)
            self.append(step)
            return True
        return False

    def find_passive_chains(self, content_ref: str) -> list[Chain]:
        """Find active (unresolved) chains whose origin gap references this hash.

        Used to detect when a gap's content_refs overlap with an existing
        passive chain — the step should append to that chain rather than
        starting a new one.
        """
        matches = []
        for chain in self.chains.values():
            if chain.resolved:
                continue
            # Check if the chain's origin gap references the same entity
            origin_gap = self.gap_index.get(chain.origin_gap)
            if origin_gap:
                all_refs = origin_gap.content_refs + origin_gap.step_refs
                if content_ref in all_refs:
                    matches.append(chain)
        return matches

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

    def _skill_ref_namespace(self, skill) -> str:
        source = str(getattr(skill, "source", ""))
        if "codons" in source:
            return "codon"
        if "actions" in source:
            return "action"
        return "entity"

    def _tag_ref(self, ref: str, layer: str, registry=None) -> str:
        """Tag a hash reference with its type prefix.

        Resolves known skill hashes into canonical typed namespaces:
          72b1d5ffc964 → entity:72b1d5ffc964
          a72c3c4dec0c → action:a72c3c4dec0c

        Falls back to layer prefix:
          step refs  → step:<hash>
          content refs → <hash> (bare — could be blob, tree, or commit)
        """
        if registry is not None:
            skill = registry.resolve(ref)
            if skill is not None:
                return f"{self._skill_ref_namespace(skill)}:{ref}"
        if layer == "step":
            return f"step:{ref}"
        return ref

    def _render_refs(self, step_refs: list[str], content_refs: list[str], registry=None) -> str:
        """Render a refs list with named tags."""
        refs = []
        for r in step_refs:
            refs.append(self._tag_ref(r, "step", registry))
        for r in content_refs:
            refs.append(self._tag_ref(r, "content", registry))
        return f" → refs:[{', '.join(refs)}]" if refs else ""

    def tree_language_key(self) -> str:
        """Compact legend for the semantic tree notation."""
        return TREE_LANGUAGE_KEY

    def _step_signature(self, step: "Step") -> str:
        """Compact step signature for tree rendering.

        Format: {kindflowN}
          kind: o observe, m mutate
          flow: + active child gaps, ~ dormant-only, = closed/no open child gaps
          N: number of active child gaps (only when > 0)
        """
        active = len(step.active_gaps())
        dormant = len(step.dormant_gaps())
        if step.is_rogue():
            kind = "r"
        else:
            kind = "m" if step.is_mutation() else "o"
        flow = "+" if active else "~" if dormant else "="
        count = str(active) if active else ""
        return f"{{{kind}{flow}{count}}}"

    def _gap_signature(self, gap: "Gap") -> str:
        """Compact gap signature for tree rendering.

        Format: {statusclassrcg/s:c}
          status: ? active, = resolved, ~ dormant
          class:  o observe, m mutate, b bridge, c clarify, _ unknown
          rcg:    relevance/confidence/grounded compressed to 0-9 bands
          s:c:    step_refs:content_refs counts
        """
        status = "~" if gap.dormant else "=" if gap.resolved else "?"
        klass = vocab_class(gap.vocab)
        rel = score_band(gap.scores.relevance)
        conf = score_band(gap.scores.confidence)
        gr = score_band(gap.scores.grounded)
        return f"{{{status}{klass}{rel}{conf}{gr}/{len(gap.step_refs)}:{len(gap.content_refs)}}}"

    def _runtime_tree_legend(self) -> str:
        return (
            "legend: step{kindflowN}; gap{statusclassrcg/s:c}; "
            "refs use typed namespaces entity/action/codon/step plus raw content refs; "
            "step refs = execution provenance; gap refs = gap-surfacing provenance; "
            "resolved -> rogue handoff = original gap closed by explicit failure handoff"
        )

    def _resolved_gap_status_label(self, gap: "Gap") -> str:
        if gap.resolution_kind == "rogue_handoff":
            return "resolved -> rogue handoff"
        return "resolved"

    def _gap_desc_for_render(self, parent_desc: str, gap_desc: str) -> str | None:
        if not gap_desc:
            return None
        normalized_gap = gap_desc.strip()
        normalized_parent = (parent_desc or "").strip()
        if normalized_gap == normalized_parent:
            return None
        collapsed = re.sub(r"^close branch \d+:\s*", "", normalized_gap, flags=re.IGNORECASE)
        if collapsed == normalized_parent:
            return None
        return normalized_gap

    def _collapsed_chain_summary(self, nodes: list[dict]) -> str:
        observe = 0
        mutate = 0
        bridge = 0
        clarify = 0
        resolved = 0
        active = 0
        for node in nodes:
            kind = node.get("kind")
            if kind == "mutate":
                mutate += 1
            elif kind in {"reason", "higher_order", "await"}:
                bridge += 1
            elif kind == "clarify":
                clarify += 1
            else:
                observe += 1
            gaps = list(node.get("gaps", []) or ([] if not node.get("gap") else [node.get("gap")]))
            if any(gap.get("status") == "active" for gap in gaps):
                active += 1
            else:
                resolved += 1
        return (
            f"history: {resolved} resolved steps, {active} active steps, "
            f"observe={observe}, bridge={bridge}, mutate={mutate}, clarify={clarify}"
        )

    def render_recent(self, n: int = 5, registry=None, mode: str = "full") -> str:
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
            origin: <gap_hash>
            ├─ {o+2} step:<hash> "desc" → refs:[admin:<hash>, commit:<sha>]
            │   ├─ {?o862/1:2} gap:<hash> "what needs doing" [hash_resolve_needed]
            │   └─ {~_210/0:1} gap:<hash> "low-value branch"
            ├─ {m=} step:<hash> "desc" → commit:<sha>
            │   └─ {=o764/1:1} gap:<hash> "closed postcondition"
            └─ ...
        """
        chains = self.recent_chains(n)
        import manifest_engine as manifest_engine_module

        if not chains:
            # No chains yet — render steps as a flat tree
            steps = self.recent(n)
            if not steps:
                return "(empty trajectory)"
            tree = manifest_engine_module.build_runtime_semantic_tree(
                [step.to_dict() for step in steps],
                source_type="trajectory_recent",
                source_ref="recent",
                summary_desc="recent trajectory",
            )
            rendered = "\n".join(self._render_semantic_tree_lines(tree, registry=registry, mode=mode))
            rogue_lines = self._render_rogue_lines(registry=registry)
            if rogue_lines:
                return f"{rendered}\n\n" + "\n".join(rogue_lines)
            return rendered

        lines = []
        for chain in chains:
            tree = manifest_engine_module.build_semantic_tree_from_trajectory(self, chain_id=chain.hash)
            lines.extend(self._render_semantic_tree_lines(tree, registry=registry, mode=mode))

        rogue_lines = self._render_rogue_lines(registry=registry)
        if rogue_lines:
            lines.append("")
            lines.extend(rogue_lines)

        return "\n".join(lines)

    def render_chain(self, chain_id: str, registry=None, highlight_gap: str | None = None,
                     mode: str = "full") -> str:
        """Render one chain as a semantic tree.

        Used for active-chain injection during iteration. Optionally marks
        the currently addressed gap so the LLM sees its causal branch.
        """
        chain = self.chains.get(chain_id)
        if not chain:
            return f"(missing chain: {chain_id})"
        import manifest_engine as manifest_engine_module
        tree = manifest_engine_module.build_semantic_tree_from_trajectory(self, chain_id=chain_id)
        return "\n".join(self._render_semantic_tree_lines(tree, registry=registry, highlight_gap=highlight_gap, mode=mode))

    def _render_semantic_tree_lines(self, tree: dict, registry=None,
                                    highlight_gap: str | None = None,
                                    mode: str = "full") -> list[str]:
        nodes = list(tree.get("nodes", []) or [])
        if tree.get("source_type") == "realized_chain":
            desc = tree.get("desc") or "in progress"
            status = "resolved" if tree.get("resolved") else f"active, {len(nodes)} steps"
            time_str = ""
            if nodes:
                last_meta = dict(nodes[-1].get("meta", {}) or {})
                if last_meta.get("timestamp", 0) > 0:
                    time_str = f" [{absolute_time(last_meta['timestamp'])}]"
            lines = [f"chain:{tree.get('source_ref')}  \"{desc}\" ({status}){time_str}"]
            origin_marker = " [focus]" if highlight_gap and tree.get("origin_gap") == highlight_gap else ""
            lines.append(f"  origin: {tree.get('origin_gap')}{origin_marker}")
            lines.append(f"  {self._runtime_tree_legend()}")
            if mode == "collapsed" and nodes:
                lines.append(f"  {self._collapsed_chain_summary(nodes)}")
                active_nodes = [node for node in nodes if any(g.get("status") == "active" for g in (node.get("gaps", []) or []))]
                tail_nodes = nodes[-4:]
                selected = []
                seen_ids = set()
                for node in [*tail_nodes, *active_nodes]:
                    if node.get("id") not in seen_ids:
                        seen_ids.add(node.get("id"))
                        selected.append(node)
                omitted = max(0, len(nodes) - len(selected))
                if omitted:
                    lines.append(f"  … {omitted} earlier resolved step(s) collapsed")
                nodes = selected
            for index, node in enumerate(nodes):
                is_last_step = index == len(nodes) - 1
                branch = "└" if is_last_step else "├"
                cont = " " if is_last_step else "│"
                meta = dict(node.get("meta", {}) or {})
                refs = dict(node.get("refs", {}) or {})
                ref_str = self._render_refs(refs.get("step_refs", []) or [], refs.get("content_refs", []) or [], registry)
                commit_str = f" → commit:{meta.get('commit')}" if meta.get("commit") else ""
                time_tag = f" ({absolute_time(meta['timestamp'])})" if meta.get("timestamp", 0) > 0 else ""
                rogue_tag = ""
                if meta.get("rogue"):
                    extras = [part for part in [meta.get("rogue_kind"), meta.get("failure_source")] if part]
                    rogue_tag = f" (rogue:{', '.join(extras)})" if extras else " (rogue)"
                lines.append(
                    f"  {branch}─ {node.get('signature')} step:{node.get('id')} "
                    f"\"{node.get('goal', '')}\"{ref_str}{commit_str}{time_tag}{rogue_tag}"
                )
                for assessment_line in meta.get("assessment", []) or []:
                    lines.append(f"  {cont}   assessment: {assessment_line}")
                gaps = list(node.get("gaps", []) or ([] if not node.get("gap") else [node.get("gap")]))
                active = [gap for gap in gaps if gap.get("status") == "active"]
                resolved = [gap for gap in gaps if gap.get("status") == "resolved"]
                dormant = [gap for gap in gaps if gap.get("status") == "dormant"]
                for gap_index, gap in enumerate(active + resolved + dormant):
                    is_last_gap = gap_index == len(active + resolved + dormant) - 1
                    gbranch = "└" if is_last_gap else "├"
                    gap_obj = Gap(
                        hash=gap.get("hash", ""),
                        desc=gap.get("desc", ""),
                        content_refs=list(gap.get("content_refs", []) or []),
                        step_refs=list(gap.get("step_refs", []) or []),
                        origin=gap.get("origin"),
                        scores=Epistemic(
                            relevance=gap.get("relevance") or 0.0,
                            confidence=gap.get("confidence") or 0.0,
                            grounded=gap.get("grounded") or 0.0,
                        ),
                        vocab=gap.get("runtime_vocab"),
                        resolved=gap.get("status") == "resolved",
                        resolution_kind=gap.get("resolution_kind"),
                        dormant=gap.get("status") == "dormant",
                    )
                    focus = " [focus]" if highlight_gap and gap_obj.hash == highlight_gap else ""
                    gap_desc = self._gap_desc_for_render(node.get("goal", ""), gap_obj.desc)
                    gref_str = self._render_refs(gap_obj.step_refs, gap_obj.content_refs, registry)
                    if gap_obj.dormant:
                        desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                        score = gap_obj.scores.magnitude()
                        lines.append(
                            f"  {cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                            f"gap:{gap_obj.hash}{desc_part}{gref_str} (dormant, score:{score:.2f}){focus}"
                        )
                    elif gap_obj.resolved:
                        desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                        lines.append(
                            f"  {cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                            f"gap:{gap_obj.hash}{desc_part}{gref_str} ({self._resolved_gap_status_label(gap_obj)}){focus}"
                        )
                    else:
                        vocab_str = f" [{gap_obj.vocab}]" if gap_obj.vocab else ""
                        desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                        lines.append(
                            f"  {cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                            f"gap:{gap_obj.hash}{desc_part}{vocab_str}{gref_str}{focus}"
                        )
            return lines

        lines = []
        for index, node in enumerate(nodes):
            is_last = index == len(nodes) - 1
            branch = "└" if is_last else "├"
            cont = " " if is_last else "│"
            meta = dict(node.get("meta", {}) or {})
            refs = dict(node.get("refs", {}) or {})
            ref_str = self._render_refs(refs.get("step_refs", []) or [], refs.get("content_refs", []) or [], registry)
            commit_str = f" → commit:{meta.get('commit')}" if meta.get("commit") else ""
            time_tag = f" ({absolute_time(meta['timestamp'])})" if meta.get("timestamp", 0) > 0 else ""
            rogue_tag = ""
            if meta.get("rogue"):
                extras = [part for part in [meta.get("rogue_kind"), meta.get("failure_source")] if part]
                rogue_tag = f" (rogue:{', '.join(extras)})" if extras else " (rogue)"
            lines.append(
                f"{branch}─ {node.get('signature')} step:{node.get('id')} "
                f"\"{node.get('goal', '')}\"{ref_str}{commit_str}{time_tag}{rogue_tag}"
            )
            for assessment_line in meta.get("assessment", []) or []:
                lines.append(f"{cont}   assessment: {assessment_line}")
            gaps = list(node.get("gaps", []) or ([] if not node.get("gap") else [node.get("gap")]))
            for gap_index, gap in enumerate(gaps):
                is_last_gap = gap_index == len(gaps) - 1
                gbranch = "└" if is_last_gap else "├"
                gap_obj = Gap(
                    hash=gap.get("hash", ""),
                    desc=gap.get("desc", ""),
                    content_refs=list(gap.get("content_refs", []) or []),
                    step_refs=list(gap.get("step_refs", []) or []),
                    origin=gap.get("origin"),
                    scores=Epistemic(
                        relevance=gap.get("relevance") or 0.0,
                        confidence=gap.get("confidence") or 0.0,
                        grounded=gap.get("grounded") or 0.0,
                    ),
                    vocab=gap.get("runtime_vocab"),
                    resolved=gap.get("status") == "resolved",
                    resolution_kind=gap.get("resolution_kind"),
                    dormant=gap.get("status") == "dormant",
                )
                gref_str = self._render_refs(gap_obj.step_refs, gap_obj.content_refs, registry)
                if gap_obj.dormant:
                    gap_desc = self._gap_desc_for_render(node.get("goal", ""), gap_obj.desc)
                    desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                        f"gap:{gap_obj.hash}{desc_part}{gref_str} (dormant)"
                    )
                elif gap_obj.resolved:
                    gap_desc = self._gap_desc_for_render(node.get("goal", ""), gap_obj.desc)
                    desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                        f"gap:{gap_obj.hash}{desc_part}{gref_str} ({self._resolved_gap_status_label(gap_obj)})"
                    )
                else:
                    vocab_str = f" [{gap_obj.vocab}]" if gap_obj.vocab else ""
                    gap_desc = self._gap_desc_for_render(node.get("goal", ""), gap_obj.desc)
                    desc_part = f" \"{gap_desc}\"" if gap_desc else ""
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap_obj)} "
                        f"gap:{gap_obj.hash}{desc_part}{vocab_str}{gref_str}"
                    )
        return lines

    def _render_chain_lines(self, chain: "Chain", registry=None,
                            highlight_gap: str | None = None) -> list[str]:
        lines = []
        status = "resolved" if chain.resolved else f"active, {chain.length()} steps"
        desc = chain.desc or "in progress"
        last_step = self.steps.get(chain.steps[-1]) if chain.steps else None
        time_str = ""
        if last_step and last_step.t > 0:
            time_str = f" [{absolute_time(last_step.t)}]"
        lines.append(f"chain:{chain.hash}  \"{desc}\" ({status}){time_str}")
        origin_marker = " [focus]" if highlight_gap and chain.origin_gap == highlight_gap else ""
        lines.append(f"  origin: {chain.origin_gap}{origin_marker}")

        for i, step_hash in enumerate(chain.steps):
            step = self.steps.get(step_hash)
            if not step:
                lines.append(f"  {'├' if i < len(chain.steps)-1 else '└'}─ step:{step_hash} (unresolved)")
                continue

            is_last_step = (i == len(chain.steps) - 1)
            branch = "└" if is_last_step else "├"
            cont = " " if is_last_step else "│"

            ref_str = self._render_refs(step.step_refs, step.content_refs, registry)
            commit_str = f" → commit:{step.commit}" if step.commit else ""
            time_tag = f" ({absolute_time(step.t)})" if step.t > 0 else ""
            rogue_tag = ""
            if step.rogue:
                extras = [part for part in [step.rogue_kind, step.failure_source] if part]
                rogue_tag = f" (rogue:{', '.join(extras)})" if extras else " (rogue)"
            lines.append(
                f"  {branch}─ {self._step_signature(step)} step:{step.hash} "
                f"\"{step.desc}\"{ref_str}{commit_str}{time_tag}{rogue_tag}"
            )
            for assessment_line in step.assessment:
                lines.append(f"  {cont}   assessment: {assessment_line}")

            active = [g for g in step.gaps if not g.dormant and not g.resolved]
            resolved = [g for g in step.gaps if g.resolved]
            dormant = [g for g in step.gaps if g.dormant]
            all_gaps = active + resolved + dormant

            for j, gap in enumerate(all_gaps):
                is_last_gap = (j == len(all_gaps) - 1)
                gbranch = "└" if is_last_gap else "├"
                focus = " [focus]" if highlight_gap and gap.hash == highlight_gap else ""

                if gap.dormant:
                    score = gap.scores.magnitude()
                    lines.append(
                        f"  {cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\" (dormant, score:{score:.2f}){focus}"
                    )
                elif gap.resolved:
                    lines.append(
                        f"  {cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\" ({self._resolved_gap_status_label(gap)}){focus}"
                    )
                else:
                    gref_str = self._render_refs(gap.step_refs, gap.content_refs, registry)
                    vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
                    lines.append(
                        f"  {cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}{focus}"
                    )

        return lines

    def _render_steps_as_tree(self, steps: list["Step"], registry=None) -> str:
        """Render loose steps (no chains yet) as a flat hash tree."""
        lines = []
        for i, step in enumerate(steps):
            is_last = (i == len(steps) - 1)
            branch = "└" if is_last else "├"
            cont = " " if is_last else "│"

            ref_str = self._render_refs(step.step_refs, step.content_refs, registry)
            commit_str = f" → commit:{step.commit}" if step.commit else ""
            time_tag = f" ({absolute_time(step.t)})" if step.t > 0 else ""
            rogue_tag = ""
            if step.rogue:
                extras = [part for part in [step.rogue_kind, step.failure_source] if part]
                rogue_tag = f" (rogue:{', '.join(extras)})" if extras else " (rogue)"
            lines.append(
                f"{branch}─ {self._step_signature(step)} step:{step.hash} "
                f"\"{step.desc}\"{ref_str}{commit_str}{time_tag}{rogue_tag}"
            )
            for assessment_line in step.assessment:
                lines.append(f"{cont}   assessment: {assessment_line}")

            for j, gap in enumerate(step.gaps):
                is_last_gap = (j == len(step.gaps) - 1)
                gbranch = "└" if is_last_gap else "├"

                if gap.dormant:
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\" (dormant)"
                    )
                elif gap.resolved:
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\" ({self._resolved_gap_status_label(gap)})"
                    )
                else:
                    gref_str = self._render_refs(gap.step_refs, gap.content_refs, registry)
                    vocab_str = f" [{gap.vocab}]" if gap.vocab else ""
                    lines.append(
                        f"{cont}   {gbranch}─ {self._gap_signature(gap)} "
                        f"gap:{gap.hash} \"{gap.desc}\"{vocab_str}{gref_str}"
                    )

        return "\n".join(lines)

    def _render_rogue_lines(self, registry=None) -> list[str]:
        rogues = self.rogue_steps()
        if not rogues:
            return []
        lines = [f"rogues ({len(rogues)})"]
        for idx, step in enumerate(rogues[-5:]):
            branch = "└" if idx == len(rogues[-5:]) - 1 else "├"
            ref_str = self._render_refs(step.step_refs, step.content_refs, registry)
            commit_str = f" → commit:{step.commit}" if step.commit else ""
            time_tag = f" ({absolute_time(step.t)})" if step.t > 0 else ""
            extras = [part for part in [step.rogue_kind, step.failure_source] if part]
            rogue_tag = f" [{', '.join(extras)}]" if extras else ""
            lines.append(
                f"  {branch}─ {self._step_signature(step)} step:{step.hash} "
                f"\"{step.desc}\"{rogue_tag}{ref_str}{commit_str}{time_tag}"
            )
            for assessment_line in step.assessment:
                lines.append(f"  │   assessment: {assessment_line}")
        return lines
