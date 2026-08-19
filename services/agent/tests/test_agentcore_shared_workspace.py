"""The deployed agent and the browser, on one workspace.

The public demo used to be two disconnected halves. The browser drove a DynamoDB-backed
session; the live action ran the deployed coordinator against a throwaway workspace
inside the AgentCore microVM. Both were real, and the second could never be the product,
because the pool it formed was invisible to the person who pressed the button.

The runtime now reads and writes the *same table and the same partition* the API serves.
That is a strictly larger blast radius, so this file is written from the position that it
must be earned: every test here is either a security boundary, a concurrency hazard, or
the specific claim that the state a visitor sees was produced by the deployed agent
rather than copied from its answer.

**How the topology is reproduced.** Two ``DynamoDBRepository`` instances over one
``FakeDynamoTable`` — one standing in for the Lambda, one for the runtime container —
because that is exactly what the deployment is. The runtime side calls the *real*
``agentcore_app.invoke``, so its payload validation, its refusal to seed a shared
workspace, and its use of the same ``PoolCoordinator`` the API drives are all under test
rather than restated here. The fake boto3 client is only the wire.

Runs entirely offline and free: deterministic planner, simulated payments, no AWS call
and no model token (AGENTS.md §3.6).
"""

from __future__ import annotations

import importlib
import json
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from pool.adapters.repository import DynamoDBRepository
from pool.agent.coordinator import PoolCoordinator
from pool.agent.offline_model import DeterministicPlannerModel, _tool_event
from pool.api import public_demo
from pool.config import AgentBounds, Settings
from pool.data.seed import seed
from tests.test_public_demo import ARN, FakeDynamoTable

WS = "wjudge0000001"
OTHER_WS = "wjudge0000002"
TABLE = "pool-demo-state"

RUNTIME_SETTINGS = Settings(
    model_provider="offline",
    repository="dynamodb",
    routing_provider="deterministic",
    payment_provider="simulated",
    purchase_executor="simulated",
    bounds=AgentBounds(),
)


# --------------------------------------------------------------------------- the wire


class RuntimeClient:
    """A ``bedrock-agentcore`` client that runs the real entrypoint in-process.

    Everything a caller can observe about the deployed runtime goes through here: the
    payload is serialised and re-parsed exactly as it would be over the wire, and the
    response is whatever ``agentcore_app.invoke`` actually returns. What it cannot
    reproduce is latency, IAM, and cold start — so no test in this file asserts anything
    about those.
    """

    def __init__(self, invoke, fail_after: bool = False) -> None:
        self._invoke = invoke
        #: Raise *after* the run has completed and written, which is what an invocation
        #: that times out on a slow-but-successful agent looks like from the Lambda.
        self.fail_after = fail_after
        self.calls: list[dict] = []

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        result = self._invoke(json.loads(kwargs["payload"]))
        if self.fail_after:
            raise RuntimeError("ReadTimeoutError")
        return {
            "statusCode": 200,
            "traceId": "1-abc-def",
            "response": json.dumps(result).encode(),
        }


class Deployment:
    """Both halves, and the one table underneath them."""

    def __init__(self, api_module, table: FakeDynamoTable, client: RuntimeClient) -> None:
        self.api = api_module
        self.table = table
        self.client = client
        self.http = TestClient(api_module.app)

    @property
    def guard(self):
        return self.api._public

    def get(self, path: str, ws: str = WS):
        return self.http.get(self._url(path, ws))

    def post(self, path: str, ws: str = WS, **kwargs):
        return self.http.post(self._url(path, ws), **kwargs)

    @staticmethod
    def _url(path: str, ws: str) -> str:
        # Percent-encoded, so a workspace containing `#`, `&`, or a space is *sent*
        # rather than silently truncated into something harmless by the client. A test
        # that cannot transmit its own hostile input proves nothing about the server.
        sep = "&" if "?" in path else "?"
        return f"{path}{sep}workspace={quote(ws, safe='')}"

    def live(self, ws: str = WS, action: str = "community"):
        """Invoke the deployed runtime.

        ``community`` by default because this file is about the runtime/store boundary
        rather than about whose question a run answers: a community scan needs no
        declaration to exist first, so every test here stays about the thing it names.
        The member-anchored action has its own tests below.
        """
        return self.post(f"/api/demo/agentcore?action={action}", ws=ws)

    def state(self, ws: str = WS) -> dict:
        return self.get("/api/state", ws=ws).json()

    def pools(self, ws: str = WS) -> list[dict]:
        return self.state(ws)["pools"]

    def sent_workspaces(self) -> list[str]:
        return [json.loads(c["payload"])["workspace"] for c in self.client.calls]


@pytest.fixture
def public_api(monkeypatch):
    """The API module under the deployed configuration. Same fixture shape as
    ``test_public_demo.py``: the module builds its guard at import time, so the honest
    way to test judge mode is to import it under judge mode."""
    monkeypatch.setenv("POOL_PUBLIC_DEMO", "true")
    monkeypatch.delenv("PUBLIC_DEMO_WEB_ROOT", raising=False)
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE", raising=False)
    from pool.api import app as api

    module = importlib.reload(api)
    yield module
    monkeypatch.undo()
    importlib.reload(api)


@pytest.fixture
def deployment(public_api, monkeypatch, request) -> Deployment:
    """Wire the Lambda half and the runtime half onto one table.

    The two repository objects are deliberately distinct instances. Sharing one would
    make the test pass for a reason the deployment does not have — a process-local cache
    is not a shared table — and would hide exactly the class of bug this whole change
    introduces.
    """
    import agentcore_app

    table = FakeDynamoTable()
    api_repo = DynamoDBRepository(TABLE, table=table)
    runtime_repo = DynamoDBRepository(TABLE, table=table)

    planner = getattr(request, "param", None)
    coordinator = PoolCoordinator(runtime_repo, settings=RUNTIME_SETTINGS, model=planner)
    monkeypatch.setattr(agentcore_app, "_repo", runtime_repo)
    monkeypatch.setattr(agentcore_app, "_coordinator", coordinator)
    monkeypatch.setattr(agentcore_app, "_shared_store", True)

    client = RuntimeClient(agentcore_app.invoke)
    guard = public_api._public
    guard.settings = type(guard.settings)(**{**vars(guard.settings), "agentcore_runtime_arn": ARN})
    guard._bridge = public_demo.AgentCoreBridge(ARN, "us-east-1", client=client)
    guard.quota = public_demo.InMemoryQuotaStore()
    guard.lease = public_demo.InMemoryLeaseStore()
    monkeypatch.setattr(public_api, "_repo", api_repo)

    return Deployment(public_api, table, client)


# ------------------------------------------------------ the same run, both sides


def test_the_member_action_reaches_the_runtime_as_a_member_trigger(deployment):
    """The consumer's own button, over the wire.

    The payload is a workspace and a trigger name and nothing else — no household, no
    prompt, no community id. Whose declarations the run is about is resolved *inside*
    the runtime, from the workspace it was given, so there is no field in which a
    caller could point it at somebody else.
    """
    deployment.get("/api/state")
    _declare_for_the_visitor(deployment)

    body = deployment.live(action="member").json()
    assert body["ok"] is True

    payload = json.loads(deployment.client.calls[-1]["payload"])
    assert payload == {"workspace": WS, "trigger": "member_scan"}
    assert set(payload) == {"workspace", "trigger"}


def test_an_unknown_live_action_never_reaches_aws(deployment):
    """A key from the server's own map, never an objective."""
    deployment.get("/api/state")
    response = deployment.post("/api/demo/agentcore?action=whatever", ws=WS)
    assert response.status_code == 400
    assert deployment.client.calls == []


def test_what_the_deployed_run_established_is_readable_from_the_other_side(deployment):
    """The reason evaluation evidence is a stored row rather than an in-process object.

    The runtime computed these facts inside a process the API cannot reach — in the
    deployment that process is a microVM that no longer exists by the time anybody asks.
    The Lambda's own repository reads them back, and builds the member's report from
    them, which is the only path the two halves share.
    """
    deployment.get("/api/state")
    household = _declare_for_the_visitor(deployment)

    body = deployment.live(action="member").json()
    run_id = body["run"]["run_id"]

    # Read through the *API's* repository object, not the runtime's.
    stored = deployment.api._repo.list_run_evaluations(WS, run_id)
    assert stored, "the deployed run recorded nothing the browser could be shown"
    assert {e.run_id for e in stored} == {run_id}

    report = deployment.get(
        f"/api/runs/{run_id}/report?household_id={household}", ws=WS
    ).json()
    assert report["is_mine"] is True
    assert report["results"], "the member has no answer to the button they pressed"
    assert report["evaluated_product_ids"]
    # Every product named is one this run actually evaluated.
    named = {r["product_id"] for r in report["results"] if r["result"] != "not_investigated"}
    assert named <= set(report["evaluated_product_ids"])


def _declare_for_the_visitor(deployment) -> str:
    """Onboard and declare through the public endpoints, as a visitor would."""
    from datetime import date, timedelta

    deployment.post(
        "/api/onboarding", ws=WS,
        json={"display_name": "Marco", "autonomy_mode": "smart_join"},
    )
    deployment.post("/api/onboarding/payment-method", ws=WS)
    household = deployment.state()["consumer"]["household_id"]
    due = date.today() + timedelta(days=12)
    response = deployment.post(
        "/api/needs", ws=WS,
        json={
            "household_id": household,
            "product_id": "prod_whey_vanilla",
            "quantity": 2,
            "cadence_days": 40,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": 11,
            "routine_lead_days": 11,
            "min_savings_pct": 20,
            "max_spend_cents": 9000,
            "substitution": "exact_only",
        },
    )
    assert response.status_code == 200, response.text
    return household


# --------------------------------------------------------------- the central claim


def test_the_pool_the_browser_sees_was_created_by_the_deployed_run(deployment):
    """The whole reason this path exists.

    Not "a pool exists afterwards" — the demo could produce that by running the
    coordinator locally and would have proved nothing. The pool's ``created_by_run`` is
    stamped by the coordinator with its own run id, and that run id is the one the
    runtime reported back through the invocation. So the row the browser renders was
    written by the process on the other side of the wire.
    """
    deployment.get("/api/state")  # seeds this session, as any read does
    assert deployment.pools() == []

    body = deployment.live().json()
    assert body["ok"] is True and body["live"] is True
    run_id = body["run"]["run_id"]

    pools = deployment.pools()
    assert len(pools) == 1, pools
    stored = deployment.api._repo.get_pool(WS, pools[0]["pool_id"])
    assert stored.created_by_run == run_id
    rendered = pools[0]
    assert rendered["created_by_run"] == run_id
    assert rendered["execution_proof"] == {
        "pool_id": rendered["pool_id"],
        "created_by_run": run_id,
        "run_id": run_id,
        "relation_verified": True,
        "execution": {
            "service": "Amazon Bedrock AgentCore Runtime",
            "live": True,
            "region": "us-east-1",
        },
        "workspace_readback": {
            "run_recorded": True,
            "pool_recorded": True,
            "same_workspace": True,
        },
        "run": rendered["execution_proof"]["run"],
    }
    assert rendered["execution_proof"]["run"]["tool_calls"] == [
        call["name"] for call in body["run"]["tool_calls"]
    ]
    assert body["observed"]["created_pool_ids"] == [rendered["pool_id"]]
    assert body["observed"]["run_pool_links_verified"] is True


def test_the_agents_own_run_record_is_readable_in_the_session_it_ran_on(deployment):
    """Two independent confirmations that the halves share one partition: the server's
    read-back at invocation time, and the run turning up in the session's own audit
    trail on the next page load."""
    deployment.get("/api/state")
    body = deployment.live().json()

    assert body["observed"]["run_recorded"] is True
    assert body["observed"]["pools"] == 1
    assert [r["run_id"] for r in deployment.state()["runs"]] == [body["run"]["run_id"]]


def test_the_response_describes_the_store_not_the_models_answer(deployment):
    """``observed`` is computed by reading the table after the run, so it disagrees with
    the runtime's own summary whenever the two disagree — which is the point of having
    it. Here it is checked against a third source: the repository, queried directly."""
    deployment.get("/api/state")
    body = deployment.live().json()

    repo = deployment.api._repo
    assert body["observed"]["pools"] == len(repo.list_pools(WS))
    assert body["observed"]["pending_decisions"] == sum(
        1 for d in repo.list_decisions(WS) if d.state.value == "pending"
    )


# --------------------------------------------------------------------- two sessions


def test_two_visitors_get_two_workspaces_and_the_agent_stays_inside_each(deployment):
    """The isolation property, asserted after the agent has run in both.

    A shared table plus an agent that writes to it is precisely the arrangement where
    isolation stops being a property of the read path and starts depending on what the
    writer was told. So: run in both, then check that neither session can see the
    other's pool and that each invocation named only its own partition.
    """
    deployment.get("/api/state", ws=WS)
    deployment.get("/api/state", ws=OTHER_WS)
    deployment.live(ws=WS)
    deployment.live(ws=OTHER_WS)

    mine = deployment.pools(WS)
    theirs = deployment.pools(OTHER_WS)
    assert len(mine) == 1 and len(theirs) == 1
    assert {p["pool_id"] for p in mine}.isdisjoint({p["pool_id"] for p in theirs})
    assert mine[0]["execution_proof"]["run_id"] != theirs[0]["execution_proof"]["run_id"]
    assert mine[0]["execution_proof"]["pool_id"] == mine[0]["pool_id"]
    assert theirs[0]["execution_proof"]["pool_id"] == theirs[0]["pool_id"]
    assert deployment.sent_workspaces() == [WS, OTHER_WS]

    # And the partitions really are separate rows, not a filter applied on the way out.
    assert {key[0].split("#", 1)[0] for key in deployment.table.items} >= {WS, OTHER_WS}


def test_a_session_cannot_aim_the_agent_at_another_session(deployment):
    """The payload workspace is the *validated* one, always.

    There is no field to smuggle a second workspace through — the endpoint takes no body
    — so the attack surface is the query parameter, and the query parameter is the thing
    the guard checked. This pins the equality rather than the absence.
    """
    deployment.get("/api/state", ws=WS)
    deployment.get("/api/state", ws=OTHER_WS)

    # A body naming someone else's workspace is not a field the endpoint has.
    deployment.post("/api/demo/agentcore", ws=WS, json={"workspace": OTHER_WS})
    assert deployment.sent_workspaces() == [WS]
    assert deployment.pools(OTHER_WS) == [], "the other session must be untouched"


@pytest.mark.parametrize(
    "forged", ["primary", "demo", "../etc", "wjudge0000001#POOL", "_quota", "_lease#agentcore"]
)
def test_a_forged_workspace_never_reaches_the_runtime(deployment, forged):
    """Including the two internal partitions. Quota and lease rows live in this same
    table under keys beginning ``_``, which ``PUBLIC_WORKSPACE_RE`` cannot match — so a
    caller cannot point the agent at the counters that are rationing it."""
    assert deployment.live(ws=forged).status_code == 400
    assert deployment.client.calls == []


def test_the_runtime_refuses_a_workspace_that_does_not_exist(deployment):
    """A fabricated-but-well-formed session id is not an error at the door — it is a
    workspace nobody has opened. The runtime will not bootstrap one on a shared store,
    because seeding starts by deleting the partition, and a stale invocation carrying a
    workspace that has since been reset must never be able to empty it.
    """
    unopened = "wnobodyhasthis01"
    body = deployment.live(ws=unopened).json()

    assert body["ok"] is False
    assert "refused this request" in body["reason"]
    assert "does not create" in body["reason"]
    assert deployment.table.items == {}, "a refused run must write nothing at all"


def test_a_refusal_is_reported_as_an_answer_not_as_a_lost_call(deployment):
    """The two failure branches say different things because they *are* different, and
    the difference is one a visitor can act on.

    A refusal means the runtime validated the payload and declined before running: no
    write can exist, so there is nothing to re-read and the workspace is handed straight
    back. Conflating it with a lost call would warn about work that never started and
    hold the session for two minutes to protect it.
    """
    unopened = "wnobodyhasthis01"
    body = deployment.live(ws=unopened).json()

    assert body["classification"] == public_demo.LIVE_CLASS_SAFE_REFUSAL
    assert body["remote_may_still_write"] is False
    assert body["allow_local_fallback"] is True
    assert body["refresh_state"] is False, "there is nothing to re-read"
    assert "may still have finished" not in body["reason"]
    # And the workspace is free immediately.
    assert deployment.guard.lease.acquire(unopened, 60) is True
    deployment.guard.release_workspace(unopened)


def test_the_runtime_cannot_be_asked_to_do_anything_but_coordinate(deployment):
    """Straight at the entrypoint, past the bridge: the payload contract is a closed
    set. A trigger outside the allowlist and a malformed workspace are both refusals,
    and neither returns something a caller could mistake for a run."""
    import agentcore_app

    for payload in [
        {"workspace": WS, "trigger": "drop_everything"},
        {"workspace": "../../etc", "trigger": "manual"},
        {"workspace": "WJUDGE0000001", "trigger": "manual"},
    ]:
        result = agentcore_app.invoke(payload)
        assert "error" in result and "run_id" not in result, payload


# ------------------------------------------------------------------- fabricated ids


class HallucinatingPlanner(DeterministicPlannerModel):
    """Opens with the invented pool id a real Bedrock run once produced (#0021)."""

    def _decide(self, view):
        if not view.calls:
            return _tool_event("recover_pool", {"pool_id": "short_of_demand_pool"})
        return super()._decide(view)


@pytest.mark.parametrize("deployment", [HallucinatingPlanner()], indirect=True)
def test_an_invented_pool_id_changes_nothing_in_the_shared_table(deployment):
    """The domain guard, re-asserted where it now matters more.

    ``_require_pool`` refused invented identifiers before this change too, but it was
    refusing them against a store that died with the microVM. It is now the thing
    standing between a model's invented string and a visitor's live session, so the
    assertion is about the table: the refusal is reported, and the row count is
    unchanged by it.
    """
    deployment.get("/api/state")
    before = dict(deployment.table.items)

    body = deployment.live().json()
    refused = [c for c in body["run"]["tool_calls"] if not c["ok"]]
    assert [c["name"] for c in refused] == ["recover_pool"]
    assert "unknown pool" in refused[0]["summary"]

    # Everything that changed, changed because a *legitimate* later call changed it.
    invented = [k for k in deployment.table.items if "short_of_demand_pool" in k[1]]
    assert invented == []
    assert set(before) <= set(deployment.table.items)


# ------------------------------------------------------------ duplicates and races


def test_a_second_invocation_cannot_start_while_one_is_running(deployment):
    """The concurrency hazard the lease exists for.

    Pool formation is idempotent on ``community:product:site:day``, but that idempotency
    is a read followed by a write: two runs that both find no matching pool will both
    create one. Reproduced by invoking from inside the runtime's own call, which is the
    same interleaving as two Lambda containers holding two tabs.
    """
    deployment.get("/api/state")
    inner: list[dict] = []
    original = deployment.client._invoke

    def reentrant(payload):
        inner.append(deployment.live().json())
        return original(payload)

    deployment.client._invoke = reentrant
    outer = deployment.live().json()

    assert outer["ok"] is True
    assert inner[0]["ok"] is False and "already working" in inner[0]["reason"]
    assert inner[0]["classification"] == public_demo.LIVE_CLASS_WORKSPACE_BUSY
    assert inner[0]["allow_local_fallback"] is False
    assert len(deployment.client.calls) == 1, "the refused run must not reach AWS"
    assert len(deployment.pools()) == 1


def test_a_repeated_invocation_does_not_produce_a_second_pool(deployment):
    """Sequential duplicates are allowed — a judge may press it again — and the domain's
    own idempotency key is what makes that safe. Agent systems retry; a coordinator that
    formed a second *identical* pool on the second press would be one.

    "Identical" is the claim, not "only one pool exists". A community scan that finds
    the next unserved opportunity on its second pass is the coordinator working: the
    Community really does hold more than one, and refusing to see the second would be a
    worse bug than seeing it twice. So the invariant is per product, per site, per
    distribution day — which is exactly the idempotency key the domain keeps.
    """
    deployment.get("/api/state")
    first = deployment.live().json()
    second = deployment.live().json()

    assert (first["ok"], second["ok"]) == (True, True)
    assert first["run"]["run_id"] != second["run"]["run_id"], "two real runs happened"
    pools = deployment.pools()
    keys = [(p["product_id"], p["pickup_site"]) for p in pools]
    assert len(keys) == len(set(keys)), [p["product_name"] for p in pools]
    # Both runs are on the record. Idempotent does not mean invisible.
    assert len(deployment.state()["runs"]) == 2


def test_reset_will_not_run_while_the_agent_is_mid_flight(deployment):
    """``seed()`` opens with a full-partition delete. Landing that between a pool being
    written and its members being written leaves a session that is internally broken
    without looking broken — so reset waits rather than racing."""
    deployment.get("/api/state")
    attempted: list[int] = []
    original = deployment.client._invoke

    def reentrant(payload):
        attempted.append(deployment.post("/api/demo/reset").status_code)
        return original(payload)

    deployment.client._invoke = reentrant
    deployment.live()

    assert attempted == [409]
    assert len(deployment.pools()) == 1, "the run that was protected still completed"


def test_reset_holds_the_lease_through_reseed_and_blocks_a_live_start(deployment, monkeypatch):
    """The old reset path released its check before ``seed()`` began.

    Calling the live endpoint from inside the destructive seed is the exact old
    interleaving: if reset has stepped out, the nested invocation acquires the same
    workspace and reaches the runtime while rows are being deleted and recreated. The
    lease now remains held until the whole reset returns, so the nested run is refused
    before it can spend quota or call AgentCore.
    """
    deployment.get("/api/state")
    original_seed = deployment.api.seed
    attempted: list[dict] = []

    def seed_while_resetting(repo, workspace):
        assert deployment.guard.lease.acquire(workspace, 60) is False
        attempted.append(deployment.live(ws=workspace).json())
        return original_seed(repo, workspace)

    monkeypatch.setattr(deployment.api, "seed", seed_while_resetting)
    response = deployment.post("/api/demo/reset")

    assert response.status_code == 200
    assert attempted and attempted[0]["ok"] is False
    assert attempted[0]["classification"] == public_demo.LIVE_CLASS_WORKSPACE_BUSY
    assert attempted[0]["allow_local_fallback"] is False
    assert deployment.client.calls == [], "the live attempt must not reach AgentCore"
    assert deployment.pools() == []


def test_reset_releases_the_workspace_lease_when_reseed_fails(deployment, monkeypatch):
    """A failed destructive reset must not leave the session permanently wedged."""
    deployment.get("/api/state")

    def fail_seed(_repo, _workspace):
        raise RuntimeError("seed failed")

    monkeypatch.setattr(deployment.api, "seed", fail_seed)
    with pytest.raises(RuntimeError, match="seed failed"):
        deployment.post("/api/demo/reset")

    assert deployment.guard.lease.acquire(WS, 60) is True
    deployment.guard.release_workspace(WS)


def test_reset_works_again_as_soon_as_the_run_is_over(deployment):
    """The lease is released on a clean return, so the protection above lasts exactly as
    long as it needs to and not one action longer."""
    deployment.get("/api/state")
    deployment.live()
    assert deployment.post("/api/demo/reset").status_code == 200
    assert deployment.pools() == []


def test_a_run_after_a_reset_works_on_the_reseeded_session(deployment):
    """Reset then discover, in the order a judge starting over would do it. The second
    run must form a pool in the *new* dataset rather than tripping over the old one's
    idempotency key, and no pool from before the reset may survive."""
    deployment.get("/api/state")
    first = deployment.live().json()
    deployment.post("/api/demo/reset")
    second = deployment.live().json()

    pools = deployment.pools()
    assert len(pools) == 1
    assert deployment.api._repo.get_pool(WS, pools[0]["pool_id"]).created_by_run == (
        second["run"]["run_id"]
    )
    assert [r["run_id"] for r in deployment.state()["runs"]] == [second["run"]["run_id"]]
    assert first["run"]["run_id"] != second["run"]["run_id"]


# ------------------------------------------------------------------------ failures


def test_a_timeout_after_the_work_landed_reports_honestly(deployment):
    """The failure mode that only exists once the state is shared.

    Before, an invocation that died on the way home cost nothing: the runtime's work was
    in a microVM nobody would look at. Now the writes are in the visitor's session, so
    "the call failed" and "nothing happened" have come apart. The endpoint must not
    conflate them — it says the agent did not answer, tells the client to re-read, and
    the re-read shows the pool that genuinely exists.
    """
    deployment.get("/api/state")
    deployment.client.fail_after = True

    body = deployment.live().json()
    assert body["ok"] is False and body["live"] is False
    assert body["classification"] == public_demo.LIVE_CLASS_AMBIGUOUS
    assert body["remote_may_still_write"] is True
    assert body["allow_local_fallback"] is False
    assert body["refresh_state"] is True
    assert "run" not in body, "a failed invocation must never present a run"

    pools = deployment.pools()
    assert len(pools) == 1, "the agent's work is in the table and must be shown"
    assert deployment.api._repo.get_pool(WS, pools[0]["pool_id"]).created_by_run


def test_a_failed_invocation_keeps_the_workspace_held(deployment):
    """From this side a timeout is indistinguishable from a crash, and in the timeout
    case the runtime is probably still writing. Holding the lease until it expires
    refuses the next run for a minute; releasing it lets a second agent into a partition
    the first is still mutating."""
    deployment.get("/api/state")
    deployment.client.fail_after = True
    body = deployment.live().json()

    assert body["classification"] == public_demo.LIVE_CLASS_AMBIGUOUS
    assert body["refresh_state"] is True
    assert body["allow_local_fallback"] is False

    deployment.client.fail_after = False
    blocked = deployment.live().json()
    assert "already working" in blocked["reason"]
    assert blocked["classification"] == public_demo.LIVE_CLASS_WORKSPACE_BUSY
    assert blocked["allow_local_fallback"] is False
    assert deployment.post("/api/demo/reset").status_code == 409

    # And it is a lease, not a lock: it lets go on its own.
    deployment.guard.lease.release(WS)
    assert deployment.live().json()["ok"] is True


def test_an_invocation_that_never_started_leaves_the_session_exactly_as_it_was(deployment):
    """AWS refusing — throttling, a bad ARN, expired credentials — must not show up as a
    changed demo. The state after is the state before, byte for byte."""
    deployment.get("/api/state")

    def refuse(_payload):
        raise RuntimeError("AccessDeniedException")

    deployment.client._invoke = refuse
    before = dict(deployment.table.items)
    body = deployment.live().json()

    assert body["ok"] is False and "run" not in body
    assert deployment.table.items == before
    assert deployment.pools() == []


def test_a_timed_out_invocation_is_never_retried_underneath_us():
    """The lease serialises *callers*. A retry issued inside botocore is not a caller.

    ``AgentCoreBridge`` asks for a single attempt so a live action that read-times-out
    stays one agent run. Botocore's two spellings of that are not synonyms: it treats
    ``max_attempts`` as the legacy shorthand and resolves it to ``max_attempts + 1``, so
    ``{"max_attempts": 1}`` silently buys a retry. Observed on the deployed stack
    (#0030) — one live action, two runs 17 ms apart, both coordinating the same
    workspace, neither of which passed :class:`DynamoDBLeaseStore` because the second
    was issued below the code that takes the lease.

    Asserted on the *resolved* client config rather than on the literal we passed in,
    because the literal is exactly what was wrong.
    """
    bridge = public_demo.AgentCoreBridge(runtime_arn=ARN, region="us-east-1")
    retries = bridge.client.meta.config.retries

    assert retries["total_max_attempts"] == 1, (
        f"one live action must be one agent run; resolved config asks for "
        f"{retries['total_max_attempts']} attempts"
    )
    assert bridge.client.meta.config.read_timeout == public_demo.LIVE_READ_TIMEOUT_SECONDS


# -------------------------------------------------------------------------- quotas


def test_the_paid_cap_still_bounds_the_shared_path(deployment):
    """Binding the agent to real state does not buy it a larger budget. The cap is the
    same one, checked in the same place, and a refusal costs nothing at Bedrock."""
    guard = deployment.guard
    guard.settings = type(guard.settings)(
        **{**vars(guard.settings), "agentcore_runtime_arn": ARN, "max_live_per_session": 2}
    )
    deployment.get("/api/state")

    assert deployment.live().json()["ok"] is True
    assert deployment.live().json()["ok"] is True
    assert deployment.live().status_code == 429
    assert len(deployment.client.calls) == 2, "a refused run must not reach AWS"
    pools = deployment.pools()
    # Two permitted scans, two distinct opportunities, no duplicate of either. The cap
    # bounds how many *runs* are paid for, not how much the community turns out to hold.
    keys = [(p["product_id"], p["pickup_site"]) for p in pools]
    assert len(keys) == len(set(keys)) and len(keys) <= 2


def test_a_run_refused_by_the_cap_hands_the_workspace_straight_back(deployment):
    """The lease is taken before the quota is spent, so the loser of a race does not also
    lose one of its paid runs. That ordering is only safe if the refusal path releases —
    otherwise a visitor who hits their cap would find the session wedged as well."""
    guard = deployment.guard
    guard.settings = type(guard.settings)(
        **{**vars(guard.settings), "agentcore_runtime_arn": ARN, "max_live_per_session": 0}
    )
    deployment.get("/api/state")

    assert deployment.live().status_code == 429
    assert deployment.client.calls == []
    # Nothing else in the session is blocked by a run that never happened.
    assert deployment.post("/api/demo/reset").status_code == 200
    assert deployment.post("/api/agent/run", json={"trigger": "manual_scan"}).status_code == 200


def test_the_kill_switch_stops_the_shared_path_without_taking_a_lease(deployment):
    guard = deployment.guard
    guard.settings = type(guard.settings)(
        **{**vars(guard.settings), "agentcore_runtime_arn": ARN, "agentcore_enabled": False}
    )
    deployment.get("/api/state")

    assert deployment.live().json()["ok"] is False
    assert deployment.client.calls == []
    assert deployment.post("/api/demo/reset").status_code == 200


# ------------------------------------------------------------- the runtime's remit


def test_the_runtime_holds_no_permission_it_does_not_use(deployment):
    """The IAM grant is three actions; this asserts the code needs no more than three.

    ``GetItem``, ``PutItem`` and ``Query`` are what the runtime's execution role is given
    (``services/agent/iam/agentcore-dynamodb.json``). A delete reaching the table would
    fail on the deployed role, and would fail *after* partially emptying a visitor's
    session — so it is worth catching here, where the fake counts every operation.
    """
    deployment.get("/api/state")
    deployment.table.ops.clear()
    deployment.live()

    assert deployment.table.ops.get("delete_item", 0) == 0
    assert deployment.table.ops.get("update_item", 0) == 0
    assert set(deployment.table.ops) <= {"get_item", "put_item", "query"}
    assert deployment.table.ops.get("put_item", 0) > 0, "the run is supposed to write"


def test_the_runtime_refuses_to_seed_a_store_it_shares(deployment):
    """Directly at the entrypoint. ``seed()`` calls ``repo.reset()`` first, which deletes
    every row in the partition — the single most destructive thing in the codebase, and
    the reason the execution role has no delete permission at all."""
    import agentcore_app

    result = agentcore_app.invoke({"workspace": "wneveropened01", "trigger": "manual"})

    assert "error" in result
    assert deployment.table.items == {}


def test_the_runtime_still_seeds_its_own_private_store(monkeypatch):
    """The refusal is scoped to a shared store, not baked in: a runtime holding its own
    in-memory copy — a scheduled scan, a smoke test — still bootstraps itself."""
    import agentcore_app
    from pool.adapters.repository import InMemoryRepository

    repo = InMemoryRepository()
    monkeypatch.setattr(agentcore_app, "_repo", repo)
    monkeypatch.setattr(
        agentcore_app,
        "_coordinator",
        PoolCoordinator(repo, settings=Settings(model_provider="offline", repository="memory")),
    )
    monkeypatch.setattr(agentcore_app, "_shared_store", False)

    result = agentcore_app.invoke({"workspace": "wprivate000001", "trigger": "manual"})
    assert "error" not in result
    assert repo.list_communities("wprivate000001")


# ---------------------------------------------------------------- the local fallback


def test_the_free_local_path_still_works_on_the_same_workspace(deployment):
    """Two agents, one partition: the deployed coordinator and the one running in this
    process. They are the same class over the same repository protocol, so a lifecycle
    that starts on AWS can be advanced here — which is what the product does, and what
    keeps every action after discovery free (AGENTS.md §3.3)."""
    deployment.get("/api/state")
    live = deployment.live().json()
    pool_id = deployment.pools()[0]["pool_id"]

    advanced = deployment.post("/api/agent/run", json={"trigger": "manual_advance"}).json()
    assert advanced["model_provider"] == "offline"
    assert live["run"]["model_provider"] == "offline"  # the planner stands in for Bedrock here

    after = deployment.pools()
    assert len(after) == 1 and after[0]["pool_id"] == pool_id
    assert after[0]["status"] != "forming", "the local run moved the deployed run's pool on"


def test_both_halves_read_the_same_rows_not_two_caches(deployment):
    """The fixture's whole fidelity claim, asserted rather than assumed: a write made
    through one repository object is visible through the other."""
    import agentcore_app

    seed(deployment.api._repo, WS)
    assert agentcore_app._repo.list_communities(WS), "the runtime must see the API's seed"
    assert agentcore_app._repo is not deployment.api._repo
