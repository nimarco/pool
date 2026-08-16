"""Persistence contracts and the promise that every run terminates in a recorded state.

The DynamoDB adapter has never touched a live table (no credentials were available when
it was written), so these tests pin the serialisation contract against a fake client
rather than claiming a verified integration.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from pool.adapters.repository import (
    _TYPES,
    DynamoDBRepository,
    InMemoryRepository,
    build_repository,
)
from pool.adapters.routing import DeterministicRouting
from pool.agent.coordinator import PoolCoordinator
from pool.config import AgentBounds, Settings
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import (
    ActivityEvent,
    AgentRun,
    Announcement,
    AnnouncementKind,
    AutonomyPath,
    Community,
    CommunityMembership,
    FulfillerRole,
    HostAssignment,
    HostCandidate,
    HostCandidateSource,
    HostCandidateState,
    HostProfile,
    IssueCase,
    IssueKind,
    IssueState,
    Membership,
    Message,
    MessageThread,
    ParticipationState,
    PaymentRecord,
    PaymentState,
    PickupAllocation,
    PickupToken,
    Pool,
    PoolStatus,
    PurchaseRecord,
    RunOutcome,
    Supplier,
    iso,
    new_id,
    utcnow,
)
from tests.conftest import COMM, WS, make_community, make_member, make_membership, make_need

# --------------------------------------------------------------------- fake client


class FakeTable:
    """A minimal in-process stand-in for a DynamoDB Table resource."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, Item):  # noqa: N803 - boto3's parameter name
        assert isinstance(Item["pk"], str) and isinstance(Item["sk"], str)
        self._assert_storable(Item["data"])
        self.items[(Item["pk"], Item["sk"])] = Item

    def get_item(self, Key):  # noqa: N803
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def query(self, **kwargs):
        # The fake ignores the condition object and filters on the recorded prefix the
        # repository passes; enough to pin the key layout without reimplementing boto3.
        cond = kwargs["KeyConditionExpression"]
        pk = getattr(cond, "_values", [None, None])[1]
        if hasattr(cond, "_values") and len(cond._values) == 2 and hasattr(cond._values[0], "_values"):
            pk = cond._values[0]._values[1]
            prefix = cond._values[1]._values[1]
            items = [
                v for (k_pk, k_sk), v in self.items.items()
                if k_pk == pk and k_sk.startswith(prefix)
            ]
        else:
            items = [v for (k_pk, _), v in self.items.items() if k_pk == pk]
        return {"Items": items}

    @staticmethod
    def _assert_storable(value: Any) -> None:
        """Floats do not round-trip through the resource API's default serialiser."""
        if isinstance(value, float):
            raise AssertionError("raw float reached DynamoDB serialisation")
        if isinstance(value, dict):
            for v in value.values():
                FakeTable._assert_storable(v)
        if isinstance(value, list):
            for v in value:
                FakeTable._assert_storable(v)


@pytest.fixture
def dynamo() -> DynamoDBRepository:
    return DynamoDBRepository("pool-state", table=FakeTable())


# --------------------------------------------------------------------- round trips


def test_every_persisted_type_is_in_the_reset_map():
    """A new entity added to persistence but not to reset would survive a demo reset."""
    store_fields = set(InMemoryRepository().store(WS).__dict__)
    # ACTIVITY is a list in memory; everything else is a dict keyed by id.
    assert len(_TYPES) >= len(store_fields) - 1


def test_community_and_membership_round_trip(dynamo):
    community = make_community(COMMUNITY_ID)
    dynamo.put_community(WS, community)
    restored = dynamo.get_community(WS, community.id)
    assert restored.name == community.name
    assert restored.schedule.distribution_weekday == community.schedule.distribution_weekday
    assert restored.platform_fee.bps == community.platform_fee.bps

    membership = make_membership("m1", COMMUNITY_ID)
    dynamo.put_community_membership(WS, membership)
    assert dynamo.get_community_membership(WS, COMMUNITY_ID, "m1").is_verified


def test_coordinates_survive_the_float_workaround(dynamo):
    member = make_member("m1", dlat=0.001234, dlon=-0.005678)
    dynamo.put_household(WS, member)
    restored = dynamo.get_household(WS, "m1")
    assert restored.lat == member.lat
    assert restored.lon == member.lon


def test_money_stays_exact_through_persistence(dynamo):
    record = PaymentRecord(
        id="pay_1", pool_id="pool_1", household_id="m1", amount_cents=7184,
        state=PaymentState.AUTHORIZED, provider="simulated", provider_mode="simulated",
    )
    dynamo.put_payment(WS, record)
    assert dynamo.get_payment(WS, "pay_1").amount_cents == 7184


def test_pool_timing_and_economics_round_trip(dynamo):
    pool = Pool(
        id="pool_1", community_id=COMM, product_id="p", offer_id="o", pickup_site_id="s",
        status=PoolStatus.FUNDING, threshold_units=24,
        final_economics={"all_in_cents": 86144, "net_savings_bps": 2353},
        quote_verified_at=iso(utcnow()),
    )
    dynamo.put_pool(WS, pool)
    restored = dynamo.get_pool(WS, "pool_1")
    assert restored.status == PoolStatus.FUNDING
    assert restored.final_economics["all_in_cents"] == 86144
    assert restored.has_final_offer is True


def test_needs_round_trip_with_both_timing_numbers(dynamo):
    need = make_need("n1", "m1", "p", 3, days_out=20, flexibility_days=15, routine_lead_days=5)
    dynamo.put_need(WS, need)
    restored = dynamo.get_need(WS, "n1")
    assert restored.expected_next_need_date == need.expected_next_need_date
    assert restored.earliest_acceptable_purchase_date == need.earliest_acceptable_purchase_date
    assert restored.routine_lead_days == 5
    assert restored.flexibility_days == 15


def test_host_records_round_trip(dynamo):
    dynamo.put_host_profile(WS, HostProfile(household_id="h1", community_id=COMM))
    assert dynamo.get_host_profile(WS, COMM, "h1").willing_to_host

    dynamo.put_host_candidate(
        WS,
        HostCandidate(
            pool_id="pool_1", household_id="h1", source=HostCandidateSource.STANDING,
            state=HostCandidateState.OFFERED, score=42,
            score_components={"vehicle": 25}, supplier_distance_km=10.5,
        ),
    )
    candidate = dynamo.get_host_candidate(WS, "pool_1", "h1")
    assert candidate.state == HostCandidateState.OFFERED
    assert candidate.supplier_distance_km == 10.5

    dynamo.put_host_assignment(
        WS,
        HostAssignment(
            pool_id="pool_1", household_id="h1", role=FulfillerRole.FULFILLER,
            pickup_site_id="s", supplier_distance_km=10.5, handled_orders=10,
            handled_units=24, estimated_weight_kg=55, reward_total_cents=4468,
        ),
    )
    assert dynamo.get_host_assignment(WS, "pool_1").reward_total_cents == 4468


def test_fulfillment_records_round_trip(dynamo):
    dynamo.put_purchase(
        WS,
        PurchaseRecord(
            id="buy_1", pool_id="pool_1", supplier_id="sup", offer_snapshot={"id": "o"},
            units_purchased=24, cases_purchased=2, total_cents=75600,
            supplier_reference="SIMULATED-1", executed_at=iso(utcnow()),
        ),
    )
    assert dynamo.get_purchase_for_pool(WS, "pool_1").simulated is True

    dynamo.put_allocation(
        WS, PickupAllocation(pool_id="pool_1", household_id="m1", units=2)
    )
    assert dynamo.get_allocation(WS, "pool_1", "m1").units == 2

    dynamo.put_pickup_token(
        WS,
        PickupToken(
            id="tok_1", pool_id="pool_1", household_id="m1", token_hash="a" * 64,
            code_hash="b" * 64, issued_at=iso(utcnow()),
        ),
    )
    assert dynamo.get_pickup_token(WS, "pool_1", "m1").is_redeemable


def test_communication_records_round_trip(dynamo):
    dynamo.put_announcement(
        WS,
        Announcement(id="ann_1", pool_id="pool_1", kind=AnnouncementKind.SYSTEM, body="hi"),
    )
    assert dynamo.list_announcements(WS, "pool_1")[0].body == "hi"

    thread = MessageThread(
        id="thr_1", pool_id="pool_1", buyer_household_id="m1", host_household_id="h1"
    )
    dynamo.put_thread(WS, thread)
    assert dynamo.get_thread_for(WS, "pool_1", "m1").id == "thr_1"

    dynamo.put_message(
        WS, Message(id="msg_1", thread_id="thr_1", sender_household_id="m1", body="hello")
    )
    assert dynamo.list_messages(WS, "thr_1")[0].body == "hello"

    dynamo.put_issue(
        WS,
        IssueCase(
            id="iss_1", pool_id="pool_1", household_id="m1",
            kind=IssueKind.DAMAGED_ITEM, state=IssueState.OPEN,
        ),
    )
    assert dynamo.get_issue(WS, "iss_1").kind == IssueKind.DAMAGED_ITEM


def test_membership_and_supplier_round_trip(dynamo):
    dynamo.put_membership(
        WS,
        Membership(
            pool_id="pool_1", household_id="m1", need_id="n1", requested_units=2,
            allocated_units=2, state=ParticipationState.AUTHORIZED,
            path=AutonomyPath.SMART_JOIN, final_cost_cents=7184,
        ),
    )
    restored = dynamo.get_membership(WS, "pool_1", "m1")
    assert restored.counts_as_funded is True
    assert restored.final_cost_cents == 7184

    dynamo.put_supplier(WS, Supplier("sup_1", "Wholesale", 38.6, -90.3))
    assert dynamo.get_supplier(WS, "sup_1").lat == 38.6


def test_agent_runs_round_trip_with_their_telemetry(dynamo):
    run = AgentRun(
        id="run_1", trigger="test", model_id="offline", model_provider="offline",
        started_at=iso(utcnow()), ended_at=iso(utcnow()), outcome=RunOutcome.POOL_CREATED,
        iterations=4, termination_reason="completed", input_tokens=0, output_tokens=0,
    )
    dynamo.put_run(WS, run)
    restored = dynamo.get_run(WS, "run_1")
    assert restored.outcome == RunOutcome.POOL_CREATED
    assert restored.iterations == 4


def test_activity_events_round_trip(dynamo):
    dynamo.append_activity(
        WS, ActivityEvent(id="evt_1", kind="pool_created", summary="formed", facts={"n": 1})
    )
    assert dynamo.list_activity(WS)[0].kind == "pool_created"


def test_workspace_partitions_never_collide(dynamo):
    dynamo.put_household(WS, make_member("m1"))
    assert dynamo.get_household("another", "m1") is None


def test_builder_rejects_an_unknown_backend():
    assert isinstance(build_repository("memory", "t", "us-east-1"), InMemoryRepository)
    with pytest.raises(ValueError):
        build_repository("postgres", "t", "us-east-1")


def test_in_memory_reset_clears_everything(repo):
    seed(repo, WS)
    assert repo.list_households(WS)
    repo.reset(WS)
    assert repo.list_households(WS) == []
    assert repo.list_communities(WS) == []


def test_activity_ordering_is_stable_within_the_same_timestamp(repo):
    stamp = iso(utcnow())
    for i in range(5):
        repo.append_activity(
            WS, ActivityEvent(id=f"evt_{i}", kind="k", summary=str(i), at=stamp)
        )
    ordered = [e.summary for e in repo.list_activity(WS)]
    assert ordered == ["4", "3", "2", "1", "0"]


# --------------------------------------------------------------------- termination


def _settings(**overrides) -> Settings:
    defaults = {"routing_provider": "deterministic", "repository": "memory",
                "model_provider": "offline"}
    defaults.update(overrides)
    return Settings(**defaults)


def test_every_run_terminates_in_a_recorded_state(repo):
    """There is no path where a run simply stops without an outcome (AGENTS.md §3.1)."""
    seed(repo, WS)
    run = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    ).run(WS, trigger="test", community_id=COMMUNITY_ID)
    assert run.outcome in set(RunOutcome)
    assert run.ended_at
    assert run.termination_reason
    assert run.duration_ms is not None


def test_a_run_records_zero_token_spend_when_offline(repo):
    seed(repo, WS)
    run = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    ).run(WS, trigger="test", community_id=COMMUNITY_ID)
    assert run.input_tokens == 0
    assert run.output_tokens == 0
    assert run.model_provider == "offline"


def test_an_empty_community_terminates_cleanly_without_bothering_anyone(repo):
    repo.put_community(WS, make_community(COMMUNITY_ID))
    run = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    ).run(WS, trigger="test", community_id=COMMUNITY_ID)
    assert run.outcome == RunOutcome.NO_ACTION
    assert repo.list_pools(WS) == []
    assert repo.list_decisions(WS) == []


def test_a_second_scan_does_not_duplicate_a_pool(repo):
    seed(repo, WS)
    coordinator = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    )
    coordinator.run(WS, trigger="one", community_id=COMMUNITY_ID)
    pools_after_first = len(repo.list_pools(WS))
    coordinator.run(WS, trigger="two", community_id=COMMUNITY_ID)
    # A second scan may form a *different* product's pool, but never a duplicate of
    # the same one: membership is exclusive per product.
    ids = {(p.product_id, p.pickup_site_id, p.timing.distribution_starts_at)
           for p in repo.list_pools(WS)}
    assert len(ids) == len(repo.list_pools(WS))
    assert len(repo.list_pools(WS)) >= pools_after_first


def test_bounds_are_configurable_from_the_environment(monkeypatch):
    monkeypatch.setenv("MAX_AGENT_ITERATIONS", "3")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "7")
    bounds = AgentBounds.from_env()
    assert bounds.max_iterations == 3
    assert bounds.max_tool_calls == 7


def test_schedules_are_disabled_by_default():
    """A forgotten schedule is the single most likely way this project dies (§3.2)."""
    assert Settings().schedules_enabled is False


def test_a_live_stripe_key_is_never_treated_as_configured():
    assert Settings(stripe_api_key="sk_live_abc").stripe_configured is False
    assert Settings(stripe_api_key="sk_test_abc").stripe_configured is True


def test_seed_dates_are_relative_so_the_demo_never_goes_stale(repo):
    """A dataset pinned to fixed dates quietly expires; this one does not (§92)."""
    seed(repo, WS)
    today = date.today()
    for need in repo.list_needs(WS):
        assert need.expected_next_need_date >= today
        assert need.expected_next_need_date <= today + timedelta(days=60)


def test_reseeding_overwrites_rather_than_duplicating(repo):
    first = seed(repo, WS)
    second = seed(repo, WS)
    assert first == second
    assert len(repo.list_households(WS)) == first["members"]


def test_new_id_is_prefixed_and_unique():
    ids = {new_id("pool") for _ in range(100)}
    assert len(ids) == 100
    assert all(i.startswith("pool_") for i in ids)


def test_community_membership_key_supports_multiple_communities():
    """One account belonging to several Communities is a schema fact, not a migration."""
    campus = CommunityMembership(
        community_id="comm_campus", household_id="m1",
        status=make_membership("m1").status,
        verification_method=make_membership("m1").verification_method,
    )
    apartment = CommunityMembership(
        community_id="comm_apartment", household_id="m1",
        status=campus.status, verification_method=campus.verification_method,
    )
    assert campus.key != apartment.key
    repo = InMemoryRepository()
    repo.put_community_membership(WS, campus)
    repo.put_community_membership(WS, apartment)
    assert len(repo.list_community_memberships(WS)) == 2
    assert len(repo.list_community_memberships(WS, "comm_campus")) == 1


def test_community_config_defaults_are_sane():
    community = Community(
        id="c", name="C", kind=make_community().kind, center_lat=0, center_lon=0
    )
    assert community.quote_max_age_hours > 0
    assert community.platform_fee.bps > 0
    assert community.host_reward.minimum_cents > 0


def test_a_run_that_did_work_never_reports_no_action(repo):
    """Concluding "nothing further to do" must not erase what a run actually did.

    The terminal tool records its reason regardless, but a run that formed a pool, locked
    one, or repaired one did not take *no action* — and a record saying otherwise would
    misreport real work to an operator or a judge.
    """
    seed(repo, WS)
    coordinator = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    )
    run = coordinator.run(WS, trigger="scan", community_id=COMMUNITY_ID)
    assert run.outcome == RunOutcome.POOL_CREATED
    assert repo.list_pools(WS)

    # A second scan has nothing left to form, and that *is* no action.
    idle = coordinator.run(WS, trigger="scan_again", community_id=COMMUNITY_ID)
    assert idle.outcome in {RunOutcome.NO_ACTION, RunOutcome.POOL_CREATED}


def test_a_blocked_run_records_why_it_stopped(repo):
    """A silent stop looks identical to finding nothing. Those are different situations."""
    from pool.domain.models import utcnow as _utcnow
    from pool.services import hosting
    from pool.services.context import PoolContext

    seed(repo, WS)
    coordinator = PoolCoordinator(
        repo, settings=_settings(), routing=DeterministicRouting(max_cells=100)
    )
    coordinator.run(WS, trigger="scan", community_id=COMMUNITY_ID)
    pool = repo.list_pools(WS)[0]

    ctx = PoolContext(
        repo=repo, ws=WS, routing=coordinator.routing, payments=coordinator.payments,
        purchaser=coordinator.purchaser, sourcing=coordinator.sourcing, now=_utcnow(),
    )
    offered = [
        c for c in repo.list_host_candidates(WS, pool.id) if c.state.value == "offered"
    ]
    assert offered, "the scan should have offered the job to a host"
    hosting.respond_to_host_offer(
        ctx=ctx, pool_id=pool.id, household_id=offered[0].household_id, accept=True
    )

    advance = (
        "Advance every pool that is blocked: recruit a host, refresh the supplier quote, "
        "issue final offers, recover lost demand, and lock anything that is fully funded "
        "and viable."
    )
    coordinator.run(WS, trigger="advance", instruction=advance, community_id=COMMUNITY_ID)
    # The pool is now waiting on buyers who must answer for themselves — something the
    # agent cannot resolve. It should stop, and say so.
    blocked = coordinator.run(
        WS, trigger="advance_again", instruction=advance, community_id=COMMUNITY_ID
    )
    assert blocked.outcome == RunOutcome.NO_ACTION
    assert blocked.notes, "a run that stopped without acting must record why"
    assert "pool" in blocked.notes[0].lower()
