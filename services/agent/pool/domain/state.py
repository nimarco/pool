"""Pool state machine.

The set of legal transitions is fixed here. The agent may *request* a transition
through a tool, but this module decides whether it is allowed — an LLM never moves
a pool into a state that violates an invariant (AGENTS.md §5).
"""

from __future__ import annotations

from .models import TERMINAL_POOL_STATUSES, PoolStatus


class IllegalTransition(ValueError):
    """Raised when a requested pool state transition is not permitted."""

    def __init__(self, current: PoolStatus, requested: PoolStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"illegal pool transition: {current.value} -> {requested.value}")


# Explicit adjacency. Anything not listed is illegal by construction.
ALLOWED: dict[PoolStatus, frozenset[PoolStatus]] = {
    PoolStatus.CANDIDATE: frozenset(
        {PoolStatus.INVITING, PoolStatus.THRESHOLD_MET, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.INVITING: frozenset(
        {PoolStatus.THRESHOLD_MET, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.THRESHOLD_MET: frozenset(
        {PoolStatus.CONFIRMED, PoolStatus.RECOVERING, PoolStatus.INVITING, PoolStatus.EXPIRED}
    ),
    # A dropout after confirmation still has to be repairable.
    PoolStatus.CONFIRMED: frozenset(
        {PoolStatus.RECOVERING, PoolStatus.COMPLETED, PoolStatus.EXPIRED}
    ),
    PoolStatus.RECOVERING: frozenset(
        {PoolStatus.THRESHOLD_MET, PoolStatus.INVITING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.FAILED: frozenset(),
    PoolStatus.EXPIRED: frozenset(),
    PoolStatus.COMPLETED: frozenset(),
}


def can_transition(current: PoolStatus, requested: PoolStatus) -> bool:
    if current == requested:
        return True  # idempotent re-assertion of the current state
    return requested in ALLOWED[current]


def assert_transition(current: PoolStatus, requested: PoolStatus) -> PoolStatus:
    """Return the new status, or raise. Re-asserting the current status is a no-op."""
    if current == requested:
        return current
    if requested not in ALLOWED[current]:
        raise IllegalTransition(current, requested)
    return requested


def is_terminal(status: PoolStatus) -> bool:
    return status in TERMINAL_POOL_STATUSES
