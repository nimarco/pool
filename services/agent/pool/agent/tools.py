"""The agent's tool surface.

Narrow, typed, and structured. Each tool is either a *read* (safe, unlimited) or a
single *consequential* operation with idempotency and an approval boundary baked in.
There is no generic "run SQL" or "update anything" escape hatch — the model reaches
the world only through these seven doors (AGENTS.md §4).

Every tool returns a JSON string. The numbers inside come from the deterministic
services layer; the agent's job is to decide which door to open next, never to
compute or restate a value (AGENTS.md §5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from strands import tool

from ..adapters.repository import Repository
from ..adapters.routing import RoutingService
from ..domain.matching import haversine_km
from ..domain.models import MembershipState, PoolStatus, RunOutcome
from ..domain.money import bps_to_pct_str, format_cents
from ..services import coordination as coord


@dataclass
class ToolContext:
    """Everything the tools are allowed to touch, and the run they belong to."""

    repo: Repository
    ws: str
    routing: RoutingService
    run_id: str
    outcome: RunOutcome = RunOutcome.NO_ACTION
    created_pool_ids: list[str] = field(default_factory=list)
    recovered_pool_ids: list[str] = field(default_factory=list)
    decisions_created: int = 0
    no_action_reason: str = ""


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def _pooled_household_ids(repo: Repository, ws: str, product_id: str) -> set[str]:
    """Households already inside a live pool for this product — do not re-recruit them."""
    out: set[str] = set()
    for pool in repo.list_pools(ws):
        if pool.product_id != product_id:
            continue
        if pool.status in {PoolStatus.FAILED, PoolStatus.EXPIRED}:
            continue
        for m in repo.list_memberships(ws, pool.id):
            if m.state in {MembershipState.COMMITTED, MembershipState.INVITED}:
                out.add(m.household_id)
    return out


def _suggest_site(repo: Repository, ws: str, household_ids: list[str]) -> tuple[str, str]:
    """Pick the public pickup site that serves the most interested households.

    Coverage first, then total travel: the best site is the one with the most
    households inside the formation radius, breaking ties on aggregate distance. A
    centroid would drift toward outliers and pick a site convenient for nobody.

    Public sites only. Naming a private residence is a consequential action needing
    its owner's approval, so the agent is never handed one as a default (AGENTS.md §5).
    """
    households = {h.id: h for h in repo.list_households(ws)}
    points = [households[h] for h in household_ids if h in households]
    sites = [s for s in repo.list_sites(ws) if s.is_public]
    if not sites:
        return "", ""
    if not points:
        return sites[0].id, sites[0].name

    def score(site) -> tuple[int, float, str]:
        distances = [haversine_km(p.lat, p.lon, site.lat, site.lon) for p in points]
        covered = sum(1 for d in distances if d <= coord.FORMATION_RADIUS_KM)
        # Negative coverage so a plain min() prefers more households.
        return (-covered, sum(d for d in distances if d <= coord.FORMATION_RADIUS_KM), site.id)

    best = min(sites, key=score)
    return best.id, best.name


def build_tools(ctx: ToolContext) -> list:
    """Construct the tool set bound to one run's context."""

    @tool
    def list_unmet_demand() -> str:
        """List declared household needs that no active buying pool is currently serving.

        Read-only. Returns candidate products ranked by how much aggregate demand is
        going unserved, each with a suggested public pickup site. Use this first to
        find out where an opportunity might exist.
        """
        repo, ws = ctx.repo, ctx.ws
        products = {p.id: p for p in repo.list_products(ws)}
        buckets: dict[str, list] = {}
        for need in repo.list_needs(ws):
            if not need.active:
                continue
            product = products.get(need.product_id)
            if product is None:
                continue
            # Group by substitute family so related products surface together.
            buckets.setdefault(product.substitute_group or product.id, []).append(need)

        opportunities = []
        for group, needs in buckets.items():
            representative = products[needs[0].product_id]
            # Prefer the product with the most demand inside the family.
            by_product: dict[str, int] = {}
            for n in needs:
                by_product[n.product_id] = by_product.get(n.product_id, 0) + n.quantity
            target_id = max(by_product.items(), key=lambda kv: (kv[1], kv[0]))[0]
            representative = products[target_id]

            already = _pooled_household_ids(repo, ws, target_id)
            open_needs = [n for n in needs if n.household_id not in already]
            if not open_needs:
                continue
            household_ids = [n.household_id for n in open_needs]
            site_id, site_name = _suggest_site(repo, ws, household_ids)
            opportunities.append(
                {
                    "product_id": target_id,
                    "product_name": representative.name,
                    "substitute_group": group,
                    "unserved_units": sum(n.quantity for n in open_needs),
                    "household_count": len({n.household_id for n in open_needs}),
                    "suggested_pickup_site_id": site_id,
                    "suggested_pickup_site_name": site_name,
                }
            )

        opportunities.sort(key=lambda o: (-o["household_count"], -o["unserved_units"], o["product_id"]))
        return _json({"opportunities": opportunities, "count": len(opportunities)})

    @tool
    def evaluate_opportunity(product_id: str, pickup_site_id: str, pickup_in_days: int = 14) -> str:
        """Evaluate whether a worthwhile bulk buying opportunity exists for one product.

        Read-only and safe to call freely: it contacts nobody and commits nothing.
        Computes compatible demand, the best bulk offer, exact per-household costs and
        savings, real travel times to the pickup site, and each household's Smart Join
        eligibility.

        Args:
            product_id: The product to evaluate, e.g. from list_unmet_demand.
            pickup_site_id: Candidate pickup location.
            pickup_in_days: How many days out to schedule pickup. Default 14.
        """
        assessment = coord.evaluate_opportunity(
            repo=ctx.repo,
            ws=ctx.ws,
            routing=ctx.routing,
            product_id=product_id,
            pickup_site_id=pickup_site_id,
            pickup_in_days=pickup_in_days,
            exclude_household_ids=frozenset(_pooled_household_ids(ctx.repo, ctx.ws, product_id)),
        )
        payload = assessment.to_dict()
        if assessment.viable and assessment.pricing:
            payload["headline"] = (
                f"{len(assessment.candidates)} households, "
                f"{assessment.pricing.total_units} units, "
                f"{bps_to_pct_str(assessment.pricing.total_savings_bps)} below retail, "
                f"avg {assessment.avg_travel_minutes} min to {assessment.pickup_site_name}"
            )
        return _json(payload)

    @tool
    def create_buying_pool(product_id: str, pickup_site_id: str, pickup_in_days: int = 14) -> str:
        """Form a candidate buying pool from a viable opportunity.

        Consequential. Households whose Smart Join policy deterministically passes are
        committed automatically; everyone else receives an approval request rather than
        being committed. Idempotent: calling twice for the same product, site, and
        pickup date returns the existing pool instead of creating a duplicate.

        Args:
            product_id: Product to pool.
            pickup_site_id: Pickup location.
            pickup_in_days: Days until pickup. Default 14.
        """
        assessment = coord.evaluate_opportunity(
            repo=ctx.repo,
            ws=ctx.ws,
            routing=ctx.routing,
            product_id=product_id,
            pickup_site_id=pickup_site_id,
            pickup_in_days=pickup_in_days,
            exclude_household_ids=frozenset(_pooled_household_ids(ctx.repo, ctx.ws, product_id)),
        )
        if not assessment.viable:
            return _json(
                {"created": False, "viable": False, "reason": assessment.reason,
                 "product_id": product_id}
            )

        key = f"{product_id}:{pickup_site_id}:{assessment.pickup_by}"
        pool, created = coord.create_pool(
            repo=ctx.repo, ws=ctx.ws, assessment=assessment,
            run_id=ctx.run_id, idempotency_key=key,
        )
        members = ctx.repo.list_memberships(ctx.ws, pool.id)
        pending = sum(1 for m in members if m.state == MembershipState.INVITED)
        if created:
            ctx.outcome = RunOutcome.POOL_CREATED
            ctx.created_pool_ids.append(pool.id)
            ctx.decisions_created += pending
        assert assessment.pricing is not None
        return _json(
            {
                "created": created,
                "pool_id": pool.id,
                "product_id": product_id,
                "product_name": assessment.product_name,
                "status": pool.status.value,
                "member_count": len(members),
                "committed_without_asking": sum(
                    1 for m in members if m.state == MembershipState.COMMITTED
                ),
                "approval_requested": pending,
                "total_units": assessment.pricing.total_units,
                "threshold_units": pool.threshold_units,
                "group_savings": format_cents(assessment.pricing.total_savings_cents),
                "savings_pct": bps_to_pct_str(assessment.pricing.total_savings_bps),
                "pickup_site": assessment.pickup_site_name,
                "pickup_by": assessment.pickup_by,
            }
        )

    @tool
    def list_pools_needing_attention() -> str:
        """List pools that have fallen below their supplier minimum and need repair.

        Read-only. Typically used after a participant withdraws.
        """
        out = []
        for pool in ctx.repo.list_pools(ctx.ws):
            if pool.status in {PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED}:
                continue
            committed = coord.committed_units(ctx.repo, ctx.ws, pool.id)
            if committed >= pool.threshold_units:
                continue
            product = ctx.repo.get_product(ctx.ws, pool.product_id)
            out.append(
                {
                    "pool_id": pool.id,
                    "product_id": pool.product_id,
                    "product_name": product.name if product else pool.product_id,
                    "status": pool.status.value,
                    "committed_units": committed,
                    "threshold_units": pool.threshold_units,
                    "shortfall_units": pool.threshold_units - committed,
                    "deadline": pool.deadline.isoformat(),
                }
            )
        out.sort(key=lambda p: (-p["shortfall_units"], p["pool_id"]))
        return _json({"pools": out, "count": len(out)})

    @tool
    def recover_pool(pool_id: str) -> str:
        """Attempt to restore a pool that has dropped below its supplier minimum.

        Consequential. Searches the wider neighbourhood for compatible unserved demand,
        auto-joins only households whose own Smart Join policy permits it, and asks
        everyone else. Existing members are left undisturbed unless their own share
        materially changed, in which case they are asked rather than silently repriced.

        Args:
            pool_id: The pool to repair.
        """
        result = coord.recover_pool(
            repo=ctx.repo, ws=ctx.ws, routing=ctx.routing,
            pool_id=pool_id, run_id=ctx.run_id,
        )
        if result.recovered:
            ctx.outcome = RunOutcome.POOL_RECOVERED
            ctx.recovered_pool_ids.append(pool_id)
        ctx.decisions_created += len(result.invited_household_ids)
        return _json(result.to_dict())

    @tool
    def record_no_action(reason: str) -> str:
        """Conclude the run with no action taken, recording why.

        Use this when no opportunity is worth pursuing. Terminating quietly is a
        success: households should only hear from Pool when there is a real decision
        for them.

        Args:
            reason: Why no action was warranted.
        """
        ctx.outcome = RunOutcome.NO_ACTION
        ctx.no_action_reason = reason
        return _json({"acknowledged": True, "reason": reason})

    return [
        list_unmet_demand,
        evaluate_opportunity,
        create_buying_pool,
        list_pools_needing_attention,
        recover_pool,
        record_no_action,
    ]
