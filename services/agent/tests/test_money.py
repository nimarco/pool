"""Money must be exact. These tests exist because a rounding bug here becomes a
wrong number in a message to a household."""

from __future__ import annotations

import pytest

from pool.domain.money import (
    MoneyError,
    allocate_cost,
    bps_to_pct_str,
    cents,
    format_cents,
    pct_to_bps,
    savings_bps,
)


class TestCents:
    @pytest.mark.parametrize(
        "raw,expected",
        [("12.34", 1234), ("0.05", 5), ("100", 10_000), ("$1,234.56", 123_456), ("-3.50", -350)],
    )
    def test_string_amounts_are_exact(self, raw, expected):
        assert cents(raw) == expected

    def test_float_rounds_half_up(self):
        assert cents(0.005) == 1
        assert cents(-0.005) == -1
        assert cents(19.994) == 1999

    def test_rejects_sub_cent_precision(self):
        with pytest.raises(MoneyError):
            cents("1.234")

    def test_rejects_garbage(self):
        with pytest.raises(MoneyError):
            cents("abc")


class TestFormat:
    @pytest.mark.parametrize(
        "amount,expected", [(0, "$0.00"), (5, "$0.05"), (1234, "$12.34"), (-350, "-$3.50")]
    )
    def test_format(self, amount, expected):
        assert format_cents(amount) == expected


class TestAllocateCost:
    def test_exact_division(self):
        assert allocate_cost(1000, [1, 1, 1, 1]) == [250, 250, 250, 250]

    def test_leftover_cents_are_never_lost(self):
        """The defining property: parts always sum to exactly the total."""
        parts = allocate_cost(1000, [1, 1, 1])
        assert sum(parts) == 1000
        assert parts == [334, 333, 333]

    def test_proportional_to_weights(self):
        """A household asking for more never pays less than one asking for less."""
        weights = [15, 20, 10, 25, 15, 12, 18, 10, 30]
        parts = allocate_cost(12_075, weights)
        assert sum(parts) == 12_075
        pairs = sorted(zip(weights, parts, strict=True))
        for (w1, p1), (w2, p2) in zip(pairs, pairs[1:], strict=False):
            if w1 < w2:
                assert p1 <= p2

    @pytest.mark.parametrize("total", [0, 1, 7, 99, 100_000, 999_983])
    def test_sums_exactly_for_many_totals(self, total):
        weights = [3, 1, 4, 1, 5, 9, 2, 6]
        assert sum(allocate_cost(total, weights)) == total

    def test_zero_weight_total_must_be_zero(self):
        assert allocate_cost(0, [0, 0]) == [0, 0]
        with pytest.raises(MoneyError):
            allocate_cost(100, [0, 0])

    def test_rejects_negative(self):
        with pytest.raises(MoneyError):
            allocate_cost(-1, [1])
        with pytest.raises(MoneyError):
            allocate_cost(10, [1, -1])

    def test_deterministic(self):
        """Same inputs must always give the same split — households compare notes."""
        a = allocate_cost(1000, [7, 11, 13])
        b = allocate_cost(1000, [7, 11, 13])
        assert a == b


class TestSavings:
    def test_basic(self):
        assert savings_bps(20_925, 12_075) == 4229  # 42.29%

    def test_no_savings(self):
        assert savings_bps(1000, 1000) == 0

    def test_negative_when_worse_than_retail(self):
        """A bad deal must read as negative, not be clamped to zero."""
        assert savings_bps(1000, 1200) == -2000

    def test_zero_baseline(self):
        assert savings_bps(0, 500) == 0

    def test_roundtrip_pct(self):
        assert pct_to_bps(25) == 2500
        assert bps_to_pct_str(4229) == "42.2%"
        assert bps_to_pct_str(-500) == "-5.0%"
