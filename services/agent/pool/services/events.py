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
