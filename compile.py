"""Compile — lawful sequencing of semantic emissions.

The compiler structures execution from semantic emissions. It is not a
planner, not a search algorithm. It is a sequencer that:
  1. Admits emitted gaps that meet threshold
  2. Places them into lawful position (depth-first, not append)
  3. Preserves O-M-O structural rhythm
  4. Manages chain boundaries (open/active/suspended/closed)
  5. Monitors epistemic convergence via linear algebra

The ledger is NOT history. It is the ordered unresolved frontier —
a recursively rewritten ordered agenda. Gaps enter by admission,
are placed by law, and exit by resolution.

Three-part gap lifecycle:
  Emission:   a step produces candidate gaps (LLM pre-diff output)
  Admission:  only gaps above threshold enter the ledger
  Placement:  admitted gaps insert at lawful position (after current step, not at end)

Chain lifecycle:
  Open:       origin gap enters ledger, chain created
  Active:     current step is addressing a gap in this chain
  Suspended:  chain's current gap spawned children, waiting for them to resolve
  Closed:     all gaps in chain resolved, chain becomes a reasoning step

The compiler pops the top of the stack and routes by vocab.
OMO rhythm (observe-mutate-observe) is enforced by the transition grammar —
the compiler will not place a mutation without a preceding observation,
and every mutation is followed by an automatic observation (postcondition).
"""

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from step import Gap, Step, Chain, Epistemic, Trajectory


# ── Configuration ─────────────────────────────────────────────────────────

ADMISSION_THRESHOLD = 0.4       # minimum combined score for gap to enter ledger
CONFIDENCE_THRESHOLD = 0.8      # gap is resolved when confidence exceeds this
DORMANT_THRESHOLD = 0.2         # below this, gap is stored as dormant (peripheral vision)
MAX_CHAIN_DEPTH = 15            # maximum steps in a single chain before force-close
SATURATION_THRESHOLD = 0.05     # information gain below this = perception saturated
STAGNATION_WINDOW = 3           # N steps with no movement = stagnation
CHAIN_EXTRACT_LENGTH = 8        # chains longer than this get extracted to file


# ── Vocab ─────────────────────────────────────────────────────────────────

OBSERVE_VOCAB = {
    "scan_needed", "pattern_needed", "hash_resolve_needed",
    "research_needed", "email_needed", "url_needed",
    "registry_needed", "external_context",
}

MUTATE_VOCAB = {
    "content_needed", "script_edit_needed", "command_needed",
    "message_needed", "json_patch_needed", "git_revert_needed",
}

BRIDGE_VOCAB = {
    "judgment_needed", "task_needed", "commitment_needed",
    "profile_needed", "task_status_needed",
}


def is_observe(vocab: str) -> bool:
    return vocab in OBSERVE_VOCAB


def is_mutate(vocab: str) -> bool:
    return vocab in MUTATE_VOCAB


# ── Chain State ───────────────────────────────────────────────────────────

class ChainState(Enum):
    OPEN = auto()        # origin gap entered, chain created
    ACTIVE = auto()      # currently being addressed
    SUSPENDED = auto()   # waiting for child chain to resolve
    CLOSED = auto()      # all gaps resolved


# ── Ledger ────────────────────────────────────────────────────────────────

@dataclass
class LedgerEntry:
    """An entry on the ledger — a gap with placement metadata."""
    gap: Gap
    chain_id: str               # which chain this gap belongs to
    depth: int = 0              # depth in the chain (0 = origin)
    parent_gap: str | None = None  # gap hash that spawned this entry


class Ledger:
    """The ordered unresolved frontier.

    A stack-based agenda. Gaps push on top when emitted by a step.
    The compiler pops from the top — deepest child first (LIFO).
    When all children of a gap resolve, control returns to the next sibling.

    This is NOT history. It is the active execution surface.
    """

    def __init__(self):
        self.stack: list[LedgerEntry] = []
        self.chain_states: dict[str, ChainState] = {}  # chain_id → state
        self.resolved: list[str] = []   # gap hashes that have been resolved
        self.history: list[str] = []    # order of gap hashes as they were popped

    def push_origin(self, gap: Gap, chain_id: str):
        """Push an origin gap (from pre-diff). Creates a new chain."""
        entry = LedgerEntry(gap=gap, chain_id=chain_id, depth=0)
        self.stack.append(entry)
        self.chain_states[chain_id] = ChainState.OPEN

    def push_child(self, gap: Gap, chain_id: str, parent_gap: str, depth: int):
        """Push a child gap (emitted by a step addressing its parent).

        Inserted at the TOP of the stack — depth-first. The parent's
        chain is suspended until all children resolve.
        """
        entry = LedgerEntry(
            gap=gap, chain_id=chain_id,
            depth=depth, parent_gap=parent_gap,
        )
        self.stack.append(entry)

    def peek(self) -> LedgerEntry | None:
        """Look at the top of the stack without removing."""
        return self.stack[-1] if self.stack else None

    def pop(self) -> LedgerEntry | None:
        """Pop the top entry. This is the next gap to address."""
        if not self.stack:
            return None
        entry = self.stack.pop()
        self.history.append(entry.gap.hash)
        # Mark chain as active
        self.chain_states[entry.chain_id] = ChainState.ACTIVE
        return entry

    def resolve_gap(self, gap_hash: str):
        """Mark a gap as resolved. Check if its chain can close."""
        self.resolved.append(gap_hash)

    def is_empty(self) -> bool:
        return len(self.stack) == 0

    def size(self) -> int:
        return len(self.stack)

    def active_gaps(self) -> list[LedgerEntry]:
        """All entries currently on the stack."""
        return list(self.stack)

    def chain_is_complete(self, chain_id: str) -> bool:
        """Are all gaps in this chain resolved?"""
        for entry in self.stack:
            if entry.chain_id == chain_id:
                return False  # still has unresolved gaps on stack
        return True

    def close_chain(self, chain_id: str):
        self.chain_states[chain_id] = ChainState.CLOSED

    def suspend_chain(self, chain_id: str):
        self.chain_states[chain_id] = ChainState.SUSPENDED


# ── Governor ──────────────────────────────────────────────────────────────

class GovernorSignal(Enum):
    ALLOW = auto()       # continue — gap is converging
    CONSTRAIN = auto()   # chain too deep — force close
    REDIRECT = auto()    # stagnation — skip to next origin gap
    REVERT = auto()      # divergence — undo last mutation
    ACT = auto()         # perception saturated — execute mutation
    HALT = auto()        # all gaps resolved or pathological


@dataclass
class GovernorState:
    """Tracks epistemic vectors across steps for convergence detection."""
    vectors: list[list[float]] = field(default_factory=list)

    def record(self, epistemic: Epistemic):
        self.vectors.append(epistemic.as_vector())

    def information_gain(self) -> float:
        """Magnitude of the delta between last two state vectors.
        When this drops below threshold, perception is saturated."""
        if len(self.vectors) < 2:
            return 1.0  # assume high gain at start
        prev = self.vectors[-2]
        curr = self.vectors[-1]
        delta = [c - p for c, p in zip(curr, prev)]
        return math.sqrt(sum(d * d for d in delta))

    def is_stagnating(self) -> bool:
        """No meaningful movement in last N steps."""
        if len(self.vectors) < STAGNATION_WINDOW:
            return False
        recent = self.vectors[-STAGNATION_WINDOW:]
        gains = []
        for i in range(1, len(recent)):
            delta = [recent[i][j] - recent[i-1][j] for j in range(len(recent[0]))]
            gains.append(math.sqrt(sum(d * d for d in delta)))
        return all(g < SATURATION_THRESHOLD for g in gains)

    def is_diverging(self) -> bool:
        """Confidence dropped after the last step."""
        if len(self.vectors) < 2:
            return False
        # Confidence is index 1 in the vector
        return self.vectors[-1][1] < self.vectors[-2][1] - 0.15

    def is_oscillating(self) -> bool:
        """Confidence alternating up/down."""
        if len(self.vectors) < 4:
            return False
        confs = [v[1] for v in self.vectors[-4:]]
        diffs = [confs[i+1] - confs[i] for i in range(len(confs)-1)]
        return all(diffs[i] * diffs[i+1] < 0 for i in range(len(diffs)-1))


def govern(entry: LedgerEntry, chain_length: int, state: GovernorState) -> GovernorSignal:
    """Deterministic governor. Pure measurement on epistemic vectors."""

    # Chain too deep
    if chain_length > MAX_CHAIN_DEPTH:
        return GovernorSignal.CONSTRAIN

    # Pathology checks
    if state.is_diverging():
        return GovernorSignal.REVERT

    if state.is_oscillating():
        return GovernorSignal.REDIRECT

    if state.is_stagnating():
        return GovernorSignal.REDIRECT

    # Gap has vocab — check if it's observe or mutate
    vocab = entry.gap.vocab
    if vocab and is_mutate(vocab):
        # Mutation requested — check if observation is sufficient
        if entry.gap.scores.grounded >= 0.5 and entry.gap.scores.confidence >= 0.5:
            return GovernorSignal.ACT
        else:
            # Not enough evidence for mutation — need more observation
            return GovernorSignal.ALLOW

    return GovernorSignal.ALLOW


# ── Compiler ──────────────────────────────────────────────────────────────

class Compiler:
    """Structures execution from semantic emissions.

    The compiler's job:
      1. Receive emitted gaps from a step (emission)
      2. Decide which gaps are admissible (admission)
      3. Place admitted gaps into lawful ledger position (placement)
      4. Pop the next gap and route by vocab (sequencing)
      5. Enforce OMO rhythm (transition grammar)
      6. Track chain boundaries (chain lifecycle)
    """

    def __init__(self, trajectory: Trajectory):
        self.ledger = Ledger()
        self.trajectory = trajectory
        self.governor_state = GovernorState()
        self.active_chain: Chain | None = None
        self.last_was_mutation: bool = False  # OMO tracking

    # ── 1. Emission → Admission → Placement ──

    def emit(self, step: Step):
        """Process a step's gaps through the three-part lifecycle.

        Emission:   step.gaps are candidate gaps
        Admission:  gaps above threshold enter ledger; below dormant threshold → stored as dormant
        Placement:  admitted gaps push onto stack (depth-first)
        """
        for gap in step.gaps:
            combined = (0.6 * gap.scores.relevance + 0.4 * gap.scores.grounded)

            if combined < DORMANT_THRESHOLD:
                # Below dormant threshold — store but don't act
                gap.dormant = True
                continue

            if combined < ADMISSION_THRESHOLD:
                # Below admission but above dormant — store as dormant
                gap.dormant = True
                continue

            # Admitted — place on ledger
            gap.dormant = False

            if self.active_chain:
                # Child gap — push on top, depth-first
                self.ledger.push_child(
                    gap=gap,
                    chain_id=self.active_chain.hash,
                    parent_gap=step.hash,
                    depth=self.active_chain.length(),
                )
            else:
                # Origin gap — create new chain
                chain = Chain.create(origin_gap=gap.hash, first_step=step.hash)
                self.trajectory.add_chain(chain)
                self.ledger.push_origin(gap=gap, chain_id=chain.hash)

    def emit_origin_gaps(self, step: Step):
        """Emit gaps from the initial pre-diff as origin gaps.
        Each origin gap creates its own chain."""
        for gap in step.gaps:
            combined = (0.6 * gap.scores.relevance + 0.4 * gap.scores.grounded)

            if combined < DORMANT_THRESHOLD:
                gap.dormant = True
                continue

            if combined < ADMISSION_THRESHOLD:
                gap.dormant = True
                continue

            chain = Chain.create(origin_gap=gap.hash, first_step=step.hash)
            self.trajectory.add_chain(chain)
            self.ledger.push_origin(gap=gap, chain_id=chain.hash)

    # ── 2. Sequencing (pop + route) ──

    def next(self) -> tuple[LedgerEntry | None, GovernorSignal]:
        """Pop the next gap and determine what to do.

        Returns (entry, signal):
          - entry: the gap to address (None if ledger empty)
          - signal: governor's decision (ALLOW, ACT, CONSTRAIN, etc.)
        """
        if self.ledger.is_empty():
            return None, GovernorSignal.HALT

        entry = self.ledger.peek()
        if entry is None:
            return None, GovernorSignal.HALT

        # Find chain length
        chain = self.trajectory.chains.get(entry.chain_id)
        chain_length = chain.length() if chain else 0

        # Record epistemic state
        self.governor_state.record(entry.gap.scores)

        # Governor decision
        signal = govern(entry, chain_length, self.governor_state)

        if signal == GovernorSignal.CONSTRAIN:
            # Force-close this chain, move to next
            self.force_close_chain(entry.chain_id)
            return self.next()  # recurse to get next entry

        if signal == GovernorSignal.REDIRECT:
            # Skip this chain, try next origin gap
            self.skip_chain(entry.chain_id)
            return self.next()

        # Pop and return
        popped = self.ledger.pop()

        # Track active chain
        chain = self.trajectory.chains.get(popped.chain_id)
        if chain:
            self.active_chain = chain

        return popped, signal

    # ── 3. OMO Enforcement ──

    def validate_omo(self, vocab: str) -> bool:
        """Check if the proposed vocab respects O-M-O rhythm.

        Rules:
          - Mutation requires preceding observation (last_was_mutation must be False)
          - After mutation, next must be observation (postcondition handles this)
          - Observations can follow observations (OOO is fine)
        """
        if is_mutate(vocab) and self.last_was_mutation:
            # Can't mutate twice without observing between
            return False
        return True

    def record_execution(self, vocab: str, produced_commit: bool):
        """Record that a step was executed, for OMO tracking."""
        self.last_was_mutation = produced_commit

    def needs_postcondition(self) -> bool:
        """After a mutation, an observation postcondition must fire."""
        return self.last_was_mutation

    # ── 4. Chain Management ──

    def resolve_current_gap(self, gap_hash: str):
        """Mark the current gap as resolved. Check chain completion."""
        self.ledger.resolve_gap(gap_hash)

        if self.active_chain:
            chain_id = self.active_chain.hash
            if self.ledger.chain_is_complete(chain_id):
                self.ledger.close_chain(chain_id)
                self.active_chain.resolved = True
                self.active_chain = None

    def add_step_to_chain(self, step_hash: str):
        """Record a step in the active chain."""
        if self.active_chain:
            self.active_chain.add_step(step_hash)

    def force_close_chain(self, chain_id: str):
        """Force-close a chain (too deep or pathological)."""
        # Remove all entries for this chain from the stack
        self.ledger.stack = [
            e for e in self.ledger.stack if e.chain_id != chain_id
        ]
        self.ledger.close_chain(chain_id)
        chain = self.trajectory.chains.get(chain_id)
        if chain:
            chain.resolved = True
            chain.desc = f"force-closed (depth exceeded or pathological)"

    def skip_chain(self, chain_id: str):
        """Skip a chain (stagnation). Move its entries to the bottom."""
        skipped = [e for e in self.ledger.stack if e.chain_id == chain_id]
        remaining = [e for e in self.ledger.stack if e.chain_id != chain_id]
        self.ledger.stack = skipped + remaining  # skipped at bottom, remaining on top
        self.ledger.suspend_chain(chain_id)

    # ── 5. Status ──

    def is_done(self) -> bool:
        return self.ledger.is_empty()

    def gap_count(self) -> int:
        return self.ledger.size()

    def active_chain_id(self) -> str | None:
        return self.active_chain.hash if self.active_chain else None

    def chain_summary(self) -> list[dict]:
        """Summary of all chains for debugging."""
        summaries = []
        for chain_id, state in self.ledger.chain_states.items():
            chain = self.trajectory.chains.get(chain_id)
            summaries.append({
                "chain_id": chain_id,
                "state": state.name,
                "steps": chain.length() if chain else 0,
                "origin": chain.origin_gap if chain else "?",
            })
        return summaries

    def render_ledger(self) -> str:
        """Render current ledger state for debugging."""
        if self.ledger.is_empty():
            return "(ledger empty)"
        lines = [f"Ledger ({self.ledger.size()} entries):"]
        for i, entry in enumerate(reversed(self.ledger.stack)):
            marker = "→" if i == 0 else " "
            vocab_tag = f" [{entry.gap.vocab}]" if entry.gap.vocab else ""
            lines.append(
                f"  {marker} [{entry.gap.hash[:8]}] d={entry.depth} "
                f"chain={entry.chain_id[:8]}{vocab_tag} — {entry.gap.desc[:60]}"
            )
        return "\n".join(lines)
