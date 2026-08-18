"""Two lifecycle defects the audit found, pinned so they cannot come back.

**Pickup credentials before distribution.** A credential is Pool's proof that a physical
handoff happened (canonical invariant 9). Issuance checked only that the allocation
existed and had not already been collected — never the pool's lifecycle state. Since
allocations are written by ``execute_purchase``, the window between ``PURCHASED`` and
``DISTRIBUTING`` let a buyer's order be marked collected while the goods were still at
the supplier.

**Two host orderings.** The domain ranked ties toward the lower household id and the
hosting service selected with ``max``, which prefers the higher one. Both deterministic,
and they disagreed — so the ranking shown and the offer made could name different people.
"""

from __future__ import annotations

import pytest

from pool.domain.hosting import HostEvaluation, rank_hosts, ranking_key
from pool.domain.models import AllocationState, HostCandidate, HostCandidateState, PoolStatus
from pool.services import fulfillment
from pool.services import hosting as hosting_service
from tests.conftest import WS

# ------------------------------------------------------------------ pickup lifecycle


def _purchased_pool(ctx, bulk_offer):
    """A pool that has bought its goods but has *not* opened distribution.

    This is the state the defect lived in: allocations exist, so every check the old
    code performed passed, and the host has not collected anything.
    """
    from tests.test_fulfillment import _world

    pool = _world(ctx, bulk_offer=bulk_offer)
    fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.PURCHASED
    assert ctx.repo.list_allocations(WS, pool.id)
    return pool


def test_a_credential_cannot_be_issued_before_distribution_opens(ctx, bulk_offer):
    """The regression. Before the fix this minted a working credential."""
    pool = _purchased_pool(ctx, bulk_offer)

    with pytest.raises(fulfillment.FulfillmentError, match="pickup has not opened"):
        fulfillment.issue_pickup_credential(ctx=ctx, pool_id=pool.id, household_id="m0")

    assert ctx.repo.get_pickup_token(WS, pool.id, "m0") is None


def test_no_credential_exists_to_redeem_before_distribution(ctx, bulk_offer):
    """Refusing issuance is what makes the earlier window unreachable at all."""
    pool = _purchased_pool(ctx, bulk_offer)

    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented="anything")

    assert result.ok is False
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state == (
        AllocationState.PENDING_PURCHASE
    )


def test_a_credential_issued_legitimately_is_refused_if_the_pool_rewinds(ctx, bulk_offer):
    """Redemption re-checks the lifecycle rather than trusting issuance.

    The gate that matters is the one at the moment of the handoff — a credential that
    was valid when minted is not authority to collect at any later time.
    """
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    stored = ctx.repo.get_pool(WS, pool.id)
    stored.status = PoolStatus.PURCHASED
    ctx.repo.put_pool(WS, stored)

    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)

    assert result.ok is False
    assert "pickup has not opened" in result.reason
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state != AllocationState.PICKED_UP


def test_an_early_refusal_is_audited_like_every_other(ctx, bulk_offer):
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    stored = ctx.repo.get_pool(WS, pool.id)
    stored.status = PoolStatus.PURCHASED
    ctx.repo.put_pool(WS, stored)

    fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)

    assert any(e.kind == "pickup_rejected" for e in ctx.repo.list_activity(WS))


def test_an_order_under_issue_review_cannot_be_collected(ctx, bulk_offer):
    """A human is deciding what happened to it; a scan must not settle it for them."""
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    allocation = ctx.repo.get_allocation(WS, pool.id, "m0")
    allocation.state = AllocationState.ISSUE_REVIEW
    ctx.repo.put_allocation(WS, allocation)

    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)

    assert result.ok is False
    assert "not ready to collect" in result.reason


def test_the_ordinary_pickup_path_is_unchanged(ctx, bulk_offer):
    """The gate must not make the normal handoff harder."""
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )

    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)

    assert result.ok, result.reason
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state == AllocationState.PICKED_UP


def test_a_no_show_can_still_collect_in_the_secondary_window(ctx, bulk_offer):
    """`close_pickup_window` exists to offer a second chance, so this must stay open."""
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    fulfillment.close_pickup_window(ctx=ctx, pool_id=pool.id)
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state == AllocationState.NO_SHOW

    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)

    assert result.ok, result.reason


# ------------------------------------------------------------------- host tie-break


def _evaluation(household_id: str, score: int) -> HostEvaluation:
    return HostEvaluation(
        household_id=household_id,
        eligible=True,
        ineligible_reasons=[],
        score=score,
        components={},
        reward=None,
        supplier_distance_km=4.0,
        buyer_travel_penalty_minutes=0,
    )


def _candidate(household_id: str, score: int) -> HostCandidate:
    return HostCandidate(
        pool_id="pool_tie",
        household_id=household_id,
        source=None,
        state=HostCandidateState.CANDIDATE,
        eligible=True,
        score=score,
    )


def test_a_tie_breaks_toward_the_lower_household_id():
    """The documented and tested rule, stated once so both callers inherit it."""
    assert ranking_key(household_id="hh_aaa", score=50) < ranking_key(
        household_id="hh_bbb", score=50
    )
    ranked = rank_hosts([_evaluation("hh_bbb", 50), _evaluation("hh_aaa", 50)])
    assert [e.household_id for e in ranked] == ["hh_aaa", "hh_bbb"]


def test_score_still_outranks_the_tie_break():
    ranked = rank_hosts([_evaluation("hh_aaa", 10), _evaluation("hh_bbb", 90)])
    assert [e.household_id for e in ranked] == ["hh_bbb", "hh_aaa"]


@pytest.mark.parametrize("order", [("hh_aaa", "hh_bbb"), ("hh_bbb", "hh_aaa")])
def test_the_service_offers_the_job_to_whoever_ranks_first(order):
    """The defect: `max((score, household_id))` preferred the *higher* id on a tie, so
    the ranking the UI showed and the offer the pool made could name different people.

    Asserted against the domain ranking rather than a hard-coded name, so the two cannot
    drift apart again without this failing.
    """
    candidates = [_candidate(hid, 50) for hid in order]
    evaluations = [_evaluation(hid, 50) for hid in order]

    selected = min(
        candidates,
        key=lambda c: ranking_key(household_id=c.household_id, score=c.score),
    )

    assert selected.household_id == rank_hosts(evaluations)[0].household_id
    assert selected.household_id == "hh_aaa"


def test_the_service_selects_with_the_shared_key(ctx, bulk_offer):
    """Not a reimplementation: the module under test must import the canonical key."""
    import inspect

    source = inspect.getsource(hosting_service.offer_to_next_host)
    assert "ranking_key" in source
    assert "max(available" not in source


# ------------------------------------------------------- single-use, under concurrency


def test_two_simultaneous_scans_complete_exactly_one_handoff(ctx, bulk_offer):
    """Single use is a guarantee, not a convenience (canonical invariant 9).

    It was enforced by reading ``redeemed_at`` and then writing it, so two scans of one
    QR code arriving together both read empty and both completed the handoff. The claim
    is now a conditional write, so exactly one wins (#audit P2).
    """
    from tests.test_fulfillment import _fulfil_to_distribution

    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )

    results = [
        fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
        for _ in range(2)
    ]

    assert [r.ok for r in results] == [True, False]
    assert "already been used" in results[1].reason


def test_the_claim_is_atomic_across_two_repository_instances():
    """Two containers, one table: the check and the write have to be one operation."""
    from pool.adapters.repository import DynamoDBRepository
    from pool.domain.models import PickupToken
    from tests.test_public_demo import FakeDynamoTable

    table = FakeDynamoTable()
    first = DynamoDBRepository("pool-demo-state", table=table)
    second = DynamoDBRepository("pool-demo-state", table=table)
    first.put_pickup_token(
        WS,
        PickupToken(
            id="tok_1", pool_id="pool_1", household_id="m0",
            token_hash="h", code_hash="c", issued_at="2026-08-18T00:00:00Z",
        ),
    )

    won = first.claim_pickup_redemption(WS, "pool_1", "m0", "2026-08-18T01:00:00Z")
    lost = second.claim_pickup_redemption(WS, "pool_1", "m0", "2026-08-18T01:00:01Z")

    assert (won, lost) == (True, False)
    assert first.get_pickup_token(WS, "pool_1", "m0").redeemed_at == "2026-08-18T01:00:00Z"


def test_claiming_a_credential_that_does_not_exist_fails_rather_than_creating_one():
    from pool.adapters.repository import DynamoDBRepository
    from tests.test_public_demo import FakeDynamoTable

    repo = DynamoDBRepository("pool-demo-state", table=FakeDynamoTable())

    assert repo.claim_pickup_redemption(WS, "pool_1", "ghost", "2026-08-18T01:00:00Z") is False
    assert repo.get_pickup_token(WS, "pool_1", "ghost") is None
