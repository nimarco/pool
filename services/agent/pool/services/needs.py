"""Declaring and amending a standing need — the one thing a member actually does.

This is the primary user input of the whole product (AGENTS.md §1). Everything else
Pool does is downstream of it: latent demand is *declared* need that no pool is serving
yet, and the agent's opening move is to look for overlap nobody asked it to find. So
this module is deliberately small and strict rather than a preferences system.

What it is not, and must not become:

* **Not group creation.** A need is a statement about a household, never about a group.
  There is no field here for who else is buying, and adding one would be the product
  failure canonical invariant 1 names.
* **Not a commitment.** Declaring a need touches nobody's card and joins nothing. It
  makes a household *eligible* to be discovered (§26).
* **Not an operator surface.** A member may only write their own declarations, and the
  ownership check is here rather than at the edge so every caller inherits it.

The validation below is domain policy, not input hygiene — the API layer already
type-checks shapes. Each rule exists because the deterministic engines downstream trust
these values: the timing engine decides pull-forward eligibility from
``earliest_acceptable_purchase_date``, and Smart Join compares real money against
``max_spend_cents``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..data import catalog
from ..domain.models import (
    LEFT_PARTICIPATION_STATES,
    MembershipStatus,
    NeedDeclaration,
    SubstitutionPolicy,
    new_id,
)
from .context import PoolContext

#: A member cannot buy more than one cycle ahead of themselves. Pulling forward further
#: would mean restocking before the previous purchase is used, which is storage the
#: household never agreed to — the flexibility window is permission, not a budget (§24).
MAX_FLEXIBILITY_MULTIPLE = 1

#: Bounds on what a standing declaration may say. Wide enough not to argue with a real
#: household, narrow enough that a mistyped field cannot distort the demand pool
#: everybody else's economics are computed from.
MIN_CADENCE_DAYS = 1
MAX_CADENCE_DAYS = 365
MAX_QUANTITY = 100
MAX_MIN_SAVINGS_PCT = 90
MAX_SPEND_CENTS = 500_000
MAX_HORIZON_DAYS = 365


class NeedError(ValueError):
    """A declaration that domain policy will not accept. Carries a human reason."""


@dataclass
class NeedInput:
    """One standing declaration, as a member states it.

    ``flexibility_days`` rather than a raw earliest-purchase date: "how far ahead of
    myself am I willing to buy" is the question a person can actually answer, and the
    date the timing engine needs is derived from it. The two-number split — when you
    next need it, and how early Pool may act — is the whole of the pull-forward
    permission model, so it is stated in the member's terms and converted here.
    """

    household_id: str
    product_id: str
    quantity: int
    cadence_days: int
    expected_next_need_date: date
    flexibility_days: int = 0
    routine_lead_days: int = 7
    min_savings_pct: int = 20
    max_spend_cents: int = 5000
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY
    active: bool = True


def declare_need(*, ctx: PoolContext, community_id: str, data: NeedInput) -> NeedDeclaration:
    """Record a new standing need for one member.

    Refuses a second active declaration for a product the member already declared:
    two rows for one household and one product would be counted twice by matching, and
    the pool would form against demand that does not exist. Amending the existing one is
    the correct action, and the error says so.
    """
    _validate(ctx, community_id, data)
    existing = _active_for_product(ctx, data.household_id, data.product_id)
    if existing is not None:
        raise NeedError(
            "You already have a standing need for this item. Change that one instead of "
            "adding a second — two declarations would count your demand twice."
        )

    need = NeedDeclaration(
        id=new_id("need"),
        household_id=data.household_id,
        community_id=community_id,
        product_id=data.product_id,
        quantity=data.quantity,
        cadence_days=data.cadence_days,
        expected_next_need_date=data.expected_next_need_date,
        earliest_acceptable_purchase_date=(
            data.expected_next_need_date - timedelta(days=data.flexibility_days)
        ),
        latest_acceptable_purchase_date=data.expected_next_need_date,
        routine_lead_days=data.routine_lead_days,
        min_savings_pct=data.min_savings_pct,
        max_spend_cents=data.max_spend_cents,
        substitution=data.substitution,
        active=data.active,
    )
    ctx.repo.put_need(ctx.ws, need)
    ctx.log(
        "need_declared",
        f"{_member_name(ctx, data.household_id)} declared a standing need for "
        f"{_product_name(ctx, data.product_id)}",
        {
            "need_id": need.id,
            "household_id": need.household_id,
            "product_id": need.product_id,
            "quantity": need.quantity,
            "cadence_days": need.cadence_days,
            "flexibility_days": need.flexibility_days,
        },
    )
    return need


def amend_need(
    *, ctx: PoolContext, community_id: str, need_id: str, data: NeedInput
) -> NeedDeclaration:
    """Change an existing declaration.

    The ownership check is the security boundary of this module: ``household_id`` on the
    input must match the stored declaration, so supplying your own id does not let you
    rewrite somebody else's rules. There is no account authentication in this build
    (``docs/PILOT_READINESS.md``), which is exactly why the check that *is* available is
    enforced in the service rather than trusted to a caller.
    """
    need = ctx.repo.get_need(ctx.ws, need_id)
    if need is None:
        raise NeedError("that need no longer exists")
    if need.household_id != data.household_id:
        raise NeedError("a need can only be changed by the member who declared it")
    _validate(ctx, community_id, data)

    clash = _active_for_product(ctx, data.household_id, data.product_id)
    if clash is not None and clash.id != need.id:
        raise NeedError(
            "You already have a standing need for that item, so this one cannot be "
            "changed to match it."
        )

    # A declaration that is already in a pool is the *reason* that member is in it —
    # `Membership.need_id` is the stored lineage every consumer surface reads to answer
    # "why am I in this". Re-pointing it at another product would leave the record
    # saying somebody joined a whey order because they buy coffee, while the units,
    # the price and the authorisation all stayed exactly as they were. Every other
    # field on the declaration stays amendable.
    if data.product_id != need.product_id:
        pooled = _pool_holding(ctx, need.id)
        if pooled:
            raise NeedError(
                "Pool is already coordinating this declaration, so the item cannot be "
                "changed. Leave that pool first, or add a separate declaration."
            )

    need.product_id = data.product_id
    need.quantity = data.quantity
    need.cadence_days = data.cadence_days
    need.expected_next_need_date = data.expected_next_need_date
    need.earliest_acceptable_purchase_date = data.expected_next_need_date - timedelta(
        days=data.flexibility_days
    )
    need.latest_acceptable_purchase_date = data.expected_next_need_date
    need.routine_lead_days = data.routine_lead_days
    need.min_savings_pct = data.min_savings_pct
    need.max_spend_cents = data.max_spend_cents
    need.substitution = data.substitution
    need.active = data.active
    ctx.repo.put_need(ctx.ws, need)
    ctx.log(
        "need_amended",
        f"{_member_name(ctx, need.household_id)} changed their standing need for "
        f"{_product_name(ctx, need.product_id)}",
        {
            "need_id": need.id,
            "household_id": need.household_id,
            "product_id": need.product_id,
            "quantity": need.quantity,
            "flexibility_days": need.flexibility_days,
            "active": need.active,
        },
    )
    return need


# --------------------------------------------------------------------------- rules


def _validate(ctx: PoolContext, community_id: str, data: NeedInput) -> None:
    household = ctx.repo.get_household(ctx.ws, data.household_id)
    if household is None:
        raise NeedError("unknown member")

    membership = ctx.repo.get_community_membership(ctx.ws, community_id, data.household_id)
    if membership is None or membership.status != MembershipStatus.VERIFIED:
        # Community membership is the trust boundary pools form inside (§2). Demand from
        # outside it must not reach an opportunity assessment.
        raise NeedError("only a verified member of this community can declare a need")

    if not _ensure_product(ctx, data.product_id):
        raise NeedError("unknown product")

    if not 1 <= data.quantity <= MAX_QUANTITY:
        raise NeedError(f"quantity must be between 1 and {MAX_QUANTITY}")

    if not MIN_CADENCE_DAYS <= data.cadence_days <= MAX_CADENCE_DAYS:
        raise NeedError(
            f"how often you restock must be between {MIN_CADENCE_DAYS} and "
            f"{MAX_CADENCE_DAYS} days"
        )

    today = ctx.now.date()
    if data.expected_next_need_date < today:
        raise NeedError("the date you next need this cannot be in the past")
    if data.expected_next_need_date > today + timedelta(days=MAX_HORIZON_DAYS):
        raise NeedError("that date is too far ahead to plan a purchase against")

    if data.flexibility_days < 0:
        raise NeedError("how early Pool may buy cannot be negative")
    if data.flexibility_days > data.cadence_days * MAX_FLEXIBILITY_MULTIPLE:
        raise NeedError(
            "Pool cannot buy more than one full cycle early — that would restock you "
            "before you have used what you have."
        )

    if not 0 <= data.min_savings_pct <= MAX_MIN_SAVINGS_PCT:
        raise NeedError(f"the saving you require must be between 0 and {MAX_MIN_SAVINGS_PCT}%")

    if not 1 <= data.max_spend_cents <= MAX_SPEND_CENTS:
        raise NeedError("that spending limit is outside the range this demo accepts")

    if data.routine_lead_days < 0 or data.routine_lead_days > data.cadence_days:
        raise NeedError("how far ahead you normally restock must fit inside one cycle")


def _ensure_product(ctx: PoolContext, product_id: str) -> bool:
    """Make sure the workspace holds the product this declaration names.

    The bundled catalogue is a few hundred consumer identities; a workspace holds only
    the handful anyone has actually declared. Writing all of them into every workspace
    would mean hundreds of stores per reset for rows nobody will ever reference, so a
    product is materialised the first time a member declares against it — which is also
    the first moment Pool has any reason to hold it.

    The catalogue supplies identity only. ``substitute_group`` comes across exactly as
    the curated snapshot recorded it, so an entry from an unreviewed category arrives
    with none and can then combine with nothing but itself (§21). Nothing here invents
    a price, a case size, or a supplier: a member may declare a need for something Pool
    cannot yet source, and the pool simply never forms until an offer exists.
    """
    if ctx.repo.get_product(ctx.ws, product_id) is not None:
        return True
    entry = catalog.get(product_id)
    if entry is None:
        return False
    ctx.repo.put_product(ctx.ws, entry.to_product())
    return True


def _pool_holding(ctx: PoolContext, need_id: str) -> str:
    """The live pool this declaration put its owner into, if there is one."""
    for pool in ctx.repo.list_pools(ctx.ws):
        for m in ctx.repo.list_memberships(ctx.ws, pool.id):
            if m.need_id == need_id and m.state not in LEFT_PARTICIPATION_STATES:
                return pool.id
    return ""


def _active_for_product(
    ctx: PoolContext, household_id: str, product_id: str
) -> NeedDeclaration | None:
    return next(
        (
            n
            for n in ctx.repo.list_needs(ctx.ws)
            if n.active and n.household_id == household_id and n.product_id == product_id
        ),
        None,
    )


def _member_name(ctx: PoolContext, household_id: str) -> str:
    household = ctx.repo.get_household(ctx.ws, household_id)
    return household.display_name if household else household_id


def _product_name(ctx: PoolContext, product_id: str) -> str:
    product = ctx.repo.get_product(ctx.ws, product_id)
    return product.name if product else product_id


def declared_as(ctx: PoolContext, need: NeedDeclaration) -> str:
    """What the member should see this declaration called.

    A group declaration stores an exemplar ``product_id`` so the membership lineage keeps
    resolving to a real product, but the member said "coffee" and never saw the exemplar.
    Showing them "Pike Place Medium Roast" on their own list would be Pool telling them
    what they declared, and it is the exemplar's only visible consequence — so this is the
    one place that decides, and every surface reads it.

    Falls back to the product name whenever the family cannot be resolved, so a
    declaration is never nameless.
    """
    product = ctx.repo.get_product(ctx.ws, need.product_id)
    if need.substitution == SubstitutionPolicy.GROUP_DECLARED and product is not None:
        family = catalog.group(product.substitute_group)
        if family is not None:
            return family.label
    return product.name if product else ""


def need_view(ctx: PoolContext, need: NeedDeclaration) -> dict[str, Any]:
    """One declaration, shaped for the client. Mirrors the rows ``/api/needs`` serves."""
    product = ctx.repo.get_product(ctx.ws, need.product_id)
    return {
        "need_id": need.id,
        "household_id": need.household_id,
        "product_id": need.product_id,
        "product_name": declared_as(ctx, need),
        #: The exact product behind a family declaration, for a surface that needs to say
        #: what an order actually bought. Empty when the member named the product.
        "declared_family": (
            product.substitute_group
            if product is not None
            and need.substitution == SubstitutionPolicy.GROUP_DECLARED
            else ""
        ),
        "unit": product.unit if product else "",
        "quantity": need.quantity,
        "cadence_days": need.cadence_days,
        "expected_next_need_date": need.expected_next_need_date.isoformat(),
        "flexibility_days": need.flexibility_days,
        "routine_lead_days": need.routine_lead_days,
        "min_savings_pct": need.min_savings_pct,
        "max_spend_cents": need.max_spend_cents,
        "substitution": need.substitution.value,
        "active": need.active,
    }
