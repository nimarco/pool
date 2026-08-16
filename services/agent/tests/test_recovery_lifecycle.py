"""The consequential recovery branch, asserted offline against the same invariants
the real-Bedrock verification asserts.

A funded pool loses committed demand to a declined card while two other buyers are still
deciding. The coordinator has to notice, repair only the hole, and know that the repaired
pool may not lock yet.

The invariants live in ``pool/scripts/recovery_scenario.py`` and are shared with
``pool/scripts/verify_recovery_bedrock.py``. That is the point: this file proves the
semantics hold, for free and with no credentials, and the paid script proves a real
Bedrock model reaches the same place. If the two ever disagree, the difference is the
model's judgement, which is exactly the thing worth looking at.

Runs entirely offline and free — deterministic planner, simulated payments, deterministic
routing. No AWS call, no token spend (AGENTS.md §3.6).
"""

from __future__ import annotations

import json

import pytest

from pool.adapters.repository import InMemoryRepository
from pool.agent.coordinator import PoolCoordinator
from pool.agent.offline_model import DeterministicPlannerModel, _tool_event
from pool.config import AgentBounds, Settings
from pool.data.seed import COMMUNITY_ID
from pool.domain.models import DecisionKind, DecisionState, ParticipationState, RunOutcome
from pool.domain.viability import ViabilityStage
from pool.scripts.recovery_scenario import (
    RECOVERY_INSTRUCTION,
    bound_checks,
    build_pre_recovery_state,
    failures,
    lock_semantics,
    projection_faithfulness,
    recovery_semantics,
    snapshot,
)
from pool.services import coordination as coord
from pool.services.context import CoordinationError
from pool.services.fulfillment import FulfillmentError

WS = "recovery_lifecycle"


@pytest.fixture
def settings() -> Settings:
    """Explicit offline settings, so the suite cannot be steered at a paid model by a
    stray environment variable."""
    return Settings(
        model_provider="offline",
        repository="memory",
        routing_provider="deterministic",
        payment_provider="simulated",
        purchase_executor="simulated",
        bounds=AgentBounds(),
    )


@pytest.fixture
def scenario(settings):
    """The pre-recovery situation: 2 units lost, 4 units merely unanswered."""
    repo = InMemoryRepository()
    coordinator = PoolCoordinator(repo, settings=settings)
    ctx, pool, final = build_pre_recovery_state(coordinator, repo, WS)
    return coordinator, repo, ctx, pool, final


def _run(coordinator):
    return coordinator.run(
        WS,
        trigger="recovery_test",
        community_id=COMMUNITY_ID,
        instruction=RECOVERY_INSTRUCTION,
    )


def _answer_pending(repo, ctx) -> int:
    answered = 0
    for d in list(repo.list_decisions(WS)):
        if d.state == DecisionState.PENDING and d.kind == DecisionKind.APPROVE_FINAL_OFFER:
            coord.respond_to_decision(ctx=ctx, decision_id=d.id, approve=True)
            answered += 1
    return answered


# ------------------------------------------------------------------ the situation


def test_the_scenario_distinguishes_lost_demand_from_unanswered_demand(scenario):
    """The whole test rests on these being different numbers.

    If they ever collapse into one, a coordinator that confuses "gone" with "has not
    replied yet" would pass every assertion below without being correct.
    """
    _, _, ctx, pool, _ = scenario
    state = snapshot(ctx, pool.id)
    assert state["lost_units"] > 0
    assert state["awaiting_units"] > 0
    assert state["lost_units"] != state["awaiting_units"]
    assert state["in_play_units"] == state["priced_units"] - state["lost_units"]
    # The order is priced against whole cases, so over-recruiting cannot stay clean.
    assert state["priced_units"] % state["case_units"] == 0
    assert (state["in_play_units"] + state["awaiting_units"]) % state["case_units"] != 0


# ------------------------------------------------------------------- the recovery


def test_the_recovery_branch_satisfies_every_lifecycle_invariant(scenario, settings):
    coordinator, _repo, ctx, pool, _ = scenario
    before = snapshot(ctx, pool.id)
    run = _run(coordinator)
    after = snapshot(ctx, pool.id)
    problems = projection_faithfulness(coordinator.last_tool_context, run)
    checks = {
        **recovery_semantics(before, after, run, problems),
        **bound_checks(run, settings),
    }
    assert not failures(checks), f"{failures(checks)} (projection: {problems})"


def test_recovery_replaces_the_hole_and_not_the_pending_replies(scenario):
    coordinator, _repo, ctx, pool, _ = scenario
    before = snapshot(ctx, pool.id)
    _run(coordinator)
    after = snapshot(ctx, pool.id)
    assert after["in_play_units"] - before["in_play_units"] == before["lost_units"]
    assert after["in_play_units"] == after["priced_units"]
    assert after["lost_units"] == 0
    # Nobody who was already waiting on a human was disturbed or replaced.
    assert after["pending_households"] == before["pending_households"]
    assert after["awaiting_units"] == before["awaiting_units"]


def test_the_repaired_pool_may_not_lock_while_buyers_are_still_deciding(scenario):
    """Deterministic lifecycle rules stay authoritative even when the instruction
    explicitly invites a lock."""
    coordinator, repo, ctx, pool, _ = scenario
    assert "lock" in RECOVERY_INSTRUCTION
    _run(coordinator)
    after = snapshot(ctx, pool.id)
    assert after["captured_payments"] == 0
    assert after["status"] == "funding"
    verdict = coord.check_viability(
        ctx=ctx, pool_id=pool.id, stage=ViabilityStage.FINAL_LOCK
    )
    assert not verdict.viable
    assert "buyer_decisions_settled" in verdict.failed
    assert repo.get_pool(WS, pool.id).final_economics


def test_a_run_that_recovered_is_not_recorded_as_no_action(scenario):
    """§0016's fix: concluding "nothing further to do" must not erase real work."""
    coordinator, _repo, _ctx, _pool, _ = scenario
    run = _run(coordinator)
    assert "recover_pool" in [t.name for t in run.tool_calls]
    assert run.outcome == RunOutcome.POOL_RECOVERED
    if "record_no_action" in [t.name for t in run.tool_calls]:
        # The reason is still recorded — only the outcome is protected.
        assert run.notes


def test_the_replacement_buyer_was_authorised_by_their_own_policy(scenario):
    """A replacement is a real commitment, so it passes the same Smart Join gate."""
    coordinator, repo, ctx, pool, final = scenario
    before = {m.household_id for m in repo.list_memberships(WS, pool.id)}
    _run(coordinator)
    added = [
        m for m in repo.list_memberships(WS, pool.id) if m.household_id not in before
    ]
    assert added, "recovery added nobody"
    for m in added:
        assert m.household_id not in final.auto_authorised
        assert m.state in {
            ParticipationState.AUTHORIZED,
            ParticipationState.FINAL_OFFERED,
        }
        assert m.final_cost_cents > 0
        if m.state == ParticipationState.AUTHORIZED:
            assert m.path.value in {"smart_join", "human_approved"}
        else:
            # Not auto-authorised means a human was asked, not charged.
            assert any(
                d.household_id == m.household_id and d.state == DecisionState.PENDING
                for d in repo.list_decisions(WS)
            )


# ------------------------------------------------------------------- then the lock


def test_the_lock_becomes_allowed_once_the_humans_answer(scenario, settings):
    coordinator, repo, ctx, pool, _ = scenario
    _run(coordinator)
    assert _answer_pending(repo, ctx) > 0
    mid = snapshot(ctx, pool.id)
    run2 = coordinator.run(
        WS, trigger="recovery_test", community_id=COMMUNITY_ID,
        instruction=RECOVERY_INSTRUCTION,
    )
    after = snapshot(ctx, pool.id)
    problems = projection_faithfulness(coordinator.last_tool_context, run2)
    checks = {**lock_semantics(mid, after, run2, problems), **bound_checks(run2, settings)}
    assert not failures(checks), f"{failures(checks)} (projection: {problems})"
    assert after["captured_cents"] == after["all_in_cents"]


# ------------------------------------------------- identifiers the model made up
#
# Found by a real Bedrock run (BUILD_HISTORY #0021): with no tool result to ground it,
# the model opened a turn by calling `recover_pool(pool_id="short_of_demand_pool")` — a
# plausible-looking identifier it invented. Nothing asserted what happens next, so this
# does.


@pytest.mark.parametrize(
    ("tool_name", "kwargs"),
    [
        ("recover_pool", {"pool_id": "short_of_demand_pool"}),
        ("lock_pool", {"pool_id": "short_of_demand_pool"}),
        ("execute_purchase", {"pool_id": "short_of_demand_pool"}),
        ("issue_final_offer", {"pool_id": "short_of_demand_pool"}),
        ("find_host_candidates", {"pool_id": "short_of_demand_pool"}),
        ("request_host_acceptance", {"pool_id": "short_of_demand_pool"}),
        (
            "create_candidate_pool",
            {"product_id": "prod_invented", "pickup_site_id": "site_invented"},
        ),
    ],
)
def test_a_consequential_tool_given_an_invented_identifier_changes_nothing(
    scenario, tool_name, kwargs
):
    """The refusal must happen before anything is written, not after.

    A tool that half-executed on an identifier the model made up would be the worst
    possible failure here: money, membership, or lifecycle state moved on a fact that
    was never true (AGENTS.md §4, §5).
    """
    from pool.agent.tools import ToolContext, build_tools

    _coordinator, repo, ctx, pool, _ = scenario
    before = snapshot(ctx, pool.id)
    counts_before = (
        len(repo.list_pools(WS)),
        len(repo.list_memberships(WS, pool.id)),
        len(repo.list_payments(WS, pool.id)),
        len(repo.list_decisions(WS)),
        len(repo.list_activity(WS, limit=999)),
    )

    tctx = ToolContext(pool=ctx, community_id=COMMUNITY_ID)
    tools = {t.tool_name: t for t in build_tools(tctx)}
    with pytest.raises((CoordinationError, FulfillmentError)) as exc:
        tools[tool_name](**kwargs)
    assert "unknown" in str(exc.value)

    assert snapshot(ctx, pool.id) == before
    assert counts_before == (
        len(repo.list_pools(WS)),
        len(repo.list_memberships(WS, pool.id)),
        len(repo.list_payments(WS, pool.id)),
        len(repo.list_decisions(WS)),
        len(repo.list_activity(WS, limit=999)),
    )
    # The run's own bookkeeping is untouched too, so a refused call cannot make a run
    # report work it did not do.
    assert tctx.outcome == RunOutcome.NO_ACTION
    assert not (tctx.created_pool_ids or tctx.advanced_pool_ids or tctx.recovered_pool_ids)
    assert tctx.decisions_created == 0


def test_reading_a_pool_that_does_not_exist_is_answered_not_raised(scenario):
    """`inspect_pool` is a read, so an unknown id is a fact to report, not an error —
    which is how the model can correct course without burning the run."""
    from pool.agent.tools import ToolContext, build_tools

    _coordinator, _repo, ctx, _pool, _ = scenario
    tctx = ToolContext(pool=ctx, community_id=COMMUNITY_ID)
    tools = {t.tool_name: t for t in build_tools(tctx)}
    result = json.loads(tools["inspect_pool"](pool_id="short_of_demand_pool"))
    assert result == {"error": "unknown pool", "pool_id": "short_of_demand_pool"}


class HallucinatingPlanner(DeterministicPlannerModel):
    """The planner, but it opens with the invented identifier the real model used.

    Reproduces BUILD_HISTORY #0021's observed behaviour deterministically so the
    recovery-from-a-bad-call path is exercised without paying for a model.
    """

    def _decide(self, view):
        if not view.calls:
            return _tool_event("recover_pool", {"pool_id": "short_of_demand_pool"})
        return super()._decide(view)


def test_a_run_survives_the_model_inventing_an_identifier(settings, scenario):
    """The observed real-model behaviour end to end: the invented call is rejected and
    recorded, the model reads its work queue, and the run still lands correctly."""
    _coordinator, repo, ctx, pool, _ = scenario
    coordinator = PoolCoordinator(repo, settings=settings, model=HallucinatingPlanner())
    before = snapshot(ctx, pool.id)
    run = _run(coordinator)

    rejected = [t for t in run.tool_calls if not t.ok]
    assert len(rejected) == 1
    assert rejected[0].name == "recover_pool"
    assert "unknown pool" in rejected[0].summary

    after = snapshot(ctx, pool.id)
    problems = projection_faithfulness(coordinator.last_tool_context, run)
    checks = recovery_semantics(before, after, run, problems)
    # Everything except the model-quality signal still holds: the pool was repaired
    # exactly once, from the real identifier, and nothing moved on the invented one.
    assert failures(checks) == ["every tool call the model made was accepted"]
    assert run.termination_reason == "completed"
    assert run.outcome == RunOutcome.POOL_RECOVERED


# --------------------------------------------------------- what the model was shown


def test_the_work_queue_shows_lost_and_unanswered_demand_separately(scenario):
    """The one fact the recovery decision cannot be made without.

    A projection that saved tokens by collapsing "gone" and "has not replied yet" into a
    single shortfall would buy cost savings with a wrong decision (AGENTS.md §5).
    """
    coordinator, _repo, ctx, pool, _ = scenario
    from pool.agent.tools import ToolContext, build_tools

    tctx = ToolContext(pool=ctx, community_id=COMMUNITY_ID)
    tools = {t.tool_name: t for t in build_tools(tctx)}
    queue = json.loads(tools["list_pools_needing_attention"]())
    entry = next(p for p in queue["pools"] if p["pool_id"] == pool.id)
    state = snapshot(ctx, pool.id)
    assert entry["lost_units"] == state["lost_units"]
    assert entry["awaiting_decision_units"] == state["awaiting_units"]
    assert entry["lost_units"] != entry["awaiting_decision_units"]
    assert entry["ready_to_lock"] is False
    assert entry["blocking_reason"]

    # And the coordinator actually reads it before repairing anything.
    run = _run(coordinator)
    assert "list_pools_needing_attention" in [t.name for t in run.tool_calls]
    assert not projection_faithfulness(coordinator.last_tool_context, run)
    full_names = {e.tool for e in coordinator.last_tool_context.full_results}
    for record in run.tool_calls:
        if record.name in {"inspect_pool", "lock_pool"} and record.ok:
            assert record.name in full_names


def test_the_authoritative_result_is_richer_than_what_the_model_saw(scenario):
    """The projection is a cost boundary, not a truth boundary: the operator UI and the
    audit trail still get the full viability roster."""
    coordinator, _repo, ctx, pool, _ = scenario
    from pool.agent.tools import ToolContext, build_tools

    tctx = ToolContext(pool=ctx, community_id=COMMUNITY_ID)
    tools = {t.tool_name: t for t in build_tools(tctx)}
    projected = tools["inspect_pool"](pool_id=pool.id)
    full = tctx.last_full_result("inspect_pool")
    assert full is not None
    assert full["viability"]["checks"], "the full result lost its check roster"
    assert "checks" not in projected
    # Every figure that survived is the service's own, not a re-derived one.
    for key in ("funded_units", "threshold_units", "provisional_units"):
        assert f'"{key}": {full[key]}' in projected
