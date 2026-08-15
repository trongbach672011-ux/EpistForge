"""Explicit state-machine transitions for the research protocol."""

from __future__ import annotations

from collections.abc import Mapping

from .models import ResearchState


ALLOWED_TRANSITIONS: Mapping[ResearchState, frozenset[ResearchState]] = {
    ResearchState.IDEA: frozenset({ResearchState.HYPOTHESIS}),
    ResearchState.HYPOTHESIS: frozenset({ResearchState.CRITIQUED}),
    ResearchState.CRITIQUED: frozenset({ResearchState.TESTABLE, ResearchState.REJECTED}),
    ResearchState.TESTABLE: frozenset({ResearchState.EXPERIMENT_REGISTERED}),
    ResearchState.EXPERIMENT_REGISTERED: frozenset({ResearchState.EXECUTED}),
    ResearchState.EXECUTED: frozenset(
        {ResearchState.SUPPORTED, ResearchState.REFUTED, ResearchState.INCONCLUSIVE}
    ),
    ResearchState.SUPPORTED: frozenset({ResearchState.VERIFIED, ResearchState.DISPUTED}),
    ResearchState.VERIFIED: frozenset(
        {ResearchState.NOVELTY_CHECKED, ResearchState.PROVISIONAL_KNOWLEDGE}
    ),
    ResearchState.NOVELTY_CHECKED: frozenset({ResearchState.PROVISIONAL_KNOWLEDGE}),
    ResearchState.PROVISIONAL_KNOWLEDGE: frozenset({ResearchState.DISPUTED}),
    ResearchState.DISPUTED: frozenset({ResearchState.RETRACTED, ResearchState.VERIFIED}),
}


def is_allowed_transition(current: ResearchState, target: ResearchState) -> bool:
    """Return whether the exact transition is registered in the protocol."""

    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def validate_transition(current: ResearchState, target: ResearchState) -> None:
    """Raise ``ValueError`` for any transition not explicitly in the spec."""

    if not is_allowed_transition(current, target):
        raise ValueError(f"Invalid research state transition: {current.value} -> {target.value}")
