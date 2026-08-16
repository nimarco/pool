"""Payment provider adapters (§54–§61).

One interface, two implementations:

* ``LocalSimulatedPaymentProvider`` — deterministic, offline, free. Powers every unit
  test, CI, the offline demo, and the failure scenarios that would be impossible to
  trigger reliably against a real processor (AGENTS.md §3.6).
* ``StripePaymentProvider`` — Stripe in **TEST mode only**.

Hard safety property
--------------------
``StripePaymentProvider`` refuses to construct with anything but a ``sk_test_`` key.
There is no flag, environment variable, or argument that relaxes this. The hackathon
environment therefore cannot silently fall back to live Stripe (§12) — the failure
mode is a loud exception at construction, not a real charge.

Authorisation vs capture
------------------------
Card authorisation is **not** captured payment, and this module never conflates them
(§56). A pool authorises exact final amounts, and only captures once every viability
condition has passed and the pool has locked.

Webhooks
--------
``verify_webhook_signature`` implements Stripe's documented scheme (a signed payload
of ``timestamp.body`` compared against ``v1=`` values, with a tolerance window) using
only ``hmac`` from the standard library. That keeps signature verification honest and
testable offline, with no secret in the repository and no dependency on the SDK being
installed.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

#: Stripe's documented default tolerance for replayed webhook timestamps.
WEBHOOK_TOLERANCE_SECONDS = 300


class PaymentError(RuntimeError):
    """A payment operation failed in a way the caller must handle explicitly."""


class LivePaymentRefused(PaymentError):
    """Raised when anything would touch real money during this build."""


@dataclass(frozen=True)
class ProviderResult:
    """What a provider says happened. Never a paraphrase of what we hoped happened."""

    ok: bool
    reference: str = ""
    status: str = ""
    failure_code: str = ""
    failure_message: str = ""
    amount_cents: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reference": self.reference,
            "status": self.status,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "amount_cents": self.amount_cents,
        }


@runtime_checkable
class PaymentProvider(Protocol):
    name: str
    #: "simulated" or "test". Never "live" in this build.
    mode: str

    def setup_payment_method(self, household_id: str) -> ProviderResult:
        """Begin saving a payment method for future use. Creates no charge (§55)."""
        ...

    def authorize(
        self,
        *,
        amount_cents: int,
        payment_method_ref: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderResult: ...

    def capture(self, *, reference: str, idempotency_key: str) -> ProviderResult: ...

    def cancel(self, *, reference: str, idempotency_key: str) -> ProviderResult: ...

    def refund(
        self, *, reference: str, amount_cents: int, idempotency_key: str
    ) -> ProviderResult: ...


# --------------------------------------------------------------------- simulated


#: A saved-method reference containing this marker always fails authorisation. It is
#: how the deterministic demo triggers the payment-failure recovery branch (§60)
#: without depending on a real processor declining a card at the right moment.
FAILING_METHOD_MARKER = "declines"

#: A method reference containing this marker authorises but fails at capture, which is
#: the nastier real-world case (§60): the pool is locked and the money is not there.
CAPTURE_FAILURE_MARKER = "capturefails"


@dataclass
class LocalSimulatedPaymentProvider:
    """Deterministic in-process payment provider. No network, no cost, no real money."""

    name: str = "simulated"
    mode: str = "simulated"
    #: reference -> {"state", "amount_cents", "method"}
    _intents: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: idempotency key -> reference, so a retried authorise returns the same intent.
    _by_key: dict[str, str] = field(default_factory=dict)

    def setup_payment_method(self, household_id: str) -> ProviderResult:
        ref = f"pm_sim_{hashlib.sha256(household_id.encode()).hexdigest()[:16]}"
        return ProviderResult(ok=True, reference=ref, status="succeeded")

    def authorize(
        self,
        *,
        amount_cents: int,
        payment_method_ref: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderResult:
        if amount_cents <= 0:
            raise PaymentError("authorisation amount must be positive")
        if not payment_method_ref:
            return ProviderResult(
                ok=False,
                status="requires_payment_method",
                failure_code="no_payment_method",
                failure_message="no saved payment method",
            )

        existing = self._by_key.get(idempotency_key)
        if existing:
            intent = self._intents[existing]
            return ProviderResult(
                ok=intent["state"] != "failed",
                reference=existing,
                status=intent["state"],
                amount_cents=intent["amount_cents"],
            )

        reference = f"pi_sim_{uuid.uuid4().hex[:20]}"
        if FAILING_METHOD_MARKER in payment_method_ref:
            self._intents[reference] = {
                "state": "failed",
                "amount_cents": amount_cents,
                "method": payment_method_ref,
            }
            self._by_key[idempotency_key] = reference
            return ProviderResult(
                ok=False,
                reference=reference,
                status="failed",
                failure_code="card_declined",
                failure_message="the card was declined",
                amount_cents=amount_cents,
            )

        self._intents[reference] = {
            "state": "requires_capture",
            "amount_cents": amount_cents,
            "method": payment_method_ref,
        }
        self._by_key[idempotency_key] = reference
        return ProviderResult(
            ok=True, reference=reference, status="requires_capture", amount_cents=amount_cents
        )

    def capture(self, *, reference: str, idempotency_key: str) -> ProviderResult:
        intent = self._intents.get(reference)
        if intent is None:
            raise PaymentError(f"unknown payment reference: {reference}")
        if intent["state"] == "succeeded":
            # Idempotent: a duplicate capture is not a second charge.
            return ProviderResult(
                ok=True, reference=reference, status="succeeded",
                amount_cents=intent["amount_cents"],
            )
        if intent["state"] != "requires_capture":
            return ProviderResult(
                ok=False, reference=reference, status=intent["state"],
                failure_code="not_capturable",
                failure_message=f"intent is {intent['state']}, not capturable",
            )
        if CAPTURE_FAILURE_MARKER in intent["method"]:
            intent["state"] = "capture_failed"
            return ProviderResult(
                ok=False, reference=reference, status="capture_failed",
                failure_code="capture_failed",
                failure_message="the processor could not capture the authorisation",
                amount_cents=intent["amount_cents"],
            )
        intent["state"] = "succeeded"
        return ProviderResult(
            ok=True, reference=reference, status="succeeded", amount_cents=intent["amount_cents"]
        )

    def cancel(self, *, reference: str, idempotency_key: str) -> ProviderResult:
        intent = self._intents.get(reference)
        if intent is None:
            raise PaymentError(f"unknown payment reference: {reference}")
        if intent["state"] == "succeeded":
            return ProviderResult(
                ok=False, reference=reference, status="succeeded",
                failure_code="already_captured",
                failure_message="a captured payment cannot be cancelled; refund instead",
            )
        intent["state"] = "canceled"
        return ProviderResult(ok=True, reference=reference, status="canceled")

    def refund(
        self, *, reference: str, amount_cents: int, idempotency_key: str
    ) -> ProviderResult:
        intent = self._intents.get(reference)
        if intent is None:
            raise PaymentError(f"unknown payment reference: {reference}")
        if intent["state"] != "succeeded":
            return ProviderResult(
                ok=False, reference=reference, status=intent["state"],
                failure_code="not_refundable",
                failure_message="only a captured payment can be refunded",
            )
        intent["state"] = "refunded"
        return ProviderResult(
            ok=True, reference=reference, status="refunded", amount_cents=amount_cents
        )


# ------------------------------------------------------------------------ stripe


class StripePaymentProvider:
    """Stripe in TEST mode. Constructing it with a live key is an error, always.

    Not exercised against Stripe's servers in this build — no test key was configured
    when it was written, so it is **implemented, not verified**. The call shapes follow
    Stripe's PaymentIntents manual-capture flow; re-check the current official docs
    before a pilot relies on them.
    """

    name = "stripe"

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if not api_key:
            raise LivePaymentRefused("Stripe provider requires an API key")
        if not api_key.startswith("sk_test_"):
            # Deliberately unconditional. There is no override, because the whole point
            # is that a misconfigured environment cannot charge a real card (§12).
            raise LivePaymentRefused(
                "refusing to construct the Stripe provider with a non-test key: this "
                "build never touches live money"
            )
        self.mode = "test"
        self._api_key = api_key
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:  # pragma: no cover - requires the stripe package
            import stripe

            stripe.api_key = self._api_key
            self._client = stripe
        return self._client

    def setup_payment_method(self, household_id: str) -> ProviderResult:
        """Create a SetupIntent — saves a method for later without charging (§55)."""
        intent = self.client.SetupIntent.create(
            usage="off_session", metadata={"household_id": household_id}
        )
        return ProviderResult(
            ok=True, reference=str(intent["id"]), status=str(intent.get("status", ""))
        )

    def authorize(
        self,
        *,
        amount_cents: int,
        payment_method_ref: str,
        idempotency_key: str,
        metadata: dict[str, str],
    ) -> ProviderResult:
        try:
            intent = self.client.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                payment_method=payment_method_ref,
                capture_method="manual",
                confirm=True,
                off_session=True,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced, never silently swallowed
            return ProviderResult(
                ok=False, status="failed", failure_code="authorization_error",
                failure_message=str(exc)[:300], amount_cents=amount_cents,
            )
        status = str(intent.get("status", ""))
        return ProviderResult(
            ok=status == "requires_capture",
            reference=str(intent["id"]),
            status=status,
            amount_cents=amount_cents,
            failure_code="" if status == "requires_capture" else "unexpected_status",
            failure_message="" if status == "requires_capture" else f"intent status {status}",
        )

    def capture(self, *, reference: str, idempotency_key: str) -> ProviderResult:
        try:
            intent = self.client.PaymentIntent.capture(
                reference, idempotency_key=idempotency_key
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                ok=False, reference=reference, status="capture_failed",
                failure_code="capture_error", failure_message=str(exc)[:300],
            )
        status = str(intent.get("status", ""))
        return ProviderResult(
            ok=status == "succeeded",
            reference=reference,
            status=status,
            amount_cents=int(intent.get("amount_received", 0) or 0),
        )

    def cancel(self, *, reference: str, idempotency_key: str) -> ProviderResult:
        try:
            intent = self.client.PaymentIntent.cancel(reference, idempotency_key=idempotency_key)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                ok=False, reference=reference, status="cancel_failed",
                failure_code="cancel_error", failure_message=str(exc)[:300],
            )
        return ProviderResult(ok=True, reference=reference, status=str(intent.get("status", "")))

    def refund(
        self, *, reference: str, amount_cents: int, idempotency_key: str
    ) -> ProviderResult:
        try:
            refund = self.client.Refund.create(
                payment_intent=reference, amount=amount_cents, idempotency_key=idempotency_key
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                ok=False, reference=reference, status="refund_failed",
                failure_code="refund_error", failure_message=str(exc)[:300],
            )
        return ProviderResult(
            ok=True, reference=reference, status=str(refund.get("status", "")),
            amount_cents=amount_cents,
        )


# ----------------------------------------------------------------------- webhook


def sign_webhook_payload(payload: str, secret: str, timestamp: int | None = None) -> str:
    """Produce a Stripe-format ``Stripe-Signature`` header. Used by tests, not in prod."""
    ts = timestamp if timestamp is not None else int(time.time())
    signature = hmac.new(
        secret.encode("utf-8"), f"{ts}.{payload}".encode(), hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={signature}"


def verify_webhook_signature(
    *,
    payload: str,
    header: str,
    secret: str,
    tolerance_seconds: int = WEBHOOK_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """Verify a Stripe-format signature header.

    Returns False rather than raising: a bad signature is an ordinary hostile input,
    not an exceptional condition. Rejects stale timestamps so a captured-and-replayed
    request outside the tolerance window cannot be re-submitted (§61).
    """
    if not payload or not header or not secret:
        return False

    timestamp: str | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False
    current = now if now is not None else int(time.time())
    if abs(current - ts) > tolerance_seconds:
        return False

    expected = hmac.new(
        secret.encode("utf-8"), f"{ts}.{payload}".encode(), hashlib.sha256
    ).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


def build_payment_provider(kind: str, stripe_api_key: str = "") -> PaymentProvider:
    """Construct the configured provider. Defaults to the free, simulated one."""
    if kind in {"simulated", "local", ""}:
        return LocalSimulatedPaymentProvider()
    if kind == "stripe":
        return StripePaymentProvider(stripe_api_key)
    raise ValueError(f"unknown payment provider: {kind!r}")
