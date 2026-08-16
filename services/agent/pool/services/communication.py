"""Communication (§77–§82).

Pool exists to *reduce* coordination overhead, so a thirty-person group chat is a
product failure, not a feature. The rule is:

    routine communication = automated
    human messaging       = exception-driven

Three channels, in order of how much human attention they cost:

1. **System updates** — generated from real state transitions. Nobody writes them and
   the host does not have to notify thirty people by hand (§78).
2. **Host announcements** — one structured message reaching the whole pool: "I'm
   here", "running late", "location changed" (§79).
3. **Private buyer ↔ host threads** — transaction-scoped, opened by a structured
   exception, archived with the pool. A host cannot open a thread with someone who is
   not their buyer, and no phone number or email is ever exposed (§80, §82).
"""

from __future__ import annotations

from typing import Any

from ..domain.models import (
    Announcement,
    AnnouncementKind,
    ExceptionKind,
    IssueKind,
    Message,
    MessageThread,
    PoolStatus,
    iso,
    new_id,
)
from .context import CoordinationError, PoolContext


class CommunicationError(RuntimeError):
    """A message could not be sent within the permissions of the sender."""


#: Structured exceptions Pool can resolve without any human messaging at all (§81).
_SELF_RESOLVING = {
    ExceptionKind.RUNNING_LATE: (
        "Thanks — the host has been told you are on your way. Your order will be held "
        "until the end of the pickup window."
    ),
    ExceptionKind.CANNOT_PICK_UP: (
        "Noted. Your order will be held and you will be offered the secondary pickup "
        "window when the primary one closes."
    ),
}


def announce_system(
    *, ctx: PoolContext, pool_id: str, body: str, facts: dict[str, Any] | None = None
) -> Announcement:
    """Post an automated operational update. One write, the whole pool sees it."""
    announcement = Announcement(
        id=new_id("ann"),
        pool_id=pool_id,
        kind=AnnouncementKind.SYSTEM,
        body=body,
        author_household_id="",
    )
    ctx.repo.put_announcement(ctx.ws, announcement)
    ctx.log("announcement_posted", body, facts or {"kind": "system"}, pool_id=pool_id)
    return announcement


def announce_as_host(
    *,
    ctx: PoolContext,
    pool_id: str,
    household_id: str,
    kind: AnnouncementKind,
    body: str = "",
) -> Announcement:
    """A structured, pool-wide announcement from the assigned host.

    Only the assigned host can post, and only structured kinds are accepted — the
    free-text option exists but is one of a small set rather than an open channel.
    """
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if assignment is None or assignment.household_id != household_id:
        raise CommunicationError("only the assigned host can post announcements to this pool")
    if kind == AnnouncementKind.SYSTEM:
        raise CommunicationError("system announcements are generated, not posted")

    text = body.strip() or _default_body(kind)
    announcement = Announcement(
        id=new_id("ann"),
        pool_id=pool_id,
        kind=kind,
        body=text,
        author_household_id=household_id,
    )
    ctx.repo.put_announcement(ctx.ws, announcement)
    ctx.log(
        "announcement_posted",
        f"Host announcement: {text}",
        {"kind": kind.value},
        pool_id=pool_id,
        household_id=household_id,
    )
    return announcement


def _default_body(kind: AnnouncementKind) -> str:
    return {
        AnnouncementKind.HOST_ARRIVED: "I'm here with the order.",
        AnnouncementKind.HOST_RUNNING_LATE: "Running a few minutes late.",
        AnnouncementKind.LOCATION_CHANGED: "The pickup spot has moved — check the pool page.",
        AnnouncementKind.PICKUP_ENDING_SOON: "Pickup is ending soon.",
        AnnouncementKind.HOST_CUSTOM: "Update from your host.",
    }.get(kind, "Update from your host.")


def report_exception(
    *,
    ctx: PoolContext,
    pool_id: str,
    household_id: str,
    kind: ExceptionKind,
    detail: str = "",
) -> dict[str, Any]:
    """A buyer raises a structured exception. Pool resolves what it can (§81).

    Common cases resolve with no human messaging at all. A product problem becomes an
    issue case for operator review rather than a debate at the pickup table. Only what
    is left over opens a private thread with the host.
    """
    from . import fulfillment

    membership = ctx.repo.get_membership(ctx.ws, pool_id, household_id)
    if membership is None:
        raise CommunicationError("only a member of this pool can raise an exception here")

    if kind in _SELF_RESOLVING:
        ctx.log(
            "exception_resolved",
            f"Buyer reported '{kind.value.replace('_', ' ')}' and Pool handled it "
            "without involving anyone",
            {"kind": kind.value},
            pool_id=pool_id,
            household_id=household_id,
        )
        return {
            "kind": kind.value,
            "resolved_automatically": True,
            "response": _SELF_RESOLVING[kind],
            "thread_id": "",
        }

    if kind == ExceptionKind.PROBLEM_WITH_ORDER:
        issue = fulfillment.open_issue(
            ctx=ctx,
            pool_id=pool_id,
            household_id=household_id,
            kind=IssueKind.WRONG_ITEM,
            detail=detail,
        )
        return {
            "kind": kind.value,
            "resolved_automatically": False,
            "response": "Reported for review. You do not need to sort this out with your host.",
            "issue_id": issue.id,
            "thread_id": "",
        }

    thread = open_thread(ctx=ctx, pool_id=pool_id, buyer_household_id=household_id, kind=kind)
    if detail.strip():
        post_message(
            ctx=ctx, thread_id=thread.id, sender_household_id=household_id, body=detail
        )
    return {
        "kind": kind.value,
        "resolved_automatically": False,
        "response": "Your host has been messaged privately.",
        "thread_id": thread.id,
    }


def open_thread(
    *,
    ctx: PoolContext,
    pool_id: str,
    buyer_household_id: str,
    kind: ExceptionKind | None = None,
) -> MessageThread:
    """Open (or reuse) the private buyer ↔ assigned-host thread for one transaction."""
    assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
    if assignment is None:
        raise CommunicationError("this pool has no assigned host to message")
    membership = ctx.repo.get_membership(ctx.ws, pool_id, buyer_household_id)
    if membership is None:
        raise CommunicationError("only a member of this pool can open a thread here")

    existing = ctx.repo.get_thread_for(ctx.ws, pool_id, buyer_household_id)
    if existing is not None:
        if kind is not None and existing.exception_kind is None:
            existing.exception_kind = kind
            ctx.repo.put_thread(ctx.ws, existing)
        return existing

    thread = MessageThread(
        id=new_id("thr"),
        pool_id=pool_id,
        buyer_household_id=buyer_household_id,
        host_household_id=assignment.household_id,
        exception_kind=kind,
    )
    ctx.repo.put_thread(ctx.ws, thread)
    return thread


def post_message(
    *, ctx: PoolContext, thread_id: str, sender_household_id: str, body: str
) -> Message:
    """Post to a transaction-scoped thread.

    Only the two participants may post, and only while the thread is open. This is the
    reason a host cannot DM an arbitrary member: there is no path from "I am a host" to
    "I can message this person" that does not pass through a thread they are already in.
    """
    thread = ctx.repo.get_thread(ctx.ws, thread_id)
    if thread is None:
        raise CoordinationError(f"unknown thread: {thread_id}")
    if sender_household_id not in {thread.buyer_household_id, thread.host_household_id}:
        raise CommunicationError("only the buyer and the assigned host can post in this thread")
    if thread.state != "open":
        raise CommunicationError("this thread has been closed with the transaction")
    text = body.strip()
    if not text:
        raise CommunicationError("an empty message cannot be sent")

    message = Message(
        id=new_id("msg"),
        thread_id=thread_id,
        sender_household_id=sender_household_id,
        body=text[:1000],
        at=iso(ctx.now),
    )
    ctx.repo.put_message(ctx.ws, message)
    return message


def archive_threads_for_pool(*, ctx: PoolContext, pool_id: str) -> int:
    """Close every thread when the transaction ends. Threads are not friendships (§80)."""
    closed = 0
    for thread in ctx.repo.list_threads(ctx.ws, pool_id):
        if thread.state == "open":
            thread.state = "archived"
            ctx.repo.put_thread(ctx.ws, thread)
            closed += 1
    return closed


#: Which lifecycle transitions are worth telling buyers about, and what to say (§78).
_STATUS_ANNOUNCEMENTS: dict[PoolStatus, str] = {
    PoolStatus.HOST_RECRUITING: "Enough people want this to reach the supplier minimum. "
                                "Pool is finding someone to collect and hand out the order.",
    PoolStatus.HOST_SELECTED: "A host has taken the job. Your exact price is being calculated.",
    PoolStatus.FINAL_OFFER: "Your exact final price is ready, including host pay and fees.",
    PoolStatus.LOCKED: "The pool locked and payment has been taken. The order is going in.",
    PoolStatus.PURCHASED: "The order has been placed.",
    PoolStatus.DISTRIBUTING: "Pickup is open. Show your one-time code to collect.",
    PoolStatus.COMPLETED: "This pool is complete. Thanks for pooling.",
    PoolStatus.FAILED: "This pool could not go ahead. Nothing was charged.",
    PoolStatus.EXPIRED: "This pool expired before it could go ahead. Nothing was charged.",
}


def announce_status(*, ctx: PoolContext, pool_id: str, status: PoolStatus) -> Announcement | None:
    """Post the automated update for a lifecycle transition, if one is warranted.

    Deliberately not every transition: a pool that pings buyers at each internal step
    has reproduced the problem the product exists to remove (AGENTS.md §1).
    """
    body = _STATUS_ANNOUNCEMENTS.get(status)
    if body is None:
        return None
    return announce_system(
        ctx=ctx, pool_id=pool_id, body=body, facts={"status": status.value, "kind": "system"}
    )
