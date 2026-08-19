"""The final-offer fixed point must fail closed.

A final offer is the moment estimates become money: the per-buyer figures in
``LandedEconomics`` are the amounts ``authorize_participant`` puts a hold on, and the
package count is what the supplier order is sized from. Both are computed for a
*specific* membership set. If the set changes after they are computed and the pricing
loop stops anyway, Pool authorises one price while describing another, and buys cases
for units nobody ordered — a direct violation of §48 and canonical invariant 6.

These tests pin the contract rather than the current arithmetic: economics are adopted
only from a pass that rejected nobody, and running out of passes is a loud failure.
"""

from __future__ import annotations

import pytest

from pool.data.seed import COMMUNITY_ID
from pool.domain.models import (
    DecisionKind,
    HostProfile,
    ParticipationState,
    PoolStatus,
    parse_iso,
)
from pool.services import coordination as coord
from pool.services import hosting
from tests.conftest import WS

PRODUCT = "prod_whey_vanilla"
SITE = "site_union"


def _pool_with_host(ctx):
    assessment = coord.evaluate_opportunity(
        ctx=ctx, community_id=COMMUNITY_ID, product_id=PRODUCT, pickup_site_id=SITE
    )
    assert assessment.viable, assessment.reason
    pool, _ = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key="converge"
    )
    hosting.open_host_recruiting(ctx=ctx, pool_id=pool.id)
    hosting.volunteer_to_host(
        ctx=ctx,
        pool_id=pool.id,
        household_id="hh_marchetti",
        profile=HostProfile(
            household_id="hh_marchetti", community_id=COMMUNITY_ID, has_vehicle=True,
            vehicle_capacity_units=100, max_orders=60, max_weight_kg=200,
            max_supplier_distance_km=50.0, minimum_compensation_cents=0, standing=False,
        ),
    )
    offer = hosting.offer_to_next_host(ctx=ctx, pool_id=pool.id)
    hosting.respond_to_host_offer(
        ctx=ctx, pool_id=pool.id, household_id=offer.offered_household_id, accept=True
    )
    return pool


def _reject_on_distribution_day(ctx, pool, household_id: str) -> None:
    """Make one buyer's rules refuse this pool outright.

    Pickup-day availability is a *hard* Smart Join rule, so the member is removed by the
    pricing loop rather than merely asked. It is also price-independent, which is what
    makes it a clean lever: the rejection lands on whichever pass runs first.
    """
    day = parse_iso(
        ctx.repo.get_pool(ctx.ws, pool.id).timing.distribution_starts_at
    ).date()
    household = ctx.repo.get_household(ctx.ws, household_id)
    household.autonomy.available_pickup_weekdays = [(day.weekday() + 2) % 7]
    ctx.repo.put_household(ctx.ws, household)


def _active(ctx, pool_id) -> list:
    return [
        m
        for m in ctx.repo.list_memberships(ctx.ws, pool_id)
        if m.state != ParticipationState.DECLINED
    ]


# --------------------------------------------------------- the canonical flow is intact


def test_canonical_final_offer_still_issues_unchanged(declared_ctx):
    """The ordinary path converges on the first pass and is untouched by the contract."""
    pool = _pool_with_host(declared_ctx)
    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert result.issued, result.reason
    assert result.removed == []
    assert result.economics["all_in_cents"] == 86144
    assert result.economics["net_savings_cents"] == 26632
    assert result.economics["packages"]["total_units"] == 24
    assert len(result.economics["lines"]) == len(_active(declared_ctx, pool.id)) == 10


def test_pruning_converges_and_reprices_for_the_survivors(declared_ctx):
    """A rejection mid-loop is repriced, not carried forward.

    The published economics must describe the buyers who remain — never the larger set
    they were first computed for.
    """
    pool = _pool_with_host(declared_ctx)
    _reject_on_distribution_day(declared_ctx, pool, "hh_villanueva")

    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert result.removed == ["hh_villanueva"]
    survivors = _active(declared_ctx, pool.id)
    assert len(survivors) == 9
    # Whether or not this smaller pool clears its other gates, the numbers it reports
    # are the survivors' numbers.
    assert len(result.economics["lines"]) == 9
    assert result.economics["packages"]["total_units"] == sum(
        m.allocated_units for m in survivors
    )


# ------------------------------------------------------- rejection on the last pass


def test_rejection_on_the_last_permitted_pass_fails_closed(declared_ctx, monkeypatch):
    """The regression: pruning on the final pass must not issue the prior set's price.

    Before the convergence contract this returned ``issued=True`` carrying economics for
    ten buyers while only nine memberships survived — and authorised seven of them at
    those ten-buyer amounts, against a 24-unit order for 22 units of real demand.
    """
    monkeypatch.setattr(coord, "MAX_PRICING_PASSES", 1)
    pool = _pool_with_host(declared_ctx)
    _reject_on_distribution_day(declared_ctx, pool, "hh_villanueva")

    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert not result.issued
    assert "did not settle" in result.reason
    assert result.removed == ["hh_villanueva"]
    # No stale economics are retained as valid, anywhere a consumer can read them.
    assert not result.economics
    assert declared_ctx.repo.get_pool(WS, pool.id).final_economics == {}


def test_non_convergence_authorises_nobody(declared_ctx, monkeypatch):
    """Failing closed means no money is touched and no buyer is put in a funded state."""
    monkeypatch.setattr(coord, "MAX_PRICING_PASSES", 1)
    pool = _pool_with_host(declared_ctx)
    _reject_on_distribution_day(declared_ctx, pool, "hh_villanueva")

    coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert declared_ctx.repo.list_payments(WS) == []
    assert not any(
        m.state == ParticipationState.FINAL_OFFERED
        for m in declared_ctx.repo.list_memberships(WS, pool.id)
    )
    assert all(m.final_cost_cents == 0 for m in _active(declared_ctx, pool.id))
    assert not any(
        d.kind == DecisionKind.APPROVE_FINAL_OFFER
        for d in declared_ctx.repo.list_decisions(WS)
    )


def test_non_convergence_is_recorded_loudly(declared_ctx, monkeypatch):
    """A bound that is hit must leave a record, never a silent truncation (§3.1)."""
    monkeypatch.setattr(coord, "MAX_PRICING_PASSES", 1)
    pool = _pool_with_host(declared_ctx)
    _reject_on_distribution_day(declared_ctx, pool, "hh_villanueva")

    coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    kinds = [e.kind for e in declared_ctx.repo.list_activity(WS)]
    assert "final_offer_not_converged" in kinds
    stored = declared_ctx.repo.get_pool(WS, pool.id)
    assert stored.status == PoolStatus.FAILED
    assert "did not settle" in stored.failure_reason


def test_every_buyer_rejected_still_reports_its_own_reason(declared_ctx, monkeypatch):
    """Losing the whole pool is a different failure from failing to converge."""
    monkeypatch.setattr(coord, "MAX_PRICING_PASSES", 4)
    pool = _pool_with_host(declared_ctx)
    for membership in _active(declared_ctx, pool.id):
        _reject_on_distribution_day(declared_ctx, pool, membership.household_id)

    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert not result.issued
    assert result.reason == "no buyer's rules accept the final price"
    assert declared_ctx.repo.get_pool(WS, pool.id).status == PoolStatus.FAILED


@pytest.mark.parametrize("passes", [2, 3, 4])
def test_a_single_rejection_converges_well_inside_the_bound(declared_ctx, monkeypatch, passes):
    """One pruning wave needs two passes: one to prune, one to confirm stability."""
    monkeypatch.setattr(coord, "MAX_PRICING_PASSES", passes)
    pool = _pool_with_host(declared_ctx)
    _reject_on_distribution_day(declared_ctx, pool, "hh_villanueva")

    result = coord.issue_final_offer(ctx=declared_ctx, pool_id=pool.id)

    assert "did not settle" not in result.reason
    assert len(result.economics["lines"]) == len(_active(declared_ctx, pool.id)) == 9
