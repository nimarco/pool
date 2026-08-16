"""The recovery scenario, its state snapshot, and the invariants a repair must satisfy.

Split out of ``verify_recovery_bedrock`` so the *same* scenario and the *same*
assertions run in two places:

* ``pool/scripts/verify_recovery_bedrock.py`` — a real Bedrock model chooses the tools.
  **(COSTS MONEY.)**
* ``tests/test_recovery_lifecycle.py`` — the deterministic offline planner chooses them,
  free and credential-free.

Nothing here configures the environment, constructs a model, or performs I/O beyond the
injected repository, so importing it is free and side-effect-free.

**What is scripted and what is not.** ``build_pre_recovery_state`` builds the
*situation* out of deterministic service calls with no model involved: a candidate pool
forms, a host accepts, the final offer is issued, one seeded card declines, and two
buyers have not answered yet. That is a seeded input, exactly as in the showcase
scenario. What the coordinator then does about it is not scripted.

The scenario is deliberately shaped so the two easy mistakes are distinguishable:

* lost demand is **2 units** (one declined card)
* demand still awaiting a human answer is **4 units** (two unanswered buyers)

A coordinator that treats "not answered yet" as "gone" recruits 6 units instead of 2,
overshoots the 24-unit order priced against whole 12-unit cases, and creates exactly the
speculative surplus §48 exists to prevent. A coordinator that forces a lock to look
successful captures money from a pool two buyers never approved.
"""

from __future__ import annotations

import json
from typing import Any

from ..agent import projection as proj
from ..data.seed import COMMUNITY_ID, seed
from ..domain.models import (
    DecisionState,
    HostProfile,
    ParticipationState,
    PaymentState,
    PoolStatus,
    RunOutcome,
)
from ..services import coordination as coord
from ..services import hosting
from ..services.context import PoolContext

PRODUCT = "prod_whey_vanilla"
SITE = "site_union"
#: The pool member who volunteers to host — the same one the showcase scenario uses.
VOLUNTEER_HOST = "hh_thibault"

#: Verbatim from ``pool/services/demo.py`` step 7. The wording is the product's, not this
#: module's: it names no pool, no tool, and no unit count, and it deliberately invites a
#: lock so the deterministic rules have to be the thing that refuses one.
RECOVERY_INSTRUCTION = (
    "A buyer authorisation failed and a pool is short of funded demand. Recover "
    "any pool below its threshold, disturbing as few people as possible, then "
    "lock anything that has become viable."
)

#: Tools whose result the coordinator sees as a projection, and the projection that
#: produced it. Used to prove the coordinator was shown a faithful view of the
#: authoritative result rather than a paraphrase of it.
PROJECTIONS = {
    "list_latent_demand": lambda full: proj.demand_view(full.get("opportunities") or []),
    "evaluate_pool_economics": proj.opportunity_view,
    "find_host_candidates": proj.host_evaluation_view,
    "request_host_acceptance": proj.host_evaluation_view,
    "issue_final_offer": proj.final_offer_view,
    "inspect_pool": proj.pool_view,
    "lock_pool": proj.lock_view,
}

#: Read tools that can hand the coordinator a pool id it did not invent.
GROUNDING_TOOLS = {"list_pools_needing_attention", "inspect_pool", "list_latent_demand"}


class ScenarioSetupError(RuntimeError):
    """The seeded situation did not come out as the scenario requires."""


# --------------------------------------------------------------------------- scenario


def build_pre_recovery_state(coordinator, repo, ws: str):
    """Drive the deterministic lifecycle to the moment committed demand is lost.

    No model runs here. These are the same service calls the offline tests and the
    showcase scenario make, against the same seeded community.

    Shares the coordinator's own adapters so the payment intents authorised here are the
    ones the agent's tools later see.

    Returns ``(ctx, pool, final_offer_result)``.
    """
    seed(repo, ws)
    ctx = PoolContext(
        repo=repo,
        ws=ws,
        routing=coordinator.routing,
        payments=coordinator.payments,
        purchaser=coordinator.purchaser,
        sourcing=coordinator.sourcing,
    )

    assessment = coord.evaluate_opportunity(
        ctx=ctx, community_id=COMMUNITY_ID, product_id=PRODUCT, pickup_site_id=SITE
    )
    if not assessment.viable:
        raise ScenarioSetupError(f"no viable opportunity: {assessment.reason}")
    pool, _ = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key="recovery_scenario"
    )

    hosting.open_host_recruiting(ctx=ctx, pool_id=pool.id)
    hosting.volunteer_to_host(
        ctx=ctx,
        pool_id=pool.id,
        household_id=VOLUNTEER_HOST,
        profile=HostProfile(
            household_id=VOLUNTEER_HOST,
            community_id=COMMUNITY_ID,
            has_vehicle=True,
            vehicle_capacity_units=60,
            max_orders=40,
            max_weight_kg=80,
            max_supplier_distance_km=16.0,
            minimum_compensation_cents=3000,
            standing=False,
        ),
    )
    offer = hosting.offer_to_next_host(ctx=ctx, pool_id=pool.id)
    if not offer.offered_household_id:
        raise ScenarioSetupError(f"no host was offered the job: {offer.reason}")
    hosting.respond_to_host_offer(
        ctx=ctx, pool_id=pool.id, household_id=offer.offered_household_id, accept=True
    )

    final = coord.issue_final_offer(ctx=ctx, pool_id=pool.id)
    if not final.issued:
        raise ScenarioSetupError(f"no final offer was issued: {final.reason}")
    if not final.authorisation_failures:
        raise ScenarioSetupError("no authorisation failed, so no demand was lost")
    if not final.awaiting_decision:
        raise ScenarioSetupError("nobody is awaiting a decision, so the two cases merge")
    stored = repo.get_pool(ws, pool.id)
    assert stored is not None
    return ctx, stored, final


def snapshot(ctx: PoolContext, pool_id: str) -> dict[str, Any]:
    """The authoritative lifecycle state, read straight from the store."""
    pool = ctx.repo.get_pool(ctx.ws, pool_id)
    if pool is None:
        raise ScenarioSetupError(f"unknown pool: {pool_id}")
    members = ctx.repo.list_memberships(ctx.ws, pool_id)
    econ = pool.final_economics or {}
    packages = econ.get("packages") or {}
    payments = ctx.repo.list_payments(ctx.ws, pool_id)
    pending = [
        d
        for d in ctx.repo.list_decisions(ctx.ws)
        if d.pool_id == pool_id and d.state == DecisionState.PENDING
    ]
    return {
        "status": pool.status.value,
        "threshold_units": pool.threshold_units,
        "priced_units": packages.get("total_units", 0),
        "case_units": packages.get("case_units", 0),
        "surplus_units": packages.get("surplus_units", 0),
        "all_in_cents": econ.get("all_in_cents", 0),
        "quote_verified_at": pool.quote_verified_at,
        "funded_units": coord.funded_units(ctx, pool_id),
        "in_play_units": coord.in_play_units(ctx, pool_id),
        "lost_units": coord.lost_units(ctx, pool_id),
        "members_total": len(members),
        "authorized": sum(1 for m in members if m.counts_as_funded),
        "awaiting_decision": sum(
            1 for m in members if m.state == ParticipationState.FINAL_OFFERED
        ),
        "authorization_failed": sum(
            1 for m in members if m.state == ParticipationState.AUTHORIZATION_FAILED
        ),
        "awaiting_units": sum(
            m.allocated_units for m in members if m.state == ParticipationState.FINAL_OFFERED
        ),
        "pending_decisions": len(pending),
        "pending_households": sorted(d.household_id for d in pending),
        "member_states": {m.household_id: m.state.value for m in members},
        "captured_payments": sum(1 for p in payments if p.state == PaymentState.CAPTURED),
        "captured_cents": sum(
            p.amount_cents for p in payments if p.state == PaymentState.CAPTURED
        ),
    }


# --------------------------------------------------------------------------- invariants


def projection_faithfulness(ctx, run) -> list[str]:
    """Check the coordinator saw a faithful projection of each authoritative result.

    ``BoundedRun`` records the first 180 characters of the exact string Strands handed
    back to the model. Re-projecting the retained authoritative result and comparing
    proves the model was shown that result's projection, not a paraphrase of it — and
    so that every figure it saw is the deterministic service's own (AGENTS.md §5).
    """
    problems: list[str] = []
    for record in run.tool_calls:
        project = PROJECTIONS.get(record.name)
        if project is None or not record.ok:
            continue
        # A tool that refused an unknown identifier returns a plain error and retains
        # nothing; there is no projection for it to be unfaithful to.
        if record.summary.startswith('{"error"'):
            continue
        entries = [e for e in ctx.full_results if e.tool == record.name]
        if not entries:
            problems.append(f"{record.name}: no authoritative result was retained")
            continue
        seen = record.summary.rstrip("…")
        if not any(
            json.dumps(project(e.result), default=str).startswith(seen) for e in entries
        ):
            problems.append(
                f"{record.name}: what the model saw is not the projection of any "
                f"retained result (saw {seen[:60]!r})"
            )
    return problems


def recovery_semantics(
    before: dict[str, Any], after: dict[str, Any], run, projection_problems: list[str]
) -> dict[str, bool]:
    """Did the coordinator repair the pool without breaking anything it must not?

    Model-agnostic on purpose: whatever chose the tools, these are the lifecycle
    semantics the repair has to satisfy.
    """
    # The call that actually repaired the pool is the first `recover_pool` the
    # deterministic layer *accepted*. A rejected one — the model guessing an identifier
    # before it has read anything — neither repairs nor grounds, so scoring against it
    # would blame the run for a call that changed nothing.
    repaired_at = next(
        (i for i, t in enumerate(run.tool_calls) if t.name == "recover_pool" and t.ok), None
    )
    grounded = repaired_at is not None and any(
        t.name in GROUNDING_TOOLS and t.ok for t in run.tool_calls[:repaired_at]
    )
    return {
        "coordinator chose an existing Pool recovery tool": repaired_at is not None,
        # The instruction names no pool, so a valid pool id can only have come out of a
        # read tool first.
        "pool id came from an inspection tool, not the model": grounded,
        "recovery replaced exactly what was lost": (
            after["in_play_units"] - before["in_play_units"] == before["lost_units"]
        ),
        "did not over-recruit": after["in_play_units"] == after["priced_units"],
        "pending human decisions were not treated as lost demand": (
            after["pending_households"] == before["pending_households"]
            and after["awaiting_units"] == before["awaiting_units"]
        ),
        "package/case boundary preserved": (
            after["surplus_units"] == 0
            and after["case_units"] > 0
            and after["priced_units"] % after["case_units"] == 0
        ),
        "authoritative economics unchanged by the repair": (
            after["all_in_cents"] == before["all_in_cents"]
            and after["priced_units"] == before["priced_units"]
            and after["quote_verified_at"] == before["quote_verified_at"]
        ),
        "successful work not overwritten by record_no_action": (
            run.outcome == RunOutcome.POOL_RECOVERED
        ),
        "pool did not lock while buyers are still deciding": after["status"]
        not in {
            PoolStatus.LOCKED.value,
            PoolStatus.PURCHASE_READY.value,
            PoolStatus.PURCHASED.value,
        },
        "no payment was captured in this run": after["captured_payments"] == 0,
        "projections were faithful to the authoritative results": not projection_problems,
        # Not a property of the system: a rejected call means the model passed an
        # argument the deterministic layer would not accept. The refusal itself is
        # correct behaviour (see test_recovery_lifecycle), but it is worth surfacing.
        "every tool call the model made was accepted": all(t.ok for t in run.tool_calls),
    }


def lock_semantics(
    before: dict[str, Any], after: dict[str, Any], run, projection_problems: list[str]
) -> dict[str, bool]:
    """Once the humans answered, did the coordinator know a lock was allowed?"""
    names = [t.name for t in run.tool_calls]
    return {
        "coordinator chose to lock once the rules allowed it": "lock_pool" in names,
        "pool locked": after["status"]
        in {
            PoolStatus.LOCKED.value,
            PoolStatus.PURCHASE_READY.value,
            PoolStatus.PURCHASED.value,
        },
        "every funded buyer was captured": after["captured_payments"] == after["authorized"],
        "captured total equals the deterministic landed price": (
            after["captured_cents"] == after["all_in_cents"]
        ),
        "no unit was added to reach the lock": after["in_play_units"] == before["in_play_units"],
        "projections were faithful to the authoritative results": not projection_problems,
        # Not a property of the system: a rejected call means the model passed an
        # argument the deterministic layer would not accept. The refusal itself is
        # correct behaviour (see test_recovery_lifecycle), but it is worth surfacing.
        "every tool call the model made was accepted": all(t.ok for t in run.tool_calls),
    }


def bound_checks(run, settings) -> dict[str, bool]:
    """The AGENTS.md §3.1 safety bounds, as observed by this run."""
    return {
        "iterations within bound": run.iterations <= settings.bounds.max_iterations,
        "tool calls within bound": len(run.tool_calls) <= settings.bounds.max_tool_calls,
        "run terminated with a recorded reason": bool(run.termination_reason),
    }


def failures(checks: dict[str, bool]) -> list[str]:
    return [label for label, ok in checks.items() if not ok]
