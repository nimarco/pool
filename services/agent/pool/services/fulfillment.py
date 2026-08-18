"""Purchase execution and physical fulfilment (§63–§76).

This is the half of the product that actually puts a sealed tub of protein powder in
someone's hands, and it is where a group-buying system usually becomes a mess of
messages and trust.

Design decisions worth naming:

* **The host never fronts the purchase** (§63). Buyers' captured funds cover the order,
  and a ``PurchaseExecutor`` places it. This build uses the simulated executor, and
  every record it writes is explicitly flagged synthetic (§65).
* **Pickup is proved, not asserted** (§76). A host cannot mark everyone collected to
  inflate their own compensation: each allocation needs its buyer's one-time
  credential, or an audited operator override with a stated reason (§72).
* **A no-show does not erase the host's work** (§38). The run compensation is earned
  once the goods are collected, transported, and held; only the handoff bonus depends
  on verified pickups.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..adapters.purchase import PurchaseOrder
from ..domain.economics import allocate_packages
from ..domain.models import (
    AllocationState,
    FulfillmentRun,
    IssueCase,
    IssueKind,
    IssueState,
    ParticipationState,
    PickupAllocation,
    PickupToken,
    Pool,
    PoolStatus,
    PurchaseRecord,
    iso,
    new_id,
)
from ..domain.money import format_cents
from ..domain.pickup import IssuedCredential, issue_credential, matches_code, matches_token
from ..domain.state import assert_transition
from .context import CoordinationError, PoolContext


class FulfillmentError(RuntimeError):
    """A fulfilment step could not be completed."""


#: Pool statuses in which a handoff can legitimately occur — the goods are with the
#: host. ``COMPLETED`` is included because the secondary window outlives settlement: a
#: no-show who collects late is the case :func:`close_pickup_window` exists to allow,
#: and the allocation-state gate below still decides whether *that* order may be
#: collected.
PICKUP_OPEN_STATUSES = frozenset({PoolStatus.DISTRIBUTING, PoolStatus.COMPLETED})

#: Allocation states a credential may be issued or honoured against. A no-show is
#: collectible because the secondary window is a designed behaviour (§74); an order
#: under issue review is not, because a human is deciding what happened to it.
COLLECTIBLE_ALLOCATION_STATES = frozenset(
    {
        AllocationState.READY_FOR_PICKUP,
        AllocationState.NO_SHOW,
        AllocationState.SECONDARY_PICKUP,
    }
)


def _require_pickup_open(ctx: PoolContext, pool_id: str) -> Pool:
    """The lifecycle gate on every credential operation.

    Pickup proves a physical handoff, so it cannot precede one. Until
    :func:`open_distribution` runs, the host has not collected the goods and there is
    nothing to hand anybody.
    """
    pool = _require_pool(ctx, pool_id)
    if pool.status not in PICKUP_OPEN_STATUSES:
        raise FulfillmentError(
            "pickup has not opened for this pool yet "
            f"(it is {pool.status.value}, not distributing)"
        )
    return pool


# --------------------------------------------------------------------------- purchase


def execute_purchase(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """Place the bulk order for a purchase-ready pool.

    Idempotent: a pool that already has a purchase record returns it rather than
    ordering twice. A failure is bounded and routed to operator review rather than
    retried in a loop (§19).
    """
    pool = _require_pool(ctx, pool_id)
    if pool.status not in {PoolStatus.PURCHASE_READY, PoolStatus.PURCHASED}:
        raise FulfillmentError(
            f"a pool in state {pool.status.value} is not ready to purchase; payments "
            "must be captured first"
        )

    existing = ctx.repo.get_purchase_for_pool(ctx.ws, pool_id)
    if existing is not None:
        # Same shape as a fresh purchase, so a caller cannot accidentally treat an
        # idempotent no-op as a different kind of result.
        return {
            "pool_id": pool_id,
            "purchased": True,
            "already_purchased": True,
            "purchase_id": existing.id,
            "simulated": existing.simulated,
            "supplier_reference": existing.supplier_reference,
            "units": existing.units_purchased,
            "cases": existing.cases_purchased,
        }

    offer = ctx.repo.get_offer(ctx.ws, pool.offer_id)
    if offer is None:
        raise CoordinationError("pool references a missing offer")
    members = [
        m for m in ctx.repo.list_memberships(ctx.ws, pool_id)
        if m.state == ParticipationState.LOCKED
    ]
    units = sum(m.allocated_units for m in members)
    packages = allocate_packages(offer, units)

    result = ctx.purchaser.execute(
        PurchaseOrder(
            pool_id=pool_id,
            supplier_id=offer.supplier_id,
            offer=offer,
            units=units,
            cases=packages.cases,
            total_cents=packages.cases * offer.case_price_cents,
        )
    )
    if not result.ok:
        ctx.log(
            "purchase_failed",
            f"Supplier purchase failed: {result.failure_reason}",
            {"executor": result.executor},
            pool_id=pool_id,
        )
        _open_issue(
            ctx, pool_id, "", IssueKind.SUPPLIER_FAILURE,
            f"purchase execution failed: {result.failure_reason}",
        )
        return {"pool_id": pool_id, "purchased": False, "reason": result.failure_reason}

    record = PurchaseRecord(
        id=new_id("buy"),
        pool_id=pool_id,
        supplier_id=offer.supplier_id,
        offer_snapshot=offer.to_dict(),
        units_purchased=packages.units_purchased,
        cases_purchased=packages.cases,
        total_cents=packages.cases * offer.case_price_cents,
        supplier_reference=result.supplier_reference,
        executed_at=result.executed_at,
        executor=result.executor,
        simulated=result.simulated,
        receipt_reference=result.receipt_reference,
        lot_reference=result.lot_reference,
    )
    ctx.repo.put_purchase(ctx.ws, record)

    pool.status = assert_transition(pool.status, PoolStatus.PURCHASED)
    ctx.repo.put_pool(ctx.ws, pool)

    for m in members:
        ctx.repo.put_allocation(
            ctx.ws,
            PickupAllocation(
                pool_id=pool_id,
                household_id=m.household_id,
                units=m.allocated_units,
                state=AllocationState.PENDING_PURCHASE,
            ),
        )

    ctx.log(
        "purchase_executed",
        f"Bulk order placed for {packages.cases} case(s) "
        f"({packages.units_purchased} units) — SIMULATED"
        if record.simulated
        else f"Bulk order placed for {packages.cases} case(s)",
        {
            "units": packages.units_purchased,
            "cases": packages.cases,
            "total_cents": record.total_cents,
            "supplier_reference": record.supplier_reference,
            "simulated": record.simulated,
            "executor": record.executor,
        },
        pool_id=pool_id,
    )
    return {
        "pool_id": pool_id,
        "purchased": True,
        "purchase_id": record.id,
        "simulated": record.simulated,
        "supplier_reference": record.supplier_reference,
        "units": packages.units_purchased,
        "cases": packages.cases,
    }


# ------------------------------------------------------------------------ dispatch


def open_distribution(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """Create the fulfilment run and make every allocation ready for pickup."""
    pool = _require_pool(ctx, pool_id)
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if assignment is None:
        raise FulfillmentError("a pool cannot be distributed without an assigned fulfiller")
    if pool.status == PoolStatus.DISTRIBUTING:
        return {"pool_id": pool_id, "distributing": True, "already_open": True}
    if pool.status == PoolStatus.COMPLETED:
        # Distribution already happened *and* finished. Saying so is more useful than
        # either pretending the window reopened or letting `assert_transition` raise —
        # this is a public route, and clicking it twice on a finished pool used to
        # return a 500.
        raise FulfillmentError("this pool has already finished distributing")

    run = FulfillmentRun(
        id=new_id("run"),
        community_id=pool.community_id,
        # v1: one run holds exactly one pool. The list shape is what makes batching
        # several pools into one trip a later optimisation rather than a migration (§66).
        pool_ids=[pool_id],
        fulfiller_household_id=assignment.household_id,
        pickup_site_id=assignment.pickup_site_id,
        starts_at=pool.timing.distribution_starts_at,
        ends_at=pool.timing.distribution_ends_at,
        state="distributing",
    )
    ctx.repo.put_fulfillment_run(ctx.ws, run)

    ready = 0
    for allocation in ctx.repo.list_allocations(ctx.ws, pool_id):
        if allocation.state == AllocationState.PENDING_PURCHASE:
            allocation.state = AllocationState.READY_FOR_PICKUP
            ctx.repo.put_allocation(ctx.ws, allocation)
            ready += 1

    pool.status = assert_transition(pool.status, PoolStatus.DISTRIBUTING)
    ctx.repo.put_pool(ctx.ws, pool)

    # The host's run compensation is earned at this point: the goods have been
    # collected, transported, and are being held for buyers (§38).
    assignment.reward_paid_cents = assignment.reward_earned_cents
    ctx.repo.put_host_assignment(ctx.ws, assignment)

    ctx.log(
        "distribution_opened",
        f"Pickup is open — {ready} order(s) ready to collect",
        {
            "run_id": run.id,
            "ready_allocations": ready,
            "starts_at": run.starts_at,
            "ends_at": run.ends_at,
            "host_earned_cents": assignment.reward_earned_cents,
        },
        pool_id=pool_id,
    )
    return {
        "pool_id": pool_id, "distributing": True, "run_id": run.id,
        "ready_allocations": ready,
    }


# --------------------------------------------------------------------------- pickup


@dataclass
class IssuedPickupCredential:
    """Returned once, to the owning buyer. The plaintext is never stored (§70)."""

    pool_id: str
    household_id: str
    token: str
    code: str
    replaced_previous: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "household_id": self.household_id,
            "token": self.token,
            "code": self.code,
            "replaced_previous": self.replaced_previous,
        }


def issue_pickup_credential(
    *, ctx: PoolContext, pool_id: str, household_id: str
) -> IssuedPickupCredential:
    """Mint a one-time pickup credential for one buyer's allocation.

    Re-issuing invalidates the previous pair, so a screenshot shared before a re-issue
    is worthless.

    **Only once the pool is actually distributing.** A credential is the proof that a
    handoff happened (canonical invariant 9), so one that exists before there is
    anything to hand over proves nothing. Allocations are written by
    :func:`execute_purchase`, which means the gap between ``PURCHASED`` and
    ``DISTRIBUTING`` was a real window in which a buyer's order could be marked
    collected while the goods were still at the supplier — the state check was on the
    allocation alone, and never on the lifecycle (#audit P2).
    """
    _require_pickup_open(ctx, pool_id)
    allocation = ctx.repo.get_allocation(ctx.ws, pool_id, household_id)
    if allocation is None:
        raise FulfillmentError("this member has no allocation in this pool")
    if allocation.state == AllocationState.PICKED_UP:
        raise FulfillmentError("this allocation has already been collected")
    if allocation.state not in COLLECTIBLE_ALLOCATION_STATES:
        raise FulfillmentError(
            f"this order is not ready to collect ({allocation.state.value})"
        )

    previous = ctx.repo.get_pickup_token(ctx.ws, pool_id, household_id)
    credential: IssuedCredential = issue_credential()
    ctx.repo.put_pickup_token(
        ctx.ws,
        PickupToken(
            id=new_id("tok"),
            pool_id=pool_id,
            household_id=household_id,
            token_hash=credential.token_hash,
            code_hash=credential.code_hash,
            issued_at=iso(ctx.now),
        ),
    )
    return IssuedPickupCredential(
        pool_id=pool_id,
        household_id=household_id,
        token=credential.token,
        code=credential.code,
        replaced_previous=previous is not None,
    )


@dataclass
class RedemptionResult:
    ok: bool
    reason: str = ""
    pool_id: str = ""
    household_id: str = ""
    units: int = 0
    picked_up_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "pool_id": self.pool_id,
            "household_id": self.household_id,
            "units": self.units,
            "picked_up_at": self.picked_up_at,
        }


def redeem_pickup(
    *, ctx: PoolContext, pool_id: str, presented: str, is_code: bool = False
) -> RedemptionResult:
    """Verify a presented credential and complete one handoff.

    Every failure path is explicit and audited: a credential from another pool, an
    unknown value, a second scan of the same credential, a revoked one, and one
    presented before the pool is distributing all fail with a distinct reason. Nothing
    is looked up by buyer id — the credential itself identifies the allocation, so a
    host cannot complete an order without one.

    The lifecycle check is repeated here rather than trusted to issuance. A credential
    minted legitimately and presented after the window is a different event from one
    that should never have existed, and the gate that matters is the one at the moment
    of the handoff.
    """
    tokens = ctx.repo.list_pickup_tokens(ctx.ws, pool_id)
    matcher = matches_code if is_code else matches_token
    stored_attr = "code_hash" if is_code else "token_hash"

    match = next(
        (t for t in tokens if matcher(presented, getattr(t, stored_attr))), None
    )
    if match is None:
        # Check whether it belongs to a *different* pool, so the audit trail can tell a
        # wrong-pool scan apart from a forged value.
        elsewhere = next(
            (
                t
                for t in ctx.repo.list_pickup_tokens(ctx.ws)
                if matcher(presented, getattr(t, stored_attr))
            ),
            None,
        )
        reason = (
            "this credential belongs to a different pool"
            if elsewhere is not None
            else "unrecognised pickup credential"
        )
        ctx.log("pickup_rejected", f"Pickup rejected: {reason}", {}, pool_id=pool_id)
        return RedemptionResult(False, reason, pool_id)

    if match.revoked:
        ctx.log(
            "pickup_rejected", "Pickup rejected: credential was replaced by a newer one",
            {}, pool_id=pool_id, household_id=match.household_id,
        )
        return RedemptionResult(
            False, "this credential was replaced by a newer one", pool_id, match.household_id
        )
    if match.redeemed_at:
        ctx.log(
            "pickup_rejected", "Pickup rejected: credential has already been used",
            {"redeemed_at": match.redeemed_at}, pool_id=pool_id, household_id=match.household_id,
        )
        return RedemptionResult(
            False, "this credential has already been used", pool_id, match.household_id
        )

    # The lifecycle gate sits *after* the credential is identified, so a wrong-pool or
    # forged scan still gets its own distinct reason — the audit trail should say what
    # was actually presented, not merely that the window was shut.
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None or pool.status not in PICKUP_OPEN_STATUSES:
        reason = "pickup has not opened for this pool yet"
        ctx.log(
            "pickup_rejected",
            f"Pickup rejected: {reason}",
            {"pool_status": pool.status.value if pool else "unknown"},
            pool_id=pool_id,
            household_id=match.household_id,
        )
        return RedemptionResult(False, reason, pool_id, match.household_id)

    allocation = ctx.repo.get_allocation(ctx.ws, pool_id, match.household_id)
    if allocation is None:
        return RedemptionResult(False, "no allocation for this credential", pool_id)
    if allocation.state == AllocationState.PICKED_UP:
        return RedemptionResult(
            False, "this allocation has already been collected", pool_id, match.household_id
        )
    if allocation.state not in COLLECTIBLE_ALLOCATION_STATES:
        reason = f"this order is not ready to collect ({allocation.state.value})"
        ctx.log(
            "pickup_rejected",
            f"Pickup rejected: {reason}",
            {"allocation_state": allocation.state.value},
            pool_id=pool_id,
            household_id=match.household_id,
        )
        return RedemptionResult(False, reason, pool_id, match.household_id)

    now = iso(ctx.now)
    # Claim the credential *before* touching the allocation, with a conditional write.
    # The `redeemed_at` check above is a read, so two scans of one QR code arriving
    # together both saw it empty and both completed the handoff. Whoever wins the
    # condition here is the only one who proceeds; the loser is told the same thing a
    # sequential replay is told, because it is the same thing.
    if not ctx.repo.claim_pickup_redemption(
        ctx.ws, pool_id, match.household_id, now
    ):
        ctx.log(
            "pickup_rejected", "Pickup rejected: credential has already been used",
            {"concurrent": True}, pool_id=pool_id, household_id=match.household_id,
        )
        return RedemptionResult(
            False, "this credential has already been used", pool_id, match.household_id
        )
    match.redeemed_at = now
    allocation.state = AllocationState.PICKED_UP
    allocation.picked_up_at = now
    allocation.picked_up_via = "code" if is_code else "qr"
    ctx.repo.put_allocation(ctx.ws, allocation)

    ctx.log(
        "pickup_completed",
        f"Handoff confirmed for {allocation.units} unit(s) via "
        f"{'short code' if is_code else 'QR'}",
        {"units": allocation.units, "via": allocation.picked_up_via},
        pool_id=pool_id,
        household_id=match.household_id,
    )
    _settle_if_complete(ctx, pool_id)
    return RedemptionResult(
        True, "handoff confirmed", pool_id, match.household_id, allocation.units, now
    )


def operator_override_pickup(
    *, ctx: PoolContext, pool_id: str, household_id: str, reason: str
) -> dict[str, Any]:
    """Mark an allocation collected without a credential. Restricted and audited (§72).

    A reason is mandatory, the original state is preserved in the event record, and the
    override is recorded as an override rather than rewriting history to look like a
    normal scan. A normal host has no route to this function — it is exposed only on
    the operator surface.
    """
    if not reason or not reason.strip():
        raise FulfillmentError("an operator override requires an explicit reason")
    allocation = ctx.repo.get_allocation(ctx.ws, pool_id, household_id)
    if allocation is None:
        raise FulfillmentError("this member has no allocation in this pool")

    previous = allocation.state
    allocation.state = AllocationState.PICKED_UP
    allocation.picked_up_at = iso(ctx.now)
    allocation.picked_up_via = "operator_override"
    allocation.override_reason = reason.strip()
    ctx.repo.put_allocation(ctx.ws, allocation)

    token = ctx.repo.get_pickup_token(ctx.ws, pool_id, household_id)
    if token is not None and not token.redeemed_at:
        token.revoked = True
        ctx.repo.put_pickup_token(ctx.ws, token)

    ctx.log(
        "pickup_override",
        "Operator marked an order collected without a credential",
        {"previous_state": previous.value, "reason": reason.strip()},
        pool_id=pool_id,
        household_id=household_id,
    )
    _settle_if_complete(ctx, pool_id)
    return {
        "pool_id": pool_id, "household_id": household_id, "state": allocation.state.value,
        "previous_state": previous.value, "reason": reason.strip(),
    }


def close_pickup_window(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """End the primary window: anything uncollected becomes a no-show (§74)."""
    no_shows: list[str] = []
    for allocation in ctx.repo.list_allocations(ctx.ws, pool_id):
        if allocation.state == AllocationState.READY_FOR_PICKUP:
            allocation.state = AllocationState.NO_SHOW
            ctx.repo.put_allocation(ctx.ws, allocation)
            no_shows.append(allocation.household_id)
    if no_shows:
        ctx.log(
            "pickup_window_closed",
            f"{len(no_shows)} order(s) were not collected — offering a secondary window",
            {"no_shows": len(no_shows)},
            pool_id=pool_id,
        )
    _settle_if_complete(ctx, pool_id)
    return {"pool_id": pool_id, "no_shows": no_shows}


def host_checklist(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """The host's live fulfilment view (§71). Read-only, and shows no contact details."""
    pool = _require_pool(ctx, pool_id)
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    allocations = ctx.repo.list_allocations(ctx.ws, pool_id)
    households = {h.id: h for h in ctx.repo.list_households(ctx.ws)}

    return {
        "pool_id": pool_id,
        "product_name": product.name if product else pool.product_id,
        "status": pool.status.value,
        "picked_up": sum(1 for a in allocations if a.state == AllocationState.PICKED_UP),
        "total": len(allocations),
        "units_total": sum(a.units for a in allocations),
        "distribution_starts_at": pool.timing.distribution_starts_at,
        "distribution_ends_at": pool.timing.distribution_ends_at,
        "earnings": _earnings_view(assignment),
        "orders": [
            {
                # A display name and nothing else: no phone, no email, no address (§82).
                "household_id": a.household_id,
                "display_name": (
                    households[a.household_id].display_name
                    if a.household_id in households
                    else a.household_id
                ),
                "units": a.units,
                "state": a.state.value,
                "picked_up_at": a.picked_up_at,
                "via": a.picked_up_via,
            }
            for a in allocations
        ],
    }


def _earnings_view(assignment) -> dict[str, Any]:
    if assignment is None:
        return {}
    return {
        "total_cents": assignment.reward_total_cents,
        "total_display": format_cents(assignment.reward_total_cents),
        "earned_cents": assignment.reward_earned_cents,
        "contingent_cents": assignment.reward_contingent_cents,
        "paid_cents": assignment.reward_paid_cents,
        "breakdown": assignment.reward_breakdown,
        "handled_orders": assignment.handled_orders,
        "note": "Run compensation is earned on completed fulfilment; only the handoff "
                "bonus depends on verified pickups.",
    }


# --------------------------------------------------------------------------- issues


def open_issue(
    *,
    ctx: PoolContext,
    pool_id: str,
    household_id: str,
    kind: IssueKind,
    detail: str = "",
) -> IssueCase:
    """Record a product or fulfilment issue for operator review (§75).

    The host's ordinary responsibility ends after correct handoff of the correct sealed
    item; a manufacturer defect is not theirs to adjudicate at a pickup table.
    """
    return _open_issue(ctx, pool_id, household_id, kind, detail)


def resolve_issue(*, ctx: PoolContext, issue_id: str, resolution: str) -> IssueCase:
    issue = ctx.repo.get_issue(ctx.ws, issue_id)
    if issue is None:
        raise FulfillmentError(f"unknown issue: {issue_id}")
    issue.state = IssueState.RESOLVED
    issue.resolution = resolution
    issue.resolved_at = iso(ctx.now)
    ctx.repo.put_issue(ctx.ws, issue)
    ctx.log(
        "issue_resolved", "An issue case was resolved", {"issue_id": issue_id},
        pool_id=issue.pool_id, household_id=issue.household_id or None,
    )
    return issue


def _open_issue(
    ctx: PoolContext, pool_id: str, household_id: str, kind: IssueKind, detail: str
) -> IssueCase:
    issue = IssueCase(
        id=new_id("iss"),
        pool_id=pool_id,
        household_id=household_id,
        kind=kind,
        state=IssueState.OPEN,
        detail=detail,
    )
    ctx.repo.put_issue(ctx.ws, issue)
    allocation = (
        ctx.repo.get_allocation(ctx.ws, pool_id, household_id) if household_id else None
    )
    if allocation is not None and allocation.state != AllocationState.PICKED_UP:
        allocation.state = AllocationState.ISSUE_REVIEW
        ctx.repo.put_allocation(ctx.ws, allocation)
    ctx.log(
        "issue_opened",
        f"Issue raised: {kind.value.replace('_', ' ')}",
        {"issue_id": issue.id, "kind": kind.value},
        pool_id=pool_id,
        household_id=household_id or None,
    )
    return issue


# --------------------------------------------------------------------------- internals


def _settle_if_complete(ctx: PoolContext, pool_id: str) -> None:
    """Complete the pool once every allocation has reached a settled state."""
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None or pool.status != PoolStatus.DISTRIBUTING:
        return
    allocations = ctx.repo.list_allocations(ctx.ws, pool_id)
    if not allocations:
        return
    unsettled = {AllocationState.PENDING_PURCHASE, AllocationState.READY_FOR_PICKUP}
    if any(a.state in unsettled for a in allocations):
        return

    picked_up = sum(1 for a in allocations if a.state == AllocationState.PICKED_UP)
    pool.status = assert_transition(pool.status, PoolStatus.COMPLETED)
    ctx.repo.put_pool(ctx.ws, pool)

    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if assignment is not None:
        # The contingent handoff component is paid in proportion to verified pickups —
        # the host keeps everything they earned by doing the run (§38).
        share = (
            assignment.reward_contingent_cents * picked_up // len(allocations)
            if allocations
            else 0
        )
        assignment.reward_paid_cents = assignment.reward_earned_cents + share
        ctx.repo.put_host_assignment(ctx.ws, assignment)

    ctx.log(
        "pool_completed",
        f"Pool completed — {picked_up}/{len(allocations)} orders collected",
        {
            "picked_up": picked_up,
            "total": len(allocations),
            "host_paid_cents": assignment.reward_paid_cents if assignment else 0,
        },
        pool_id=pool_id,
    )


def _require_pool(ctx: PoolContext, pool_id: str) -> Pool:
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")
    return pool
