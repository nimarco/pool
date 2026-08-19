"""The HTTP surface: shape, safety, and the privacy guarantees it must uphold.

The API is the only thing a browser talks to, so this is where "no address, no email,
no payment reference ever leaves the server" has to actually hold.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pool.agent.tools import TOOL_KINDS
from pool.api import app as api
from pool.data.seed import COMMUNITY_ID
from pool.domain.models import PoolStatus


@pytest.fixture
def client() -> TestClient:
    # A fresh workspace per test keeps runs isolated, exactly as two judges would be.
    api._repo.reset("demo")
    return TestClient(api.app)


def _seed(client: TestClient) -> dict:
    return client.get("/api/state").json()


class _Scoped:
    """A client bound to one workspace, so a test does not repeat the query parameter.

    Needed because the canonical showcase runs in its own partition: it must never
    rewrite the account a visitor set up for themselves, so a test that wants a finished
    pool reads the workspace the showcase actually ran in rather than expecting the
    visitor's own to have been overwritten.
    """

    def __init__(self, client: TestClient, ws: str) -> None:
        self._client, self._ws = client, ws

    def _url(self, path: str) -> str:
        return f"{path}{'&' if '?' in path else '?'}workspace={self._ws}"

    def get(self, path: str, **kwargs):
        return self._client.get(self._url(path), **kwargs)

    def post(self, path: str, **kwargs):
        return self._client.post(self._url(path), **kwargs)


def _showcase(client: TestClient) -> _Scoped:
    """Drive the canonical lifecycle, and hand back a client reading where it ran."""
    body = client.post("/api/demo/scenario").json()
    assert body["ok"] is True, body.get("failure")
    return _Scoped(client, body["workspace"])


# --------------------------------------------------------------------------- health


def test_health_reports_the_active_adapters(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["payment_mode"] in {"simulated", "test"}
    assert body["purchase_simulated"] is True
    assert body["schedules_enabled"] is False


def test_health_never_reports_a_live_payment_mode(client):
    """A live mode here would mean a misconfiguration could charge a real card."""
    assert client.get("/api/health").json()["payment_mode"] != "live"


def test_health_publishes_the_agent_tool_surface(client):
    """The UI shows a judge which tools the agent could have chosen from.

    It reads that list from here rather than keeping its own copy, so this endpoint has
    to serve it in every mode. ``test_agent_projection.py`` is what keeps the list
    honest against the tools actually built.
    """
    tools = client.get("/api/health").json()["agent_tools"]
    assert len(tools) == 12
    assert tools[0] == {"name": "list_latent_demand", "kind": "read"}
    assert {t["kind"] for t in tools} <= TOOL_KINDS
    # The host search writes, so it must not be published to the UI as a read.
    assert {"name": "find_host_candidates", "kind": "record"} in tools


def test_a_named_trigger_gets_the_same_prompt_locally_as_it_would_deployed(client):
    """`manual_advance` has to mean "advance" everywhere.

    The trigger-to-prompt map used to be consulted only in public mode, so the same
    button ran the *discovery* prompt against the local API: the agent went hunting for
    new pools instead of moving the one in front of it. Identical name, identical
    request, different behaviour depending on an environment variable.
    """
    _seed(client)
    client.post("/api/agent/run", json={"trigger": "manual_scan"})
    body = client.post("/api/agent/run", json={"trigger": "manual_advance"}).json()
    called = [t["name"] for t in body["tool_calls"]]
    assert "list_pools_needing_attention" in called
    assert "list_latent_demand" not in called


def test_demo_config_answers_outside_public_mode(client):
    """Off is a real answer, and a 404 here put a red line in a judge's console.

    The client asks this on every load to decide whether to offer the live AgentCore
    action. When the route existed only in public mode, a local run answered 404 — the
    behaviour was right and the console looked broken.
    """
    body = client.get("/api/demo/config").json()
    assert body["public_demo"] is False
    assert body["live_agent_available"] is False
    assert body["payments"] == "simulated"


# --------------------------------------------------------------------------- state


def test_state_seeds_on_first_read_and_is_labelled_demo_data(client):
    body = _seed(client)
    assert body["is_demo_data"] is True
    assert body["community"]["name"] == "Demo University"
    assert body["community"]["synthetic"] is True
    assert body["counts"]["members"] > 0
    assert body["counts"]["needs"] > 0
    enablement = body["community"]["enablement"]
    assert enablement["total_memberships"] == body["counts"]["members"]
    assert enablement["verified_members"] == enablement["total_memberships"]
    assert enablement["independent_need_declarers"] > 0
    assert enablement["verification_methods"] == ["demo"]
    assert enablement["designated_pickup_sites"]
    assert {site["permission"] for site in enablement["designated_pickup_sites"]} == {"demo"}


def test_an_invalid_workspace_is_rejected(client):
    assert client.get("/api/state?workspace=../etc").status_code == 400
    assert client.get("/api/state?workspace=" + "x" * 60).status_code == 400


def test_workspaces_are_isolated(client):
    """One workspace's coordination is invisible in another's.

    Driven with a real coordinator run rather than the showcase, because the showcase
    now writes its own partition — so using it here would prove isolation between two
    workspaces neither of which was ever written.
    """
    client.get("/api/state?workspace=one")
    client.post("/api/agent/run?workspace=one", json={"trigger": "manual_scan"})
    assert client.get("/api/state?workspace=one").json()["pools"]
    assert client.get("/api/state?workspace=two").json()["pools"] == []


# --------------------------------------------------------------------------- privacy


def test_no_endpoint_leaks_contact_details_or_payment_references(client):
    """The three things that must never reach a browser (§82, AGENTS.md §4)."""
    client = _showcase(client)
    payloads = [
        client.get("/api/state").text,
        client.get("/api/map").text,
        client.get("/api/needs").text,
        client.get("/api/operator").text,
    ]
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]
    payloads.append(client.get(f"/api/pools/{pool_id}").text)
    payloads.append(client.get(f"/api/pools/{pool_id}/checklist").text)
    combined = "".join(payloads)
    assert "@demo.invalid" not in combined
    assert "pm_sim_" not in combined
    assert "contact_email" not in combined


def test_member_positions_are_coarse_and_carry_no_address(client):
    body = client.get("/api/map").json()
    assert body["position_precision_m"] == 110
    for member in body["members"]:
        assert round(member["lat"], 3) == member["lat"]
        assert round(member["lon"], 3) == member["lon"]
        assert "address" not in member


def test_a_member_view_exposes_a_boolean_not_a_payment_reference(client):
    _seed(client)
    body = client.get("/api/members/hh_okafor").json()
    assert body["has_payment_method"] is True
    assert "payment_method_ref" not in body
    assert "contact_email" not in body


def test_pickup_sites_carry_an_honest_permission_status(client):
    body = client.get("/api/pickup-sites").json()
    assert body["sites"]
    # Nothing in the demo claims a real space authorised commercial pickup.
    assert all(s["permission"] == "demo" for s in body["sites"])


# --------------------------------------------------------------------------- agent


def test_a_run_returns_a_trace_with_no_reasoning_text(client):
    _seed(client)
    body = client.post("/api/agent/run", json={"trigger": "test"}).json()
    assert body["outcome"] in {
        "pool_created", "pool_advanced", "pool_recovered", "no_action"
    }
    assert isinstance(body["tool_calls"], list)
    assert body["model_provider"] == "offline"
    assert "reasoning" not in body
    assert "prompt" not in body


def test_the_full_run_record_is_retrievable(client):
    _seed(client)
    run_id = client.post("/api/agent/run", json={"trigger": "test"}).json()["run_id"]
    body = client.get(f"/api/runs/{run_id}").json()
    assert body["id"] == run_id
    assert body["duration_ms"] is not None
    assert set(body["tool_calls"][0]) == {"name", "arguments_digest", "ok", "summary", "at"}


def test_an_unknown_run_is_a_404(client):
    assert client.get("/api/runs/run_nope").status_code == 404


# --------------------------------------------------------------------------- flow


def test_the_scenario_endpoint_runs_the_whole_lifecycle(client):
    body = client.post("/api/demo/scenario").json()
    assert body["ok"] is True, body["failure"]
    names = [s["name"] for s in body["steps"]]
    assert "latent_demand_discovered" in names
    assert "host_accepted" in names
    assert "final_offer" in names
    assert "locked_and_captured" in names
    assert "pickup" in names


def test_pool_detail_exposes_economics_hosts_and_viability(client):
    client = _showcase(client)
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]
    body = client.get(f"/api/pools/{pool_id}").json()
    assert body["members"]
    assert body["host"]["display_name"]
    assert body["economics"]["all_in_cents"] > 0
    assert "viability" in body
    assert body["host_candidates"]


def test_a_pool_reports_buyers_and_memberships_separately(client):
    """After a declined card these two counts differ, and the UI shows both.

    `member_count` is every membership still on the record; `buyer_count` is how many
    people actually receive something. Collapsing them left a judge reconciling
    "11 members" against "10 handoffs confirmed" with nothing to go on.
    """
    client = _showcase(client)
    pool = client.get("/api/state").json()["pools"][0]
    assert pool["buyer_count"] >= 1
    assert pool["member_count"] >= pool["buyer_count"]
    declined = [
        m
        for m in client.get(f"/api/pools/{pool['pool_id']}").json()["members"]
        if m["state"] == "authorization_failed"
    ]
    assert pool["member_count"] - pool["buyer_count"] == len(declined)


def test_an_unknown_pool_is_a_404(client):
    assert client.get("/api/pools/pool_nope").status_code == 404


def test_withdrawing_after_lock_is_a_conflict_not_a_silent_success(client):
    client = _showcase(client)
    state = client.get("/api/state").json()
    pool = state["pools"][0]
    detail = client.get(f"/api/pools/{pool['pool_id']}").json()
    buyer = detail["members"][0]["household_id"]
    response = client.post(f"/api/pools/{pool['pool_id']}/withdraw/{buyer}")
    assert response.status_code == 409
    assert "locked" in response.json()["detail"]


def test_volunteering_to_host_does_not_claim_the_job(client):
    _seed(client)
    client.post("/api/agent/run", json={"trigger": "scan"})
    pools = client.get("/api/state").json()["pools"]
    if not pools:
        pytest.skip("no pool formed in this scan")
    pool_id = pools[0]["pool_id"]
    body = client.post(
        f"/api/pools/{pool_id}/host-offer/hh_okafor",
        json={"has_vehicle": True, "minimum_compensation_cents": 0},
    ).json()
    assert "candidate set" in body["note"]
    assert body["candidates"]


def test_the_operator_console_shows_offers_payments_and_purchases(client):
    client = _showcase(client)
    body = client.get("/api/operator").json()
    assert body["offers"]
    assert any(o["source"] == "synthetic" for o in body["offers"])
    pool = body["pools"][0]
    assert pool["payments"]
    assert pool["purchase"]["simulated"] is True
    assert body["metrics"]["is_demo_data"] is True


def test_an_operator_can_record_a_manually_verified_offer(client):
    _seed(client)
    response = client.post(
        "/api/operator/offers",
        json={
            "offer_id": "off_manual_1",
            "supplier_id": "sup_riverbend",
            "product_id": "prod_coffee_beans",
            "unit_price_cents": 1500,
            "case_units": 6,
            "moq_amount": 12,
            "supplier_reference": "phoned 2026-08-15",
        },
    )
    body = response.json()
    assert body["source"] == "manual_verified"
    assert body["verified_at"]


def test_an_operator_offer_for_an_unknown_product_is_rejected(client):
    _seed(client)
    response = client.post(
        "/api/operator/offers",
        json={
            "offer_id": "off_x", "supplier_id": "sup_riverbend",
            "product_id": "nope", "unit_price_cents": 100,
        },
    )
    assert response.status_code == 400


def test_disabling_an_offer_takes_it_out_of_circulation(client):
    _seed(client)
    body = client.post("/api/operator/offers/off_whey_bulk/disable").json()
    assert body["active"] is False


# --------------------------------------------------------------------------- pickup


def test_a_pickup_credential_is_returned_once_and_works_once(client):
    client = _showcase(client)
    state = client.get("/api/state").json()
    pool_id = state["pools"][0]["pool_id"]
    allocations = client.get(f"/api/pools/{pool_id}/allocations").json()
    assert allocations["picked_up"] == len(allocations["allocations"])
    # Every credential in the scenario has already been redeemed, so re-issuing is
    # refused rather than quietly minting a second way in.
    buyer = allocations["allocations"][0]["household_id"]
    response = client.post(f"/api/pools/{pool_id}/pickup-credential/{buyer}")
    assert response.status_code == 400


def test_redeeming_a_forged_credential_fails(client):
    client = _showcase(client)
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]
    body = client.post(
        f"/api/pools/{pool_id}/redeem", json={"value": "definitely-not-a-token"}
    ).json()
    assert body["ok"] is False


def test_an_operator_override_requires_a_reason(client):
    client = _showcase(client)
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]
    response = client.post(
        f"/api/pools/{pool_id}/override/hh_okafor", json={"reason": "x"}
    )
    assert response.status_code == 422  # too short for the validator


# --------------------------------------------------------------------------- webhook


def test_the_webhook_is_unavailable_without_a_configured_secret(client):
    response = client.post("/api/webhooks/payments", content="{}")
    assert response.status_code == 503


def test_an_unsigned_webhook_is_rejected(client, monkeypatch):
    import dataclasses

    monkeypatch.setattr(
        api, "_settings",
        dataclasses.replace(api._settings, stripe_webhook_secret="whsec_test_x"),
    )
    response = client.post(
        "/api/webhooks/payments",
        content=json.dumps({"id": "evt_1", "type": "x", "data": {"object": {"id": "pi_1"}}}),
        headers={"stripe-signature": "t=1,v1=nope"},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- reset


def test_reset_returns_a_workspace_to_its_starting_state(client):
    client = _showcase(client)
    assert client.get("/api/state").json()["pools"]
    counts = client.post("/api/demo/reset").json()
    assert counts["reset"] is True
    assert counts["seeded"]["members"] > 0
    assert client.get("/api/state").json()["pools"] == []


def test_needs_expose_both_timing_numbers(client):
    _seed(client)
    needs = client.get("/api/needs").json()["needs"]
    assert needs
    sample = needs[0]
    assert "flexibility_days" in sample and "routine_lead_days" in sample
    assert sample["earliest_purchase_date"] <= sample["latest_purchase_date"]


def test_state_reports_the_communitys_own_schedule(client):
    body = _seed(client)
    schedule = body["community"]["schedule"]
    assert schedule["distribution_weekday"] == 5
    assert schedule["distribution_start_hour"] < schedule["distribution_end_hour"]


def test_pool_status_values_are_canonical(client):
    client = _showcase(client)
    statuses = {p["status"] for p in client.get("/api/state").json()["pools"]}
    assert statuses <= {s.value for s in PoolStatus}
    assert client.get("/api/state").json()["community"]["id"] == COMMUNITY_ID


def test_a_refused_lifecycle_move_is_a_conflict_not_a_server_error(client):
    """`assert_transition` raises `IllegalTransition`, which is a `ValueError`.

    Routes that did not name it explicitly turned a correct refusal into a 500 — and
    `open-distribution` is a *public* route, so a judge clicking it twice on a finished
    pool got one. Handled once at the app level so no route can miss it.
    """
    client = _showcase(client)
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]
    assert client.get(f"/api/pools/{pool_id}").json()["status"] == "completed"

    response = client.post(f"/api/pools/{pool_id}/open-distribution")

    assert response.status_code in {400, 409}, response.text
    assert "detail" in response.json()


def test_no_lifecycle_refusal_anywhere_returns_a_500(client):
    """The general property, not just the one route that exposed it."""
    client = _showcase(client)
    pool_id = client.get("/api/state").json()["pools"][0]["pool_id"]

    for path in (
        f"/api/pools/{pool_id}/open-distribution",
        f"/api/pools/{pool_id}/lock",
        f"/api/pools/{pool_id}/purchase",
    ):
        assert client.post(path).status_code < 500, path
