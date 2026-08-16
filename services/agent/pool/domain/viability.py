"""The central Pool viability engine (§51, §52).

One deterministic evaluator answers whether a transaction should exist at all:

    buyer_ok && supplier_ok && host_ok && platform_ok && timing_ok
      && quote_fresh_ok && package_allocation_ok && pickup_ok && funding_ok

Pool coordinates only transactions that are independently viable for **all four
parties**. It must never manufacture viability by hiding costs, violating a member's
authorisation rules, requiring speculative inventory, or silently subsidising a
participant. If the four sides do not work, the correct outcome is that no pool forms.

Two stages exist because two different questions are being asked:

``PRE_FUNDING``
    "Is this worth issuing a final offer for?" Funding does not exist yet, so the
    funding check is skipped and buyer checks run against provisional demand.

``FINAL_LOCK``
    "May we take these people's money?" Every check runs, funding is authoritative,
    and the answer must rest on stored facts rather than on anything the model said.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .economics import LandedEconomics
from .models import (
    Community,
    Offer,
    PickupPermission,
    PickupSite,
    PoolTiming,
    parse_iso,
    utcnow,
)
from .money import format_cents


class ViabilityStage(str, Enum):
    PRE_FUNDING = "pre_funding"
    FINAL_LOCK = "final_lock"


@dataclass(frozen=True)
class ViabilityCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class ViabilityVerdict:
    stage: ViabilityStage
    viable: bool
    checks: list[ViabilityCheck] = field(default_factory=list)

    @property
    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]

    @property
    def blocking_reason(self) -> str:
        for c in self.checks:
            if not c.passed:
                return c.detail
        return ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "viable": self.viable,
            "failed": self.failed,
            "blocking_reason": self.blocking_reason,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class ViabilityInputs:
    """Everything the engine needs, already computed by deterministic code.

    Deliberately a plain data bag: the engine performs no I/O and calls no service, so
    it is trivially testable and cannot be talked into a different answer.
    """

    community: Community
    economics: LandedEconomics
    bulk_offer: Offer
    site: PickupSite
    timing: PoolTiming
    #: Units whose buyers have authorised payment for the exact final amount.
    funded_units: int
    #: Units counted for discovery, whether or not they are funded yet.
    provisional_units: int
    host_assigned: bool
    host_reward_meets_minimum: bool
    #: Buyers whose own Smart Join / final-offer authority does not accept the final
    #: price. At lock these must be zero — everyone charged agreed to what they pay.
    buyers_failing_policy: int
    #: Buyers still awaiting a human answer to the final offer.
    buyers_awaiting_decision: int
    now: datetime = field(default_factory=utcnow)


def evaluate_viability(inputs: ViabilityInputs, stage: ViabilityStage) -> ViabilityVerdict:
    """Run every check for ``stage``. All checks are evaluated, never short-circuited,
    so the UI and the agent trace can show *every* reason a pool is not viable."""
    checks: list[ViabilityCheck] = []
    econ = inputs.economics
    final = stage == ViabilityStage.FINAL_LOCK
    counted_units = inputs.funded_units if final else inputs.provisional_units

    # --- supplier -----------------------------------------------------------
    moq = inputs.bulk_offer.min_units
    checks.append(
        ViabilityCheck(
            "supplier_moq",
            counted_units >= moq,
            f"{counted_units}/{moq} units "
            f"({'funded' if final else 'provisional'}) against the supplier minimum",
        )
    )
    checks.append(
        ViabilityCheck(
            "offer_active",
            inputs.bulk_offer.active and not inputs.bulk_offer.is_expired(inputs.now),
            "supplier offer is active and unexpired"
            if inputs.bulk_offer.active and not inputs.bulk_offer.is_expired(inputs.now)
            else "supplier offer has expired or been disabled",
        )
    )

    # --- quote freshness ----------------------------------------------------
    age = inputs.bulk_offer.age_hours(inputs.now)
    max_age = inputs.community.quote_max_age_hours
    if age is None:
        fresh, detail = False, "supplier quote has never been verified"
    elif age > max_age:
        fresh, detail = False, f"supplier quote is {age:.1f}h old, limit is {max_age}h"
    else:
        fresh, detail = True, f"supplier quote verified {age:.1f}h ago (limit {max_age}h)"
    checks.append(ViabilityCheck("quote_fresh", fresh, detail))

    # --- package allocation -------------------------------------------------
    # Case rounding must not create inventory nobody bought (§48).
    pkg = econ.packages
    checks.append(
        ViabilityCheck(
            "package_allocation",
            pkg.surplus_resolved,
            "every purchased unit has a buyer"
            if pkg.surplus_resolved
            else f"{pkg.surplus_units} unit(s) of a {pkg.case_units}-unit case are unallocated",
        )
    )

    # --- host ---------------------------------------------------------------
    checks.append(
        ViabilityCheck(
            "host_assigned",
            inputs.host_assigned,
            "a fulfiller has accepted the job" if inputs.host_assigned else "no host has accepted",
        )
    )
    checks.append(
        ViabilityCheck(
            "host_compensation",
            inputs.host_reward_meets_minimum,
            "host compensation clears their stated minimum"
            if inputs.host_reward_meets_minimum
            else "host compensation is below the minimum they accept",
        )
    )

    # --- buyers -------------------------------------------------------------
    checks.append(
        ViabilityCheck(
            "buyer_savings",
            econ.net_savings_cents > 0,
            f"net landed savings {format_cents(econ.net_savings_cents)} after all costs"
            if econ.net_savings_cents > 0
            else "the all-in Pool cost does not beat buying retail alone",
        )
    )
    checks.append(
        ViabilityCheck(
            "buyer_authorisation",
            inputs.buyers_failing_policy == 0,
            "every participating buyer's own rules accept the final price"
            if inputs.buyers_failing_policy == 0
            else f"{inputs.buyers_failing_policy} buyer(s) do not accept the final price",
        )
    )
    if final:
        checks.append(
            ViabilityCheck(
                "buyer_decisions_settled",
                inputs.buyers_awaiting_decision == 0,
                "no buyer decision is outstanding"
                if inputs.buyers_awaiting_decision == 0
                else f"{inputs.buyers_awaiting_decision} buyer(s) have not answered yet",
            )
        )

    # --- platform -----------------------------------------------------------
    floor = inputs.community.min_platform_contribution_cents
    contribution = format_cents(econ.platform_fee_cents)
    checks.append(
        ViabilityCheck(
            "platform_economics",
            econ.platform_fee_cents >= floor,
            f"platform contribution {contribution} meets the {format_cents(floor)} floor"
            if econ.platform_fee_cents >= floor
            else f"platform contribution {contribution} is below the {format_cents(floor)} floor",
        )
    )

    # --- timing -------------------------------------------------------------
    lock_at = inputs.timing.lock_at
    if not lock_at:
        timing_ok, timing_detail = False, "pool has no lock deadline"
    elif final and inputs.now > parse_iso(lock_at):
        timing_ok, timing_detail = False, "the lock deadline has already passed"
    else:
        timing_ok, timing_detail = True, "inside the pool's scheduled window"
    checks.append(ViabilityCheck("timing", timing_ok, timing_detail))

    # --- pickup -------------------------------------------------------------
    pickup_ok = inputs.site.permission in {PickupPermission.DEMO, PickupPermission.VERIFIED}
    checks.append(
        ViabilityCheck(
            "pickup_site",
            pickup_ok,
            f"pickup site permission is {inputs.site.permission.value}"
            if pickup_ok
            else f"pickup site is {inputs.site.permission.value} and cannot be used",
        )
    )

    # --- funding ------------------------------------------------------------
    if final:
        checks.append(
            ViabilityCheck(
                "funding",
                inputs.funded_units >= moq and inputs.funded_units >= pkg.total_units,
                f"{inputs.funded_units} funded units cover the order"
                if inputs.funded_units >= moq and inputs.funded_units >= pkg.total_units
                else f"only {inputs.funded_units} of {pkg.total_units} priced units are funded",
            )
        )

    return ViabilityVerdict(
        stage=stage, viable=all(c.passed for c in checks), checks=checks
    )
