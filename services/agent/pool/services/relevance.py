"""What, out of everything Pool is doing, is genuinely *this member's*.

Pool coordinates a whole Community. One coordination run reads every standing
declaration in it and may legitimately form a pool that has nothing to do with the
person who happens to be looking at the screen — that is the product working, not
failing. What is *not* allowed is for a consumer surface to present that pool as
theirs.

This module is the one place that decides the difference. It exists because the answer
used to be inferred, in the browser, from "the first pool in the workspace" — which is
how a member who declared coffee was shown a whey protein order formed out of ten other
students' declarations (#0031).

The rule, derived from the domain rather than invented here
-----------------------------------------------------------

A pool is this member's when **all** of these hold:

1. it is in the Community this member is a verified part of — the boundary pools form
   inside (§2, ``domain.matching``);
2. there is a ``Membership`` row joining that household to that pool. Membership is the
   only thing in the model that means "this person is in this pool"; it is what the
   allocation, the price, the authorisation and the pickup credential all key off;
3. that membership is in a state where the member is still in it —
   :data:`~pool.domain.models.LIVE_PARTICIPATION_STATES`. Declining or withdrawing ends
   the relationship; a *failed* authorisation does not, because that member is exactly
   the person who needs to be told;
4. the membership's ``need_id`` resolves to a declaration that household actually made.
   Membership already carries that link, so lineage is read rather than guessed: the
   answer to "which of my declarations put me in here" is a stored field, never a
   product-name or timestamp heuristic.

Nothing about product identity is re-decided here. Whether this member's declaration
could be served by the pool's product was settled by ``domain.substitution`` at the
moment they were matched, and re-litigating it at read time would let a later change to
their preferences retroactively erase an order they are already funding.

And the outlook
---------------

When none of a member's declarations is in a pool, "nothing yet" is a real answer, but
an unexplained one. :func:`need_outlook` runs the *same* deterministic opportunity
evaluator the coordinator's tools use and reports what it found for that one
declaration — a supplier minimum still short, no bulk supplier at all, a substitution
rule the community's demand does not satisfy. It creates nothing and commits nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..domain.models import (
    LIVE_PARTICIPATION_STATES,
    Membership,
    NeedDeclaration,
    Pool,
    PoolStatus,
)
from . import coordination as coord
from . import discovery
from . import needs as needs_service
from .context import PoolContext

#: Ordering for the pool a member is shown first when they are in more than one. Pools
#: that still need something from them come before pools that are merely progressing,
#: and anything finished or failed comes last — a completed order is a record, not an
#: opportunity.
_STATUS_RANK: dict[PoolStatus, int] = {
    PoolStatus.FINAL_OFFER: 0,
    PoolStatus.FUNDING: 1,
    PoolStatus.RECOVERING: 2,
    PoolStatus.DISTRIBUTING: 3,
    PoolStatus.PURCHASED: 4,
    PoolStatus.PURCHASE_READY: 5,
    PoolStatus.LOCKED: 6,
    PoolStatus.HOST_SELECTED: 7,
    PoolStatus.HOST_RECRUITING: 8,
    PoolStatus.FORMING: 9,
    PoolStatus.COMPLETED: 10,
    PoolStatus.FAILED: 11,
    PoolStatus.EXPIRED: 12,
}


@dataclass(frozen=True)
class PersonalPool:
    """One pool that genuinely belongs to one member, and the declaration behind it."""

    pool: Pool
    membership: Membership
    need: NeedDeclaration
    #: What the member typed, when the pool is buying something else. Empty when the
    #: pool's product *is* what they declared.
    declared_product_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool.id,
            "status": self.pool.status.value,
            "product_id": self.pool.product_id,
            "participation_state": self.membership.state.value,
            "units": self.membership.allocated_units,
            # The lineage, as a stored field rather than an inference: this declaration
            # is why this member is in this pool.
            "need_id": self.need.id,
            "declared_product_id": self.need.product_id,
            # False means the pool is buying an *authorised substitute*. The card shows
            # the pool's product and its photograph, so the interface has to be able to
            # say that it is not the thing this member typed — otherwise the name and
            # the image silently disagree with the declaration behind them (§21).
            "is_exact_product": self.membership.is_exact_product,
            "declared_product_name": self.declared_product_name,
        }


def personal_pools(
    ctx: PoolContext, community_id: str, household_id: str
) -> list[PersonalPool]:
    """Every pool this member is genuinely in, most worth their attention first.

    Read-only. Returns an empty list rather than a fallback: "no pool of yours exists"
    is a first-class answer, and substituting somebody else's is the bug this module
    was written to remove.
    """
    if not household_id:
        return []
    needs = {n.id: n for n in ctx.repo.list_needs(ctx.ws) if n.household_id == household_id}
    out: list[PersonalPool] = []
    for pool in ctx.repo.list_pools(ctx.ws):
        if pool.community_id != community_id:
            continue
        membership = ctx.repo.get_membership(ctx.ws, pool.id, household_id)
        if membership is None or membership.state not in LIVE_PARTICIPATION_STATES:
            continue
        # No lineage, no claim. A membership whose need_id names a declaration this
        # household does not hold cannot be explained to them, so it is not shown to
        # them as theirs.
        need = needs.get(membership.need_id)
        if need is None:
            continue
        declared = ctx.repo.get_product(ctx.ws, need.product_id)
        out.append(
            PersonalPool(
                pool=pool,
                membership=membership,
                need=need,
                declared_product_name=(
                    declared.name
                    if declared and declared.id != pool.product_id
                    else ""
                ),
            )
        )
    out.sort(key=lambda p: (_STATUS_RANK.get(p.pool.status, 99), p.pool.created_at, p.pool.id))
    return out


def personal_pool(
    ctx: PoolContext, community_id: str, household_id: str
) -> PersonalPool | None:
    """The one pool a consumer surface may lead with, or ``None``."""
    found = personal_pools(ctx, community_id, household_id)
    return found[0] if found else None


# ------------------------------------------------------------ read-only pass


class _ReadCache:
    """Memoises repository *reads* for the duration of one read-only pass.

    :func:`need_outlook` calls ``evaluate_opportunity`` once per (sourceable product ×
    public pickup site), and every one of those re-reads the whole need table, the
    household table, the product table, the offer table and the community memberships.
    Against DynamoDB each of those is a Query, and one member view was costing four
    times what ``/api/state`` costs — for an answer that cannot change while it is being
    computed.

    Safe precisely because the pass is read-only by construction: ``evaluate_opportunity``
    creates nothing and commits nothing (its own contract, asserted by
    ``test_agent_effects.py`` snapshotting the workspace around it), and
    ``test_a_member_view_writes_nothing`` pins that the endpoint using this changes no
    row. Anything that is not a ``list_``/``get_`` call — every write — is handed to the
    real repository untouched rather than being cached or blocked, so a future caller
    that does write still works; it simply must not do so inside this pass.
    """

    def __init__(self, repo: Any) -> None:
        self._repo = repo
        self._memo: dict[tuple, Any] = {}

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._repo, name)
        if not name.startswith(("list_", "get_")) or not callable(target):
            return target

        def cached(*args: Any, **kwargs: Any) -> Any:
            if kwargs:
                return target(*args, **kwargs)
            key = (name, args)
            if key not in self._memo:
                self._memo[key] = target(*args)
            return self._memo[key]

        return cached


def read_only(ctx: PoolContext) -> PoolContext:
    """``ctx`` with its repository reads memoised. For read-only passes only."""
    return replace(ctx, repo=_ReadCache(ctx.repo))


# ------------------------------------------------------------------ outlook


#: What Pool can currently say about one standing declaration.
OUTLOOK_IN_POOL = "in_pool"          # already being coordinated
OUTLOOK_READY = "ready"              # a worthwhile pool could form now
OUTLOOK_SHORT = "short"              # compatible demand exists, not enough of it
OUTLOOK_NO_SUPPLY = "no_supply"      # nothing to buy in bulk at any quantity
OUTLOOK_NOT_MATCHED = "not_matched"  # the demand that exists cannot serve this member
OUTLOOK_RETIRED = "retired"          # the member stopped buying it
OUTLOOK_NOT_WORTH_IT = "not_worth_it"  # demand is there; pooling it saves nothing
OUTLOOK_NOT_IN_ROUND = "not_in_round"  # a round formed for it, without these units
#: Worth doing, and this member's units did not fit the last whole case. Split out from
#: ``not_matched`` because they are opposite news wearing the same word: a matcher
#: rejection means nothing near you can serve this, and a case boundary means the order
#: happened and was full. Telling somebody whose neighbours just bought the thing they
#: wanted that "nothing nearby fits" is the single most misleading sentence Pool had.
OUTLOOK_CASE_BOUNDARY = "case_boundary"


#: The five words a member is ever shown for the state of one thing they buy.
#:
#: There are far more deterministic outcomes than five, and every one of them stays
#: readable — as the *reason* underneath. What was wrong was making the member learn a
#: new sentence per outcome: seven near-identical paragraphs, each having to be read in
#: full before it could be told apart from the other six. A short status they already
#: understand, plus the specific fact, says the same thing and can be scanned.
#:
#: Decided here because a screen must not re-derive it. Home, the item list and the
#: order surfaces all read the same field, so they cannot disagree about whether Pool is
#: waiting on somebody — which is the class of contradiction this grammar exists to make
#: impossible.
STATUS_NEEDS_YOU = "needs_you"          # one question, already worked out
STATUS_COORDINATING = "coordinating"    # an order exists and is moving
STATUS_READY = "ready_to_collect"       # the pickup window is open
STATUS_WATCHING = "watching"            # standing, and nothing to do about it yet
STATUS_DONE = "done"                    # collected and reconciled

CONSUMER_STATUSES = (
    STATUS_NEEDS_YOU,
    STATUS_COORDINATING,
    STATUS_READY,
    STATUS_WATCHING,
    STATUS_DONE,
)

#: Short label for *why* a watching declaration is watching. Four or five words, so it
#: can sit on the row rather than in a paragraph under it. The full sentence stays in
#: ``NeedOutlook.reason``, which is what a member reads when they want the detail.
#:
#: ``not_in_round`` and the case-boundary case are deliberately different sentences from
#: ``short``. "Not enough demand" is technically true of what is *left* after an order
#: formed, and it is the wrong thing to tell somebody whose neighbours just bought the
#: thing they wanted.
_WATCHING_HEADLINES = {
    OUTLOOK_NO_SUPPLY: "No verified supplier yet",
    OUTLOOK_SHORT: "Not enough demand yet",
    OUTLOOK_NOT_WORTH_IT: "Supplier found — not cheaper",
    OUTLOOK_NOT_IN_ROUND: "An order filled without your units",
    OUTLOOK_CASE_BOUNDARY: "An order filled without your units",
    OUTLOOK_NOT_MATCHED: "Nothing nearby fits this one",
    OUTLOOK_RETIRED: "Paused by you",
    OUTLOOK_READY: "Worth doing — Pool has not run yet",
}


def consumer_status(outlook_state: str) -> str:
    """The member-facing status for one outlook state.

    ``in_pool`` is the only outlook that is not watching, and the order's own lifecycle
    then decides between coordinating, needing an answer, and ready to collect — which
    is a fact about the pool, not about the declaration, so it is resolved where the pool
    is read rather than guessed here.
    """
    if outlook_state == OUTLOOK_IN_POOL:
        return STATUS_COORDINATING
    return STATUS_WATCHING


def watching_headline(outlook_state: str) -> str:
    """The short reason a watching declaration is watching."""
    return _WATCHING_HEADLINES.get(outlook_state, "Pool is watching this")


@dataclass(frozen=True)
class NeedOutlook:
    """Why one declaration has not produced a pool, in facts the member can check."""

    need_id: str
    product_id: str
    product_name: str
    state: str
    reason: str
    pool_id: str = ""
    units_needed: int = 0
    units_available: int = 0
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "state": self.state,
            "reason": self.reason,
            "pool_id": self.pool_id,
            "units_needed": self.units_needed,
            "units_available": self.units_available,
            # The consumer grammar, decided here so no screen re-derives it. ``state``
            # stays exactly what it was — the deterministic outcome every test and the
            # operator surfaces read — and these two are the reading of it.
            "status": consumer_status(self.state),
            "headline": watching_headline(self.state),
            **({"detail": self.detail} if self.detail else {}),
        }


def _rejection_for(assessment, need_id: str) -> str:
    """Why *this declaration* was left out, keyed on the need rather than the member.

    A household can hold several declarations, and the matcher rejects each one
    separately. Keying on ``household_id`` returned whichever of their needs happened to
    be rejected first, which is how a paper-towel declaration ended up explained by a
    coffee one.
    """
    for row in assessment.rejected:
        if row.get("need_id") == need_id:
            raw = str(row.get("reason", ""))
            return raw.split(":", 1)[1].strip() if ":" in raw else raw
    return ""


def need_outlook(
    ctx: PoolContext,
    community_id: str,
    need: NeedDeclaration,
    *,
    in_pool: dict[str, str] | None = None,
) -> NeedOutlook:
    """What Pool can currently do about one standing declaration, and why.

    Uses ``coordination.evaluate_opportunity`` — the same read-only evaluator the
    agent's ``evaluate_pool_economics`` tool calls — so the sentence a member reads and
    the verdict the coordinator acts on come from one implementation. Evaluated at every
    public pickup site in the Community and reported at the most favourable one, because
    "no site works" and "one site works" are different answers and only the second is
    worth telling somebody about.

    Creates nothing, contacts nobody, commits no money.
    """
    # What the member called it, which for a family declaration is the family.
    name = needs_service.declared_as(ctx, need) or need.product_id

    def outlook(state: str, reason: str, best=None, pool_id: str = "") -> NeedOutlook:
        return NeedOutlook(
            need_id=need.id,
            product_id=need.product_id,
            product_name=name,
            state=state,
            reason=reason,
            pool_id=pool_id,
            units_needed=best.minimum_units if best else 0,
            units_available=best.matched_units if best else 0,
        )

    pooled = (in_pool or {}).get(need.id, "")
    if pooled:
        return outlook(OUTLOOK_IN_POOL, "Pool is already coordinating this one.", pool_id=pooled)

    if not need.active:
        return outlook(OUTLOOK_RETIRED, "You retired this declaration, so Pool leaves it alone.")

    targets = coord.sourceable_targets(ctx, need.product_id)
    if not targets:
        # Missing supply is not missing demand, and the sentence has to put them in that
        # order. Pool holds no verified bulk offer for this product or any substitute,
        # so there is genuinely nothing to evaluate — but the compatible demand standing
        # behind the declaration is a fact Pool already knows, and reporting it as
        # nothing was the more misleading of the two available errors.
        #
        # ``units_needed`` stays 0 on purpose. It means "the supplier will not sell
        # fewer than this", and no supplier has said anything.
        standing = discovery.unsourced_demand(ctx, community_id, need)
        others = standing.other_members
        unit = _unit_word(ctx, need.product_id, standing.other_units)
        return NeedOutlook(
            need_id=need.id,
            product_id=need.product_id,
            product_name=name,
            state=OUTLOOK_NO_SUPPLY,
            reason=(
                f"{others} other {'member' if others == 1 else 'members'} near you "
                f"already buy this — {standing.other_units} {unit} standing. No "
                "supplier Pool has verified sells it in bulk yet, so there is nothing "
                "to price a group order against."
                if others
                else "No supplier Pool has verified sells this in bulk yet."
            ),
            units_available=standing.units,
        )

    # A round that has already formed for this product, without this member in it. Said
    # plainly, because "not enough demand" is technically true of what is *left* and
    # completely misses what actually happened: the case filled, and their units were
    # not among the ones that fitted (§48).
    formed = _round_already_formed(ctx, community_id, targets, need.household_id)
    if formed:
        return outlook(
            OUTLOOK_NOT_IN_ROUND,
            "A group order for this has already formed, and it filled to a whole case "
            "without your units. Your declaration stays standing for the next one.",
            pool_id=formed,
        )

    sites = [
        s
        for s in ctx.repo.list_sites(ctx.ws)
        if s.is_public and s.community_id == community_id
    ]
    best = None
    best_rank: tuple = ()
    for target in targets:
        # The same exclusion the coordinator's own tools apply: demand already inside a
        # live pool for this product is spoken for. Without it, a member trimmed off a
        # case boundary would be told there was "enough demand" for a pool that had
        # already formed out of it.
        already = frozenset(coord.pooled_household_ids(ctx, community_id, target))
        for site in sites:
            assessment = coord.evaluate_opportunity(
                ctx=ctx,
                community_id=community_id,
                product_id=target,
                pickup_site_id=site.id,
                include_future_demand=True,
                exclude_household_ids=already,
            )
            included = any(c.need_id == need.id for c in assessment.candidates)
            rank = (
                assessment.viable and included,
                not _rejection_for(assessment, need.id),
                assessment.matched_units,
            )
            if best is None or rank > best_rank:
                best, best_rank = assessment, rank

    if best is None:
        return outlook(
            OUTLOOK_NO_SUPPLY, "This community has no public pickup point yet."
        )

    included = any(c.need_id == need.id for c in best.candidates)
    if best.viable and included:
        return outlook(
            OUTLOOK_READY,
            "Enough compatible demand exists — Pool can form this one.",
            best,
        )

    excluded = _rejection_for(best, need.id)
    if excluded:
        return outlook(OUTLOOK_NOT_MATCHED, plain_reason(excluded), best)

    if best.reason_code == coord.REASON_NOT_CHEAPER:
        # Enough demand, and it still should not happen. The bulk tier barely beats
        # retail, and once a fulfiller's pay, processing and Pool's own fee are counted
        # the saving is gone — so the correct behaviour is to bother nobody (§1).
        return outlook(
            OUTLOOK_NOT_WORTH_IT,
            "There is enough demand, but buying it together would not actually be "
            "cheaper once collection and fees are counted.",
            best,
        )

    if best.viable:
        # Compatible and in range, but the order filled to a whole case without these
        # units. Pool does not buy stock nobody ordered, so the boundary decides who is
        # in this round (§48).
        return outlook(
            OUTLOOK_CASE_BOUNDARY,
            "There is a group order for this, but it filled to a whole case without "
            "your units this time.",
            best,
        )

    unit = _unit_word(ctx, need.product_id, best.minimum_units)
    return outlook(
        OUTLOOK_SHORT,
        (
            f"Not enough of it yet: {best.matched_units} {unit} declared nearby, and the "
            f"supplier will not sell fewer than {best.minimum_units}."
            if best.minimum_units
            else "Not enough compatible demand nearby yet."
        ),
        best,
    )


def _round_already_formed(
    ctx: PoolContext, community_id: str, targets: list[str], household_id: str
) -> str:
    """A live pool for one of these products that this member is *not* in."""
    for pool in ctx.repo.list_pools(ctx.ws):
        if pool.community_id != community_id or pool.product_id not in targets:
            continue
        if pool.status in {PoolStatus.FAILED, PoolStatus.EXPIRED}:
            continue
        membership = ctx.repo.get_membership(ctx.ws, pool.id, household_id)
        if membership is None or membership.state not in LIVE_PARTICIPATION_STATES:
            return pool.id
    return ""


def _unit_word(ctx: PoolContext, product_id: str, count: int) -> str:
    product = ctx.repo.get_product(ctx.ws, product_id)
    unit = product.unit if product else "unit"
    return unit if count == 1 else f"{unit}s"


#: Matcher rejection reasons, in the member's words. Anything unmapped is passed
#: through as the matcher wrote it rather than replaced with a guess.
_PLAIN_REASONS = {
    "member accepts the exact product only": (
        "The demand near you is for a different product, and you asked for this exact "
        "one only."
    ),
    "different product family": "Nothing compatible has been declared nearby.",
    "different brand requires broader authority": (
        "The demand near you is another brand, and you allowed only this one."
    ),
    "different category": "The demand near you is in a different category.",
    "outside_radius": "The demand for this is too far from any pickup point you would use.",
    "already_in_pool": "Pool is already coordinating this one.",
    "community_membership_not_verified": "Your community membership is not verified yet.",
}


def plain_reason(reason: str) -> str:
    """A matcher rejection reason, in the member's words. Shared with the run report,
    so the sentence explaining an exclusion is the same wherever it is read."""
    if not reason:
        return ""
    if reason in _PLAIN_REASONS:
        return _PLAIN_REASONS[reason]
    if reason.startswith("timing"):
        return "You do not need this soon enough to be worth buying now."
    return reason
