"""Complete landed economics (§50).

Every number a buyer is ever shown originates here or in ``money.py``. The agent
reads these values; it never computes or restates them (AGENTS.md §5).

The cost model
--------------
A bulk offer sells whole cases of sealed consumer units. To serve ``total_units`` the
pool must buy ``ceil(total_units / case_units)`` cases and pay for all of them. Any
leftover units are *surplus*, and by default Pool refuses to quietly buy them (§48) —
surplus is surfaced, not absorbed by the host or the platform.

Buyers collectively fund the whole transaction (§36)::

    bulk merchandise
  + host / runner compensation
  + payment processing
  + Pool platform fee
  = all-in Pool cost

    retail comparison  −  all-in Pool cost  =  net savings

Ordering matters, because two of those components would otherwise be circular:

1. ``merchandise`` and ``host_compensation`` are computed first; both are independent
   of the fees.
2. The **platform fee** is a share of *gross* savings — retail baseline minus the
   pre-fee subtotal — so the fee is defined without referring to itself. Pool earns
   only when the group is actually better off.
3. **Processing** is grossed up per buyer, so the buyer's charge covers the
   processor's cut of that very charge exactly::

       charge = ceil((share + fixed) * 10000 / (10000 - rate_bps))

   Computing the fee on the pre-fee share instead would under-recover by a few cents
   per buyer, which is a silent platform subsidy — precisely what §36 forbids.

Smart Join is then evaluated against **net landed savings**, never gross (§50).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    HostRewardConfig,
    Offer,
    PlatformFeeConfig,
    ProcessingFeeConfig,
)
from .money import allocate_cost, savings_bps


class EconomicsError(ValueError):
    """Raised when an economics input is structurally invalid."""


@dataclass(frozen=True)
class Request:
    """One buyer's ask, as it enters pricing."""

    household_id: str
    need_id: str
    units: int


@dataclass(frozen=True)
class PackageAllocation:
    """Case math and its consequences (§47, §48)."""

    total_units: int
    case_units: int
    cases: int
    units_purchased: int
    surplus_units: int
    moq_units: int
    moq_met: bool

    @property
    def surplus_resolved(self) -> bool:
        """True when every purchased unit has a buyer. The default lock requirement."""
        return self.surplus_units == 0

    def to_dict(self) -> dict:
        return {
            "total_units": self.total_units,
            "case_units": self.case_units,
            "cases": self.cases,
            "units_purchased": self.units_purchased,
            "surplus_units": self.surplus_units,
            "moq_units": self.moq_units,
            "moq_met": self.moq_met,
            "surplus_resolved": self.surplus_resolved,
        }


def allocate_packages(offer: Offer, total_units: int) -> PackageAllocation:
    """Work out how many cases must be bought and what that leaves over."""
    if offer.case_units <= 0:
        raise EconomicsError("case_units must be positive")
    if total_units < 0:
        raise EconomicsError("total_units cannot be negative")
    cases = -(-total_units // offer.case_units)  # ceiling division, no floats
    units_purchased = cases * offer.case_units
    return PackageAllocation(
        total_units=total_units,
        case_units=offer.case_units,
        cases=cases,
        units_purchased=units_purchased,
        surplus_units=units_purchased - total_units,
        moq_units=offer.min_units,
        moq_met=total_units >= offer.min_units,
    )


@dataclass(frozen=True)
class CaseFit:
    """Which buyers make an order that fills whole cases exactly (§48).

    ``selected`` is the subset of the offered items whose quantities sum to a multiple
    of the case size and clear the supplier minimum. ``excluded`` is everyone the fit
    could not accommodate, and they are not silently dropped — the caller reports them.
    """

    ok: bool
    selected: list[int]
    excluded: list[int]
    total_units: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "selected_count": len(self.selected),
            "excluded_count": len(self.excluded),
            "total_units": self.total_units,
            "reason": self.reason,
        }


def fit_to_cases(
    quantities: list[int],
    *,
    case_units: int,
    moq_units: int,
    priority: list[int] | None = None,
    max_extra_cases: int = 3,
) -> CaseFit:
    """Choose the buyers whose combined demand fills whole cases exactly.

    This is what turns "zero speculative surplus" from a rule that merely *rejects*
    pools into one the system can actually satisfy. Case rounding would otherwise force
    Pool to buy units nobody ordered and quietly bill someone for them (§48).

    Selection is a bounded exact search over reachable totals, so it is deterministic
    and cheap: the state space is capped at the supplier minimum plus a few extra cases,
    and each buyer is considered once.

    Preference order, applied when several subsets are valid:

    1. include as many **priority** buyers as possible — people whose need is already
       due, rather than demand pulled forward from the future;
    2. then take the larger order, because more units means better unit economics;
    3. then prefer earlier positions, which callers order nearest-first.

    Returns ``ok=False`` with a reason when no combination lands on a case boundary.
    """
    if case_units <= 0:
        raise EconomicsError("case_units must be positive")
    if any(q <= 0 for q in quantities):
        raise EconomicsError("every quantity must be positive")

    priority_set = set(priority or range(len(quantities)))
    total_available = sum(quantities)
    if total_available < moq_units:
        return CaseFit(
            False, [], list(range(len(quantities))), 0,
            f"available demand is {total_available} units, below the {moq_units}-unit minimum",
        )

    # Cap the search a few cases above the minimum: buying far beyond the minimum is not
    # the goal, and an unbounded state space is exactly the kind of thing that becomes a
    # performance surprise later.
    required_cases = -(-moq_units // case_units)
    cap = min(total_available, (required_cases + max_extra_cases) * case_units)

    # state: total units -> (priority_count, selected indices)
    states: dict[int, tuple[int, list[int]]] = {0: (0, [])}
    for index, qty in enumerate(quantities):
        is_priority = 1 if index in priority_set else 0
        for total in sorted(states.keys(), reverse=True):
            new_total = total + qty
            if new_total > cap:
                continue
            count, chosen = states[total]
            candidate = (count + is_priority, [*chosen, index])
            existing = states.get(new_total)
            # Strictly-better replacement only, so ties keep the earlier-built subset
            # and the whole function stays order-stable.
            if existing is None or candidate[0] > existing[0]:
                states[new_total] = candidate

    valid = [
        total
        for total in states
        if total >= moq_units and total % case_units == 0 and total > 0
    ]
    if not valid:
        return CaseFit(
            False, [], list(range(len(quantities))), 0,
            f"no combination of the available demand fills whole {case_units}-unit cases "
            f"at or above the {moq_units}-unit minimum",
        )

    best_total = max(valid, key=lambda t: (states[t][0], t))
    selected = sorted(states[best_total][1])
    excluded = [i for i in range(len(quantities)) if i not in set(selected)]
    return CaseFit(
        True,
        selected,
        excluded,
        best_total,
        f"{best_total} units fills {best_total // case_units} whole case(s) exactly",
    )


# --------------------------------------------------------------------------- host pay


@dataclass(frozen=True)
class HostReward:
    """A host's compensation, itemised (§37).

    ``earned_cents`` is owed once fulfilment responsibility has been discharged —
    collection, transport, and custody of the buyers' units. ``contingent_cents`` is
    the handoff component, which does depend on verified pickups. A buyer no-show
    therefore cannot erase the work the host already did (§38).
    """

    base_cents: int
    per_order_cents: int
    distance_cents: int
    weight_cents: int
    merchandise_share_cents: int
    handoff_bonus_cents: int
    total_cents: int
    earned_cents: int
    contingent_cents: int
    orders: int
    distance_km: float
    weight_kg: int
    clamped: str = ""  # "minimum" | "maximum" | ""

    def to_dict(self) -> dict:
        return {
            "base_cents": self.base_cents,
            "per_order_cents": self.per_order_cents,
            "distance_cents": self.distance_cents,
            "weight_cents": self.weight_cents,
            "merchandise_share_cents": self.merchandise_share_cents,
            "handoff_bonus_cents": self.handoff_bonus_cents,
            "total_cents": self.total_cents,
            "earned_cents": self.earned_cents,
            "contingent_cents": self.contingent_cents,
            "orders": self.orders,
            "distance_km": round(self.distance_km, 2),
            "weight_kg": self.weight_kg,
            "clamped": self.clamped,
        }

    def breakdown(self) -> dict[str, int]:
        return {
            "base": self.base_cents,
            "per_order": self.per_order_cents,
            "distance": self.distance_cents,
            "weight": self.weight_cents,
            "merchandise_share": self.merchandise_share_cents,
            "handoff_bonus": self.handoff_bonus_cents,
        }


def compute_host_reward(
    *,
    config: HostRewardConfig,
    orders: int,
    units: int,
    distance_km: float,
    weight_kg: int,
    merchandise_cents: int,
) -> HostReward:
    """Deterministic host compensation. Scales with the work actually done.

    ``distance_km`` is the supplier round trip, so a farther supplier pays more.
    Weight only contributes above a threshold — an ordinary load is already covered
    by the base and per-order components.
    """
    if orders < 0 or units < 0 or weight_kg < 0 or distance_km < 0:
        raise EconomicsError("host reward inputs must be non-negative")

    base = config.base_cents
    per_order = config.per_order_cents * orders
    distance = int(round(config.per_km_cents * distance_km))
    excess_kg = max(0, weight_kg - config.weight_threshold_kg)
    weight = config.per_kg_over_threshold_cents * excess_kg
    merch_share = merchandise_cents * config.merchandise_bps // 10_000
    handoff = config.handoff_bonus_cents

    total = base + per_order + distance + weight + merch_share + handoff
    clamped = ""
    if total < config.minimum_cents:
        total, clamped = config.minimum_cents, "minimum"
    elif total > config.maximum_cents:
        total, clamped = config.maximum_cents, "maximum"

    # The handoff component is the only contingent slice, and it cannot exceed the
    # clamped total — otherwise a clamp could make "earned" negative.
    contingent = min(handoff, total)
    return HostReward(
        base_cents=base,
        per_order_cents=per_order,
        distance_cents=distance,
        weight_cents=weight,
        merchandise_share_cents=merch_share,
        handoff_bonus_cents=handoff,
        total_cents=total,
        earned_cents=total - contingent,
        contingent_cents=contingent,
        orders=orders,
        distance_km=distance_km,
        weight_kg=weight_kg,
        clamped=clamped,
    )


# --------------------------------------------------------------------------- fees


def compute_platform_fee(
    config: PlatformFeeConfig,
    *,
    gross_savings_cents: int,
    merchandise_cents: int,
    buyer_count: int,
) -> int:
    """Pool's transparent take. Never hidden, never negative.

    ``fixed_cents_per_buyer`` is a standing per-buyer component that applies in every
    mode; ``fixed_per_buyer`` is simply the mode where it is the *only* component.
    """
    fixed = config.fixed_cents_per_buyer * buyer_count
    if config.mode == "percent_of_savings":
        variable = max(0, gross_savings_cents) * config.bps // 10_000
    elif config.mode == "percent_of_merchandise":
        variable = merchandise_cents * config.bps // 10_000
    elif config.mode == "fixed_per_buyer":
        variable = 0
    else:
        raise EconomicsError(f"unknown platform fee mode: {config.mode!r}")
    return max(variable + fixed, config.minimum_cents)


def gross_up_processing(share_cents: int, config: ProcessingFeeConfig) -> int:
    """The charge that leaves exactly ``share_cents`` after the processor's cut.

    Exact integer arithmetic; ``charge - share`` is the fee the buyer funds. Returns
    the total charge, not the fee.
    """
    if config.bps >= 10_000:
        raise EconomicsError("processing rate must be below 100%")
    if share_cents < 0:
        raise EconomicsError("share cannot be negative")
    numerator = (share_cents + config.fixed_cents) * 10_000
    denominator = 10_000 - config.bps
    return -(-numerator // denominator)  # ceiling division


# --------------------------------------------------------------------------- landed


@dataclass(frozen=True)
class BuyerLine:
    """What one buyer actually pays, and what they would have paid alone."""

    household_id: str
    need_id: str
    units: int
    merchandise_share_cents: int
    host_share_cents: int
    platform_fee_share_cents: int
    processing_cents: int
    landed_cents: int
    baseline_cents: int

    @property
    def savings_cents(self) -> int:
        return self.baseline_cents - self.landed_cents

    @property
    def savings_bps(self) -> int:
        return savings_bps(self.baseline_cents, self.landed_cents)

    def to_dict(self) -> dict:
        return {
            "household_id": self.household_id,
            "need_id": self.need_id,
            "units": self.units,
            "merchandise_share_cents": self.merchandise_share_cents,
            "host_share_cents": self.host_share_cents,
            "platform_fee_share_cents": self.platform_fee_share_cents,
            "processing_cents": self.processing_cents,
            "landed_cents": self.landed_cents,
            "baseline_cents": self.baseline_cents,
            "savings_cents": self.savings_cents,
            "savings_bps": self.savings_bps,
        }


@dataclass(frozen=True)
class LandedEconomics:
    """The complete, exact economics of one pool. Nothing is left out or absorbed."""

    offer_id: str
    packages: PackageAllocation
    merchandise_cents: int
    host_compensation_cents: int
    other_fulfillment_cents: int
    platform_fee_cents: int
    payment_processing_cents: int
    all_in_cents: int
    retail_baseline_cents: int
    lines: list[BuyerLine] = field(default_factory=list)
    host_reward: HostReward | None = None
    #: True when host compensation is still an estimate because no host has accepted.
    host_is_estimated: bool = True

    @property
    def net_savings_cents(self) -> int:
        return self.retail_baseline_cents - self.all_in_cents

    @property
    def net_savings_bps(self) -> int:
        return savings_bps(self.retail_baseline_cents, self.all_in_cents)

    @property
    def gross_savings_cents(self) -> int:
        """Savings before Pool's fee and processing — the base the fee is drawn from."""
        return self.retail_baseline_cents - (
            self.merchandise_cents + self.host_compensation_cents + self.other_fulfillment_cents
        )

    def line_for(self, household_id: str) -> BuyerLine | None:
        for line in self.lines:
            if line.household_id == household_id:
                return line
        return None

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "packages": self.packages.to_dict(),
            "merchandise_cents": self.merchandise_cents,
            "host_compensation_cents": self.host_compensation_cents,
            "other_fulfillment_cents": self.other_fulfillment_cents,
            "platform_fee_cents": self.platform_fee_cents,
            "payment_processing_cents": self.payment_processing_cents,
            "all_in_cents": self.all_in_cents,
            "retail_baseline_cents": self.retail_baseline_cents,
            "gross_savings_cents": self.gross_savings_cents,
            "net_savings_cents": self.net_savings_cents,
            "net_savings_bps": self.net_savings_bps,
            "host_is_estimated": self.host_is_estimated,
            "host_reward": self.host_reward.to_dict() if self.host_reward else None,
            "lines": [ln.to_dict() for ln in self.lines],
        }


def price_pool(
    *,
    bulk_offer: Offer,
    retail_offer: Offer,
    requests: list[Request],
    host_reward: HostReward | None,
    platform_fee: PlatformFeeConfig,
    processing_fee: ProcessingFeeConfig,
    other_fulfillment_cents: int = 0,
    host_is_estimated: bool = True,
) -> LandedEconomics:
    """Compute the complete landed economics for a set of buyer requests.

    Raises on structurally invalid input rather than silently producing a number
    nobody can defend.
    """
    if bulk_offer.product_id != retail_offer.product_id:
        raise EconomicsError("bulk and retail offers must reference the same product")
    if any(r.units <= 0 for r in requests):
        raise EconomicsError("every request must be for a positive number of units")

    total_units = sum(r.units for r in requests)
    packages = allocate_packages(bulk_offer, total_units)

    if total_units == 0:
        return LandedEconomics(
            offer_id=bulk_offer.id,
            packages=packages,
            merchandise_cents=0,
            host_compensation_cents=0,
            other_fulfillment_cents=0,
            platform_fee_cents=0,
            payment_processing_cents=0,
            all_in_cents=0,
            retail_baseline_cents=0,
            lines=[],
            host_reward=host_reward,
            host_is_estimated=host_is_estimated,
        )

    merchandise = packages.cases * bulk_offer.case_price_cents
    host_cents = host_reward.total_cents if host_reward else 0
    retail_baseline = retail_offer.unit_price_cents * total_units

    # Step 2: the platform fee is a share of gross savings, so it is well defined
    # without referring to the total it is part of.
    pre_fee_subtotal = merchandise + host_cents + other_fulfillment_cents
    gross_savings = retail_baseline - pre_fee_subtotal
    fee = compute_platform_fee(
        platform_fee,
        gross_savings_cents=gross_savings,
        merchandise_cents=merchandise,
        buyer_count=len(requests),
    )

    # Step 3: split each pre-processing component across buyers by units, using the
    # largest-remainder method so every split sums to exactly its total.
    weights = [r.units for r in requests]
    merch_shares = allocate_cost(merchandise, weights)
    host_shares = allocate_cost(host_cents, weights)
    fee_shares = allocate_cost(fee, weights)

    # Step 4: gross up processing per buyer so nobody silently subsidises the processor.
    lines: list[BuyerLine] = []
    processing_total = 0
    for r, merch, host_share, fee_share in zip(
        requests, merch_shares, host_shares, fee_shares, strict=True
    ):
        share = merch + host_share + fee_share
        charge = gross_up_processing(share, processing_fee)
        processing = charge - share
        processing_total += processing
        lines.append(
            BuyerLine(
                household_id=r.household_id,
                need_id=r.need_id,
                units=r.units,
                merchandise_share_cents=merch,
                host_share_cents=host_share,
                platform_fee_share_cents=fee_share,
                processing_cents=processing,
                landed_cents=charge,
                baseline_cents=retail_offer.unit_price_cents * r.units,
            )
        )

    all_in = pre_fee_subtotal + fee + processing_total
    return LandedEconomics(
        offer_id=bulk_offer.id,
        packages=packages,
        merchandise_cents=merchandise,
        host_compensation_cents=host_cents,
        other_fulfillment_cents=other_fulfillment_cents,
        platform_fee_cents=fee,
        payment_processing_cents=processing_total,
        all_in_cents=all_in,
        retail_baseline_cents=retail_baseline,
        lines=lines,
        host_reward=host_reward,
        host_is_estimated=host_is_estimated,
    )
