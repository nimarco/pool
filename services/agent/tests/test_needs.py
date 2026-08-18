"""Declaring a standing need — the product's primary user action.

Everything Pool does is downstream of this. Latent demand *is* declared need that no
pool is serving yet, so the rules here decide what the agent is later allowed to
discover, and the numbers here are what the deterministic engines compute against.

The tests that matter are therefore about the boundary, not the CRUD: a declaration
creates no group, commits no money, cannot be written on somebody else's behalf, and
cannot double-count one household's demand.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from pool.data.seed import COMMUNITY_ID
from pool.domain.models import SubstitutionPolicy
from pool.services import needs as needs_service
from tests.conftest import WS

ROSA = "hh_navarro"
OTHER = "hh_okafor"


def _input(ctx, **overrides) -> needs_service.NeedInput:
    defaults = {
        "household_id": ROSA,
        "product_id": "prod_detergent_pods",
        "quantity": 3,
        "cadence_days": 30,
        "expected_next_need_date": ctx.now.date() + timedelta(days=21),
        "flexibility_days": 7,
        "routine_lead_days": 5,
        "min_savings_pct": 15,
        "max_spend_cents": 4000,
        "substitution": SubstitutionPolicy.EXACT_ONLY,
    }
    defaults.update(overrides)
    return needs_service.NeedInput(**defaults)


def _declare(ctx, **overrides):
    return needs_service.declare_need(
        ctx=ctx, community_id=COMMUNITY_ID, data=_input(ctx, **overrides)
    )


# --------------------------------------------------------------------------- creating


def test_a_member_can_declare_what_they_routinely_buy(seeded_ctx):
    need = _declare(seeded_ctx)

    stored = seeded_ctx.repo.get_need(WS, need.id)
    assert stored is not None
    assert stored.household_id == ROSA
    assert stored.quantity == 3
    assert stored.cadence_days == 30
    assert stored.active is True


def test_the_flexibility_window_becomes_the_pull_forward_permission(seeded_ctx):
    """The member answers "how early may you buy"; the timing engine needs a date."""
    need = _declare(seeded_ctx, flexibility_days=10)

    assert need.flexibility_days == 10
    assert need.earliest_acceptable_purchase_date == (
        need.expected_next_need_date - timedelta(days=10)
    )
    assert need.latest_acceptable_purchase_date == need.expected_next_need_date


def test_no_flexibility_means_nothing_is_ever_moved(seeded_ctx):
    """Setting it to nothing must genuinely forbid pull-forward, not merely discourage."""
    need = _declare(seeded_ctx, flexibility_days=0)

    assert need.flexibility_days == 0
    assert need.earliest_acceptable_purchase_date == need.expected_next_need_date


def test_declaring_a_need_creates_no_group_and_commits_no_money(seeded_ctx):
    """Canonical invariant 1 and 2, asserted at the point they could be broken."""
    before_pools = len(seeded_ctx.repo.list_pools(WS))

    _declare(seeded_ctx)

    assert len(seeded_ctx.repo.list_pools(WS)) == before_pools
    assert seeded_ctx.repo.list_payments(WS) == []
    assert seeded_ctx.repo.list_memberships(WS) == []
    assert seeded_ctx.repo.list_decisions(WS) == []


def test_the_declaration_is_recorded_in_the_activity_feed(seeded_ctx):
    _declare(seeded_ctx)

    assert any(e.kind == "need_declared" for e in seeded_ctx.repo.list_activity(WS))


# ------------------------------------------------------------------------- validation


def test_a_second_declaration_for_the_same_product_is_refused(seeded_ctx):
    """Two rows for one household and one product would count its demand twice."""
    _declare(seeded_ctx)

    with pytest.raises(needs_service.NeedError, match="already have a standing need"):
        _declare(seeded_ctx)


def test_a_retired_need_does_not_block_a_fresh_declaration(seeded_ctx):
    need = _declare(seeded_ctx)
    needs_service.amend_need(
        ctx=seeded_ctx,
        community_id=COMMUNITY_ID,
        need_id=need.id,
        data=_input(seeded_ctx, active=False),
    )

    assert _declare(seeded_ctx).id != need.id


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"product_id": "prod_nope"}, "unknown product"),
        ({"household_id": "hh_nobody"}, "unknown member"),
        ({"quantity": 0}, "quantity must be"),
        ({"quantity": 5000}, "quantity must be"),
        ({"cadence_days": 0}, "how often you restock"),
        ({"min_savings_pct": 99}, "saving you require"),
        ({"max_spend_cents": 0}, "spending limit"),
    ],
)
def test_a_declaration_outside_domain_policy_is_refused(seeded_ctx, overrides, message):
    with pytest.raises(needs_service.NeedError, match=message):
        _declare(seeded_ctx, **overrides)


def test_a_need_date_in_the_past_is_refused(seeded_ctx):
    with pytest.raises(needs_service.NeedError, match="cannot be in the past"):
        _declare(seeded_ctx, expected_next_need_date=seeded_ctx.now.date() - timedelta(days=1))


def test_pull_forward_cannot_exceed_one_whole_cycle(seeded_ctx):
    """Buying more than a cycle early restocks a household before it has used what it
    has — storage nobody agreed to, and the flexibility window is permission, not budget."""
    with pytest.raises(needs_service.NeedError, match="one full cycle"):
        _declare(seeded_ctx, cadence_days=14, flexibility_days=30)


def test_only_a_verified_community_member_can_declare(seeded_ctx):
    """Community membership is the trust boundary pools form inside (§2)."""
    membership = seeded_ctx.repo.get_community_membership(WS, COMMUNITY_ID, ROSA)
    seeded_ctx.repo.store(WS).community_memberships.pop(membership.key)

    with pytest.raises(needs_service.NeedError, match="verified member"):
        _declare(seeded_ctx)


# ---------------------------------------------------------------------------- editing


def test_a_member_can_change_their_own_declaration(seeded_ctx):
    need = _declare(seeded_ctx)

    amended = needs_service.amend_need(
        ctx=seeded_ctx,
        community_id=COMMUNITY_ID,
        need_id=need.id,
        data=_input(seeded_ctx, quantity=8, max_spend_cents=9000, flexibility_days=0),
    )

    assert amended.id == need.id
    stored = seeded_ctx.repo.get_need(WS, need.id)
    assert stored.quantity == 8
    assert stored.max_spend_cents == 9000
    assert stored.flexibility_days == 0


def test_a_member_cannot_change_another_members_declaration(seeded_ctx):
    """The one ownership check available without account authentication, enforced in the
    service so no caller can skip it."""
    theirs = next(n for n in seeded_ctx.repo.list_needs(WS) if n.household_id == OTHER)

    with pytest.raises(needs_service.NeedError, match="only be changed by the member"):
        needs_service.amend_need(
            ctx=seeded_ctx,
            community_id=COMMUNITY_ID,
            need_id=theirs.id,
            data=_input(seeded_ctx, household_id=ROSA, product_id=theirs.product_id),
        )

    assert seeded_ctx.repo.get_need(WS, theirs.id).quantity == theirs.quantity


def test_retiring_a_need_removes_it_from_latent_demand(seeded_ctx):
    """`active` is what the discovery tool filters on, so this has to be the same flag."""
    need = _declare(seeded_ctx)

    needs_service.amend_need(
        ctx=seeded_ctx,
        community_id=COMMUNITY_ID,
        need_id=need.id,
        data=_input(seeded_ctx, active=False),
    )

    assert seeded_ctx.repo.get_need(WS, need.id).active is False


def test_amending_an_unknown_need_is_refused(seeded_ctx):
    with pytest.raises(needs_service.NeedError, match="no longer exists"):
        needs_service.amend_need(
            ctx=seeded_ctx,
            community_id=COMMUNITY_ID,
            need_id="need_nope",
            data=_input(seeded_ctx),
        )


# ------------------------------------------------------------------- through the API


@pytest.fixture
def client() -> TestClient:
    from pool.api import app as api

    api._repo.reset("demo")
    return TestClient(api.app)


def _body(client, **overrides) -> dict:
    from datetime import date

    payload = {
        "household_id": ROSA,
        "product_id": "prod_detergent_pods",
        "quantity": 2,
        "cadence_days": 28,
        "expected_next_need_date": (date.today() + timedelta(days=20)).isoformat(),
        "flexibility_days": 6,
        "routine_lead_days": 4,
        "min_savings_pct": 12,
        "max_spend_cents": 3500,
        "substitution": "exact_only",
        "active": True,
    }
    payload.update(overrides)
    return payload


def test_the_api_creates_a_need_and_reads_it_back_authoritatively(client):
    """The Product must show what the server stored, not what the form submitted."""
    client.get("/api/needs")

    created = client.post("/api/needs", json=_body(client))
    assert created.status_code == 200, created.text
    need_id = created.json()["need_id"]

    rows = client.get("/api/needs").json()["needs"]
    stored = next(n for n in rows if n["need_id"] == need_id)
    assert stored["household_id"] == ROSA
    assert stored["quantity"] == 2
    assert stored["flexibility_days"] == 6


def test_the_api_edits_a_need_in_place(client):
    client.get("/api/needs")
    need_id = client.post("/api/needs", json=_body(client)).json()["need_id"]

    updated = client.post(f"/api/needs/{need_id}", json=_body(client, quantity=9))
    assert updated.status_code == 200, updated.text

    rows = client.get("/api/needs").json()["needs"]
    assert next(n for n in rows if n["need_id"] == need_id)["quantity"] == 9
    # Edited in place — an amendment must never leave a second declaration behind.
    assert len([n for n in rows if n["need_id"] == need_id]) == 1


def test_the_api_refuses_an_invalid_declaration_with_a_readable_reason(client):
    client.get("/api/needs")

    response = client.post("/api/needs", json=_body(client, product_id="prod_nope"))

    assert response.status_code == 400
    assert "unknown product" in response.json()["detail"]


def test_the_api_refuses_a_malformed_date(client):
    client.get("/api/needs")

    response = client.post("/api/needs", json=_body(client, expected_next_need_date="soon"))

    assert response.status_code in {400, 422}


def test_the_needs_endpoint_offers_the_catalogue_to_declare_against(client):
    body = client.get("/api/needs").json()

    assert body["products"]
    assert {"product_id", "name", "unit", "brand"} <= set(body["products"][0])
    assert body["limits"]["max_quantity"] > 0


def test_a_need_written_in_one_workspace_is_invisible_in_another(client):
    client.get("/api/needs?workspace=needsone")
    client.get("/api/needs?workspace=needstwo")
    created = client.post("/api/needs?workspace=needsone", json=_body(client))
    assert created.status_code == 200, created.text
    need_id = created.json()["need_id"]

    other = client.get("/api/needs?workspace=needstwo").json()["needs"]

    assert all(n["need_id"] != need_id for n in other)


def test_a_declared_need_joins_the_communitys_latent_demand(client):
    """The point of the whole action: what a member declares is what the agent can find.

    Nobody organises anything. The declaration is a statement about one household, and
    it lands in the same undifferentiated pile of standing needs the discovery tool
    reads — which is where the overlap nobody asked for comes from.
    """
    before = client.get("/api/needs").json()["needs"]

    created = client.post("/api/needs", json=_body(client, quantity=4))
    assert created.status_code == 200, created.text

    after = client.get("/api/needs").json()["needs"]
    assert len(after) == len(before) + 1
    mine = next(n for n in after if n["need_id"] == created.json()["need_id"])
    assert mine["quantity"] == 4
    assert mine["active"] is True
    # A declaration is not a membership: nothing was organised by declaring it.
    assert client.get("/api/state").json()["pools"] == []
