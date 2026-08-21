"""A declaration becomes coordination, once, and the run that answers it is a search.

Three things are proved here, and the third is the one the phase exists for.

**One cause, one event, one run.** Submitting a form twice, reloading the page, or saving
an edit that changed nothing must not buy a second model call. Dedupe is identity: an
event's id is a digest of the declaration and its content, so the duplicate resolves to
the row that already exists.

**The run is attributable.** Event → run → pool is a chain a person can follow
afterwards, and each link is stored rather than inferred from timestamps.

**The model is choosing, and cannot cheat.** The canonical fixture offers two options
that look equally plausible in the listing; the first one costed is refused on economics
nothing in the listing could have contained; the run adapts and costs the second; and the
pool that forms is built entirely from re-derived state, because the only things the
model supplied were two identifiers.

The planner driving that sequence is deterministic, and this module never pretends
otherwise (``agent/offline_model.py``). What is proved is that the *architecture* poses a
real search — the tools, the budgets, the refusal, the adaptation and the guarded
mutation are all the production ones.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.agent.coordinator import PoolCoordinator
from pool.agent.objective import build_declaration_objective
from pool.agent.tools import STRATEGY_TOOL_SURFACE, TOOL_SURFACE, ToolContext, build_tools
from pool.config import get_settings
from pool.data.roast_coffee_fixture import (
    A_MEDIUM,
    ANCHOR_HOUSEHOLD,
    ANCHOR_NEED,
    B_DARK,
    install_roast_coffee,
)
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import (
    CoordinationEventStatus,
    ParticipationState,
    RunOutcome,
    iso,
    utcnow,
)
from pool.services import events as events_service
from pool.services import strategy as strategy_svc
from pool.services.context import PoolContext

from .conftest import WS
from .test_public_demo import FakeDynamoTable

KESTREL = A_MEDIUM
HARBOURSTONE = B_DARK


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def coffee_ctx() -> PoolContext:
    repo = InMemoryRepository()
    seed(repo, WS)
    install_roast_coffee(repo, WS)
    return PoolContext(
        repo=repo, ws=WS, routing=CachingRouting(DeterministicRouting(max_cells=400))
    )


def anchor_need(ctx: PoolContext):
    return ctx.repo.get_need(WS, ANCHOR_NEED)


def record(ctx: PoolContext, need=None):
    return events_service.record_declaration_event(ctx, need or anchor_need(ctx), COMMUNITY_ID)


def coordinator(ctx: PoolContext) -> PoolCoordinator:
    return PoolCoordinator(ctx.repo, settings=get_settings(), routing=ctx.routing)


def dispatch(ctx: PoolContext, event):
    agent = coordinator(ctx)
    return events_service.dispatch(
        ctx,
        event,
        run=lambda e: agent.run(
            WS, trigger="need_declared", community_id=COMMUNITY_ID, event_id=e.id
        ),
    )


def tool_names(run) -> list[str]:
    return [t.name for t in run.tool_calls]


def call(tool, *args, **kwargs):
    """Invoke a Strands-decorated tool directly, as ``test_agent_effects`` does.

    ``@tool`` keeps the undecorated function on ``__wrapped__``, which is what makes a
    tool callable here without a model, a session, or a token spend.
    """
    return tool.__wrapped__(*args, **kwargs)


# ----------------------------------------------------------------- event semantics


def test_one_declaration_owes_one_piece_of_coordination(coffee_ctx):
    event = record(coffee_ctx)
    assert event is not None
    assert event.status == CoordinationEventStatus.PENDING.value
    assert event.need_id == ANCHOR_NEED
    assert event.household_id == ANCHOR_HOUSEHOLD
    assert len(coffee_ctx.repo.list_coordination_events(WS)) == 1


def test_asking_twice_is_the_same_request(coffee_ctx):
    """A duplicate submission, a reload, a double-tap. All the same event."""
    first = record(coffee_ctx)
    second = record(coffee_ctx)
    assert second.id == first.id
    assert len(coffee_ctx.repo.list_coordination_events(WS)) == 1


def test_an_edit_that_changed_nothing_owes_nothing_new(coffee_ctx):
    first = record(coffee_ctx)
    need = anchor_need(coffee_ctx)
    coffee_ctx.repo.put_need(WS, need)  # saved again, identical
    assert record(coffee_ctx).id == first.id
    assert len(coffee_ctx.repo.list_coordination_events(WS)) == 1


def test_an_edit_that_changed_something_owes_a_fresh_look(coffee_ctx):
    first = record(coffee_ctx)
    need = anchor_need(coffee_ctx)
    need.quantity += 1
    coffee_ctx.repo.put_need(WS, need)
    second = record(coffee_ctx)
    assert second.id != first.id
    assert len(coffee_ctx.repo.list_coordination_events(WS)) == 2


def test_a_retired_declaration_owes_no_coordination(coffee_ctx):
    """Retiring is a real edit and a real content change. It is not work."""
    need = anchor_need(coffee_ctx)
    need.active = False
    coffee_ctx.repo.put_need(WS, need)
    assert record(coffee_ctx, need) is None
    assert coffee_ctx.repo.list_coordination_events(WS) == []


def test_one_event_produces_one_run(coffee_ctx):
    event = record(coffee_ctx)
    first = dispatch(coffee_ctx, event)
    assert first.ran is True
    assert first.event.status == CoordinationEventStatus.COMPLETED.value
    assert first.event.run_id

    again = dispatch(coffee_ctx, first.event)
    assert again.ran is False
    assert again.reason == events_service.CLAIM_ALREADY_TERMINAL
    assert len(coffee_ctx.repo.list_runs(WS)) == 1


def test_a_second_dispatcher_finds_the_work_already_taken(coffee_ctx):
    event = record(coffee_ctx)
    assert events_service.claim(coffee_ctx, event) == ""
    assert events_service.claim(coffee_ctx, event) == events_service.CLAIM_ALREADY_RUNNING


def test_a_failing_run_leaves_an_auditable_failure(coffee_ctx):
    """Failed is not "considered and declined". Collapsing them would let a bug read as
    a verdict."""
    event = record(coffee_ctx)

    def explode(_event):
        raise RuntimeError("model unavailable")

    with pytest.raises(RuntimeError):
        events_service.dispatch(coffee_ctx, event, run=explode)

    stored = coffee_ctx.repo.get_coordination_event(WS, event.id)
    assert stored.status == CoordinationEventStatus.FAILED.value
    assert stored.terminal_reason == "RuntimeError"
    assert stored.attempts == 1


def test_a_dispatcher_cannot_keep_retrying_a_broken_event(coffee_ctx):
    event = record(coffee_ctx)
    for _ in range(events_service.MAX_EVENT_ATTEMPTS):
        events_service.claim(coffee_ctx, event)
        event.status = CoordinationEventStatus.PENDING.value
    assert events_service.claim(coffee_ctx, event) == events_service.CLAIM_ATTEMPTS_EXHAUSTED


def test_event_run_and_pool_form_one_readable_chain(coffee_ctx):
    event = record(coffee_ctx)
    result = dispatch(coffee_ctx, event)
    run = coffee_ctx.repo.get_run(WS, result.event.run_id)
    pool = coffee_ctx.repo.get_pool(WS, result.event.pool_id)

    assert run.event_id == event.id
    assert run.objective_kind == "member"
    assert run.objective_need_ids == [ANCHOR_NEED]
    assert pool.created_by_run == run.id
    assert result.event.outcome == RunOutcome.POOL_CREATED.value


def test_an_event_survives_dynamodb_shaped_storage(coffee_ctx):
    event = dispatch(coffee_ctx, record(coffee_ctx)).event
    dynamo = DynamoDBRepository("pool-demo-state", table=FakeDynamoTable())
    dynamo.put_coordination_event(WS, event)
    restored = dynamo.get_coordination_event(WS, event.id)
    assert restored.to_dict() == event.to_dict()
    assert [e.id for e in dynamo.list_coordination_events(WS)] == [
        e.id for e in coffee_ctx.repo.list_coordination_events(WS)
    ]


def test_the_member_facing_view_distinguishes_every_real_situation(coffee_ctx):
    pending = events_service.view(record(coffee_ctx))
    assert pending["status"] == "pending"
    assert pending["reached_a_verdict"] is False
    assert pending["formed_order"] is False

    done = events_service.view(dispatch(coffee_ctx, record(coffee_ctx)).event)
    assert done["status"] == "completed"
    assert done["reached_a_verdict"] is True
    assert done["formed_order"] is True
    assert done["pool_id"]
    # Stored facts only: no prose written for a human, and no progress stage.
    assert set(done) == {
        "event_id", "kind", "need_id", "status", "run_id", "outcome", "terminal_reason",
        "pool_id", "attempts", "created_at", "ended_at", "formed_order",
        "reached_a_verdict",
    }


# --------------------------------------------------------------- the canonical run


@pytest.fixture
def canonical(coffee_ctx):
    """The run this phase exists to produce, executed once and inspected by several tests."""
    event = record(coffee_ctx)
    result = dispatch(coffee_ctx, event)
    run = coffee_ctx.repo.get_run(WS, result.event.run_id)
    return coffee_ctx, event, result, run


def test_the_run_lists_options_costs_one_adapts_and_forms_the_other(canonical):
    """The whole sequence, in the order it actually happened.

    List once. Cost the option with the most demand and the most room over its supplier
    minimum. Be refused on economics that were not in the listing. Cost the other one.
    Form that.
    """
    _ctx, _event, result, run = canonical
    assert tool_names(run) == [
        "list_cohort_strategies",
        "evaluate_cohort_strategy",
        "evaluate_cohort_strategy",
        "create_candidate_pool_from_strategy",
    ]
    assert run.outcome == RunOutcome.POOL_CREATED
    assert run.termination_reason == "completed"
    assert result.event.pool_id


def test_the_first_option_costed_is_refused_on_economics(canonical):
    """Kestrel, exactly as Phase 2 established, reached through the agent this time."""
    ctx, _event, _result, _run = canonical
    kestrel = next(
        e
        for e in ctx.repo.list_strategy_evaluations(WS)
        if e.target_product_id == KESTREL
    )
    assert kestrel.viable is False
    assert kestrel.blocker_code == "not_cheaper"
    assert kestrel.matched_units == 20 >= kestrel.minimum_units == 15
    assert kestrel.cases == 4 and kestrel.case_units == 5 and kestrel.surplus_units == 0
    assert kestrel.all_in_cents == 36_719
    assert kestrel.retail_baseline_cents == 36_000
    assert kestrel.net_savings_cents == -719


def test_the_option_it_adapts_to_is_viable_and_complete_cased(canonical):
    ctx, _event, _result, _run = canonical
    dark = next(
        e for e in ctx.repo.list_strategy_evaluations(WS) if e.target_product_id == HARBOURSTONE
    )
    assert dark.viable is True
    assert dark.selected_units == 12 == dark.cases * dark.case_units
    assert dark.surplus_units == 0
    assert dark.all_in_cents == 18_558
    assert dark.retail_baseline_cents == 22_200
    assert dark.net_savings_cents == 3_642
    assert dark.net_savings_bps == 1_641


def test_the_order_that_formed_is_the_one_that_was_verified(canonical):
    ctx, _event, result, run = canonical
    pool = ctx.repo.get_pool(WS, result.event.pool_id)
    assert pool.product_id == HARBOURSTONE
    assert pool.created_by_run == run.id

    memberships = ctx.repo.list_memberships(WS, pool.id)
    assert sum(m.requested_units for m in memberships) == 12
    assert pool.threshold_units == 12
    # Provisional, and nothing else. Declaring and being discovered never touch a card.
    assert {m.state for m in memberships} == {ParticipationState.PROVISIONAL}
    assert ctx.repo.list_payments(WS, pool.id) == []


def test_the_member_who_asked_is_in_the_order(canonical):
    """A member-anchored question may only be answered by an order they are in (§8)."""
    ctx, _event, result, _run = canonical
    memberships = ctx.repo.list_memberships(WS, result.event.pool_id)
    assert ANCHOR_NEED in {m.need_id for m in memberships}
    assert ANCHOR_HOUSEHOLD in {m.household_id for m in memberships}


def test_the_listing_did_not_say_which_one_would_work(canonical):
    """The property that makes the choice real, checked on the bytes the model received.

    Both options appear with more compatible demand than their supplier will sell below.
    Neither carries a verdict, a price, a case structure or a rank — and the one that
    looks stronger on every fact present is the one that was refused.
    """
    ctx, _event, _result, run = canonical

    # The bytes the model actually received, as recorded by the bound hook.
    transmitted = next(t for t in run.tool_calls if t.name == "list_cohort_strategies").summary
    assert '"viable"' not in transmitted
    assert "net_savings" not in transmitted and "all_in" not in transmitted

    # And the same projection, in full, from the rows the tool projected.
    summaries = [
        strategy_svc.strategy_summary(s) for s in ctx.repo.list_cohort_strategies(WS)
    ]
    by_product = {s["product_id"]: s for s in summaries}
    assert set(by_product) == {KESTREL, HARBOURSTONE}

    for summary in summaries:
        assert summary["compatible_units"] >= summary["lowest_supplier_minimum_units"]
        blob = json.dumps(summary)
        assert "viable" not in blob and "cents" not in blob and "$" not in blob
        assert not {"rank", "score", "winner", "recommended"} & set(summary)

    assert by_product[KESTREL]["compatible_units"] > by_product[HARBOURSTONE]["compatible_units"]
    assert (
        by_product[KESTREL]["compatible_declarations"]
        > by_product[HARBOURSTONE]["compatible_declarations"]
    )


def test_no_trivial_rule_over_the_listing_reaches_the_right_answer(canonical):
    """The check the phase brief asks for, made executable.

    A search is only a search if the answer is not already implied by the shape of the
    options. So: take the obvious single-step heuristics a rule engine would use over the
    listing — first in the list, most compatible demand, most declarations, fewest
    refusals, most headroom over the supplier minimum — and confirm every one of them
    picks the option the evaluator went on to refuse.

    This is not a claim that the problem is hard. It is the narrower and checkable claim
    that reaching the right answer requires *costing* something and reacting to what came
    back, which is what the tools, the budget and the refusal are for.
    """
    ctx, _event, _result, _run = canonical
    summaries = [
        strategy_svc.strategy_summary(s) for s in ctx.repo.list_cohort_strategies(WS)
    ]
    listed_order = [
        strategy_svc.strategy_summary(s)
        for s in strategy_svc.generate_strategies(
            ctx=ctx,
            objective=strategy_svc.StrategyObjective(
                kind=strategy_svc.OBJECTIVE_MEMBER,
                community_id=COMMUNITY_ID,
                household_id=ANCHOR_HOUSEHOLD,
                need_id=ANCHOR_NEED,
            ),
            persist=False,
        )
    ]
    refused = {
        e.target_product_id
        for e in ctx.repo.list_strategy_evaluations(WS)
        if not e.viable
    }
    assert refused == {KESTREL}

    heuristics = {
        "first_listed": listed_order[0],
        "most_units": max(summaries, key=lambda s: s["compatible_units"]),
        "most_declarations": max(summaries, key=lambda s: s["compatible_declarations"]),
        "fewest_exclusions": min(summaries, key=lambda s: s["excluded_declarations"]),
        "most_headroom": max(
            summaries,
            key=lambda s: s["compatible_units"] - s["lowest_supplier_minimum_units"],
        ),
    }
    for name, picked in heuristics.items():
        assert picked["product_id"] in refused, f"{name} would have got it right by luck"


# ------------------------------------------------------------- the tool contract


@pytest.fixture
def strategy_tools(coffee_ctx):
    objective = build_declaration_objective(
        coffee_ctx, COMMUNITY_ID, event_id="cev_test", need_id=ANCHOR_NEED
    )
    ctx = ToolContext(pool=coffee_ctx, community_id=COMMUNITY_ID, objective=objective)
    return ctx, {t.tool_name: t for t in build_tools(ctx)}


def test_a_declaration_run_gets_the_search_surface_and_not_the_sweep(strategy_tools):
    """Two doors to one mutation is one door too many.

    ``create_candidate_pool`` is not guarded by ``ensure_actionable``; the strategy
    creator is. A run holding both would have an unguarded way past the guard.
    """
    _ctx, tools = strategy_tools
    assert {name for name, _ in STRATEGY_TOOL_SURFACE} <= set(tools)
    assert "create_candidate_pool" not in tools
    assert "evaluate_pool_economics" not in tools
    assert "list_latent_demand" not in tools


def test_every_other_run_keeps_exactly_the_surface_it_had(coffee_ctx):
    ctx = ToolContext(pool=coffee_ctx, community_id=COMMUNITY_ID, objective=None)
    assert {t.tool_name for t in build_tools(ctx)} == {name for name, _ in TOOL_SURFACE}


def test_the_published_tool_list_reports_both_surfaces(client):
    """``/api/health`` is where a judge reads what the agent may do. It has to be complete."""
    health = client.get("/api/health").json()
    assert [(t["name"], t["kind"]) for t in health["agent_strategy_tools"]] == list(
        STRATEGY_TOOL_SURFACE
    )
    # Two lists, because no run ever holds both.
    published = {t["name"] for t in health["agent_tools"]}
    assert published.isdisjoint({name for name, _ in STRATEGY_TOOL_SURFACE})


def test_costing_an_option_commits_nothing(strategy_tools):
    """``evaluate_cohort_strategy`` is labelled ``record``, and the label is checked.

    It writes Pool's own evidence and nothing a member or supplier could observe: no
    pool, no membership, no decision, no payment. Asserted rather than trusted, in the
    spirit of ``test_agent_effects``.
    """
    ctx, tools = strategy_tools
    tools_repo = ctx.pool.repo
    call(tools["list_cohort_strategies"])
    for sid in list(ctx.listed_strategy_ids):
        call(tools["evaluate_cohort_strategy"], sid)

    assert tools_repo.list_pools(WS) == []
    assert tools_repo.list_decisions(WS) == []
    assert tools_repo.list_payments(WS, "") == []
    # What it does write is exactly the evidence it exists to leave behind.
    assert len(tools_repo.list_strategy_evaluations(WS)) == len(ctx.evaluated_strategy_ids)


def test_the_listing_tool_takes_no_arguments(strategy_tools):
    """There is no field in which to ask about another member or another Community."""
    _ctx, tools = strategy_tools
    spec = tools["list_cohort_strategies"].tool_spec
    assert spec["inputSchema"]["json"].get("properties", {}) == {}


def test_listing_happens_once_per_declaration(strategy_tools):
    ctx, tools = strategy_tools
    first = json.loads(call(tools["list_cohort_strategies"], ))
    assert first["count"] == 2
    second = json.loads(call(tools["list_cohort_strategies"], ))
    assert second["strategies"] == []
    assert "already listed" in second["reason"]
    assert ctx.strategy_listings == 1


def test_an_option_this_run_never_listed_cannot_be_costed(strategy_tools):
    """An id is evidence about one objective. Accepting one from anywhere else would let
    a run act on a question it was not asked."""
    ctx, tools = strategy_tools
    # A real, current strategy — generated for a *different* member's objective.
    other = strategy_svc.generate_strategies(
        ctx=ctx.pool,
        objective=strategy_svc.StrategyObjective(
            kind=strategy_svc.OBJECTIVE_MEMBER,
            community_id=COMMUNITY_ID,
            household_id="hh_rc_varga",
            need_id="need_rc_varga",
        ),
    )[0]
    result = json.loads(call(tools["evaluate_cohort_strategy"], other.id))
    assert result["evaluated"] is False
    assert "not offered by this run" in result["reason"]

    created = json.loads(
        call(tools["create_candidate_pool_from_strategy"], other.id, "seval_x")
    )
    assert created["created"] is False
    assert created["refusal_code"] == "strategy_not_in_this_run"


def test_the_evaluation_budget_is_smaller_than_the_search_space(strategy_tools):
    """Three of six, so "cost everything and pick the winner" is not available.

    That is the difference between a search and a sweep, and it is a cost decision as
    much as a design one (AGENTS.md §3.3).
    """
    ctx, tools = strategy_tools
    assert ctx.bounds.max_strategy_evaluations < strategy_svc.MAX_COHORT_STRATEGIES

    call(tools["list_cohort_strategies"], )
    listed = list(ctx.listed_strategy_ids)
    for sid in listed:
        json.loads(call(tools["evaluate_cohort_strategy"], sid))
    assert len(ctx.evaluated_strategy_ids) == len(listed)

    # Re-costing an option already costed is refused rather than silently repeated.
    repeat = json.loads(call(tools["evaluate_cohort_strategy"], listed[0]))
    assert repeat["evaluated"] is False
    assert "already evaluated" in repeat["reason"]


def test_the_budget_is_enforced_and_not_merely_advertised(strategy_tools):
    import dataclasses

    ctx, tools = strategy_tools
    ctx.bounds = dataclasses.replace(ctx.bounds, max_strategy_evaluations=1)
    call(tools["list_cohort_strategies"], )
    listed = list(ctx.listed_strategy_ids)
    assert len(listed) == 2

    json.loads(call(tools["evaluate_cohort_strategy"], listed[0]))
    blocked = json.loads(call(tools["evaluate_cohort_strategy"], listed[1]))
    assert blocked["evaluated"] is False
    assert blocked["reason"] == "evaluation budget exhausted for this declaration"


def test_only_one_order_forms_per_declaration(strategy_tools):
    ctx, tools = strategy_tools
    call(tools["list_cohort_strategies"], )
    viable = None
    for sid in list(ctx.listed_strategy_ids):
        result = json.loads(call(tools["evaluate_cohort_strategy"], sid))
        if result.get("viable"):
            viable = result
            break
    assert viable is not None

    first = json.loads(
        call(tools["create_candidate_pool_from_strategy"],
            viable["strategy_id"], viable["evaluation_id"]
        )
    )
    assert first["created"] is True
    second = json.loads(
        call(tools["create_candidate_pool_from_strategy"],
            viable["strategy_id"], viable["evaluation_id"]
        )
    )
    assert second["created"] is False
    assert second["refusal_code"] == "creation_budget_exhausted"
    assert len(ctx.pool.repo.list_pools(WS)) == 1


def test_the_creation_tool_accepts_identifiers_and_nothing_else(strategy_tools):
    """The whole safety of the mutation: there is no parameter for a member, a quantity,
    a price, a supplier term or a product fact."""
    _ctx, tools = strategy_tools
    schema = tools["create_candidate_pool_from_strategy"].tool_spec["inputSchema"]["json"]
    assert set(schema.get("properties", {})) == {"strategy_id", "evaluation_id"}
    for name, spec in schema["properties"].items():
        assert spec.get("type") == "string", name


def test_no_strategy_tool_leaks_personal_data(strategy_tools):
    ctx, tools = strategy_tools
    payloads = [call(tools["list_cohort_strategies"], )]
    for sid in list(ctx.listed_strategy_ids):
        payloads.append(call(tools["evaluate_cohort_strategy"], sid))
    blob = "".join(payloads)

    households = ctx.pool.repo.list_households(WS)
    for secret in (
        {h.display_name for h in households}
        | {h.contact_email for h in households if h.contact_email}
        | {h.id for h in households}
    ):
        assert secret not in blob, secret
    assert "lat" not in blob and "contact" not in blob


# ------------------------------------------------ the model cannot get round the truth


def test_a_refused_option_cannot_be_formed_anyway(strategy_tools):
    """The refusal stands. There is no argument the model can make against it."""
    ctx, tools = strategy_tools
    call(tools["list_cohort_strategies"], )
    kestrel = next(
        s
        for s in ctx.pool.repo.list_cohort_strategies(WS)
        if s.target_product_id == KESTREL and s.id in ctx.listed_strategy_ids
    )
    refused = json.loads(call(tools["evaluate_cohort_strategy"], kestrel.id))
    assert refused["viable"] is False

    result = json.loads(
        call(tools["create_candidate_pool_from_strategy"],
            kestrel.id, refused["evaluation_id"]
        )
    )
    assert result["created"] is False
    assert result["refusal_code"] == strategy_svc.CREATE_REFUSED_NOT_VIABLE
    assert ctx.pool.repo.list_pools(WS) == []


def test_evidence_that_expired_between_reading_and_acting_cannot_form_a_pool(strategy_tools):
    ctx, tools = strategy_tools
    call(tools["list_cohort_strategies"], )
    viable = next(
        r
        for r in (
            json.loads(call(tools["evaluate_cohort_strategy"], sid))
            for sid in list(ctx.listed_strategy_ids)
        )
        if r.get("viable")
    )

    # The supplier requotes between the model reading the answer and acting on it.
    offer = ctx.pool.repo.get_offer(WS, "off_rc_harbourstone_dark_bulk")
    offer.unit_price_cents = 1_090
    offer.verified_at = iso(utcnow())
    ctx.pool.repo.put_offer(WS, offer)

    result = json.loads(
        call(tools["create_candidate_pool_from_strategy"],
            viable["strategy_id"], viable["evaluation_id"]
        )
    )
    assert result["created"] is False
    assert result["refusal_code"] == strategy_svc.CREATE_REFUSED_STALE
    assert ctx.pool.repo.list_pools(WS) == []


def test_an_order_that_would_exclude_the_member_who_asked_is_not_their_answer(coffee_ctx):
    """Viable for the neighbours, and not an answer to this member's question (§8).

    The anchor's declaration is amended so case fitting cannot include it — five units
    against six-unit cases — and the order remains perfectly viable for everybody else.
    The member-scoped mutation refuses it rather than forming it as though it were theirs.
    """
    need = anchor_need(coffee_ctx)
    need.quantity = 5
    coffee_ctx.repo.put_need(WS, need)

    objective = build_declaration_objective(
        coffee_ctx, COMMUNITY_ID, event_id="cev_test", need_id=ANCHOR_NEED
    )
    ctx = ToolContext(pool=coffee_ctx, community_id=COMMUNITY_ID, objective=objective)
    tools = {t.tool_name: t for t in build_tools(ctx)}
    call(tools["list_cohort_strategies"], )

    outcomes = [
        json.loads(call(tools["evaluate_cohort_strategy"], sid))
        for sid in list(ctx.listed_strategy_ids)
    ]
    viable = [o for o in outcomes if o.get("viable")]
    excluded = [o for o in viable if o["includes_objective_declaration"] is False]
    assert excluded, "the fixture should produce a viable order this member is not in"

    result = json.loads(
        call(tools["create_candidate_pool_from_strategy"],
            excluded[0]["strategy_id"], excluded[0]["evaluation_id"]
        )
    )
    assert result["created"] is False
    assert result["refusal_code"] == strategy_svc.CREATE_REFUSED_OBJECTIVE_EXCLUDED
    assert coffee_ctx.repo.list_pools(WS) == []


def test_a_run_that_finds_nothing_worth_forming_says_so(coffee_ctx):
    """Honest no-action, reached through the same tools rather than a special case.

    Every supplier withdraws. There is nothing to source, so there is no option to list,
    and the run records why instead of ending silently.
    """
    for offer in coffee_ctx.repo.list_offers(WS):
        if offer.product_id.startswith("prod_rc_"):
            offer.active = False
            coffee_ctx.repo.put_offer(WS, offer)

    result = dispatch(coffee_ctx, record(coffee_ctx))
    run = coffee_ctx.repo.get_run(WS, result.event.run_id)
    assert run.outcome == RunOutcome.NO_ACTION
    assert tool_names(run) == ["list_cohort_strategies", "record_no_action"]
    assert run.notes and "no supplier" in run.notes[0]
    assert coffee_ctx.repo.list_pools(WS) == []
    # Completed, not failed: Pool looked and there was nothing to do.
    assert result.event.status == CoordinationEventStatus.COMPLETED.value
    assert result.event.pool_id == ""


def test_a_declaration_retired_before_dispatch_reaches_no_action(coffee_ctx):
    event = record(coffee_ctx)
    need = anchor_need(coffee_ctx)
    need.active = False
    coffee_ctx.repo.put_need(WS, need)

    result = dispatch(coffee_ctx, event)
    run = coffee_ctx.repo.get_run(WS, result.event.run_id)
    assert run.outcome == RunOutcome.NO_ACTION
    assert coffee_ctx.repo.list_pools(WS) == []


def test_the_full_authoritative_results_are_kept_and_the_model_sees_less(canonical):
    """Cost boundary, not a truth boundary (AGENTS.md §3.3)."""
    ctx, _event, result, _run = canonical
    evaluations = ctx.repo.list_strategy_evaluations(WS)
    assert len(evaluations) >= 2
    stored = evaluations[0].to_dict()
    projected = strategy_svc.evaluation_summary(evaluations[0])
    assert set(projected) < set(stored) | set(projected)
    # The roster of who was excluded is stored and is not projected.
    assert "excluded" in stored and "excluded" not in projected
    assert stored["excluded_count"] == projected["excluded_declarations"]
    del result


# ---------------------------------------------------------------- the HTTP boundary


@pytest.fixture
def client(monkeypatch) -> TestClient:
    from pool.api import app as api

    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    install_roast_coffee(api._repo, "demo")
    return c


def _declare(client: TestClient, household_id: str) -> dict:
    return client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": KESTREL,
            "quantity": 3,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "flexibility_days": 11,
            "max_spend_cents": 20_000,
        },
    ).json()


def _onboard(client: TestClient) -> str:
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    return client.get("/api/state").json()["consumer"]["household_id"]


def test_declaring_over_http_records_coordination_and_starts_nothing(client):
    """The default. Work is owed and durably recorded; no model call happens."""
    household_id = _onboard(client)
    body = _declare(client, household_id)
    assert body["coordination"]["status"] == "pending"

    listing = client.get("/api/events").json()
    assert listing["count"] == 1
    assert listing["pending"] == 1
    assert listing["auto_dispatch"] is False
    from pool.api import app as api

    assert api._repo.list_runs("demo") == []


def test_reading_state_never_starts_a_run(client):
    _onboard(client)
    _declare(client, client.get("/api/state").json()["consumer"]["household_id"])
    from pool.api import app as api

    for _ in range(3):
        client.get("/api/state")
        client.get("/api/events")
        client.get("/api/needs")
    assert api._repo.list_runs("demo") == []
    assert len(api._repo.list_coordination_events("demo")) == 1


def test_dispatching_over_http_runs_it_once(client):
    household_id = _onboard(client)
    event_id = _declare(client, household_id)["coordination"]["event_id"]

    first = client.post(f"/api/events/{event_id}/dispatch").json()
    assert first["ran"] is True
    assert first["status"] == "completed"

    second = client.post(f"/api/events/{event_id}/dispatch").json()
    assert second["ran"] is False
    assert second["skipped_reason"] == events_service.CLAIM_ALREADY_TERMINAL

    from pool.api import app as api

    assert len(api._repo.list_runs("demo")) == 1


def test_dispatching_an_event_nobody_issued_is_a_404(client):
    assert client.post("/api/events/cev_nope/dispatch").status_code == 404


def _auto_dispatch(monkeypatch) -> None:
    """Turn on synchronous dispatch for one test.

    ``Settings`` is frozen on purpose — configuration a running process can rewrite is
    configuration nothing can be reasoned about — so the whole object is replaced rather
    than a field mutated.
    """
    import dataclasses

    from pool.api import app as api

    monkeypatch.setattr(
        api, "_settings", dataclasses.replace(api._settings, auto_dispatch_declaration_events=True)
    )


def test_a_duplicate_declaration_cannot_buy_a_second_run(client, monkeypatch):
    """With dispatch on, the second submission is refused by the declaration service and
    never reaches coordination at all."""
    from pool.api import app as api

    _auto_dispatch(monkeypatch)
    household_id = _onboard(client)

    first = _declare(client, household_id)
    assert first["coordination"]["status"] == "completed"
    assert len(api._repo.list_runs("demo")) == 1

    duplicate = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": KESTREL,
            "quantity": 3,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "max_spend_cents": 20_000,
        },
    )
    assert duplicate.status_code == 400
    assert len(api._repo.list_runs("demo")) == 1
    assert len(api._repo.list_coordination_events("demo")) == 1


def test_saving_an_unchanged_edit_cannot_buy_a_second_run(client, monkeypatch):
    from pool.api import app as api

    _auto_dispatch(monkeypatch)
    household_id = _onboard(client)
    created = _declare(client, household_id)
    need_id = created["need_id"]

    body = {
        "household_id": household_id,
        "product_id": KESTREL,
        "quantity": 3,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "flexibility_days": 11,
        "max_spend_cents": 20_000,
    }
    again = client.post(f"/api/needs/{need_id}", json=body).json()
    assert again["coordination"]["event_id"] == created["coordination"]["event_id"]
    assert len(api._repo.list_runs("demo")) == 1

    # A change that alters what Pool would coordinate does owe a fresh look.
    changed = client.post(f"/api/needs/{need_id}", json={**body, "quantity": 4}).json()
    assert changed["coordination"]["event_id"] != created["coordination"]["event_id"]
    assert len(api._repo.list_coordination_events("demo")) == 2


# ------------------------------------------------------------ nothing else moved


def test_the_ordinary_member_run_is_untouched(coffee_ctx):
    """The button still asks the question it always asked, on the surface it always had."""
    run = coordinator(coffee_ctx).run(WS, trigger="member_scan", community_id=COMMUNITY_ID)
    assert "list_cohort_strategies" not in tool_names(run)
    assert run.event_id == ""


def test_the_community_scan_is_untouched(coffee_ctx):
    run = coordinator(coffee_ctx).run(WS, trigger="pool_day", community_id=COMMUNITY_ID)
    assert "list_latent_demand" in tool_names(run)
    assert "list_cohort_strategies" not in tool_names(run)


def test_nothing_recurring_was_added():
    """No schedule, no poller, no timer. An event is dispatched because something asked."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(events_service.__file__).read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        for alias in getattr(node, "names", []) or []
    }
    assert not imported & {"time", "threading", "asyncio", "sched", "schedule"}
    assert not any(isinstance(node, (ast.While, ast.AsyncFor)) for node in ast.walk(tree))
    assert get_settings().schedules_enabled is False
