from __future__ import annotations

import pytest

from pool.domain.models import PoolStatus
from pool.domain.state import ALLOWED, IllegalTransition, assert_transition, can_transition, is_terminal


class TestTransitions:
    @pytest.mark.parametrize(
        "current,requested",
        [
            (PoolStatus.CANDIDATE, PoolStatus.INVITING),
            (PoolStatus.CANDIDATE, PoolStatus.THRESHOLD_MET),
            (PoolStatus.INVITING, PoolStatus.THRESHOLD_MET),
            (PoolStatus.THRESHOLD_MET, PoolStatus.CONFIRMED),
            (PoolStatus.THRESHOLD_MET, PoolStatus.RECOVERING),
            (PoolStatus.RECOVERING, PoolStatus.THRESHOLD_MET),
            (PoolStatus.CONFIRMED, PoolStatus.RECOVERING),
            (PoolStatus.CONFIRMED, PoolStatus.COMPLETED),
        ],
    )
    def test_legal_transitions(self, current, requested):
        assert can_transition(current, requested)
        assert assert_transition(current, requested) == requested

    @pytest.mark.parametrize(
        "current,requested",
        [
            (PoolStatus.CANDIDATE, PoolStatus.CONFIRMED),   # cannot skip the threshold
            (PoolStatus.CANDIDATE, PoolStatus.COMPLETED),
            (PoolStatus.INVITING, PoolStatus.CONFIRMED),
            (PoolStatus.FAILED, PoolStatus.THRESHOLD_MET),  # terminal
            (PoolStatus.COMPLETED, PoolStatus.RECOVERING),
            (PoolStatus.EXPIRED, PoolStatus.INVITING),
        ],
    )
    def test_illegal_transitions_raise(self, current, requested):
        assert not can_transition(current, requested)
        with pytest.raises(IllegalTransition):
            assert_transition(current, requested)

    def test_reasserting_current_state_is_idempotent(self):
        for status in PoolStatus:
            assert assert_transition(status, status) == status

    def test_terminal_states_have_no_exits(self):
        for status in (PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED):
            assert is_terminal(status)
            assert ALLOWED[status] == frozenset()

    def test_every_status_is_covered_by_the_table(self):
        """A status missing from ALLOWED would KeyError at runtime instead of failing safe."""
        assert set(ALLOWED.keys()) == set(PoolStatus)

    def test_a_confirmed_pool_can_still_be_repaired(self):
        """Dropouts happen after confirmation too; the machine must not trap them."""
        assert can_transition(PoolStatus.CONFIRMED, PoolStatus.RECOVERING)
