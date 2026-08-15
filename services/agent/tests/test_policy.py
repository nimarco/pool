"""Smart Join is the autonomy boundary. Every rule gets a test that proves it can
block an auto-join, because a policy engine that never says no is decoration."""

from __future__ import annotations

from pool.domain.models import AutonomyMode, AutonomyPolicy
from pool.domain.policy import (
    AUTONOMOUS_ACTIONS,
    CONSEQUENTIAL_ACTIONS,
    evaluate_smart_join,
    requires_human_approval,
)

from .conftest import make_need

PASSING = dict(
    cost_cents=1500,
    savings_bps_value=3400,  # 34%
    travel_minutes=5,
    is_exact_product=True,
    pickup_is_public=True,
)


def verdict(policy: AutonomyPolicy, **overrides):
    need = overrides.pop("need", make_need("n1", "h1", "p_rice", 10))
    kwargs = {**PASSING, **overrides}
    return evaluate_smart_join(household_id="h1", policy=policy, need=need, **kwargs)


def smart(**kw) -> AutonomyPolicy:
    base = dict(
        mode=AutonomyMode.SMART_JOIN,
        min_savings_pct=20,
        max_total_cost_cents=5000,
        max_travel_minutes=15,
        allow_substitutes=False,
        public_pickup_only=True,
    )
    base.update(kw)
    return AutonomyPolicy(**base)


class TestAllRulesPass:
    def test_auto_join_when_everything_passes(self):
        v = verdict(smart())
        assert v.eligible_for_auto_join is True
        assert v.failed_rules == []
        assert len(v.checks) == 6


class TestEachRuleCanBlock:
    def test_ask_me_mode_blocks(self):
        v = verdict(smart(mode=AutonomyMode.ASK_ME))
        assert v.eligible_for_auto_join is False
        assert "autonomy_mode" in v.failed_rules

    def test_savings_below_policy_floor_blocks(self):
        v = verdict(smart(min_savings_pct=40))
        assert v.eligible_for_auto_join is False
        assert "min_savings" in v.failed_rules

    def test_savings_below_the_needs_own_floor_blocks(self):
        """The stricter of policy and need wins."""
        need = make_need("n1", "h1", "p_rice", 10, min_savings_pct=50)
        v = verdict(smart(min_savings_pct=10), need=need)
        assert "min_savings" in v.failed_rules

    def test_cost_above_policy_cap_blocks(self):
        v = verdict(smart(max_total_cost_cents=1000))
        assert "max_spend" in v.failed_rules

    def test_cost_above_the_needs_own_cap_blocks(self):
        need = make_need("n1", "h1", "p_rice", 10, max_spend=500)
        v = verdict(smart(max_total_cost_cents=100_000), need=need)
        assert "max_spend" in v.failed_rules

    def test_travel_over_limit_blocks(self):
        v = verdict(smart(max_travel_minutes=3))
        assert "max_travel" in v.failed_rules

    def test_substitute_blocked_without_permission(self):
        v = verdict(smart(allow_substitutes=False), is_exact_product=False)
        assert "substitution" in v.failed_rules

    def test_substitute_needs_both_policy_and_need_consent(self):
        need_no = make_need("n1", "h1", "p_rice", 10, accept_substitutes=False)
        assert "substitution" in verdict(
            smart(allow_substitutes=True), need=need_no, is_exact_product=False
        ).failed_rules

        need_yes = make_need("n1", "h1", "p_rice", 10, accept_substitutes=True)
        assert verdict(
            smart(allow_substitutes=True), need=need_yes, is_exact_product=False
        ).eligible_for_auto_join is True

    def test_private_pickup_blocks_when_public_required(self):
        v = verdict(smart(public_pickup_only=True), pickup_is_public=False)
        assert "public_pickup" in v.failed_rules

    def test_private_pickup_allowed_when_household_permits(self):
        v = verdict(smart(public_pickup_only=False), pickup_is_public=False)
        assert v.eligible_for_auto_join is True


class TestBoundaries:
    def test_savings_exactly_at_threshold_passes(self):
        assert verdict(smart(min_savings_pct=34), savings_bps_value=3400).eligible_for_auto_join

    def test_savings_one_bp_under_fails(self):
        assert not verdict(smart(min_savings_pct=34), savings_bps_value=3399).eligible_for_auto_join

    def test_cost_exactly_at_cap_passes(self):
        assert verdict(smart(max_total_cost_cents=1500), cost_cents=1500).eligible_for_auto_join

    def test_travel_exactly_at_limit_passes(self):
        assert verdict(smart(max_travel_minutes=5), travel_minutes=5).eligible_for_auto_join


class TestAuditTrail:
    def test_all_checks_are_evaluated_not_short_circuited(self):
        """The UI must be able to show every failing rule, not just the first."""
        v = verdict(smart(min_savings_pct=99, max_travel_minutes=0, max_total_cost_cents=1))
        assert set(v.failed_rules) >= {"min_savings", "max_travel", "max_spend"}
        assert len(v.checks) == 6

    def test_verdict_serialises_for_the_ui(self):
        d = verdict(smart(mode=AutonomyMode.ASK_ME)).to_dict()
        assert d["eligible_for_auto_join"] is False
        assert d["mode"] == "ask_me"
        assert all({"rule", "passed", "detail"} <= set(c) for c in d["checks"])


class TestActionClassification:
    def test_the_two_action_sets_are_disjoint(self):
        assert AUTONOMOUS_ACTIONS.isdisjoint(CONSEQUENTIAL_ACTIONS)

    def test_consequential_actions_require_approval(self):
        for action in CONSEQUENTIAL_ACTIONS:
            assert requires_human_approval(action) is True

    def test_safe_actions_do_not(self):
        for action in AUTONOMOUS_ACTIONS:
            assert requires_human_approval(action) is False

    def test_unknown_actions_are_treated_as_consequential(self):
        """An action nobody classified is not evidence that it is safe."""
        assert requires_human_approval("wire_the_neighbours_money") is True
