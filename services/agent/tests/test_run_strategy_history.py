"""What a run considered, kept exactly, forever.

A cohort strategy's id is a digest of what the strategy *is* — the Community, the
objective, the SKU, the site — and that is deliberate: an evaluation stored against it
still resolves after the world moves, so a stale option can be *recognised* and reported
as stale rather than becoming an unknown id indistinguishable from an invented one.

The cost is that the row is current shared state. Two runs asking overlapping questions
generate the same id, and the later one rewrites it — its ``run_id`` and every count on
it. Deriving "what did that run consider?" from that table therefore answered a different
question than it appeared to, and the answer changed depending on what happened
afterwards. Historical proof that moves is not proof.

So a run's listing is its own append-only row, keyed by the pair, carrying the exact
projection the model was transmitted. This module is about the properties that makes
true, and the sharpest one is the snapshot: the numbers are stored rather than looked up
again, because they provably move under a stable id.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.data.roast_coffee_fixture import (
    A_MEDIUM,
    ANCHOR_HOUSEHOLD,
    ANCHOR_NEED,
    B_DARK,
    install_roast_coffee,
)
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import RunStrategyReference, SubstitutionPolicy
from pool.services import strategy as st
from pool.services.context import PoolContext

from .conftest import WS
from .test_public_demo import FakeDynamoTable


def fresh_repo(kind: str = "memory"):
    repo = (
        InMemoryRepository()
        if kind == "memory"
        else DynamoDBRepository("pool-demo-state", table=FakeDynamoTable())
    )
    seed(repo, WS)
    install_roast_coffee(repo, WS)
    return repo


def ctx_for(repo, run_id: str = "") -> PoolContext:
    return PoolContext(
        repo=repo,
        ws=WS,
        routing=CachingRouting(DeterministicRouting(max_cells=400)),
        run_id=run_id,
    )


def member_objective() -> st.StrategyObjective:
    return st.StrategyObjective(
        kind=st.OBJECTIVE_MEMBER,
        community_id=COMMUNITY_ID,
        household_id=ANCHOR_HOUSEHOLD,
        need_id=ANCHOR_NEED,
    )


# ------------------------------------------------------------------ the association


def test_listing_options_to_a_run_records_what_that_run_was_shown():
    repo = fresh_repo()
    ctx = ctx_for(repo, "run_first")
    strategies = st.generate_strategies(ctx=ctx, objective=member_objective())
    assert len(strategies) >= 2

    references = repo.list_run_strategy_references(WS, "run_first")
    assert [r.strategy_id for r in references] == [s.id for s in strategies]
    assert [r.ordinal for r in references] == list(range(len(strategies)))
    assert all(r.run_id == "run_first" for r in references)
    # The pair is the key, so a write addresses one run's view of one option.
    assert [r.id for r in references] == [f"run_first#{s.id}" for s in strategies]


def test_the_snapshot_is_the_projection_the_model_was_transmitted():
    """Not a re-derivation, and not a subset the record chose for itself."""
    repo = fresh_repo()
    ctx = ctx_for(repo, "run_first")
    strategies = st.generate_strategies(ctx=ctx, objective=member_objective())
    by_id = {s.id: s for s in strategies}

    for reference in repo.list_run_strategy_references(WS, "run_first"):
        assert reference.summary == st.strategy_summary(by_id[reference.strategy_id])
        # And it is the shape the tool sends: no verdict, no price.
        assert "viable" not in reference.summary
        assert not any("cent" in key for key in reference.summary)


def test_generation_outside_a_run_records_nothing():
    """An association with no run in it would be a row that means nothing."""
    repo = fresh_repo()
    st.generate_strategies(ctx=ctx_for(repo, ""), objective=member_objective())
    assert repo.list_run_strategy_references(WS) == []


# ------------------------------------------------------------------ the immutability


def test_a_later_run_regenerating_an_option_does_not_touch_the_earlier_listing():
    """The whole point. One repository, two runs, a shared option between them."""
    repo = fresh_repo()
    st.generate_strategies(ctx=ctx_for(repo, "run_first"), objective=member_objective())
    before = [
        (r.ordinal, r.strategy_id, dict(r.summary))
        for r in repo.list_run_strategy_references(WS, "run_first")
    ]
    assert len(before) >= 2

    st.generate_strategies(ctx=ctx_for(repo, "run_second"), objective=member_objective())

    after = [
        (r.ordinal, r.strategy_id, dict(r.summary))
        for r in repo.list_run_strategy_references(WS, "run_first")
    ]
    assert after == before

    second = repo.list_run_strategy_references(WS, "run_second")
    assert [r.strategy_id for r in second] == [sid for _, sid, _ in before]
    # And the shared strategy row now names the later run, which is all that field means.
    for _, strategy_id, _ in before:
        assert repo.get_cohort_strategy(WS, strategy_id).run_id == "run_second"


def test_the_snapshot_survives_the_world_moving_under_a_stable_id():
    """The reason ids and an ordinal would not have been enough.

    ``compatible_units``, ``excluded_declaration_count`` and the exclusion codes are
    computed from the current world and are *not* part of the identity digest, so the same
    option carries different numbers once a neighbour declares. A record that re-read them
    would be today's listing wearing an older date.
    """
    repo = fresh_repo()
    first = ctx_for(repo, "run_first")
    st.generate_strategies(ctx=first, objective=member_objective())
    snapshot = {
        r.strategy_id: dict(r.summary)
        for r in repo.list_run_strategy_references(WS, "run_first")
    }

    from pool.services import needs as needs_service

    needs_service.declare_need(
        ctx=first,
        community_id=COMMUNITY_ID,
        data=needs_service.NeedInput(
            household_id="hh_navarro",
            product_id=A_MEDIUM,
            quantity=4,
            cadence_days=30,
            expected_next_need_date=date.today() + timedelta(days=10),
            flexibility_days=5,
            max_spend_cents=20_000,
            substitution=SubstitutionPolicy.EXACT_ONLY,
        ),
    )

    regenerated = {
        s.id: st.strategy_summary(s)
        for s in st.generate_strategies(
            ctx=ctx_for(repo, "run_second"), objective=member_objective()
        )
    }
    moved = [
        sid for sid in snapshot if sid in regenerated and regenerated[sid] != snapshot[sid]
    ]
    assert moved, "if nothing moves here the fixture stopped exercising the risk"

    assert {
        r.strategy_id: dict(r.summary)
        for r in repo.list_run_strategy_references(WS, "run_first")
    } == snapshot


def test_writing_the_same_listing_twice_is_idempotent():
    """A retried dispatch must not double a run's own history."""
    repo = fresh_repo()
    ctx = ctx_for(repo, "run_first")
    st.generate_strategies(ctx=ctx, objective=member_objective())
    once = [r.id for r in repo.list_run_strategy_references(WS, "run_first")]
    st.generate_strategies(ctx=ctx, objective=member_objective())
    assert [r.id for r in repo.list_run_strategy_references(WS, "run_first")] == once


# ---------------------------------------------------------------------- evaluations


def test_evaluations_were_never_the_problem_and_still_are_not():
    """Each evaluation is its own row with its own id, so runs cannot collide.

    Checked rather than assumed, because the strategy table looked safe for the same
    reason until somebody asked what the second write did.
    """
    repo = fresh_repo()
    strategies = st.generate_strategies(
        ctx=ctx_for(repo, "run_first"), objective=member_objective()
    )
    shared = next(s for s in strategies if s.target_product_id == B_DARK)
    a = st.evaluate_strategy(ctx=ctx_for(repo, "run_first"), strategy_id=shared.id)

    st.generate_strategies(ctx=ctx_for(repo, "run_second"), objective=member_objective())
    b = st.evaluate_strategy(ctx=ctx_for(repo, "run_second"), strategy_id=shared.id)

    assert a.id != b.id
    assert a.run_id == "run_first" and b.run_id == "run_second"
    stored = {e.id: e for e in repo.list_strategy_evaluations(WS)}
    assert stored[a.id].run_id == "run_first", "a later evaluation overwrote an earlier one"
    assert a.strategy_id == b.strategy_id == shared.id
    for run_id, expected in (("run_first", a.id), ("run_second", b.id)):
        found = [e.id for e in repo.list_strategy_evaluations(WS) if e.run_id == run_id]
        assert found == [expected]


# --------------------------------------------------------------------- both backends


def test_both_backends_store_and_order_the_history_identically():
    memory, dynamo = fresh_repo("memory"), fresh_repo("dynamo")
    for repo in (memory, dynamo):
        st.generate_strategies(ctx=ctx_for(repo, "run_first"), objective=member_objective())

    a = memory.list_run_strategy_references(WS, "run_first")
    b = dynamo.list_run_strategy_references(WS, "run_first")
    assert [(r.run_id, r.ordinal, r.strategy_id) for r in a] == [
        (r.run_id, r.ordinal, r.strategy_id) for r in b
    ]
    assert [r.summary for r in a] == [r.summary for r in b]
    assert [r.id for r in memory.list_run_strategy_references(WS)] == [
        r.id for r in dynamo.list_run_strategy_references(WS)
    ]


def test_a_reference_survives_a_serialisation_round_trip():
    reference = RunStrategyReference(
        run_id="run_x",
        strategy_id="strat_y",
        ordinal=3,
        summary={"strategy_id": "strat_y", "compatible_units": 12},
    )
    assert RunStrategyReference.from_dict(reference.to_dict()) == reference
    assert reference.to_dict()["id"] == "run_x#strat_y"


@pytest.mark.parametrize("backend", ["memory", "dynamo"])
def test_one_run_cannot_read_another_runs_listing(backend):
    repo = fresh_repo(backend)
    st.generate_strategies(ctx=ctx_for(repo, "run_first"), objective=member_objective())
    st.generate_strategies(
        ctx=ctx_for(repo, "run_second"),
        objective=st.StrategyObjective(kind=st.OBJECTIVE_COMMUNITY, community_id=COMMUNITY_ID),
    )

    first = repo.list_run_strategy_references(WS, "run_first")
    second = repo.list_run_strategy_references(WS, "run_second")
    assert first and second
    assert all(r.run_id == "run_first" for r in first)
    assert all(r.run_id == "run_second" for r in second)
    assert len(repo.list_run_strategy_references(WS)) == len(first) + len(second)
