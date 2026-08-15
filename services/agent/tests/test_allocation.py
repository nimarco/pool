from __future__ import annotations

import pytest

from pool.domain.allocation import Request, price_pool
from pool.domain.models import Offer, OfferKind


def reqs(*pairs) -> list[Request]:
    return [Request(f"hh{i}", f"need{i}", units) for i, units in enumerate(pairs)]


class TestPricing:
    def test_buys_whole_cases_and_records_surplus(self, bulk_offer, retail_offer):
        # 105 units in 25-unit cases -> 5 cases -> 125 purchased, 20 surplus.
        p = price_pool(bulk_offer, retail_offer, reqs(50, 30, 25))
        assert p.total_units == 105
        assert p.cases == 5
        assert p.units_purchased == 125
        assert p.surplus_units == 20
        assert p.total_cost_cents == 5 * 25 * 60

    def test_exact_case_multiple_has_no_surplus(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, reqs(50, 50))
        assert p.cases == 4
        assert p.surplus_units == 0

    def test_lines_sum_to_total_cost(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, reqs(15, 20, 10, 25, 15, 12, 18, 10, 30))
        assert sum(ln.cost_cents for ln in p.lines) == p.total_cost_cents

    def test_baseline_is_retail_times_units(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, reqs(40, 60))
        assert p.total_baseline_cents == 100 * 100  # 100 units at 100c retail
        assert p.line_for("hh0").baseline_cents == 4000

    def test_savings_are_positive_for_a_real_bulk_deal(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, reqs(50, 50))
        assert p.total_savings_cents > 0
        assert p.total_savings_bps > 0

    def test_surplus_can_erase_savings(self, retail_offer):
        """A near-empty case is paid for by the group, and the maths must show it."""
        # 26 units forces 2 cases (50 units) at 95c: 4750c for 26 units vs 2600c retail.
        bad = Offer("o_bad", "W", "p_rice", OfferKind.BULK, 95, 25, 1, None)
        p = price_pool(bad, retail_offer, reqs(26))
        assert p.total_cost_cents == 4750
        assert p.total_savings_cents < 0
        assert p.total_savings_bps < 0


class TestThreshold:
    def test_threshold_met(self, bulk_offer, retail_offer):
        assert price_pool(bulk_offer, retail_offer, reqs(60, 40)).threshold_met is True

    def test_threshold_not_met(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, reqs(60, 39))
        assert p.threshold_met is False
        assert p.threshold_units == 100

    def test_boundary_is_inclusive(self, bulk_offer, retail_offer):
        assert price_pool(bulk_offer, retail_offer, reqs(100)).threshold_met is True
        assert price_pool(bulk_offer, retail_offer, reqs(99)).threshold_met is False


class TestValidation:
    def test_mismatched_products_rejected(self, bulk_offer):
        other_retail = Offer("o2", "G", "p_other", OfferKind.RETAIL, 100, 1, 1, None)
        with pytest.raises(ValueError, match="same product"):
            price_pool(bulk_offer, other_retail, reqs(10))

    def test_non_positive_units_rejected(self, bulk_offer, retail_offer):
        with pytest.raises(ValueError, match="positive"):
            price_pool(bulk_offer, retail_offer, [Request("h", "n", 0)])

    def test_empty_request_set(self, bulk_offer, retail_offer):
        p = price_pool(bulk_offer, retail_offer, [])
        assert p.total_units == 0 and p.threshold_met is False and p.lines == []
