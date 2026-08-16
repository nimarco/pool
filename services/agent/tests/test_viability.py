"""The central viability engine — the truth table for "should this transaction exist".

Pool coordinates only transactions that work for all four parties. These tests walk the
engine one failing condition at a time, because the failure modes are the product: a
pool that locks when it should not is a real person out of pocket.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pool.domain.economics import Request, compute_host_reward, price_pool
from pool.domain.models import (
    HostRewardConfig,
    PickupPermission,
    PickupSite,
    PlatformFeeConfig,
    PoolTiming,
    ProcessingFeeConfig,
    iso,
    utcnow,
)
from pool.domain.viability import (
    ViabilityInputs,
    ViabilityStage,
    evaluate_viability,
)
from tests.conftest import COMM, make_community


def _economics(retail, bulk, units_each=10, buyers=2):
    reward = compute_host_reward(
        config=HostRewardConfig(), orders=buyers, units=units_each * buyers,
        distance_km=8, weight_kg=30, merchandise_cents=0,
    )
    return price_pool(
        bulk_offer=bulk,
        retail_offer=retail,
        requests=[Request(f"m{i}", f"n{i}", units_each) for i in range(buyers)],
        host_reward=reward,
        platform_fee=PlatformFeeConfig(mode="percent_of_savings", bps=1000),
        processing_fee=ProcessingFeeConfig(),
        host_is_estimated=False,
    )


def _timing(now):
    return PoolTiming(lock_at=iso(now + timedelta(hours=2)))


def _inputs(retail, bulk, **overrides):
    now = utcnow()
    econ = _economics(retail, bulk)
    defaults = {
        "community": make_community(),
        "economics": econ,
        "bulk_offer": bulk,
        "site": PickupSite("s1", "Union", COMM, 38.6, -90.3, True, "campus_common",
                           PickupPermission.DEMO),
        "timing": _timing(now),
        "funded_units": econ.packages.total_units,
        "provisional_units": econ.packages.total_units,
        "host_assigned": True,
        "host_reward_meets_minimum": True,
        "buyers_failing_policy": 0,
        "buyers_awaiting_decision": 0,
        "now": now,
    }
    defaults.update(overrides)
    return ViabilityInputs(**defaults)


def _verdict(retail, bulk, stage=ViabilityStage.FINAL_LOCK, **overrides):
    return evaluate_viability(_inputs(retail, bulk, **overrides), stage)


# --------------------------------------------------------------------------- passing


def test_a_fully_satisfied_pool_is_viable(retail_offer, bulk_offer):
    verdict = _verdict(retail_offer, bulk_offer)
    assert verdict.viable is True
    assert verdict.failed == []


def test_pre_funding_stage_does_not_require_funding(retail_offer, bulk_offer):
    verdict = _verdict(
        retail_offer, bulk_offer, stage=ViabilityStage.PRE_FUNDING, funded_units=0
    )
    assert verdict.viable is True
    assert "funding" not in {c.name for c in verdict.checks}


# --------------------------------------------------------------------------- failing


def test_below_the_supplier_minimum_is_not_viable(retail_offer, bulk_offer):
    bulk_offer.moq_amount = 999
    verdict = _verdict(retail_offer, bulk_offer)
    assert not verdict.viable
    assert "supplier_moq" in verdict.failed


def test_a_stale_quote_blocks_a_lock(retail_offer, bulk_offer):
    """A final offer may never rest on a price nobody re-checked (§43)."""
    now = utcnow()
    bulk_offer.verified_at = iso(now - timedelta(hours=100))
    verdict = _verdict(retail_offer, bulk_offer)
    assert not verdict.viable
    assert "quote_fresh" in verdict.failed


def test_a_never_verified_quote_blocks_a_lock(retail_offer, bulk_offer):
    bulk_offer.verified_at = ""
    assert "quote_fresh" in _verdict(retail_offer, bulk_offer).failed


def test_an_expired_offer_blocks_a_lock(retail_offer, bulk_offer):
    bulk_offer.valid_until = iso(utcnow() - timedelta(days=1))
    assert "offer_active" in _verdict(retail_offer, bulk_offer).failed


def test_a_disabled_offer_blocks_a_lock(retail_offer, bulk_offer):
    bulk_offer.active = False
    assert "offer_active" in _verdict(retail_offer, bulk_offer).failed


def test_unallocated_case_surplus_blocks_a_lock(retail_offer, bulk_offer):
    """Pool refuses to buy stock nobody ordered (§48)."""
    econ = _economics(retail_offer, bulk_offer, units_each=7, buyers=3)  # 21 of 30
    verdict = evaluate_viability(
        _inputs(retail_offer, bulk_offer, economics=econ, funded_units=21,
                provisional_units=21),
        ViabilityStage.FINAL_LOCK,
    )
    assert not verdict.viable
    assert "package_allocation" in verdict.failed


def test_no_host_blocks_a_lock(retail_offer, bulk_offer):
    assert "host_assigned" in _verdict(retail_offer, bulk_offer, host_assigned=False).failed


def test_underpaid_host_blocks_a_lock(retail_offer, bulk_offer):
    assert "host_compensation" in _verdict(
        retail_offer, bulk_offer, host_reward_meets_minimum=False
    ).failed


def test_no_net_saving_blocks_a_lock(retail_offer, bulk_offer):
    """If the all-in cost does not beat buying alone, the pool should not exist."""
    bulk_offer.unit_price_cents = retail_offer.unit_price_cents
    verdict = _verdict(retail_offer, bulk_offer)
    assert not verdict.viable
    assert "buyer_savings" in verdict.failed


def test_a_buyer_whose_rules_reject_the_price_blocks_a_lock(retail_offer, bulk_offer):
    assert "buyer_authorisation" in _verdict(
        retail_offer, bulk_offer, buyers_failing_policy=1
    ).failed


def test_an_unanswered_buyer_blocks_a_lock_but_not_a_pre_funding_check(
    retail_offer, bulk_offer
):
    assert "buyer_decisions_settled" in _verdict(
        retail_offer, bulk_offer, buyers_awaiting_decision=2
    ).failed
    assert _verdict(
        retail_offer, bulk_offer, stage=ViabilityStage.PRE_FUNDING, buyers_awaiting_decision=2
    ).viable


def test_platform_economics_below_the_floor_block_a_lock(retail_offer, bulk_offer):
    community = make_community(min_platform_contribution_cents=10_000_000)
    assert "platform_economics" in _verdict(
        retail_offer, bulk_offer, community=community
    ).failed


def test_a_passed_lock_deadline_blocks_a_lock(retail_offer, bulk_offer):
    now = utcnow()
    verdict = _verdict(
        retail_offer, bulk_offer,
        timing=PoolTiming(lock_at=iso(now - timedelta(hours=1))), now=now,
    )
    assert "timing" in verdict.failed


def test_a_pool_with_no_lock_deadline_is_not_viable(retail_offer, bulk_offer):
    assert "timing" in _verdict(retail_offer, bulk_offer, timing=PoolTiming()).failed


@pytest.mark.parametrize(
    "permission,expected",
    [
        (PickupPermission.DEMO, True),
        (PickupPermission.VERIFIED, True),
        (PickupPermission.PENDING_VERIFICATION, False),
        (PickupPermission.RESTRICTED, False),
    ],
)
def test_pickup_site_permission_gates_a_lock(retail_offer, bulk_offer, permission, expected):
    site = PickupSite("s1", "Union", COMM, 38.6, -90.3, True, "campus_common", permission)
    verdict = _verdict(retail_offer, bulk_offer, site=site)
    assert ("pickup_site" not in verdict.failed) is expected


def test_partially_funded_demand_blocks_a_lock(retail_offer, bulk_offer):
    verdict = _verdict(retail_offer, bulk_offer, funded_units=5)
    assert not verdict.viable
    assert "funding" in verdict.failed or "supplier_moq" in verdict.failed


# --------------------------------------------------------------------------- shape


def test_all_checks_run_so_every_reason_is_visible(retail_offer, bulk_offer):
    """The UI and the agent trace need every failure, not just the first one."""
    verdict = _verdict(
        retail_offer, bulk_offer, host_assigned=False, buyers_failing_policy=3, funded_units=0
    )
    assert len(verdict.failed) >= 3
    assert verdict.blocking_reason


def test_verdict_serialises_with_every_check(retail_offer, bulk_offer):
    payload = _verdict(retail_offer, bulk_offer).to_dict()
    assert payload["viable"] is True
    assert payload["stage"] == "final_lock"
    assert len(payload["checks"]) >= 10
