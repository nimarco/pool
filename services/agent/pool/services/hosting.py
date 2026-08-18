"""Host recruiting, ranking, and assignment (§27–§35).

The fulfilment side is a real economic side, not a checkbox. A pool that nobody will
collect and distribute is not a pool, and a host who is paid the same for five orders
as for thirty will stop showing up.

Three rules are enforced here:

* **Candidates come from two places** (§27): people who previously opted in as
  standing hosts, and ordinary pool members who clicked "Offer to host" on this
  specific pool. A buyer does not need to have registered in advance.
* **Offering to host is not claiming the job** (§28). Several people can offer at once;
  the deterministic evaluator ranks them; the top eligible candidate receives the
  offer. If they decline or their window expires, the next one is offered. There is no
  first-come-first-served path.
* **The host is selected before buyers authorise** (§35), because host compensation is
  part of the buyer's price, and buyers are never charged more than they agreed to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from ..domain.economics import allocate_packages, compute_host_reward
from ..domain.hosting import (
    HostEvaluation,
    HostJob,
    estimate_weight_kg,
    evaluate_host,
    rank_hosts,
    ranking_key,
)
from ..domain.models import (
    DecisionKind,
    DecisionRequest,
    DecisionState,
    FulfillerRole,
    HostAssignment,
    HostCandidate,
    HostCandidateSource,
    HostCandidateState,
    HostProfile,
    Pool,
    PoolStatus,
    iso,
    new_id,
    parse_iso,
)
from ..domain.money import format_cents
from ..domain.state import assert_transition
from ..domain.timing import next_pool_day
from .context import CoordinationError, PoolContext
from .coordination import provisional_units, supplier_distance_km

#: How long an offered host has to accept before the offer moves to the next candidate.
HOST_OFFER_WINDOW_HOURS = 12


@dataclass
class HostRecruitingResult:
    pool_id: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    eligible_count: int = 0
    offered_household_id: str = ""
    status: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "candidates": self.candidates,
            "eligible_count": self.eligible_count,
            "offered_household_id": self.offered_household_id,
            "status": self.status,
            "reason": self.reason,
        }


def open_host_recruiting(*, ctx: PoolContext, pool_id: str) -> bool:
    """Move a candidate pool into host recruiting once demand clears the MOQ.

    Returns True when the pool is now recruiting. A pool below its minimum stays in
    ``FORMING`` — there is no point recruiting labour for an order that cannot happen.
    """
    pool = _require_pool(ctx, pool_id)
    if pool.status == PoolStatus.HOST_RECRUITING:
        return True
    if pool.status != PoolStatus.FORMING:
        return False
    if provisional_units(ctx, pool_id) < pool.threshold_units:
        return False
    pool.status = assert_transition(pool.status, PoolStatus.HOST_RECRUITING)
    ctx.repo.put_pool(ctx.ws, pool)
    ctx.log(
        "host_recruiting_opened",
        "Provisional demand clears the supplier minimum — recruiting a fulfiller",
        {
            "provisional_units": provisional_units(ctx, pool_id),
            "threshold_units": pool.threshold_units,
            "host_acceptance_deadline": pool.timing.host_acceptance_deadline,
        },
        pool_id=pool_id,
    )
    return True


def volunteer_to_host(
    *, ctx: PoolContext, pool_id: str, household_id: str, profile: HostProfile | None = None
) -> HostCandidate:
    """A pool member offers to host this specific pool (§27).

    This adds them to the candidate set; it does **not** give them the job (§28). Only
    the missing pool-specific information needs collecting: someone who already has a
    standing profile keeps it.
    """
    pool = _require_pool(ctx, pool_id)
    existing_profile = ctx.repo.get_host_profile(ctx.ws, pool.community_id, household_id)
    if profile is not None:
        profile.household_id = household_id
        profile.community_id = pool.community_id
        profile.standing = existing_profile.standing if existing_profile else False
        ctx.repo.put_host_profile(ctx.ws, profile)
    elif existing_profile is None:
        # An ad-hoc volunteer with no standing profile gets a minimal one so the
        # deterministic evaluator has something factual to check.
        ctx.repo.put_host_profile(
            ctx.ws,
            HostProfile(
                household_id=household_id,
                community_id=pool.community_id,
                standing=False,
            ),
        )

    membership = ctx.repo.get_membership(ctx.ws, pool_id, household_id)
    source = (
        HostCandidateSource.POOL_MEMBER_VOLUNTEER
        if membership is not None
        else HostCandidateSource.STANDING
    )
    candidate = ctx.repo.get_host_candidate(ctx.ws, pool_id, household_id) or HostCandidate(
        pool_id=pool_id,
        household_id=household_id,
        source=source,
        state=HostCandidateState.CANDIDATE,
    )
    if candidate.state in {HostCandidateState.DECLINED, HostCandidateState.EXPIRED}:
        candidate.state = HostCandidateState.CANDIDATE
    candidate.source = source
    ctx.repo.put_host_candidate(ctx.ws, candidate)
    ctx.log(
        "host_volunteered",
        "A pool member offered to host this pool",
        {"source": source.value},
        pool_id=pool_id,
        household_id=household_id,
    )
    return candidate


def evaluate_host_candidates(*, ctx: PoolContext, pool_id: str) -> HostRecruitingResult:
    """Evaluate and rank every host candidate for a pool.

    Read-only with respect to assignment: it records the evaluation on each candidate
    so the reasoning is inspectable, but it does not offer anyone the job.
    """
    pool = _require_pool(ctx, pool_id)
    community = ctx.community(pool.community_id)
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    if product is None or site is None or offer is None:
        raise CoordinationError("pool references a missing product, site, or offer")

    members = [
        m
        for m in ctx.repo.list_memberships(ctx.ws, pool_id)
        if m.counts_as_provisional
    ]
    units = sum(m.allocated_units for m in members)
    if not members:
        return HostRecruitingResult(pool_id, status=pool.status.value, reason="no members yet")

    packages = allocate_packages(offer, units)
    merchandise = packages.cases * offer.case_price_cents
    weight = estimate_weight_kg(units, product.unit_weight_grams)
    dist_day = (
        parse_iso(pool.timing.distribution_starts_at).date()
        if pool.timing.distribution_starts_at
        else next_pool_day(ctx.now.date(), community.schedule)
    )

    profiles = _candidate_profiles(ctx, pool)
    distances = {
        p.household_id: _supplier_distance_for(ctx, pool, offer, p.household_id)
        for p in profiles
    }
    job = HostJob(
        orders=len(members),
        units=units,
        weight_kg=weight,
        distribution_day=dist_day,
        supplier_distance_km=distances,
        buyer_travel_penalty={p.household_id: 0 for p in profiles},
    )

    evaluations: list[HostEvaluation] = []
    for profile in profiles:
        reward = compute_host_reward(
            config=community.host_reward,
            orders=job.orders,
            units=job.units,
            distance_km=distances[profile.household_id],
            weight_kg=weight,
            merchandise_cents=merchandise,
        )
        evaluation = evaluate_host(
            profile=profile,
            job=job,
            reward=reward,
            site=site,
            is_standing=profile.standing,
        )
        evaluations.append(evaluation)

        candidate = ctx.repo.get_host_candidate(
            ctx.ws, pool_id, profile.household_id
        ) or HostCandidate(
            pool_id=pool_id,
            household_id=profile.household_id,
            source=HostCandidateSource.STANDING if profile.standing
            else HostCandidateSource.POOL_MEMBER_VOLUNTEER,
            state=HostCandidateState.CANDIDATE,
        )
        # Re-evaluating updates eligibility, but never overwrites a settled answer: an
        # accepted, declined, or expired candidate keeps that state, and an outstanding
        # offer is not silently withdrawn because the numbers moved.
        if candidate.state in {HostCandidateState.CANDIDATE, HostCandidateState.INELIGIBLE}:
            candidate.state = (
                HostCandidateState.CANDIDATE if evaluation.eligible
                else HostCandidateState.INELIGIBLE
            )
        candidate.eligible = evaluation.eligible
        candidate.ineligible_reasons = evaluation.ineligible_reasons
        candidate.score = evaluation.score
        candidate.score_components = evaluation.components
        candidate.estimated_reward_cents = reward.total_cents
        candidate.supplier_distance_km = evaluation.supplier_distance_km
        ctx.repo.put_host_candidate(ctx.ws, candidate)

    ranked = rank_hosts(evaluations)
    return HostRecruitingResult(
        pool_id=pool_id,
        candidates=[e.to_dict() for e in ranked] + [
            e.to_dict() for e in evaluations if not e.eligible
        ],
        eligible_count=len(ranked),
        status=pool.status.value,
        reason="candidates evaluated",
    )


def offer_to_next_host(*, ctx: PoolContext, pool_id: str) -> HostRecruitingResult:
    """Offer the job to the best-ranked eligible candidate who has not yet answered.

    Exactly one offer is outstanding at a time. If an existing offer has expired it is
    marked expired first, so the pool always moves forward rather than stalling on a
    candidate who never replied (§34).
    """
    pool = _require_pool(ctx, pool_id)
    expire_stale_host_offers(ctx=ctx, pool_id=pool_id)

    result = evaluate_host_candidates(ctx=ctx, pool_id=pool_id)
    candidates = ctx.repo.list_host_candidates(ctx.ws, pool_id)

    outstanding = next((c for c in candidates if c.state == HostCandidateState.OFFERED), None)
    if outstanding is not None:
        result.offered_household_id = outstanding.household_id
        result.reason = "an offer is already outstanding"
        return result

    available = [
        c
        for c in candidates
        if c.eligible and c.state == HostCandidateState.CANDIDATE
    ]
    if not available:
        result.reason = "no eligible host candidate is available"
        _fail_if_host_deadline_passed(ctx, pool)
        result.status = _require_pool(ctx, pool_id).status.value
        return result

    # `min` with the canonical descending-score key, not `max` with an ad-hoc one:
    # this must select exactly the candidate `rank_hosts` puts first, or the ranking
    # the UI shows and the offer the pool actually makes can name different people.
    best = min(
        available,
        key=lambda c: ranking_key(household_id=c.household_id, score=c.score),
    )
    best.state = HostCandidateState.OFFERED
    best.offered_at = iso(ctx.now)
    best.expires_at = _offer_deadline(ctx, pool)
    ctx.repo.put_host_candidate(ctx.ws, best)

    ctx.repo.put_decision(
        ctx.ws,
        DecisionRequest(
            id=new_id("dec"),
            household_id=best.household_id,
            pool_id=pool_id,
            kind=DecisionKind.HOST_OFFER,
            state=DecisionState.PENDING,
            facts={
                "orders": sum(
                    1 for m in ctx.repo.list_memberships(ctx.ws, pool_id)
                    if m.counts_as_provisional
                ),
                "units": provisional_units(ctx, pool_id),
                "supplier_distance_km": round(best.supplier_distance_km, 1),
                "estimated_earnings_cents": best.estimated_reward_cents,
                "estimated_earnings_display": format_cents(best.estimated_reward_cents),
                "distribution_starts_at": pool.timing.distribution_starts_at,
                "distribution_ends_at": pool.timing.distribution_ends_at,
                "score_components": best.score_components,
            },
            expires_at=best.expires_at,
        ),
    )
    ctx.log(
        "host_offered",
        "Best-ranked eligible host was offered the fulfilment job",
        {
            "estimated_earnings_cents": best.estimated_reward_cents,
            "score": best.score,
            "score_components": best.score_components,
            "eligible_candidates": result.eligible_count,
            "expires_at": best.expires_at,
        },
        pool_id=pool_id,
        household_id=best.household_id,
    )
    result.offered_household_id = best.household_id
    result.reason = "offer issued to the best-ranked eligible candidate"
    return result


def respond_to_host_offer(
    *, ctx: PoolContext, pool_id: str, household_id: str, accept: bool
) -> dict[str, Any]:
    """Record a host's answer, and assign the job on acceptance.

    Declining is a normal outcome, not an error: the next-ranked candidate is offered.
    """
    pool = _require_pool(ctx, pool_id)
    candidate = ctx.repo.get_host_candidate(ctx.ws, pool_id, household_id)
    if candidate is None:
        raise CoordinationError(f"{household_id} is not a host candidate for {pool_id}")
    if candidate.state != HostCandidateState.OFFERED:
        return {
            "pool_id": pool_id,
            "household_id": household_id,
            "accepted": candidate.state == HostCandidateState.ACCEPTED,
            "state": candidate.state.value,
            "note": "this candidate does not hold the outstanding offer",
        }

    candidate.responded_at = iso(ctx.now)
    for d in ctx.repo.list_decisions(ctx.ws):
        if (
            d.pool_id == pool_id
            and d.household_id == household_id
            and d.kind == DecisionKind.HOST_OFFER
            and d.state == DecisionState.PENDING
        ):
            d.state = DecisionState.APPROVED if accept else DecisionState.REJECTED
            ctx.repo.put_decision(ctx.ws, d)

    if not accept:
        candidate.state = HostCandidateState.DECLINED
        ctx.repo.put_host_candidate(ctx.ws, candidate)
        ctx.log(
            "host_declined",
            "Host declined the job — offering the next-ranked candidate",
            {},
            pool_id=pool_id,
            household_id=household_id,
        )
        follow_up = offer_to_next_host(ctx=ctx, pool_id=pool_id)
        return {
            "pool_id": pool_id,
            "household_id": household_id,
            "accepted": False,
            "state": candidate.state.value,
            "next_offered_household_id": follow_up.offered_household_id,
        }

    candidate.state = HostCandidateState.ACCEPTED
    ctx.repo.put_host_candidate(ctx.ws, candidate)
    assignment = _assign(ctx, pool, household_id)
    ctx.log(
        "host_accepted",
        "A fulfiller accepted the job — the pool can now be priced exactly",
        {
            "reward_total_cents": assignment.reward_total_cents,
            "reward_breakdown": assignment.reward_breakdown,
            "handled_orders": assignment.handled_orders,
            "supplier_distance_km": round(assignment.supplier_distance_km, 1),
        },
        pool_id=pool_id,
        household_id=household_id,
    )
    return {
        "pool_id": pool_id,
        "household_id": household_id,
        "accepted": True,
        "state": candidate.state.value,
        "reward_total_cents": assignment.reward_total_cents,
        "pool_status": _require_pool(ctx, pool_id).status.value,
    }


def expire_stale_host_offers(*, ctx: PoolContext, pool_id: str) -> list[str]:
    """Expire any outstanding host offer past its deadline. Bounded, never cycling."""
    expired: list[str] = []
    for c in ctx.repo.list_host_candidates(ctx.ws, pool_id):
        if c.state != HostCandidateState.OFFERED or not c.expires_at:
            continue
        if ctx.now <= parse_iso(c.expires_at):
            continue
        c.state = HostCandidateState.EXPIRED
        ctx.repo.put_host_candidate(ctx.ws, c)
        expired.append(c.household_id)
        for d in ctx.repo.list_decisions(ctx.ws):
            if (
                d.pool_id == pool_id
                and d.household_id == c.household_id
                and d.kind == DecisionKind.HOST_OFFER
                and d.state == DecisionState.PENDING
            ):
                d.state = DecisionState.EXPIRED
                ctx.repo.put_decision(ctx.ws, d)
        ctx.log(
            "host_offer_expired",
            "A host offer expired without an answer",
            {},
            pool_id=pool_id,
            household_id=c.household_id,
        )
    return expired


# --------------------------------------------------------------------------- internals


def _candidate_profiles(ctx: PoolContext, pool: Pool) -> list[HostProfile]:
    """Standing hosts plus anyone who volunteered for this pool (§27)."""
    profiles: dict[str, HostProfile] = {}
    for p in ctx.repo.list_host_profiles(ctx.ws, pool.community_id):
        if p.standing and p.willing_to_host:
            profiles[p.household_id] = p
    for c in ctx.repo.list_host_candidates(ctx.ws, pool.id):
        if c.state in {HostCandidateState.DECLINED, HostCandidateState.EXPIRED}:
            profiles.pop(c.household_id, None)
            continue
        profile = ctx.repo.get_host_profile(ctx.ws, pool.community_id, c.household_id)
        if profile is not None:
            profiles[c.household_id] = profile
    # A verified member of this Community only — hosting is community-scoped.
    out = []
    for hid, profile in profiles.items():
        membership = ctx.repo.get_community_membership(ctx.ws, pool.community_id, hid)
        if membership is not None and membership.is_verified:
            out.append(profile)
    return sorted(out, key=lambda p: p.household_id)


def _supplier_distance_for(ctx: PoolContext, pool: Pool, offer, household_id: str) -> float:
    household = ctx.repo.get_household(ctx.ws, household_id)
    if household is None:
        return 999.0
    return supplier_distance_km(ctx, offer, household.lat, household.lon)


def _offer_deadline(ctx: PoolContext, pool: Pool) -> str:
    """The earlier of the pool's host deadline and a fixed response window."""
    window = iso(ctx.now + timedelta(hours=HOST_OFFER_WINDOW_HOURS))
    deadline = pool.timing.host_acceptance_deadline
    if deadline and parse_iso(deadline) < parse_iso(window):
        return deadline
    return window


def _fail_if_host_deadline_passed(ctx: PoolContext, pool: Pool) -> None:
    """No viable host by the deadline is an honest failure, not an endless cycle (§34)."""
    deadline = pool.timing.host_acceptance_deadline
    if not deadline or ctx.now <= parse_iso(deadline):
        return
    if pool.status in {PoolStatus.FORMING, PoolStatus.HOST_RECRUITING}:
        pool.status = assert_transition(pool.status, PoolStatus.FAILED)
        pool.failure_reason = "no viable host accepted before the deadline"
        ctx.repo.put_pool(ctx.ws, pool)
        ctx.log(
            "pool_failed",
            "No viable host accepted before the deadline — the pool did not form",
            {},
            pool_id=pool.id,
        )


def _assign(ctx: PoolContext, pool: Pool, household_id: str) -> HostAssignment:
    community = ctx.community(pool.community_id)
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    if product is None or offer is None:
        raise CoordinationError("pool references a missing product or offer")

    members = [
        m for m in ctx.repo.list_memberships(ctx.ws, pool.id) if m.counts_as_provisional
    ]
    units = sum(m.allocated_units for m in members)
    packages = allocate_packages(offer, units)
    weight = estimate_weight_kg(units, product.unit_weight_grams)
    distance = _supplier_distance_for(ctx, pool, offer, household_id)
    reward = compute_host_reward(
        config=community.host_reward,
        orders=len(members),
        units=units,
        distance_km=distance,
        weight_kg=weight,
        merchandise_cents=packages.cases * offer.case_price_cents,
    )
    assignment = HostAssignment(
        pool_id=pool.id,
        household_id=household_id,
        # v1 uses one fulfiller for both legs; runner and host stay separable (§39).
        role=FulfillerRole.FULFILLER,
        pickup_site_id=pool.pickup_site_id,
        supplier_distance_km=distance,
        handled_orders=len(members),
        handled_units=units,
        estimated_weight_kg=weight,
        reward_breakdown=reward.breakdown(),
        reward_total_cents=reward.total_cents,
        reward_earned_cents=reward.earned_cents,
        reward_contingent_cents=reward.contingent_cents,
        accepted_at=iso(ctx.now),
    )
    ctx.repo.put_host_assignment(ctx.ws, assignment)
    pool.host_household_id = household_id
    pool.status = assert_transition(pool.status, PoolStatus.HOST_SELECTED)
    ctx.repo.put_pool(ctx.ws, pool)
    return assignment


def _require_pool(ctx: PoolContext, pool_id: str) -> Pool:
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")
    return pool
