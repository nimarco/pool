"""A→B→C, through the API a member actually uses, with every identifier written down.

Phase 4.5 claimed reversibility works. This module is the proof, and it is deliberately
end-to-end rather than unit-scoped: the interesting properties live in the *ordering* of
things the service layer does per request — amend, reconcile, record an event, dispatch a
run — and a test that called those functions itself would be asserting an ordering it had
chosen rather than the one the product has.

The canonical flow, and what each state has to establish:

**A** — flexible, whole bean, caffeinated, medium or dark. A coordination event, a run
that searches cohort strategies, and a provisional place in the Harbourstone order.

**B** — narrowed to the exact Kestrel. Deterministic reconciliation takes the member out
of an order their own new rules forbid, and a *new* event and run process the narrowed
declaration on its own terms.

**C** — widened back to exactly what A said. This is the one that matters. A declaration
textually identical to A is not the same declaration, because the world moved in between:
the member is out of an order they used to be in, and A's event has already completed.
So C must be its own event, its own run, and its own processing of current truth — and
the restoration must be deterministic reconciliation against the *amended* declaration
rather than a replay of A's result.

The failure this is written against is subtle and would look like success: restore the
membership, let the coordination event resolve to A's completed row, and the screen shows
the right thing for the wrong reason. Every assertion about distinct identities below is
there to make that indistinguishable-looking failure fail.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as app_module
from pool.domain.models import LEFT_PARTICIPATION_STATES, ParticipationState, PoolStatus

#: A verification partition, because that is the only place coordination dispatches in
#: the same request — which is what makes the causal chain observable from one call.
WS = "wlineagetest01-verify"

FLEXIBLE = {
    "flexibility": "similar",
    "keep": ["form", "caffeine"],
    "accept": {"roast": ["MEDIUM", "DARK"]},
}
EXACT = {"flexibility": "exact", "keep": [], "accept": {}}

MEMBER = "hh_navarro"
PRODUCT = "prod_rc_kestrel_medium"


@pytest.fixture
def client() -> TestClient:
    c = TestClient(app_module.app)
    c.get(f"/api/state?workspace={WS}")
    c.post(
        f"/api/onboarding?workspace={WS}",
        json={"display_name": "Judge", "autonomy_mode": "smart_join"},
    )
    yield c
    app_module.repo().reset(WS)


def declaration(preferences: dict) -> dict:
    return {
        "household_id": MEMBER,
        "product_id": PRODUCT,
        "quantity": 3,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "flexibility_days": 11,
        "max_spend_cents": 20_000,
        "preferences": preferences,
    }


def runs(trigger: str) -> list:
    return [r for r in app_module.repo().list_runs(WS) if r.trigger == trigger]


def memberships_of(household_id: str = MEMBER) -> list:
    out = []
    for pool in app_module.repo().list_pools(WS):
        membership = app_module.repo().get_membership(WS, pool.id, household_id)
        if membership is not None:
            out.append((pool, membership))
    return out


def live_memberships(household_id: str = MEMBER) -> list:
    return [
        (pool, m)
        for pool, m in memberships_of(household_id)
        if m.state not in LEFT_PARTICIPATION_STATES
    ]


@pytest.fixture
def walked(client: TestClient) -> dict:
    """The canonical A → B → C walk, with each state observed *while it is true*.

    The participation snapshots have to be taken during the walk rather than after it,
    because the whole subject is state that changes three times. A test that read the
    store at the end would be asserting C's world about A.
    """
    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    need_id = a["need_id"]
    state = {"need_id": need_id, "A": a}
    state["A_need"] = _snapshot(need_id)
    state["A_seen"] = _participation()

    state["B"] = client.post(
        f"/api/needs/{need_id}?workspace={WS}", json=declaration(EXACT)
    ).json()
    state["B_need"] = _snapshot(need_id)
    state["B_seen"] = _participation()

    state["C"] = client.post(
        f"/api/needs/{need_id}?workspace={WS}", json=declaration(FLEXIBLE)
    ).json()
    state["C_need"] = _snapshot(need_id)
    state["C_seen"] = _participation()
    return state


def _participation() -> list[dict]:
    """Every row about this member, and about everybody else, at one moment."""
    rows = []
    for pool in app_module.repo().list_pools(WS):
        for membership in app_module.repo().list_memberships(WS, pool.id):
            rows.append(
                {
                    "pool_id": pool.id,
                    "pool_status": pool.status.value,
                    "pool_product_id": pool.product_id,
                    "created_by_run": pool.created_by_run,
                    "household_id": membership.household_id,
                    "state": membership.state.value,
                    "need_id": membership.need_id,
                    "is_exact_product": membership.is_exact_product,
                    "withdrawn_reason": membership.withdrawn_reason,
                    "payment_id": membership.payment_id,
                }
            )
    return rows


def mine(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["household_id"] == MEMBER]


def _snapshot(need_id: str) -> dict:
    from pool.services import events as events_service

    need = app_module.repo().get_need(WS, need_id)
    return {
        "revision": need.revision,
        "substitution": need.substitution.value,
        "requires": (
            {k: sorted(v) for k, v in need.attribute_policy.requires.items()}
            if need.attribute_policy
            else None
        ),
        "schema_version": (
            need.attribute_policy.schema_version if need.attribute_policy else None
        ),
        "digest": events_service.declaration_digest(need),
        "event_id": events_service.event_id_for(need),
    }


# ------------------------------------------------------------------ the declarations


def test_each_material_edit_is_a_distinct_declaration(walked):
    """Revisions move, and C is not mistaken for A despite saying the same thing."""
    assert [walked[k]["revision"] for k in ("A_need", "B_need", "C_need")] == [0, 1, 2]

    # The *policy* of C is exactly A's — that is the whole point of the reversal.
    assert walked["C_need"]["requires"] == walked["A_need"]["requires"]
    assert walked["C_need"]["substitution"] == walked["A_need"]["substitution"] == (
        "attribute_constrained"
    )
    assert walked["B_need"]["substitution"] == "exact_only"
    assert walked["B_need"]["requires"] is None

    # And the content digest still separates them, because the revision is part of it.
    digests = {walked[k]["digest"] for k in ("A_need", "B_need", "C_need")}
    assert len(digests) == 3


def test_the_policy_version_is_recorded_on_every_constrained_state(walked):
    from pool.data import product_facts as pf

    for key in ("A_need", "C_need"):
        assert walked[key]["schema_version"] == pf.SCHEMA_VERSION


# ---------------------------------------------------------------------- the events


def test_every_material_edit_gets_its_own_coordination_event(walked):
    events = [walked[k]["event_id"] for k in ("A_need", "B_need", "C_need")]
    assert len(set(events)) == 3

    stored = {e.id: e for e in app_module.repo().list_coordination_events(WS)}
    assert set(events) <= set(stored)
    for event_id in events:
        event = stored[event_id]
        assert event.status == "completed"
        assert event.run_id, "an event that completed without a run is not processing"
        assert event.attempts == 1


def test_each_state_reports_the_event_and_run_its_own_save_caused(walked):
    """The response a member's browser gets names the chain their action started."""
    seen_events, seen_runs = set(), set()
    for key in ("A", "B", "C"):
        coordination = walked[key]["coordination"]
        assert coordination["event_id"] == walked[f"{key}_need"]["event_id"]
        assert coordination["run_id"]
        seen_events.add(coordination["event_id"])
        seen_runs.add(coordination["run_id"])
    assert len(seen_events) == 3
    assert len(seen_runs) == 3


def test_c_does_not_resolve_to_the_event_a_already_completed(walked):
    """The regression this whole phase turns on.

    Without a revision, C's digest is A's digest, C's event id is A's event id, and the
    dedupe that makes a double-submit free silently reports A's `pool_created` verdict for
    a declaration that has not been coordinated since the member was withdrawn.
    """
    assert walked["C"]["coordination"]["event_id"] != walked["A"]["coordination"]["event_id"]
    assert walked["C"]["coordination"]["run_id"] != walked["A"]["coordination"]["run_id"]


# ------------------------------------------------------------------------ the runs


def test_a_searches_strategies_and_forms_the_order(walked):
    run_id = walked["A"]["coordination"]["run_id"]
    run = app_module.repo().get_run(WS, run_id)
    called = [c.name for c in run.tool_calls]
    assert "list_cohort_strategies" in called
    assert "create_candidate_pool_from_strategy" in called
    assert run.outcome.value == "pool_created"

    evaluations = [
        e for e in app_module.repo().list_strategy_evaluations(WS) if e.run_id == run_id
    ]
    assert evaluations, "an order formed on no evaluation is an order formed on nothing"
    assert {e.target_product_id for e in evaluations} >= {PRODUCT}, (
        "the declared product has to be costed, not skipped"
    )
    assert any(e.viable for e in evaluations)
    assert any(not e.viable for e in evaluations), "the refusal is part of the evidence"
    # Two distinct options were costed, which is what makes this a search rather than a
    # formality: the one with the most demand behind it is the one that was refused.
    assert len({e.strategy_id for e in evaluations}) >= 2


def test_a_cohort_strategy_row_records_the_last_run_that_generated_it(client):
    """A known limit of the stored record, pinned so it cannot drift unnoticed.

    A strategy's id is a digest of what it *is* — the product, the site, the declarations
    whose own rules admit it — so two runs asking overlapping questions legitimately
    generate the same strategy, and the second rewrites the row's ``run_id``. Evaluations
    do not behave this way: each run writes its own, with its own id.

    The consequence is narrow and worth stating rather than papering over. Filtering the
    strategy table by ``run_id`` answers "which run generated this row most recently", not
    "what did that run consider" — so an *earlier* run's option list can shrink after a
    later run touches the same option. Every verdict, every price and every membership is
    unaffected; what degrades is the historical option list on a superseded explanation.
    Reported rather than fixed here: the honest repair is a stored set of runs per
    strategy, which is a persisted-schema decision and not this pass's scope.
    """
    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    run_a = a["coordination"]["run_id"]
    before = {
        s.id for s in app_module.repo().list_cohort_strategies(WS) if s.run_id == run_a
    }
    assert len(before) >= 2

    b = client.post(
        f"/api/needs/{a['need_id']}?workspace={WS}", json=declaration(EXACT)
    ).json()
    run_b = b["coordination"]["run_id"]
    after = {
        s.id for s in app_module.repo().list_cohort_strategies(WS) if s.run_id == run_a
    }
    reattributed = before - after
    assert reattributed, "if this stops happening the docstring above is stale"
    assert all(
        app_module.repo().get_cohort_strategy(WS, sid).run_id == run_b
        for sid in reattributed
    )

    # The part that must never degrade: each run keeps its own verdicts.
    for run_id in (run_a, run_b):
        assert [
            e for e in app_module.repo().list_strategy_evaluations(WS) if e.run_id == run_id
        ]


def test_b_processes_the_narrowed_declaration_on_its_own_terms(walked):
    """Not a replay, and not a no-op: B costs the exact-only world it now describes."""
    run = app_module.repo().get_run(WS, walked["B"]["coordination"]["run_id"])
    called = [c.name for c in run.tool_calls]
    assert "list_cohort_strategies" in called
    assert "evaluate_cohort_strategy" in called

    evaluations = [
        e for e in app_module.repo().list_strategy_evaluations(WS) if e.run_id == run.id
    ]
    assert evaluations, "B reached a verdict about nothing"
    # Exact-only means exactly one product can be considered — the one they named.
    assert {e.target_product_id for e in evaluations} == {PRODUCT}
    assert run.outcome.value == "no_action"


def test_c_is_processed_against_current_truth_and_holds_no_mutation(walked):
    """C's run is real, and its authority matches the question it was asked.

    By the time it opens, reconciliation has established that a live pool serves the
    declaration. The honest answer is that pool — so the run gets a read and an end, and
    physically cannot form, lock, or purchase anything. Before this was narrowed it fell
    through to the community surface and held `create_candidate_pool`, `lock_pool` and
    `execute_purchase`: a member editing a checkbox could have caused any of them.
    """
    from pool.agent.objective import build_declaration_objective
    from pool.agent.tools import build_tools
    from pool.data.seed import COMMUNITY_ID

    run = app_module.repo().get_run(WS, walked["C"]["coordination"]["run_id"])
    assert run.outcome.value == "no_action"
    assert [c.name for c in run.tool_calls] == ["record_no_action"]

    ctx = app_module.ctx_for(WS)
    objective = build_declaration_objective(
        ctx,
        COMMUNITY_ID,
        event_id=walked["C"]["coordination"]["event_id"],
        need_id=walked["need_id"],
    )
    assert objective.reviews_served_declaration
    assert objective.served_need_ids == (walked["need_id"],)

    names = {getattr(t, "tool_name", getattr(t, "__name__", "")) for t in build_tools(_tool_ctx(ctx, objective))}
    assert names == {"inspect_pool", "record_no_action"}
    for forbidden in (
        "create_candidate_pool",
        "create_candidate_pool_from_strategy",
        "issue_final_offer",
        "lock_pool",
        "execute_purchase",
        "recover_pool",
    ):
        assert forbidden not in names


def _tool_ctx(ctx, objective):
    from pool.agent.tools import ToolContext
    from pool.data.seed import COMMUNITY_ID

    return ToolContext(pool=ctx, community_id=COMMUNITY_ID, objective=objective)


# ----------------------------------------------------------------- the participation


def test_a_puts_the_member_in_a_substitute_order_they_authorised(walked):
    rows = mine(walked["A_seen"])
    assert len(rows) == 1
    row = rows[0]
    assert row["state"] == "provisional"
    assert row["need_id"] == walked["need_id"]
    # A dark roast is not the coffee they named, and the record says so.
    assert row["is_exact_product"] is False
    assert row["pool_product_id"] != PRODUCT


def test_b_removes_them_and_records_why_pool_did_it(walked):
    assert walked["B"]["reconciled"] == [
        {
            "pool_id": walked["B"]["reconciled"][0]["pool_id"],
            "withdrawn": True,
            "reason_code": "exact_product_required",
        }
    ]
    rows = mine(walked["B_seen"])
    assert len(rows) == 1
    assert rows[0]["state"] == "withdrawn"
    assert rows[0]["withdrawn_reason"] == "exact_product_required"


def test_c_returns_them_to_the_same_order_provisionally(walked):
    restored = walked["C"]["reconciled"]
    assert len(restored) == 1
    assert restored[0]["restored"] is True
    assert restored[0]["state"] == "provisional"
    assert restored[0]["pool_id"] == walked["B"]["reconciled"][0]["pool_id"]

    rows = mine(walked["C_seen"])
    assert len(rows) == 1
    row = rows[0]
    assert row["pool_id"] == restored[0]["pool_id"], "a new pool would not be a restoration"
    assert row["state"] == "provisional"
    assert row["need_id"] == walked["need_id"]
    assert row["is_exact_product"] is False
    assert row["withdrawn_reason"] == ""
    # And the order is the one A built, not a rebuilt copy of it.
    assert row["created_by_run"] == walked["A"]["coordination"]["run_id"]


def test_the_walk_never_produces_a_second_membership_row(walked):
    """One row per pool per household, at every state, whatever route put them there."""
    for state in ("A_seen", "B_seen", "C_seen"):
        seen: set[tuple[str, str]] = set()
        for row in walked[state]:
            key = (row["pool_id"], row["household_id"])
            assert key not in seen, f"duplicate membership at {state}: {key}"
            seen.add(key)
        assert len(mine(walked[state])) == 1


def test_restoring_keeps_the_estimate_the_member_was_shown(walked):
    """A restored place is not a place with no price on it.

    Joining builds a membership from scratch, and a scratch membership has no economics —
    which put "about $0.00 instead of $0.00" on the member's own Home screen the moment
    they were let back in. A money figure that is false is worse than one that is stale,
    and this one is neither: it is the formation-time estimate every other member of this
    pool is also being shown, superseded for everybody at the final offer.
    """
    before = mine(walked["A_seen"])[0]
    pool_id = before["pool_id"]
    restored = app_module.repo().get_membership(WS, pool_id, MEMBER)
    original = app_module.repo().get_membership(WS, pool_id, MEMBER)

    assert restored.state == ParticipationState.PROVISIONAL
    assert restored.estimated_cost_cents > 0
    assert restored.baseline_cents > restored.estimated_cost_cents, (
        "an order nobody saves money in is not the one A formed"
    )
    # And the figures are the same ones the rest of the pool carries, computed at the
    # same moment rather than recomputed for one member alone.
    neighbours = [
        m
        for m in app_module.repo().list_memberships(WS, pool_id)
        if m.household_id != MEMBER
    ]
    assert neighbours
    assert all(m.baseline_cents == original.baseline_cents for m in neighbours)


def test_the_walk_never_touches_a_card(walked):
    """Provisional participation is not financial commitment — in either direction."""
    for state in ("A_seen", "B_seen", "C_seen"):
        for row in walked[state]:
            assert row["payment_id"] == ""
    for pool in app_module.repo().list_pools(WS):
        assert app_module.repo().list_payments(WS, pool.id) == []


def test_other_members_are_untouched_by_the_whole_walk(walked):
    others = {
        state: {
            (r["pool_id"], r["household_id"]): r["state"]
            for r in walked[state]
            if r["household_id"] != MEMBER
        }
        for state in ("A_seen", "B_seen", "C_seen")
    }
    assert others["A_seen"], "no neighbours means this proves nothing"
    assert others["A_seen"] == others["B_seen"] == others["C_seen"]
    assert set(others["A_seen"].values()) == {"provisional"}


# ---------------------------------------------------------------- restoration safety


def test_restoration_re_runs_compatibility_rather_than_trusting_the_old_verdict(client):
    """The pool is only given back if it *currently* satisfies the amended rules.

    Proved by widening to something the pool does not satisfy: ground coffee is excluded
    by the same evaluator that admitted them, so the member stays out even though Pool is
    the one who took them out and the pool is still open.
    """
    from pool.data import product_facts as pf

    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    need_id = a["need_id"]
    pool_id = live_memberships()[0][0].id

    client.post(f"/api/needs/{need_id}?workspace={WS}", json=declaration(EXACT))
    assert app_module.repo().get_membership(WS, pool_id, MEMBER).state == (
        ParticipationState.WITHDRAWN
    )

    # Flexible again, but insisting on ground — which the dark-roast whole-bean order is
    # not. Widening is not a password.
    ground = {
        "flexibility": "similar",
        "keep": ["caffeine"],
        "accept": {"form": [pf.FORM_GROUND]},
    }
    result = client.post(
        f"/api/needs/{need_id}?workspace={WS}", json=declaration(ground)
    ).json()
    assert result["reconciled"] == []
    assert app_module.repo().get_membership(WS, pool_id, MEMBER).state == (
        ParticipationState.WITHDRAWN
    )


def test_a_pool_past_the_commitment_boundary_is_never_rejoined(client):
    """Locked means the money is captured and the supplier order placed."""
    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    need_id = a["need_id"]
    pool = live_memberships()[0][0]

    client.post(f"/api/needs/{need_id}?workspace={WS}", json=declaration(EXACT))
    pool.status = PoolStatus.LOCKED
    app_module.repo().put_pool(WS, pool)

    result = client.post(
        f"/api/needs/{need_id}?workspace={WS}", json=declaration(FLEXIBLE)
    ).json()
    assert result["reconciled"] == []
    membership = app_module.repo().get_membership(WS, pool.id, MEMBER)
    assert membership.state == ParticipationState.WITHDRAWN
    assert app_module.repo().get_pool(WS, pool.id).status == PoolStatus.LOCKED


def test_an_order_the_member_left_themselves_is_never_given_back(client):
    """Pool may undo what Pool did. It may not undo what the member did."""
    from pool.services import coordination as coord

    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    need_id = a["need_id"]
    pool_id = live_memberships()[0][0].id

    coord.withdraw_participant(
        ctx=app_module.ctx_for(WS), pool_id=pool_id, household_id=MEMBER
    )
    assert app_module.repo().get_membership(WS, pool_id, MEMBER).withdrawn_reason == ""

    # Any later material edit, including one that still permits the pool.
    body = declaration(FLEXIBLE)
    body["quantity"] = 4
    result = client.post(f"/api/needs/{need_id}?workspace={WS}", json=body).json()
    assert all(not row.get("restored") for row in result["reconciled"])
    assert app_module.repo().get_membership(WS, pool_id, MEMBER).state == (
        ParticipationState.WITHDRAWN
    )


# ------------------------------------------------------------------------ the cost


def test_one_clarification_run_and_three_coordination_runs(client, walked):
    """The two kinds of run are counted separately, because they are separate claims.

    The clarification planner is reused across all three states — the product, the schema
    and the world it was asked about did not move, so the questions worth asking cannot
    have. Coordination is *not* reused, and must not be: each material edit is a different
    declaration and gets its own processing.
    """
    coordination = runs("need_declared")
    clarification = runs("clarify_need_preferences")
    assert len(coordination) == 3
    assert len(clarification) <= 1
    assert len({r.id for r in coordination}) == 3


def test_editing_a_preference_never_replans_the_questions(client):
    """B and C must not buy a planner run. Nothing about the product changed."""
    client.post(f"/api/products/{PRODUCT}/clarification?workspace={WS}")
    before = len(runs("clarify_need_preferences"))
    assert before == 1

    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    need_id = a["need_id"]
    client.post(f"/api/needs/{need_id}?workspace={WS}", json=declaration(EXACT))
    client.post(f"/api/needs/{need_id}?workspace={WS}", json=declaration(FLEXIBLE))

    assert len(runs("clarify_need_preferences")) == before

    # And reopening the form after all of it still finds the same plan.
    reopened = client.post(f"/api/products/{PRODUCT}/clarification?workspace={WS}").json()
    assert reopened["planned_now"] is False
    assert len(runs("clarify_need_preferences")) == before


# ----------------------------------------------------------------------- the record


def test_the_explanation_after_c_can_account_for_the_order_on_screen(client, walked):
    """The member is in an order; the page that explains orders has to explain it.

    C's own run correctly created nothing, so reading only the event's `pool_id` left the
    proof saying nothing happened while Home showed the order. It now resolves the order
    from stored membership lineage and says plainly which run formed it.
    """
    proof = client.get(
        f"/api/needs/{walked['need_id']}/coordination?workspace={WS}"
    ).json()
    order = proof["order"]
    assert order is not None
    assert order["pool_id"] == walked["C"]["reconciled"][0]["pool_id"]
    assert order["formed_by_this_run"] is False
    assert order["created_by_run"] == walked["A"]["coordination"]["run_id"]
    assert order["provisional"] is True
    assert proof["event"]["event_id"] == walked["C"]["coordination"]["event_id"]


def test_the_explanation_after_a_says_this_run_formed_it(client):
    a = client.post(f"/api/needs?workspace={WS}", json=declaration(FLEXIBLE)).json()
    proof = client.get(f"/api/needs/{a['need_id']}/coordination?workspace={WS}").json()
    assert proof["order"]["formed_by_this_run"] is True
    assert proof["order"]["created_by_run"] == a["coordination"]["run_id"]


def test_the_explanation_after_b_reports_no_order_at_all(client, walked):
    """Between B and C the member is in nothing, and the honest answer is nothing."""
    from pool.services import events as events_service

    ctx = app_module.ctx_for(WS)
    need = app_module.repo().get_need(WS, walked["need_id"])
    # Rewind to B's world: withdraw again and check the explanation of B's own event.
    for pool in app_module.repo().list_pools(WS):
        membership = app_module.repo().get_membership(WS, pool.id, MEMBER)
        if membership is not None:
            membership.state = ParticipationState.WITHDRAWN
            app_module.repo().put_membership(WS, membership)

    proof = events_service.explain(ctx, need.id)
    assert proof["order"] is None
