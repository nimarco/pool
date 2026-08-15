"""Demand matching — finding latent overlap nobody declared.

This is the deterministic half of Pool's core insight: households never say "let's
buy rice together", so the system has to discover that a viable group *could* exist
from standing declarations alone.

Matching answers "who is even eligible", using product compatibility, timing, and
coarse geography. It deliberately does not decide whether a pool is *worthwhile* —
that is pricing (``allocation.py``) plus policy (``policy.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .models import Household, NeedDeclaration, Product

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
    is_exact_product: bool
    distance_km: float

    def to_dict(self) -> dict:
        return {
            "need_id": self.need.id,
            "household_id": self.household.id,
            "units": self.need.quantity,
            "is_exact_product": self.is_exact_product,
            # Rounded: households are located approximately by design (AGENTS.md §4).
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

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "total_units": self.total_units,
            "candidate_count": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected": [
                {"need_id": r.need_id, "household_id": r.household_id, "reason": r.reason}
                for r in self.rejections
            ],
        }


def products_compatible(
    target: Product,
    candidate: Product,
    accept_substitutes: bool,
) -> tuple[bool, bool]:
    """Return ``(compatible, is_exact)``.

    An exact product match always works. A different product in the same substitute
    group only works when the household explicitly accepts substitutes — Pool never
    infers that tolerance (AGENTS.md §5: substitutions are consequential).
    """
    if target.id == candidate.id:
        return True, True
    if not accept_substitutes:
        return False, False
    if target.substitute_group and target.substitute_group == candidate.substitute_group:
        return True, False
    return False, False


def find_candidates(
    *,
    target_product: Product,
    needs: list[NeedDeclaration],
    households: dict[str, Household],
    products: dict[str, Product],
    pickup_lat: float,
    pickup_lon: float,
    pickup_by: date,
    max_radius_km: float = 8.0,
    horizon_days: int = 45,
    exclude_household_ids: frozenset[str] = frozenset(),
) -> MatchResult:
    """Find every declared need that could legitimately join a pool for this product.

    Rejections are returned alongside candidates so the agent — and the activity feed —
    can explain why a household was left out without guessing.
    """
    candidates: list[MatchCandidate] = []
    rejections: list[MatchRejection] = []

    for need in needs:
        household = households.get(need.household_id)
        if household is None:
            rejections.append(MatchRejection(need.id, need.household_id, "unknown_household"))
            continue
        if not need.active:
            rejections.append(MatchRejection(need.id, household.id, "need_inactive"))
            continue
        if household.id in exclude_household_ids:
            rejections.append(MatchRejection(need.id, household.id, "already_in_pool"))
            continue

        need_product = products.get(need.product_id)
        if need_product is None:
            rejections.append(MatchRejection(need.id, household.id, "unknown_product"))
            continue

        compatible, is_exact = products_compatible(
            target_product, need_product, need.accept_substitutes
        )
        if not compatible:
            rejections.append(MatchRejection(need.id, household.id, "product_incompatible"))
            continue

        # Timing: the pickup must land before the household needs the item, and we
        # don't drag in demand from months away.
        if need.needed_by < pickup_by:
            rejections.append(MatchRejection(need.id, household.id, "needed_before_pickup"))
            continue
        if (need.needed_by - pickup_by).days > horizon_days:
            rejections.append(MatchRejection(need.id, household.id, "outside_horizon"))
            continue

        distance = haversine_km(household.lat, household.lon, pickup_lat, pickup_lon)
        if distance > max_radius_km:
            rejections.append(MatchRejection(need.id, household.id, "outside_radius"))
            continue

        candidates.append(
            MatchCandidate(
                need=need,
                household=household,
                is_exact_product=is_exact,
                distance_km=distance,
            )
        )

    # Stable, explainable ordering: nearest first, then by need id.
    candidates.sort(key=lambda c: (round(c.distance_km, 4), c.need.id))
    return MatchResult(target_product.id, candidates, rejections)
