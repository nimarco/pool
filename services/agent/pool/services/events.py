"""Coordination events — the seam between declaring a need and coordinating one.

Declaring is a member's action. Coordinating is Pool's. They are different transactions
with different failure modes, and running them as one statement gets both wrong: a
declaration that fails because the agent was unavailable is a product that lost the
user's input, and a run triggered from a page render is a bill that grows with traffic.

So the write side records that work is *owed*, and a dispatcher decides when it happens.

Three properties are load-bearing.

**One cause, one event.** The event id is a digest of the declaration and its material
content, so re-submitting a form, reloading the page, or saving an edit that changed
nothing all resolve to the same event — which already exists, and is not run again.
Dedupe is a primary-key lookup in both backends rather than a scan.

**One event, one run.** Claiming is a state transition on the event, and a claimed event
is not claimable again. A dispatcher that arrives second sees ``running`` or a terminal
state and does nothing.

**Nothing is scheduled.** There is no poller and no timer here. An event is dispatched
because something asked for it — a request, a test, or later a queue consumer
(AGENTS.md §3.2).

What this is not
----------------

Not a message bus. There is no topic, no subscriber registry, no retry daemon and no
generic payload — a coordination event names a declaration and a Community, and the run
derives everything else from stored state exactly as it always has (``agent/objective``).

**Atomicity is honestly bounded.** ``declare_need`` writes the declaration and this
module writes the event, as two writes against a repository whose interface has no
transaction. On DynamoDB that is genuinely two ``PutItem`` calls: a crash between them
leaves a declaration with no event, which is the safe direction — the member's input is
kept and coordination is merely not owed yet. The unsafe direction cannot happen, because
the event is written second. Making the pair atomic needs ``TransactWriteItems`` and the
IAM to go with it; that is recorded as a production requirement rather than claimed here
(§7 of the phase brief, BUILD_HISTORY #0056).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from ..domain.models import (
    CoordinationEvent,
    CoordinationEventKind,
    CoordinationEventStatus,
    NeedDeclaration,
    RunOutcome,
    iso,
    utcnow,
)
from .context import PoolContext

#: How many claims one event may accumulate before a dispatcher refuses it. A failed run
#: leaves the event ``failed`` and does **not** retry itself; this bounds a caller who
#: keeps asking, so a broken run cannot become an unbounded spend (AGENTS.md §3.1).
MAX_EVENT_ATTEMPTS = 3


def declaration_digest(need: NeedDeclaration) -> str:
    """A digest of everything about a declaration that could change what Pool would do.

    Taken over the declaration's own serialised form minus its id, so a field added to
    ``NeedDeclaration`` is covered the day it is added rather than the day somebody
    remembers to list it here. That is deliberately coarse: amending a quantity by one
    unit produces a new event even though the verdict might not move, and the alternative
    is a hand-maintained list of "significant" fields that is wrong in the dangerous
    direction the first time it is edited.
    """
    payload = {k: v for k, v in need.to_dict().items() if k != "id"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def event_id_for(need: NeedDeclaration, kind: str = CoordinationEventKind.NEED_DECLARED.value) -> str:
    """The deterministic id one declaration at one content produces."""
    return "cev_" + hashlib.sha256(
        f"{kind}|{need.id}|{declaration_digest(need)}".encode()
    ).hexdigest()[:16]


def is_coordinatable(ctx: PoolContext, need: NeedDeclaration) -> bool:
    """Is there anything a run could usefully do about this declaration?

    Retiring a declaration is a real edit and a legitimate reason for a new event id —
    but there is no coordination owed for something a member has stopped buying, and a
    run that opened, found the declaration inactive and recorded no action would be a
    model call bought to learn something already known. The product has to exist for the
    same reason.
    """
    if not need.active:
        return False
    return ctx.repo.get_product(ctx.ws, need.product_id) is not None


def record_declaration_event(
    ctx: PoolContext, need: NeedDeclaration, community_id: str = ""
) -> CoordinationEvent | None:
    """Note that coordination is owed for this declaration, once.

    Returns the event — existing or new — or ``None`` when nothing is owed. Writing an
    event that already exists is a no-op rather than an error: the caller is usually a
    member pressing a button twice, and refusing them would be reporting a duplicate
    submission as a failure.
    """
    if not is_coordinatable(ctx, need):
        return None

    event_id = event_id_for(need)
    existing = ctx.repo.get_coordination_event(ctx.ws, event_id)
    if existing is not None:
        return existing

    event = CoordinationEvent(
        id=event_id,
        kind=CoordinationEventKind.NEED_DECLARED.value,
        community_id=community_id or need.community_id,
        household_id=need.household_id,
        need_id=need.id,
    )
    ctx.repo.put_coordination_event(ctx.ws, event)
    ctx.log(
        "coordination_owed",
        "A standing declaration changed, so Pool owes it a look",
        {
            "event_id": event.id,
            "kind": event.kind,
            "need_id": need.id,
            "product_id": need.product_id,
        },
        household_id=need.household_id,
    )
    return event


# ------------------------------------------------------------------------ dispatch


@dataclass(frozen=True)
class Dispatch:
    """What happened when a dispatcher took one event on.

    ``ran`` distinguishes "a run happened" from "there was nothing to do" — a second
    dispatcher arriving at a claimed event, or an event already terminal, is a normal
    outcome and not a failure.
    """

    event: CoordinationEvent
    ran: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict(), "ran": self.ran, "reason": self.reason}


CLAIM_ALREADY_TERMINAL = "already_completed"
CLAIM_ALREADY_RUNNING = "already_running"
CLAIM_ATTEMPTS_EXHAUSTED = "attempts_exhausted"


def claim(ctx: PoolContext, event: CoordinationEvent) -> str:
    """Move an event to ``running``, or say why it cannot be claimed.

    Returns an empty string on a successful claim. Deliberately a read-then-write against
    the same interface every other service uses: the workspace lease the API already
    takes around a run is what serialises two dispatchers in this build, and claiming
    conditionally on ``status`` would need the repository's conditional-write path — a
    change worth making when a second dispatcher exists, and not before.
    """
    if event.is_terminal:
        return CLAIM_ALREADY_TERMINAL
    if event.status == CoordinationEventStatus.RUNNING.value:
        return CLAIM_ALREADY_RUNNING
    if event.attempts >= MAX_EVENT_ATTEMPTS:
        return CLAIM_ATTEMPTS_EXHAUSTED

    event.status = CoordinationEventStatus.RUNNING.value
    event.attempts += 1
    event.claimed_at = iso(utcnow())
    ctx.repo.put_coordination_event(ctx.ws, event)
    return ""


def complete(
    ctx: PoolContext,
    event: CoordinationEvent,
    *,
    run_id: str,
    outcome: str,
    terminal_reason: str,
    pool_id: str = "",
) -> CoordinationEvent:
    """Record that a run reached a verdict — including a verdict of "nothing to do"."""
    event.status = CoordinationEventStatus.COMPLETED.value
    event.run_id = run_id
    event.outcome = outcome
    event.terminal_reason = terminal_reason
    event.pool_id = pool_id
    event.ended_at = iso(utcnow())
    ctx.repo.put_coordination_event(ctx.ws, event)
    return event


def fail(
    ctx: PoolContext, event: CoordinationEvent, *, run_id: str = "", reason: str = ""
) -> CoordinationEvent:
    """Record that a run did not reach a verdict. Distinct from reaching "no action"."""
    event.status = CoordinationEventStatus.FAILED.value
    event.run_id = run_id or event.run_id
    event.terminal_reason = reason
    event.ended_at = iso(utcnow())
    ctx.repo.put_coordination_event(ctx.ws, event)
    return event


def pending(ctx: PoolContext) -> list[CoordinationEvent]:
    """Events nobody has taken on yet, oldest first."""
    return [
        e
        for e in ctx.repo.list_coordination_events(ctx.ws)
        if e.status == CoordinationEventStatus.PENDING.value
    ]


def view(event: CoordinationEvent) -> dict[str, Any]:
    """Server-owned state for a surface that has to say what Pool is doing.

    Six distinguishable situations, none of them invented by a client and none of them a
    progress animation: waiting to be looked at, being looked at now, an order formed,
    looked at and nothing worth doing, stopped by a safety bound, and failed. The words a
    member reads are chosen elsewhere; what is guaranteed here is that they are chosen
    from stored facts (AGENTS.md §8).
    """
    return {
        "event_id": event.id,
        "kind": event.kind,
        "need_id": event.need_id,
        "status": event.status,
        "run_id": event.run_id,
        "outcome": event.outcome,
        "terminal_reason": event.terminal_reason,
        "pool_id": event.pool_id,
        "attempts": event.attempts,
        "created_at": event.created_at,
        "ended_at": event.ended_at,
        "formed_order": bool(event.pool_id),
        "reached_a_verdict": event.status == CoordinationEventStatus.COMPLETED.value,
    }


def dispatch(
    ctx: PoolContext,
    event: CoordinationEvent,
    *,
    run: Any,
) -> Dispatch:
    """Claim one event, run the bounded coordinator, and record what it reached.

    ``run`` is a callable taking ``(trigger, event)`` and returning an ``AgentRun``. The
    coordinator is injected rather than imported so this module stays a service — the
    agent package depends on services, and reversing that would make an event impossible
    to write without building a model.

    A run that raises is recorded as a failed event and the exception is re-raised: the
    event exists to make the failure auditable, not to swallow it.
    """
    refusal = claim(ctx, event)
    if refusal:
        return Dispatch(event, False, refusal)

    try:
        record = run(event)
    except Exception as exc:  # noqa: BLE001 - recorded on the event, then re-raised
        fail(ctx, event, reason=f"{type(exc).__name__}")
        raise

    pool_id = ""
    outcome = getattr(record, "outcome", None)
    if outcome is not None and outcome == RunOutcome.POOL_CREATED:
        created = [
            p
            for p in ctx.repo.list_pools(ctx.ws)
            if p.created_by_run == record.id
        ]
        pool_id = created[0].id if created else ""

    if outcome == RunOutcome.ERROR:
        # The run itself classified this as a failure. An event that called it complete
        # would tell a member Pool looked and decided, which it did not.
        return Dispatch(
            fail(ctx, event, run_id=record.id, reason=record.termination_reason or "error"),
            True,
        )

    return Dispatch(
        complete(
            ctx,
            event,
            run_id=record.id,
            outcome=outcome.value if outcome is not None else "",
            terminal_reason=record.termination_reason or "completed",
            pool_id=pool_id,
        ),
        True,
    )


# ------------------------------------------------------- what one declaration caused


#: Bounds on the explanation. It is read by a member on a phone and by a judge on a
#: laptop, and neither of them wants a transcript.
MAX_EXPLAINED_OPTIONS = 6
MAX_EXPLAINED_TOOL_CALLS = 12


def latest_for_need(ctx: PoolContext, need_id: str) -> CoordinationEvent | None:
    """The most recent coordination this declaration caused, if any."""
    matching = [
        e for e in ctx.repo.list_coordination_events(ctx.ws) if e.need_id == need_id
    ]
    return matching[-1] if matching else None


def explain(ctx: PoolContext, need_id: str) -> dict[str, Any] | None:
    """The whole causal chain one declaration set off, read from stored rows.

    Reload-safe by construction: nothing here is reconstructed from what a browser
    happened to see. The event names the run, the run's own strategy rows name what was
    considered, its evaluations name what was costed and what each verdict was, and the
    pool — if one formed — names itself. Refreshing the page re-reads the same rows.

    Two audiences, one source. The member-facing half answers "what happened and what has
    *not* happened"; the technical half answers "which model, which tools, in what order,
    under what bounds". They are the same facts at two levels of detail, so they cannot
    disagree — which is the property that makes the second one proof of the first.

    Counts, never a roster: which specific neighbour was excluded is not an answer to
    anybody else's question (AGENTS.md §4).
    """
    event = latest_for_need(ctx, need_id)
    if event is None:
        return None
    run = ctx.repo.get_run(ctx.ws, event.run_id) if event.run_id else None

    considered = [
        s for s in ctx.repo.list_cohort_strategies(ctx.ws) if run and s.run_id == run.id
    ][:MAX_EXPLAINED_OPTIONS]
    investigated = [
        e for e in ctx.repo.list_strategy_evaluations(ctx.ws) if run and e.run_id == run.id
    ]
    # One verdict per option: the guarded creator re-costs before it writes, so the same
    # option can carry two identical evaluations and showing both would read as two
    # investigations.
    seen: set[str] = set()
    unique: list[Any] = []
    for evaluation in investigated:
        if evaluation.strategy_id in seen:
            continue
        seen.add(evaluation.strategy_id)
        unique.append(evaluation)

    pool = ctx.repo.get_pool(ctx.ws, event.pool_id) if event.pool_id else None
    memberships = ctx.repo.list_memberships(ctx.ws, pool.id) if pool else []
    chosen = next(
        (e for e in unique if pool is not None and e.target_product_id == pool.product_id),
        None,
    )

    exclusions: dict[str, int] = {}
    for evaluation in unique:
        for code, count in (evaluation.exclusion_codes or {}).items():
            exclusions[code] = max(exclusions.get(code, 0), int(count))

    return {
        "need_id": need_id,
        "event": view(event),
        "run": _run_view(ctx, run),
        # What Pool decided to *ask* before any of this, when the member allowed
        # alternatives. A separate run, earlier and cheaper, and the only place in the
        # chain where a model chose something a member then saw: the questions in front
        # of them, and their order. What each answer means is not here because no run
        # decided it — see `services/needs.policy_from_answers`.
        "clarification": _clarification_view(ctx, event),
        "considered": [_option_view(s) for s in considered],
        "investigated": [_verdict_view(e) for e in unique],
        "chosen": _verdict_view(chosen) if chosen is not None else None,
        "exclusion_codes": dict(sorted(exclusions.items())),
        "order": _order_view(ctx, pool, memberships, chosen),
        # What has **not** happened. Stated positively so a surface cannot forget to say
        # it: candidate formation touches no card, and nobody has agreed to fulfil
        # anything (AGENTS.md §8, canonical invariants 2 and 3).
        "not_yet": {
            "host_accepted": False,
            "final_price_issued": bool(pool and pool.has_final_offer),
            "card_authorised": bool(ctx.repo.list_payments(ctx.ws, pool.id)) if pool else False,
            "purchased": False,
        },
    }


def _clarification_view(ctx: PoolContext, event: Any) -> dict[str, Any] | None:
    """The plan that shaped the questions this declaration's preferences came from.

    Looked up by member and product rather than by run id, because the two runs are
    deliberately not the same one: asking happens while somebody is still deciding, and
    coordinating happens after they have decided. Tying the record to the coordination
    run would have meant either running the planner inside it — too late to be of any use
    — or inventing a link the storage layer does not have.

    ``None`` for an exact-only declaration, which is the truthful answer: nothing was
    asked, because nothing needed to be.
    """
    need = ctx.repo.get_need(ctx.ws, event.need_id)
    if need is None:
        return None
    plans = [
        p
        for p in ctx.repo.list_clarification_plans(ctx.ws)
        if p.household_id == need.household_id and p.product_id == need.product_id
    ]
    if not plans:
        return None
    plan = plans[-1]
    run = ctx.repo.get_run(ctx.ws, plan.run_id) if plan.run_id else None
    return {
        "plan_id": plan.id,
        "run_id": plan.run_id,
        "status": plan.status,
        "family": plan.family,
        "schema_version": plan.schema_version,
        "question_definition_version": plan.question_definition_version,
        # Both, and in this order: what the deterministic layer put on the table, and
        # what the model took from it. A reader checking that the model chose *within* an
        # approved set needs the set, not a promise that one existed.
        "offered": list(plan.candidate_question_ids),
        "asked": list(plan.question_ids),
        "model_provider": run.model_provider if run else "",
        "model_id": run.model_id if run else "",
        "iterations": run.iterations if run else 0,
        "input_tokens": run.input_tokens if run else 0,
        "output_tokens": run.output_tokens if run else 0,
    }


def _run_view(ctx: PoolContext, run: Any) -> dict[str, Any] | None:
    if run is None:
        return None
    from ..config import get_settings

    # The configured bounds, so a reader can check the run against them rather than
    # taking the word "bounded" on trust.
    bounds = get_settings().bounds
    return {
        "run_id": run.id,
        "trigger": run.trigger,
        "objective": run.objective_kind,
        "model_provider": run.model_provider,
        "model_id": run.model_id,
        "outcome": run.outcome.value,
        "termination_reason": run.termination_reason,
        "iterations": run.iterations,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "duration_ms": run.duration_ms,
        "tool_calls": [
            {"name": t.name, "ok": t.ok} for t in run.tool_calls[:MAX_EXPLAINED_TOOL_CALLS]
        ],
        "bounds": {
            "max_iterations": bounds.max_iterations,
            "max_tool_calls": bounds.max_tool_calls,
            "max_strategy_listings": bounds.max_strategy_listings,
            "max_strategy_evaluations": bounds.max_strategy_evaluations,
            "max_strategy_pool_creations": bounds.max_strategy_pool_creations,
        },
    }


def _option_view(strategy: Any) -> dict[str, Any]:
    """One option as it was offered, before anything was costed. No verdict, no price."""
    return {
        "strategy_id": strategy.id,
        "product": strategy.target_product_name,
        "attributes": dict(strategy.target_attributes),
        "compatible_declarations": strategy.compatible_declaration_count,
        "compatible_units": strategy.compatible_units,
        "lowest_supplier_minimum_units": strategy.lowest_minimum_units,
    }


def _verdict_view(evaluation: Any) -> dict[str, Any]:
    from ..domain.money import bps_to_pct_str, format_cents

    return {
        "strategy_id": evaluation.strategy_id,
        "evaluation_id": evaluation.id,
        "product": evaluation.target_product_name,
        "viable": evaluation.viable,
        "blocker_code": evaluation.blocker_code,
        "matched_units": evaluation.matched_units,
        "minimum_units": evaluation.minimum_units,
        "selected_units": evaluation.selected_units,
        "cases": evaluation.cases,
        "case_units": evaluation.case_units,
        "surplus_units": evaluation.surplus_units,
        "all_in_display": format_cents(evaluation.all_in_cents),
        "retail_baseline_display": format_cents(evaluation.retail_baseline_cents),
        "net_savings_display": format_cents(evaluation.net_savings_cents),
        "net_savings_pct": bps_to_pct_str(evaluation.net_savings_bps),
        "includes_your_declaration": evaluation.includes_objective_need,
    }


def _order_view(
    ctx: PoolContext, pool: Any, memberships: list[Any], chosen: Any
) -> dict[str, Any] | None:
    if pool is None:
        return None
    product = ctx.repo.get_product(ctx.ws, pool.product_id)
    site = ctx.repo.get_site(ctx.ws, pool.pickup_site_id)
    return {
        "pool_id": pool.id,
        "status": pool.status.value,
        "product": product.display_name if product else pool.product_id,
        "member_count": len(memberships),
        "units": sum(m.requested_units for m in memberships),
        "threshold_units": pool.threshold_units,
        "cases": chosen.cases if chosen is not None else 0,
        "case_units": chosen.case_units if chosen is not None else 0,
        "surplus_units": chosen.surplus_units if chosen is not None else 0,
        "pickup_site": site.name if site else "",
        "distribution_day": pool.timing.distribution_starts_at[:10]
        if pool.timing.distribution_starts_at
        else "",
        # Provisional is the whole state, so it is a field rather than a sentence.
        "provisional": all(m.state.value == "provisional" for m in memberships),
        "host_status": "recruiting" if ctx.repo.get_host_assignment(ctx.ws, pool.id) is None
        else "assigned",
    }
