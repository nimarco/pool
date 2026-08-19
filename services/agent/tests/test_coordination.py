"""The coordination lifecycle, exercised against the deterministic demo community.

These are integration tests over the real services: real matching, real economics, real
host ranking, real payment provider, real state machine. They assert the ordering rules
that make the product honest — provisional is not committed, the host is chosen before
anyone is charged, and no stale quote becomes a final price.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from pool.adapters.sourcing import DriftingCatalogProvider, SyntheticCatalogProvider
from pool.data.seed import COMMUNITY_ID
from pool.domain.models import (
    DecisionKind,
    DecisionState,
    HostProfile,
    ParticipationState,
    PaymentState,
    PoolStatus,
    iso,
)
from pool.domain.viability import ViabilityStage
from pool.services import coordination as coord
from pool.services import hosting
from pool.services.context import CoordinationError
from tests.conftest import WS

PRODUCT = "prod_whey_vanilla"
SITE = "site_union"


def _assess(ctx, **kwargs):
    return coord.evaluate_opportunity(
        ctx=ctx, community_id=COMMUNITY_ID, product_id=PRODUCT, pickup_site_id=SITE, **kwargs
    )


def _candidate_pool(ctx):
    assessment = _assess(ctx)
    assert assessment.viable, assessment.reason
    pool, _ = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key="k1"
    )
    return pool, assessment


def _with_host(ctx, pool, household_id="hh_marchetti"):
    hosting.open_host_recruiting(ctx=ctx, pool_id=pool.id)
    hosting.volunteer_to_host(
        ctx=ctx,
        pool_id=pool.id,
        household_id=household_id,
        profile=HostProfile(
            household_id=household_id, community_id=COMMUNITY_ID, has_vehicle=True,
            vehicle_capacity_units=100, max_orders=60, max_weight_kg=200,
            max_supplier_distance_km=50.0, minimum_compensation_cents=0, standing=False,
        ),
    )
    offer = hosting.offer_to_next_host(ctx=ctx, pool_id=pool.id)
    hosting.respond_to_host_offer(
        ctx=ctx, pool_id=pool.id, household_id=offer.offered_household_id, accept=True
    )
    return offer.offered_household_id


# ------------------------------------------------------------------------ discovery


def test_a_viable_opportunity_is_found_without_anyone_organising_it(seeded_ctx):
    assessment = _assess(seeded_ctx)
    assert assessment.viable
    assert assessment.economics is not None
    assert assessment.economics.net_savings_cents > 0


def test_the_pool_lands_on_an_exact_case_boundary(seeded_ctx):
    """Pool never quietly buys the leftovers of a part-filled case (§48)."""
    assessment = _assess(seeded_ctx)
    packages = assessment.economics.packages
    assert packages.surplus_units == 0
    assert packages.total_units % packages.case_units == 0
    assert packages.total_units >= packages.moq_units


def test_permitted_future_demand_unlocks_the_better_supplier_tier(declared_ctx):
    """Current demand alone cannot reach the 24-unit tier; the pull-forward can (§24).

    Without it the pool falls back to a smaller, worse-priced tier — which is the
    honest outcome, not a failure — so the assertion is about which offer wins and how
    much the group actually saves.
    """
    with_future = _assess(declared_ctx)
    without_future = _assess(declared_ctx, include_future_demand=False)
    assert with_future.viable and without_future.viable
    assert with_future.future_units > 0
    assert without_future.future_units == 0
    assert with_future.bulk_offer_id != without_future.bulk_offer_id
    assert (
        with_future.economics.net_savings_cents
        > without_future.economics.net_savings_cents
    )


def test_the_estimate_is_labelled_as_an_estimate_before_a_host_exists(seeded_ctx):
    assessment = _assess(seeded_ctx)
    assert assessment.economics.host_is_estimated is True


def test_a_product_whose_bulk_price_does_not_beat_retail_forms_no_pool(seeded_ctx):
    """The *reason* is the assertion, not the absence of a pool.

    This used to assert ``viable is False`` alone, and passed for years without the
    economics ever being reached: at the old global 1.6 km formation radius the
    detergent demand never cleared its supplier minimum, so the run refused on
    ``below_minimum`` and the branch this test is named after was dead. A test that
    cannot distinguish "too few people" from "pooling this saves nothing" is not
    testing the invariant in its name (AGENTS.md §7).
    """
    assessment = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id="prod_detergent_pods", pickup_site_id="site_quad",
    )
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_NOT_CHEAPER
    # Enough demand existed; the all-in price is what failed.
    assert assessment.matched_units >= assessment.minimum_units
    assert assessment.economics is not None
    assert assessment.economics.net_savings_cents <= 0


def test_rejections_belong_to_the_offer_that_won_not_the_one_evaluated_last(seeded_ctx):
    """Which supplier tier a member was measured against changes who it excluded.

    Whey has two tiers: $31.50/unit with a 24-unit minimum, and $39.80/unit with a
    12-unit one. A member whose substitution rule carries a per-unit ceiling between
    them is compatible with the cheap tier and rejected by the expensive one — and the
    expensive one is evaluated second.

    The rejection list used to be written onto one shared record inside the tier loop,
    so a *winning* assessment came back explaining itself with the *losing* tier's
    rejections: this member appeared excluded from the very pool they were in. Nothing
    downstream could have noticed, which is why the run report must not be built on it.
    """
    from datetime import date, timedelta

    from pool.domain.models import NeedDeclaration, SubstitutionPolicy

    due = date.today() + timedelta(days=12)
    seeded_ctx.repo.put_need(
        WS,
        NeedDeclaration(
            id="need_ceiling",
            household_id="hh_navarro",
            community_id=COMMUNITY_ID,
            # A different variant of the same brand, so the substitution rule is what
            # decides — and the price ceiling then applies, as it does to every
            # non-exact substitution.
            product_id="prod_whey_chocolate",
            quantity=2,
            cadence_days=40,
            expected_next_need_date=due,
            earliest_acceptable_purchase_date=due - timedelta(days=12),
            latest_acceptable_purchase_date=due,
            routine_lead_days=12,
            substitution=SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT,
            max_unit_price_cents=3500,
        ),
    )
    assessment = _assess(seeded_ctx)
    assert assessment.viable
    assert assessment.bulk_offer_id == "off_whey_bulk"

    rejected_needs = {r["need_id"] for r in assessment.rejected}
    selected_needs = {c.need_id for c in assessment.candidates}
    # The invariant in general form: an assessment never both selects and rejects the
    # same declaration, whatever the tiers disagreed about.
    assert not (rejected_needs & selected_needs)
    assert "need_ceiling" not in rejected_needs

    # And the two quantities a member reads describe the same real offer.
    winning = seeded_ctx.repo.get_offer(WS, assessment.bulk_offer_id)
    assert assessment.minimum_units == winning.min_units
    assert assessment.matched_units >= assessment.minimum_units


def test_a_refusal_is_explained_by_the_tier_that_came_closest(seeded_ctx):
    """When no tier prices, the units-found and units-required a member is shown have to
    come from one supplier offer. Reporting the largest match from one tier beside the
    smallest minimum from another is two true numbers describing an offer nobody made."""
    assessment = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id="prod_paper_towels", pickup_site_id=SITE,
    )
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_BELOW_MINIMUM
    tiers = {o.min_units for o in coord.offers_for(seeded_ctx, "prod_paper_towels")[1]}
    assert assessment.minimum_units in tiers
    assert assessment.matched_units < assessment.minimum_units


def test_an_unknown_product_or_site_is_an_error(seeded_ctx):
    with pytest.raises(CoordinationError):
        coord.evaluate_opportunity(
            ctx=seeded_ctx, community_id=COMMUNITY_ID,
            product_id="nope", pickup_site_id=SITE,
        )
    with pytest.raises(CoordinationError):
        coord.evaluate_opportunity(
            ctx=seeded_ctx, community_id=COMMUNITY_ID,
            product_id=PRODUCT, pickup_site_id="nope",
        )


# --------------------------------------------------------------------- candidate pool


def test_creating_a_pool_commits_no_money(seeded_ctx):
    """A candidate pool is visible demand, not a charge (§25, §26)."""
    pool, _ = _candidate_pool(seeded_ctx)
    members = seeded_ctx.repo.list_memberships(WS, pool.id)
    assert members
    assert all(m.state == ParticipationState.PROVISIONAL for m in members)
    assert all(m.final_cost_cents == 0 for m in members)
    assert seeded_ctx.repo.list_payments(WS, pool.id) == []
    assert seeded_ctx.repo.list_decisions(WS) == []


def test_pool_creation_is_idempotent(seeded_ctx):
    assessment = _assess(seeded_ctx)
    first, created_first = coord.create_candidate_pool(
        ctx=seeded_ctx, assessment=assessment, idempotency_key="same"
    )
    second, created_second = coord.create_candidate_pool(
        ctx=seeded_ctx, assessment=assessment, idempotency_key="same"
    )
    assert created_first is True and created_second is False
    assert first.id == second.id
    assert len(seeded_ctx.repo.list_pools(WS)) == 1


def test_a_non_viable_assessment_cannot_become_a_pool(seeded_ctx):
    assessment = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id="prod_detergent_pods", pickup_site_id="site_quad",
    )
    with pytest.raises(CoordinationError):
        coord.create_candidate_pool(
            ctx=seeded_ctx, assessment=assessment, idempotency_key="k"
        )


def test_provisional_demand_opens_host_recruiting(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    assert hosting.open_host_recruiting(ctx=seeded_ctx, pool_id=pool.id) is True
    assert seeded_ctx.repo.get_pool(WS, pool.id).status == PoolStatus.HOST_RECRUITING


def test_a_member_can_join_a_candidate_pool_and_it_is_idempotent(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    existing = {m.household_id for m in seeded_ctx.repo.list_memberships(WS, pool.id)}
    newcomer = next(
        n for n in seeded_ctx.repo.list_needs(WS)
        if n.product_id == PRODUCT and n.household_id not in existing
    )
    first = coord.join_pool_provisionally(
        ctx=seeded_ctx, pool_id=pool.id, household_id=newcomer.household_id,
        need_id=newcomer.id,
    )
    second = coord.join_pool_provisionally(
        ctx=seeded_ctx, pool_id=pool.id, household_id=newcomer.household_id,
        need_id=newcomer.id,
    )
    assert first.state == ParticipationState.PROVISIONAL
    assert second.key == first.key


# -------------------------------------------------------------------------- hosting


def test_offering_to_host_does_not_claim_the_job(seeded_ctx):
    """Several people may offer; the evaluator decides (§28)."""
    pool, _ = _candidate_pool(seeded_ctx)
    hosting.open_host_recruiting(ctx=seeded_ctx, pool_id=pool.id)
    candidate = hosting.volunteer_to_host(
        ctx=seeded_ctx, pool_id=pool.id, household_id="hh_okafor"
    )
    assert candidate.state.value == "candidate"
    assert seeded_ctx.repo.get_host_assignment(WS, pool.id) is None


def test_only_one_host_offer_is_outstanding_at_a_time(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    hosting.open_host_recruiting(ctx=declared_ctx, pool_id=pool.id)
    first = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    second = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    assert first.offered_household_id == second.offered_household_id
    offered = [
        c for c in declared_ctx.repo.list_host_candidates(WS, pool.id)
        if c.state.value == "offered"
    ]
    assert len(offered) == 1


def test_a_declined_offer_moves_to_the_next_candidate(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    hosting.open_host_recruiting(ctx=declared_ctx, pool_id=pool.id)
    # Give a second eligible candidate so there is somewhere to go.
    hosting.volunteer_to_host(
        ctx=declared_ctx, pool_id=pool.id, household_id="hh_thibault",
        profile=HostProfile(
            household_id="hh_thibault", community_id=COMMUNITY_ID, has_vehicle=True,
            vehicle_capacity_units=100, max_orders=60, max_weight_kg=200,
            max_supplier_distance_km=50.0, minimum_compensation_cents=0, standing=False,
        ),
    )
    first = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    result = hosting.respond_to_host_offer(
        ctx=declared_ctx, pool_id=pool.id,
        household_id=first.offered_household_id, accept=False,
    )
    assert result["accepted"] is False
    assert result["next_offered_household_id"]
    assert result["next_offered_household_id"] != first.offered_household_id


def test_answering_a_host_offer_from_the_decision_inbox_assigns_the_host(declared_ctx):
    """The decision inbox is the one place a person answers anything Pool asks.

    A host offer creates a `HOST_OFFER` decision, and `respond_to_decision` used to
    handle only the two buyer kinds: the decision went to APPROVED, the candidate stayed
    OFFERED, no assignment was written, and the pool sat in HOST_RECRUITING forever. The
    UI shipped an "Accept the job" button wired to exactly that path, so the button did
    nothing. Answering here must reach the same service the host's own endpoint calls.
    """
    pool, _ = _candidate_pool(declared_ctx)
    hosting.open_host_recruiting(ctx=declared_ctx, pool_id=pool.id)
    offer = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    decision = next(
        d
        for d in declared_ctx.repo.list_decisions(WS)
        if d.kind == DecisionKind.HOST_OFFER
        and d.household_id == offer.offered_household_id
        and d.state == DecisionState.PENDING
    )

    coord.respond_to_decision(ctx=declared_ctx, decision_id=decision.id, approve=True)

    assignment = declared_ctx.repo.get_host_assignment(WS, pool.id)
    assert assignment is not None
    assert assignment.household_id == offer.offered_household_id
    assert declared_ctx.repo.get_pool(WS, pool.id).status == PoolStatus.HOST_SELECTED
    # And the record says what actually happened, rather than reporting a host's answer
    # as a buyer approving a price.
    answered = [e for e in declared_ctx.repo.list_activity(WS) if e.kind == "decision_answered"]
    assert answered and "Host accepted" in answered[0].summary


def test_declining_a_host_offer_from_the_decision_inbox_moves_on(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    hosting.open_host_recruiting(ctx=declared_ctx, pool_id=pool.id)
    hosting.volunteer_to_host(
        ctx=declared_ctx, pool_id=pool.id, household_id="hh_thibault",
        profile=HostProfile(
            household_id="hh_thibault", community_id=COMMUNITY_ID, has_vehicle=True,
            vehicle_capacity_units=100, max_orders=60, max_weight_kg=200,
            max_supplier_distance_km=50.0, minimum_compensation_cents=0, standing=False,
        ),
    )
    offer = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    decision = next(
        d
        for d in declared_ctx.repo.list_decisions(WS)
        if d.kind == DecisionKind.HOST_OFFER
        and d.household_id == offer.offered_household_id
        and d.state == DecisionState.PENDING
    )

    coord.respond_to_decision(ctx=declared_ctx, decision_id=decision.id, approve=False)

    assert declared_ctx.repo.get_host_assignment(WS, pool.id) is None
    still_offered = [
        c for c in declared_ctx.repo.list_host_candidates(WS, pool.id)
        if c.state.value == "offered"
    ]
    assert len(still_offered) == 1
    assert still_offered[0].household_id != offer.offered_household_id


def test_an_expired_host_offer_does_not_stall_the_pool(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    hosting.open_host_recruiting(ctx=declared_ctx, pool_id=pool.id)
    offer = hosting.offer_to_next_host(ctx=declared_ctx, pool_id=pool.id)
    candidate = declared_ctx.repo.get_host_candidate(
        WS, pool.id, offer.offered_household_id
    )
    candidate.expires_at = iso(declared_ctx.now - timedelta(hours=1))
    declared_ctx.repo.put_host_candidate(WS, candidate)
    expired = hosting.expire_stale_host_offers(ctx=declared_ctx, pool_id=pool.id)
    assert expired == [offer.offered_household_id]
    decisions = [
        d for d in declared_ctx.repo.list_decisions(WS) if d.kind == DecisionKind.HOST_OFFER
    ]
    assert all(d.state == DecisionState.EXPIRED for d in decisions)


def test_accepting_assigns_the_job_and_fixes_the_compensation(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    host_id = _with_host(seeded_ctx, pool)
    assignment = seeded_ctx.repo.get_host_assignment(WS, pool.id)
    assert assignment.household_id == host_id
    assert assignment.reward_total_cents > 0
    assert sum(assignment.reward_breakdown.values()) >= assignment.reward_total_cents * 0.5
    assert seeded_ctx.repo.get_pool(WS, pool.id).status == PoolStatus.HOST_SELECTED


def test_a_host_who_is_also_a_buyer_keeps_two_separate_ledger_entries(declared_ctx):
    """Buyer allocation and host pay are never netted together invisibly (§30)."""
    pool, _ = _candidate_pool(declared_ctx)
    host_id = _with_host(declared_ctx, pool, household_id="hh_marchetti")
    coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)
    membership = declared_ctx.repo.get_membership(WS, pool.id, host_id)
    assignment = declared_ctx.repo.get_host_assignment(WS, pool.id)
    assert membership is not None and membership.final_cost_cents > 0
    assert assignment.reward_total_cents > 0
    assert membership.final_cost_cents != assignment.reward_total_cents


# --------------------------------------------------------------------- final offer


def test_no_final_offer_without_a_host(seeded_ctx):
    """Host pay is part of the buyer's price, so it cannot be priced without one (§35)."""
    pool, _ = _candidate_pool(seeded_ctx)
    result = coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    assert result.issued is False
    assert "host" in result.reason


def test_the_final_offer_refreshes_the_quote_and_prices_everything(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    result = coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    assert result.issued
    econ = result.economics
    assert econ["merchandise_cents"] > 0
    assert econ["host_compensation_cents"] > 0
    assert econ["payment_processing_cents"] > 0
    assert econ["platform_fee_cents"] > 0
    assert econ["all_in_cents"] < econ["retail_baseline_cents"]
    pool = seeded_ctx.repo.get_pool(WS, pool.id)
    assert pool.quote_verified_at
    assert pool.status == PoolStatus.FUNDING


def test_smart_join_authorises_and_everyone_else_is_asked(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    _with_host(declared_ctx, pool)
    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)
    assert result.auto_authorised
    assert result.awaiting_decision
    for household_id in result.auto_authorised:
        membership = declared_ctx.repo.get_membership(WS, pool.id, household_id)
        assert membership.state == ParticipationState.AUTHORIZED
        assert membership.final_cost_cents > 0
    decisions = [
        d for d in declared_ctx.repo.list_decisions(WS)
        if d.kind == DecisionKind.APPROVE_FINAL_OFFER
    ]
    assert len(decisions) == len(result.awaiting_decision)


def test_the_decision_carries_the_full_cost_breakdown(seeded_ctx):
    """A human is asked with the answer already worked out, not a bare number."""
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    decision = next(
        d for d in seeded_ctx.repo.list_decisions(WS)
        if d.kind == DecisionKind.APPROVE_FINAL_OFFER
    )
    breakdown = decision.facts["cost_breakdown"]
    assert set(breakdown) == {
        "merchandise", "host_compensation", "pool_fee", "payment_processing"
    }
    assert decision.facts["final_cost_cents"] == sum(breakdown.values())
    assert decision.facts["policy_checks"]


def test_a_declined_final_offer_does_not_charge_anyone(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    result = coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    decision = next(
        d for d in seeded_ctx.repo.list_decisions(WS)
        if d.household_id == result.awaiting_decision[0]
    )
    coord.respond_to_decision(ctx=seeded_ctx, decision_id=decision.id, approve=False)
    membership = seeded_ctx.repo.get_membership(WS, pool.id, decision.household_id)
    assert membership.state == ParticipationState.DECLINED
    assert not [
        p for p in seeded_ctx.repo.list_payments(WS, pool.id)
        if p.household_id == decision.household_id
    ]


def test_answering_a_decision_twice_is_a_no_op(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    decision = next(
        d for d in seeded_ctx.repo.list_decisions(WS)
        if d.kind == DecisionKind.APPROVE_FINAL_OFFER
    )
    coord.respond_to_decision(ctx=seeded_ctx, decision_id=decision.id, approve=True)
    payments_after_first = len(seeded_ctx.repo.list_payments(WS, pool.id))
    coord.respond_to_decision(ctx=seeded_ctx, decision_id=decision.id, approve=False)
    assert len(seeded_ctx.repo.list_payments(WS, pool.id)) == payments_after_first


def test_a_moved_supplier_price_invalidates_the_final_economics(seeded_ctx):
    """A stale price must never become someone's charge (§43)."""
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    seeded_ctx.sourcing = DriftingCatalogProvider(
        delta_cents=400, inner=SyntheticCatalogProvider()
    )
    refresh = coord.refresh_quote(ctx=seeded_ctx, pool_id=pool.id)
    assert refresh.ok and refresh.changed
    assert seeded_ctx.repo.get_pool(WS, pool.id).final_economics == {}


def test_a_quote_that_cannot_be_re_verified_blocks_the_final_offer(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    offer = seeded_ctx.repo.get_offer(WS, pool.offer_id)
    offer.active = False
    seeded_ctx.repo.put_offer(WS, offer)
    result = coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    assert result.issued is False
    assert "re-verified" in result.reason


# -------------------------------------------------------------------- lock and exit


def _fully_funded(ctx):
    pool, _ = _candidate_pool(ctx)
    _with_host(ctx, pool)
    coord.issue_final_offer(ctx=ctx, pool_id=pool.id)
    for d in list(ctx.repo.list_decisions(WS)):
        if d.state == DecisionState.PENDING and d.kind == DecisionKind.APPROVE_FINAL_OFFER:
            coord.respond_to_decision(ctx=ctx, decision_id=d.id, approve=True)
    return ctx.repo.get_pool(WS, pool.id)


def test_a_fully_funded_viable_pool_locks_and_captures(declared_ctx):
    pool = _fully_funded(declared_ctx)
    if coord.lost_units(declared_ctx, pool.id):
        coord.recover_pool(ctx=declared_ctx, pool_id=pool.id)
    result = coord.lock_pool(ctx=declared_ctx, pool_id=pool.id)
    assert result["locked"] is True
    pool = declared_ctx.repo.get_pool(WS, pool.id)
    assert pool.status == PoolStatus.PURCHASE_READY
    captured = [
        p for p in declared_ctx.repo.list_payments(WS, pool.id)
        if p.state == PaymentState.CAPTURED
    ]
    assert captured
    assert sum(p.amount_cents for p in captured) == pool.final_economics["all_in_cents"]


def test_an_underfunded_pool_refuses_to_lock(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    result = coord.lock_pool(ctx=seeded_ctx, pool_id=pool.id)
    assert result["locked"] is False
    assert result["viability"]["failed"]
    assert not [
        p for p in seeded_ctx.repo.list_payments(WS, pool.id)
        if p.state == PaymentState.CAPTURED
    ]


def test_locking_twice_is_a_no_op(declared_ctx):
    pool = _fully_funded(declared_ctx)
    if coord.lost_units(declared_ctx, pool.id):
        coord.recover_pool(ctx=declared_ctx, pool_id=pool.id)
    coord.lock_pool(ctx=declared_ctx, pool_id=pool.id)
    again = coord.lock_pool(ctx=declared_ctx, pool_id=pool.id)
    assert again["already_locked"] is True


def test_a_buyer_can_leave_freely_before_authorisation(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    member = seeded_ctx.repo.list_memberships(WS, pool.id)[0]
    result = coord.withdraw_participant(
        ctx=seeded_ctx, pool_id=pool.id, household_id=member.household_id
    )
    assert result["already_withdrawn"] is False
    assert seeded_ctx.repo.get_membership(
        WS, pool.id, member.household_id
    ).state == ParticipationState.WITHDRAWN


def test_withdrawing_after_authorisation_releases_the_hold(declared_ctx):
    pool, _ = _candidate_pool(declared_ctx)
    _with_host(declared_ctx, pool)
    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)
    leaver = result.auto_authorised[0]
    outcome = coord.withdraw_participant(
        ctx=declared_ctx, pool_id=pool.id, household_id=leaver
    )
    assert outcome["authorization_released"] is True
    assert outcome["below_threshold"] is True


def test_withdrawing_after_lock_is_refused(declared_ctx):
    """Past the lock the money is captured and the supplier order is committed (§59)."""
    pool = _fully_funded(declared_ctx)
    if coord.lost_units(declared_ctx, pool.id):
        coord.recover_pool(ctx=declared_ctx, pool_id=pool.id)
    coord.lock_pool(ctx=declared_ctx, pool_id=pool.id)
    member = next(
        m for m in declared_ctx.repo.list_memberships(WS, pool.id) if m.counts_as_funded
    )
    with pytest.raises(CoordinationError) as exc:
        coord.withdraw_participant(
            ctx=declared_ctx, pool_id=pool.id, household_id=member.household_id
        )
    assert "locked" in str(exc.value)


def test_withdrawing_twice_does_not_double_subtract(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    member = seeded_ctx.repo.list_memberships(WS, pool.id)[0]
    coord.withdraw_participant(
        ctx=seeded_ctx, pool_id=pool.id, household_id=member.household_id
    )
    again = coord.withdraw_participant(
        ctx=seeded_ctx, pool_id=pool.id, household_id=member.household_id
    )
    assert again["already_withdrawn"] is True


# ---------------------------------------------------------------------- recovery


def test_recovery_replaces_exactly_what_was_lost(seeded_ctx):
    """Over-recruiting would trade a funding hole for speculative stock (§48)."""
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    for d in list(seeded_ctx.repo.list_decisions(WS)):
        if d.state == DecisionState.PENDING and d.kind == DecisionKind.APPROVE_FINAL_OFFER:
            coord.respond_to_decision(ctx=seeded_ctx, decision_id=d.id, approve=True)

    priced_units = seeded_ctx.repo.get_pool(WS, pool.id).final_economics["packages"][
        "total_units"
    ]
    lost = coord.lost_units(seeded_ctx, pool.id)
    assert lost > 0  # the seeded declining card did its job
    result = coord.recover_pool(ctx=seeded_ctx, pool_id=pool.id)
    assert result.recovered is True
    assert coord.in_play_units(seeded_ctx, pool.id) == priced_units


def test_an_unanswered_buyer_is_not_treated_as_a_hole_to_fill(seeded_ctx):
    """Recruiting over the top of someone who has not replied leaves Pool oversubscribed."""
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    result = coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    awaiting_units = sum(
        m.allocated_units
        for m in seeded_ctx.repo.list_memberships(WS, pool.id)
        if m.state == ParticipationState.FINAL_OFFERED
    )
    failed_units = sum(
        m.allocated_units
        for m in seeded_ctx.repo.list_memberships(WS, pool.id)
        if m.state == ParticipationState.AUTHORIZATION_FAILED
    )
    assert awaiting_units > 0
    assert len(result.awaiting_decision) > 0
    # The gap Pool tries to fill is exactly what was lost — never the pending replies.
    assert coord.lost_units(seeded_ctx, pool.id) == failed_units


def test_recovery_is_a_no_op_when_nothing_has_been_lost(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    coord.recover_pool(ctx=seeded_ctx, pool_id=pool.id)  # fills the genuine gap
    again = coord.recover_pool(ctx=seeded_ctx, pool_id=pool.id)
    assert again.recovered is True
    assert again.shortfall_units == 0
    assert again.added_household_ids == []


def test_recovery_reports_honestly_when_nothing_can_replace_the_gap(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    _with_host(seeded_ctx, pool)
    coord.issue_final_offer(ctx=seeded_ctx, pool_id=pool.id)
    # Remove every unpooled whey need so no replacement exists.
    for need in list(seeded_ctx.repo.list_needs(WS)):
        if need.product_id == PRODUCT:
            member = seeded_ctx.repo.get_membership(WS, pool.id, need.household_id)
            if member is None:
                need.active = False
                seeded_ctx.repo.put_need(WS, need)
    for m in seeded_ctx.repo.list_memberships(WS, pool.id):
        if m.state == ParticipationState.FINAL_OFFERED:
            m.state = ParticipationState.WITHDRAWN
            seeded_ctx.repo.put_membership(WS, m)
    result = coord.recover_pool(ctx=seeded_ctx, pool_id=pool.id)
    assert result.recovered is False


# ---------------------------------------------------------------------- viability


def test_viability_checks_run_against_stored_state(seeded_ctx):
    pool, _ = _candidate_pool(seeded_ctx)
    verdict = coord.check_viability(
        ctx=seeded_ctx, pool_id=pool.id, stage=ViabilityStage.PRE_FUNDING
    )
    assert "host_assigned" in verdict.failed
    _with_host(seeded_ctx, pool)
    after = coord.check_viability(
        ctx=seeded_ctx, pool_id=pool.id, stage=ViabilityStage.PRE_FUNDING
    )
    assert "host_assigned" not in after.failed


# ------------------------------------------------------------------------ metrics


def test_metrics_are_computed_from_records_and_labelled_as_demo_data(seeded_ctx):
    pool = _fully_funded(seeded_ctx)
    if coord.lost_units(seeded_ctx, pool.id):
        coord.recover_pool(ctx=seeded_ctx, pool_id=pool.id)
    coord.lock_pool(ctx=seeded_ctx, pool_id=pool.id)
    metrics = coord.impact_metrics(seeded_ctx)
    assert metrics["is_demo_data"] is True
    assert metrics["members_participating"] > 0
    assert metrics["collective_savings_cents"] > 0
    assert metrics["host_earnings_cents"] > 0
    assert (
        metrics["estimated_retail_spend_cents"] - metrics["pool_spend_cents"]
        == metrics["collective_savings_cents"]
    )
