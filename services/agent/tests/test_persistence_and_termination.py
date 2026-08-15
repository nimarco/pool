from __future__ import annotations

from datetime import date

import pytest

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.agent.coordinator import PoolCoordinator
from pool.data.seed import seed
from pool.domain.models import (
    ActivityEvent,
    AgentRun,
    AutonomyPath,
    AutonomyPolicy,
    Household,
    Membership,
    MembershipState,
    Offer,
    OfferKind,
    Pool,
    PoolStatus,
    RunOutcome,
)

WS = "test"


class FakeTable:
    """Minimal in-memory stand-in for a boto3 DynamoDB Table resource."""

    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    def put_item(self, Item):  # noqa: N803 - boto3 casing
        self.items[(Item["pk"], Item["sk"])] = Item

    def get_item(self, Key):  # noqa: N803
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def query(self, KeyConditionExpression=None, **kw):  # noqa: N803
        # The fake understands only what the repository actually builds: an equality
        # on pk, optionally AND-ed with begins_with on sk.
        expr = KeyConditionExpression
        pk, prefix = self._decompose(expr)
        out = [
            v for (k_pk, k_sk), v in sorted(self.items.items())
            if k_pk == pk and (prefix is None or k_sk.startswith(prefix))
        ]
        return {"Items": out}

    @staticmethod
    def _decompose(expr):
        """Walk the boto3 condition tree rather than parsing its repr.

        ``Key('pk').eq(v)`` is an ``Equals`` whose ``_values`` is ``(Key, value)``;
        ``a & b`` is an ``And`` whose ``_values`` is ``(a, b)``.
        """
        pk = ""
        prefix = None

        def visit(node):
            nonlocal pk, prefix
            values = getattr(node, "_values", None)
            if values is None:
                return
            op = getattr(node, "expression_operator", "")
            if op == "AND":
                for child in values:
                    visit(child)
                return
            key_obj, value = values[0], values[1]
            name = getattr(key_obj, "name", None)
            if name == "pk" and op == "=":
                pk = value
            elif name == "sk" and op == "begins_with":
                prefix = value

        visit(expr)
        return pk, prefix

    def batch_writer(self):
        table = self

        class W:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def delete_item(self_inner, Key):  # noqa: N803
                table.items.pop((Key["pk"], Key["sk"]), None)

        return W()


@pytest.fixture
def dynamo() -> DynamoDBRepository:
    return DynamoDBRepository(table_name="pool-test", table=FakeTable())


class TestDynamoSerialisation:
    """Pins the storage contract. The table itself is unverified against real AWS,
    but the shapes that would be written are asserted here."""

    def test_household_roundtrip_preserves_floats_and_policy(self, dynamo):
        h = Household(
            id="h1", display_name="Test household", neighborhood="Core",
            lat=38.65583, lon=-90.30501, is_host_willing=True,
            autonomy=AutonomyPolicy(min_savings_pct=27, max_total_cost_cents=3300),
        )
        dynamo.put_household(WS, h)
        got = dynamo.get_household(WS, "h1")
        assert got.lat == pytest.approx(38.65583)
        assert got.lon == pytest.approx(-90.30501)
        assert got.autonomy.min_savings_pct == 27
        assert got.is_host_willing is True

    def test_money_survives_as_exact_integers(self, dynamo):
        m = Membership(
            pool_id="p1", household_id="h1", need_id="n1", requested_units=15,
            allocated_units=15, cost_cents=1336, baseline_cents=2025,
            savings_cents=689, savings_bps=3402, travel_minutes=3,
            state=MembershipState.COMMITTED, path=AutonomyPath.SMART_JOIN,
        )
        dynamo.put_membership(WS, m)
        got = dynamo.get_membership(WS, "p1", "h1")
        assert got.cost_cents == 1336 and isinstance(got.cost_cents, int)
        assert got.savings_bps == 3402

    def test_enums_and_dates_roundtrip(self, dynamo):
        p = Pool(
            id="p1", product_id="prod", offer_id="off", pickup_site_id="site",
            status=PoolStatus.THRESHOLD_MET, threshold_units=150,
            deadline=date(2026, 9, 1), created_by_run="r1", idempotency_key="k",
        )
        dynamo.put_pool(WS, p)
        got = dynamo.get_pool(WS, "p1")
        assert got.status == PoolStatus.THRESHOLD_MET
        assert got.deadline == date(2026, 9, 1)

    def test_offer_optional_date_roundtrips_as_none(self, dynamo):
        dynamo.put_offer(WS, Offer("o1", "S", "prod", OfferKind.BULK, 69, 25, 150, None))
        assert dynamo.get_offer(WS, "o1").valid_until is None

    def test_memberships_query_is_scoped_to_one_pool(self, dynamo):
        for pool_id in ("p1", "p2"):
            for hid in ("h1", "h2"):
                dynamo.put_membership(WS, Membership(
                    pool_id=pool_id, household_id=hid, need_id="n", requested_units=1,
                    allocated_units=1, cost_cents=1, baseline_cents=2, savings_cents=1,
                    savings_bps=5000, travel_minutes=1,
                    state=MembershipState.COMMITTED, path=AutonomyPath.SMART_JOIN,
                ))
        assert len(dynamo.list_memberships(WS, "p1")) == 2
        assert {m.pool_id for m in dynamo.list_memberships(WS, "p1")} == {"p1"}

    def test_demo_workspaces_get_a_ttl_and_primary_does_not(self, dynamo):
        dynamo.append_activity("judge_x", ActivityEvent(id="e1", kind="k", summary="s"))
        dynamo.append_activity("primary", ActivityEvent(id="e2", kind="k", summary="s"))
        items = list(dynamo.table.items.values())
        demo = [i for i in items if i["pk"].startswith("judge_x")][0]
        primary = [i for i in items if i["pk"].startswith("primary")][0]
        assert "ttl" in demo and demo["ttl"] > 0
        assert "ttl" not in primary

    def test_reset_is_scoped_to_one_workspace(self, dynamo):
        """A cleanup path that could reach another workspace is a cleanup path that
        could one day reach another table."""
        dynamo.put_household("ws_a", Household("h", "A", "n", 1.0, 2.0))
        dynamo.put_household("ws_b", Household("h", "B", "n", 1.0, 2.0))
        dynamo.reset("ws_a")
        assert dynamo.get_household("ws_a", "h") is None
        assert dynamo.get_household("ws_b", "h") is not None

    def test_run_record_roundtrips(self, dynamo):
        run = AgentRun(
            id="r1", trigger="t", model_id="m", model_provider="offline",
            started_at="2026-08-15T00:00:00+00:00", outcome=RunOutcome.POOL_CREATED,
            iterations=3, termination_reason="completed",
        )
        dynamo.put_run(WS, run)
        got = dynamo.get_run(WS, "r1")
        assert got.outcome == RunOutcome.POOL_CREATED and got.iterations == 3


class TestTerminationRegression:
    """Regression: the planner used to re-issue record_no_action forever once it ran
    out of viable products. The run-level bound caught it, but a planner that relies on
    the safety net every cycle is a bug, not a design."""

    def test_a_scan_with_nothing_to_do_terminates_cleanly(self):
        repo = InMemoryRepository()
        seed(repo, WS)
        c = PoolCoordinator(repo)
        # First scan takes the one good opportunity.
        c.run(WS, trigger="first")
        # Subsequent scans have nothing worthwhile left and must stop on their own.
        for _ in range(3):
            run = c.run(WS, trigger="repeat")
            assert run.outcome != RunOutcome.LOOP_FAULT, run.termination_reason
            assert run.termination_reason == "completed"
            assert run.iterations <= 8

    def test_recovery_with_no_broken_pool_terminates_cleanly(self):
        repo = InMemoryRepository()
        seed(repo, WS)
        run = PoolCoordinator(repo).run(
            WS, trigger="t", instruction="Recover any pool below its threshold."
        )
        assert run.outcome == RunOutcome.NO_ACTION
        assert run.termination_reason == "completed"
