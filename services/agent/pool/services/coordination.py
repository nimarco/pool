"""The deterministic coordination engine.

Everything the agent can *do* to the world goes through this module. The agent decides
which of these operations to invoke and in what order; this module decides what is
true, what is legal, and what a human must approve (AGENTS.md §5).

Every consequential operation is idempotent by explicit key, because agent systems
retry and a retried ``create_pool`` must not produce two pools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..adapters.repository import Repository
from ..adapters.routing import Coordinate, RoutingError, RoutingService
from ..domain.allocation import PoolPricing, Request, price_pool
from ..domain.matching import MatchResult, find_candidates
from ..domain.models import (
    ActivityEvent,
    AutonomyPath,
    DecisionKind,
    DecisionRequest,
    DecisionState,
    Household,
    Membership,
    MembershipState,
    Offer,
    OfferKind,
    PickupSite,
    Pool,
    PoolStatus,
    iso,
    new_id,
    utcnow,
)
from ..domain.money import format_cents
from ..domain.policy import PolicyVerdict, evaluate_smart_join
from ..domain.state import assert_transition

# Pools form tight and repair wide: the initial search stays close to the pickup site
# so travel burden is low, and only a recovery widens the net. Both are still bounded
# by each household's own max-travel policy.
FORMATION_RADIUS_KM = 2.0
RECOVERY_RADIUS_KM = 8.0


class CoordinationError(RuntimeError):
    """A coordination operation could not be completed."""


# --------------------------------------------------------------------------- results


@dataclass
class CandidateAssessment:
    household_id: str
    household_name: str
    need_id: str
    units: int
    is_exact_product: bool
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
            "cost_cents": self.cost_cents,
            "cost_display": format_cents(self.cost_cents),
            "baseline_cents": self.baseline_cents,
            "savings_cents": self.savings_cents,
            "savings_bps": self.savings_bps,
            "travel_minutes": self.travel_minutes,
            "distance_km": round(self.distance_km, 2),
            "auto_join_eligible": self.verdict.eligible_for_auto_join,
            "blocking_rule": (self.verdict.failed_rules[0] if self.verdict.failed_rules else None),
            "blocking_reason": self.verdict.blocking_reason,
        }


@dataclass
class OpportunityAssessment:
    """A fully-costed candidate opportunity. Not yet a pool; nobody has been contacted."""

    product_id: str
    product_name: str
    pickup_site_id: str
    pickup_site_name: str
    pickup_is_public: bool
    pickup_by: str
    bulk_offer_id: str | None
    retail_offer_id: str | None
    viable: bool
    reason: str
    pricing: PoolPricing | None
    candidates: list[CandidateAssessment] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    routing_provider: str = ""
    avg_travel_minutes: int = 0
    max_travel_minutes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "pickup_site_id": self.pickup_site_id,
            "pickup_site_name": self.pickup_site_name,
            "pickup_is_public": self.pickup_is_public,
            "pickup_by": self.pickup_by,
            "bulk_offer_id": self.bulk_offer_id,
            "retail_offer_id": self.retail_offer_id,
            "viable": self.viable,
            "reason": self.reason,
            "routing_provider": self.routing_provider,
            "avg_travel_minutes": self.avg_travel_minutes,
            "max_travel_minutes": self.max_travel_minutes,
            "pricing": self.pricing.to_dict() if self.pricing else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected_count": len(self.rejected),
            "auto_join_count": sum(1 for c in self.candidates if c.verdict.eligible_for_auto_join),
            "approval_required_count": sum(
                1 for c in self.candidates if not c.verdict.eligible_for_auto_join
            ),
        }


@dataclass
class RecoveryResult:
    pool_id: str
    recovered: bool
    reason: str
    shortfall_units: int
    added_household_ids: list[str] = field(default_factory=list)
    invited_household_ids: list[str] = field(default_factory=list)
    repriced_household_ids: list[str] = field(default_factory=list)
    approval_required_household_ids: list[str] = field(default_factory=list)
    new_status: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "recovered": self.recovered,
            "reason": self.reason,
            "shortfall_units": self.shortfall_units,
            "added_household_ids": self.added_household_ids,
            "invited_household_ids": self.invited_household_ids,
            "repriced_household_ids": self.repriced_household_ids,
            "approval_required_household_ids": self.approval_required_household_ids,
            "new_status": self.new_status,
        }


# --------------------------------------------------------------------------- helpers


def _log(repo: Repository, ws: str, event: ActivityEvent) -> None:
    repo.append_activity(ws, event)


def _offers_for(repo: Repository, ws: str, product_id: str) -> tuple[Offer | None, list[Offer]]:
    retail: Offer | None = None
    bulk: list[Offer] = []
    today = date.today()
    for o in repo.list_offers(ws):
        if o.product_id != product_id:
            continue
        if o.valid_until and o.valid_until < today:
            continue
        if o.kind == OfferKind.RETAIL:
            retail = o
        else:
            bulk.append(o)
    return retail, bulk


def _travel_minutes_map(
    routing: RoutingService,
    households: list[Household],
    site: PickupSite,
) -> tuple[dict[str, int], dict[str, float], str]:
    """One bounded route-matrix call for the whole candidate set."""
    if not households:
        return {}, {}, routing.name
    origins = [Coordinate(h.lat, h.lon) for h in households]
    matrix = routing.travel_matrix(origins, [Coordinate(site.lat, site.lon)])
    minutes = {h.id: matrix[i][0].duration_minutes for i, h in enumerate(households)}
    km = {h.id: matrix[i][0].distance_km for i, h in enumerate(households)}
    return minutes, km, routing.name


# --------------------------------------------------------------------------- assess


def evaluate_opportunity(
    *,
    repo: Repository,
    ws: str,
    routing: RoutingService,
    product_id: str,
    pickup_site_id: str,
    pickup_in_days: int = 14,
    radius_km: float = FORMATION_RADIUS_KM,
    exclude_household_ids: frozenset[str] = frozenset(),
) -> OpportunityAssessment:
    """Evaluate whether a worthwhile bulk opportunity exists for one product+site.

    This is a read-only assessment. Nothing is created, nobody is contacted, and no
    money is committed — so the agent may call it freely (AGENTS.md §5).
    """
    product = repo.get_product(ws, product_id)
    site = repo.get_site(ws, pickup_site_id)
    if product is None:
        raise CoordinationError(f"unknown product: {product_id}")
    if site is None:
        raise CoordinationError(f"unknown pickup site: {pickup_site_id}")

    pickup_by = date.today() + timedelta(days=pickup_in_days)
    empty = OpportunityAssessment(
        product_id=product_id,
        product_name=product.name,
        pickup_site_id=site.id,
        pickup_site_name=site.name,
        pickup_is_public=site.is_public,
        pickup_by=pickup_by.isoformat(),
        bulk_offer_id=None,
        retail_offer_id=None,
        viable=False,
        reason="",
        pricing=None,
        routing_provider=routing.name,
    )

    retail, bulk_offers = _offers_for(repo, ws, product_id)
    if retail is None:
        empty.reason = "no retail baseline offer available for this product"
        return empty
    empty.retail_offer_id = retail.id
    if not bulk_offers:
        empty.reason = "no bulk offer available for this product"
        return empty

    households = {h.id: h for h in repo.list_households(ws)}
    products = {p.id: p for p in repo.list_products(ws)}

    match: MatchResult = find_candidates(
        target_product=product,
        needs=repo.list_needs(ws),
        households=households,
        products=products,
        pickup_lat=site.lat,
        pickup_lon=site.lon,
        pickup_by=pickup_by,
        max_radius_km=radius_km,
        exclude_household_ids=exclude_household_ids,
    )
    empty.rejected = [
        {"need_id": r.need_id, "household_id": r.household_id, "reason": r.reason}
        for r in match.rejections
    ]

    if not match.candidates:
        empty.reason = "no compatible declared demand within range"
        return empty

    requests = [
        Request(c.household.id, c.need.id, c.need.quantity) for c in match.candidates
    ]

    # Compare every bulk tier and keep the one that maximises group savings while
    # actually clearing its own minimum. This is a genuine comparison the agent asks
    # for — the arithmetic is ours, the decision to investigate is the agent's.
    best: tuple[Offer, PoolPricing] | None = None
    for offer in bulk_offers:
        pricing = price_pool(offer, retail, requests)
        if not pricing.threshold_met:
            continue
        if best is None or pricing.total_savings_cents > best[1].total_savings_cents:
            best = (offer, pricing)

    if best is None:
        shortfalls = [
            f"{o.id} needs {o.min_units} units, have {match.total_units}" for o in bulk_offers
        ]
        empty.reason = "aggregate demand below every bulk minimum: " + "; ".join(shortfalls)
        return empty

    bulk_offer, pricing = best
    if pricing.total_savings_cents <= 0:
        empty.bulk_offer_id = bulk_offer.id
        empty.pricing = pricing
        empty.reason = "bulk pricing does not beat the retail baseline"
        return empty

    # Routing: one matrix call for all candidates.
    candidate_households = [c.household for c in match.candidates]
    try:
        minutes, kms, provider = _travel_minutes_map(routing, candidate_households, site)
    except RoutingError as exc:
        empty.bulk_offer_id = bulk_offer.id
        empty.pricing = pricing
        empty.reason = f"routing unavailable: {exc}"
        return empty

    assessments: list[CandidateAssessment] = []
    for c in match.candidates:
        line = pricing.line_for(c.household.id)
        if line is None:
            continue
        travel = minutes.get(c.household.id, 0)
        verdict = evaluate_smart_join(
            household_id=c.household.id,
            policy=c.household.autonomy,
            need=c.need,
            cost_cents=line.cost_cents,
            savings_bps_value=line.savings_bps,
            travel_minutes=travel,
            is_exact_product=c.is_exact_product,
            pickup_is_public=site.is_public,
        )
        assessments.append(
            CandidateAssessment(
                household_id=c.household.id,
                household_name=c.household.display_name,
                need_id=c.need.id,
                units=c.need.quantity,
                is_exact_product=c.is_exact_product,
                cost_cents=line.cost_cents,
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
        product_id=product_id,
        product_name=product.name,
        pickup_site_id=site.id,
        pickup_site_name=site.name,
        pickup_is_public=site.is_public,
        pickup_by=pickup_by.isoformat(),
        bulk_offer_id=bulk_offer.id,
        retail_offer_id=retail.id,
        viable=True,
        reason="viable bulk opportunity",
        pricing=pricing,
        candidates=assessments,
        rejected=empty.rejected,
        routing_provider=provider,
        avg_travel_minutes=round(sum(travel_values) / len(travel_values)),
        max_travel_minutes=max(travel_values),
    )


# --------------------------------------------------------------------------- create


def create_pool(
    *,
    repo: Repository,
    ws: str,
    assessment: OpportunityAssessment,
    run_id: str,
    idempotency_key: str,
) -> tuple[Pool, bool]:
    """Materialise an assessment into a pool. Returns ``(pool, created)``.

    Idempotent on ``idempotency_key``: a retried call returns the existing pool rather
    than creating a duplicate (AGENTS.md §7, brief §14).
    """
    if not assessment.viable or assessment.pricing is None or assessment.bulk_offer_id is None:
        raise CoordinationError(f"cannot create a pool from a non-viable assessment: {assessment.reason}")

    for existing in repo.list_pools(ws):
        if existing.idempotency_key == idempotency_key:
            return existing, False

    pool = Pool(
        id=new_id("pool"),
        product_id=assessment.product_id,
        offer_id=assessment.bulk_offer_id,
        pickup_site_id=assessment.pickup_site_id,
        status=PoolStatus.CANDIDATE,
        threshold_units=assessment.pricing.threshold_units,
        deadline=date.fromisoformat(assessment.pickup_by),
        created_by_run=run_id,
        idempotency_key=idempotency_key,
    )
    repo.put_pool(ws, pool)

    auto_joined = 0
    invited = 0
    for c in assessment.candidates:
        if c.verdict.eligible_for_auto_join:
            state, path = MembershipState.COMMITTED, AutonomyPath.SMART_JOIN
            auto_joined += 1
        else:
            state, path = MembershipState.INVITED, AutonomyPath.PENDING_APPROVAL
            invited += 1
        repo.put_membership(
            ws,
            Membership(
                pool_id=pool.id,
                household_id=c.household_id,
                need_id=c.need_id,
                requested_units=c.units,
                allocated_units=c.units,
                cost_cents=c.cost_cents,
                baseline_cents=c.baseline_cents,
                savings_cents=c.savings_cents,
                savings_bps=c.savings_bps,
                travel_minutes=c.travel_minutes,
                state=state,
                path=path,
            ),
        )
        if state == MembershipState.INVITED:
            _create_decision(
                repo, ws, pool, c, DecisionKind.JOIN_POOL, assessment
            )

    _log(
        repo,
        ws,
        ActivityEvent(
            id=new_id("evt"),
            kind="pool_created",
            summary=(
                f"Found {len(assessment.candidates)} households wanting "
                f"{assessment.product_name.lower()} and formed a buying pool"
            ),
            facts={
                "product": assessment.product_name,
                "households": len(assessment.candidates),
                "total_units": assessment.pricing.total_units,
                "threshold_units": assessment.pricing.threshold_units,
                "savings_bps": assessment.pricing.total_savings_bps,
                "total_savings_cents": assessment.pricing.total_savings_cents,
                "pickup_site": assessment.pickup_site_name,
                "avg_travel_minutes": assessment.avg_travel_minutes,
                "auto_joined": auto_joined,
                "approval_requested": invited,
                "routing_provider": assessment.routing_provider,
            },
            pool_id=pool.id,
            run_id=run_id,
        ),
    )

    # A pool with outstanding invitations is "inviting"; one where every member was
    # pre-authorised may already clear the threshold.
    new_status = PoolStatus.INVITING if invited else PoolStatus.CANDIDATE
    pool.status = assert_transition(pool.status, new_status)
    repo.put_pool(ws, pool)
    refresh_threshold(repo=repo, ws=ws, pool_id=pool.id, run_id=run_id)
    return repo.get_pool(ws, pool.id) or pool, True


def _create_decision(
    repo: Repository,
    ws: str,
    pool: Pool,
    c: CandidateAssessment,
    kind: DecisionKind,
    assessment: OpportunityAssessment,
) -> DecisionRequest:
    decision = DecisionRequest(
        id=new_id("dec"),
        household_id=c.household_id,
        pool_id=pool.id,
        kind=kind,
        state=DecisionState.PENDING,
        facts={
            "product": assessment.product_name,
            "units": c.units,
            "cost_cents": c.cost_cents,
            "cost_display": format_cents(c.cost_cents),
            "baseline_cents": c.baseline_cents,
            "savings_cents": c.savings_cents,
            "savings_bps": c.savings_bps,
            "travel_minutes": c.travel_minutes,
            "pickup_site": assessment.pickup_site_name,
            "pickup_by": assessment.pickup_by,
            "is_exact_product": c.is_exact_product,
            "blocking_rule": (c.verdict.failed_rules[0] if c.verdict.failed_rules else None),
            "policy_checks": [chk.to_dict() for chk in c.verdict.checks],
        },
        expires_at=iso(utcnow() + timedelta(days=3)),
    )
    repo.put_decision(ws, decision)
    return decision


# --------------------------------------------------------------------------- threshold


def committed_units(repo: Repository, ws: str, pool_id: str) -> int:
    return sum(
        m.allocated_units
        for m in repo.list_memberships(ws, pool_id)
        if m.state == MembershipState.COMMITTED
    )


def refresh_threshold(*, repo: Repository, ws: str, pool_id: str, run_id: str = "") -> PoolStatus:
    """Recompute whether a pool clears its supplier minimum and move it if so.

    Purely deterministic and safe to call repeatedly — the state machine rejects any
    move that is not legal from the current state.
    """
    pool = repo.get_pool(ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")

    units = committed_units(repo, ws, pool_id)
    met = units >= pool.threshold_units

    if met and pool.status in {PoolStatus.CANDIDATE, PoolStatus.INVITING, PoolStatus.RECOVERING}:
        pool.status = assert_transition(pool.status, PoolStatus.THRESHOLD_MET)
        repo.put_pool(ws, pool)
        _log(
            repo,
            ws,
            ActivityEvent(
                id=new_id("evt"),
                kind="threshold_met",
                summary=f"Bulk threshold satisfied — {units}/{pool.threshold_units} units committed",
                facts={"committed_units": units, "threshold_units": pool.threshold_units},
                pool_id=pool.id,
                run_id=run_id or None,
            ),
        )
    elif not met and pool.status == PoolStatus.THRESHOLD_MET:
        pool.status = assert_transition(pool.status, PoolStatus.RECOVERING)
        repo.put_pool(ws, pool)

    return pool.status


# --------------------------------------------------------------------------- HITL


def respond_to_decision(
    *, repo: Repository, ws: str, decision_id: str, approve: bool
) -> DecisionRequest:
    """Record a human's answer. Idempotent — re-answering an answered decision is a no-op."""
    decision = repo.get_decision(ws, decision_id)
    if decision is None:
        raise CoordinationError(f"unknown decision: {decision_id}")
    if decision.state != DecisionState.PENDING:
        return decision  # already answered; do not double-count

    decision.state = DecisionState.APPROVED if approve else DecisionState.REJECTED
    repo.put_decision(ws, decision)

    membership = repo.get_membership(ws, decision.pool_id, decision.household_id)
    if membership is not None:
        membership.state = MembershipState.COMMITTED if approve else MembershipState.DECLINED
        membership.path = AutonomyPath.HUMAN_APPROVED if approve else membership.path
        repo.put_membership(ws, membership)

    _log(
        repo,
        ws,
        ActivityEvent(
            id=new_id("evt"),
            kind="decision_answered",
            summary=("Household approved joining the pool" if approve else "Household declined"),
            facts={"decision_id": decision.id, "approved": approve},
            pool_id=decision.pool_id,
            household_id=decision.household_id,
        ),
    )
    refresh_threshold(repo=repo, ws=ws, pool_id=decision.pool_id)
    return decision


# --------------------------------------------------------------------------- dropout


def withdraw_household(
    *, repo: Repository, ws: str, pool_id: str, household_id: str
) -> dict[str, Any]:
    """Record a dropout. Idempotent — withdrawing twice does not double-subtract."""
    membership = repo.get_membership(ws, pool_id, household_id)
    if membership is None:
        raise CoordinationError(f"{household_id} is not a member of {pool_id}")
    if membership.state == MembershipState.WITHDRAWN:
        return {"already_withdrawn": True, "pool_id": pool_id, "household_id": household_id}

    released = membership.allocated_units
    membership.state = MembershipState.WITHDRAWN
    repo.put_membership(ws, membership)

    pool = repo.get_pool(ws, pool_id)
    assert pool is not None
    _log(
        repo,
        ws,
        ActivityEvent(
            id=new_id("evt"),
            kind="participant_withdrew",
            summary=f"A participant withdrew, releasing {released} units",
            facts={"released_units": released, "threshold_units": pool.threshold_units},
            pool_id=pool_id,
            household_id=household_id,
        ),
    )

    status = refresh_threshold(repo=repo, ws=ws, pool_id=pool_id)
    remaining = committed_units(repo, ws, pool_id)
    return {
        "already_withdrawn": False,
        "pool_id": pool_id,
        "household_id": household_id,
        "released_units": released,
        "committed_units": remaining,
        "threshold_units": pool.threshold_units,
        "below_threshold": remaining < pool.threshold_units,
        "pool_status": status.value,
    }


# --------------------------------------------------------------------------- recovery


def recover_pool(
    *,
    repo: Repository,
    ws: str,
    routing: RoutingService,
    pool_id: str,
    run_id: str,
    radius_km: float = RECOVERY_RADIUS_KM,
) -> RecoveryResult:
    """Attempt to restore a pool that has fallen below its threshold.

    The quietest sufficient repair wins: Pool looks for compatible households who are
    not already in the pool, adds the ones whose own Smart Join policy pre-authorises
    it, and only asks a human when it must. Existing members are *not* disturbed unless
    their own share materially changed (AGENTS.md §5).
    """
    pool = repo.get_pool(ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")

    memberships = repo.list_memberships(ws, pool_id)
    active = [m for m in memberships if m.state == MembershipState.COMMITTED]
    current_units = sum(m.allocated_units for m in active)
    shortfall = pool.threshold_units - current_units

    if shortfall <= 0:
        return RecoveryResult(
            pool_id=pool_id,
            recovered=True,
            reason="pool already meets its threshold",
            shortfall_units=0,
            new_status=refresh_threshold(repo=repo, ws=ws, pool_id=pool_id, run_id=run_id).value,
        )

    product = repo.get_product(ws, pool.product_id)
    site = repo.get_site(ws, pool.pickup_site_id)
    retail, _ = _offers_for(repo, ws, pool.product_id)
    bulk = repo.get_offer(ws, pool.offer_id)
    if product is None or site is None or retail is None or bulk is None:
        raise CoordinationError("pool references missing product, site, or offer")

    involved = {m.household_id for m in memberships}
    households = {h.id: h for h in repo.list_households(ws)}
    products = {p.id: p for p in repo.list_products(ws)}

    match = find_candidates(
        target_product=product,
        needs=repo.list_needs(ws),
        households=households,
        products=products,
        pickup_lat=site.lat,
        pickup_lon=site.lon,
        pickup_by=pool.deadline,
        max_radius_km=radius_km,
        exclude_household_ids=frozenset(involved),
    )

    if not match.candidates:
        _log(
            repo, ws,
            ActivityEvent(
                id=new_id("evt"), kind="recovery_failed",
                summary="No compatible replacement demand found in the neighbourhood",
                facts={"shortfall_units": shortfall}, pool_id=pool_id, run_id=run_id,
            ),
        )
        return RecoveryResult(
            pool_id=pool_id, recovered=False,
            reason="no compatible replacement demand available",
            shortfall_units=shortfall,
            new_status=pool.status.value,
        )

    # Prefer the smallest set that covers the shortfall: largest contributors first
    # means fewer people disturbed. Ties break on distance for a lower travel burden.
    ordered = sorted(
        match.candidates, key=lambda c: (-c.need.quantity, c.distance_km, c.need.id)
    )
    chosen = []
    covered = 0
    for c in ordered:
        if covered >= shortfall:
            break
        chosen.append(c)
        covered += c.need.quantity

    if covered < shortfall:
        # Everything available still doesn't reach the threshold.
        chosen = ordered

    # Re-price the pool as it *would* be with the replacements included.
    requests = [Request(m.household_id, m.need_id, m.allocated_units) for m in active]
    requests += [Request(c.household.id, c.need.id, c.need.quantity) for c in chosen]
    pricing = price_pool(bulk, retail, requests)

    try:
        minutes, kms, _ = _travel_minutes_map(routing, [c.household for c in chosen], site)
    except RoutingError as exc:
        return RecoveryResult(
            pool_id=pool_id, recovered=False,
            reason=f"routing unavailable during recovery: {exc}",
            shortfall_units=shortfall, new_status=pool.status.value,
        )

    added: list[str] = []
    invited: list[str] = []
    for c in chosen:
        line = pricing.line_for(c.household.id)
        if line is None:
            continue
        travel = minutes.get(c.household.id, 0)
        verdict = evaluate_smart_join(
            household_id=c.household.id,
            policy=c.household.autonomy,
            need=c.need,
            cost_cents=line.cost_cents,
            savings_bps_value=line.savings_bps,
            travel_minutes=travel,
            is_exact_product=c.is_exact_product,
            pickup_is_public=site.is_public,
        )
        state = MembershipState.COMMITTED if verdict.eligible_for_auto_join else MembershipState.INVITED
        path = AutonomyPath.SMART_JOIN if verdict.eligible_for_auto_join else AutonomyPath.PENDING_APPROVAL
        repo.put_membership(
            ws,
            Membership(
                pool_id=pool_id, household_id=c.household.id, need_id=c.need.id,
                requested_units=c.need.quantity, allocated_units=c.need.quantity,
                cost_cents=line.cost_cents, baseline_cents=line.baseline_cents,
                savings_cents=line.savings_cents, savings_bps=line.savings_bps,
                travel_minutes=travel, state=state, path=path,
            ),
        )
        if verdict.eligible_for_auto_join:
            added.append(c.household.id)
        else:
            invited.append(c.household.id)
            repo.put_decision(
                ws,
                DecisionRequest(
                    id=new_id("dec"), household_id=c.household.id, pool_id=pool_id,
                    kind=DecisionKind.JOIN_POOL, state=DecisionState.PENDING,
                    facts={
                        "product": product.name, "units": c.need.quantity,
                        "cost_cents": line.cost_cents, "cost_display": format_cents(line.cost_cents),
                        "savings_bps": line.savings_bps, "travel_minutes": travel,
                        "pickup_site": site.name, "pickup_by": pool.deadline.isoformat(),
                        "context": "replacement_for_dropout",
                        "policy_checks": [chk.to_dict() for chk in verdict.checks],
                    },
                    expires_at=iso(utcnow() + timedelta(days=2)),
                ),
            )

    # Existing members' shares move when the group changes. Silently raising someone's
    # cost past their own cap would be exactly the "materially worse terms" case that
    # requires approval, so those members are flagged rather than quietly updated.
    repriced: list[str] = []
    needs_approval: list[str] = []
    for m in active:
        line = pricing.line_for(m.household_id)
        if line is None or line.cost_cents == m.cost_cents:
            continue
        household = households[m.household_id]
        need = repo.get_need(ws, m.need_id)
        if need is None:
            continue
        verdict = evaluate_smart_join(
            household_id=m.household_id, policy=household.autonomy, need=need,
            cost_cents=line.cost_cents, savings_bps_value=line.savings_bps,
            travel_minutes=m.travel_minutes, is_exact_product=True,
            pickup_is_public=site.is_public,
        )
        worse = line.cost_cents > m.cost_cents
        if worse and not verdict.eligible_for_auto_join:
            needs_approval.append(m.household_id)
            continue  # leave the commitment untouched pending a human answer
        m.cost_cents = line.cost_cents
        m.baseline_cents = line.baseline_cents
        m.savings_cents = line.savings_cents
        m.savings_bps = line.savings_bps
        repo.put_membership(ws, m)
        repriced.append(m.household_id)

    status = refresh_threshold(repo=repo, ws=ws, pool_id=pool_id, run_id=run_id)
    recovered = status == PoolStatus.THRESHOLD_MET

    if recovered:
        _log(
            repo, ws,
            ActivityEvent(
                id=new_id("evt"), kind="pool_recovered",
                summary=(
                    "Pool recovered automatically — a participant withdrew and Pool matched "
                    "another compatible household, preserving the group discount"
                ),
                facts={
                    "shortfall_units": shortfall,
                    "replacements_added": len(added),
                    "replacements_invited": len(invited),
                    "existing_members_undisturbed": len(active) - len(needs_approval),
                    "savings_bps": pricing.total_savings_bps,
                },
                pool_id=pool_id, run_id=run_id,
            ),
        )
    else:
        _log(
            repo, ws,
            ActivityEvent(
                id=new_id("evt"), kind="recovery_pending",
                summary=f"Recovery under way — {len(invited)} household(s) asked to fill the gap",
                facts={"shortfall_units": shortfall, "invited": len(invited)},
                pool_id=pool_id, run_id=run_id,
            ),
        )

    return RecoveryResult(
        pool_id=pool_id,
        recovered=recovered,
        reason="threshold restored" if recovered else "awaiting replacement approval",
        shortfall_units=shortfall,
        added_household_ids=added,
        invited_household_ids=invited,
        repriced_household_ids=repriced,
        approval_required_household_ids=needs_approval,
        new_status=status.value,
    )


# --------------------------------------------------------------------------- metrics


def impact_metrics(repo: Repository, ws: str) -> dict[str, Any]:
    """Compute impact from stored state. Every figure traces to a record (brief §33)."""
    pools = repo.list_pools(ws)
    all_memberships = [m for p in pools for m in repo.list_memberships(ws, p.id)]
    committed = [m for m in all_memberships if m.state == MembershipState.COMMITTED]

    baseline = sum(m.baseline_cents for m in committed)
    actual = sum(m.cost_cents for m in committed)
    savings = baseline - actual

    decisions = repo.list_decisions(ws)
    activity = repo.list_activity(ws, limit=10_000)
    autonomous_events = [
        e for e in activity
        if e.kind in {"pool_created", "threshold_met", "pool_recovered", "recovery_pending",
                      "opportunity_evaluated", "participant_withdrew"}
    ]
    travel = [m.travel_minutes for m in committed] or [0]

    return {
        "households_participating": len({m.household_id for m in committed}),
        "pools_total": len(pools),
        "pools_at_or_past_threshold": sum(
            1 for p in pools
            if p.status in {PoolStatus.THRESHOLD_MET, PoolStatus.CONFIRMED, PoolStatus.COMPLETED}
        ),
        "pools_recovered": sum(1 for e in activity if e.kind == "pool_recovered"),
        "estimated_retail_spend_cents": baseline,
        "pool_spend_cents": actual,
        "collective_savings_cents": savings,
        "average_household_savings_cents": (savings // len(committed)) if committed else 0,
        "coordination_actions_automated": len(autonomous_events),
        "human_decisions_requested": len(decisions),
        "commitments_without_asking": sum(1 for m in committed if m.path == AutonomyPath.SMART_JOIN),
        "average_pickup_travel_minutes": round(sum(travel) / len(travel)),
        "is_demo_data": True,
    }
