"""Pool Days, lifecycle deadlines, and the authority to buy early."""

from __future__ import annotations

from datetime import date, timedelta

from pool.domain.models import PoolDaySchedule
from pool.domain.timing import (
    build_timing,
    evaluate_timing,
    next_pool_day,
    next_weekday_on_or_after,
    pickup_day_acceptable,
)
from tests.conftest import make_community, make_need


def test_next_pool_day_respects_community_configuration():
    """Saturday is not hardcoded anywhere — a Community picks its own day (§23)."""
    wednesday = PoolDaySchedule(distribution_weekday=2)
    monday = date(2026, 8, 17)  # a Monday
    assert next_pool_day(monday, wednesday).weekday() == 2
    assert next_pool_day(monday, wednesday) == date(2026, 8, 19)


def test_a_pool_cannot_form_and_distribute_on_the_same_day():
    schedule = PoolDaySchedule(distribution_weekday=5)
    saturday = date(2026, 8, 15)
    assert saturday.weekday() == 5
    assert next_pool_day(saturday, schedule) == saturday + timedelta(days=7)


def test_next_weekday_on_or_after_includes_today():
    monday = date(2026, 8, 17)
    assert next_weekday_on_or_after(monday, 0) == monday


def test_deadlines_are_ordered_host_then_offer_then_lock_then_distribution():
    """Host selection must precede the final offer, which must precede lock (§35)."""
    community = make_community()
    timing = build_timing(community=community, today=date(2026, 8, 17))
    assert (
        timing.host_acceptance_deadline
        <= timing.final_offer_at
        <= timing.authorization_deadline
        <= timing.lock_at
        <= timing.purchase_by
        <= timing.distribution_starts_at
        < timing.distribution_ends_at
    )


def test_distribution_window_uses_the_configured_hours():
    community = make_community(
        schedule=PoolDaySchedule(distribution_start_hour=9, distribution_end_hour=11)
    )
    timing = build_timing(community=community, today=date(2026, 8, 17))
    assert "T09:00" in timing.distribution_starts_at
    assert "T11:00" in timing.distribution_ends_at


# --------------------------------------------------------------------------- windows


def test_routine_restock_is_not_a_pull_forward():
    need = make_need("n", "m", "p", 2, days_out=10, flexibility_days=10, routine_lead_days=10)
    verdict = evaluate_timing(need, date.today() + timedelta(days=7))
    assert verdict.eligible
    assert verdict.is_future_pull_forward is False


def test_buying_earlier_than_normal_but_inside_the_authorised_window_is_a_pull_forward():
    need = make_need("n", "m", "p", 2, days_out=30, flexibility_days=30, routine_lead_days=7)
    verdict = evaluate_timing(need, date.today() + timedelta(days=5))
    assert verdict.eligible
    assert verdict.is_future_pull_forward is True
    assert verdict.days_early == 25


def test_purchase_before_the_authorised_date_is_refused():
    need = make_need("n", "m", "p", 2, days_out=30, flexibility_days=3, routine_lead_days=3)
    verdict = evaluate_timing(need, date.today() + timedelta(days=5))
    assert verdict.eligible is False
    assert "earlier than the member authorised" in verdict.reason


def test_purchase_after_the_need_date_is_refused():
    need = make_need("n", "m", "p", 2, days_out=3, flexibility_days=30)
    verdict = evaluate_timing(need, date.today() + timedelta(days=10))
    assert verdict.eligible is False
    assert "latest useful date" in verdict.reason


def test_inactive_need_is_never_eligible():
    need = make_need("n", "m", "p", 2, active=False)
    assert evaluate_timing(need, date.today()).eligible is False


def test_a_need_with_no_flexibility_can_only_be_served_on_its_own_date():
    need = make_need("n", "m", "p", 2, days_out=10, flexibility_days=0)
    exact = date.today() + timedelta(days=10)
    assert evaluate_timing(need, exact).eligible
    assert evaluate_timing(need, exact - timedelta(days=1)).eligible is False


# --------------------------------------------------------------------------- pickup


def test_empty_pickup_availability_means_any_day():
    assert pickup_day_acceptable([], date(2026, 8, 15)) is True


def test_pickup_availability_is_respected():
    saturday = date(2026, 8, 15)
    assert pickup_day_acceptable([5], saturday) is True
    assert pickup_day_acceptable([0, 1, 2], saturday) is False
