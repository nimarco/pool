"""Two coordinators must never mutate one workspace at the same time.

The demo's authoritative store is written from more than one place: the public Lambda
seeds and resets it, a local coordinator run writes it, the showcase reseeds and drives
the whole lifecycle through it, and the deployed AgentCore runtime writes it from an
entirely different compute environment. Any two of those overlapping produces state that
is wrong without looking broken — a reset deleting rows a run is still writing, two
first-load seeds each starting with a partition-wide delete, two runs both finding "no
pool exists" and both creating one.

The protection is one lease per workspace, taken by every mutating path. These tests
exercise it the way it actually fails: through the API, and — where the point is that
in-process state would not have caught it — through *two* repository or store instances,
so nothing here can pass merely because one Python object happened to be shared.
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.api import public_demo
from pool.data.seed import COMMUNITY_ID, seed
from tests.conftest import WS
from tests.test_public_demo import FakeDynamoTable, FakeRuntime, _with_live

WS_A = "wconcurrencya"
WS_B = "wconcurrencyb"


@pytest.fixture
def api(monkeypatch):
    """The public app, on an in-memory store, with a real lease store behind it."""
    monkeypatch.setenv("POOL_PUBLIC_DEMO", "true")
    monkeypatch.setenv("DYNAMODB_TABLE", "")
    from pool.config import reset_settings

    reset_settings()
    import importlib

    from pool.api import app as app_module

    importlib.reload(app_module)
    yield app_module
    reset_settings()


@pytest.fixture
def client(api):
    return TestClient(api.app)


def _guard() -> public_demo.PublicDemoGuard:
    """A guard wired to a real in-process lease, standing in for one Lambda container."""
    return public_demo.PublicDemoGuard(
        settings=public_demo.PublicDemoSettings(enabled=True),
        quota=public_demo.InMemoryQuotaStore(),
        lease=public_demo.InMemoryLeaseStore(),
    )


def _two_containers() -> tuple[public_demo.PublicDemoGuard, public_demo.PublicDemoGuard]:
    """Two guards sharing one lease store — two Lambda containers, one DynamoDB table.

    Separate guard objects on purpose: a test that used one guard twice would prove only
    that a single process does not deadlock against itself.
    """
    shared = public_demo.InMemoryLeaseStore()
    settings = public_demo.PublicDemoSettings(enabled=True)
    return (
        public_demo.PublicDemoGuard(
            settings=settings, quota=public_demo.InMemoryQuotaStore(), lease=shared
        ),
        public_demo.PublicDemoGuard(
            settings=settings, quota=public_demo.InMemoryQuotaStore(), lease=shared
        ),
    )


# ------------------------------------------------------------- the lease itself


def test_two_containers_cannot_hold_one_workspace(monkeypatch):
    """The exclusion has to survive being in two processes, which is where it matters."""
    first, second = _two_containers()
    assert first.hold_workspace(WS_A) is True
    assert second.hold_workspace(WS_A) is False
    first.release_workspace(WS_A)
    assert second.hold_workspace(WS_A) is True


def test_unrelated_workspaces_never_contend():
    """Two judges in two sessions are two rows. A global lock would be a bug, not a fix."""
    first, second = _two_containers()
    assert first.hold_workspace(WS_A) is True
    assert second.hold_workspace(WS_B) is True
    first.release_workspace(WS_A)
    assert second.hold_workspace(WS_A) is True


def test_a_stale_lease_expires_so_a_dead_holder_cannot_wedge_a_session():
    """The holder is a Lambda that can be killed mid-flight; the lease must outlive it
    but not forever."""
    first, second = _two_containers()
    assert first.hold_workspace(WS_A, seconds=0) is True
    # Its own clock has already run out, so the next arrival reclaims it rather than
    # waiting for a release that is never coming.
    assert second.hold_workspace(WS_A) is True


def test_the_lease_is_re_entrant_within_one_request():
    """Handlers compose: a coordinator run seeds a cold workspace before it runs. An
    inner acquisition must not block on the lease its own caller holds."""
    guard = _guard()
    assert guard.hold_workspace(WS_A) is True
    assert guard.hold_workspace(WS_A) is True
    guard.release_workspace(WS_A)
    # Still held by the outer frame — a nested release must not open the workspace up.
    other = public_demo.PublicDemoGuard(
        settings=guard.settings, quota=public_demo.InMemoryQuotaStore(), lease=guard.lease
    )
    assert other.hold_workspace(WS_A) is False
    guard.release_workspace(WS_A)
    assert other.hold_workspace(WS_A) is True


def test_a_failed_action_releases_the_lease():
    """A handler that raised has stopped writing, so holding on would only wedge the
    visitor's own next click."""
    guard = _guard()
    with pytest.raises(RuntimeError), guard.workspace_mutation(WS_A, "busy"):
        raise RuntimeError("boom")
    assert guard.hold_workspace(WS_A) is True


def test_an_abandoned_lease_is_left_to_expire():
    """The ambiguous-remote case: releasing would let a second coordinator into a
    partition the first may still be writing."""
    first, second = _two_containers()
    assert first.hold_workspace(WS_A) is True
    first.abandon_workspace(WS_A)
    assert second.hold_workspace(WS_A) is False


# ------------------------------------------------------- initialisation is not a race


def test_two_simultaneous_first_loads_seed_a_workspace_once(api):
    """The browser opens with `Promise.all([state(), map()])`; both seed a cold session.

    `seed()` starts by deleting every row in the partition, so an unsynchronised second
    seed destroys the first one's work rather than duplicating it.
    """
    calls: list[str] = []
    real_seed = api.seed

    def counting_seed(repo, ws):
        calls.append(ws)
        return real_seed(repo, ws)

    api.seed = counting_seed
    try:
        results: list[Exception | None] = [None, None]

        def load(index: int) -> None:
            try:
                api.ensure_seeded(WS_A)
            except Exception as exc:  # noqa: BLE001 - reported through the list
                results[index] = exc

        threads = [threading.Thread(target=load, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
    finally:
        api.seed = real_seed

    assert results == [None, None]
    assert calls == [WS_A], "a cold workspace must be seeded exactly once"
    assert api.repo().list_communities(WS_A)


def test_a_second_load_of_an_established_workspace_writes_nothing(api):
    """Duplicate initialisation must never destructively overwrite settled state."""
    api.ensure_seeded(WS_A)
    marker = api.repo().list_households(WS_A)[0]
    marker.display_name = "Established"
    api.repo().put_household(WS_A, marker)

    api.ensure_seeded(WS_A)

    assert api.repo().get_household(WS_A, marker.id).display_name == "Established"


def test_a_workspace_held_by_another_coordinator_is_not_reseeded(api):
    """A read arriving mid-run waits for the holder rather than seeding over the top."""
    api._public.settings = public_demo.PublicDemoSettings(
        enabled=True, seed_wait_seconds=0.3
    )
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    api.ensure_seeded(WS_A)

    # Nothing was written: the holder owns this partition until it lets go.
    assert api.repo().list_communities(WS_A) == []


# ----------------------------------------------------- mutating routes exclude each other


def test_reset_is_refused_while_a_live_run_holds_the_workspace(client, api):
    """Reset deletes every row in the partition. It must never land inside a live run."""
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    response = client.post(f"/api/demo/reset?workspace={WS_A}")

    assert response.status_code == 409
    other.release_workspace(WS_A)
    assert client.post(f"/api/demo/reset?workspace={WS_A}").status_code == 200


def test_a_local_run_is_refused_while_the_workspace_is_held(client, api):
    """The local coordinator writes the same partition the deployed one does."""
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    response = client.post(
        f"/api/agent/run?workspace={WS_A}", json={"trigger": "manual_scan"}
    )

    assert response.status_code == 409


def test_the_scenario_is_refused_while_the_workspace_is_held(client, api):
    """The showcase reseeds and then drives the whole lifecycle — hundreds of writes."""
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    response = client.post(f"/api/demo/scenario?workspace={WS_A}")

    assert response.status_code == 409


def test_a_live_run_is_refused_while_a_local_action_holds_the_workspace(api):
    """The exclusion runs both ways, or it is not an exclusion.

    And the refusal must not offer the local fallback: the whole point of holding the
    workspace is that something is already writing it.
    """
    runtime = FakeRuntime()
    live_client = _with_live(api, runtime)
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    body = live_client.post(f"/api/demo/agentcore?workspace={WS_A}").json()

    assert body["ok"] is False
    assert body["classification"] == public_demo.LIVE_CLASS_WORKSPACE_BUSY
    assert body["allow_local_fallback"] is False
    assert runtime.calls == [], "a refused run must never reach the paid runtime"


def test_losing_the_workspace_race_costs_no_paid_quota(api):
    """The lease is taken before the quota, so the loser keeps all three live runs."""
    live_client = _with_live(api, FakeRuntime())
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True
    live_client.post(f"/api/demo/agentcore?workspace={WS_A}")
    other.release_workspace(WS_A)

    allowance = api._public.settings.max_live_per_session
    for _ in range(allowance):
        assert live_client.post(f"/api/demo/agentcore?workspace={WS_A}").json()["ok"] is True


def test_a_refused_mutation_leaves_the_workspace_intact(client, api):
    """Losing the race must cost the loser nothing but the click."""
    client.get(f"/api/state?workspace={WS_A}")
    before = len(api.repo().list_households(WS_A))
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    assert client.post(f"/api/demo/reset?workspace={WS_A}").status_code == 409

    assert len(api.repo().list_households(WS_A)) == before


def test_two_tabs_racing_one_mutating_action_produce_one_winner(client, api):
    """Exactly one of two simultaneous resets runs; the other is told to wait."""
    client.get(f"/api/state?workspace={WS_A}")
    codes: list[int] = []
    lock = threading.Lock()
    ready = threading.Barrier(2, timeout=30)

    def reset() -> None:
        ready.wait()
        code = client.post(f"/api/demo/reset?workspace={WS_A}").status_code
        with lock:
            codes.append(code)

    threads = [threading.Thread(target=reset) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(codes) in ([200, 200], [200, 409]), codes
    # Whatever the interleaving, the workspace is whole afterwards.
    assert api.repo().list_communities(WS_A)


def test_one_workspace_being_busy_does_not_block_another(client, api):
    """Serialisation is per workspace. One judge waiting must not stop the next one."""
    other = public_demo.PublicDemoGuard(
        settings=api._public.settings,
        quota=public_demo.InMemoryQuotaStore(),
        lease=api._public.lease,
    )
    assert other.hold_workspace(WS_A) is True

    assert client.post(f"/api/demo/reset?workspace={WS_A}").status_code == 409
    assert client.post(f"/api/demo/reset?workspace={WS_B}").status_code == 200


def test_workspaces_stay_isolated_across_a_reset(client, api):
    """A destructive action is scoped to its own partition and can never reach another."""
    client.get(f"/api/state?workspace={WS_A}")
    client.get(f"/api/state?workspace={WS_B}")
    household = api.repo().list_households(WS_B)[0]
    household.display_name = "Untouched"
    api.repo().put_household(WS_B, household)

    assert client.post(f"/api/demo/reset?workspace={WS_A}").status_code == 200

    assert api.repo().get_household(WS_B, household.id).display_name == "Untouched"


# ------------------------------------------------- candidate creation across repositories


def test_two_repositories_cannot_both_create_the_same_candidate_pool():
    """The duplicate-pool race, proved where the in-memory fake cannot hide it.

    Two `DynamoDBRepository` instances over one table are two Lambda containers. Both
    scan, both find no pool for the key, and both proceed — so the claim, not the scan,
    has to be what decides.
    """
    table = FakeDynamoTable()
    first = DynamoDBRepository("pool-demo-state", table=table)
    second = DynamoDBRepository("pool-demo-state", table=table)

    won = first.claim_pool_idempotency(WS, "comm:prod:site:2026-08-22", "pool_first")
    lost = second.claim_pool_idempotency(WS, "comm:prod:site:2026-08-22", "pool_second")

    assert won == "pool_first"
    assert lost == "pool_first", "the loser must be handed the winner's pool, not its own"


def test_a_claim_whose_pool_was_never_written_is_reusable():
    """A container that died between claiming a key and writing the pool must not
    poison that key forever — the next caller creates the id already agreed on."""
    table = FakeDynamoTable()
    repo = DynamoDBRepository("pool-demo-state", table=table)

    intended = repo.claim_pool_idempotency(WS, "k", "pool_agreed")
    assert repo.get_pool(WS, intended) is None

    again = repo.claim_pool_idempotency(WS, "k", "pool_other")
    assert again == "pool_agreed"


def test_claims_are_scoped_to_their_workspace():
    table = FakeDynamoTable()
    repo = DynamoDBRepository("pool-demo-state", table=table)

    assert repo.claim_pool_idempotency(WS_A, "k", "pool_a") == "pool_a"
    assert repo.claim_pool_idempotency(WS_B, "k", "pool_b") == "pool_b"


def test_a_reset_clears_the_claims_it_left_behind():
    """Otherwise a reseeded workspace could never form the same pool again."""
    table = FakeDynamoTable()
    repo = DynamoDBRepository("pool-demo-state", table=table)
    repo.claim_pool_idempotency(WS_A, "k", "pool_a")

    repo.reset(WS_A)

    assert repo.claim_pool_idempotency(WS_A, "k", "pool_fresh") == "pool_fresh"


def test_duplicate_candidate_creation_returns_one_pool(ctx, repo):
    """The service-level contract: calling twice for the same product, site and day
    returns the pool that exists rather than a second one."""
    from pool.services import coordination as coord

    seed(repo, ctx.ws)
    assessment = coord.evaluate_opportunity(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        product_id="prod_whey_vanilla",
        pickup_site_id="site_union",
    )
    key = f"{COMMUNITY_ID}:prod_whey_vanilla:site_union:{assessment.distribution_day}"

    first, created_first = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key=key
    )
    second, created_second = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key=key
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert len(repo.list_pools(ctx.ws)) == 1


def test_the_claim_decides_even_when_the_scan_cannot(ctx, repo):
    """With the scan blinded, the pool must still be created exactly once — which is
    what a second container racing this one actually looks like."""
    from pool.services import coordination as coord

    seed(repo, ctx.ws)
    assessment = coord.evaluate_opportunity(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        product_id="prod_whey_vanilla",
        pickup_site_id="site_union",
    )
    key = "fixed-key"
    coord.create_candidate_pool(ctx=ctx, assessment=assessment, idempotency_key=key)

    # A container whose scan is stale — it has not seen the winner's pool yet.
    class BlindScan(InMemoryRepository):
        def list_pools(self, ws):
            return []

    blind = BlindScan()
    blind._ws = repo._ws  # same underlying store, stale view of it
    ctx.repo = blind

    _, created = coord.create_candidate_pool(
        ctx=ctx, assessment=assessment, idempotency_key=key
    )

    assert created is False
    assert len(repo.list_pools(ctx.ws)) == 1
