"""Which products deserve investigation, and on whose behalf.

Discovery is the step before evaluation: it reads the Community's standing declarations
and proposes what is worth costing. ``coordination.evaluate_opportunity`` then decides
whether any of it is actually worthwhile.

Two things live here because they were previously inferred inside the agent's tool, and
being inferred is how they drifted.

**Actionable demand, not category interest.**
The listing used to bucket declarations by substitute group and report the whole
bucket's units as the demand behind the group's largest product. That is not what the
matcher does. A visitor who declares Death Wish coffee *exact-only* is interested in
coffee and can never be served by a Pike Place order — so counting their bags toward
"coffee demand" made discovery and evaluation disagree about who constitutes demand,
and the disagreement surfaced as an opportunity that shrank the moment it was costed.

The invariant this module enforces:

    a declaration contributes to the actionable demand estimate for product X only if
    ``domain.substitution`` would let X serve it.

That is the same pure function ``domain.matching`` calls, applied to the same
declaration, at the most favourable bulk price any tier offers — so a declaration
counted here is one some tier can genuinely use, and a declaration excluded here would
be excluded by every tier. Broader interest is still reported, under its own name, so
"people who buy some coffee" and "people whose standing authority this order can use"
are two numbers rather than one.

**Whose question is this run answering.**
The same listing serves two very different triggers (``agent/objective.py``). A
community scan ranks the whole Community by unserved demand. A member-triggered run is
anchored to one member's own declarations: those come first, and they appear *even when
nothing much has accumulated behind them*, because the member asked about them. The
member's anchor sets the objective; it never predetermines the answer — every entry
still has to survive ``evaluate_opportunity`` on its own facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.attributes import ProductFactSource
from ..domain.matching import haversine_km
from ..domain.models import NeedDeclaration, Product
from ..domain.substitution import evaluate_compatibility
from . import coordination as coord
from . import needs as needs_service
from .context import PoolContext

#: Community-wide opportunities proposed per run, before the model's own projection
#: trims further. Ranked, so the cut is always the tail.
MAX_COMMUNITY_OPPORTUNITIES = 12


def compatible_needs(
    *,
    target: Product,
    needs: list[NeedDeclaration],
    products: dict[str, Product],
    community_id: str,
    offer_unit_price_cents: int | None = None,
    exclude_household_ids: frozenset[str] = frozenset(),
    facts: ProductFactSource | None = None,
) -> list[NeedDeclaration]:
    """Declarations a pool buying ``target`` could actually serve.

    Deliberately *only* the checks that are settled before an opportunity is costed:
    the declaration is live, it belongs to this Community, its household is not already
    being served, and the member's own substitution policy permits this product. Timing,
    geography, case fitting and economics are not decided here — they are what
    evaluation is for, and pretending to know them would be the opposite mistake.
    """
    out: list[NeedDeclaration] = []
    for need in needs:
        if not need.active or need.community_id != community_id:
            continue
        if need.household_id in exclude_household_ids:
            continue
        declared = products.get(need.product_id)
        if declared is None:
            continue
        verdict = evaluate_compatibility(
            target=target,
            candidate=declared,
            need=need,
            offer_unit_price_cents=offer_unit_price_cents,
            facts=facts,
        )
        if verdict.compatible:
            out.append(need)
    return out


def suggest_site(ctx: PoolContext, community_id: str, household_ids: list[str]) -> tuple[str, str]:
    """Pick the public pickup site that serves the most interested members.

    Coverage first, then total travel: the best site is the one the most of them can
    walk to (:data:`coordination.WALKABLE_PICKUP_KM`), breaking ties on aggregate
    distance among those people. A centroid would drift toward outliers and pick a site
    convenient for nobody. This *ranks* sites and excludes nobody — who is eligible is
    the Community's business and each member's own travel policy's.

    Public sites only. Naming a private residence is a consequential action needing its
    owner's approval, so the agent is never handed one as a default (AGENTS.md §5).
    """
    households = {h.id: h for h in ctx.repo.list_households(ctx.ws)}
    points = [households[h] for h in household_ids if h in households]
    sites = [
        s for s in ctx.repo.list_sites(ctx.ws) if s.is_public and s.community_id == community_id
    ]
    if not sites:
        return "", ""
    if not points:
        return sites[0].id, sites[0].name

    def score(site) -> tuple[int, float, str]:
        distances = [haversine_km(p.lat, p.lon, site.lat, site.lon) for p in points]
        covered = sum(1 for d in distances if d <= coord.WALKABLE_PICKUP_KM)
        # Negative coverage so a plain min() prefers more members.
        return (-covered, sum(d for d in distances if d <= coord.WALKABLE_PICKUP_KM), site.id)

    best = min(sites, key=score)
    return best.id, best.name


def _opportunity(
    ctx: PoolContext,
    community_id: str,
    target: Product,
    *,
    needs: list[NeedDeclaration],
    products: dict[str, Product],
    group_members: set[str],
    group_units: int,
    for_member: str = "",
    member_need_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    already = frozenset(coord.pooled_household_ids(ctx, community_id, target.id))
    usable = compatible_needs(
        target=target,
        needs=needs,
        products=products,
        community_id=community_id,
        offer_unit_price_cents=coord.best_bulk_unit_price_cents(ctx, target.id),
        exclude_household_ids=already,
        facts=ctx.product_facts,
    )
    households = sorted({n.household_id for n in usable})
    # A member-anchored entry is sited around that member too: they are the person who
    # asked, and a site chosen only from other people's coordinates can be one they
    # would never walk to.
    site_points = list(households)
    if for_member and for_member not in site_points:
        site_points.append(for_member)
    site_id, site_name = suggest_site(ctx, community_id, site_points)
    return {
        "product_id": target.id,
        "product_name": target.name,
        "substitute_group": target.substitute_group,
        # Compatible with *this* product under each member's own substitution rule, and
        # not already being served. This is the number the matcher can reproduce.
        "unserved_units": sum(n.quantity for n in usable),
        "member_count": len(households),
        # Everyone who declared anything in the same substitute group. Context, not
        # supply: some of these people's rules will not accept this product.
        "group_interest_units": group_units,
        "group_interest_members": len(group_members),
        "suggested_pickup_site_id": site_id,
        "suggested_pickup_site_name": site_name,
        "for_member": bool(for_member),
        "member_need_ids": list(member_need_ids),
    }


@dataclass(frozen=True)
class UnsourcedDemand:
    """Compatible standing demand for a product Pool holds no bulk offer for.

    "Pool cannot buy this" and "nobody wants this" are completely different product
    states, and the second one is a much worse thing to say by accident. Discovery used
    to collapse them: with no sourceable target there was nothing to evaluate, so the
    member's screen reported zero compatible members and zero compatible units beside a
    declaration that six of their neighbours had also made.

    What this counts is exactly what the matcher would count, with the one input that
    genuinely is not known left unknown:

    * the target is the **declared product itself**, because that is the only thing a
      supplier offer could later arrive *for*;
    * no unit price is supplied, because none exists. A member's per-unit ceiling is a
      rule about an offer, and there is no offer — inventing a price to test it against
      would be inventing the very supply fact this exists to report as missing.

    The consequence is worth stating plainly rather than hiding: a neighbour who
    declared a *different* product in the same substitute group, allows substitution,
    and set a price ceiling is counted here, and a future offer might still breach that
    ceiling. Members who declared this exact product — which is what the count is mostly
    made of — are exact matches, and no ceiling applies to them at all. Nothing here
    asserts that a viable order exists; it asserts that demand does.
    """

    #: Distinct households, including the member this was computed for.
    members: int
    #: Units, including this member's own.
    units: int
    #: The same two counts with this member removed, for surfaces that show their own
    #: quantity separately and would otherwise count it twice.
    other_members: int
    other_units: int


def unsourced_demand(
    ctx: PoolContext, community_id: str, need: NeedDeclaration
) -> UnsourcedDemand:
    """Compatible demand standing behind one declaration Pool cannot currently source.

    Read-only. Creates nothing, prices nothing, and reports no verdict — a supplier
    minimum it could be measured against does not exist yet, which is the whole point.
    """
    product = ctx.repo.get_product(ctx.ws, need.product_id)
    if product is None:
        return UnsourcedDemand(0, 0, 0, 0)
    usable = compatible_needs(
        target=product,
        needs=ctx.repo.list_needs(ctx.ws),
        products={p.id: p for p in ctx.repo.list_products(ctx.ws)},
        community_id=community_id,
        offer_unit_price_cents=None,
        exclude_household_ids=frozenset(
            coord.pooled_household_ids(ctx, community_id, need.product_id)
        ),
        facts=ctx.product_facts,
    )
    others = [n for n in usable if n.household_id != need.household_id]
    return UnsourcedDemand(
        members=len({n.household_id for n in usable}),
        units=sum(n.quantity for n in usable),
        other_members=len({n.household_id for n in others}),
        other_units=sum(n.quantity for n in others),
    )


def standing_demand_for(
    ctx: PoolContext, community_id: str, need: NeedDeclaration
) -> dict[str, Any]:
    """What already exists around one declaration, *before* anything is evaluated.

    The pre-run half of the product's whole claim: nobody organised a group, and here is
    the overlap that accumulated anyway. It is deliberately **inputs only** — how many
    other members have independently declared something this order could serve, how many
    units that is, and the smallest quantity the supplier will sell.

    It reports no verdict, because it has not earned one. Whether those people can reach
    one pickup point, whether their restock dates overlap, whether the units land on a
    case boundary and whether the all-in price beats retail are all decided by
    ``evaluate_opportunity`` during a run — and a screen that answered them in advance
    would be telling a member the result before Pool had done the work (§8).

    Read-only, and no PII: counts and quantities, never who.
    """
    product = ctx.repo.get_product(ctx.ws, need.product_id)
    targets = coord.sourceable_targets_for_need(ctx, need)
    base = {
        "need_id": need.id,
        "product_id": need.product_id,
        # What the member called it, which for a family declaration is the family and
        # never the exemplar row behind it.
        "product_name": needs_service.declared_as(ctx, need) or need.product_id,
        "unit": product.unit if product else "unit",
        "my_units": need.quantity,
        "compatible_members": 0,
        "compatible_units": 0,
        "minimum_units": 0,
        "has_supplier": bool(targets),
        # The target a pool would actually buy, when it is not the declared product —
        # so the interface can disclose the substitution rather than quietly counting
        # somebody else's product as this member's demand.
        "sourceable_product_id": "",
        "sourceable_product_name": "",
    }
    if not targets:
        # No verified bulk supplier — for this product, or for any substitute this
        # member's own rules authorise. That is a fact about *supply*, and it used to
        # take the demand numbers down with it: the screen said nothing was here when
        # the truth was that people want this and Pool does not yet know how to buy it.
        #
        # `minimum_units` stays 0 and `has_supplier` stays false beside these counts.
        # There is no supplier, so there is no minimum, and printing a threshold nobody
        # has quoted would be the same fabrication in the opposite direction (§8).
        standing = unsourced_demand(ctx, community_id, need)
        return {
            **base,
            "compatible_members": standing.other_members,
            "compatible_units": standing.other_units,
        }

    needs = ctx.repo.list_needs(ctx.ws)
    products = {p.id: p for p in ctx.repo.list_products(ctx.ws)}
    best: dict[str, Any] | None = None
    for target_id in targets:
        target = products.get(target_id)
        if target is None:
            continue
        already = frozenset(coord.pooled_household_ids(ctx, community_id, target_id))
        usable = [
            n
            for n in compatible_needs(
                target=target,
                needs=needs,
                products=products,
                community_id=community_id,
                offer_unit_price_cents=coord.best_bulk_unit_price_cents(ctx, target_id),
                exclude_household_ids=already,
                facts=ctx.product_facts,
            )
            if n.household_id != need.household_id
        ]
        # The minimum of the *cheapest* tier, not of all of them. Whey has a 12-unit tier
        # at $39.80 and a 24-unit one at $31.50, and the evaluator takes the second — so
        # reporting 12 here put "the supplier will not sell fewer than 12" on the screen
        # before a run and "reached the supplier's 24-unit minimum" on the screen after
        # it. Both true, and side by side they read as a contradiction.
        _, bulk = coord.offers_for(ctx, target_id)
        cheapest = min(bulk, key=lambda o: (o.unit_price_cents, o.min_units), default=None)
        row = {
            **base,
            "compatible_members": len({n.household_id for n in usable}),
            "compatible_units": sum(n.quantity for n in usable),
            "minimum_units": cheapest.min_units if cheapest else 0,
            "sourceable_product_id": target_id if target_id != need.product_id else "",
            "sourceable_product_name": target.name if target_id != need.product_id else "",
        }
        if best is None or row["compatible_units"] > best["compatible_units"]:
            best = row
    return best or base


def latent_demand(ctx: PoolContext, community_id: str, objective: Any = None) -> dict[str, Any]:
    """Products worth investigating in this Community, most promising first.

    With a member objective, that member's own declarations lead the list — one entry
    per product a pool could buy to serve each of them — followed by whatever else the
    Community has accumulated. Without one, it is the whole Community, ranked.
    """
    products = {p.id: p for p in ctx.repo.list_products(ctx.ws)}
    needs = ctx.repo.list_needs(ctx.ws)
    live = [n for n in needs if n.active and n.community_id == community_id]

    groups: dict[str, list[NeedDeclaration]] = {}
    for need in live:
        product = products.get(need.product_id)
        if product is None:
            continue
        groups.setdefault(product.substitute_group or product.id, []).append(need)

    def group_context(target: Product) -> tuple[set[str], int]:
        members = groups.get(target.substitute_group or target.id, [])
        return {n.household_id for n in members}, sum(n.quantity for n in members)

    member_rows: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    member_needs = tuple(getattr(objective, "needs", ()) or ())
    household_id = str(getattr(objective, "household_id", "") or "")
    for entry in member_needs:
        for target_id in entry.target_product_ids:
            if target_id in seen_targets:
                # Two of this member's declarations can share a sourceable target. One
                # entry, carrying both need ids, so the run evaluates it once and the
                # record still explains which declarations it was asked about.
                for row in member_rows:
                    if row["product_id"] == target_id:
                        row["member_need_ids"].append(entry.need_id)
                continue
            target = products.get(target_id)
            if target is None:
                continue
            seen_targets.add(target_id)
            members, units = group_context(target)
            member_rows.append(
                _opportunity(
                    ctx,
                    community_id,
                    target,
                    needs=live,
                    products=products,
                    group_members=members,
                    group_units=units,
                    for_member=household_id,
                    member_need_ids=(entry.need_id,),
                )
            )

    community_rows: list[dict[str, Any]] = []
    for group_needs in groups.values():
        # One target per substitute group: the product whose *actionable* demand is
        # largest. Ranking by raw declared quantity picked whichever product the group's
        # incompatible declarations happened to name.
        candidates = sorted({n.product_id for n in group_needs})
        best: dict[str, Any] | None = None
        members = {n.household_id for n in group_needs}
        units = sum(n.quantity for n in group_needs)
        best_rank: tuple[int, int, int, str] | None = None
        for product_id in candidates:
            target = products.get(product_id)
            if target is None or target.id in seen_targets:
                continue
            row = _opportunity(
                ctx,
                community_id,
                target,
                needs=live,
                products=products,
                group_members=members,
                group_units=units,
            )
            # Sourceability outranks demand, because it is the difference between an
            # opportunity and a dead end. Demand alone would name whichever product the
            # group's declarations happened to favour, and `evaluate_opportunity` would
            # then refuse it for `no_retail_baseline` — proposing an order for something
            # no supplier sells. It was latent while exact-only declarations were rare
            # enough to be outvoted; a group-level declaration makes every member of the
            # family compatible, so target choice decides the whole outcome.
            retail, bulk = coord.offers_for(ctx, target.id)
            rank = (
                1 if (bulk and retail is not None) else 0,
                row["member_count"],
                row["unserved_units"],
                row["product_id"],
            )
            if best_rank is None or rank > best_rank:
                best, best_rank = row, rank
        if best is None or best["member_count"] == 0:
            # Everybody in this group is already being served, or nobody's rules can be
            # served by anything in it. Either way there is nothing to propose.
            continue
        community_rows.append(best)
        seen_targets.add(best["product_id"])

    community_rows.sort(
        key=lambda o: (-o["member_count"], -o["unserved_units"], o["product_id"])
    )
    opportunities = member_rows + community_rows[:MAX_COMMUNITY_OPPORTUNITIES]
    return {
        "objective": objective.to_dict() if objective is not None else None,
        "opportunities": opportunities,
        "count": len(opportunities),
    }
