"""The canonical pool state machine.

The adjacency table is the single source of truth for the lifecycle, so these tests
assert the *properties* that matter rather than restating the table: a pool cannot lock
without funding, and it cannot rewind once the money is captured.
"""

from __future__ import annotations

import pytest

from pool.domain.models import COMMITTED_POOL_STATUSES, PoolStatus
from pool.domain.state import (
    ALLOWED,
    IllegalTransition,
    assert_transition,
    can_transition,
    is_committed,
    is_open_to_joining,
    is_terminal,
)


def test_every_status_appears_in_the_adjacency_table():
    assert set(ALLOWED) == set(PoolStatus)


def test_terminal_statuses_have_no_way_out():
    for status in (PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED):
        assert ALLOWED[status] == frozenset()
        assert is_terminal(status)


def test_re_asserting_the_current_status_is_a_no_op():
    for status in PoolStatus:
        assert can_transition(status, status)
        assert assert_transition(status, status) == status


def test_the_happy_path_is_walkable_end_to_end():
    path = [
        PoolStatus.FORMING,
        PoolStatus.HOST_RECRUITING,
        PoolStatus.HOST_SELECTED,
        PoolStatus.FINAL_OFFER,
        PoolStatus.FUNDING,
        PoolStatus.LOCKED,
        PoolStatus.PURCHASE_READY,
        PoolStatus.PURCHASED,
        PoolStatus.DISTRIBUTING,
        PoolStatus.COMPLETED,
    ]
    current = path[0]
    for nxt in path[1:]:
        current = assert_transition(current, nxt)
    assert current == PoolStatus.COMPLETED


def test_nothing_reaches_locked_except_through_funding_or_recovery():
    """A pool cannot be locked before authorisations exist (§56)."""
    sources = {s for s, targets in ALLOWED.items() if PoolStatus.LOCKED in targets}
    assert sources == {PoolStatus.FUNDING, PoolStatus.RECOVERING}


def test_a_forming_pool_cannot_skip_straight_to_a_final_offer():
    with pytest.raises(IllegalTransition):
        assert_transition(PoolStatus.FORMING, PoolStatus.FINAL_OFFER)


def test_a_forming_pool_cannot_skip_straight_to_lock():
    with pytest.raises(IllegalTransition):
        assert_transition(PoolStatus.FORMING, PoolStatus.LOCKED)


def test_captured_pools_cannot_rewind_into_a_forming_state():
    """Once money is captured and the supplier order is committed, there is no undo."""
    forming = {
        PoolStatus.FORMING,
        PoolStatus.HOST_RECRUITING,
        PoolStatus.HOST_SELECTED,
        PoolStatus.FINAL_OFFER,
        PoolStatus.FUNDING,
        PoolStatus.RECOVERING,
    }
    for status in COMMITTED_POOL_STATUSES:
        assert ALLOWED[status] & forming == frozenset()


def test_committed_statuses_are_recognised():
    assert is_committed(PoolStatus.LOCKED)
    assert is_committed(PoolStatus.PURCHASED)
    assert not is_committed(PoolStatus.FUNDING)


def test_only_early_statuses_accept_new_members():
    assert is_open_to_joining(PoolStatus.FORMING)
    assert is_open_to_joining(PoolStatus.HOST_RECRUITING)
    assert not is_open_to_joining(PoolStatus.FINAL_OFFER)
    assert not is_open_to_joining(PoolStatus.LOCKED)


def test_recovery_can_return_to_several_earlier_stages():
    """Recovery may need a new host, a fresh quote, or simply more funded demand."""
    assert {
        PoolStatus.FUNDING,
        PoolStatus.FINAL_OFFER,
        PoolStatus.HOST_RECRUITING,
        PoolStatus.LOCKED,
    } <= ALLOWED[PoolStatus.RECOVERING]


def test_an_illegal_transition_names_both_states():
    with pytest.raises(IllegalTransition) as exc:
        assert_transition(PoolStatus.COMPLETED, PoolStatus.FORMING)
    assert "completed" in str(exc.value) and "forming" in str(exc.value)
