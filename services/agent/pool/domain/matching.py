"""Demand matching — finding latent overlap nobody declared.

This is the deterministic half of Pool's core insight: members never say "let's buy
protein powder together", so the system has to discover that a viable group *could*
exist from standing declarations alone.

Matching answers "who is even eligible", using Community membership, product
compatibility, timing authority, and coarse geography. It deliberately does not decide
whether a pool is *worthwhile* — that is economics (``economics.py``) plus policy
(``policy.py``) plus the viability engine (``viability.py``).

Two boundaries are enforced here and nowhere else:

* **Community scope.** Demand from one Community never leaks into another's pool.
  Cross-community pooling is out of scope for this build (§9).
* **Verified membership.** Unverified members are matched only when the caller
  explicitly permits it, which is how deterministic fixtures stay usable without
  turning verification into a rubber stamp (§10).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .models import (
    CommunityMembership,
    Household,
    NeedDeclaration,
    Product,
)
from .substitution import CompatibilityVerdict, evaluate_compatibility
from .timing import TimingEligibility, evaluate_timing

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres. Pure function, no I/O."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class MatchCandidate:
    need: NeedDeclaration
    household: Household
    compatibility: CompatibilityVerdict
    timing: TimingEligibility
    distance_km: float

    @property
    def is_exact_product(self) -> bool:
        return self.compatibility.is_exact

    @property
    def is_future_pull_forward(self) -> bool:
        return self.timing.is_future_pull_forward

    def to_dict(self) -> dict:
        return {
            "need_id": self.need.id,
            "household_id": self.household.id,
            "units": self.need.quantity,
            "is_exact_product": self.is_exact_product,
            "is_future_pull_forward": self.is_future_pull_forward,
            "days_early": self.timing.days_early,
            # Rounded: members are located approximately by design (AGENTS.md §4).
            "distance_km": round(self.distance_km, 2),
        }


@dataclass(frozen=True)
class MatchRejection:
    need_id: str
    household_id: str
    reason: str


@dataclass(frozen=True)
class MatchResult:
    product_id: str
    candidates: list[MatchCandidate]
    rejections: list[MatchRejection]

    @property
    def total_units(self) -> int:
        return sum(c.need.quantity for c in self.candidates)

    @property
    def current_units(self) -> int:
        """Units from members whose need is already due — no pull-forward involved."""
        return sum(c.need.quantity for c in self.candidates if not c.is_future_pull_forward)

    @property
    def future_units(self) -> int:
        """Units only available because a member authorised an early purchase (§24)."""
        return sum(c.need.quantity for c in self.candidates if c.is_future_pull_forward)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "total_units": self.total_units,
            "current_units": self.current_units,
            "future_units": self.future_units,
            "candidate_count": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected": [
                {"need_id": r.need_id, "household_id": r.household_id, "reason": r.reason}
                for r in self.rejections
            ],
        }


def find_candidates(
    *,
    community_id: str,
    target_product: Product,
    needs: list[NeedDeclaration],
    households: dict[str, Household],
    products: dict[str, Product],
    memberships: dict[str, CommunityMembership],
    pickup_lat: float,
    pickup_lon: float,
    purchase_date: date,
    offer_unit_price_cents: int | None = None,
    max_radius_km: float = 3.0,
    exclude_household_ids: frozenset[str] = frozenset(),
    include_future_demand: bool = True,
    require_verified_membership: bool = True,
) -> MatchResult:
    """Find every declared need that could legitimately join a pool for this product.

    ``memberships`` is keyed ``"<community_id>#<household_id>"``. Rejections are
    returned alongside candidates so the agent — and the activity feed — can explain
    why someone was left out without guessing.
    """
    candidates: list[MatchCandidate] = []
    rejections: list[MatchRejection] = []

    def reject(need: NeedDeclaration, household_id: str, reason: str) -> None:
        rejections.append(MatchRejection(need.id, household_id, reason))

    for need in needs:
        if need.community_id != community_id:
            reject(need, need.household_id, "other_community")
            continue

        household = households.get(need.household_id)
        if household is None:
            reject(need, need.household_id, "unknown_household")
            continue
        if need.household_id in exclude_household_ids:
            reject(need, household.id, "already_in_pool")
            continue

        if require_verified_membership:
            membership = memberships.get(f"{community_id}#{household.id}")
            if membership is None or not membership.is_verified:
                reject(need, household.id, "community_membership_not_verified")
                continue

        need_product = products.get(need.product_id)
        if need_product is None:
            reject(need, household.id, "unknown_product")
            continue

        compatibility = evaluate_compatibility(
            target=target_product,
            candidate=need_product,
            need=need,
            offer_unit_price_cents=offer_unit_price_cents,
        )
        if not compatibility.compatible:
            reject(need, household.id, f"product_incompatible:{compatibility.reason}")
            continue

        timing = evaluate_timing(need, purchase_date)
        if not timing.eligible:
            reject(need, household.id, f"timing:{timing.reason}")
            continue
        if timing.is_future_pull_forward and not include_future_demand:
            reject(need, household.id, "future_demand_not_requested")
            continue

        distance = haversine_km(household.lat, household.lon, pickup_lat, pickup_lon)
        if distance > max_radius_km:
            reject(need, household.id, "outside_radius")
            continue

        candidates.append(
            MatchCandidate(
                need=need,
                household=household,
                compatibility=compatibility,
                timing=timing,
                distance_km=distance,
            )
        )

    # Stable, explainable ordering. Members whose need is already due come first, so a
    # pool is built from real current demand and only reaches into the future when it
    # genuinely has to.
    candidates.sort(
        key=lambda c: (c.is_future_pull_forward, round(c.distance_km, 4), c.need.id)
    )
    return MatchResult(target_product.id, candidates, rejections)
