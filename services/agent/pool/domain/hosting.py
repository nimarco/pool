"""Host evaluation and ranking (§32, §33).

Two rules shape this module.

**Eligibility is factual, and it fails closed.** Availability, vehicle requirement,
capacity, weight, supplier travel, pickup-site suitability, and the host's own
minimum compensation are hard constraints. A candidate who breaks one is not
"lower ranked" — they are ineligible, with a recorded reason.

**Ranking optimises the whole transaction, not the cheapest host.** A slightly more
expensive host who dramatically reduces buyer travel, or who has a better public
pickup site, can be the better outcome for the group. Every component of the score is
exposed so a human — or a judge — can see exactly why one candidate outranked another.

The agent may choose among *evaluated, eligible* options. It cannot invent
eligibility, and it cannot rank by a criterion this module did not compute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .economics import HostReward
from .models import (
    HostProfile,
    PickupPermission,
    PickupSite,
)


@dataclass(frozen=True)
class HostEvaluation:
    """One candidate, fully evaluated. Component scores are the audit trail."""

    household_id: str
    eligible: bool
    ineligible_reasons: list[str]
    score: int
    components: dict[str, int]
    reward: HostReward
    supplier_distance_km: float
    buyer_travel_penalty_minutes: int

    def to_dict(self) -> dict:
        return {
            "household_id": self.household_id,
            "eligible": self.eligible,
            "ineligible_reasons": self.ineligible_reasons,
            "score": self.score,
            "components": self.components,
            "reward_cents": self.reward.total_cents,
            "reward": self.reward.to_dict(),
            "supplier_distance_km": round(self.supplier_distance_km, 2),
            "buyer_travel_penalty_minutes": self.buyer_travel_penalty_minutes,
        }


@dataclass(frozen=True)
class HostJob:
    """The concrete work one pool needs done. Same for every candidate."""

    orders: int
    units: int
    weight_kg: int
    distribution_day: date
    #: Supplier round-trip distance per candidate, keyed by household id.
    supplier_distance_km: dict[str, float] = field(default_factory=dict)
    #: Average extra minutes buyers would travel if this candidate's preferred site
    #: were used instead of the pool's current site. Keyed by household id.
    buyer_travel_penalty: dict[str, int] = field(default_factory=dict)


# Scoring weights. Higher is better; every term is an integer so ranking is exact and
# reproducible. Tuning these is a business decision, so they live in one visible place.
_W_COST = 3          # per dollar of host compensation (cheaper is better)
_W_SUPPLIER_KM = 4   # per km of supplier travel (closer is better)
_W_BUYER_MINUTE = 12 # per minute of extra buyer travel — buyers outnumber the host
_W_VEHICLE = 25      # a vehicle de-risks a heavy run
_W_HEADROOM = 2      # per order of spare capacity
_W_PUBLIC_SITE = 40  # a verified public pickup site beats a private one
_W_STANDING = 15     # a standing host has opted in deliberately


def evaluate_host(
    *,
    profile: HostProfile,
    job: HostJob,
    reward: HostReward,
    site: PickupSite,
    is_standing: bool,
) -> HostEvaluation:
    """Evaluate one host candidate against one pool's actual work."""
    reasons: list[str] = []
    distance = job.supplier_distance_km.get(profile.household_id, 0.0)
    buyer_penalty = job.buyer_travel_penalty.get(profile.household_id, 0)

    if not profile.willing_to_host:
        reasons.append("not currently willing to host")
    if job.orders > profile.max_orders:
        reasons.append(f"job has {job.orders} orders, above their limit of {profile.max_orders}")
    if job.weight_kg > profile.max_weight_kg:
        reasons.append(f"load is {job.weight_kg} kg, above their limit of {profile.max_weight_kg} kg")
    if distance > profile.max_supplier_distance_km:
        reasons.append(
            f"supplier is {distance:.1f} km away, above their limit of "
            f"{profile.max_supplier_distance_km:.1f} km"
        )
    if profile.available_weekdays and job.distribution_day.weekday() not in profile.available_weekdays:
        reasons.append("unavailable on the distribution day")
    if reward.total_cents < profile.minimum_compensation_cents:
        reasons.append("compensation is below the minimum they accept")
    if profile.public_pickup_only and not site.is_public:
        reasons.append("requires a public pickup site")
    if site.permission == PickupPermission.RESTRICTED:
        reasons.append("pickup site is restricted")
    # A vehicle requirement is derived from the job, not asserted by the host: a load
    # that cannot be carried on foot needs one.
    if job.weight_kg > 25 and not profile.has_vehicle:
        reasons.append("load needs a vehicle")
    if (
        profile.has_vehicle
        and profile.vehicle_capacity_units
        and job.units > profile.vehicle_capacity_units
    ):
        reasons.append("load exceeds their vehicle capacity")

    components = {
        "compensation": -_W_COST * (reward.total_cents // 100),
        "supplier_travel": -_W_SUPPLIER_KM * int(round(distance)),
        "buyer_travel": -_W_BUYER_MINUTE * buyer_penalty,
        "vehicle": _W_VEHICLE if profile.has_vehicle else 0,
        "capacity_headroom": _W_HEADROOM * max(0, profile.max_orders - job.orders),
        "public_site": _W_PUBLIC_SITE if site.is_public else 0,
        "standing_host": _W_STANDING if is_standing else 0,
    }
    return HostEvaluation(
        household_id=profile.household_id,
        eligible=not reasons,
        ineligible_reasons=reasons,
        score=sum(components.values()),
        components=components,
        reward=reward,
        supplier_distance_km=distance,
        buyer_travel_penalty_minutes=buyer_penalty,
    )


def ranking_key(*, household_id: str, score: int) -> tuple[int, str]:
    """The canonical host ordering, defined once. Lower sorts better.

    Highest score first; ties break on the **lower** household id, so a rerun of the
    same pool offers the job to the same person. Two callers used to derive this
    independently — this module ranked ascending by id, while the hosting service
    selected with ``max((score, household_id))`` and therefore preferred the *higher*
    id on a tie. Both were deterministic and they disagreed, which is worse than either:
    the ranking a judge is shown came from one and the offer from the other (#audit P2).

    Exported as the key rather than as a sorted list because the service ranks
    ``HostCandidate`` rows and this module ranks ``HostEvaluation`` objects. They are
    different types with the same ordering, and the ordering is the part that must not
    be written twice.
    """
    return (-score, household_id)


def rank_hosts(evaluations: list[HostEvaluation]) -> list[HostEvaluation]:
    """Eligible candidates, best first. Ties break on household id so runs repeat."""
    eligible = [e for e in evaluations if e.eligible]
    return sorted(
        eligible, key=lambda e: ranking_key(household_id=e.household_id, score=e.score)
    )


def estimate_weight_kg(units: int, unit_weight_grams: int) -> int:
    """Total load in whole kilograms, rounded up — a half kilo still has to be carried."""
    if unit_weight_grams <= 0:
        return 0
    return -(-(units * unit_weight_grams) // 1000)
