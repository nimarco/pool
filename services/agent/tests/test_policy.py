"""Smart Join — the deterministic autonomy boundary.

This is the module that decides whether Pool may commit someone's money without
asking, so these tests are the ones that matter most if they ever start failing.
"""

from __future__ import annotations

from datetime import date

import pytest

from pool.domain.models import AutonomyMode, SubstitutionPolicy
from pool.domain.policy import (
    AUTONOMOUS_ACTIONS,
    CONSEQUENTIAL_ACTIONS,
    JoinVerdictKind,
    evaluate_smart_join,
    requires_human_approval,
)
from tests.conftest import make_member, make_need


def _evaluate(member=None, need=None, **overrides):
    member = member or make_member("m1")
    need = need or make_need("n1", "m1", "p_protein", 2)
    args = {
        "household_id": member.id,
        "policy": member.autonomy,
        "need": need,
        "landed_cost_cents": 5000,
        "net_savings_bps": 2500,
        "travel_minutes": 5,
        "is_exact_product": True,
        "substitution_authorised": True,
        "pickup_is_public": True,
        "distribution_day": None,
    }
    args.update(overrides)
    return evaluate_smart_join(**args)


def test_a_fully_satisfied_policy_auto_approves():
    verdict = _evaluate()
    assert verdict.kind == JoinVerdictKind.AUTO_APPROVED
    assert verdict.eligible_for_auto_join is True
    assert verdict.failed_rules == []


def test_ask_me_never_auto_joins():
    member = make_member("m1", mode=AutonomyMode.ASK_ME)
    verdict = _evaluate(member)
    assert verdict.kind == JoinVerdictKind.HUMAN_APPROVAL_REQUIRED
    assert "autonomy_mode" in verdict.failed_rules


def test_the_stricter_of_policy_and_need_wins_on_savings():
    member = make_member("m1", min_savings_pct=10)
    need = make_need("n1", "m1", "p_protein", 2, min_savings_pct=30)
    assert _evaluate(member, need, net_savings_bps=2000).kind == (
        JoinVerdictKind.HUMAN_APPROVAL_REQUIRED
    )
    assert _evaluate(member, need, net_savings_bps=3000).kind == JoinVerdictKind.AUTO_APPROVED


def test_the_stricter_of_policy_and_need_wins_on_spend():
    member = make_member("m1", max_spend=10_000)
    need = make_need("n1", "m1", "p_protein", 2, max_spend=4000)
    assert "max_spend" in _evaluate(member, need, landed_cost_cents=5000).failed_rules
    assert _evaluate(member, need, landed_cost_cents=3000).kind == JoinVerdictKind.AUTO_APPROVED


def test_travel_ceiling_is_enforced():
    member = make_member("m1", max_travel=10)
    assert "max_travel" in _evaluate(member, travel_minutes=25).failed_rules


def test_savings_are_net_not_gross():
    """A pool whose gross saving looks fine but nets out below the floor must be asked."""
    member = make_member("m1", min_savings_pct=20)
    assert _evaluate(member, net_savings_bps=1500).kind == (
        JoinVerdictKind.HUMAN_APPROVAL_REQUIRED
    )


def test_a_product_outside_substitution_authority_is_a_hard_no():
    """No prompt can create authority the member never gave (§21)."""
    verdict = _evaluate(is_exact_product=False, substitution_authorised=False)
    assert verdict.kind == JoinVerdictKind.NOT_ALLOWED


def test_an_authorised_substitute_still_needs_approval_under_a_strict_standing_policy():
    member = make_member("m1", substitution=SubstitutionPolicy.EXACT_ONLY)
    verdict = _evaluate(member, is_exact_product=False, substitution_authorised=True)
    assert verdict.kind == JoinVerdictKind.HUMAN_APPROVAL_REQUIRED


def test_a_pre_authorised_substitute_auto_joins():
    member = make_member("m1", substitution=SubstitutionPolicy.APPROVED_BRANDS)
    verdict = _evaluate(member, is_exact_product=False, substitution_authorised=True)
    assert verdict.kind == JoinVerdictKind.AUTO_APPROVED


def test_public_pickup_preference_is_respected():
    member = make_member("m1", public_only=True)
    assert "public_pickup" in _evaluate(member, pickup_is_public=False).failed_rules
    assert _evaluate(member, pickup_is_public=True).kind == JoinVerdictKind.AUTO_APPROVED


def test_a_scheduling_conflict_is_a_hard_no():
    """No amount of approving fixes being unavailable on the distribution day."""
    member = make_member("m1", pickup_weekdays=[0, 1])
    saturday = date(2026, 8, 15)
    verdict = _evaluate(member, distribution_day=saturday)
    assert verdict.kind == JoinVerdictKind.NOT_ALLOWED
    assert "pickup_day" in verdict.failed_rules


def test_every_rule_is_evaluated_so_the_ui_can_show_them_all():
    member = make_member("m1", mode=AutonomyMode.ASK_ME, max_travel=1, max_spend=1)
    verdict = _evaluate(member, travel_minutes=99, landed_cost_cents=99_999)
    assert len(verdict.failed_rules) >= 3
    assert all(isinstance(c.detail, str) and c.detail for c in verdict.checks)


def test_verdict_serialises_with_its_audit_trail():
    payload = _evaluate().to_dict()
    assert payload["verdict"] == "auto_approved"
    assert isinstance(payload["checks"], list)
    assert {"rule", "passed", "detail", "hard"} <= set(payload["checks"][0])


# --------------------------------------------------------------------------- actions


@pytest.mark.parametrize("action", sorted(CONSEQUENTIAL_ACTIONS))
def test_consequential_actions_require_a_human(action):
    assert requires_human_approval(action) is True


@pytest.mark.parametrize("action", sorted(AUTONOMOUS_ACTIONS))
def test_autonomous_actions_do_not(action):
    assert requires_human_approval(action) is False


def test_an_unclassified_action_fails_closed():
    """A new verb nobody classified is not evidence that it is safe."""
    assert requires_human_approval("wire_money_to_a_stranger") is True


def test_the_two_action_sets_do_not_overlap():
    assert frozenset() == AUTONOMOUS_ACTIONS & CONSEQUENTIAL_ACTIONS
