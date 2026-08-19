"""The deterministic coordination engine.

Everything the agent can *do* to the world goes through this module and its siblings.
The agent decides which of these operations to invoke and in what order; this module
decides what is true, what is legal, and what a human must approve (AGENTS.md §5).

Every consequential operation is idempotent by explicit key, because agent systems
retry and a retried ``create_candidate_pool`` must not produce two pools.

The lifecycle implemented here is the canonical one (§18)::

    latent demand -> candidate pool -> host recruiting -> host selected
      -> quote refresh -> final landed economics -> final offer
      -> authorisation -> funded -> final viability -> LOCKED

Three rules are enforced structurally rather than by convention:

* **Provisional participation is never financial commitment** (§25). A candidate pool
  counts provisional demand for discovery; only authorised demand counts for funding.
* **Host selection happens before final buyer authorisation** (§35), because the host's
  compensation is part of the buyer's price. Pool never authorises $42 and later
  charges $47.
* **A final offer never rests on a stale quote** (§43). The supplier price is
  re-verified immediately before the final economics are computed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..domain.economics import (
    HostReward,
    LandedEconomics,
    Request,
    allocate_packages,
    compute_host_reward,
    fit_to_cases,
    price_pool,
)
from ..domain.hosting import estimate_weight_kg
from ..domain.matching import MatchResult, find_candidates, haversine_km
from ..domain.models import (
    LEFT_PARTICIPATION_STATES,
    AutonomyPath,
    Community,
    DecisionKind,
    DecisionRequest,
    DecisionState,
    Membership,
    NeedDeclaration,
    Offer,
    OfferKind,
    ParticipationState,
    PickupSite,
    Pool,
    PoolStatus,
    PoolTiming,
    Product,
    iso,
    new_id,
    parse_iso,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.policy import JoinVerdictKind, PolicyVerdict, evaluate_smart_join
from ..domain.state import assert_transition, is_open_to_joining
from ..domain.substitution import evaluate_compatibility
from ..domain.timing import build_timing, next_pool_day
from ..domain.viability import (
    ViabilityInputs,
    ViabilityStage,
    ViabilityVerdict,
    evaluate_viability,
)
from .context import CoordinationError, PoolContext

#: Pools form inside the Community and repair beyond it.
#:
#: The Community is the boundary Pool coordinates inside (AGENTS.md §1, §2), and its
#: ``radius_km`` is the authoritative statement of how far apart its members are. A
#: verified member of a Community is therefore eligible to be *discovered* anywhere
#: inside it, and how far any one of them is willing to travel is decided by their own
#: ``max_travel_minutes`` — a real declared preference the Smart Join engine already
#: evaluates against real routed travel time (``domain.policy``).
#:
#: Formation used to stop at a global ``FORMATION_RADIUS_KM = 1.6``. Two things were
#: wrong with that, and neither was the number:
#:
#: * ``Community.radius_km`` was read nowhere at all, so the model carried a field
#:   declaring the community's extent while the engine silently used a different,
#:   tighter one. The constants' own docstring claimed both radii were "bounded by the
#:   Community radius"; nothing bounded them, and ``RECOVERY_RADIUS_KM = 4.0`` in fact
#:   searched well outside a 2.5 km Community.
#: * A hard geographic cut *overrides* each member's stated travel authority in the
#:   stricter direction and never tells them. Somebody who said they would walk 24
#:   minutes was excluded from their own community's order by a rule they never agreed
#:   to and never saw — while the rule they did state was only ever a soft prompt.
#:
#: The asymmetry itself is still right, and it survives: formation searches the
#: Community; recovery widens *past* it, because repairing a funded pool is worth
#: reaching further than forming a speculative one. Coarse geography is a search bound
#: and a site-ranking preference here — never an authority over a member.
RECOVERY_WIDENING = 1.6

#: How far a member is assumed to be willing to walk to a pickup point, used **only**
#: to rank candidate pickup sites (``agent/tools.py``): the best site is the one most of
#: the interested members can reach on foot. It excludes nobody. Ranking by the demand
#: centroid instead drifts toward outliers and picks a site convenient for nobody, which
#: is the failure this replaced.
WALKABLE_PICKUP_KM = 1.6


def formation_radius_km(community: Community) -> float:
    """How far from a pickup site formation may look. The Community's own extent."""
    return community.radius_km


def recovery_radius_km(community: Community) -> float:
    """How far a *repair* may look — deliberately wider than the Community (§27)."""
    return community.radius_km * RECOVERY_WIDENING

#: Distance assumed for the supplier round trip when no host has been selected yet, so
#: a candidate pool can show an honest *estimate* rather than a precise-looking lie.
ESTIMATED_SUPPLIER_DISTANCE_KM = 6.0

#: Dropping buyers whose rules reject the final price changes the price for everyone
#: else, so pricing is a small fixed-point iteration. Bounded, like every loop here.
#:
#: The bound is a *fail-closed* limit, not a budget to be spent: economics are only ever
#: adopted from a pass that removed nobody, so exhausting these passes means the pool
#: does not price rather than pricing approximately. See :func:`issue_final_offer`.
MAX_PRICING_PASSES = 4


# --------------------------------------------------------------------------- results


@dataclass
class CandidateAssessment:
    household_id: str
    household_name: str
    need_id: str
    units: int
    is_exact_product: bool
    is_future_pull_forward: bool
    days_early: int
    cost_cents: int
    baseline_cents: int
    savings_cents: int
    savings_bps: int
    travel_minutes: int
    distance_km: float
    verdict: PolicyVerdict

    def to_dict(self) -> dict[str, Any]:
        return {
            "household_id": self.household_id,
            "household_name": self.household_name,
            "need_id": self.need_id,
            "units": self.units,
            "is_exact_product": self.is_exact_product,
            "is_future_pull_forward": self.is_future_pull_forward,
            "days_early": self.days_early,
            "cost_cents": self.cost_cents,
            "cost_display": format_cents(self.cost_cents),
            "baseline_cents": self.baseline_cents,
            "savings_cents": self.savings_cents,
            "savings_bps": self.savings_bps,
            "travel_minutes": self.travel_minutes,
            "distance_km": round(self.distance_km, 2),
            "auto_join_eligible": self.verdict.eligible_for_auto_join,
            "verdict": self.verdict.kind.value,
            "blocking_rule": (self.verdict.failed_rules[0] if self.verdict.failed_rules else None),
            "blocking_reason": self.verdict.blocking_reason,
        }


#: What happened to one bulk tier inside an evaluation. Values, not prose, so a run
#: report can group and count them without parsing a sentence.
TIER_SELECTED = "selected"
TIER_NO_COMPATIBLE_DEMAND = "no_compatible_demand"
TIER_BELOW_MINIMUM = "below_minimum"
TIER_NO_CASE_FIT = "no_case_fit"
TIER_LOWER_SAVINGS = "lower_savings"
TIER_OUTCOMES = frozenset(
    {
        TIER_SELECTED,
        TIER_NO_COMPATIBLE_DEMAND,
        TIER_BELOW_MINIMUM,
        TIER_NO_CASE_FIT,
        TIER_LOWER_SAVINGS,
    }
)

#: Why an opportunity is not worth forming, as a value rather than a sentence.
REASON_VIABLE = ""
REASON_NO_RETAIL_BASELINE = "no_retail_baseline"
REASON_NO_BULK_OFFER = "no_bulk_offer"
REASON_NO_COMPATIBLE_DEMAND = "no_compatible_demand"
REASON_BELOW_MINIMUM = "below_minimum"
REASON_NOT_CHEAPER = "not_cheaper"
REASON_ROUTING_UNAVAILABLE = "routing_unavailable"
OPPORTUNITY_REASON_CODES = frozenset(
    {
        REASON_VIABLE,
        REASON_NO_RETAIL_BASELINE,
        REASON_NO_BULK_OFFER,
        REASON_NO_COMPATIBLE_DEMAND,
        REASON_BELOW_MINIMUM,
        REASON_NOT_CHEAPER,
        REASON_ROUTING_UNAVAILABLE,
    }
)


@dataclass
class OpportunityAssessment:
    """A fully-costed candidate opportunity. Not yet a pool; nobody has been contacted.

    Host compensation is an *estimate* here, because no host has been recruited yet.
    That is why a candidate pool shows a savings range rather than an exact price (§26).
    """

    community_id: str
    product_id: str
    product_name: str
    pickup_site_id: str
    pickup_site_name: str
    pickup_is_public: bool
    distribution_day: str
    bulk_offer_id: str | None
    retail_offer_id: str | None
    viable: bool
    reason: str
    #: Machine-readable form of ``reason``. ``reason`` is a sentence written for a human
    #: reading a run trace and has been reworded more than once; anything that has to
    #: *branch* on why an opportunity failed reads this instead of matching on prose.
    #: One of :data:`OPPORTUNITY_REASON_CODES`.
    reason_code: str
    economics: LandedEconomics | None
    timing: PoolTiming | None = None
    candidates: list[CandidateAssessment] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    routing_provider: str = ""
    avg_travel_minutes: int = 0
    max_travel_minutes: int = 0
    current_units: int = 0
    future_units: int = 0
    #: Compatible, in-range, in-time units this evaluation actually found, before any
    #: case fitting. Populated on the *unviable* path too, which the prose ``reason``
    #: already carried inside a sentence — a member asking "how far off is this" needs
    #: the number, and parsing it back out of a string is not an answer.
    #:
    #: Always read together with :attr:`minimum_units`, and always from the *same*
    #: supplier tier: the winning one when a tier priced, otherwise the one that came
    #: closest. Taking the largest match from one tier and the smallest minimum from
    #: another produces a pair of true numbers that together describe a supplier offer
    #: nobody made.
    matched_units: int = 0
    #: The quantity that tier will not sell below.
    minimum_units: int = 0
    #: Every bulk tier this evaluation actually compared, and what happened to each.
    #: The agent is never shown it (a tier it cannot name is not a decision it can
    #: make), but "which supplier offer won, and what lost to it" is one of the few
    #: genuinely interesting things a run establishes, and it existed nowhere durable.
    #: Shape: ``{offer_id, unit_price_cents, min_units, case_units, matched_units,
    #: outcome}`` where outcome is one of :data:`TIER_OUTCOMES`.
    offers_considered: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        econ = self.economics
        return {
            "community_id": self.community_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "pickup_site_id": self.pickup_site_id,
            "pickup_site_name": self.pickup_site_name,
            "pickup_is_public": self.pickup_is_public,
            "distribution_day": self.distribution_day,
            "bulk_offer_id": self.bulk_offer_id,
            "retail_offer_id": self.retail_offer_id,
            "viable": self.viable,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "routing_provider": self.routing_provider,
            "avg_travel_minutes": self.avg_travel_minutes,
            "max_travel_minutes": self.max_travel_minutes,
            "current_units": self.current_units,
            "future_units": self.future_units,
            "matched_units": self.matched_units,
            "minimum_units": self.minimum_units,
            "offers_considered": self.offers_considered,
            "economics": econ.to_dict() if econ else None,
            "estimated_savings_pct": bps_to_pct_str(econ.net_savings_bps) if econ else "0.0%",
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected_count": len(self.rejected),
            "auto_join_count": sum(1 for c in self.candidates if c.verdict.eligible_for_auto_join),
            "approval_required_count": sum(
                1 for c in self.candidates if not c.verdict.eligible_for_auto_join
            ),
        }


# --------------------------------------------------------------------------- helpers


def offers_for(ctx: PoolContext, product_id: str, now=None) -> tuple[Offer | None, list[Offer]]:
    """The retail baseline and every usable bulk tier for one product."""
    now = now or ctx.now
    retail: Offer | None = None
    bulk: list[Offer] = []
    for o in ctx.repo.list_offers(ctx.ws):
        if o.product_id != product_id or not o.active:
            continue
        if o.is_expired(now):
            continue
        if o.kind == OfferKind.RETAIL:
            retail = o
        else:
            bulk.append(o)
    return retail, bulk


def _travel_map(ctx: PoolContext, households, site: PickupSite):
    """One bounded route-matrix call for a whole candidate set."""
    from ..adapters.routing import Coordinate

    if not households:
        return {}, {}, ctx.routing.name
    origins = [Coordinate(h.lat, h.lon) for h in households]
    matrix = ctx.routing.travel_matrix(origins, [Coordinate(site.lat, site.lon)])
    minutes = {h.id: matrix[i][0].duration_minutes for i, h in enumerate(households)}
    km = {h.id: matrix[i][0].distance_km for i, h in enumerate(households)}
    return minutes, km, ctx.routing.name


def _memberships_map(ctx: PoolContext, community_id: str) -> dict[str, Any]:
    return {
        m.key: m for m in ctx.repo.list_community_memberships(ctx.ws, community_id)
    }


def sourceable_targets(ctx: PoolContext, product_id: str) -> list[str]:
    """Products a pool could actually buy that might serve a need for ``product_id``.

    The declared product first, then anything else in its substitute group Pool holds a
    bulk offer for. The member's own substitution policy still decides whether any of
    them may serve *them* — that verdict belongs to ``domain.substitution`` and is
    reached inside the matcher, not here. Widening the *search* is not widening the
    *authority*: without this, somebody who said "any equivalent product is fine" was
    told no supplier existed while Pool held a bulk quote for the neighbouring brand.

    One implementation, because three callers need the same answer: the member outlook,
    the run objective a member-triggered run is built from, and discovery.
    """
    declared = ctx.repo.get_product(ctx.ws, product_id)
    group = declared.substitute_group if declared else ""
    out: list[str] = []
    for candidate in [declared, *ctx.repo.list_products(ctx.ws)]:
        if candidate is None or candidate.id in out:
            continue
        if candidate.id != product_id and (
            not group or candidate.substitute_group != group
        ):
            continue
        if offers_for(ctx, candidate.id)[1]:
            out.append(candidate.id)
    return out


def sourceable_targets_for_need(ctx: PoolContext, need: NeedDeclaration) -> list[str]:
    """The subset of :func:`sourceable_targets` this member's own rules authorise.

    Widening the *search* to a substitute group is right when the question is "what
    might serve this declaration"; it is wrong when the question is "what may this run
    act on". A member who declared one coffee **exact-only** cannot join an order for a
    different one, so proposing that order as an answer to *their* button would form a
    pool for six other people because their categories happened to coincide.

    The authority is ``domain.substitution`` — the same pure function the matcher
    applies — evaluated at the most favourable bulk price any tier offers, so a target
    kept here is one some tier can genuinely use.
    """
    declared = ctx.repo.get_product(ctx.ws, need.product_id)
    if declared is None:
        return []
    out: list[str] = []
    for target_id in sourceable_targets(ctx, need.product_id):
        target = ctx.repo.get_product(ctx.ws, target_id)
        if target is None:
            continue
        verdict = evaluate_compatibility(
            target=target,
            candidate=declared,
            need=need,
            offer_unit_price_cents=best_bulk_unit_price_cents(ctx, target_id),
        )
        if verdict.compatible:
            out.append(target_id)
    return out


def best_bulk_unit_price_cents(ctx: PoolContext, product_id: str) -> int | None:
    """The cheapest per-unit price any usable bulk tier for this product will sell at.

    Discovery needs this to ask the compatibility question the matcher will later ask
    per tier: a member's per-unit price ceiling applies to every non-exact substitution,
    so a declaration rejected even at the *cheapest* tier is rejected at all of them.
    ``None`` when there is no bulk tier, which is also what the matcher is passed when
    no price is known.
    """
    _, bulk = offers_for(ctx, product_id)
    return min((o.unit_price_cents for o in bulk), default=None)


def pooled_household_ids(ctx: PoolContext, community_id: str, product_id: str) -> set[str]:
    """Members already inside a live pool for this product — do not re-recruit them."""
    out: set[str] = set()
    for pool in ctx.repo.list_pools(ctx.ws):
        if pool.community_id != community_id or pool.product_id != product_id:
            continue
        if pool.status in {PoolStatus.FAILED, PoolStatus.EXPIRED}:
            continue
        for m in ctx.repo.list_memberships(ctx.ws, pool.id):
            if m.state not in LEFT_PARTICIPATION_STATES:
                out.add(m.household_id)
    return out


def supplier_distance_km(ctx: PoolContext, offer: Offer, lat: float, lon: float) -> float:
    """Round-trip distance from a point to the offer's supplier."""
    supplier = ctx.repo.get_supplier(ctx.ws, offer.supplier_id)
    if supplier is None:
        return ESTIMATED_SUPPLIER_DISTANCE_KM * 2
    return 2 * haversine_km(lat, lon, supplier.lat, supplier.lon)


def estimate_host_reward(
    *,
    community: Community,
    orders: int,
    units: int,
    product: Product,
    distance_km: float,
    merchandise_cents: int,
) -> HostReward:
    return compute_host_reward(
        config=community.host_reward,
        orders=orders,
        units=units,
        distance_km=distance_km,
        weight_kg=estimate_weight_kg(units, product.unit_weight_grams),
        merchandise_cents=merchandise_cents,
    )


def units_in_states(ctx: PoolContext, pool_id: str, states: set[ParticipationState]) -> int:
    return sum(
        m.allocated_units
        for m in ctx.repo.list_memberships(ctx.ws, pool_id)
        if m.state in states
    )


def provisional_units(ctx: PoolContext, pool_id: str) -> int:
    from ..domain.models import PROVISIONAL_PARTICIPATION_STATES

    return units_in_states(ctx, pool_id, set(PROVISIONAL_PARTICIPATION_STATES))


def funded_units(ctx: PoolContext, pool_id: str) -> int:
    from ..domain.models import FUNDED_PARTICIPATION_STATES

    return units_in_states(ctx, pool_id, set(FUNDED_PARTICIPATION_STATES))


def in_play_units(ctx: PoolContext, pool_id: str) -> int:
    """Units that are funded *or* still awaiting a buyer's answer.

    The distinction matters for recovery: a buyer who has not replied yet has not been
    lost, and treating them as a hole would make Pool over-recruit and then have to
    disappoint someone. Only units that are genuinely gone — a failed authorisation, a
    withdrawal, a decline — need replacing.
    """
    from ..domain.models import FUNDED_PARTICIPATION_STATES

    return units_in_states(
        ctx, pool_id, set(FUNDED_PARTICIPATION_STATES) | {ParticipationState.FINAL_OFFERED}
    )


def lost_units(ctx: PoolContext, pool_id: str) -> int:
    """Units the pool has actually lost and must replace to stay whole.

    Zero until a final offer exists: before buyers have been given an exact price there
    is nothing to have lost, and treating an unpriced pool as short by its whole order
    would send the agent recruiting for a pool that has not been costed yet.
    """
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None or not pool.has_final_offer:
        return 0
    target = _priced_units(pool) or pool.threshold_units
    return max(0, target - in_play_units(ctx, pool_id))


# --------------------------------------------------------------------------- assess


def evaluate_opportunity(
    *,
    ctx: PoolContext,
    community_id: str,
    product_id: str,
    pickup_site_id: str,
    distribution_day: date | None = None,
    radius_km: float | None = None,
    exclude_household_ids: frozenset[str] = frozenset(),
    include_future_demand: bool = True,
) -> OpportunityAssessment:
    """Evaluate whether a worthwhile bulk opportunity exists for one product and site.

    Read-only: it contacts nobody, creates nothing, and commits no money, so the agent
    may call it freely (AGENTS.md §5).
    """
    community = ctx.community(community_id)
    product = ctx.repo.get_product(ctx.ws, product_id)
    site = ctx.repo.get_site(ctx.ws, pickup_site_id)
    if product is None:
        raise CoordinationError(f"unknown product: {product_id}")
    if site is None:
        raise CoordinationError(f"unknown pickup site: {pickup_site_id}")
    if site.community_id != community_id:
        raise CoordinationError("pickup site belongs to a different community")
    if radius_km is None:
        radius_km = formation_radius_km(community)

    today = ctx.now.date()
    dist_day = distribution_day or next_pool_day(today, community.schedule)
    timing = build_timing(community=community, today=today, distribution_day=dist_day)

    empty = OpportunityAssessment(
        community_id=community_id,
        product_id=product_id,
        product_name=product.name,
        pickup_site_id=site.id,
        pickup_site_name=site.name,
        pickup_is_public=site.is_public,
        distribution_day=dist_day.isoformat(),
        bulk_offer_id=None,
        retail_offer_id=None,
        viable=False,
        reason="",
        reason_code=REASON_NO_COMPATIBLE_DEMAND,
        economics=None,
        timing=timing,
        routing_provider=ctx.routing.name,
    )

    retail, bulk_offers = offers_for(ctx, product_id)
    if retail is None:
        empty.reason = "no retail baseline offer available for this product"
        empty.reason_code = REASON_NO_RETAIL_BASELINE
        return empty
    empty.retail_offer_id = retail.id
    if not bulk_offers:
        empty.reason = "no bulk offer available for this product"
        empty.reason_code = REASON_NO_BULK_OFFER
        return empty

    households = {h.id: h for h in ctx.repo.list_households(ctx.ws)}
    products = {p.id: p for p in ctx.repo.list_products(ctx.ws)}
    memberships = _memberships_map(ctx, community_id)

    # Compare every bulk tier and keep the one that maximises *net landed* savings
    # while actually clearing its own minimum. The comparison is ours; the decision to
    # investigate this product at all was the agent's.
    #
    # Everything a tier establishes is kept *with that tier*. It used to be written onto
    # one shared record inside the loop, so the rejections a caller read back were
    # whichever tier happened to be evaluated last — and the tiers genuinely disagree,
    # because a member's per-unit price ceiling is applied against each tier's own price.
    # An assessment explaining a *winning* offer with a *losing* offer's rejections is
    # exactly the kind of plausible-looking evidence a run report must not be built on.
    best: tuple[Offer, LandedEconomics, MatchResult] | None = None
    best_rejected: list[dict[str, str]] = []
    best_matched = 0
    shortfalls: list[str] = []
    #: (shortfall, -matched, min_units, offer_id) for every tier that produced no
    #: economics — the tier that came closest is the one whose numbers explain a refusal.
    near_misses: list[tuple[int, int, int, str, list[dict[str, str]]]] = []
    tiers: dict[str, dict[str, Any]] = {}
    for offer in bulk_offers:
        match = find_candidates(
            community_id=community_id,
            target_product=product,
            needs=ctx.repo.list_needs(ctx.ws),
            households=households,
            products=products,
            memberships=memberships,
            pickup_lat=site.lat,
            pickup_lon=site.lon,
            purchase_date=dist_day,
            offer_unit_price_cents=offer.unit_price_cents,
            max_radius_km=radius_km,
            exclude_household_ids=exclude_household_ids,
            include_future_demand=include_future_demand,
        )
        rejected = [
            {"need_id": r.need_id, "household_id": r.household_id, "reason": r.reason}
            for r in match.rejections
        ]
        near_misses.append(
            (
                max(0, offer.min_units - match.total_units),
                -match.total_units,
                offer.min_units,
                offer.id,
                rejected,
            )
        )
        tiers[offer.id] = {
            "offer_id": offer.id,
            "unit_price_cents": offer.unit_price_cents,
            "min_units": offer.min_units,
            "case_units": offer.case_units,
            "matched_units": match.total_units,
            "outcome": TIER_NO_COMPATIBLE_DEMAND,
        }
        if not match.candidates:
            continue
        if match.total_units < offer.min_units:
            tiers[offer.id]["outcome"] = TIER_BELOW_MINIMUM
            shortfalls.append(
                f"{offer.id} needs {offer.min_units} units, have {match.total_units}"
            )
            continue

        # Case rounding must not create inventory nobody bought, so the buyer set is
        # chosen to fill whole cases exactly rather than trimmed afterwards (§48).
        # Members whose need is already due are preferred over demand pulled forward.
        pre_fit_units = match.total_units
        fit = fit_to_cases(
            [c.need.quantity for c in match.candidates],
            case_units=offer.case_units,
            moq_units=offer.min_units,
            priority=[i for i, c in enumerate(match.candidates) if not c.is_future_pull_forward],
        )
        if not fit.ok:
            tiers[offer.id]["outcome"] = TIER_NO_CASE_FIT
            shortfalls.append(f"{offer.id}: {fit.reason}")
            continue

        fitted = [match.candidates[i] for i in fit.selected]
        match = MatchResult(match.product_id, fitted, match.rejections)
        requests = [Request(c.household.id, c.need.id, c.need.quantity) for c in fitted]
        packages = allocate_packages(offer, fit.total_units)
        merchandise = packages.cases * offer.case_price_cents
        reward = estimate_host_reward(
            community=community,
            orders=len(requests),
            units=fit.total_units,
            product=product,
            distance_km=ESTIMATED_SUPPLIER_DISTANCE_KM * 2,
            merchandise_cents=merchandise,
        )
        economics = price_pool(
            bulk_offer=offer,
            retail_offer=retail,
            requests=requests,
            host_reward=reward,
            platform_fee=community.platform_fee,
            processing_fee=community.processing_fee,
            host_is_estimated=True,
        )
        tiers[offer.id]["outcome"] = TIER_LOWER_SAVINGS
        tiers[offer.id]["net_savings_cents"] = economics.net_savings_cents
        if best is None or economics.net_savings_cents > best[1].net_savings_cents:
            best = (offer, economics, match)
            best_rejected = rejected
            # Before case fitting, which is what this field documents: how much
            # compatible, in-range, in-time demand this tier actually found.
            best_matched = pre_fit_units

    if best is None:
        # No tier priced. The refusal is explained by the tier that came closest, so the
        # two numbers a member reads — how much exists, how much is required — describe
        # one real supplier offer rather than being taken from two different ones.
        empty.offers_considered = list(tiers.values())
        near_misses.sort()
        if near_misses:
            _, negative_matched, minimum, _, rejected = near_misses[0]
            empty.matched_units = -negative_matched
            empty.minimum_units = minimum
            empty.rejected = rejected
        empty.reason = (
            "aggregate demand below every bulk minimum: " + "; ".join(shortfalls)
            if shortfalls
            else "no compatible declared demand within range"
        )
        empty.reason_code = (
            REASON_BELOW_MINIMUM if shortfalls else REASON_NO_COMPATIBLE_DEMAND
        )
        return empty

    bulk_offer, economics, match = best
    empty.bulk_offer_id = bulk_offer.id
    empty.current_units = match.current_units
    empty.future_units = match.future_units
    empty.matched_units = best_matched
    empty.minimum_units = bulk_offer.min_units
    empty.rejected = best_rejected
    tiers[bulk_offer.id]["outcome"] = TIER_SELECTED
    empty.offers_considered = list(tiers.values())

    if economics.net_savings_cents <= 0:
        empty.economics = economics
        empty.reason = "all-in Pool cost does not beat buying retail alone"
        empty.reason_code = REASON_NOT_CHEAPER
        return empty

    try:
        minutes, kms, provider = _travel_map(
            ctx, [c.household for c in match.candidates], site
        )
    except Exception as exc:  # noqa: BLE001 - routing failure is reported, never faked
        empty.economics = economics
        empty.reason = f"routing unavailable: {exc}"
        empty.reason_code = REASON_ROUTING_UNAVAILABLE
        return empty

    assessments: list[CandidateAssessment] = []
    for c in match.candidates:
        line = economics.line_for(c.household.id)
        if line is None:
            continue
        travel = minutes.get(c.household.id, 0)
        verdict = evaluate_smart_join(
            household_id=c.household.id,
            policy=c.household.autonomy,
            need=c.need,
            landed_cost_cents=line.landed_cents,
            net_savings_bps=line.savings_bps,
            travel_minutes=travel,
            is_exact_product=c.is_exact_product,
            substitution_authorised=c.compatibility.compatible,
            pickup_is_public=site.is_public,
            distribution_day=dist_day,
        )
        assessments.append(
            CandidateAssessment(
                household_id=c.household.id,
                household_name=c.household.display_name,
                need_id=c.need.id,
                units=c.need.quantity,
                is_exact_product=c.is_exact_product,
                is_future_pull_forward=c.is_future_pull_forward,
                days_early=c.timing.days_early,
                cost_cents=line.landed_cents,
                baseline_cents=line.baseline_cents,
                savings_cents=line.savings_cents,
                savings_bps=line.savings_bps,
                travel_minutes=travel,
                distance_km=kms.get(c.household.id, 0.0),
                verdict=verdict,
            )
        )

    travel_values = [a.travel_minutes for a in assessments] or [0]
    return OpportunityAssessment(
        community_id=community_id,
        product_id=product_id,
        product_name=product.name,
        pickup_site_id=site.id,
        pickup_site_name=site.name,
        pickup_is_public=site.is_public,
        distribution_day=dist_day.isoformat(),
        bulk_offer_id=bulk_offer.id,
        retail_offer_id=retail.id,
        viable=True,
        reason="viable bulk opportunity",
        reason_code=REASON_VIABLE,
        economics=economics,
        timing=timing,
        candidates=assessments,
        # The *winning* tier's rejections. Which offer a member was measured against
        # changes who it excluded, so this list travels with the offer that produced it.
        rejected=empty.rejected,
        routing_provider=provider,
        avg_travel_minutes=round(sum(travel_values) / len(travel_values)),
        max_travel_minutes=max(travel_values),
        current_units=match.current_units,
        future_units=match.future_units,
        matched_units=empty.matched_units,
        minimum_units=empty.minimum_units,
        offers_considered=empty.offers_considered,
    )


# --------------------------------------------------------------------------- create


def create_candidate_pool(
    *,
    ctx: PoolContext,
    assessment: OpportunityAssessment,
    idempotency_key: str,
) -> tuple[Pool, bool]:
    """Materialise an assessment into a candidate pool. Returns ``(pool, created)``.

    Members join **provisionally**: nobody's card is touched and nobody is asked
    anything yet (§25, §26). The pool is visible, the savings are shown as an
    estimate, and fulfilment is still being recruited. Idempotent on
    ``idempotency_key``, so a retried call returns the existing pool.
    """
    if not assessment.viable or assessment.economics is None or assessment.bulk_offer_id is None:
        raise CoordinationError(
            f"cannot create a pool from a non-viable assessment: {assessment.reason}"
        )

    for existing in ctx.repo.list_pools(ctx.ws):
        if existing.idempotency_key == idempotency_key:
            return existing, False

    # The scan above answers the common case and costs nothing extra, but it is a read
    # followed by a write: two coordinators that both find nothing both create a pool.
    # The claim settles that atomically. The loser is handed the winner's pool id rather
    # than being refused, so a retry — which is what agent systems do — returns the
    # existing pool instead of a second one (§25).
    pool_id = ctx.repo.claim_pool_idempotency(ctx.ws, idempotency_key, new_id("pool"))
    claimed = ctx.repo.get_pool(ctx.ws, pool_id)
    if claimed is not None:
        return claimed, False

    offer = ctx.repo.get_offer(ctx.ws, assessment.bulk_offer_id)
    assert offer is not None
    pool = Pool(
        id=pool_id,
        community_id=assessment.community_id,
        product_id=assessment.product_id,
        offer_id=assessment.bulk_offer_id,
        pickup_site_id=assessment.pickup_site_id,
        status=PoolStatus.FORMING,
        threshold_units=offer.min_units,
        timing=assessment.timing or PoolTiming(),
        created_by_run=ctx.run_id,
        idempotency_key=idempotency_key,
    )
    ctx.repo.put_pool(ctx.ws, pool)

    for c in assessment.candidates:
        ctx.repo.put_membership(
            ctx.ws,
            Membership(
                pool_id=pool.id,
                household_id=c.household_id,
                need_id=c.need_id,
                requested_units=c.units,
                allocated_units=c.units,
                state=ParticipationState.PROVISIONAL,
                path=AutonomyPath.PENDING_APPROVAL,
                estimated_cost_cents=c.cost_cents,
                baseline_cents=c.baseline_cents,
                travel_minutes=c.travel_minutes,
                is_exact_product=c.is_exact_product,
            ),
        )

    econ = assessment.economics
    ctx.log(
        "pool_created",
        f"Found {len(assessment.candidates)} members wanting "
        f"{assessment.product_name.lower()} and formed a candidate pool",
        {
            "product": assessment.product_name,
            "members": len(assessment.candidates),
            "provisional_units": econ.packages.total_units,
            "current_units": assessment.current_units,
            "future_units_pulled_forward": assessment.future_units,
            "threshold_units": pool.threshold_units,
            "estimated_savings_bps": econ.net_savings_bps,
            "estimated_savings_cents": econ.net_savings_cents,
            "pickup_site": assessment.pickup_site_name,
            "avg_travel_minutes": assessment.avg_travel_minutes,
            "host_status": "recruiting",
            "routing_provider": assessment.routing_provider,
        },
        pool_id=pool.id,
    )
    return pool, True


def join_pool_provisionally(
    *, ctx: PoolContext, pool_id: str, household_id: str, need_id: str
) -> Membership:
    """Add a member to a candidate pool. Not a financial commitment (§25).

    Idempotent: re-joining returns the existing membership rather than duplicating it.
    """
    pool = _require_pool(ctx, pool_id)
    if not is_open_to_joining(pool.status):
        raise CoordinationError(f"pool {pool_id} is no longer open to new members")

    existing = ctx.repo.get_membership(ctx.ws, pool_id, household_id)
    if existing is not None and existing.state not in {
        ParticipationState.WITHDRAWN,
        ParticipationState.DECLINED,
    }:
        return existing

    need = ctx.repo.get_need(ctx.ws, need_id)
    if need is None or need.household_id != household_id:
        raise CoordinationError("need does not belong to this member")
    if need.community_id != pool.community_id:
        raise CoordinationError("need belongs to a different community")

    membership = Membership(
        pool_id=pool_id,
        household_id=household_id,
        need_id=need_id,
        requested_units=need.quantity,
        allocated_units=need.quantity,
        state=ParticipationState.PROVISIONAL,
        path=AutonomyPath.HUMAN_APPROVED,
    )
    ctx.repo.put_membership(ctx.ws, membership)
    ctx.log(
        "member_joined",
        "A member joined the candidate pool provisionally",
        {"units": need.quantity},
        pool_id=pool_id,
        household_id=household_id,
    )
    return membership


# --------------------------------------------------------------------------- quotes


@dataclass
class QuoteRefresh:
    ok: bool
    offer: Offer | None
    changed: bool
    previous_unit_price_cents: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "changed": self.changed,
            "previous_unit_price_cents": self.previous_unit_price_cents,
            "unit_price_cents": self.offer.unit_price_cents if self.offer else 0,
            "verified_at": self.offer.verified_at if self.offer else "",
            "reason": self.reason,
        }


def refresh_quote(*, ctx: PoolContext, pool_id: str) -> QuoteRefresh:
    """Re-verify a pool's supplier quote and persist the result (§43).

    A refreshed price is written back to the offer, so any economics computed after
    this call use the current terms. If the provider cannot re-verify, that is
    reported honestly and the pool cannot proceed to a final offer.
    """
    pool = _require_pool(ctx, pool_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    if offer is None:
        raise CoordinationError(f"pool references a missing offer: {pool.offer_id}")

    result = ctx.sourcing.refresh(offer)
    if not result.ok or result.offer is None:
        ctx.log(
            "quote_refresh_failed",
            "Supplier quote could not be re-verified",
            {"offer_id": offer.id, "reason": result.reason},
            pool_id=pool_id,
        )
        return QuoteRefresh(False, offer, False, offer.unit_price_cents, result.reason)

    ctx.repo.put_offer(ctx.ws, result.offer)
    pool.quote_verified_at = result.offer.verified_at
    ctx.repo.put_pool(ctx.ws, pool)
    if result.changed:
        # A moved price invalidates any final economics built on the old one.
        pool.final_economics = {}
        ctx.repo.put_pool(ctx.ws, pool)
        ctx.log(
            "quote_changed",
            "Supplier re-quoted at a different price; final economics invalidated",
            {
                "offer_id": offer.id,
                "previous_unit_price_cents": result.previous_unit_price_cents,
                "unit_price_cents": result.offer.unit_price_cents,
            },
            pool_id=pool_id,
        )
    return QuoteRefresh(
        True, result.offer, result.changed, result.previous_unit_price_cents, result.reason
    )


# --------------------------------------------------------------------------- pricing


def _active_memberships(ctx: PoolContext, pool_id: str) -> list[Membership]:
    return [
        m
        for m in ctx.repo.list_memberships(ctx.ws, pool_id)
        if m.state
        not in {
            ParticipationState.WITHDRAWN,
            ParticipationState.DECLINED,
            ParticipationState.AUTHORIZATION_FAILED,
        }
    ]


def price_pool_now(
    *,
    ctx: PoolContext,
    pool: Pool,
    members: list[Membership],
    host_reward: HostReward | None,
    host_is_estimated: bool,
) -> LandedEconomics:
    """Compute complete landed economics for a specific member set."""
    community = ctx.community(pool.community_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    retail, _ = offers_for(ctx, pool.product_id)
    if offer is None or retail is None:
        raise CoordinationError("pool references a missing offer or retail baseline")
    requests = [Request(m.household_id, m.need_id, m.allocated_units) for m in members]
    return price_pool(
        bulk_offer=offer,
        retail_offer=retail,
        requests=requests,
        host_reward=host_reward,
        platform_fee=community.platform_fee,
        processing_fee=community.processing_fee,
        host_is_estimated=host_is_estimated,
    )


@dataclass
class FinalOfferResult:
    pool_id: str
    issued: bool
    reason: str
    economics: dict[str, Any] | None = None
    auto_authorised: list[str] = field(default_factory=list)
    awaiting_decision: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    authorisation_failures: list[str] = field(default_factory=list)
    surplus_units: int = 0
    status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "issued": self.issued,
            "reason": self.reason,
            "economics": self.economics,
            "auto_authorised": self.auto_authorised,
            "awaiting_decision": self.awaiting_decision,
            "removed": self.removed,
            "authorisation_failures": self.authorisation_failures,
            "surplus_units": self.surplus_units,
            "status": self.status,
        }


def issue_final_offer(*, ctx: PoolContext, pool_id: str) -> FinalOfferResult:
    """Refresh the quote, compute exact landed economics, and issue the final offer.

    This is the point at which estimates become commitments, so the order is fixed
    (§35): host selected → quote refreshed → exact landed cost → final offer → buyer
    policies evaluated → payment authorisation.

    Buyers whose own rules **cannot** accept the final price are removed from the pool
    and the price is recomputed for everyone else — a bounded fixed point, because
    removing a buyer changes the per-unit split.

    **Convergence contract.** A final offer may only rest on economics that were
    computed for exactly the membership set that survives. So economics are adopted
    *only* from a pass that rejected nobody; a pass that prunes discards its own numbers
    before iterating. If no such pass occurs inside :data:`MAX_PRICING_PASSES`, the pool
    fails loudly and authorises nobody, rather than issuing prices computed for a set
    that no longer exists.

    Without that rule the last permitted pass could prune and fall out of the loop
    carrying the *previous* set's economics — which is not merely a display error. Those
    per-buyer amounts are what ``authorize_participant`` puts a hold on, and the case
    count is what the supplier order is sized from, so a stale pair would authorise
    money at the wrong price and buy units nobody ordered (§48).
    """
    from . import payments as payment_service

    pool = _require_pool(ctx, pool_id)
    community = ctx.community(pool.community_id)
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if site is None or product is None:
        raise CoordinationError("pool references a missing site or product")
    if assignment is None:
        return FinalOfferResult(
            pool_id, False, "no host has accepted this pool yet", status=pool.status.value
        )

    refresh = refresh_quote(ctx=ctx, pool_id=pool_id)
    if not refresh.ok or refresh.offer is None:
        return FinalOfferResult(
            pool_id, False, f"supplier quote could not be re-verified: {refresh.reason}",
            status=pool.status.value,
        )
    pool = _require_pool(ctx, pool_id)

    removed: list[str] = []
    members = _active_memberships(ctx, pool_id)
    economics: LandedEconomics | None = None
    converged = False

    for _ in range(MAX_PRICING_PASSES):
        if not members:
            break
        reward = compute_host_reward(
            config=community.host_reward,
            orders=len(members),
            units=sum(m.allocated_units for m in members),
            distance_km=assignment.supplier_distance_km,
            weight_kg=estimate_weight_kg(
                sum(m.allocated_units for m in members), product.unit_weight_grams
            ),
            merchandise_cents=0,
        )
        # Held on a local until this pass proves it changed nobody. Assigning straight
        # to `economics` is what let a pruning final pass leave the loop with numbers
        # describing a membership set that no longer exists.
        priced = price_pool_now(
            ctx=ctx, pool=pool, members=members, host_reward=reward, host_is_estimated=False
        )
        rejected_now: list[Membership] = []
        for m in members:
            line = priced.line_for(m.household_id)
            household = ctx.repo.get_household(ctx.ws, m.household_id)
            need = ctx.repo.get_need(ctx.ws, m.need_id)
            if line is None or household is None or need is None:
                continue
            verdict = evaluate_smart_join(
                household_id=m.household_id,
                policy=household.autonomy,
                need=need,
                landed_cost_cents=line.landed_cents,
                net_savings_bps=line.savings_bps,
                travel_minutes=m.travel_minutes,
                is_exact_product=m.is_exact_product,
                substitution_authorised=True,
                pickup_is_public=site.is_public,
                distribution_day=_distribution_date(pool),
            )
            if verdict.kind == JoinVerdictKind.NOT_ALLOWED:
                rejected_now.append(m)
        if not rejected_now:
            # The set this was priced for is the set that survives. Only now is it safe
            # to adopt, and this is the *only* place `economics` is ever assigned.
            economics = priced
            converged = True
            break
        for m in rejected_now:
            m.state = ParticipationState.DECLINED
            ctx.repo.put_membership(ctx.ws, m)
            removed.append(m.household_id)
        members = [m for m in members if m not in rejected_now]

    if not members:
        _fail(ctx, pool, "no buyer's rules accept the final price")
        return FinalOfferResult(
            pool_id, False, "no buyer's rules accept the final price", removed=removed,
            status=pool.status.value,
        )

    if not converged or economics is None:
        # Buyers were still being pruned when the last permitted pass ran, so no pass
        # ever priced the set that survives. There is no honest number to offer: the
        # last figures computed describe a larger group, and re-using them would
        # authorise money at a price nobody was quoted. Fail loudly instead (§3.1).
        reason = (
            f"final pricing did not settle within {MAX_PRICING_PASSES} "
            f"pass{'es' if MAX_PRICING_PASSES != 1 else ''} — the buyer set was still "
            "changing when the last one ran"
        )
        ctx.log(
            "final_offer_not_converged",
            "Final pricing did not settle on a stable buyer set, so no price was "
            "issued and nobody was charged",
            {
                "passes": MAX_PRICING_PASSES,
                "removed": removed,
                "remaining_buyers": len(members),
            },
            pool_id=pool_id,
        )
        _fail(ctx, pool, reason)
        return FinalOfferResult(
            pool_id, False, reason, removed=removed, status=pool.status.value
        )

    # Case rounding must not create inventory nobody bought (§48).
    if not economics.packages.surplus_resolved:
        ctx.log(
            "surplus_unallocated",
            f"{economics.packages.surplus_units} unit(s) of a "
            f"{economics.packages.case_units}-unit case have no buyer — Pool will not "
            "buy speculative stock",
            economics.packages.to_dict(),
            pool_id=pool_id,
        )
        return FinalOfferResult(
            pool_id,
            False,
            "case rounding leaves unallocated units and Pool does not buy speculative stock",
            economics=economics.to_dict(),
            surplus_units=economics.packages.surplus_units,
            removed=removed,
            status=pool.status.value,
        )

    if economics.net_savings_cents <= 0:
        return FinalOfferResult(
            pool_id, False, "final landed cost does not beat retail",
            economics=economics.to_dict(), removed=removed, status=pool.status.value,
        )

    # Record the offer and move the pool into FINAL_OFFER before touching any money.
    pool.final_economics = economics.to_dict()
    pool.quote_verified_at = refresh.offer.verified_at
    pool.status = assert_transition(pool.status, PoolStatus.FINAL_OFFER)
    ctx.repo.put_pool(ctx.ws, pool)

    auto: list[str] = []
    asked: list[str] = []
    failures: list[str] = []
    now_iso = iso(ctx.now)

    for m in members:
        line = economics.line_for(m.household_id)
        household = ctx.repo.get_household(ctx.ws, m.household_id)
        need = ctx.repo.get_need(ctx.ws, m.need_id)
        if line is None or household is None or need is None:
            continue
        m.final_cost_cents = line.landed_cents
        m.final_savings_cents = line.savings_cents
        m.final_savings_bps = line.savings_bps
        m.final_offer_at = now_iso
        m.state = ParticipationState.FINAL_OFFERED
        ctx.repo.put_membership(ctx.ws, m)

        verdict = evaluate_smart_join(
            household_id=m.household_id,
            policy=household.autonomy,
            need=need,
            landed_cost_cents=line.landed_cents,
            net_savings_bps=line.savings_bps,
            travel_minutes=m.travel_minutes,
            is_exact_product=m.is_exact_product,
            substitution_authorised=True,
            pickup_is_public=site.is_public,
            distribution_day=_distribution_date(pool),
        )
        if verdict.kind == JoinVerdictKind.AUTO_APPROVED:
            result = payment_service.authorize_participant(
                ctx=ctx, pool_id=pool_id, household_id=m.household_id,
                path=AutonomyPath.SMART_JOIN,
            )
            (auto if result.ok else failures).append(m.household_id)
        else:
            asked.append(m.household_id)
            _create_final_offer_decision(ctx, pool, m, line, product.name, verdict)

    pool = _require_pool(ctx, pool_id)
    pool.status = assert_transition(pool.status, PoolStatus.FUNDING)
    ctx.repo.put_pool(ctx.ws, pool)

    ctx.log(
        "final_offer_issued",
        f"Exact landed price issued to {len(members)} buyer(s) after host selection "
        "and a fresh supplier quote",
        {
            "buyers": len(members),
            "auto_authorised": len(auto),
            "awaiting_decision": len(asked),
            "authorisation_failures": len(failures),
            "removed": len(removed),
            "merchandise_cents": economics.merchandise_cents,
            "host_compensation_cents": economics.host_compensation_cents,
            "payment_processing_cents": economics.payment_processing_cents,
            "platform_fee_cents": economics.platform_fee_cents,
            "all_in_cents": economics.all_in_cents,
            "retail_baseline_cents": economics.retail_baseline_cents,
            "net_savings_cents": economics.net_savings_cents,
            "net_savings_bps": economics.net_savings_bps,
            "quote_verified_at": pool.quote_verified_at,
        },
        pool_id=pool_id,
    )
    return FinalOfferResult(
        pool_id=pool_id,
        issued=True,
        reason="final offer issued",
        economics=economics.to_dict(),
        auto_authorised=auto,
        awaiting_decision=asked,
        removed=removed,
        authorisation_failures=failures,
        status=pool.status.value,
    )


def _create_final_offer_decision(
    ctx: PoolContext,
    pool: Pool,
    membership: Membership,
    line,
    product_name: str,
    verdict: PolicyVerdict,
) -> DecisionRequest:
    """Ask one human, with the whole answer already worked out."""
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    econ = pool.final_economics or {}
    decision = DecisionRequest(
        id=new_id("dec"),
        household_id=membership.household_id,
        pool_id=pool.id,
        kind=DecisionKind.APPROVE_FINAL_OFFER,
        state=DecisionState.PENDING,
        facts={
            "product": product_name,
            "units": membership.allocated_units,
            "final_cost_cents": line.landed_cents,
            "final_cost_display": format_cents(line.landed_cents),
            "baseline_cents": line.baseline_cents,
            "baseline_display": format_cents(line.baseline_cents),
            "savings_cents": line.savings_cents,
            "savings_bps": line.savings_bps,
            "cost_breakdown": {
                "merchandise": line.merchandise_share_cents,
                "host_compensation": line.host_share_cents,
                "pool_fee": line.platform_fee_share_cents,
                "payment_processing": line.processing_cents,
            },
            "travel_minutes": membership.travel_minutes,
            "pickup_site": site.name if site else "",
            "distribution_starts_at": pool.timing.distribution_starts_at,
            "host_compensation_total_cents": econ.get("host_compensation_cents", 0),
            "blocking_rule": (verdict.failed_rules[0] if verdict.failed_rules else None),
            "policy_checks": [c.to_dict() for c in verdict.checks],
        },
        expires_at=pool.timing.authorization_deadline
        or iso(ctx.now + timedelta(days=2)),
    )
    ctx.repo.put_decision(ctx.ws, decision)
    return decision


def _distribution_date(pool: Pool) -> date | None:
    if not pool.timing.distribution_starts_at:
        return None
    return parse_iso(pool.timing.distribution_starts_at).date()


# --------------------------------------------------------------------------- HITL


def respond_to_decision(
    *, ctx: PoolContext, decision_id: str, approve: bool
) -> DecisionRequest:
    """Record a human's answer. Idempotent — re-answering an answered decision is a no-op."""
    from . import payments as payment_service

    decision = ctx.repo.get_decision(ctx.ws, decision_id)
    if decision is None:
        raise CoordinationError(f"unknown decision: {decision_id}")
    if decision.state != DecisionState.PENDING:
        return decision  # already answered; do not double-count

    decision.state = DecisionState.APPROVED if approve else DecisionState.REJECTED
    ctx.repo.put_decision(ctx.ws, decision)

    if decision.kind in {DecisionKind.APPROVE_FINAL_OFFER, DecisionKind.PRICE_CHANGED}:
        membership = ctx.repo.get_membership(ctx.ws, decision.pool_id, decision.household_id)
        if membership is not None:
            if approve:
                payment_service.authorize_participant(
                    ctx=ctx,
                    pool_id=decision.pool_id,
                    household_id=decision.household_id,
                    path=AutonomyPath.HUMAN_APPROVED,
                )
            else:
                membership.state = ParticipationState.DECLINED
                ctx.repo.put_membership(ctx.ws, membership)

    elif decision.kind == DecisionKind.HOST_OFFER:
        # Answering a host offer here used to mark the decision approved and do nothing
        # else: the candidate stayed OFFERED, no assignment was written, and the pool sat
        # in HOST_RECRUITING forever. The decision inbox is the one place a person answers
        # anything Pool asks, so an offer answered there has to reach the same service the
        # host's own endpoint calls. Imported inside the function because `hosting` imports
        # from this module at load time.
        from . import hosting

        hosting.respond_to_host_offer(
            ctx=ctx,
            pool_id=decision.pool_id,
            household_id=decision.household_id,
            accept=approve,
        )

    # The summary has to match the question that was asked. It previously said "Buyer
    # approved the final offer" for every kind, including a host being offered a job.
    if decision.kind == DecisionKind.HOST_OFFER:
        summary = "Host accepted the fulfilment job" if approve else "Host declined the job"
    elif approve:
        summary = "Buyer approved the final offer"
    else:
        summary = "Buyer declined the final offer"

    ctx.log(
        "decision_answered",
        summary,
        {"decision_id": decision.id, "kind": decision.kind.value, "approved": approve},
        pool_id=decision.pool_id,
        household_id=decision.household_id,
    )
    return decision


# --------------------------------------------------------------------------- exit


def withdraw_participant(
    *, ctx: PoolContext, pool_id: str, household_id: str
) -> dict[str, Any]:
    """A buyer leaves. The boundary is the lock, and it is explicit (§59).

    Before authorisation: free. Authorised but not locked: the authorisation is
    released and the pool tries to recover. Locked or later: refused — the money is
    captured and the supplier order is committed.
    """
    from . import payments as payment_service

    pool = _require_pool(ctx, pool_id)
    membership = ctx.repo.get_membership(ctx.ws, pool_id, household_id)
    if membership is None:
        raise CoordinationError(f"{household_id} is not a member of {pool_id}")
    if membership.state == ParticipationState.WITHDRAWN:
        return {"already_withdrawn": True, "pool_id": pool_id, "household_id": household_id}

    from ..domain.state import is_committed

    if is_committed(pool.status):
        raise CoordinationError(
            "this pool has locked: payment is captured and the supplier order is "
            "committed, so it cannot be cancelled with one click"
        )

    released = membership.allocated_units
    cancelled = False
    if membership.state in {ParticipationState.AUTHORIZED} and membership.payment_id:
        cancelled = payment_service.cancel_authorization(
            ctx=ctx, payment_id=membership.payment_id
        ).ok

    membership.state = ParticipationState.WITHDRAWN
    ctx.repo.put_membership(ctx.ws, membership)

    ctx.log(
        "participant_withdrew",
        f"A buyer withdrew before lock, releasing {released} units",
        {
            "released_units": released,
            "threshold_units": pool.threshold_units,
            "authorization_released": cancelled,
        },
        pool_id=pool_id,
        household_id=household_id,
    )

    funded = funded_units(ctx, pool_id)
    if funded < pool.threshold_units and pool.status in {
        PoolStatus.FUNDING,
        PoolStatus.FINAL_OFFER,
    }:
        pool.status = assert_transition(pool.status, PoolStatus.RECOVERING)
        ctx.repo.put_pool(ctx.ws, pool)

    return {
        "already_withdrawn": False,
        "pool_id": pool_id,
        "household_id": household_id,
        "released_units": released,
        "authorization_released": cancelled,
        "funded_units": funded,
        "threshold_units": pool.threshold_units,
        "below_threshold": funded < pool.threshold_units,
        "pool_status": pool.status.value,
    }


# --------------------------------------------------------------------------- lock


def check_viability(
    *, ctx: PoolContext, pool_id: str, stage: ViabilityStage
) -> ViabilityVerdict:
    """Run the central viability engine against stored facts (§51)."""
    pool = _require_pool(ctx, pool_id)
    community = ctx.community(pool.community_id)
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    if site is None or offer is None:
        raise CoordinationError("pool references a missing site or offer")

    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    members = _active_memberships(ctx, pool_id)
    funded = funded_units(ctx, pool_id)

    if pool.final_economics:
        economics = _economics_from_snapshot(ctx, pool, members, assignment)
    else:
        economics = price_pool_now(
            ctx=ctx,
            pool=pool,
            members=members,
            host_reward=_assignment_reward(assignment),
            host_is_estimated=assignment is None,
        )

    host_profile = (
        ctx.repo.get_host_profile(ctx.ws, pool.community_id, assignment.household_id)
        if assignment
        else None
    )
    reward_ok = bool(
        assignment
        and (
            host_profile is None
            or assignment.reward_total_cents >= host_profile.minimum_compensation_cents
        )
    )

    awaiting = sum(
        1
        for d in ctx.repo.list_decisions(ctx.ws)
        if d.pool_id == pool_id and d.state == DecisionState.PENDING
    )
    failing = sum(
        1 for m in members if m.state == ParticipationState.AUTHORIZATION_FAILED
    )

    return evaluate_viability(
        ViabilityInputs(
            community=community,
            economics=economics,
            bulk_offer=offer,
            site=site,
            timing=pool.timing,
            funded_units=funded,
            provisional_units=provisional_units(ctx, pool_id),
            host_assigned=assignment is not None,
            host_reward_meets_minimum=reward_ok,
            buyers_failing_policy=failing,
            buyers_awaiting_decision=awaiting,
            now=ctx.now,
        ),
        stage,
    )


def lock_pool(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """Lock a pool, then capture. Only ever on authoritative deterministic facts (§51).

    Locking is the point of no return, so the final viability check runs against stored
    state — not against anything the model said, and not against the estimate a
    candidate pool displayed.
    """
    from . import payments as payment_service

    pool = _require_pool(ctx, pool_id)
    if pool.status in {PoolStatus.LOCKED, PoolStatus.PURCHASE_READY, PoolStatus.PURCHASED}:
        return {"pool_id": pool_id, "locked": True, "already_locked": True,
                "status": pool.status.value}

    verdict = check_viability(ctx=ctx, pool_id=pool_id, stage=ViabilityStage.FINAL_LOCK)
    if not verdict.viable:
        ctx.log(
            "lock_blocked",
            f"Pool did not lock: {verdict.blocking_reason}",
            {"failed_checks": verdict.failed},
            pool_id=pool_id,
        )
        return {
            "pool_id": pool_id,
            "locked": False,
            "reason": verdict.blocking_reason,
            "viability": verdict.to_dict(),
            "status": pool.status.value,
        }

    pool.status = assert_transition(pool.status, PoolStatus.LOCKED)
    ctx.repo.put_pool(ctx.ws, pool)
    for m in _active_memberships(ctx, pool_id):
        if m.state == ParticipationState.AUTHORIZED:
            m.state = ParticipationState.LOCKED
            ctx.repo.put_membership(ctx.ws, m)

    ctx.log(
        "pool_locked",
        "Every viability condition passed — pool locked; "
        f"{'simulated' if ctx.payments.mode == 'simulated' else 'test-mode'} "
        "capture is beginning",
        {
            "funded_units": funded_units(ctx, pool_id),
            "threshold_units": pool.threshold_units,
            "checks_passed": [c.name for c in verdict.checks],
            "provider_mode": ctx.payments.mode,
        },
        pool_id=pool_id,
    )

    capture = payment_service.capture_pool(ctx=ctx, pool_id=pool_id)
    pool = _require_pool(ctx, pool_id)
    return {
        "pool_id": pool_id,
        "locked": True,
        "status": pool.status.value,
        "viability": verdict.to_dict(),
        "capture": capture,
    }


# --------------------------------------------------------------------------- recovery


@dataclass
class RecoveryResult:
    pool_id: str
    recovered: bool
    reason: str
    shortfall_units: int = 0
    added_household_ids: list[str] = field(default_factory=list)
    invited_household_ids: list[str] = field(default_factory=list)
    new_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "recovered": self.recovered,
            "reason": self.reason,
            "shortfall_units": self.shortfall_units,
            "added_household_ids": self.added_household_ids,
            "invited_household_ids": self.invited_household_ids,
            "new_status": self.new_status,
        }


def recover_pool(
    *, ctx: PoolContext, pool_id: str, radius_km: float | None = None
) -> RecoveryResult:
    """Attempt to restore a pool that lost funded demand.

    The quietest sufficient repair wins (AGENTS.md §5): Pool looks for compatible
    members who are not already in the pool, adds the ones whose own Smart Join policy
    pre-authorises the *current final price*, and only asks a human when it must.
    Existing buyers are never silently re-priced — a replacement changes the split, so
    anyone whose share rises past their own cap is asked rather than charged.
    """
    pool = _require_pool(ctx, pool_id)
    community = ctx.community(pool.community_id)
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if product is None or site is None or offer is None:
        raise CoordinationError("pool references a missing product, site, or offer")
    if radius_km is None:
        radius_km = recovery_radius_km(community)

    # Replace only what is genuinely gone. Buyers who have not yet answered their final
    # offer are still in play, and recruiting over the top of them would leave Pool
    # over-subscribed and someone disappointed.
    target = max(pool.threshold_units, _priced_units(pool) or pool.threshold_units)
    shortfall = target - in_play_units(ctx, pool_id)
    if shortfall <= 0:
        return RecoveryResult(
            pool_id, True, "no demand has been lost; the pool is still whole", 0,
            new_status=pool.status.value,
        )

    involved = {m.household_id for m in ctx.repo.list_memberships(ctx.ws, pool_id)}
    households = {h.id: h for h in ctx.repo.list_households(ctx.ws)}
    products = {p.id: p for p in ctx.repo.list_products(ctx.ws)}
    dist_day = _distribution_date(pool) or next_pool_day(ctx.now.date(), community.schedule)

    match = find_candidates(
        community_id=pool.community_id,
        target_product=product,
        needs=ctx.repo.list_needs(ctx.ws),
        households=households,
        products=products,
        memberships=_memberships_map(ctx, pool.community_id),
        pickup_lat=site.lat,
        pickup_lon=site.lon,
        purchase_date=dist_day,
        offer_unit_price_cents=offer.unit_price_cents,
        max_radius_km=radius_km,
        exclude_household_ids=frozenset(involved),
    )

    if not match.candidates:
        ctx.log(
            "recovery_failed",
            "No compatible replacement demand found in this community",
            {"shortfall_units": shortfall},
            pool_id=pool_id,
        )
        return RecoveryResult(
            pool_id, False, "no compatible replacement demand available", shortfall,
            new_status=pool.status.value,
        )

    # Prefer a set that covers the shortfall *exactly*: an exact fill both restores the
    # threshold and keeps case rounding clean, so the pool does not trade a funding
    # problem for a surplus problem.
    chosen = _select_replacements(match.candidates, shortfall)
    if not chosen:
        ctx.log(
            "recovery_failed",
            f"No combination of available demand replaces exactly {shortfall} unit(s), "
            "and Pool will not over-buy to close the gap",
            {"shortfall_units": shortfall, "candidates": len(match.candidates)},
            pool_id=pool_id,
        )
        return RecoveryResult(
            pool_id, False, "available replacement demand cannot restore the order cleanly",
            shortfall, new_status=pool.status.value,
        )

    try:
        minutes, _kms, _ = _travel_map(ctx, [c.household for c in chosen], site)
    except Exception as exc:  # noqa: BLE001
        return RecoveryResult(
            pool_id, False, f"routing unavailable during recovery: {exc}", shortfall,
            new_status=pool.status.value,
        )

    # Price the pool as it *would* be with the replacements included.
    keep = [m for m in _active_memberships(ctx, pool_id)]
    provisional = [
        Membership(
            pool_id=pool_id,
            household_id=c.household.id,
            need_id=c.need.id,
            requested_units=c.need.quantity,
            allocated_units=c.need.quantity,
            state=ParticipationState.PROVISIONAL,
            path=AutonomyPath.PENDING_APPROVAL,
            travel_minutes=minutes.get(c.household.id, 0),
            is_exact_product=c.is_exact_product,
        )
        for c in chosen
    ]
    economics = price_pool_now(
        ctx=ctx,
        pool=pool,
        members=keep + provisional,
        host_reward=_assignment_reward(assignment),
        host_is_estimated=assignment is None,
    )

    for m in provisional:
        ctx.repo.put_membership(ctx.ws, m)

    added, invited = _authorise_replacements(
        ctx, pool, provisional, economics, site, product.name
    )
    _reprice_existing(ctx, pool, keep, economics, site)

    pool = _require_pool(ctx, pool_id)
    if pool.status == PoolStatus.RECOVERING:
        pool.status = assert_transition(pool.status, PoolStatus.FUNDING)
        ctx.repo.put_pool(ctx.ws, pool)

    # Recovery succeeds when the *hole* is filled, not when the whole pool is funded:
    # buyers who have simply not answered their final offer yet are not something
    # recovery can or should fix, and claiming otherwise would misreport the outcome.
    funded_after = funded_units(ctx, pool_id)
    recovered = in_play_units(ctx, pool_id) >= target
    ctx.log(
        "pool_recovered" if recovered else "recovery_pending",
        "Pool recovered automatically — a buyer dropped and Pool matched compatible "
        "replacement demand, preserving the group order"
        if recovered
        else f"Recovery under way — {len(invited)} member(s) asked to fill the gap",
        {
            "shortfall_units": shortfall,
            "replacements_authorised": len(added),
            "replacements_asked": len(invited),
            "funded_units": funded_after,
            "threshold_units": pool.threshold_units,
        },
        pool_id=pool_id,
    )
    return RecoveryResult(
        pool_id=pool_id,
        recovered=recovered,
        reason="funded demand restored" if recovered else "awaiting replacement approval",
        shortfall_units=shortfall,
        added_household_ids=added,
        invited_household_ids=invited,
        new_status=pool.status.value,
    )


def _select_replacements(candidates, shortfall: int):
    """Choose replacements summing to **exactly** the shortfall.

    Exactly, not "at least": the order the pool is already priced against fills whole
    cases, so over-recruiting would reintroduce the surplus that §48 exists to prevent —
    trading a funding problem for speculative stock. If no combination lands on the
    number, recovery fails honestly and the pool does not lock.

    A single candidate is preferred (fewest people disturbed), then the smallest
    combination, with nearer members first so travel burden stays low.
    """
    if shortfall <= 0:
        return []
    ordered = sorted(candidates, key=lambda c: (c.distance_km, c.need.id))
    exact = [c for c in ordered if c.need.quantity == shortfall]
    if exact:
        return [exact[0]]

    # Bounded exact-sum search: reachable total -> the fewest candidates reaching it.
    states: dict[int, list] = {0: []}
    for candidate in ordered:
        for total in sorted(states.keys(), reverse=True):
            new_total = total + candidate.need.quantity
            if new_total > shortfall:
                continue
            chosen = [*states[total], candidate]
            existing = states.get(new_total)
            if existing is None or len(chosen) < len(existing):
                states[new_total] = chosen
    return states.get(shortfall, [])


def _authorise_replacements(
    ctx: PoolContext,
    pool: Pool,
    provisional: list[Membership],
    economics: LandedEconomics,
    site: PickupSite,
    product_name: str,
) -> tuple[list[str], list[str]]:
    from . import payments as payment_service

    added: list[str] = []
    invited: list[str] = []
    for m in provisional:
        line = economics.line_for(m.household_id)
        household = ctx.repo.get_household(ctx.ws, m.household_id)
        need = ctx.repo.get_need(ctx.ws, m.need_id)
        if line is None or household is None or need is None:
            continue
        m.final_cost_cents = line.landed_cents
        m.final_savings_cents = line.savings_cents
        m.final_savings_bps = line.savings_bps
        m.baseline_cents = line.baseline_cents
        m.final_offer_at = iso(ctx.now)
        m.state = ParticipationState.FINAL_OFFERED
        ctx.repo.put_membership(ctx.ws, m)

        verdict = evaluate_smart_join(
            household_id=m.household_id,
            policy=household.autonomy,
            need=need,
            landed_cost_cents=line.landed_cents,
            net_savings_bps=line.savings_bps,
            travel_minutes=m.travel_minutes,
            is_exact_product=m.is_exact_product,
            substitution_authorised=True,
            pickup_is_public=site.is_public,
            distribution_day=_distribution_date(pool),
        )
        if verdict.kind == JoinVerdictKind.AUTO_APPROVED:
            result = payment_service.authorize_participant(
                ctx=ctx, pool_id=pool.id, household_id=m.household_id,
                path=AutonomyPath.SMART_JOIN,
            )
            if result.ok:
                added.append(m.household_id)
            else:
                invited.append(m.household_id)
        elif verdict.kind == JoinVerdictKind.HUMAN_APPROVAL_REQUIRED:
            invited.append(m.household_id)
            _create_final_offer_decision(ctx, pool, m, line, product_name, verdict)
        else:
            m.state = ParticipationState.DECLINED
            ctx.repo.put_membership(ctx.ws, m)
    return added, invited


def _reprice_existing(
    ctx: PoolContext,
    pool: Pool,
    members: list[Membership],
    economics: LandedEconomics,
    site: PickupSite,
) -> list[str]:
    """Update existing buyers' shares, asking rather than charging when they rise.

    Silently raising someone's cost past their own cap is exactly the "materially worse
    terms" case that requires approval (AGENTS.md §5), and a buyer who already
    authorised a smaller amount cannot simply be charged more (§35).
    """
    asked: list[str] = []
    for m in members:
        line = economics.line_for(m.household_id)
        if line is None or line.landed_cents == m.final_cost_cents:
            continue
        worse = m.final_cost_cents and line.landed_cents > m.final_cost_cents
        household = ctx.repo.get_household(ctx.ws, m.household_id)
        need = ctx.repo.get_need(ctx.ws, m.need_id)
        if household is None or need is None:
            continue
        if worse:
            verdict = evaluate_smart_join(
                household_id=m.household_id,
                policy=household.autonomy,
                need=need,
                landed_cost_cents=line.landed_cents,
                net_savings_bps=line.savings_bps,
                travel_minutes=m.travel_minutes,
                is_exact_product=m.is_exact_product,
                substitution_authorised=True,
                pickup_is_public=site.is_public,
                distribution_day=_distribution_date(pool),
            )
            if verdict.kind != JoinVerdictKind.AUTO_APPROVED:
                asked.append(m.household_id)
                ctx.repo.put_decision(
                    ctx.ws,
                    DecisionRequest(
                        id=new_id("dec"),
                        household_id=m.household_id,
                        pool_id=pool.id,
                        kind=DecisionKind.PRICE_CHANGED,
                        state=DecisionState.PENDING,
                        facts={
                            "previous_cost_cents": m.final_cost_cents,
                            "new_cost_cents": line.landed_cents,
                            "new_cost_display": format_cents(line.landed_cents),
                            "savings_bps": line.savings_bps,
                            "reason": "the group changed, which changed your share",
                            "policy_checks": [c.to_dict() for c in verdict.checks],
                        },
                        expires_at=pool.timing.authorization_deadline,
                    ),
                )
                continue
        m.final_cost_cents = line.landed_cents
        m.final_savings_cents = line.savings_cents
        m.final_savings_bps = line.savings_bps
        m.baseline_cents = line.baseline_cents
        ctx.repo.put_membership(ctx.ws, m)
    return asked


# --------------------------------------------------------------------------- internals


def _require_pool(ctx: PoolContext, pool_id: str) -> Pool:
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")
    return pool


def _fail(ctx: PoolContext, pool: Pool, reason: str) -> None:
    pool.status = assert_transition(pool.status, PoolStatus.FAILED)
    pool.failure_reason = reason
    ctx.repo.put_pool(ctx.ws, pool)
    ctx.log("pool_failed", f"Pool could not proceed: {reason}", {}, pool_id=pool.id)


def _priced_units(pool: Pool) -> int:
    return int((pool.final_economics or {}).get("packages", {}).get("total_units", 0))


def _assignment_reward(assignment) -> HostReward | None:
    if assignment is None:
        return None
    b = assignment.reward_breakdown
    return HostReward(
        base_cents=b.get("base", 0),
        per_order_cents=b.get("per_order", 0),
        distance_cents=b.get("distance", 0),
        weight_cents=b.get("weight", 0),
        merchandise_share_cents=b.get("merchandise_share", 0),
        handoff_bonus_cents=b.get("handoff_bonus", 0),
        total_cents=assignment.reward_total_cents,
        earned_cents=assignment.reward_earned_cents,
        contingent_cents=assignment.reward_contingent_cents,
        orders=assignment.handled_orders,
        distance_km=assignment.supplier_distance_km,
        weight_kg=assignment.estimated_weight_kg,
    )


def _economics_from_snapshot(
    ctx: PoolContext, pool: Pool, members: list[Membership], assignment
) -> LandedEconomics:
    """Re-derive economics for the current member set using the assigned host's reward."""
    return price_pool_now(
        ctx=ctx,
        pool=pool,
        members=members,
        host_reward=_assignment_reward(assignment),
        host_is_estimated=assignment is None,
    )


# --------------------------------------------------------------------------- metrics


def impact_metrics(ctx: PoolContext) -> dict[str, Any]:
    """Compute impact from stored state. Every figure traces to a record (§98).

    Nothing here is a projection or a claim of traction: these are counts and sums over
    synthetic demo data, and the payload says so.
    """
    repo, ws = ctx.repo, ctx.ws
    pools = repo.list_pools(ws)
    all_members = [m for p in pools for m in repo.list_memberships(ws, p.id)]
    committed = [m for m in all_members if m.counts_as_funded]

    baseline = sum(m.baseline_cents for m in committed)
    actual = sum(m.final_cost_cents for m in committed)
    activity = repo.list_activity(ws, limit=10_000)
    assignments = repo.list_host_assignments(ws)
    allocations = [a for p in pools for a in repo.list_allocations(ws, p.id)]
    picked_up = [a for a in allocations if a.state.value == "picked_up"]

    autonomous_kinds = {
        "pool_created", "final_offer_issued", "pool_locked", "pool_recovered",
        "recovery_pending", "host_offered", "host_accepted", "quote_changed",
        "purchase_executed", "payment_authorized", "payment_captured",
    }
    econ_totals = [p.final_economics for p in pools if p.final_economics]

    return {
        "members_participating": len({m.household_id for m in committed}),
        "pools_total": len(pools),
        "pools_locked_or_beyond": sum(
            1
            for p in pools
            if p.status
            in {
                PoolStatus.LOCKED, PoolStatus.PURCHASE_READY, PoolStatus.PURCHASED,
                PoolStatus.DISTRIBUTING, PoolStatus.COMPLETED,
            }
        ),
        "pools_recovered": sum(1 for e in activity if e.kind == "pool_recovered"),
        "estimated_retail_spend_cents": baseline,
        "pool_spend_cents": actual,
        "collective_savings_cents": baseline - actual,
        "average_buyer_savings_cents": ((baseline - actual) // len(committed)) if committed else 0,
        "merchandise_cents": sum(e.get("merchandise_cents", 0) for e in econ_totals),
        "host_compensation_cents": sum(e.get("host_compensation_cents", 0) for e in econ_totals),
        "payment_processing_cents": sum(e.get("payment_processing_cents", 0) for e in econ_totals),
        "platform_fee_cents": sum(e.get("platform_fee_cents", 0) for e in econ_totals),
        "host_jobs": len(assignments),
        "host_earnings_cents": sum(a.reward_total_cents for a in assignments),
        "host_handled_orders": sum(a.handled_orders for a in assignments),
        "pickups_completed": len(picked_up),
        "pickups_expected": len(allocations),
        "no_shows": sum(1 for a in allocations if a.state.value == "no_show"),
        "coordination_actions_automated": sum(1 for e in activity if e.kind in autonomous_kinds),
        "human_decisions_requested": len(repo.list_decisions(ws)),
        "commitments_without_asking": sum(
            1 for m in committed if m.path == AutonomyPath.SMART_JOIN
        ),
        "is_demo_data": True,
    }
