from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pool.api import app as app_module


@pytest.fixture
def client(monkeypatch):
    from pool.adapters.repository import InMemoryRepository

    fresh = InMemoryRepository()
    monkeypatch.setattr(app_module, "_repo", fresh)
    return TestClient(app_module.app)


class TestHealth:
    def test_health_reports_configuration(self, client):
        body = client.get("/api/health").json()
        assert body["ok"] is True
        assert body["repository"] == "memory"
        assert body["bounds"]["max_iterations"] > 0

    def test_health_reports_schedules_disabled_by_default(self, client):
        """Cost safety is visible from the outside."""
        assert client.get("/api/health").json()["schedules_enabled"] is False


class TestState:
    def test_state_autoseeds_and_returns_everything(self, client):
        body = client.get("/api/state?workspace=demo").json()
        assert body["counts"]["households"] == 25
        assert body["is_demo_data"] is True
        assert "metrics" in body and "activity" in body

    def test_invalid_workspace_rejected(self, client):
        assert client.get("/api/state?workspace=../etc").status_code == 400
        assert client.get("/api/state?workspace=A_B").status_code == 400

    def test_workspaces_are_isolated(self, client):
        client.post("/api/agent/run?workspace=alpha", json={"trigger": "t"})
        alpha = client.get("/api/state?workspace=alpha").json()
        beta = client.get("/api/state?workspace=beta").json()
        assert len(alpha["pools"]) == 1
        assert len(beta["pools"]) == 0


class TestAgentRun:
    def test_run_forms_a_pool(self, client):
        body = client.post("/api/agent/run?workspace=demo", json={"trigger": "test"}).json()
        assert body["outcome"] == "pool_created"
        assert body["iterations"] > 0
        assert [t["name"] for t in body["tool_calls"]][0] == "list_unmet_demand"

    def test_run_exposes_bounds_and_cost_telemetry(self, client):
        body = client.post("/api/agent/run?workspace=demo", json={"trigger": "test"}).json()
        assert body["termination_reason"] == "completed"
        assert body["model_provider"] == "offline"
        assert body["input_tokens"] == 0  # offline runs cost nothing

    def test_trace_contains_no_reasoning_text(self, client):
        run = client.post("/api/agent/run?workspace=demo", json={"trigger": "t"}).json()
        trace = client.get(f"/api/runs/{run['run_id']}?workspace=demo").json()
        blob = str(trace).lower()
        assert "thinking" not in blob and "reasoning" not in blob
        assert [t["name"] for t in trace["tool_calls"]]


class TestDecisions:
    def test_pending_decisions_are_listed_then_answerable(self, client):
        client.post("/api/agent/run?workspace=demo", json={"trigger": "t"})
        state = client.get("/api/state?workspace=demo").json()
        assert state["decisions"], "expected Ask Me households to need approval"
        d = state["decisions"][0]
        assert "policy_checks" in d["facts"]

        result = client.post(
            f"/api/decisions/{d['decision_id']}/respond?workspace=demo", json={"approve": True}
        ).json()
        assert result["state"] == "approved"

    def test_unknown_decision_404s(self, client):
        r = client.post("/api/decisions/nope/respond?workspace=demo", json={"approve": True})
        assert r.status_code == 404


class TestScenario:
    def test_full_scenario_endpoint(self, client):
        body = client.post("/api/demo/scenario?workspace=demo").json()
        assert body["ok"] is True, body.get("failure")
        names = [s["name"] for s in body["steps"]]
        assert names == ["seed", "background_scan", "pool_formed", "approvals",
                         "dropout", "recovery", "impact"]

    def test_reset_restores_the_starting_state(self, client):
        client.post("/api/demo/scenario?workspace=demo")
        assert len(client.get("/api/state?workspace=demo").json()["pools"]) == 1
        client.post("/api/demo/reset?workspace=demo")
        assert client.get("/api/state?workspace=demo").json()["pools"] == []


class TestPrivacy:
    def test_map_never_returns_precise_household_coordinates(self, client):
        """The single most important privacy assertion in the product."""
        body = client.get("/api/map?workspace=demo").json()
        assert body["households"]
        for h in body["households"]:
            assert h["lat"] == round(h["lat"], 3)
            assert h["lon"] == round(h["lon"], 3)
            assert "address" not in h
            assert "display_name" not in h  # map markers are not identified

    def test_map_only_exposes_public_pickup_sites(self, client):
        body = client.get("/api/map?workspace=demo").json()
        assert body["sites"]
        assert all(s["is_public"] for s in body["sites"])

    def test_pool_members_are_named_but_never_located(self, client):
        client.post("/api/agent/run?workspace=demo", json={"trigger": "t"})
        pool = client.get("/api/state?workspace=demo").json()["pools"][0]
        for m in pool["members"]:
            assert "lat" not in m and "lon" not in m and "address" not in m
            assert m["neighborhood"]  # neighbourhood-level context only


class TestWithdrawAndRecover:
    def test_withdraw_then_recover_through_the_api(self, client):
        client.post("/api/agent/run?workspace=demo", json={"trigger": "scan"})
        state = client.get("/api/state?workspace=demo").json()
        for d in state["decisions"]:
            client.post(f"/api/decisions/{d['decision_id']}/respond?workspace=demo",
                        json={"approve": True})

        pool = client.get("/api/state?workspace=demo").json()["pools"][0]
        assert pool["status"] == "threshold_met"
        biggest = max(
            (m for m in pool["members"] if m["state"] == "committed"),
            key=lambda m: m["units"],
        )
        out = client.post(
            f"/api/pools/{pool['pool_id']}/withdraw/{biggest['household_id']}?workspace=demo"
        ).json()
        assert out["below_threshold"] is True

        run = client.post("/api/agent/run?workspace=demo", json={"trigger": "recovery"}).json()
        # The scan prompt handles recovery too, but the explicit recovery path is what
        # the UI uses; either way the pool must come back.
        after = client.get(f"/api/pools/{pool['pool_id']}?workspace=demo").json()
        assert after["status"] in {"threshold_met", "recovering"}
        assert run["outcome"] in {"pool_recovered", "pool_created", "no_action"}

    def test_withdrawing_a_non_member_404s(self, client):
        client.post("/api/agent/run?workspace=demo", json={"trigger": "t"})
        pool = client.get("/api/state?workspace=demo").json()["pools"][0]
        r = client.post(f"/api/pools/{pool['pool_id']}/withdraw/ghost?workspace=demo")
        assert r.status_code == 404
