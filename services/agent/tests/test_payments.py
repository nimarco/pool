"""Payments: provider behaviour, orchestration, idempotency, and webhook safety.

The most important test in this file is the one asserting the Stripe adapter refuses a
live key. Everything else protects money that is only ever simulated; that one protects
money that is not.
"""

from __future__ import annotations

import json
import time

import pytest

from pool.adapters.payments import (
    CAPTURE_FAILURE_MARKER,
    FAILING_METHOD_MARKER,
    LivePaymentRefused,
    LocalSimulatedPaymentProvider,
    PaymentError,
    StripePaymentProvider,
    build_payment_provider,
    sign_webhook_payload,
    verify_webhook_signature,
)
from pool.domain.models import (
    AutonomyPath,
    Membership,
    ParticipationState,
    PaymentRecord,
    PaymentState,
    Pool,
    PoolStatus,
    PoolTiming,
    iso,
    utcnow,
)
from pool.services import payments as payment_service
from tests.conftest import WS, make_member

# --------------------------------------------------------------------- live refusal


@pytest.mark.parametrize("key", ["sk_live_abc123", "rk_live_abc", "pk_test_abc", ""])
def test_stripe_provider_refuses_anything_that_is_not_a_test_key(key):
    """There is no flag that relaxes this. A misconfigured environment cannot charge."""
    with pytest.raises(LivePaymentRefused):
        StripePaymentProvider(key)


def test_stripe_provider_accepts_a_test_key_and_reports_test_mode():
    provider = StripePaymentProvider("sk_test_abc123", client=object())
    assert provider.mode == "test"


def test_the_default_provider_is_the_free_simulated_one():
    provider = build_payment_provider("simulated")
    assert provider.name == "simulated"
    assert provider.mode == "simulated"


def test_unknown_provider_fails_loudly():
    with pytest.raises(ValueError):
        build_payment_provider("paypal-ish")


# ------------------------------------------------------------------ simulated provider


def test_authorisation_is_idempotent_on_its_key():
    provider = LocalSimulatedPaymentProvider()
    first = provider.authorize(
        amount_cents=1000, payment_method_ref="pm_a", idempotency_key="k1", metadata={}
    )
    second = provider.authorize(
        amount_cents=1000, payment_method_ref="pm_a", idempotency_key="k1", metadata={}
    )
    assert first.reference == second.reference


def test_a_declining_method_fails_authorisation():
    provider = LocalSimulatedPaymentProvider()
    result = provider.authorize(
        amount_cents=1000, payment_method_ref=f"pm_{FAILING_METHOD_MARKER}",
        idempotency_key="k", metadata={},
    )
    assert result.ok is False
    assert result.failure_code == "card_declined"


def test_authorising_without_a_method_fails_cleanly():
    provider = LocalSimulatedPaymentProvider()
    result = provider.authorize(
        amount_cents=1000, payment_method_ref="", idempotency_key="k", metadata={}
    )
    assert result.ok is False
    assert result.failure_code == "no_payment_method"


def test_a_non_positive_authorisation_is_rejected():
    with pytest.raises(PaymentError):
        LocalSimulatedPaymentProvider().authorize(
            amount_cents=0, payment_method_ref="pm_a", idempotency_key="k", metadata={}
        )


def test_duplicate_capture_is_not_a_second_charge():
    provider = LocalSimulatedPaymentProvider()
    auth = provider.authorize(
        amount_cents=1000, payment_method_ref="pm_a", idempotency_key="k", metadata={}
    )
    first = provider.capture(reference=auth.reference, idempotency_key="c")
    second = provider.capture(reference=auth.reference, idempotency_key="c")
    assert first.ok and second.ok
    assert second.status == "succeeded"


def test_capture_can_fail_and_says_so():
    provider = LocalSimulatedPaymentProvider()
    auth = provider.authorize(
        amount_cents=1000, payment_method_ref=f"pm_{CAPTURE_FAILURE_MARKER}",
        idempotency_key="k", metadata={},
    )
    result = provider.capture(reference=auth.reference, idempotency_key="c")
    assert result.ok is False
    assert result.failure_code == "capture_failed"


def test_a_captured_payment_cannot_be_cancelled():
    provider = LocalSimulatedPaymentProvider()
    auth = provider.authorize(
        amount_cents=1000, payment_method_ref="pm_a", idempotency_key="k", metadata={}
    )
    provider.capture(reference=auth.reference, idempotency_key="c")
    result = provider.cancel(reference=auth.reference, idempotency_key="x")
    assert result.ok is False
    assert result.failure_code == "already_captured"


def test_only_a_captured_payment_can_be_refunded():
    provider = LocalSimulatedPaymentProvider()
    auth = provider.authorize(
        amount_cents=1000, payment_method_ref="pm_a", idempotency_key="k", metadata={}
    )
    assert provider.refund(
        reference=auth.reference, amount_cents=1000, idempotency_key="r"
    ).ok is False
    provider.capture(reference=auth.reference, idempotency_key="c")
    assert provider.refund(
        reference=auth.reference, amount_cents=1000, idempotency_key="r"
    ).ok is True


def test_an_unknown_reference_raises_rather_than_guessing():
    with pytest.raises(PaymentError):
        LocalSimulatedPaymentProvider().capture(reference="nope", idempotency_key="c")


# ------------------------------------------------- one processor, many processes
#
# Every test above uses one provider instance, which is one Lambda container. The
# deployed demo is not one container: the browser fires several requests per action and
# Lambda answers them from whichever it likes, so an authorisation is routinely taken on
# one and captured on another. These four run each half on its *own* provider, which is
# the only arrangement that can see #0030.


def _second_container() -> LocalSimulatedPaymentProvider:
    """A provider that has never seen the reference it is about to be handed."""
    return LocalSimulatedPaymentProvider()


def test_a_capture_on_another_container_still_finds_the_authorisation():
    """The bug that stranded a locked pool on the deployed demo.

    Authorise on container A, capture on container B. B's ``_intents`` is empty, and it
    used to raise ``unknown payment reference`` from inside ``capture_pool`` — after the
    pool had already locked, so the money was neither captured nor released and no
    further run could reach it (``lock_pool`` short-circuits on an already-locked pool).
    """
    auth = LocalSimulatedPaymentProvider().authorize(
        amount_cents=7184, payment_method_ref="pm_ok", idempotency_key="a", metadata={}
    )
    captured = _second_container().capture(reference=auth.reference, idempotency_key="c")

    assert captured.ok is True
    assert captured.status == "succeeded"
    assert captured.amount_cents == 7184, "the amount must survive the hop, not be guessed"


def test_a_capture_failure_still_fails_on_another_container():
    """The simulation's teeth have to survive the hop too. A method that authorises and
    fails at capture must fail on whichever container captures it — otherwise the
    recovery branch quietly stops being reachable in the deployment that has it."""
    auth = LocalSimulatedPaymentProvider().authorize(
        amount_cents=5000,
        payment_method_ref=f"pm_{CAPTURE_FAILURE_MARKER}",
        idempotency_key="a",
        metadata={},
    )
    result = _second_container().capture(reference=auth.reference, idempotency_key="c")

    assert result.ok is False
    assert result.failure_code == "capture_failed"


def test_a_declined_authorisation_cannot_be_captured_on_another_container():
    """The one rebuild that must ignore what the caller is asking for. A declined card
    is declined from every container; reconstructing it as capturable would turn a
    refusal into a charge."""
    auth = LocalSimulatedPaymentProvider().authorize(
        amount_cents=5000,
        payment_method_ref=f"pm_{FAILING_METHOD_MARKER}",
        idempotency_key="a",
        metadata={},
    )
    result = _second_container().capture(reference=auth.reference, idempotency_key="c")

    assert result.ok is False
    assert auth.ok is False


def test_cancel_and_refund_also_survive_the_hop():
    """Release-the-stale-hold and refund run on whatever container the next request
    lands on, and both are gated on the authoritative ``PaymentRecord`` before they get
    here (``services/payments.py``)."""
    ref = LocalSimulatedPaymentProvider().authorize(
        amount_cents=2500, payment_method_ref="pm_ok", idempotency_key="a", metadata={}
    ).reference

    assert _second_container().cancel(reference=ref, idempotency_key="x").ok is True
    assert _second_container().refund(
        reference=ref, amount_cents=2500, idempotency_key="y"
    ).ok is True


# ------------------------------------------------------------------------ webhooks


SECRET = "whsec_test_not_a_real_secret"


def _event(event_id="evt_1", event_type="payment_intent.succeeded", reference="pi_1"):
    return json.dumps(
        {"id": event_id, "type": event_type, "data": {"object": {"id": reference}}}
    )


def test_a_valid_signature_verifies():
    payload = _event()
    header = sign_webhook_payload(payload, SECRET)
    assert verify_webhook_signature(payload=payload, header=header, secret=SECRET)


def test_a_tampered_payload_fails_verification():
    header = sign_webhook_payload(_event(), SECRET)
    assert not verify_webhook_signature(
        payload=_event(event_id="evt_forged"), header=header, secret=SECRET
    )


def test_the_wrong_secret_fails_verification():
    payload = _event()
    header = sign_webhook_payload(payload, SECRET)
    assert not verify_webhook_signature(payload=payload, header=header, secret="whsec_other")


def test_a_stale_timestamp_is_rejected():
    """A captured request replayed hours later must not be re-submittable (§61)."""
    payload = _event()
    old = int(time.time()) - 10_000
    header = sign_webhook_payload(payload, SECRET, timestamp=old)
    assert not verify_webhook_signature(payload=payload, header=header, secret=SECRET)


@pytest.mark.parametrize("header", ["", "garbage", "t=abc,v1=def", "v1=abc"])
def test_malformed_signature_headers_are_rejected(header):
    assert not verify_webhook_signature(payload=_event(), header=header, secret=SECRET)


def test_missing_inputs_are_rejected():
    assert not verify_webhook_signature(payload="", header="t=1,v1=x", secret=SECRET)
    assert not verify_webhook_signature(payload="{}", header="t=1,v1=x", secret="")


# -------------------------------------------------------------------- orchestration


def _prepare_pool(ctx, *, method: str | None = None, amount: int = 5000):
    member = make_member("m1", payment_method=method)
    ctx.repo.put_household(WS, member)
    pool = Pool(
        id="pool_1", community_id="comm_test", product_id="p", offer_id="o",
        pickup_site_id="s", status=PoolStatus.FUNDING, threshold_units=2,
        timing=PoolTiming(lock_at=iso(utcnow())),
    )
    ctx.repo.put_pool(WS, pool)
    ctx.repo.put_membership(
        WS,
        Membership(
            pool_id=pool.id, household_id="m1", need_id="n1", requested_units=2,
            allocated_units=2, state=ParticipationState.FINAL_OFFERED,
            path=AutonomyPath.PENDING_APPROVAL, final_cost_cents=amount,
        ),
    )
    return pool


def test_authorising_marks_the_buyer_funded(ctx):
    _prepare_pool(ctx)
    result = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    assert result.ok
    membership = ctx.repo.get_membership(WS, "pool_1", "m1")
    assert membership.state == ParticipationState.AUTHORIZED
    assert membership.counts_as_funded


def test_a_failed_authorisation_stops_the_units_counting(ctx):
    """This is what makes the recovery branch real rather than narrated (§60)."""
    _prepare_pool(ctx, method=f"pm_{FAILING_METHOD_MARKER}")
    result = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    assert result.ok is False
    membership = ctx.repo.get_membership(WS, "pool_1", "m1")
    assert membership.state == ParticipationState.AUTHORIZATION_FAILED
    assert membership.counts_as_funded is False
    assert ctx.repo.get_pool(WS, "pool_1").status == PoolStatus.RECOVERING


def test_a_member_with_no_saved_method_cannot_be_authorised(ctx):
    _prepare_pool(ctx, method="")
    result = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    assert result.failure_code == "no_payment_method"


def test_authorising_before_a_final_price_exists_is_refused(ctx):
    """Nobody's card is touched until the exact amount is known (§55)."""
    _prepare_pool(ctx, amount=0)
    with pytest.raises(payment_service.PaymentFlowError):
        payment_service.authorize_participant(
            ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
        )


def test_re_authorising_the_same_amount_reuses_the_hold(ctx):
    _prepare_pool(ctx)
    first = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    second = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    assert first.payment_id == second.payment_id
    assert len(ctx.repo.list_payments(WS, "pool_1")) == 1


def test_a_changed_price_releases_the_stale_hold_and_re_authorises(ctx):
    """Pool never captures an amount the buyer did not agree to (§35)."""
    _prepare_pool(ctx)
    payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    membership = ctx.repo.get_membership(WS, "pool_1", "m1")
    membership.final_cost_cents = 7000
    ctx.repo.put_membership(WS, membership)
    payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    states = {p.state for p in ctx.repo.list_payments(WS, "pool_1")}
    assert PaymentState.CANCELLED in states
    assert PaymentState.AUTHORIZED in states


def test_cancelling_before_lock_releases_the_authorisation(ctx):
    _prepare_pool(ctx)
    result = payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    assert payment_service.cancel_authorization(ctx=ctx, payment_id=result.payment_id).ok
    assert ctx.repo.get_payment(WS, result.payment_id).state == PaymentState.CANCELLED


def test_capture_only_happens_at_lock(ctx):
    pool = _prepare_pool(ctx)
    payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    with pytest.raises(payment_service.PaymentFlowError):
        payment_service.capture_pool(ctx=ctx, pool_id=pool.id)

    pool.status = PoolStatus.LOCKED
    ctx.repo.put_pool(WS, pool)
    result = payment_service.capture_pool(ctx=ctx, pool_id=pool.id)
    assert result["purchase_ready"] is True
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.PURCHASE_READY


def test_capture_failure_leaves_the_pool_locked_for_operator_review(ctx):
    pool = _prepare_pool(ctx, method=f"pm_{CAPTURE_FAILURE_MARKER}")
    payment_service.authorize_participant(
        ctx=ctx, pool_id="pool_1", household_id="m1", path=AutonomyPath.SMART_JOIN
    )
    pool.status = PoolStatus.LOCKED
    ctx.repo.put_pool(WS, pool)
    result = payment_service.capture_pool(ctx=ctx, pool_id=pool.id)
    assert result["purchase_ready"] is False
    assert result["failed"] == ["m1"]
    assert ctx.repo.get_pool(WS, pool.id).status == PoolStatus.LOCKED


def test_setting_up_a_payment_method_creates_no_charge(ctx):
    ctx.repo.put_household(WS, make_member("m1", payment_method=""))
    result = payment_service.setup_payment_method(ctx=ctx, household_id="m1")
    assert result["ok"] and result["has_payment_method"]
    assert ctx.repo.list_payments(WS) == []


# --------------------------------------------------------------- webhook application


def _record(ctx, state=PaymentState.AUTHORIZED, reference="pi_1"):
    record = PaymentRecord(
        id="pay_1", pool_id="pool_1", household_id="m1", amount_cents=5000,
        state=state, provider_ref=reference,
    )
    ctx.repo.put_payment(WS, record)
    return record


def _deliver(ctx, payload):
    return payment_service.handle_provider_event(
        ctx=ctx,
        payload=payload,
        signature_header=sign_webhook_payload(payload, SECRET, int(ctx.now.timestamp())),
        webhook_secret=SECRET,
    )


def test_an_unsigned_event_is_rejected(ctx):
    _record(ctx)
    result = payment_service.handle_provider_event(
        ctx=ctx, payload=_event(), signature_header="t=1,v1=nope", webhook_secret=SECRET
    )
    assert result["ok"] is False
    assert result["applied"] is False


def test_a_signed_event_updates_state(ctx):
    _record(ctx)
    result = _deliver(ctx, _event())
    assert result["applied"] is True
    assert ctx.repo.get_payment(WS, "pay_1").state == PaymentState.CAPTURED


def test_a_replayed_event_is_a_no_op(ctx):
    _record(ctx)
    payload = _event()
    assert _deliver(ctx, payload)["applied"] is True
    replay = _deliver(ctx, payload)
    assert replay["ok"] is True
    assert replay["applied"] is False
    assert replay["reason"] == "event already applied"


def test_a_late_authorisation_event_cannot_walk_a_capture_backwards(ctx):
    _record(ctx, state=PaymentState.CAPTURED)
    result = _deliver(
        ctx, _event(event_id="evt_2", event_type="payment_intent.amount_capturable_updated")
    )
    assert result["applied"] is False
    assert ctx.repo.get_payment(WS, "pay_1").state == PaymentState.CAPTURED


def test_an_unknown_event_type_is_acknowledged_but_changes_nothing(ctx):
    _record(ctx)
    result = _deliver(ctx, _event(event_id="evt_3", event_type="invoice.paid"))
    assert result["ok"] is True and result["applied"] is False
    assert ctx.repo.get_payment(WS, "pay_1").state == PaymentState.AUTHORIZED


def test_an_event_for_an_unknown_payment_is_acknowledged_not_an_error(ctx):
    result = _deliver(ctx, _event(reference="pi_someone_else"))
    assert result["ok"] is True and result["applied"] is False


def test_malformed_json_is_rejected(ctx):
    result = _deliver(ctx, "not json at all")
    assert result["ok"] is False


def test_a_failure_event_unfunds_the_buyer(ctx):
    _record(ctx)
    ctx.repo.put_pool(
        WS,
        Pool(id="pool_1", community_id="c", product_id="p", offer_id="o",
             pickup_site_id="s", status=PoolStatus.FUNDING, threshold_units=1),
    )
    ctx.repo.put_membership(
        WS,
        Membership(pool_id="pool_1", household_id="m1", need_id="n1", requested_units=2,
                   allocated_units=2, state=ParticipationState.AUTHORIZED,
                   path=AutonomyPath.SMART_JOIN),
    )
    _deliver(ctx, _event(event_id="evt_f", event_type="payment_intent.payment_failed"))
    membership = ctx.repo.get_membership(WS, "pool_1", "m1")
    assert membership.state == ParticipationState.AUTHORIZATION_FAILED
