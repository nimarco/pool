"""The agent's tool surface (§95).

Narrow, typed, and structured. Each tool is a pure read, a record of Pool's own working
state, or a single consequential operation with idempotency and an approval boundary
baked in — see :data:`TOOL_SURFACE` for which is which, and ``test_agent_effects.py``
for the test that checks the labels against what the tools actually write rather than
against what their docstrings claim. There is no generic "run SQL" or "update anything"
escape hatch — the model reaches the world only through these doors (AGENTS.md §4).

Every tool returns a JSON string. The numbers inside come from the deterministic
services layer; the agent's job is to decide which door to open next, never to compute
or restate a value (AGENTS.md §5). In particular, the model can ask *whether* a host is
eligible, *whether* a pool is viable, and *whether* a buyer's policy passes — it can
never decide any of those things.

The larger results are *projected* before they reach the model (see ``projection.py``):
the model receives the decision-critical facts, and the complete authoritative result is
kept on :class:`ToolContext` for the API, the operator UI, auditing, and tests. This is
a cost boundary, not a truth boundary — the projection selects and aggregates fields
that deterministic code already computed, and never recomputes one (AGENTS.md §3.3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from strands import tool

from ..domain.matching import haversine_km
from ..domain.models import (
    DecisionState,
    ParticipationState,
    PoolStatus,
    RunOutcome,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.viability import ViabilityStage
from ..services import coordination as coord
from ..services import fulfillment as fulfil
from ..services import hosting
from ..services.context import PoolContext
from . import projection as proj

#: Full results retained per run. One per tool call, so the tool-call bound already caps
#: it; the ceiling exists so a mis-set bound cannot grow this without limit.
MAX_RETAINED_FULL_RESULTS = 64


@dataclass
class FullToolResult:
    """The complete, unprojected result a tool computed, kept for the record."""

    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class ToolContext:
    """Everything the tools are allowed to touch, and the run they belong to."""

    pool: PoolContext
    community_id: str
    outcome: RunOutcome = RunOutcome.NO_ACTION
    created_pool_ids: list[str] = field(default_factory=list)
    advanced_pool_ids: list[str] = field(default_factory=list)
    recovered_pool_ids: list[str] = field(default_factory=list)
    decisions_created: int = 0
    no_action_reason: str = ""
    #: Authoritative results in call order, for auditing and any consumer that needs
    #: the detail the model is deliberately not shown.
    full_results: list[FullToolResult] = field(default_factory=list)

    @property
    def repo(self):
        return self.pool.repo

    @property
    def ws(self) -> str:
        return self.pool.ws

    def record_full(
        self, tool: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Retain a complete tool result and return it unchanged."""
        if len(self.full_results) < MAX_RETAINED_FULL_RESULTS:
            self.full_results.append(FullToolResult(tool, arguments, result))
        return result

    def last_full_result(self, tool: str) -> dict[str, Any] | None:
        for entry in reversed(self.full_results):
            if entry.tool == tool:
                return entry.result
        return None


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def _suggest_site(ctx: ToolContext, household_ids: list[str]) -> tuple[str, str]:
    """Pick the public pickup site that serves the most interested members.

    Coverage first, then total travel: the best site is the one with the most people
    inside the formation radius, breaking ties on aggregate distance. A centroid would
    drift toward outliers and pick a site convenient for nobody.

    Public sites only. Naming a private residence is a consequential action needing its
    owner's approval, so the agent is never handed one as a default (AGENTS.md §5).
    """
    households = {h.id: h for h in ctx.repo.list_households(ctx.ws)}
    points = [households[h] for h in household_ids if h in households]
    sites = [
        s
        for s in ctx.repo.list_sites(ctx.ws)
        if s.is_public and s.community_id == ctx.community_id
    ]
    if not sites:
        return "", ""
    if not points:
        return sites[0].id, sites[0].name

    def score(site) -> tuple[int, float, str]:
        distances = [haversine_km(p.lat, p.lon, site.lat, site.lon) for p in points]
        covered = sum(1 for d in distances if d <= coord.FORMATION_RADIUS_KM)
        # Negative coverage so a plain min() prefers more members.
        return (-covered, sum(d for d in distances if d <= coord.FORMATION_RADIUS_KM), site.id)

    best = min(sites, key=score)
    return best.id, best.name


#: The complete tool surface, in the order the model is given it, with the authority
#: each entry carries.
#:
#: Four kinds, because three could not describe what these tools actually do:
#:
#: * ``read`` — writes nothing at all. Safe to call freely, and
#:   ``test_agent_effects.py`` *proves* it by snapshotting the whole workspace around
#:   every one of them rather than trusting this label.
#: * ``record`` — writes Pool's own working state: an evaluation it wants to be able to
#:   show its reasoning from, or a lifecycle status catching up with facts that are
#:   already true. Nothing a member or a supplier can observe as a commitment, nobody is
#:   contacted, and no money moves.
#: * ``act`` — consequential. Commits Pool to something a member or supplier can
#:   observe: forms a pool, offers someone paid work, issues a price, authorises or
#:   captures money, places an order. ``execute_purchase`` is the externally
#:   consequential one, and in this build its executor is simulated and says so.
#: * ``end`` — closes the run.
#:
#: ``find_host_candidates`` was labelled ``read`` and is not: it opens host recruiting
#: and persists a candidate record per evaluation. Nothing about the tool changed —
#: the label did, because the label was the thing that was wrong (#audit P1-1).
#:
#: Published by the API so the UI can show what the agent may choose from without
#: keeping a second list that drifts; ``test_agent_projection.py`` asserts it against
#: what :func:`build_tools` returns, so adding a tool without describing it fails the
#: suite.
TOOL_KINDS = frozenset({"read", "record", "act", "end"})

#: Kinds that write. The complement of ``read``, stated once so the effect test and the
#: API cannot disagree about which tools are supposed to be inert.
MUTATING_TOOL_KINDS = frozenset({"record", "act"})

TOOL_SURFACE: tuple[tuple[str, str], ...] = (
    ("list_latent_demand", "read"),
    ("evaluate_pool_economics", "read"),
    ("create_candidate_pool", "act"),
    ("find_host_candidates", "record"),
    ("request_host_acceptance", "act"),
    ("issue_final_offer", "act"),
    ("inspect_pool", "read"),
    ("list_pools_needing_attention", "read"),
    ("recover_pool", "act"),
    ("lock_pool", "act"),
    ("execute_purchase", "act"),
    ("record_no_action", "end"),
)


def build_tools(ctx: ToolContext) -> list:
    """Construct the tool set bound to one run's context."""

    @tool
    def list_latent_demand() -> str:
        """List recurring needs in this community that no active pool is serving.

        Read-only. This is where the product's core claim lives: nobody declared a
        group, so the opportunity has to be discovered from standing declarations.
        Returns candidate products ranked by how much aggregate demand is unserved,
        each with a suggested public pickup site.
        """
        products = {p.id: p for p in ctx.repo.list_products(ctx.ws)}
        buckets: dict[str, list] = {}
        for need in ctx.repo.list_needs(ctx.ws):
            if not need.active or need.community_id != ctx.community_id:
                continue
            product = products.get(need.product_id)
            if product is None:
                continue
            buckets.setdefault(product.substitute_group or product.id, []).append(need)

        opportunities = []
        for group, needs in buckets.items():
            by_product: dict[str, int] = {}
            for n in needs:
                by_product[n.product_id] = by_product.get(n.product_id, 0) + n.quantity
            target_id = max(by_product.items(), key=lambda kv: (kv[1], kv[0]))[0]
            representative = products[target_id]

            already = coord.pooled_household_ids(ctx.pool, ctx.community_id, target_id)
            open_needs = [n for n in needs if n.household_id not in already]
            if not open_needs:
                continue
            site_id, site_name = _suggest_site(ctx, [n.household_id for n in open_needs])
            opportunities.append(
                {
                    "product_id": target_id,
                    "product_name": representative.name,
                    "substitute_group": group,
                    "unserved_units": sum(n.quantity for n in open_needs),
                    "member_count": len({n.household_id for n in open_needs}),
                    "suggested_pickup_site_id": site_id,
                    "suggested_pickup_site_name": site_name,
                }
            )

        opportunities.sort(
            key=lambda o: (-o["member_count"], -o["unserved_units"], o["product_id"])
        )
        full = {"opportunities": opportunities, "count": len(opportunities)}
        ctx.record_full("list_latent_demand", {}, full)
        return _json(proj.demand_view(opportunities))

    @tool
    def evaluate_pool_economics(
        product_id: str, pickup_site_id: str, include_future_demand: bool = True
    ) -> str:
        """Evaluate whether a worthwhile bulk opportunity exists for one product.

        Read-only and safe to call freely: it contacts nobody and commits nothing.
        Computes compatible demand, the best bulk tier, complete landed economics
        (merchandise + host pay + processing + Pool fee), real travel times, and how
        many members' Smart Join rules accept the estimated price.

        Args:
            product_id: The product to evaluate, e.g. from list_latent_demand.
            pickup_site_id: Candidate public pickup location.
            include_future_demand: Whether to consider members who authorised an early
                purchase. Their timing rules still decide who is actually eligible.
        """
        assessment = coord.evaluate_opportunity(
            ctx=ctx.pool,
            community_id=ctx.community_id,
            product_id=product_id,
            pickup_site_id=pickup_site_id,
            include_future_demand=include_future_demand,
            exclude_household_ids=frozenset(
                coord.pooled_household_ids(ctx.pool, ctx.community_id, product_id)
            ),
        )
        payload = assessment.to_dict()
        if assessment.viable and assessment.economics:
            econ = assessment.economics
            payload["headline"] = (
                f"{len(assessment.candidates)} members, {econ.packages.total_units} units, "
                f"{bps_to_pct_str(econ.net_savings_bps)} below retail after all costs, "
                f"avg {assessment.avg_travel_minutes} min to {assessment.pickup_site_name}"
            )
        ctx.record_full(
            "evaluate_pool_economics",
            {
                "product_id": product_id,
                "pickup_site_id": pickup_site_id,
                "include_future_demand": include_future_demand,
            },
            payload,
        )
        return _json(proj.opportunity_view(payload))

    @tool
    def create_candidate_pool(product_id: str, pickup_site_id: str) -> str:
        """Form a candidate pool from a viable opportunity.

        Consequential, but it commits no money: members join **provisionally**, the
        savings shown are an estimate, and fulfilment is still being recruited. No card
        is touched until a host is selected and the exact final price is known.
        Idempotent — calling twice for the same product, site, and distribution day
        returns the existing pool.

        Args:
            product_id: Product to pool.
            pickup_site_id: Public pickup location.
        """
        assessment = coord.evaluate_opportunity(
            ctx=ctx.pool,
            community_id=ctx.community_id,
            product_id=product_id,
            pickup_site_id=pickup_site_id,
            exclude_household_ids=frozenset(
                coord.pooled_household_ids(ctx.pool, ctx.community_id, product_id)
            ),
        )
        if not assessment.viable:
            return _json(
                {"created": False, "viable": False, "reason": assessment.reason,
                 "product_id": product_id}
            )

        key = f"{ctx.community_id}:{product_id}:{pickup_site_id}:{assessment.distribution_day}"
        pool, created = coord.create_candidate_pool(
            ctx=ctx.pool, assessment=assessment, idempotency_key=key
        )
        if created:
            ctx.outcome = RunOutcome.POOL_CREATED
            ctx.created_pool_ids.append(pool.id)
        econ = assessment.economics
        assert econ is not None
        return _json(
            {
                "created": created,
                "pool_id": pool.id,
                "product_id": product_id,
                "product_name": assessment.product_name,
                "status": pool.status.value,
                "member_count": len(assessment.candidates),
                "provisional_units": econ.packages.total_units,
                "current_units": assessment.current_units,
                "future_units_pulled_forward": assessment.future_units,
                "threshold_units": pool.threshold_units,
                "estimated_group_savings": format_cents(econ.net_savings_cents),
                "estimated_savings_pct": bps_to_pct_str(econ.net_savings_bps),
                "pickup_site": assessment.pickup_site_name,
                "distribution_day": assessment.distribution_day,
                "host_status": "not yet recruited",
            }
        )

    @tool
    def find_host_candidates(pool_id: str) -> str:
        """Evaluate who could fulfil this pool, and why.

        Records state, but commits nothing: it opens host recruiting if demand now
        clears the supplier minimum, and stores each candidate's evaluation so the
        ranking can be inspected later. Nobody is offered the job and nobody is
        contacted — that is ``request_host_acceptance``.

        Candidates come from standing hosts and from pool members who offered to host
        this specific pool. Returns each candidate's eligibility, rank, deterministic
        pay, and the factual reasons anyone is ineligible — so a selection can be
        explained rather than asserted.

        Args:
            pool_id: The pool that needs fulfilment.
        """
        hosting.open_host_recruiting(ctx=ctx.pool, pool_id=pool_id)
        result = hosting.evaluate_host_candidates(ctx=ctx.pool, pool_id=pool_id)
        full = ctx.record_full("find_host_candidates", {"pool_id": pool_id}, result.to_dict())
        return _json(proj.host_evaluation_view(full))

    @tool
    def request_host_acceptance(pool_id: str) -> str:
        """Offer the fulfilment job to the best-ranked eligible host candidate.

        Consequential. Exactly one offer is outstanding at a time; offering does not
        assign the job, and the candidate must accept. If an outstanding offer has
        expired it is expired first and the next candidate is offered. If nobody
        eligible remains and the host deadline has passed, the pool fails honestly
        rather than cycling.

        Args:
            pool_id: The pool that needs a host.
        """
        hosting.open_host_recruiting(ctx=ctx.pool, pool_id=pool_id)
        result = hosting.offer_to_next_host(ctx=ctx.pool, pool_id=pool_id)
        if result.offered_household_id:
            ctx.decisions_created += 1
            if ctx.outcome == RunOutcome.NO_ACTION:
                ctx.outcome = RunOutcome.POOL_ADVANCED
            if pool_id not in ctx.advanced_pool_ids:
                ctx.advanced_pool_ids.append(pool_id)
        full = ctx.record_full("request_host_acceptance", {"pool_id": pool_id}, result.to_dict())
        return _json(proj.host_evaluation_view(full))

    @tool
    def issue_final_offer(pool_id: str) -> str:
        """Refresh the supplier quote and issue exact final prices to buyers.

        Consequential and order-dependent: it requires an accepted host, re-verifies
        the supplier price, computes complete landed economics, then authorises the
        buyers whose own Smart Join rules pass and asks everyone else. Buyers whose
        rules cannot accept the final price are removed and the price is recomputed.
        Refuses to proceed if case rounding would leave unallocated units — Pool does
        not buy speculative stock.

        Args:
            pool_id: The pool to price and offer.
        """
        result = coord.issue_final_offer(ctx=ctx.pool, pool_id=pool_id)
        if result.issued:
            ctx.decisions_created += len(result.awaiting_decision)
            if ctx.outcome == RunOutcome.NO_ACTION:
                ctx.outcome = RunOutcome.POOL_ADVANCED
            if pool_id not in ctx.advanced_pool_ids:
                ctx.advanced_pool_ids.append(pool_id)
        full = ctx.record_full("issue_final_offer", {"pool_id": pool_id}, result.to_dict())
        return _json(proj.final_offer_view(full))

    @tool
    def inspect_pool(pool_id: str) -> str:
        """Read one pool's current state: funding, host, timing, and viability.

        Read-only. The viability verdict is the deterministic engine's, including every
        check that failed and why.

        Args:
            pool_id: The pool to inspect.
        """
        pool = ctx.repo.get_pool(ctx.ws, pool_id)
        if pool is None:
            return _json({"error": "unknown pool", "pool_id": pool_id})
        assignment = ctx.repo.get_host_assignment(ctx.ws, pool_id)
        members = ctx.repo.list_memberships(ctx.ws, pool_id)
        stage = (
            ViabilityStage.FINAL_LOCK
            if pool.status in {PoolStatus.FUNDING, PoolStatus.RECOVERING}
            else ViabilityStage.PRE_FUNDING
        )
        verdict = coord.check_viability(ctx=ctx.pool, pool_id=pool_id, stage=stage)
        full = ctx.record_full(
            "inspect_pool",
            {"pool_id": pool_id},
            {
                "pool_id": pool_id,
                "status": pool.status.value,
                "product_id": pool.product_id,
                "threshold_units": pool.threshold_units,
                "provisional_units": coord.provisional_units(ctx.pool, pool_id),
                "funded_units": coord.funded_units(ctx.pool, pool_id),
                "host_household_id": assignment.household_id if assignment else "",
                "has_final_offer": pool.has_final_offer,
                "quote_verified_at": pool.quote_verified_at,
                "timing": pool.timing.to_dict(),
                "members": {
                    "total": len(members),
                    "authorized": sum(1 for m in members if m.counts_as_funded),
                    "awaiting_decision": sum(
                        1 for m in members if m.state == ParticipationState.FINAL_OFFERED
                    ),
                    "authorization_failed": sum(
                        1 for m in members
                        if m.state == ParticipationState.AUTHORIZATION_FAILED
                    ),
                },
                "pending_decisions": sum(
                    1
                    for d in ctx.repo.list_decisions(ctx.ws)
                    if d.pool_id == pool_id and d.state == DecisionState.PENDING
                ),
                "viability": verdict.to_dict(),
            },
        )
        return _json(proj.pool_view(full))

    @tool
    def list_pools_needing_attention() -> str:
        """List pools that cannot currently proceed, and what is blocking each one.

        Read-only. This is the agent's work queue: pools short of demand, without a
        host, with a stale quote, with a failed authorisation, or ready to lock.
        """
        out = []
        for pool in ctx.repo.list_pools(ctx.ws):
            if pool.community_id != ctx.community_id:
                continue
            if pool.status in {
                PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED,
                PoolStatus.PURCHASED, PoolStatus.DISTRIBUTING,
            }:
                continue
            funded = coord.funded_units(ctx.pool, pool.id)
            provisional = coord.provisional_units(ctx.pool, pool.id)
            # Buyers who have not answered yet are not a hole to be filled, so the
            # shortfall the agent acts on counts only demand that is genuinely gone.
            lost = coord.lost_units(ctx.pool, pool.id)
            assignment = ctx.repo.get_host_assignment(ctx.ws, pool.id)
            product = ctx.repo.get_product(ctx.ws, pool.product_id)
            stage = (
                ViabilityStage.FINAL_LOCK
                if pool.status in {PoolStatus.FUNDING, PoolStatus.RECOVERING}
                else ViabilityStage.PRE_FUNDING
            )
            verdict = coord.check_viability(ctx=ctx.pool, pool_id=pool.id, stage=stage)
            out.append(
                {
                    "pool_id": pool.id,
                    "product_name": product.name if product else pool.product_id,
                    "status": pool.status.value,
                    "provisional_units": provisional,
                    "funded_units": funded,
                    "threshold_units": pool.threshold_units,
                    "lost_units": lost,
                    "awaiting_decision_units": coord.in_play_units(ctx.pool, pool.id) - funded,
                    "has_host": assignment is not None,
                    "has_final_offer": pool.has_final_offer,
                    "ready_to_lock": verdict.viable and stage == ViabilityStage.FINAL_LOCK,
                    "blocking_reason": verdict.blocking_reason,
                    "failed_checks": verdict.failed,
                }
            )
        out.sort(key=lambda p: (not p["ready_to_lock"], -p["lost_units"], p["pool_id"]))
        return _json({"pools": out, "count": len(out)})

    @tool
    def recover_pool(pool_id: str) -> str:
        """Repair a pool that lost funded demand.

        Consequential. Searches the wider community for compatible unserved demand,
        authorises only members whose own Smart Join policy accepts the current final
        price, and asks everyone else. Existing buyers are never silently re-priced: a
        buyer whose share rises past their own cap is asked rather than charged.

        Args:
            pool_id: The pool to repair.
        """
        result = coord.recover_pool(ctx=ctx.pool, pool_id=pool_id)
        if result.recovered:
            ctx.outcome = RunOutcome.POOL_RECOVERED
            ctx.recovered_pool_ids.append(pool_id)
        ctx.decisions_created += len(result.invited_household_ids)
        return _json(result.to_dict())

    @tool
    def lock_pool(pool_id: str) -> str:
        """Run the final viability check and, if it passes, lock and capture.

        Consequential and irreversible for buyers. The check runs against stored facts:
        supplier minimum, quote freshness, package allocation, host assignment and pay,
        buyer authorisation, platform economics, timing, pickup site, and funding. If
        any of them fails, nothing is captured and the reason is returned.

        Args:
            pool_id: The pool to lock.
        """
        result = coord.lock_pool(ctx=ctx.pool, pool_id=pool_id)
        if result.get("locked"):
            if ctx.outcome in {RunOutcome.NO_ACTION, RunOutcome.POOL_ADVANCED}:
                ctx.outcome = RunOutcome.POOL_ADVANCED
            if pool_id not in ctx.advanced_pool_ids:
                ctx.advanced_pool_ids.append(pool_id)
        full = ctx.record_full("lock_pool", {"pool_id": pool_id}, result)
        return _json(proj.lock_view(full))

    @tool
    def execute_purchase(pool_id: str) -> str:
        """Place the bulk order for a pool whose payments have been captured.

        Consequential. In this build the executor is clearly simulated and every record
        it writes is flagged as such — no supplier is contacted and no money moves.
        Idempotent: a pool that already has a purchase record is not ordered twice.

        Args:
            pool_id: The purchase-ready pool.
        """
        result = fulfil.execute_purchase(ctx=ctx.pool, pool_id=pool_id)
        if result.get("purchased") and pool_id not in ctx.advanced_pool_ids:
            ctx.advanced_pool_ids.append(pool_id)
            if ctx.outcome == RunOutcome.NO_ACTION:
                ctx.outcome = RunOutcome.POOL_ADVANCED
        return _json(result)

    @tool
    def record_no_action(reason: str) -> str:
        """Conclude the run with no action taken, recording why.

        Use this when nothing is worth pursuing. Terminating quietly is a success:
        members should only hear from Pool when there is a real decision for them.

        Args:
            reason: Why no action was warranted.
        """
        # The reason is always worth recording, but the *outcome* is not overwritten when
        # this run already did something. A run that locked a pool and placed an order and
        # then concluded there was nothing further to do did not take "no action" — and a
        # record saying otherwise would misreport real work.
        ctx.no_action_reason = reason
        acted = bool(ctx.created_pool_ids or ctx.advanced_pool_ids or ctx.recovered_pool_ids)
        if not acted:
            ctx.outcome = RunOutcome.NO_ACTION
        return _json({"acknowledged": True, "reason": reason, "prior_actions_this_run": acted})

    return [
        list_latent_demand,
        evaluate_pool_economics,
        create_candidate_pool,
        find_host_candidates,
        request_host_acceptance,
        issue_final_offer,
        inspect_pool,
        list_pools_needing_attention,
        recover_pool,
        lock_pool,
        execute_purchase,
        record_no_action,
    ]
