"""Purchase execution, pickup credentials, the host checklist, no-shows, and issues.

The security properties matter most here: a host must not be able to complete an order
without the buyer's credential, and a credential must not work twice.
"""

from __future__ import annotations

import pytest

from pool.adapters.purchase import (
    PURCHASE_FAILURE_MARKER,
    PurchaseError,
    PurchaseOrder,
    SimulatedPurchaseExecutor,
    build_purchase_executor,
)
from pool.domain.models import (
    AllocationState,
    AutonomyPath,
    FulfillerRole,
    HostAssignment,
    IssueKind,
    IssueState,
    Membership,
    ParticipationState,
    PickupPermission,
    PickupSite,
    Pool,
    PoolStatus,
    PoolTiming,
    Product,
    iso,
    utcnow,
)
from pool.domain.pickup import (
    CODE_ALPHABET,
    hash_code,
    issue_credential,
    matches_code,
    matches_token,
    normalise_code,
)
from pool.services import fulfillment
from tests.conftest import COMM, WS, make_member

# --------------------------------------------------------------------- credentials


def test_a_credential_is_unguessable_and_stored_only_as_a_hash():
    first, second = issue_credential(), issue_credential()
    assert first.token != second.token
    assert first.code != second.code
    assert len(first.token) >= 24
    assert first.token_hash != first.token
    assert first.code_hash != first.code


def test_the_short_code_avoids_characters_that_get_misread():
    for _ in range(50):
        code = issue_credential().code
        assert set(code) <= set(CODE_ALPHABET)
        assert not (set("ILOU01") & set(code))


def test_codes_match_regardless_of_case_or_separators():
    credential = issue_credential()
    messy = f" {credential.code[:4].lower()}-{credential.code[4:].lower()} "
    assert matches_code(messy, credential.code_hash)
    assert normalise_code(messy) == credential.code


def test_a_wrong_value_never_matches():
    credential = issue_credential()
    assert not matches_token("nonsense", credential.token_hash)
    assert not matches_code("AAAAAAAA", credential.code_hash)
    assert not matches_token("", credential.token_hash)
    assert not matches_token(credential.token, "")


def test_hashing_is_stable():
    assert hash_code("abc-def") == hash_code("ABCDEF")


# ------------------------------------------------------------------------ purchase


def _order(pool_id="pool_1", offer=None, units=20, cases=2, total=12_000):
    return PurchaseOrder(
        pool_id=pool_id, supplier_id="sup_test", offer=offer, units=units,
        cases=cases, total_cents=total,
    )


def test_a_simulated_purchase_is_labelled_simulated(bulk_offer):
    result = SimulatedPurchaseExecutor().execute(_order(offer=bulk_offer))
    assert result.ok
    assert result.simulated is True
    assert result.supplier_reference.startswith("SIMULATED-")


def test_the_same_order_produces_the_same_reference(bulk_offer):
    """A retry must not look like a second purchase."""
    executor = SimulatedPurchaseExecutor()
    first = executor.execute(_order(offer=bulk_offer))
    second = executor.execute(_order(offer=bulk_offer))
    assert first.supplier_reference == second.supplier_reference


def test_an_empty_order_is_rejected(bulk_offer):
    with pytest.raises(PurchaseError):
        SimulatedPurchaseExecutor().execute(_order(offer=bulk_offer, units=0, cases=0))


def test_purchase_failure_is_reported_not_retried_forever(bulk_offer):
    result = SimulatedPurchaseExecutor().execute(
        _order(pool_id=f"pool_{PURCHASE_FAILURE_MARKER}", offer=bulk_offer)
    )
    assert result.ok is False
    assert "operator review" in result.failure_reason


def test_only_the_simulated_executor_exists_in_this_build():
    assert build_purchase_executor("simulated").simulated is True
    with pytest.raises(ValueError):
        build_purchase_executor("operator")


# ------------------------------------------------------------------- end-to-end fixture


def _world(ctx, *, units=(2, 3), status=PoolStatus.PURCHASE_READY, bulk_offer=None):
    """A minimal captured pool with a host and locked buyers, ready to fulfil."""
    ctx.repo.put_product(
        WS, Product("p_protein", "Protein", "nutrition", "tub", "protein",
                    unit_weight_grams=2000)
    )
    ctx.repo.put_offer(WS, bulk_offer)
    ctx.repo.put_site(
        WS, PickupSite("s_union", "Union", COMM, 38.6488, -90.3108, True,
                       "campus_common", PickupPermission.DEMO)
    )
    pool = Pool(
        id="pool_1", community_id=COMM, product_id="p_protein", offer_id=bulk_offer.id,
        pickup_site_id="s_union", status=status, threshold_units=sum(units),
        timing=PoolTiming(
            distribution_starts_at=iso(utcnow()), distribution_ends_at=iso(utcnow())
        ),
    )
    ctx.repo.put_pool(WS, pool)
    for i, qty in enumerate(units):
        hid = f"m{i}"
        ctx.repo.put_household(WS, make_member(hid))
        ctx.repo.put_membership(
            WS,
            Membership(
                pool_id=pool.id, household_id=hid, need_id=f"n{i}", requested_units=qty,
                allocated_units=qty, state=ParticipationState.LOCKED,
                path=AutonomyPath.SMART_JOIN, final_cost_cents=1000 * qty,
            ),
        )
    ctx.repo.put_household(WS, make_member("host"))
    ctx.repo.put_host_assignment(
        WS,
        HostAssignment(
            pool_id=pool.id, household_id="host", role=FulfillerRole.FULFILLER,
            pickup_site_id="s_union", supplier_distance_km=8.0,
            handled_orders=len(units), handled_units=sum(units), estimated_weight_kg=20,
            reward_total_cents=5000, reward_earned_cents=4500, reward_contingent_cents=500,
        ),
    )
    return pool


def _fulfil_to_distribution(ctx, bulk_offer):
    pool = _world(ctx, bulk_offer=bulk_offer)
    fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    fulfillment.open_distribution(ctx=ctx, pool_id=pool.id)
    return pool


def test_purchase_creates_provenance_and_allocations(ctx, bulk_offer):
    pool = _world(ctx, bulk_offer=bulk_offer)
    result = fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    assert result["purchased"] and result["simulated"]
    record = ctx.repo.get_purchase_for_pool(WS, pool.id)
    assert record.simulated is True
    assert record.offer_snapshot["id"] == bulk_offer.id
    assert record.supplier_reference
    assert len(ctx.repo.list_allocations(WS, pool.id)) == 2
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.PURCHASED


def test_purchasing_twice_does_not_order_twice(ctx, bulk_offer):
    pool = _world(ctx, bulk_offer=bulk_offer)
    fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    again = fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    assert again["already_purchased"] is True
    assert len(ctx.repo.list_purchases(WS)) == 1


def test_an_unlocked_pool_cannot_be_purchased(ctx, bulk_offer):
    pool = _world(ctx, status=PoolStatus.FUNDING, bulk_offer=bulk_offer)
    with pytest.raises(fulfillment.FulfillmentError):
        fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)


def test_opening_distribution_pays_the_hosts_earned_component(ctx, bulk_offer):
    """The run is earned once the goods are collected and held, before any pickup (§38)."""
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    assignment = ctx.repo.get_host_assignment(WS, pool.id)
    assert assignment.reward_paid_cents == assignment.reward_earned_cents
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.DISTRIBUTING
    assert all(
        a.state == AllocationState.READY_FOR_PICKUP
        for a in ctx.repo.list_allocations(WS, pool.id)
    )


def test_distribution_needs_an_assigned_fulfiller(ctx, bulk_offer):
    pool = _world(ctx, bulk_offer=bulk_offer)
    fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    ctx.repo.store(WS).host_assignments.clear()
    with pytest.raises(fulfillment.FulfillmentError):
        fulfillment.open_distribution(ctx=ctx, pool_id=pool.id)


# -------------------------------------------------------------------------- pickup


def test_a_valid_credential_completes_one_handoff(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    assert result.ok
    assert result.household_id == "m0"
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state == AllocationState.PICKED_UP


def test_the_short_code_works_when_scanning_is_awkward(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    result = fulfillment.redeem_pickup(
        ctx=ctx, pool_id=pool.id, presented=credential.code, is_code=True
    )
    assert result.ok


def test_a_credential_cannot_be_used_twice(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    replay = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    assert replay.ok is False
    assert "already been used" in replay.reason


def test_an_unknown_credential_is_rejected(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    result = fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented="made-up")
    assert result.ok is False
    assert "unrecognised" in result.reason


def test_a_credential_from_another_pool_is_rejected_with_a_distinct_reason(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    result = fulfillment.redeem_pickup(
        ctx=ctx, pool_id="pool_other", presented=credential.token
    )
    assert result.ok is False
    assert "different pool" in result.reason


def test_re_issuing_invalidates_the_previous_credential(ctx, bulk_offer):
    """A screenshot shared before a re-issue must be worthless (§70)."""
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    first = fulfillment.issue_pickup_credential(ctx=ctx, pool_id=pool.id, household_id="m0")
    second = fulfillment.issue_pickup_credential(ctx=ctx, pool_id=pool.id, household_id="m0")
    assert second.replaced_previous is True
    assert fulfillment.redeem_pickup(
        ctx=ctx, pool_id=pool.id, presented=first.token
    ).ok is False
    assert fulfillment.redeem_pickup(
        ctx=ctx, pool_id=pool.id, presented=second.token
    ).ok is True


def test_a_collected_allocation_cannot_be_re_credentialled(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    with pytest.raises(fulfillment.FulfillmentError):
        fulfillment.issue_pickup_credential(ctx=ctx, pool_id=pool.id, household_id="m0")


def test_a_member_with_no_allocation_gets_no_credential(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    with pytest.raises(fulfillment.FulfillmentError):
        fulfillment.issue_pickup_credential(
            ctx=ctx, pool_id=pool.id, household_id="a_stranger"
        )


def test_the_host_cannot_complete_orders_without_credentials(ctx, bulk_offer):
    """There is no route from "I am the host" to "everyone collected" (§76)."""
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    assert not hasattr(fulfillment, "mark_all_picked_up")
    # The only completion paths are credential redemption and an audited override.
    assert fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented="m0").ok is False


def test_completing_every_allocation_completes_the_pool(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    for hid in ("m0", "m1"):
        credential = fulfillment.issue_pickup_credential(
            ctx=ctx, pool_id=pool.id, household_id=hid
        )
        assert fulfillment.redeem_pickup(
            ctx=ctx, pool_id=pool.id, presented=credential.token
        ).ok
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.COMPLETED


# ---------------------------------------------------------------------- no-show


def test_closing_the_window_marks_uncollected_orders_as_no_shows(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    result = fulfillment.close_pickup_window(ctx=ctx, pool_id=pool.id)
    assert result["no_shows"] == ["m1"]
    assert ctx.repo.get_allocation(WS, pool.id, "m1").state == AllocationState.NO_SHOW


def test_a_no_show_does_not_erase_the_hosts_earned_pay(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    fulfillment.close_pickup_window(ctx=ctx, pool_id=pool.id)
    assignment = ctx.repo.get_host_assignment(WS, pool.id)
    assert assignment.reward_paid_cents >= assignment.reward_earned_cents
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.COMPLETED


def test_the_handoff_bonus_scales_with_verified_pickups(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    fulfillment.redeem_pickup(ctx=ctx, pool_id=pool.id, presented=credential.token)
    fulfillment.close_pickup_window(ctx=ctx, pool_id=pool.id)
    assignment = ctx.repo.get_host_assignment(WS, pool.id)
    # One of two collected: earned in full, half the contingent component.
    assert assignment.reward_paid_cents == (
        assignment.reward_earned_cents + assignment.reward_contingent_cents // 2
    )


# --------------------------------------------------------------------- override


def test_an_operator_override_requires_a_reason(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    with pytest.raises(fulfillment.FulfillmentError):
        fulfillment.operator_override_pickup(
            ctx=ctx, pool_id=pool.id, household_id="m0", reason="  "
        )


def test_an_override_is_audited_and_preserves_the_previous_state(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    result = fulfillment.operator_override_pickup(
        ctx=ctx, pool_id=pool.id, household_id="m0", reason="collected in person, phone dead"
    )
    assert result["previous_state"] == "ready_for_pickup"
    allocation = ctx.repo.get_allocation(WS, pool.id, "m0")
    assert allocation.picked_up_via == "operator_override"
    assert allocation.override_reason
    events = [e for e in ctx.repo.list_activity(WS) if e.kind == "pickup_override"]
    assert events and events[0].facts["reason"]


def test_an_override_revokes_any_outstanding_credential(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    credential = fulfillment.issue_pickup_credential(
        ctx=ctx, pool_id=pool.id, household_id="m0"
    )
    fulfillment.operator_override_pickup(
        ctx=ctx, pool_id=pool.id, household_id="m0", reason="handed over at the desk"
    )
    assert fulfillment.redeem_pickup(
        ctx=ctx, pool_id=pool.id, presented=credential.token
    ).ok is False


# ---------------------------------------------------------------------- checklist


def test_the_checklist_shows_progress_and_no_contact_details(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    checklist = fulfillment.host_checklist(ctx=ctx, pool_id=pool.id)
    assert checklist["total"] == 2
    assert checklist["picked_up"] == 0
    serialized = str(checklist)
    assert "@" not in serialized  # no email address anywhere in the host's view
    assert checklist["earnings"]["total_cents"] == 5000


# ------------------------------------------------------------------------- issues


def test_an_issue_routes_to_operator_review_not_to_the_host(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    issue = fulfillment.open_issue(
        ctx=ctx, pool_id=pool.id, household_id="m0",
        kind=IssueKind.DAMAGED_ITEM, detail="seal broken",
    )
    assert issue.state == IssueState.OPEN
    assert ctx.repo.get_allocation(WS, pool.id, "m0").state == AllocationState.ISSUE_REVIEW


def test_an_issue_can_be_resolved(ctx, bulk_offer):
    pool = _fulfil_to_distribution(ctx, bulk_offer)
    issue = fulfillment.open_issue(
        ctx=ctx, pool_id=pool.id, household_id="m0", kind=IssueKind.WRONG_ITEM
    )
    resolved = fulfillment.resolve_issue(
        ctx=ctx, issue_id=issue.id, resolution="replacement arranged"
    )
    assert resolved.state == IssueState.RESOLVED
    assert resolved.resolved_at


def test_a_purchase_failure_opens_a_supplier_issue(ctx, bulk_offer):
    """A supplier that cannot fill the order becomes an operator case, not a retry loop."""
    pool = _world(ctx, bulk_offer=bulk_offer)
    ctx.repo.store(WS).pools.clear()
    ctx.repo.store(WS).memberships.clear()
    pool.id = f"pool_{PURCHASE_FAILURE_MARKER}"
    ctx.repo.put_pool(WS, pool)
    ctx.repo.put_membership(
        WS,
        Membership(
            pool_id=pool.id, household_id="m0", need_id="n0", requested_units=2,
            allocated_units=2, state=ParticipationState.LOCKED,
            path=AutonomyPath.SMART_JOIN, final_cost_cents=2000,
        ),
    )
    result = fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    assert result["purchased"] is False
    assert any(i.kind == IssueKind.SUPPLIER_FAILURE for i in ctx.repo.list_issues(WS))
