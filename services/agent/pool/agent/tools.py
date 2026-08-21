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

from ..config import AgentBounds, get_settings
from ..domain.models import (
    DecisionState,
    ParticipationState,
    PoolStatus,
    RunOutcome,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.viability import ViabilityStage
from ..services import coordination as coord
from ..services import discovery, hosting
from ..services import fulfillment as fulfil
from ..services import strategy as strategy_svc
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
    #: The bounded question this run is answering (``agent/objective.py``). Derived by
    #: the coordinator from stored state, never from a caller. ``None`` only in the
    #: narrow unit tests that build a context directly.
    objective: Any = None
    outcome: RunOutcome = RunOutcome.NO_ACTION
    created_pool_ids: list[str] = field(default_factory=list)
    advanced_pool_ids: list[str] = field(default_factory=list)
    recovered_pool_ids: list[str] = field(default_factory=list)
    decisions_created: int = 0
    no_action_reason: str = ""
    #: Authoritative results in call order, for auditing and any consumer that needs
    #: the detail the model is deliberately not shown.
    full_results: list[FullToolResult] = field(default_factory=list)

    #: Hard caps on the strategy surface. Held here rather than read from settings inside
    #: each tool so one run cannot see two different budgets.
    bounds: AgentBounds = field(default_factory=lambda: get_settings().bounds)
    #: Options this run itself listed. An id the model did not receive from
    #: ``list_cohort_strategies`` in *this* run is refused — a strategy is evidence about
    #: one objective, and accepting an id from anywhere else would let one run act on
    #: another run's question.
    listed_strategy_ids: list[str] = field(default_factory=list)
    strategy_listings: int = 0
    #: Options actually evaluated, in order, so a repeat is visible as a repeat.
    evaluated_strategy_ids: list[str] = field(default_factory=list)
    strategy_pool_creations: int = 0

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

    The rule lives in ``services.discovery`` so discovery and the tool cannot disagree
    about which site an opportunity is proposed at.
    """
    return discovery.suggest_site(ctx.pool, ctx.community_id, household_ids)


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

#: The cohort-strategy surface, offered *instead of* latent demand when a declaration
#: event is the question (``objective.searches_strategies``). Kept separate rather than
#: merged so a run never holds two doors to the same mutation — only
#: ``create_candidate_pool_from_strategy`` is guarded by ``ensure_actionable``, and a run
#: that could also reach ``create_candidate_pool`` would have an unguarded way past it.
STRATEGY_TOOL_SURFACE: tuple[tuple[str, str], ...] = (
    ("list_cohort_strategies", "record"),
    ("evaluate_cohort_strategy", "record"),
    ("create_candidate_pool_from_strategy", "act"),
)

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
        """List products in this community worth investigating, and why.

        Read-only. This is where the product's core claim lives: nobody declared a
        group, so the opportunity has to be discovered from standing declarations.

        ``unserved_units`` and ``member_count`` count only declarations whose own
        substitution rules a pool for that product could actually serve, and that no
        live pool is already serving — the same rule the matcher applies later, so this
        listing and the evaluation cannot disagree about who constitutes demand.
        ``group_interest_units`` is the wider category, for context only.

        When this run was triggered by a member, the entries marked ``for_member`` are
        that member's own declarations, listed first and in priority order, each
        naming the declaration behind it. Evaluate every one of those before acting.
        """
        full = discovery.latent_demand(ctx.pool, ctx.community_id, ctx.objective)
        ctx.record_full("list_latent_demand", {}, full)
        return _json(proj.demand_view(full["opportunities"], objective=full["objective"]))

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
        # Whether *this run's own member* would be in the order. A deterministic fact,
        # computed here rather than left to the model, and the difference between "Pool
        # formed the thing you asked about" and "Pool formed an order you are not in"
        # (§48). Absent on a community scan, which has no member to be in anything.
        objective_needs = {
            entry.need_id
            for entry in (getattr(ctx.objective, "needs", ()) or ())
            if product_id in entry.target_product_ids
        }
        if objective_needs:
            payload["includes_member_declaration"] = bool(
                objective_needs & {c.need_id for c in assessment.candidates}
            )
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

    # ------------------------------------------------------- cohort strategies
    #
    # Offered only when a declaration event is the question. Each one is bounded by its
    # own budget as well as by the global run bounds, because "well-behaved by every
    # global measure and still more expensive than the question is worth" is a real
    # failure mode for a search (AGENTS.md §3.1, §3.3).

    def _objective_strategy_objective():
        return strategy_svc.StrategyObjective(
            kind=strategy_svc.OBJECTIVE_MEMBER,
            community_id=ctx.community_id,
            household_id=getattr(ctx.objective, "household_id", "") or "",
            need_id=getattr(ctx.objective, "anchor_need_id", "") or "",
        )

    @tool
    def list_cohort_strategies() -> str:
        """List the distinct orders Pool could assemble from this declaration's demand.

        Takes no arguments: the question is the one this run was given, and there is no
        field in which to ask about another member, another Community, or another
        product.

        Each option names an exact product, its curated attributes, how much compatible
        demand its own rules admit, how that demand splits between now and demand pulled
        forward, how many declarations it refused and under which codes, where it would
        be handed over, and the lowest quantity any supplier will sell.

        **No option carries a verdict, and none is ranked as the winner.** Nothing has
        been costed yet: which supplier tier wins, whether the demand fills whole cases,
        what the group would pay and whether that beats buying alone are facts about a
        chosen buyer set, and choosing one is what evaluation does. Clearing a supplier
        minimum is necessary and nowhere near sufficient — an option with plenty of
        demand can still cost more than buying alone once fulfilment and processing are
        paid for.
        """
        if ctx.strategy_listings >= ctx.bounds.max_strategy_listings:
            return _json(
                {
                    "listed": False,
                    "reason": "already listed this run; the options are derived from state "
                    "no read-only call has changed",
                    "strategies": [],
                }
            )
        ctx.strategy_listings += 1
        strategies = strategy_svc.generate_strategies(
            ctx=ctx.pool, objective=_objective_strategy_objective()
        )
        for strategy in strategies:
            if strategy.id not in ctx.listed_strategy_ids:
                ctx.listed_strategy_ids.append(strategy.id)
        summaries = [strategy_svc.strategy_summary(s) for s in strategies]
        full = ctx.record_full(
            "list_cohort_strategies", {}, {"strategies": [s.to_dict() for s in strategies]}
        )
        del full
        return _json(
            {
                "strategies": summaries,
                "count": len(summaries),
                "evaluations_allowed": ctx.bounds.max_strategy_evaluations,
            }
        )

    @tool
    def evaluate_cohort_strategy(strategy_id: str) -> str:
        """Cost one listed option against current authoritative state.

        This is the answer, and it is not yours to argue with: compatible demand after
        timing and geography, the supplier tier that wins, whether the demand fills whole
        cases with nothing left over, the complete landed price including fulfilment and
        processing, whether that beats buying alone, how many members' own Smart Join
        rules accept it, and whether the declaration that caused this run is inside the
        result.

        A refusal is a result. If this option is refused, decide whether another listed
        option is materially worth investigating — do not re-evaluate this one, and do
        not form it anyway.

        Args:
            strategy_id: The id of an option returned by list_cohort_strategies.
        """
        if strategy_id not in ctx.listed_strategy_ids:
            return _json(
                {
                    "evaluated": False,
                    "reason": "that option was not offered by this run's own listing",
                    "strategy_id": strategy_id,
                }
            )
        remaining = ctx.bounds.max_strategy_evaluations - len(ctx.evaluated_strategy_ids)
        if strategy_id in ctx.evaluated_strategy_ids:
            return _json(
                {
                    "evaluated": False,
                    "reason": "already evaluated this run; the answer has not changed",
                    "strategy_id": strategy_id,
                    "evaluations_remaining": remaining,
                }
            )
        if remaining <= 0:
            return _json(
                {
                    "evaluated": False,
                    "reason": "evaluation budget exhausted for this declaration",
                    "strategy_id": strategy_id,
                    "evaluations_remaining": 0,
                }
            )

        ctx.evaluated_strategy_ids.append(strategy_id)
        evaluation = strategy_svc.evaluate_strategy(ctx=ctx.pool, strategy_id=strategy_id)
        ctx.record_full(
            "evaluate_cohort_strategy", {"strategy_id": strategy_id}, evaluation.to_dict()
        )
        payload = strategy_svc.evaluation_summary(evaluation)
        payload["evaluations_remaining"] = (
            ctx.bounds.max_strategy_evaluations - len(ctx.evaluated_strategy_ids)
        )
        payload["options_not_yet_evaluated"] = [
            sid for sid in ctx.listed_strategy_ids if sid not in ctx.evaluated_strategy_ids
        ]
        return _json(payload)

    @tool
    def create_candidate_pool_from_strategy(strategy_id: str, evaluation_id: str) -> str:
        """Form a candidate pool from an option a specific evaluation confirmed viable.

        Consequential, and it commits no money: members join **provisionally**, the
        saving shown is an estimate, and fulfilment is still being recruited. No card is
        touched until a host accepts and the exact final price is known.

        You supply two identifiers and nothing else. Who is in the order, how many units
        each takes, what it costs and which supplier tier is used are all re-derived from
        stored state — and re-derived *again* here, because evidence that was true when
        you read it may not be true now. If anything it rested on has moved, this refuses
        rather than building a pool from a stale answer.

        Args:
            strategy_id: The option to form.
            evaluation_id: The evaluation that confirmed it viable.
        """
        if strategy_id not in ctx.listed_strategy_ids:
            return _json(
                {
                    "created": False,
                    "refusal_code": "strategy_not_in_this_run",
                    "refusal_reason": "that option was not offered by this run's own listing",
                }
            )
        if ctx.strategy_pool_creations >= ctx.bounds.max_strategy_pool_creations:
            return _json(
                {
                    "created": False,
                    "refusal_code": "creation_budget_exhausted",
                    "refusal_reason": "one order has already been formed for this declaration",
                }
            )

        ctx.strategy_pool_creations += 1
        result = strategy_svc.create_candidate_pool_from_strategy(
            ctx=ctx.pool,
            strategy_id=strategy_id,
            evaluation_id=evaluation_id,
            # A member-anchored question may only be answered by an order that member is
            # actually in. An order that is viable for the neighbours is a real outcome
            # and a different one (AGENTS.md §8).
            require_objective_need=True,
        )
        full = ctx.record_full(
            "create_candidate_pool_from_strategy",
            {"strategy_id": strategy_id, "evaluation_id": evaluation_id},
            result.to_dict(),
        )
        if result.created:
            ctx.outcome = RunOutcome.POOL_CREATED
            ctx.created_pool_ids.append(result.pool_id)
        elif result.pool_id:
            # An equivalent pool already existed. Not created, not a refusal.
            if result.pool_id not in ctx.advanced_pool_ids:
                ctx.advanced_pool_ids.append(result.pool_id)
        return _json(full)

    if getattr(ctx.objective, "searches_strategies", False):
        return [
            list_cohort_strategies,
            evaluate_cohort_strategy,
            create_candidate_pool_from_strategy,
            find_host_candidates,
            request_host_acceptance,
            inspect_pool,
            record_no_action,
        ]

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
