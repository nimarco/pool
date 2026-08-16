"""Package maths, host compensation, fees, and complete landed economics.

These are the numbers a buyer is actually shown, so the tests are deliberately exact:
an assertion on "roughly the right price" would defeat the point of integer cents.
"""

from __future__ import annotations

import pytest

from pool.domain.economics import (
    EconomicsError,
    Request,
    allocate_packages,
    compute_host_reward,
    compute_platform_fee,
    fit_to_cases,
    gross_up_processing,
    price_pool,
)
from pool.domain.models import HostRewardConfig, PlatformFeeConfig, ProcessingFeeConfig

# --------------------------------------------------------------------------- packages


def test_case_rounding_reports_surplus(bulk_offer):
    packages = allocate_packages(bulk_offer, 24)
    assert packages.cases == 3
    assert packages.units_purchased == 30
    assert packages.surplus_units == 6
    assert packages.surplus_resolved is False


def test_exact_case_boundary_has_no_surplus(bulk_offer):
    packages = allocate_packages(bulk_offer, 20)
    assert (packages.cases, packages.surplus_units) == (2, 0)
    assert packages.surplus_resolved is True
    assert packages.moq_met is True


def test_moq_measured_in_cases_converts_to_units(bulk_offer):
    from pool.domain.models import MoqKind

    bulk_offer.moq_kind = MoqKind.CASES
    bulk_offer.moq_amount = 3
    assert bulk_offer.min_units == 30


def test_zero_case_size_is_rejected(bulk_offer):
    bulk_offer.case_units = 0
    with pytest.raises(EconomicsError):
        allocate_packages(bulk_offer, 10)


# --------------------------------------------------------------------------- case fit


def test_fit_selects_an_exact_case_boundary():
    fit = fit_to_cases([3, 3, 2, 2, 2], case_units=6, moq_units=6)
    assert fit.ok
    assert fit.total_units % 6 == 0
    assert fit.total_units >= 6


def test_fit_prefers_members_whose_need_is_already_due():
    # 4 current units and 8 future units are available; a 12-unit case can only be
    # filled by using all of them, but a 6-unit target should keep the current ones.
    fit = fit_to_cases([2, 2, 4, 4], case_units=6, moq_units=6, priority=[0, 1])
    assert fit.ok
    assert 0 in fit.selected and 1 in fit.selected


def test_fit_refuses_when_nothing_lands_on_a_case_boundary():
    # 7 units available, 5-unit cases, 5-unit minimum: 5 is reachable only as 2+5 or
    # similar — with these quantities nothing sums to a multiple of 5.
    fit = fit_to_cases([3, 4], case_units=5, moq_units=5)
    assert not fit.ok
    assert "whole" in fit.reason


def test_fit_refuses_below_the_supplier_minimum():
    fit = fit_to_cases([2, 2], case_units=2, moq_units=20)
    assert not fit.ok
    assert "below" in fit.reason


def test_fit_is_deterministic_across_runs():
    quantities = [3, 2, 4, 1, 2, 3, 5]
    results = {
        tuple(fit_to_cases(quantities, case_units=6, moq_units=12).selected)
        for _ in range(5)
    }
    assert len(results) == 1


# ------------------------------------------------------------------------- host pay


def _reward(orders: int, units: int = 20, distance: float = 10.0, weight: int = 40):
    return compute_host_reward(
        config=HostRewardConfig(),
        orders=orders,
        units=units,
        distance_km=distance,
        weight_kg=weight,
        merchandise_cents=100_000,
    )


def test_host_pay_scales_with_the_number_of_orders():
    assert _reward(5).total_cents < _reward(30).total_cents


def test_host_pay_scales_with_distance():
    near = _reward(10, distance=2.0)
    far = _reward(10, distance=25.0)
    assert far.distance_cents > near.distance_cents
    assert far.total_cents > near.total_cents


def test_weight_only_contributes_above_the_threshold():
    config = HostRewardConfig()
    light = compute_host_reward(
        config=config, orders=5, units=5, distance_km=1,
        weight_kg=config.weight_threshold_kg, merchandise_cents=0,
    )
    heavy = compute_host_reward(
        config=config, orders=5, units=5, distance_km=1,
        weight_kg=config.weight_threshold_kg + 10, merchandise_cents=0,
    )
    assert light.weight_cents == 0
    assert heavy.weight_cents == config.per_kg_over_threshold_cents * 10


def test_earned_and_contingent_split_protects_the_host_from_no_shows():
    """A buyer failing to collect must not erase pay for work already done (§38)."""
    reward = _reward(10)
    assert reward.contingent_cents == HostRewardConfig().handoff_bonus_cents
    assert reward.earned_cents == reward.total_cents - reward.contingent_cents
    assert reward.earned_cents > reward.contingent_cents


def test_reward_is_clamped_to_the_configured_band():
    tiny = compute_host_reward(
        config=HostRewardConfig(minimum_cents=5000),
        orders=1, units=1, distance_km=0, weight_kg=0, merchandise_cents=0,
    )
    assert tiny.total_cents == 5000
    assert tiny.clamped == "minimum"
    huge = compute_host_reward(
        config=HostRewardConfig(maximum_cents=3000),
        orders=500, units=500, distance_km=500, weight_kg=500, merchandise_cents=0,
    )
    assert huge.total_cents == 3000
    assert huge.clamped == "maximum"


def test_negative_inputs_are_rejected():
    with pytest.raises(EconomicsError):
        compute_host_reward(
            config=HostRewardConfig(), orders=-1, units=1,
            distance_km=1, weight_kg=1, merchandise_cents=0,
        )


# ----------------------------------------------------------------------------- fees


def test_platform_fee_is_a_share_of_savings_and_never_negative():
    config = PlatformFeeConfig(mode="percent_of_savings", bps=1000)
    assert compute_platform_fee(
        config, gross_savings_cents=10_000, merchandise_cents=50_000, buyer_count=5
    ) == 1000
    # A pool that saves nothing earns Pool nothing.
    assert compute_platform_fee(
        config, gross_savings_cents=-500, merchandise_cents=50_000, buyer_count=5
    ) == 0


def test_platform_fee_modes():
    merch = PlatformFeeConfig(mode="percent_of_merchandise", bps=500)
    assert compute_platform_fee(
        merch, gross_savings_cents=0, merchandise_cents=20_000, buyer_count=4
    ) == 1000
    fixed = PlatformFeeConfig(mode="fixed_per_buyer", fixed_cents_per_buyer=50)
    assert compute_platform_fee(
        fixed, gross_savings_cents=99_999, merchandise_cents=20_000, buyer_count=4
    ) == 200


def test_unknown_fee_mode_fails_loudly():
    with pytest.raises(EconomicsError):
        compute_platform_fee(
            PlatformFeeConfig(mode="vibes"),
            gross_savings_cents=1, merchandise_cents=1, buyer_count=1,
        )


def test_processing_gross_up_recovers_the_processors_cut_exactly():
    """The charge must cover the processor's fee on that very charge (§36, §50)."""
    config = ProcessingFeeConfig(bps=290, fixed_cents=30)
    share = 10_000
    charge = gross_up_processing(share, config)
    # What the processor keeps out of `charge`, rounded the way a processor rounds.
    processor_take = (charge * config.bps + 9999) // 10_000 + config.fixed_cents
    assert charge - processor_take >= share  # never under-recovers -> no silent subsidy
    assert charge - processor_take <= share + 1  # and never over-charges meaningfully


def test_processing_rate_of_100_percent_is_rejected():
    with pytest.raises(EconomicsError):
        gross_up_processing(100, ProcessingFeeConfig(bps=10_000))


# --------------------------------------------------------------------------- landed


def _price(requests, retail, bulk, reward=None):
    return price_pool(
        bulk_offer=bulk,
        retail_offer=retail,
        requests=requests,
        host_reward=reward,
        platform_fee=PlatformFeeConfig(mode="percent_of_savings", bps=1000),
        processing_fee=ProcessingFeeConfig(bps=290, fixed_cents=30),
    )


def test_landed_price_includes_every_modelled_cost(retail_offer, bulk_offer):
    reward = compute_host_reward(
        config=HostRewardConfig(), orders=2, units=20,
        distance_km=10, weight_kg=40, merchandise_cents=12_000,
    )
    econ = _price(
        [Request("a", "n1", 10), Request("b", "n2", 10)], retail_offer, bulk_offer, reward
    )
    # 2 cases x 10 units x 600c = 12000c merchandise, retail 20 x 1000c = 20000c.
    assert econ.merchandise_cents == 12_000
    assert econ.retail_baseline_cents == 20_000
    assert econ.host_compensation_cents == reward.total_cents
    assert econ.platform_fee_cents > 0
    assert econ.payment_processing_cents > 0
    assert econ.all_in_cents == (
        econ.merchandise_cents
        + econ.host_compensation_cents
        + econ.other_fulfillment_cents
        + econ.platform_fee_cents
        + econ.payment_processing_cents
    )


def test_buyer_lines_sum_to_the_all_in_total(retail_offer, bulk_offer):
    """Every cent a buyer pays is a cent the pool accounts for. No rounding leaks."""
    reward = compute_host_reward(
        config=HostRewardConfig(), orders=3, units=20,
        distance_km=8, weight_kg=40, merchandise_cents=12_000,
    )
    econ = _price(
        [Request("a", "n1", 7), Request("b", "n2", 6), Request("c", "n3", 7)],
        retail_offer, bulk_offer, reward,
    )
    assert sum(line.landed_cents for line in econ.lines) == econ.all_in_cents
    assert sum(line.merchandise_share_cents for line in econ.lines) == econ.merchandise_cents
    assert sum(line.host_share_cents for line in econ.lines) == econ.host_compensation_cents
    assert (
        sum(line.platform_fee_share_cents for line in econ.lines) == econ.platform_fee_cents
    )


def test_net_savings_are_measured_after_all_costs(retail_offer, bulk_offer):
    """Smart Join must never see a gross figure with the operating costs hidden (§50)."""
    reward = compute_host_reward(
        config=HostRewardConfig(), orders=2, units=20,
        distance_km=10, weight_kg=40, merchandise_cents=12_000,
    )
    econ = _price(
        [Request("a", "n1", 10), Request("b", "n2", 10)], retail_offer, bulk_offer, reward
    )
    assert econ.net_savings_cents == econ.retail_baseline_cents - econ.all_in_cents
    assert econ.net_savings_cents < econ.gross_savings_cents
    assert 0 < econ.net_savings_bps < 10_000


def test_host_pay_can_erase_the_saving_entirely(retail_offer, bulk_offer):
    """If fair host pay wipes out the benefit, the pool should not look attractive (§36)."""
    huge = compute_host_reward(
        config=HostRewardConfig(base_cents=20_000, minimum_cents=20_000, maximum_cents=99_999),
        orders=2, units=20, distance_km=1, weight_kg=1, merchandise_cents=0,
    )
    econ = _price(
        [Request("a", "n1", 10), Request("b", "n2", 10)], retail_offer, bulk_offer, huge
    )
    assert econ.net_savings_cents < 0


def test_mismatched_products_are_rejected(retail_offer, bulk_offer):
    bulk_offer.product_id = "p_other"
    with pytest.raises(EconomicsError):
        _price([Request("a", "n1", 10)], retail_offer, bulk_offer)


def test_non_positive_request_is_rejected(retail_offer, bulk_offer):
    with pytest.raises(EconomicsError):
        _price([Request("a", "n1", 0)], retail_offer, bulk_offer)


def test_pricing_is_reproducible(retail_offer, bulk_offer):
    requests = [Request("a", "n1", 7), Request("b", "n2", 6), Request("c", "n3", 7)]
    first = _price(requests, retail_offer, bulk_offer)
    second = _price(requests, retail_offer, bulk_offer)
    assert first.to_dict() == second.to_dict()
