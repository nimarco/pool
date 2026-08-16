"""Host evaluation, ranking, and the offer lifecycle.

The fulfilment side is where a group-buying system quietly fails, so the tests here are
about refusal as much as selection: an ineligible host must be ineligible for a stated
factual reason, and clicking "offer to host" must never be enough to claim the job.
"""

from __future__ import annotations

from datetime import date

from pool.domain.economics import compute_host_reward
from pool.domain.hosting import HostJob, estimate_weight_kg, evaluate_host, rank_hosts
from pool.domain.models import HostRewardConfig, PickupPermission, PickupSite
from tests.conftest import COMM, make_host_profile

SATURDAY = date(2026, 8, 15)


def _site(public: bool = True, permission=PickupPermission.DEMO) -> PickupSite:
    return PickupSite("s1", "Union", COMM, 38.6488, -90.3108, public, "campus_common",
                      permission)


def _job(
    orders: int = 10, units: int = 20, weight: int = 40, distances: dict | None = None
) -> HostJob:
    return HostJob(
        orders=orders,
        units=units,
        weight_kg=weight,
        distribution_day=SATURDAY,
        supplier_distance_km=distances if distances is not None else {"h1": 8.0},
        buyer_travel_penalty={},
    )


def _reward(cents: int = 6000):
    return compute_host_reward(
        config=HostRewardConfig(minimum_cents=cents, maximum_cents=cents),
        orders=10, units=20, distance_km=8, weight_kg=40, merchandise_cents=0,
    )


def _evaluate(profile, job=None, reward=None, site=None, standing=True):
    return evaluate_host(
        profile=profile,
        job=job or _job(distances={profile.household_id: 8.0}),
        reward=reward or _reward(),
        site=site or _site(),
        is_standing=standing,
    )


# ----------------------------------------------------------------------- eligibility


def test_a_qualified_host_is_eligible():
    assert _evaluate(make_host_profile("h1")).eligible is True


def test_too_many_orders_is_a_stated_factual_refusal():
    result = _evaluate(make_host_profile("h1", max_orders=5))
    assert result.eligible is False
    assert any("orders" in r for r in result.ineligible_reasons)


def test_too_heavy_a_load_is_refused():
    result = _evaluate(make_host_profile("h1", max_weight_kg=10))
    assert result.eligible is False
    assert any("kg" in r for r in result.ineligible_reasons)


def test_a_heavy_load_requires_a_vehicle():
    """The requirement comes from the job, not from the host asserting it."""
    profile = make_host_profile("h1", has_vehicle=False, max_weight_kg=500)
    result = _evaluate(profile, job=_job(weight=60, distances={"h1": 8.0}))
    assert result.eligible is False
    assert any("vehicle" in r for r in result.ineligible_reasons)


def test_a_light_load_does_not_require_a_vehicle():
    profile = make_host_profile("h1", has_vehicle=False)
    result = _evaluate(profile, job=_job(weight=10, distances={"h1": 8.0}))
    assert result.eligible is True


def test_supplier_distance_limit_is_enforced():
    profile = make_host_profile("h1", max_supplier_distance_km=3.0)
    result = _evaluate(profile, job=_job(distances={"h1": 20.0}))
    assert result.eligible is False
    assert any("km away" in r for r in result.ineligible_reasons)


def test_availability_on_the_distribution_day_is_enforced():
    profile = make_host_profile("h1", available_weekdays=[0, 1, 2])
    result = _evaluate(profile)
    assert result.eligible is False
    assert any("unavailable" in r for r in result.ineligible_reasons)


def test_compensation_below_the_hosts_minimum_makes_them_ineligible():
    """Pool never asks someone to work for less than they said they would (§32)."""
    profile = make_host_profile("h1", minimum_compensation_cents=99_999)
    result = _evaluate(profile)
    assert result.eligible is False
    assert any("minimum they accept" in r for r in result.ineligible_reasons)


def test_public_pickup_preference_is_enforced():
    profile = make_host_profile("h1", public_pickup_only=True)
    assert _evaluate(profile, site=_site(public=False)).eligible is False


def test_a_restricted_pickup_site_blocks_everyone():
    profile = make_host_profile("h1")
    result = _evaluate(profile, site=_site(permission=PickupPermission.RESTRICTED))
    assert result.eligible is False


def test_vehicle_capacity_is_checked_when_stated():
    profile = make_host_profile("h1", vehicle_capacity_units=5)
    result = _evaluate(profile, job=_job(units=50, distances={"h1": 8.0}))
    assert result.eligible is False
    assert any("capacity" in r for r in result.ineligible_reasons)


def test_someone_not_currently_willing_is_ineligible():
    assert _evaluate(make_host_profile("h1", willing_to_host=False)).eligible is False


# --------------------------------------------------------------------------- ranking


def test_only_eligible_candidates_are_ranked():
    good = _evaluate(make_host_profile("h1"))
    bad = _evaluate(make_host_profile("h2", max_orders=1))
    assert [e.household_id for e in rank_hosts([good, bad])] == ["h1"]


def test_a_closer_host_outranks_a_further_one_all_else_equal():
    near = _evaluate(make_host_profile("h1"), job=_job(distances={"h1": 2.0}))
    far = _evaluate(make_host_profile("h2"), job=_job(distances={"h2": 30.0}))
    assert rank_hosts([far, near])[0].household_id == "h1"


def test_reducing_buyer_travel_can_outweigh_a_more_expensive_host():
    """Host selection optimises the whole transaction, not the cheapest line (§33)."""
    cheap_but_awkward = evaluate_host(
        profile=make_host_profile("cheap"),
        job=HostJob(
            orders=10, units=20, weight_kg=40, distribution_day=SATURDAY,
            supplier_distance_km={"cheap": 8.0}, buyer_travel_penalty={"cheap": 15},
        ),
        reward=_reward(4000),
        site=_site(),
        is_standing=True,
    )
    pricier_but_central = evaluate_host(
        profile=make_host_profile("central"),
        job=HostJob(
            orders=10, units=20, weight_kg=40, distribution_day=SATURDAY,
            supplier_distance_km={"central": 8.0}, buyer_travel_penalty={"central": 0},
        ),
        reward=_reward(6000),
        site=_site(),
        is_standing=True,
    )
    assert rank_hosts([cheap_but_awkward, pricier_but_central])[0].household_id == "central"


def test_ranking_is_stable_for_identical_candidates():
    a = _evaluate(make_host_profile("aaa"))
    b = _evaluate(make_host_profile("bbb"), job=_job(distances={"bbb": 8.0}))
    assert [e.household_id for e in rank_hosts([b, a])] == ["aaa", "bbb"]


def test_score_components_are_exposed_for_debugging():
    result = _evaluate(make_host_profile("h1"))
    assert set(result.components) == {
        "compensation", "supplier_travel", "buyer_travel", "vehicle",
        "capacity_headroom", "public_site", "standing_host",
    }
    assert result.score == sum(result.components.values())


def test_evaluation_serialises_with_its_reasoning():
    payload = _evaluate(make_host_profile("h1", max_orders=1)).to_dict()
    assert payload["eligible"] is False
    assert payload["ineligible_reasons"]
    assert "components" in payload and "reward" in payload


# ---------------------------------------------------------------------------- weight


def test_weight_estimate_rounds_up_because_half_a_kilo_still_gets_carried():
    assert estimate_weight_kg(3, 2270) == 7  # 6.81 kg
    assert estimate_weight_kg(0, 2270) == 0
    assert estimate_weight_kg(10, 0) == 0
