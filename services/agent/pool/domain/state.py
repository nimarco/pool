"""Pool state machine.

The set of legal transitions is fixed here. The agent may *request* a transition
through a tool, but this module decides whether it is allowed — an LLM never moves
a pool into a state that violates an invariant (AGENTS.md §5).

The adjacency below is the canonical lifecycle of §18. There is exactly one such
diagram in this repository; the architecture doc renders this table rather than
maintaining a second copy that can drift.
"""

from __future__ import annotations

from .models import COMMITTED_POOL_STATUSES, TERMINAL_POOL_STATUSES, PoolStatus


class IllegalTransition(ValueError):
    """Raised when a requested pool state transition is not permitted."""

    def __init__(self, current: PoolStatus, requested: PoolStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"illegal pool transition: {current.value} -> {requested.value}")


# Explicit adjacency. Anything not listed is illegal by construction.
#
# Two properties are load-bearing and asserted in tests:
#   * Nothing can reach LOCKED except through FUNDING or RECOVERING — a pool cannot
#     be locked before authorisations exist.
#   * Nothing can leave the post-capture states back into a forming state — once
#     money is captured and the supplier order is committed, the pool cannot rewind.
ALLOWED: dict[PoolStatus, frozenset[PoolStatus]] = {
    PoolStatus.FORMING: frozenset(
        {PoolStatus.HOST_RECRUITING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.HOST_RECRUITING: frozenset(
        # Back to FORMING when demand drops below MOQ again while recruiting.
        {PoolStatus.HOST_SELECTED, PoolStatus.FORMING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.HOST_SELECTED: frozenset(
        # A host can fall through before the final offer is issued.
        {PoolStatus.FINAL_OFFER, PoolStatus.HOST_RECRUITING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.FINAL_OFFER: frozenset(
        {PoolStatus.FUNDING, PoolStatus.RECOVERING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.FUNDING: frozenset(
        {PoolStatus.LOCKED, PoolStatus.RECOVERING, PoolStatus.FAILED, PoolStatus.EXPIRED}
    ),
    PoolStatus.RECOVERING: frozenset(
        # Recovery may need a new host, a fresh quote, or simply more funded demand.
        {
            PoolStatus.FUNDING,
            PoolStatus.LOCKED,
            PoolStatus.FINAL_OFFER,
            PoolStatus.HOST_RECRUITING,
            PoolStatus.FAILED,
            PoolStatus.EXPIRED,
        }
    ),
    PoolStatus.LOCKED: frozenset({PoolStatus.PURCHASE_READY, PoolStatus.FAILED}),
    PoolStatus.PURCHASE_READY: frozenset({PoolStatus.PURCHASED, PoolStatus.FAILED}),
    PoolStatus.PURCHASED: frozenset({PoolStatus.DISTRIBUTING, PoolStatus.FAILED}),
    PoolStatus.DISTRIBUTING: frozenset({PoolStatus.COMPLETED, PoolStatus.FAILED}),
    PoolStatus.FAILED: frozenset(),
    PoolStatus.EXPIRED: frozenset(),
    PoolStatus.COMPLETED: frozenset(),
}

#: Statuses in which more provisional demand can still join.
OPEN_TO_JOINING = frozenset(
    {PoolStatus.FORMING, PoolStatus.HOST_RECRUITING, PoolStatus.RECOVERING}
)

#: Statuses in which a supplier quote may still be refreshed and re-priced.
REPRICEABLE = frozenset(
    {
        PoolStatus.FORMING,
        PoolStatus.HOST_RECRUITING,
        PoolStatus.HOST_SELECTED,
        PoolStatus.FINAL_OFFER,
        PoolStatus.FUNDING,
        PoolStatus.RECOVERING,
    }
)


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


def is_committed(status: PoolStatus) -> bool:
    """True once buyers have been charged and the supplier order is committed (§59)."""
    return status in COMMITTED_POOL_STATUSES


def is_open_to_joining(status: PoolStatus) -> bool:
    return status in OPEN_TO_JOINING
