"""Payment orchestration (§55–§61).

The provider is authoritative for provider facts. This module maps those facts onto
Pool's explicit internal states and never asserts a payment happened because the
client said so.

The shape of the flow, and why
------------------------------
1. **Saving a card is separate from authorising a pool.** Adding a recurring need does
   not touch anyone's money. A saved method is set up once, and the pool-specific
   authorisation is created only when the exact final price is known (§55).
2. **Authorise late, capture at lock.** Authorisations are created after the host is
   selected and the quote refreshed, so a card is never held for days against a price
   that might change (§58). Capture happens only once the pool has passed the final
   viability check.
3. **Nothing is idempotent by accident.** Every provider call carries a derived
   idempotency key, and every webhook event id is recorded on the payment record, so a
   duplicate or replayed event is a no-op rather than a second charge (§61).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..adapters.payments import ProviderResult, verify_webhook_signature
from ..domain.models import (
    AutonomyPath,
    Membership,
    ParticipationState,
    PaymentRecord,
    PaymentState,
    PoolStatus,
    iso,
    new_id,
)
from ..domain.money import format_cents
from .context import CoordinationError, PoolContext


class PaymentFlowError(RuntimeError):
    """A payment orchestration step could not be completed."""


@dataclass
class AuthorizationResult:
    ok: bool
    payment_id: str = ""
    state: str = ""
    amount_cents: int = 0
    failure_code: str = ""
    failure_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "payment_id": self.payment_id,
            "state": self.state,
            "amount_cents": self.amount_cents,
            "amount_display": format_cents(self.amount_cents),
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
        }


def setup_payment_method(*, ctx: PoolContext, household_id: str) -> dict[str, Any]:
    """Save a payment method for future use. Creates no charge and no hold (§55)."""
    household = ctx.repo.get_household(ctx.ws, household_id)
    if household is None:
        raise CoordinationError(f"unknown member: {household_id}")
    result = ctx.payments.setup_payment_method(household_id)
    if result.ok:
        household.payment_method_ref = result.reference
        ctx.repo.put_household(ctx.ws, household)
    return {
        "household_id": household_id,
        "ok": result.ok,
        "provider": ctx.payments.name,
        "provider_mode": ctx.payments.mode,
        "has_payment_method": bool(household.payment_method_ref),
    }


def authorize_participant(
    *, ctx: PoolContext, pool_id: str, household_id: str, path: AutonomyPath
) -> AuthorizationResult:
    """Authorise one buyer's exact final amount.

    Idempotent per (pool, buyer, amount): a retry returns the existing authorisation
    rather than placing a second hold. A failure is recorded explicitly — the buyer's
    units stop counting toward the funded threshold, which is what makes the
    payment-failure recovery branch real rather than decorative (§60).
    """
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    membership = ctx.repo.get_membership(ctx.ws, pool_id, household_id)
    household = ctx.repo.get_household(ctx.ws, household_id)
    if pool is None or membership is None or household is None:
        raise CoordinationError("unknown pool, membership, or member")
    amount = membership.final_cost_cents
    if amount <= 0:
        raise PaymentFlowError(
            "cannot authorise before an exact final price exists for this buyer"
        )

    existing = _find_payment(ctx, pool_id, household_id)
    if existing is not None and existing.state in {
        PaymentState.AUTHORIZED,
        PaymentState.CAPTURED,
    }:
        if existing.amount_cents == amount:
            return AuthorizationResult(
                True, existing.id, existing.state.value, existing.amount_cents
            )
        # The price moved after authorisation. Release the stale hold rather than
        # capturing an amount the buyer never agreed to (§35).
        cancel_authorization(ctx=ctx, payment_id=existing.id)
        existing = None

    idempotency_key = f"auth:{pool_id}:{household_id}:{amount}"
    record = existing or PaymentRecord(
        id=new_id("pay"),
        pool_id=pool_id,
        household_id=household_id,
        amount_cents=amount,
        state=PaymentState.AUTHORIZATION_PENDING,
        provider=ctx.payments.name,
        provider_mode=ctx.payments.mode,
        payment_method_ref=household.payment_method_ref,
        idempotency_key=idempotency_key,
    )
    record.amount_cents = amount
    record.state = PaymentState.AUTHORIZATION_PENDING
    record.idempotency_key = idempotency_key
    record.payment_method_ref = household.payment_method_ref
    ctx.repo.put_payment(ctx.ws, record)

    if not household.payment_method_ref:
        record.state = PaymentState.PAYMENT_METHOD_REQUIRED
        ctx.repo.put_payment(ctx.ws, record)
        _mark_failed(ctx, membership, record, "no_payment_method")
        return AuthorizationResult(
            False, record.id, record.state.value, amount, "no_payment_method",
            "the buyer has no saved payment method",
        )

    result = ctx.payments.authorize(
        amount_cents=amount,
        payment_method_ref=household.payment_method_ref,
        idempotency_key=idempotency_key,
        metadata={"pool_id": pool_id, "household_id": household_id},
    )
    record.provider_ref = result.reference
    if result.ok:
        record.state = PaymentState.AUTHORIZED
        record.authorized_at = iso(ctx.now)
        ctx.repo.put_payment(ctx.ws, record)
        membership.state = ParticipationState.AUTHORIZED
        membership.path = path
        membership.payment_id = record.id
        ctx.repo.put_membership(ctx.ws, membership)
        ctx.log(
            "payment_authorized",
            f"Authorised {format_cents(amount)} for the exact final price"
            + (" without asking (Smart Join)" if path == AutonomyPath.SMART_JOIN else ""),
            {
                "amount_cents": amount,
                "provider": ctx.payments.name,
                "provider_mode": ctx.payments.mode,
                "path": path.value,
            },
            pool_id=pool_id,
            household_id=household_id,
        )
        return AuthorizationResult(True, record.id, record.state.value, amount)

    record.state = PaymentState.AUTHORIZATION_FAILED
    record.failure_code = result.failure_code
    record.failure_message = result.failure_message
    ctx.repo.put_payment(ctx.ws, record)
    _mark_failed(ctx, membership, record, result.failure_code)
    return AuthorizationResult(
        False, record.id, record.state.value, amount, result.failure_code,
        result.failure_message,
    )


def cancel_authorization(*, ctx: PoolContext, payment_id: str) -> ProviderResult:
    """Release a hold. Used when a buyer leaves before lock, or when the price moved."""
    record = ctx.repo.get_payment(ctx.ws, payment_id)
    if record is None:
        raise CoordinationError(f"unknown payment: {payment_id}")
    if record.state == PaymentState.CAPTURED:
        return ProviderResult(
            ok=False, reference=record.provider_ref, status="captured",
            failure_code="already_captured",
            failure_message="a captured payment cannot be cancelled; refund instead",
        )
    if record.state in {PaymentState.CANCELLED, PaymentState.AUTHORIZATION_FAILED}:
        return ProviderResult(ok=True, reference=record.provider_ref, status="canceled")

    record.state = PaymentState.CANCEL_PENDING
    ctx.repo.put_payment(ctx.ws, record)
    result = ctx.payments.cancel(
        reference=record.provider_ref, idempotency_key=f"cancel:{record.id}"
    )
    record.state = PaymentState.CANCELLED if result.ok else PaymentState.AUTHORIZED
    record.cancelled_at = iso(ctx.now) if result.ok else ""
    ctx.repo.put_payment(ctx.ws, record)
    if result.ok:
        ctx.log(
            "payment_cancelled",
            f"Released a {format_cents(record.amount_cents)} authorisation before lock",
            {"amount_cents": record.amount_cents},
            pool_id=record.pool_id,
            household_id=record.household_id,
        )
    return result


def capture_pool(*, ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """Capture every authorisation for a locked pool.

    Only ever called after the final viability check passed. A capture failure does not
    silently degrade into "close enough": the pool stops at ``LOCKED`` and the failure
    is surfaced for operator review (§19).
    """
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None:
        raise CoordinationError(f"unknown pool: {pool_id}")
    if pool.status not in {PoolStatus.LOCKED, PoolStatus.PURCHASE_READY}:
        raise PaymentFlowError(
            f"cannot capture a pool in state {pool.status.value}; capture happens at lock"
        )

    captured: list[str] = []
    failed: list[str] = []
    total = 0
    for record in ctx.repo.list_payments(ctx.ws, pool_id):
        if record.state == PaymentState.CAPTURED:
            captured.append(record.household_id)
            total += record.amount_cents
            continue
        if record.state != PaymentState.AUTHORIZED:
            continue
        record.state = PaymentState.CAPTURE_PENDING
        ctx.repo.put_payment(ctx.ws, record)
        result = ctx.payments.capture(
            reference=record.provider_ref, idempotency_key=f"capture:{record.id}"
        )
        if result.ok:
            record.state = PaymentState.CAPTURED
            record.captured_at = iso(ctx.now)
            captured.append(record.household_id)
            total += record.amount_cents
        else:
            record.state = PaymentState.AUTHORIZATION_FAILED
            record.failure_code = result.failure_code
            record.failure_message = result.failure_message
            failed.append(record.household_id)
        ctx.repo.put_payment(ctx.ws, record)

    if failed:
        ctx.log(
            "capture_failed",
            f"{len(failed)} payment(s) could not be captured — routed to operator review",
            {"failed": len(failed), "captured": len(captured)},
            pool_id=pool_id,
        )
        return {
            "pool_id": pool_id, "captured": captured, "failed": failed,
            "captured_cents": total, "status": pool.status.value,
            "purchase_ready": False,
        }

    pool.status = PoolStatus.PURCHASE_READY
    ctx.repo.put_pool(ctx.ws, pool)
    capture_mode = "Simulated" if ctx.payments.mode == "simulated" else "Test-mode"
    ctx.log(
        "payment_captured",
        f"{capture_mode} capture recorded: {format_cents(total)} across "
        f"{len(captured)} buyer(s); the order is ready to purchase",
        {
            "captured_cents": total,
            "buyers": len(captured),
            "provider": ctx.payments.name,
            "provider_mode": ctx.payments.mode,
        },
        pool_id=pool_id,
    )
    return {
        "pool_id": pool_id, "captured": captured, "failed": [],
        "captured_cents": total, "status": pool.status.value, "purchase_ready": True,
    }


def refund_payment(*, ctx: PoolContext, payment_id: str, amount_cents: int = 0) -> ProviderResult:
    """Refund a captured payment. Modelled, but only an operator can trigger it."""
    record = ctx.repo.get_payment(ctx.ws, payment_id)
    if record is None:
        raise CoordinationError(f"unknown payment: {payment_id}")
    if record.state != PaymentState.CAPTURED:
        return ProviderResult(
            ok=False, reference=record.provider_ref, status=record.state.value,
            failure_code="not_refundable",
            failure_message="only a captured payment can be refunded",
        )
    amount = amount_cents or record.amount_cents
    record.state = PaymentState.REFUND_PENDING
    ctx.repo.put_payment(ctx.ws, record)
    result = ctx.payments.refund(
        reference=record.provider_ref, amount_cents=amount,
        idempotency_key=f"refund:{record.id}:{amount}",
    )
    record.state = PaymentState.REFUNDED if result.ok else PaymentState.CAPTURED
    ctx.repo.put_payment(ctx.ws, record)
    if result.ok:
        ctx.log(
            "payment_refunded",
            f"Refunded {format_cents(amount)}",
            {"amount_cents": amount},
            pool_id=record.pool_id, household_id=record.household_id,
        )
    return result


# --------------------------------------------------------------------------- webhooks


#: Provider event types this system understands. Anything else is acknowledged and
#: ignored rather than guessed at.
_HANDLED_EVENTS = {
    "payment_intent.amount_capturable_updated": PaymentState.AUTHORIZED,
    "payment_intent.succeeded": PaymentState.CAPTURED,
    "payment_intent.payment_failed": PaymentState.AUTHORIZATION_FAILED,
    "payment_intent.canceled": PaymentState.CANCELLED,
    "charge.refunded": PaymentState.REFUNDED,
}


def handle_provider_event(
    *,
    ctx: PoolContext,
    payload: str,
    signature_header: str,
    webhook_secret: str,
) -> dict[str, Any]:
    """Verify, deduplicate, and apply one provider webhook event.

    Three defences, in order: the signature must verify against the shared secret; the
    event id must not already have been applied to that payment; and only known event
    types change state. A replayed event is accepted and does nothing.
    """
    if not verify_webhook_signature(
        payload=payload,
        header=signature_header,
        secret=webhook_secret,
        now=int(ctx.now.timestamp()),
    ):
        return {"ok": False, "reason": "signature verification failed", "applied": False}

    try:
        event = json.loads(payload)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "payload is not valid JSON", "applied": False}

    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    obj = (event.get("data") or {}).get("object") or {}
    reference = str(obj.get("id", ""))
    if not event_id or not reference:
        return {"ok": False, "reason": "event is missing an id or object reference",
                "applied": False}

    record = next(
        (p for p in ctx.repo.list_payments(ctx.ws) if p.provider_ref == reference), None
    )
    if record is None:
        # An event for something we do not track is acknowledged, not an error: the
        # provider must not retry forever because of a foreign object.
        return {"ok": True, "reason": "no matching payment record", "applied": False}

    if event_id in record.applied_event_ids:
        return {
            "ok": True, "reason": "event already applied", "applied": False,
            "payment_id": record.id, "state": record.state.value,
        }

    new_state = _HANDLED_EVENTS.get(event_type)
    record.applied_event_ids.append(event_id)
    if new_state is None:
        ctx.repo.put_payment(ctx.ws, record)
        return {
            "ok": True, "reason": f"unhandled event type {event_type}", "applied": False,
            "payment_id": record.id, "state": record.state.value,
        }

    # A captured payment is terminal for our purposes: a late "authorized" event must
    # never walk it backwards.
    if record.state == PaymentState.CAPTURED and new_state == PaymentState.AUTHORIZED:
        ctx.repo.put_payment(ctx.ws, record)
        return {
            "ok": True, "reason": "ignored a stale authorisation event", "applied": False,
            "payment_id": record.id, "state": record.state.value,
        }

    record.state = new_state
    if new_state == PaymentState.CAPTURED and not record.captured_at:
        record.captured_at = iso(ctx.now)
    if new_state == PaymentState.AUTHORIZED and not record.authorized_at:
        record.authorized_at = iso(ctx.now)
    ctx.repo.put_payment(ctx.ws, record)

    membership = ctx.repo.get_membership(ctx.ws, record.pool_id, record.household_id)
    if membership is not None and new_state == PaymentState.AUTHORIZATION_FAILED:
        _mark_failed(ctx, membership, record, "provider_event")

    ctx.log(
        "payment_event_applied",
        f"Applied provider event {event_type}",
        {"event_type": event_type, "state": record.state.value},
        pool_id=record.pool_id,
        household_id=record.household_id,
    )
    return {
        "ok": True, "reason": "applied", "applied": True,
        "payment_id": record.id, "state": record.state.value,
    }


# --------------------------------------------------------------------------- internals


def _find_payment(ctx: PoolContext, pool_id: str, household_id: str) -> PaymentRecord | None:
    for p in ctx.repo.list_payments(ctx.ws, pool_id):
        if p.household_id == household_id and p.state not in {
            PaymentState.CANCELLED,
            PaymentState.AUTHORIZATION_FAILED,
        }:
            return p
    return None


def _mark_failed(
    ctx: PoolContext, membership: Membership, record: PaymentRecord, code: str
) -> None:
    """An unfunded buyer stops counting toward the threshold. That is the whole point."""
    membership.state = ParticipationState.AUTHORIZATION_FAILED
    membership.payment_id = record.id
    ctx.repo.put_membership(ctx.ws, membership)
    ctx.log(
        "payment_failed",
        f"Authorisation failed ({code}) — these units no longer count as funded",
        {"amount_cents": record.amount_cents, "failure_code": code},
        pool_id=record.pool_id,
        household_id=record.household_id,
    )
    pool = ctx.repo.get_pool(ctx.ws, record.pool_id)
    if pool is not None and pool.status == PoolStatus.FUNDING:
        pool.status = PoolStatus.RECOVERING
        ctx.repo.put_pool(ctx.ws, pool)
