"""The showcase scenario, as executable code.

This drives the *real* path end to end: real agent runs, real tools, real economics,
real host ranking, real policy evaluation, real payment provider, real state machine,
real pickup credentials. The only things the scenario supplies are the situation and
the human answers — a seeded community, a member volunteering to host, buyers replying
to their Decision Inbox — which is legitimate scripting of inputs.

Nothing about the outcome is predetermined. If the arithmetic stopped clearing the
supplier minimum, if the case maths stopped landing on a boundary, or if no host
qualified, this scenario would report failure rather than pretend (AGENTS.md §8).

Used by ``make demo`` and by the UI's "Run full scenario" action, so the demo a judge
watches is the same code the tests assert on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from ..adapters.repository import Repository
from ..adapters.routing import RoutingService
from ..agent.coordinator import PoolCoordinator
from ..config import Settings
from ..data.seed import COMMUNITY_ID, CONSUMER_HOUSEHOLD, seed
from ..domain.models import (
    AllocationState,
    DecisionKind,
    DecisionState,
    HostProfile,
    ParticipationState,
    PaymentState,
    PoolStatus,
    iso,
    parse_iso,
    utcnow,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.timing import evaluate_timing
from . import communication, fulfillment, hosting
from . import coordination as coord
from . import needs as needs_service
from . import payments as payment_service
from .context import PoolContext

#: The member who offers to host from inside the pool (§27, second source of hosts).
VOLUNTEER_HOST = "hh_thibault"

@dataclass
class Step:
    name: str
    detail: str
    facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "detail": self.detail, "facts": self.facts}


@dataclass
class ScenarioResult:
    ok: bool
    steps: list[Step]
    failure: str = ""
    pool_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "failure": self.failure,
            "pool_id": self.pool_id,
            "steps": [s.to_dict() for s in self.steps],
        }


#: The account a visitor acts as, and the declaration she makes for herself.
#:
#: These are the numbers a person would type into the form: two tubs, restocked roughly
#: every six weeks, needed in a fortnight, and — the one field that actually authorises
#: anything — willing to have it bought any time between now and then if that is what
#: makes a group order work. Nothing here is tuned to hit a threshold; they are simply
#: what the seeded fixture's other students already look like, and the arithmetic lands
#: where it lands (AGENTS.md §8).
FLAGSHIP_MEMBER = CONSUMER_HOUSEHOLD
FLAGSHIP_PRODUCT = "prod_whey_vanilla"
FLAGSHIP_QUANTITY = 2
FLAGSHIP_CADENCE_DAYS = 40
FLAGSHIP_DUE_DAYS = 11
#: Equal to ``FLAGSHIP_DUE_DAYS``: "buy it any time between now and when I need it",
#: which is the plain reading of the date she gave and what the form derives by default.
FLAGSHIP_FLEX_DAYS = 11
FLAGSHIP_LEAD_DAYS = 11
FLAGSHIP_MIN_SAVINGS_PCT = 20
FLAGSHIP_MAX_SPEND_CENTS = 9000


def onboard_consumer(ctx: PoolContext) -> Step:
    """Set the consumer's account up the way the onboarding does, then declare.

    The fixture seeds this household with nothing — no saved card, no declaration, no
    completed setup — because a first-run member should not find Pool already believing
    things about them. So an automated run has to do what a person does, through the same
    services, or it starts from a state the product never produces.

    The payment method is not decoration here. Without one this member's authorisation
    fails at the final offer, and the scenario ends with *two* failed memberships instead
    of one — twelve rows rather than eleven — quietly breaking the reconciliation the
    whole recovery story rests on. Measured, not assumed.

    Idempotent on purpose. A judge watching the live demo declares this through the form
    a minute before pressing "run", and ``declare_need`` correctly refuses a second
    active declaration for the same product — two rows would count her demand twice. So
    the scripted path checks first and reports which of the two happened, rather than
    either failing or quietly creating a duplicate.
    """
    existing = next(
        (
            n
            for n in ctx.repo.list_needs(ctx.ws)
            if n.active
            and n.household_id == FLAGSHIP_MEMBER
            and n.product_id == FLAGSHIP_PRODUCT
        ),
        None,
    )
    member = ctx.repo.get_household(ctx.ws, FLAGSHIP_MEMBER)
    name = member.display_name if member else FLAGSHIP_MEMBER
    product = ctx.repo.get_product(ctx.ws, FLAGSHIP_PRODUCT)

    # Whatever else happened, this member needs a saved method before Pool may ask them
    # to authorise anything. Adding one creates no charge and no hold (§55).
    if member is not None and not member.payment_method_ref:
        payment_service.setup_payment_method(ctx=ctx, household_id=FLAGSHIP_MEMBER)
        # Re-read, because that call wrote the row. The in-memory store hands back the
        # *same object* every time, so a stale local copy silently stays correct there;
        # DynamoDB deserialises a fresh one, and writing the pre-call copy back would put
        # `payment_method_ref` to empty again — which does not fail loudly, it just makes
        # this member's authorisation fail later and turns eleven membership rows into
        # twelve. Found by the store-parity test, which exists for exactly this.
        member = ctx.repo.get_household(ctx.ws, FLAGSHIP_MEMBER)

    if existing is not None:
        return Step(
            "member_declared_need",
            f"{name} had already told Pool she buys "
            f"{product.name.lower() if product else FLAGSHIP_PRODUCT}",
            {
                "need_id": existing.id,
                "household_id": existing.household_id,
                "product_id": existing.product_id,
                "quantity": existing.quantity,
                "cadence_days": existing.cadence_days,
                "flexibility_days": existing.flexibility_days,
                "declared_by": "member",
                "created_here": False,
            },
        )

    # An automated replay has to leave the workspace in a state a person could actually
    # be in. Half-set-up — holding a saved card while still being asked for a name — is
    # not one of those, so the scripted path finishes setup too. It supplies no name: it
    # is not a person, and inventing one on their behalf would be worse than the
    # placeholder the interface already knows how to keep quiet about.
    if member is not None and not member.is_onboarded:
        member.onboarded_at = iso(utcnow())
        ctx.repo.put_household(ctx.ws, member)

    today = ctx.now.date()
    need = needs_service.declare_need(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        data=needs_service.NeedInput(
            household_id=FLAGSHIP_MEMBER,
            product_id=FLAGSHIP_PRODUCT,
            quantity=FLAGSHIP_QUANTITY,
            cadence_days=FLAGSHIP_CADENCE_DAYS,
            expected_next_need_date=today + timedelta(days=FLAGSHIP_DUE_DAYS),
            flexibility_days=FLAGSHIP_FLEX_DAYS,
            routine_lead_days=FLAGSHIP_LEAD_DAYS,
            min_savings_pct=FLAGSHIP_MIN_SAVINGS_PCT,
            max_spend_cents=FLAGSHIP_MAX_SPEND_CENTS,
        ),
    )
    return Step(
        "member_declared_need",
        f"{name} told Pool she buys "
        f"{product.name.lower() if product else FLAGSHIP_PRODUCT} — no group, no "
        "invitations, nobody else mentioned",
        {
            "need_id": need.id,
            "household_id": need.household_id,
            "product_id": need.product_id,
            "quantity": need.quantity,
            "cadence_days": need.cadence_days,
            "flexibility_days": need.flexibility_days,
            "declared_by": "scenario",
            "created_here": True,
        },
    )


def _timing_split(
    repo: Repository, ws: str, pool: Any, members: list[Any]
) -> dict[str, int]:
    """How much of this pool was already due, and how much had to be pulled forward.

    The headline claim — *seven people were buying about now anyway, and it only clears
    the supplier's minimum because three more had authorised an early purchase* — is the
    whole point of §24, so it should be a number the transcript carries rather than a
    sentence the interface asserts. Computed here by the same
    :func:`~pool.domain.timing.evaluate_timing` the matcher uses, against the pool's own
    distribution date, so it cannot disagree with the eligibility decision that formed
    the pool.

    Returns zeros rather than raising if the pool has no distribution date yet; a
    transcript step is not the place to discover a missing timing record.
    """
    split = {
        "due_now_members": 0,
        "due_now_units": 0,
        "pulled_forward_members": 0,
        "pulled_forward_units": 0,
    }
    if not pool.timing.distribution_starts_at:
        return split
    purchase_date = parse_iso(pool.timing.distribution_starts_at).date()
    for membership in members:
        need = repo.get_need(ws, membership.need_id)
        if need is None:
            continue
        units = membership.allocated_units or membership.requested_units
        if evaluate_timing(need, purchase_date).is_future_pull_forward:
            split["pulled_forward_members"] += 1
            split["pulled_forward_units"] += units
        else:
            split["due_now_members"] += 1
            split["due_now_units"] += units
    return split


def run_showcase(
    repo: Repository,
    ws: str,
    *,
    settings: Settings | None = None,
    routing: RoutingService | None = None,
    reseed: bool = True,
) -> ScenarioResult:
    """Run the full canonical lifecycle and return a structured transcript.

    ``ok`` is False if any stage did not actually happen — the scenario reports what
    occurred, it does not assert success.
    """
    steps: list[Step] = []
    pool_id = ""

    def fail(msg: str) -> ScenarioResult:
        return ScenarioResult(ok=False, steps=steps, failure=msg, pool_id=pool_id)

    if reseed:
        counts = seed(repo, ws)
        steps.append(Step("seed", "Loaded the synthetic Demo University community", counts))

    coordinator = PoolCoordinator(repo, settings=settings, routing=routing)
    ctx = PoolContext(
        repo=repo,
        ws=ws,
        routing=coordinator.routing,
        payments=coordinator.payments,
        purchaser=coordinator.purchaser,
        sourcing=coordinator.sourcing,
        now=utcnow(),
    )

    # 0. The member says what she buys. This is scripted *input*, in the same category as
    #    the volunteer host below and the buyers answering their inbox — the situation is
    #    arranged, the behaviour is not (AGENTS.md §8).
    #
    #    It matters that this is a step at all. The fixture deliberately does not seed
    #    Rosa's whey declaration, so the scenario has to begin where the product begins:
    #    somebody telling Pool what they routinely buy. It goes through the real
    #    ``declare_need`` service, with the real validation, writing the real row the
    #    coordinator later reads — so the automated showcase and a human using the form
    #    start from the same premise instead of two that merely resemble each other.
    steps.append(onboard_consumer(ctx))

    # 1. Background scan. The agent picks the product and the pickup site itself, and
    #    decides whether flexible future demand is worth investigating.
    run1 = coordinator.run(ws, trigger="demo_background_scan", community_id=COMMUNITY_ID)
    pools = [p for p in repo.list_pools(ws) if p.community_id == COMMUNITY_ID]
    if not pools:
        steps.append(Step("background_scan", "Pool found nothing worth forming",
                          {"outcome": run1.outcome.value,
                           "tools_called": [t.name for t in run1.tool_calls]}))
        return fail("the background scan formed no pool")
    pool = pools[0]
    pool_id = pool.id
    product = repo.get_product(ws, pool.product_id)
    site = repo.get_site(ws, pool.pickup_site_id)
    members = repo.list_memberships(ws, pool.id)

    timing_split = _timing_split(repo, ws, pool, members)
    steps.append(
        Step(
            "latent_demand_discovered",
            f"Nobody created a group. Pool noticed {len(members)} students independently "
            f"needed {product.name.lower() if product else 'the same product'} and formed "
            "a candidate pool",
            {
                "outcome": run1.outcome.value,
                "tools_called": [t.name for t in run1.tool_calls],
                "iterations": run1.iterations,
                "model_provider": run1.model_provider,
                "run_id": run1.id,
                "pool_id": pool.id,
                "members": len(members),
                "provisional_units": coord.provisional_units(ctx, pool.id),
                "threshold_units": pool.threshold_units,
                "pickup_site": site.name if site else "",
                "status": pool.status.value,
                **timing_split,
            },
        )
    )

    # 2. A pool member offers to host — the second source of host candidates (§27).
    #    They are added to the candidate set, not handed the job (§28).
    hosting.volunteer_to_host(
        ctx=ctx,
        pool_id=pool.id,
        household_id=VOLUNTEER_HOST,
        profile=HostProfile(
            household_id=VOLUNTEER_HOST,
            community_id=COMMUNITY_ID,
            has_vehicle=True,
            vehicle_capacity_units=60,
            max_orders=40,
            max_weight_kg=80,
            max_supplier_distance_km=16.0,
            minimum_compensation_cents=3000,
            standing=False,
        ),
    )
    evaluation = hosting.evaluate_host_candidates(ctx=ctx, pool_id=pool.id)

    def _named(household_id: str) -> str:
        """Everywhere else in the product a member is a display name, never an id.

        The evaluator works in identifiers because that is what it joins on, but a
        transcript is read by people, and `hh_marchetti` says more about someone than
        `Gio M.` does. Falling back to the id keeps the step honest if a household has
        gone missing rather than quietly printing nothing.
        """
        household = repo.get_household(ws, household_id)
        return household.display_name if household else household_id

    steps.append(
        Step(
            "host_candidates_evaluated",
            "Standing hosts and one pool member who volunteered were evaluated against "
            "the actual job — capacity, vehicle, distance, availability, and their own "
            "minimum pay",
            {
                "candidates": [
                    {**candidate, "display_name": _named(str(candidate.get("household_id", "")))}
                    for candidate in evaluation.candidates
                ],
                "eligible_count": evaluation.eligible_count,
                # The identifier, deliberately: this is a cross-reference into the
                # candidate list, not something rendered to anyone.
                "volunteer": VOLUNTEER_HOST,
                "volunteer_display_name": _named(VOLUNTEER_HOST),
            },
        )
    )
    if evaluation.eligible_count == 0:
        return fail("no host candidate was eligible for this job")

    # 3. Pool offers the job to the best-ranked candidate, and they accept.
    offer = hosting.offer_to_next_host(ctx=ctx, pool_id=pool.id)
    if not offer.offered_household_id:
        return fail(f"no host was offered the job: {offer.reason}")
    accept = hosting.respond_to_host_offer(
        ctx=ctx, pool_id=pool.id, household_id=offer.offered_household_id, accept=True
    )
    assignment = repo.get_host_assignment(ws, pool.id)
    steps.append(
        Step(
            "host_accepted",
            "The best-ranked host accepted. Their pay is now a known input to every "
            "buyer's price",
            {
                "host": _named(offer.offered_household_id),
                "reward_total": format_cents(accept.get("reward_total_cents", 0)),
                "reward_breakdown": assignment.reward_breakdown if assignment else {},
                "handled_orders": assignment.handled_orders if assignment else 0,
                "supplier_distance_km": round(assignment.supplier_distance_km, 1)
                if assignment
                else 0,
                "status": accept.get("pool_status", ""),
            },
        )
    )

    # 4. Quote refresh + exact landed economics + final offer. Smart Join authorises
    #    who it may; everyone else lands in the Decision Inbox.
    run2 = coordinator.run(
        ws,
        trigger="demo_final_offer",
        community_id=COMMUNITY_ID,
        instruction=(
            "A host has accepted a pool. Advance every pool that is blocked: refresh "
            "the supplier quote, issue exact final offers, and lock anything that is "
            "fully funded and viable."
        ),
    )
    pool = repo.get_pool(ws, pool.id) or pool
    economics = pool.final_economics
    if not economics:
        return fail("no final offer was issued")

    pending = [
        d for d in repo.list_decisions(ws)
        if d.pool_id == pool.id
        and d.state == DecisionState.PENDING
        and d.kind == DecisionKind.APPROVE_FINAL_OFFER
    ]
    authorised = [
        m for m in repo.list_memberships(ws, pool.id)
        if m.state == ParticipationState.AUTHORIZED
    ]
    failed_auth = [
        m for m in repo.list_memberships(ws, pool.id)
        if m.state == ParticipationState.AUTHORIZATION_FAILED
    ]
    steps.append(
        Step(
            "final_offer",
            "Supplier quote re-verified, then the complete landed price computed: "
            "merchandise + host pay + processing + Pool's fee. Nothing is hidden",
            {
                "run_id": run2.id,
                "tools_called": [t.name for t in run2.tool_calls],
                "merchandise": format_cents(economics["merchandise_cents"]),
                "host_compensation": format_cents(economics["host_compensation_cents"]),
                "payment_processing": format_cents(economics["payment_processing_cents"]),
                "pool_fee": format_cents(economics["platform_fee_cents"]),
                "all_in": format_cents(economics["all_in_cents"]),
                "retail_baseline": format_cents(economics["retail_baseline_cents"]),
                "net_savings": format_cents(economics["net_savings_cents"]),
                "net_savings_pct": bps_to_pct_str(economics["net_savings_bps"]),
                "authorised_by_smart_join": len(authorised),
                "awaiting_human_decision": len(pending),
                "authorisation_failures": len(failed_auth),
                "quote_verified_at": pool.quote_verified_at,
            },
        )
    )

    # 5. A payment failed. This is not narration — the simulated provider genuinely
    #    declined a saved method, and those units stopped counting as funded. The
    #    numbers below are captured here, before anything repairs them, so the
    #    transcript reads in the order events actually happened.
    if failed_auth:
        steps.append(
            Step(
                "payment_failure",
                "One buyer's card was declined, so their units stopped counting toward "
                "the funded order and the pool fell short",
                {
                    "declined": [m.household_id for m in failed_auth],
                    "units_lost": sum(m.allocated_units for m in failed_auth),
                    "threshold_units": pool.threshold_units,
                    "provider": ctx.payments.name,
                },
            )
        )

    # 6. The humans who had to be asked answer. This is the Decision Inbox.
    answered = 0
    for d in pending:
        coord.respond_to_decision(ctx=ctx, decision_id=d.id, approve=True)
        answered += 1
    steps.append(
        Step(
            "decision_inbox",
            f"{answered} buyer(s) approved their exact final price from the Decision Inbox",
            {
                "approved": answered,
                "funded_units": coord.funded_units(ctx, pool.id),
                "threshold_units": pool.threshold_units,
            },
        )
    )

    # 7. Recovery — real agent runs, not a scripted branch. Which run repairs the gap
    #    depends on when the authorisation failed, so the transcript reports what the
    #    agent actually did rather than asserting it happened on a particular pass.
    funded_before = coord.funded_units(ctx, pool.id)
    run3 = coordinator.run(
        ws,
        trigger="demo_recovery",
        community_id=COMMUNITY_ID,
        instruction=(
            "A buyer authorisation failed and a pool is short of funded demand. Recover "
            "any pool below its threshold, disturbing as few people as possible, then "
            "lock anything that has become viable."
        ),
    )
    pool = repo.get_pool(ws, pool.id) or pool
    recovery_events = [
        e for e in repo.list_activity(ws, limit=500) if e.kind == "pool_recovered"
    ]
    replacements = (
        int(recovery_events[0].facts.get("replacements_authorised", 0))
        if recovery_events
        else 0
    )
    # The count reconciliation, in the one place where the numbers stop agreeing: ten
    # people were matched, one card was declined, one replacement was found — so ten
    # people buy, and the record carries eleven memberships. Without this a reader adds
    # 8 authorised + 2 asked + 1 declined, gets 11, and cannot square it with "ten".
    all_memberships = repo.list_memberships(ws, pool.id)
    paying_states = {
        ParticipationState.AUTHORIZED,
        ParticipationState.LOCKED,
        ParticipationState.FINAL_OFFERED,
    }
    steps.append(
        Step(
            "recovery",
            "Pool searched the wider community for compatible demand and restored the "
            "order without disturbing the buyers who were already committed",
            {
                # `members` is still the discovery-time list, which is exactly the
                # "ten people were matched at the start" the reconciliation needs.
                "members_matched_at_discovery": len(members),
                "buyers_after_recovery": sum(
                    1 for m in all_memberships if m.state in paying_states
                ),
                "memberships_on_record": len(all_memberships),
                "memberships_that_failed": sum(
                    1
                    for m in all_memberships
                    if m.state == ParticipationState.AUTHORIZATION_FAILED
                ),
                "recovered": bool(recovery_events),
                "replacements_authorised": replacements,
                "tools_called": [t.name for t in run2.tool_calls + run3.tool_calls],
                "funded_units_before_this_run": funded_before,
                "funded_units_now": coord.funded_units(ctx, pool.id),
                "threshold_units": pool.threshold_units,
                "status": pool.status.value,
            },
        )
    )

    # 8. Lock. Runs the central viability engine against stored facts, then captures.
    if pool.status not in {PoolStatus.LOCKED, PoolStatus.PURCHASE_READY,
                           PoolStatus.PURCHASED, PoolStatus.DISTRIBUTING,
                           PoolStatus.COMPLETED}:
        lock = coord.lock_pool(ctx=ctx, pool_id=pool.id)
        if not lock.get("locked"):
            steps.append(Step("lock_blocked", "Pool did not lock", lock))
            return fail(f"pool did not lock: {lock.get('reason', '')}")
        pool = repo.get_pool(ws, pool.id) or pool

    captured = [
        p for p in repo.list_payments(ws, pool.id) if p.state == PaymentState.CAPTURED
    ]
    steps.append(
        Step(
            "locked_and_captured",
            "Every viability condition passed — buyer, supplier, host, timing, quote "
            "freshness, package allocation, pickup, and funding — so the pool locked "
            "and payments captured",
            {
                "status": pool.status.value,
                "captured_payments": len(captured),
                "captured_total": format_cents(sum(p.amount_cents for p in captured)),
                "provider": ctx.payments.name,
                "provider_mode": ctx.payments.mode,
            },
        )
    )

    # 9. Purchase. Clearly simulated, and labelled as such everywhere it appears.
    purchase = fulfillment.execute_purchase(ctx=ctx, pool_id=pool.id)
    if not purchase.get("purchased"):
        return fail(f"purchase did not execute: {purchase.get('reason', '')}")
    record = repo.get_purchase_for_pool(ws, pool.id)
    steps.append(
        Step(
            "purchase",
            "The bulk order was placed against the captured funds — SIMULATED in this "
            "build; the host never fronts the money",
            {
                "simulated": purchase.get("simulated"),
                "supplier_reference": purchase.get("supplier_reference"),
                "units": purchase.get("units"),
                "cases": purchase.get("cases"),
                "total": format_cents(record.total_cents) if record else "",
            },
        )
    )

    # 10. Distribution opens; the host gets a real fulfilment job.
    fulfillment.open_distribution(ctx=ctx, pool_id=pool.id)
    communication.announce_status(ctx=ctx, pool_id=pool.id, status=PoolStatus.DISTRIBUTING)
    checklist = fulfillment.host_checklist(ctx=ctx, pool_id=pool.id)
    steps.append(
        Step(
            "distribution_open",
            "The host sees a fulfilment job with a live checklist, and every buyer gets "
            "a one-time pickup credential",
            {
                "orders": checklist["total"],
                "units": checklist["units_total"],
                "window": f"{checklist['distribution_starts_at']} → "
                          f"{checklist['distribution_ends_at']}",
                "host_earnings": checklist["earnings"].get("total_display", ""),
            },
        )
    )

    # 11. Pickup. Each buyer's one-time credential is issued and redeemed.
    redeemed = 0
    rejected_reasons: list[str] = []
    allocations = repo.list_allocations(ws, pool.id)
    for index, allocation in enumerate(allocations):
        credential = fulfillment.issue_pickup_credential(
            ctx=ctx, pool_id=pool.id, household_id=allocation.household_id
        )
        result = fulfillment.redeem_pickup(
            ctx=ctx, pool_id=pool.id, presented=credential.token
        )
        if result.ok:
            redeemed += 1
        # Prove the single-use guarantee by actually re-scanning — but only once.
        # Replaying all ten would bury the rest of the activity feed under rejections,
        # and one genuine rejection demonstrates the property just as well. Every
        # credential is covered by the test suite.
        if index == 0:
            replay = fulfillment.redeem_pickup(
                ctx=ctx, pool_id=pool.id, presented=credential.token
            )
            if not replay.ok:
                rejected_reasons.append(replay.reason)

    pool = repo.get_pool(ws, pool.id) or pool
    steps.append(
        Step(
            "pickup",
            f"{redeemed} handoffs confirmed by one-time QR, and re-scanning a used "
            "credential was rejected",
            {
                "confirmed": redeemed,
                "expected": len(allocations),
                "replay_attempts_rejected": len(rejected_reasons),
                "replay_rejection_reason": rejected_reasons[0] if rejected_reasons else "",
                "status": pool.status.value,
            },
        )
    )

    if pool.status != PoolStatus.COMPLETED:
        return fail(f"pool did not complete (status={pool.status.value})")

    picked_up = sum(
        1 for a in repo.list_allocations(ws, pool.id) if a.state == AllocationState.PICKED_UP
    )
    metrics = coord.impact_metrics(ctx)
    steps.append(
        Step(
            "impact",
            "Impact computed from stored records — every figure traces to a row",
            {
                # Money is formatted here because the transcript is read by people. The
                # underlying metrics payload keeps exact cents; this is presentation only.
                "buying_alone": format_cents(metrics["estimated_retail_spend_cents"]),
                "all_in_pool_cost": format_cents(metrics["pool_spend_cents"]),
                "collective_saving": format_cents(metrics["collective_savings_cents"]),
                "average_saving_each": format_cents(metrics["average_buyer_savings_cents"]),
                "host_earnings": format_cents(metrics["host_earnings_cents"]),
                "pool_fee": format_cents(metrics["platform_fee_cents"]),
                "members_participating": metrics["members_participating"],
                "pickups_confirmed": f"{picked_up}/{metrics['pickups_expected']}",
                "actions_taken_automatically": metrics["coordination_actions_automated"],
                "humans_asked": metrics["human_decisions_requested"],
                "committed_without_asking": metrics["commitments_without_asking"],
                "pools_repaired": metrics["pools_recovered"],
                "is_demo_data": metrics["is_demo_data"],
            },
        )
    )
    return ScenarioResult(ok=True, steps=steps, pool_id=pool.id)
