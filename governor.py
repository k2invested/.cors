"""Governor — deterministic convergence monitor.

Measures epistemic vectors. Decides: allow, constrain, redirect, revert, halt.
Pure math. No LLM. Watches the numbers and raises flags.
"""

from dataclasses import dataclass
from enum import Enum, auto
from step import Step, Gap


CONFIDENCE_THRESHOLD = 0.8
MAX_CHAIN_DEPTH = 10
STAGNATION_WINDOW = 3


class Signal(Enum):
    ALLOW = auto()       # gaps converging, continue
    CONSTRAIN = auto()   # exploration too deep, limit
    REDIRECT = auto()    # stagnation, force different gap
    REVERT = auto()      # divergence, undo last
    ACT = auto()         # perception saturated, gaps remain — take action
    HALT = auto()        # all gaps closed or pathological — done


@dataclass
class GovernorState:
    """Tracks epistemic history for convergence detection."""
    confidence_history: list[float]

    def record(self, avg_confidence: float):
        self.confidence_history.append(avg_confidence)

    def is_stagnating(self) -> bool:
        if len(self.confidence_history) < STAGNATION_WINDOW:
            return False
        recent = self.confidence_history[-STAGNATION_WINDOW:]
        # No movement: max - min < epsilon
        return (max(recent) - min(recent)) < 0.05

    def is_diverging(self) -> bool:
        if len(self.confidence_history) < 2:
            return False
        return self.confidence_history[-1] < self.confidence_history[-2] - 0.1

    def is_oscillating(self) -> bool:
        if len(self.confidence_history) < 4:
            return False
        recent = self.confidence_history[-4:]
        # Alternating up/down
        diffs = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        return all(diffs[i] * diffs[i+1] < 0 for i in range(len(diffs)-1))


def govern(gaps: list[Gap], step: Step, state: GovernorState) -> Signal:
    """Deterministic governor. Pure measurement."""

    # No gaps — done
    if not gaps:
        return Signal.HALT

    # All gaps above threshold — done
    if all(g.confidence >= CONFIDENCE_THRESHOLD for g in gaps):
        return Signal.HALT

    # Track average confidence
    open_gaps = [g for g in gaps if g.confidence < CONFIDENCE_THRESHOLD]
    avg_conf = sum(g.confidence for g in open_gaps) / len(open_gaps)
    state.record(avg_conf)

    # Pathology checks
    if state.is_diverging():
        return Signal.REVERT

    if state.is_oscillating():
        return Signal.REDIRECT

    if state.is_stagnating():
        return Signal.REDIRECT

    # Exploration too deep
    if step.pre.depth() > MAX_CHAIN_DEPTH:
        return Signal.CONSTRAIN

    # Perception saturated — chain is built, gaps remain
    # If the step explored hashes but gaps didn't narrow, action is needed
    if step.pre.depth() > 0 and avg_conf > 0.5:
        return Signal.ACT

    return Signal.ALLOW


def widest_gap(gaps: list[Gap]) -> Gap | None:
    """Select the gap furthest from confidence threshold."""
    open_gaps = [g for g in gaps if g.confidence < CONFIDENCE_THRESHOLD]
    if not open_gaps:
        return None
    return min(open_gaps, key=lambda g: g.confidence)
