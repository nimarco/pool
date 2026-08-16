"""Communication: automated updates, host announcements, private threads, privacy.

Pool exists to reduce coordination overhead, so the assertions here are largely about
what does *not* happen: no group chat, no host DMing strangers, no contact details
leaking because two people ended up in the same order.
"""

from __future__ import annotations

import pytest

from pool.domain.models import (
    AnnouncementKind,
    AutonomyPath,
    ExceptionKind,
    FulfillerRole,
    HostAssignment,
    IssueKind,
    Membership,
    ParticipationState,
    Pool,
    PoolStatus,
)
from pool.services import communication
from tests.conftest import COMM, WS, make_member


def _pool_with_host(ctx, *, buyers=("m0", "m1")):
    pool = Pool(
        id="pool_1", community_id=COMM, product_id="p", offer_id="o",
        pickup_site_id="s", status=PoolStatus.DISTRIBUTING, threshold_units=2,
    )
    ctx.repo.put_pool(WS, pool)
    for hid in buyers:
        ctx.repo.put_household(WS, make_member(hid))
        ctx.repo.put_membership(
            WS,
            Membership(
                pool_id=pool.id, household_id=hid, need_id=f"n_{hid}", requested_units=1,
                allocated_units=1, state=ParticipationState.LOCKED,
                path=AutonomyPath.SMART_JOIN,
            ),
        )
    ctx.repo.put_household(WS, make_member("host"))
    ctx.repo.put_host_assignment(
        WS,
        HostAssignment(
            pool_id=pool.id, household_id="host", role=FulfillerRole.FULFILLER,
            pickup_site_id="s", supplier_distance_km=5.0, handled_orders=len(buyers),
            handled_units=len(buyers), estimated_weight_kg=10,
        ),
    )
    ctx.repo.put_household(WS, make_member("outsider"))
    return pool


# ------------------------------------------------------------------ announcements


def test_a_system_update_reaches_the_pool_without_anyone_writing_it(ctx):
    pool = _pool_with_host(ctx)
    announcement = communication.announce_status(
        ctx=ctx, pool_id=pool.id, status=PoolStatus.DISTRIBUTING
    )
    assert announcement is not None
    assert announcement.author_household_id == ""
    assert "pickup" in announcement.body.lower()


def test_not_every_transition_is_worth_a_notification(ctx):
    """A pool that pings buyers at each internal step has recreated the problem."""
    pool = _pool_with_host(ctx)
    assert communication.announce_status(
        ctx=ctx, pool_id=pool.id, status=PoolStatus.HOST_SELECTED
    ) is not None
    assert communication.announce_status(
        ctx=ctx, pool_id=pool.id, status=PoolStatus.PURCHASE_READY
    ) is None


def test_the_assigned_host_can_post_one_structured_announcement(ctx):
    pool = _pool_with_host(ctx)
    announcement = communication.announce_as_host(
        ctx=ctx, pool_id=pool.id, household_id="host", kind=AnnouncementKind.HOST_ARRIVED
    )
    assert announcement.body
    assert len(ctx.repo.list_announcements(WS, pool.id)) == 1


def test_a_non_host_cannot_announce_to_the_pool(ctx):
    pool = _pool_with_host(ctx)
    with pytest.raises(communication.CommunicationError):
        communication.announce_as_host(
            ctx=ctx, pool_id=pool.id, household_id="m0",
            kind=AnnouncementKind.HOST_ARRIVED,
        )


def test_a_host_cannot_forge_a_system_announcement(ctx):
    pool = _pool_with_host(ctx)
    with pytest.raises(communication.CommunicationError):
        communication.announce_as_host(
            ctx=ctx, pool_id=pool.id, household_id="host", kind=AnnouncementKind.SYSTEM
        )


# --------------------------------------------------------------------- exceptions


def test_common_exceptions_resolve_without_involving_a_human(ctx):
    """Only what Pool cannot handle should cost anyone attention (§81)."""
    pool = _pool_with_host(ctx)
    result = communication.report_exception(
        ctx=ctx, pool_id=pool.id, household_id="m0", kind=ExceptionKind.RUNNING_LATE
    )
    assert result["resolved_automatically"] is True
    assert result["thread_id"] == ""
    assert ctx.repo.list_threads(WS, pool.id) == []


def test_cannot_pick_up_is_handled_automatically(ctx):
    pool = _pool_with_host(ctx)
    result = communication.report_exception(
        ctx=ctx, pool_id=pool.id, household_id="m0", kind=ExceptionKind.CANNOT_PICK_UP
    )
    assert result["resolved_automatically"] is True
    assert "secondary" in result["response"]


def test_a_product_problem_becomes_an_operator_case_not_a_host_argument(ctx):
    pool = _pool_with_host(ctx)
    result = communication.report_exception(
        ctx=ctx, pool_id=pool.id, household_id="m0",
        kind=ExceptionKind.PROBLEM_WITH_ORDER, detail="wrong flavour",
    )
    assert result["issue_id"]
    assert result["thread_id"] == ""
    issues = ctx.repo.list_issues(WS)
    assert issues and issues[0].kind == IssueKind.WRONG_ITEM


def test_an_unresolvable_exception_opens_a_private_thread(ctx):
    pool = _pool_with_host(ctx)
    result = communication.report_exception(
        ctx=ctx, pool_id=pool.id, household_id="m0",
        kind=ExceptionKind.NEED_ALTERNATE_PICKUP, detail="I'm off campus until 6",
    )
    assert result["thread_id"]
    thread = ctx.repo.get_thread(WS, result["thread_id"])
    assert thread.buyer_household_id == "m0"
    assert thread.host_household_id == "host"
    assert len(ctx.repo.list_messages(WS, thread.id)) == 1


def test_a_non_member_cannot_raise_an_exception_on_this_pool(ctx):
    pool = _pool_with_host(ctx)
    with pytest.raises(communication.CommunicationError):
        communication.report_exception(
            ctx=ctx, pool_id=pool.id, household_id="outsider",
            kind=ExceptionKind.RUNNING_LATE,
        )


# ------------------------------------------------------------------------ threads


def test_a_thread_is_scoped_to_one_transaction_and_reused(ctx):
    pool = _pool_with_host(ctx)
    first = communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")
    second = communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")
    assert first.id == second.id


def test_only_the_buyer_and_the_assigned_host_can_post(ctx):
    pool = _pool_with_host(ctx)
    thread = communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")
    assert communication.post_message(
        ctx=ctx, thread_id=thread.id, sender_household_id="m0", body="on my way"
    )
    assert communication.post_message(
        ctx=ctx, thread_id=thread.id, sender_household_id="host", body="no rush"
    )
    for intruder in ("m1", "outsider"):
        with pytest.raises(communication.CommunicationError):
            communication.post_message(
                ctx=ctx, thread_id=thread.id, sender_household_id=intruder, body="hello"
            )


def test_a_host_cannot_open_a_thread_with_someone_who_is_not_their_buyer(ctx):
    """There is no path from "I am a host" to "I can message this person" (§80)."""
    pool = _pool_with_host(ctx)
    with pytest.raises(communication.CommunicationError):
        communication.open_thread(
            ctx=ctx, pool_id=pool.id, buyer_household_id="outsider"
        )


def test_a_pool_with_no_host_has_nobody_to_message(ctx):
    pool = _pool_with_host(ctx)
    ctx.repo.store(WS).host_assignments.clear()
    with pytest.raises(communication.CommunicationError):
        communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")


def test_an_empty_message_is_refused(ctx):
    pool = _pool_with_host(ctx)
    thread = communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")
    with pytest.raises(communication.CommunicationError):
        communication.post_message(
            ctx=ctx, thread_id=thread.id, sender_household_id="m0", body="   "
        )


def test_threads_archive_with_the_transaction(ctx):
    pool = _pool_with_host(ctx)
    thread = communication.open_thread(ctx=ctx, pool_id=pool.id, buyer_household_id="m0")
    assert communication.archive_threads_for_pool(ctx=ctx, pool_id=pool.id) == 1
    with pytest.raises(communication.CommunicationError):
        communication.post_message(
            ctx=ctx, thread_id=thread.id, sender_household_id="m0", body="still here?"
        )


def test_posting_to_an_unknown_thread_fails(ctx):
    from pool.services.context import CoordinationError

    with pytest.raises(CoordinationError):
        communication.post_message(
            ctx=ctx, thread_id="thr_nope", sender_household_id="m0", body="hi"
        )


# ------------------------------------------------------------------------ privacy


def test_no_contact_detail_ever_appears_in_a_pool_scoped_record(ctx):
    """Being in the same order is not consent to share an email address (§82)."""
    pool = _pool_with_host(ctx)
    communication.report_exception(
        ctx=ctx, pool_id=pool.id, household_id="m0",
        kind=ExceptionKind.NEED_ALTERNATE_PICKUP, detail="running behind",
    )
    communication.announce_as_host(
        ctx=ctx, pool_id=pool.id, household_id="host", kind=AnnouncementKind.HOST_ARRIVED
    )
    serialised = "".join(
        [
            str([a.to_dict() for a in ctx.repo.list_announcements(WS, pool.id)]),
            str([t.to_dict() for t in ctx.repo.list_threads(WS, pool.id)]),
            str([e.to_dict() for e in ctx.repo.list_activity(WS)]),
        ]
    )
    assert "@example.invalid" not in serialised
    assert "pm_sim_" not in serialised
