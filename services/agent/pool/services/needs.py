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

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..data import catalog, product_facts
from ..domain.attributes import (
    AttributeConstraint,
    ConstraintError,
    check_product_attributes,
    validate_constraint,
)
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
    #: The typed rule an ``ATTRIBUTE_CONSTRAINED`` declaration carries. Required by that
    #: policy and refused by every other, so a caller cannot attach attribute authority
    #: to a declaration whose stated policy is something narrower.
    attribute_policy: AttributeConstraint | None = None
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
        attribute_policy=data.attribute_policy,
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
    need.attribute_policy = data.attribute_policy
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

    _validate_attribute_policy(ctx, data)

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


def _validate_attribute_policy(ctx: PoolContext, data: NeedInput) -> None:
    """Accept a constrained declaration only when it can actually decide something.

    Four refusals, and each one closes a way of ending up with a policy that reads as a
    restriction and behaves as something else:

    * a constrained declaration with no policy would authorise nothing at all, silently;
    * a policy attached to any other declaration would be authority nobody's stated rule
      accounts for — the matcher would ignore it today and might not tomorrow;
    * a policy the shipped schema does not accept (unknown attribute, unknown value,
      superseded version, no hard rule) can never match anything, and the member should
      be told that now rather than discovering it as silence;
    * a policy whose family is not the declared product's family, or that the declared
      product itself fails, is a contradiction — the row's own exemplar would be refused
      by the rule attached to it, which is how a member ends up believing they declared
      something they did not.

    The last one is a check at the edge, not a guarantee. Facts get re-curated, so the
    evaluator re-derives the answer on every match rather than trusting that this ran.
    """
    policy = data.attribute_policy
    constrained = data.substitution == SubstitutionPolicy.ATTRIBUTE_CONSTRAINED
    if constrained and policy is None:
        raise NeedError(
            "a declaration with product requirements has to say what they are"
        )
    if policy is None:
        return
    if not constrained:
        raise NeedError(
            "product requirements only apply to a declaration that states them as its rule"
        )

    schema = ctx.product_facts.family_schema(policy.family)
    try:
        validate_constraint(policy, schema)
    except ConstraintError as exc:
        raise NeedError(str(exc)) from exc

    product = ctx.repo.get_product(ctx.ws, data.product_id)
    if product is None or product.substitute_group != policy.family:
        raise NeedError("those requirements do not describe the item you chose")

    check = check_product_attributes(
        product_id=product.id,
        product_family=product.substitute_group,
        constraint=policy,
        source=ctx.product_facts,
    )
    if not check.ok:
        raise NeedError("the item you chose does not meet the requirements you set")


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
        #: The member's typed product requirements, exactly as stored — server-owned,
        #: never re-derived by a client, and ``None`` for every declaration that has
        #: none. Emitted rather than summarised because the whole claim of the
        #: constrained policy is that a person can check what Pool was told.
        "attribute_policy": (
            need.attribute_policy.to_dict() if need.attribute_policy else None
        ),
        "active": need.active,
    }


# ------------------------------------------------------- product-specific preferences
#
# What a member is *asked* about a product, and what their answers deterministically
# mean. Both ends are authoritative: the dimensions come from the curated family schema
# (§21) and the wording from the curated question table beside it, so nothing at runtime —
# least of all a model — decides either what may be asked or what an answer implies.


class Flexibility:
    """The one question every declaration answers, in the member's own terms."""

    #: This exact product and nothing else. The default, everywhere.
    EXACT = "exact"
    #: Similar products are acceptable, subject to the answers below.
    SIMILAR = "similar"


@dataclass
class PreferenceAnswers:
    """A member's answers, as the form collects them.

    ``keep`` is the set of attributes they insist stay as they are on the product they
    picked; ``accept`` maps an attribute to every value they would be happy with. Both
    are answers about *this* product, which is why neither carries a value the member
    would have had to look up.
    """

    flexibility: str = Flexibility.EXACT
    keep: tuple[str, ...] = ()
    accept: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


def preference_questions(ctx: PoolContext, product_id: str) -> dict[str, Any]:
    """What this product can be asked about, in consumer language.

    Only attributes the *selected product* carries a **verified** fact for. Asking
    somebody to insist on a value Pool cannot establish would build a rule that refuses
    everything; asking about a fact nobody has confirmed would be asking them to guess.
    A product outside any curated family yields no questions at all, and the form then
    offers exact-only — which is what Pool can actually honour for it.
    """
    product = ctx.repo.get_product(ctx.ws, product_id)
    if product is None:
        return {"family": "", "schema_version": 0, "questions": []}
    schema = ctx.product_facts.family_schema(product.substitute_group)
    if schema is None:
        return {"family": "", "schema_version": 0, "questions": []}

    facts = ctx.product_facts.facts_for(product_id)
    questions: list[dict[str, Any]] = []
    for definition in schema.attributes:
        fact = facts.get(definition.key)
        if fact is None or not fact.is_authoritative:
            continue
        question = product_facts.question_for(definition.key)
        if question is None:
            continue
        value_label = product_facts.label_for(definition.key, fact.value)
        questions.append(
            {
                "attribute": definition.key,
                "kind": question.kind,
                "prompt": question.prompt.replace("{value}", value_label.lower()),
                "hint": question.hint,
                "product_value": fact.value,
                "product_value_label": value_label,
                "options": [
                    {
                        "value": value,
                        "label": product_facts.label_for(definition.key, value),
                    }
                    for value in sorted(definition.allowed_values)
                ],
            }
        )
    return {
        "family": schema.family,
        "schema_version": schema.version,
        "product_id": product_id,
        "questions": questions,
    }


def policy_from_answers(
    ctx: PoolContext, product_id: str, answers: PreferenceAnswers
) -> tuple[SubstitutionPolicy, AttributeConstraint | None]:
    """Turn what a member said into what Pool is allowed to buy. Deterministic.

    **Every default is the narrowest reading.** That is the whole rule, and it is why
    this function exists rather than the browser assembling a policy:

    * exact-only is the default and produces no attribute policy at all;
    * an attribute the member was asked to keep and did not answer stays kept, because
      unanswered is not consent to change it;
    * an attribute whose acceptable values they did not choose is required to match the
      product they picked, which is the narrowest rule that can be written;
    * a value outside the curated schema, or an attribute the product carries no
      verified fact for, is simply not expressible — ``validate_constraint`` refuses it
      downstream and the member is told, rather than having their rule quietly widened.

    An answer can therefore only ever *widen* by being given explicitly. Omitting one
    never does.
    """
    if answers.flexibility != Flexibility.SIMILAR:
        return SubstitutionPolicy.EXACT_ONLY, None

    offered = preference_questions(ctx, product_id)
    if not offered["questions"]:
        # Nothing about this product can be constrained deterministically, so "similar is
        # fine" has no expressible meaning. Exact-only is the honest answer, and it is
        # narrower than the alternative rather than wider.
        return SubstitutionPolicy.EXACT_ONLY, None

    keep = set(answers.keep)
    requires: dict[str, frozenset[str]] = {}
    for question in offered["questions"]:
        attribute = question["attribute"]
        own = question["product_value"]
        if question["kind"] == product_facts.QUESTION_KIND_KEEP:
            # Unanswered means kept. The member was shown a checked box; unchecking it is
            # the deliberate act, and treating silence as "anything goes" would broaden a
            # rule nobody widened.
            if attribute in keep or attribute not in answers.accept:
                requires[attribute] = frozenset({own})
            continue
        chosen = tuple(answers.accept.get(attribute, ()))
        requires[attribute] = frozenset(chosen) if chosen else frozenset({own})

    return SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, AttributeConstraint(
        family=offered["family"],
        schema_version=int(offered["schema_version"]),
        requires=requires,
    )
