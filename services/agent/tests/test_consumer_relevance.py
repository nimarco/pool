"""The causal chain from "what I declared" to "what Pool showed me".

Pool coordinates a whole Community, so a single run may legitimately form an order that
has nothing to do with the person who pressed the button. That is the product working.
What broke — and what this file exists to stop coming back — is a consumer surface
presenting *that* order as theirs.

The observed failure: a member onboarded, declared coffee, pressed Run Pool now, and was
shown a whey protein opportunity. Nothing was scripted and nothing was reseeded; the
coordinator correctly formed the biggest real opportunity in the community (twelve
students' whey declarations against six coffee ones), and Home led with "the first pool
in the workspace". The member was in none of it.

So these tests run the *real* interactive path — the same endpoints the browser calls,
in the same order — and assert on what a consumer surface is given, not on what the
coordinator happened to do.

The invariant, in one sentence: **a member is only ever shown a pool as theirs when a
stored membership row, carrying the id of a declaration they actually made, says they
are in it.**
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.data.seed import CONSUMER_HOUSEHOLD
from pool.services import relevance


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    return TestClient(api.app)


# --------------------------------------------------------------------------- helpers


def _onboard(client: TestClient) -> str:
    """Everything a person does before declaring anything, through the real endpoints."""
    client.get("/api/state")
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    client.post("/api/onboarding/payment-method")
    return client.get("/api/state").json()["consumer"]["household_id"]


def _declare(
    client: TestClient,
    household_id: str,
    product_id: str,
    *,
    quantity: int = 2,
    substitution: str = "exact_only",
) -> dict:
    due = date.today() + timedelta(days=12)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": product_id,
            "quantity": quantity,
            "cadence_days": 40,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": 11,
            "routine_lead_days": 11,
            "min_savings_pct": 20,
            "max_spend_cents": 9000,
            "substitution": substitution,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _search_first(client: TestClient, query: str) -> str:
    results = client.get("/api/products/search", params={"q": query}).json()["results"]
    assert results, f"nothing resolved for {query!r}"
    return results[0]["product_id"]


def _run(client: TestClient) -> dict:
    """The consumer's own **Run Pool now**, anchored to their own declarations."""
    response = client.post("/api/agent/run", json={"trigger": "member_scan"})
    assert response.status_code == 200, response.text
    return response.json()


def _community_run(client: TestClient) -> dict:
    """The scan the scheduled pool-day invocation performs. Nobody's button."""
    response = client.post("/api/agent/run", json={"trigger": "manual_scan"})
    assert response.status_code == 200, response.text
    return response.json()


def _me(client: TestClient, household_id: str) -> dict:
    return client.get(f"/api/members/{household_id}").json()


def _outlook_for(member: dict, need_id: str) -> dict:
    match = [o for o in member["needs_outlook"] if o["need_id"] == need_id]
    assert match, "every active declaration must have an outlook"
    return match[0]


# ------------------------------------------------------------- the reported bug


def test_a_coffee_consumer_is_never_shown_the_whey_pool_as_theirs(client):
    """The exact reported sequence, asserted end to end.

    The run is still allowed to form the whey pool — twelve students really did declare
    whey, and refusing to coordinate it because a thirteenth person is looking at the
    screen would be the opposite failure. What must not happen is that pool being
    presented to *this* member as their result.
    """
    household = _onboard(client)
    coffee = _search_first(client, "coffee")
    need = _declare(client, household, coffee)

    before = client.get("/api/needs").json()["needs"]
    mine = [n for n in before if n["household_id"] == household]
    assert [n["product_id"] for n in mine] == [coffee]

    _run(client)

    member = _me(client, household)
    assert member["opportunity"] is None, (
        "a pool the member is not in must never be handed back as their opportunity"
    )
    # And the declaration is untouched: no whey need appeared, nothing was reseeded.
    after = client.get("/api/needs").json()["needs"]
    still_mine = [n for n in after if n["household_id"] == household]
    assert [n["need_id"] for n in still_mine] == [need["need_id"]]
    assert all("whey" not in n["product_id"] for n in still_mine)


def test_the_interactive_run_never_declares_the_flagship_need(client):
    """`services/demo.py` writes a whey declaration for this household. The consumer
    endpoint must not reach it — that is the scripted showcase's prerequisite, not
    something a normal run may do behind a member's back."""
    household = _onboard(client)
    _declare(client, household, _search_first(client, "coffee"))
    _run(client)

    products = {
        n["product_id"]
        for n in client.get("/api/needs").json()["needs"]
        if n["household_id"] == household
    }
    assert "prod_whey_vanilla" not in products


def test_the_interactive_run_does_not_reseed_the_members_account(client):
    """A reseed would silently restore the fixture's placeholder name and drop the card."""
    household = _onboard(client)
    _declare(client, household, _search_first(client, "coffee"))
    before = client.get("/api/state").json()["consumer"]

    _run(client)

    after = client.get("/api/state").json()["consumer"]
    assert after == before
    assert after["display_name"] == "Marco"
    assert after["has_payment_method"] is True


# ------------------------------------------------------ the canonical consumer


def test_the_flagship_whey_consumer_is_genuinely_in_the_pool_the_agent_formed(client):
    """The canonical scenario, reached with no scripted helper at all.

    Onboard, type what the README tells a visitor to type, pick the tub, press the
    button. The pool that comes back has to contain this member, and the membership has
    to point at the declaration they just made.
    """
    household = _onboard(client)
    whey = _search_first(client, "vanilla whey")
    assert whey == "prod_whey_vanilla", "the flagship query must still resolve to the flagship product"
    need = _declare(client, household, whey, quantity=2)

    run = _run(client)
    assert run["outcome"] == "pool_created"

    member = _me(client, household)
    opportunity = member["opportunity"]
    assert opportunity is not None
    # Lineage: this pool is theirs *because of this declaration*, read from the stored
    # membership rather than inferred from a product name.
    assert opportunity["need_id"] == need["need_id"]
    assert opportunity["declared_product_id"] == whey

    pool = client.get(f"/api/pools/{opportunity['pool_id']}").json()
    assert pool["product_id"] == whey
    assert household in {m["household_id"] for m in pool["members"]}
    assert _outlook_for(member, need["need_id"])["state"] == relevance.OUTLOOK_IN_POOL


# ------------------------------------------------------------- no-op behaviour


def test_a_product_with_no_viable_pool_keeps_the_need_and_substitutes_nothing(client):
    """Paper towels exist in the fixture precisely to never clear a supplier minimum."""
    household = _onboard(client)
    towels = "prod_paper_towels"
    need = _declare(client, household, towels)

    _run(client)

    member = _me(client, household)
    assert member["opportunity"] is None
    outlook = _outlook_for(member, need["need_id"])
    assert outlook["state"] == relevance.OUTLOOK_SHORT
    # The truthful shape of the answer: this many declared, this many required.
    assert outlook["units_available"] < outlook["units_needed"]
    assert outlook["product_id"] == towels
    # The declaration survives, so Pool can act on it later.
    assert any(
        n["need_id"] == need["need_id"] and n["active"]
        for n in client.get("/api/needs").json()["needs"]
    )


def test_demand_that_pools_without_saving_anything_says_so_rather_than_forming(client):
    """Detergent clears the minimum and still must not pool: once a fulfiller's pay,
    processing and Pool's fee are counted the saving is gone (AGENTS.md §1)."""
    household = _onboard(client)
    need = _declare(client, household, "prod_detergent_pods", quantity=4)
    _run(client)

    outlook = _outlook_for(_me(client, household), need["need_id"])
    assert outlook["state"] == relevance.OUTLOOK_NOT_WORTH_IT


def test_an_unsourceable_product_is_declarable_and_forms_nothing(client):
    """A member may declare something Pool cannot buy in bulk. The need is real; the
    honest consequence is that no pool ever forms for it."""
    household = _onboard(client)
    custom = client.post("/api/products/custom", json={"name": "Cardamom pods, 500g"}).json()
    assert custom["sourceable"] is False
    need = _declare(client, household, custom["product_id"])

    _run(client)

    member = _me(client, household)
    assert member["opportunity"] is None
    assert _outlook_for(member, need["need_id"])["state"] == relevance.OUTLOOK_NO_SUPPLY


def test_a_catalogue_product_with_no_offer_does_not_borrow_another_products_pool(client):
    """The catalogue holds hundreds of coffees; Pool holds a bulk quote for one of them.

    Declaring a different one is legitimate and must not quietly resolve into the
    product Pool *can* source — that would be Pool deciding what somebody buys.
    """
    household = _onboard(client)
    typed = _search_first(client, "coffee")
    assert typed != "prod_coffee_beans"
    need = _declare(client, household, typed)

    stored = [
        n for n in client.get("/api/needs").json()["needs"] if n["need_id"] == need["need_id"]
    ]
    assert stored[0]["product_id"] == typed

    _run(client)
    member = _me(client, household)
    assert member["opportunity"] is None
    assert _outlook_for(member, need["need_id"])["state"] == relevance.OUTLOOK_NOT_MATCHED


def test_an_authorised_substitute_carries_what_the_member_actually_declared(client):
    """A pool may legitimately buy something other than the exact product typed, when
    that member's own substitution rule allows it. The card then shows the *pool's*
    name and photograph, so the lineage has to carry the declaration alongside it —
    otherwise the product on screen silently disagrees with the one on the record."""
    household = _onboard(client)
    need = _declare(
        client,
        household,
        "prod_whey_chocolate",
        substitution="same_product_other_variant",
    )

    _run(client)

    opportunity = _me(client, household)["opportunity"]
    assert opportunity is not None
    assert opportunity["product_id"] == "prod_whey_vanilla"
    assert opportunity["declared_product_id"] == "prod_whey_chocolate"
    assert opportunity["need_id"] == need["need_id"]
    assert opportunity["is_exact_product"] is False
    assert opportunity["declared_product_name"] == "Gold Standard 100% Whey"


def test_an_exact_match_names_no_substitute(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)

    opportunity = _me(client, household)["opportunity"]
    assert opportunity["is_exact_product"] is True
    assert opportunity["declared_product_name"] == ""


# ------------------------------------------------------------- several declarations


def test_with_two_declarations_the_result_traces_to_one_of_them(client):
    household = _onboard(client)
    coffee = _declare(client, household, _search_first(client, "coffee"))
    whey = _declare(client, household, "prod_whey_vanilla", quantity=2)

    _run(client)

    member = _me(client, household)
    opportunity = member["opportunity"]
    assert opportunity is not None
    assert opportunity["need_id"] in {coffee["need_id"], whey["need_id"]}
    pool = client.get(f"/api/pools/{opportunity['pool_id']}").json()
    declared = {n["need_id"]: n["product_id"] for n in client.get("/api/needs").json()["needs"]}
    assert pool["product_id"] == declared[opportunity["need_id"]]


# ------------------------------------------------------------- stale and global


def test_leaving_a_pool_stops_it_being_this_members_opportunity(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)
    pool_id = _me(client, household)["opportunity"]["pool_id"]

    client.post(f"/api/pools/{pool_id}/withdraw/{household}")

    assert _me(client, household)["opportunity"] is None
    # The pool itself is still there, and still the community's. It simply is not theirs.
    assert client.get("/api/state").json()["pools"]


def test_another_members_pool_is_never_the_consumers_opportunity(client):
    """The general form of the reported bug: a pool exists, the consumer is not in it."""
    household = _onboard(client)
    # The pool-day scan, not this member's button: it forms the whey pool out of the
    # synthetic members' declarations, and this member is in none of it.
    _community_run(client)

    state = client.get("/api/state").json()
    assert state["pools"], "the coordinator should still have formed the community's pool"
    assert _me(client, household)["opportunity"] is None


def test_an_operator_acting_as_a_synthetic_member_sees_that_members_pool_only(client):
    """Stepping into somebody else must show *their* stake and must not survive the
    step back out."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)

    mine = _me(client, household)["opportunity"]
    assert mine is not None
    theirs = _me(client, "hh_okafor")["opportunity"]
    assert theirs is not None
    assert theirs["pool_id"] == mine["pool_id"]
    # Different member, different declaration behind the same pool.
    assert theirs["need_id"] != mine["need_id"]
    assert theirs["need_id"] == "need_whey_okafor"

    # A member who is in nothing gets nothing, even while somebody else's pool exists.
    assert _me(client, "hh_whitfield")["opportunity"] is None


def test_every_pool_the_member_is_in_is_reported_not_only_the_first(client):
    """Home names the pools that are *not* this member's as the community's. It has to
    be able to exclude all of theirs, or a member in two pools is told they are not in
    one of them."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)

    member = _me(client, household)
    reported = {member["opportunity"]["pool_id"], *member["other_pool_ids"]}
    actually_in = {
        pool["pool_id"]
        for pool in client.get("/api/state").json()["pools"]
        if household
        in {
            m["household_id"]
            for m in client.get(f"/api/pools/{pool['pool_id']}").json()["members"]
            if m["state"] not in {"withdrawn", "declined"}
        }
    }
    assert reported == actually_in


def test_a_workspace_cannot_see_another_workspaces_pool(client):
    other = TestClient(api.app)
    api._repo.reset("wisolationb")
    other.get("/api/state", params={"workspace": "wisolationb"})

    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)
    assert _me(client, household)["opportunity"] is not None

    assert other.get("/api/state", params={"workspace": "wisolationb"}).json()["pools"] == []
    theirs = other.get(
        f"/api/members/{CONSUMER_HOUSEHOLD}", params={"workspace": "wisolationb"}
    ).json()
    assert theirs["opportunity"] is None


def test_a_repeated_run_does_not_hand_back_a_second_conflicting_opportunity(client):
    """Idempotency, from the member's side: pressing the button twice is one pool."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)
    first = _me(client, household)["opportunity"]

    _run(client)
    second = _me(client, household)["opportunity"]

    assert first is not None
    assert second["pool_id"] == first["pool_id"]
    assert second["need_id"] == first["need_id"]
    assert len(client.get("/api/state").json()["pools"]) == 1


# ------------------------------------------------------------- read-only pass


def test_a_member_view_writes_nothing(client):
    """The outlook runs the opportunity evaluator once per sourceable product per pickup
    site. That is only safe — and its read memo is only safe — because the whole pass
    creates nothing, commits nothing and logs nothing."""
    household = _onboard(client)
    _declare(client, household, "prod_paper_towels")
    _declare(client, household, _search_first(client, "coffee"))

    def snapshot() -> dict:
        state = client.get("/api/state").json()
        return {
            "pools": state["pools"],
            "decisions": state["decisions"],
            "activity": len(state["activity"]),
            "counts": state["counts"],
            "needs": client.get("/api/needs").json()["needs"],
        }

    before = snapshot()
    client.get(f"/api/members/{household}")
    client.get(f"/api/members/{household}")
    assert snapshot() == before


def test_the_outlook_is_stable_across_repeated_reads(client):
    """A memoised read that returned a different answer twice would be worse than no
    memo at all."""
    household = _onboard(client)
    _declare(client, household, "prod_paper_towels")
    assert _me(client, household)["needs_outlook"] == _me(client, household)["needs_outlook"]


# ------------------------------------------------------------- lineage integrity


def test_a_retired_declaration_cannot_be_pooled(client):
    """`active=False` is how a member says they stopped buying something. It has to
    stop counting toward a supplier minimum and stop being authorisable."""
    household = _onboard(client)
    need = _declare(client, household, "prod_whey_vanilla", quantity=2)
    client.post(
        f"/api/needs/{need['need_id']}",
        json={
            "household_id": household,
            "product_id": "prod_whey_vanilla",
            "quantity": 2,
            "cadence_days": 40,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "flexibility_days": 11,
            "routine_lead_days": 11,
            "min_savings_pct": 20,
            "max_spend_cents": 9000,
            "substitution": "exact_only",
            "active": False,
        },
    )

    # Their own button first: a retired declaration is not a question, so there is
    # nothing for a member-anchored run to investigate.
    assert _run(client)["outcome"] == "no_action"
    # And the community's own scan, which does form the whey pool, must not count them.
    _community_run(client)

    member = _me(client, household)
    assert member["opportunity"] is None
    pools = client.get("/api/state").json()["pools"]
    assert pools, "the community scan should still have formed the whey pool"
    for pool in pools:
        detail = client.get(f"/api/pools/{pool['pool_id']}").json()
        assert household not in {m["household_id"] for m in detail["members"]}


def test_a_declaration_already_in_a_pool_cannot_be_repointed_at_another_product(client):
    """Membership.need_id is the lineage every consumer surface reads. Re-pointing it
    would leave the record saying somebody joined a whey order because they buy coffee,
    with the units and the authorisation untouched."""
    household = _onboard(client)
    need = _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)
    assert _me(client, household)["opportunity"] is not None

    response = client.post(
        f"/api/needs/{need['need_id']}",
        json={
            "household_id": household,
            "product_id": "prod_coffee_beans",
            "quantity": 2,
            "cadence_days": 40,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "flexibility_days": 11,
            "routine_lead_days": 11,
            "min_savings_pct": 20,
            "max_spend_cents": 9000,
            "substitution": "exact_only",
        },
    )
    assert response.status_code == 400
    assert "already coordinating" in response.json()["detail"]
    # Amending everything else about it still works.
    assert (
        client.post(
            f"/api/needs/{need['need_id']}",
            json={
                "household_id": household,
                "product_id": "prod_whey_vanilla",
                "quantity": 3,
                "cadence_days": 40,
                "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
                "flexibility_days": 11,
                "routine_lead_days": 11,
                "min_savings_pct": 20,
                "max_spend_cents": 9000,
                "substitution": "exact_only",
            },
        ).status_code
        == 200
    )
