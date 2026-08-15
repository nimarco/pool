"""Bulk purchase pricing and per-household allocation.

Every number a household is ever shown originates here or in ``money.py``. The
agent reads these values; it never computes or restates them (AGENTS.md §5).

Cost model
----------
A bulk offer sells whole cases. To serve ``total_requested`` units the pool buys
``ceil(total_requested / case_units)`` cases and pays for all of them, including any
surplus. That surplus cost is shared across the units households actually asked for,
which is what happens in a real split-a-case buy: you pay for the case, you divide by
what you wanted. Savings are always measured against the retail baseline each
household would have paid buying alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Offer
from .money import allocate_cost, savings_bps


@dataclass(frozen=True)
class Request:
    """One household's ask, as it enters pricing."""

    household_id: str
    need_id: str
    units: int


@dataclass(frozen=True)
class AllocationLine:
    household_id: str
    need_id: str
    units: int
    cost_cents: int
    baseline_cents: int

    @property
    def savings_cents(self) -> int:
        return self.baseline_cents - self.cost_cents

    @property
    def savings_bps(self) -> int:
        return savings_bps(self.baseline_cents, self.cost_cents)


@dataclass(frozen=True)
class PoolPricing:
    """The complete, exact economics of a candidate pool."""

    offer_id: str
    total_units: int
    cases: int
    units_purchased: int
    surplus_units: int
    total_cost_cents: int
    total_baseline_cents: int
    threshold_units: int
    threshold_met: bool
    lines: list[AllocationLine] = field(default_factory=list)

    @property
    def total_savings_cents(self) -> int:
        return self.total_baseline_cents - self.total_cost_cents

    @property
    def total_savings_bps(self) -> int:
        return savings_bps(self.total_baseline_cents, self.total_cost_cents)

    def line_for(self, household_id: str) -> AllocationLine | None:
        for line in self.lines:
            if line.household_id == household_id:
                return line
        return None

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "total_units": self.total_units,
            "cases": self.cases,
            "units_purchased": self.units_purchased,
            "surplus_units": self.surplus_units,
            "total_cost_cents": self.total_cost_cents,
            "total_baseline_cents": self.total_baseline_cents,
            "total_savings_cents": self.total_savings_cents,
            "total_savings_bps": self.total_savings_bps,
            "threshold_units": self.threshold_units,
            "threshold_met": self.threshold_met,
            "lines": [
                {
                    "household_id": ln.household_id,
                    "need_id": ln.need_id,
                    "units": ln.units,
                    "cost_cents": ln.cost_cents,
                    "baseline_cents": ln.baseline_cents,
                    "savings_cents": ln.savings_cents,
                    "savings_bps": ln.savings_bps,
                }
                for ln in self.lines
            ],
        }


def price_pool(
    bulk_offer: Offer,
    retail_offer: Offer,
    requests: list[Request],
) -> PoolPricing:
    """Compute exact costs, allocations, and savings for a set of requests.

    Raises ValueError on structurally invalid input (non-positive units, mismatched
    products) rather than silently producing a number nobody can defend.
    """
    if bulk_offer.product_id != retail_offer.product_id:
        raise ValueError("bulk and retail offers must reference the same product")
    if bulk_offer.case_units <= 0:
        raise ValueError("case_units must be positive")
    if any(r.units <= 0 for r in requests):
        raise ValueError("every request must be for a positive number of units")

    total_units = sum(r.units for r in requests)
    threshold_met = total_units >= bulk_offer.min_units

    if total_units == 0:
        return PoolPricing(
            offer_id=bulk_offer.id,
            total_units=0,
            cases=0,
            units_purchased=0,
            surplus_units=0,
            total_cost_cents=0,
            total_baseline_cents=0,
            threshold_units=bulk_offer.min_units,
            threshold_met=False,
            lines=[],
        )

    # Ceiling division without floats.
    cases = -(-total_units // bulk_offer.case_units)
    units_purchased = cases * bulk_offer.case_units
    total_cost = cases * bulk_offer.case_price_cents

    weights = [r.units for r in requests]
    shares = allocate_cost(total_cost, weights)

    lines = [
        AllocationLine(
            household_id=r.household_id,
            need_id=r.need_id,
            units=r.units,
            cost_cents=share,
            baseline_cents=retail_offer.unit_price_cents * r.units,
        )
        for r, share in zip(requests, shares, strict=True)
    ]

    total_baseline = sum(ln.baseline_cents for ln in lines)

    return PoolPricing(
        offer_id=bulk_offer.id,
        total_units=total_units,
        cases=cases,
        units_purchased=units_purchased,
        surplus_units=units_purchased - total_units,
        total_cost_cents=total_cost,
        total_baseline_cents=total_baseline,
        threshold_units=bulk_offer.min_units,
        threshold_met=threshold_met,
        lines=lines,
    )
