"""One member, many products, and a truthful answer for each.

The demo's credibility rests on a claim that cannot be checked by watching the happy
path: that Pool behaves correctly for *arbitrary supported input*, not for one memorised
product. A system that only works when you type the flagship phrase is a scripted video
with a database behind it.

So every case below goes through the interactive path a person actually uses — onboard,
search, declare, press the button — and asserts the deterministic verdict and the
sentence the member is shown. No case calls the scripted showcase, none reseeds, and none
reaches inside the services to arrange an outcome.

Read as a table, these are the result classes the product can reach:

======================  =========================================================
sourceable whey         forms, and the member is in it
sourceable coffee       forms — the broad query finds it, and it is not the whey pool
energy drinks           a third independent product, on its own members
detergent               refused on **economics**, with enough demand to prove it
paper towels            refused on the **supplier minimum**
chocolate whey          refused for having **no bulk quote**, exact-only
unsourceable catalogue  stays what was chosen, and truthfully no-ops
authorised substitute   participates, and is disclosed as a substitute
two declarations        one order, a verdict for each, lineage on the membership
retired declaration     excluded from everything, everywhere
existing community pool never becomes the personal answer
repeated press          no duplicate pool, no stale report
======================  =========================================================
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.services import coordination as coord
from pool.services import run_report


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    return c


# --------------------------------------------------------------------------- helpers


def _onboard(client: TestClient) -> str:
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    client.post("/api/onboarding/payment-method")
    return client.get("/api/state").json()["consumer"]["household_id"]


def _search(client: TestClient, query: str) -> list[dict]:
    return client.get("/api/products/search", params={"q": query}).json()["results"]


def _declare(
    client: TestClient,
    household_id: str,
    product_id: str,
    *,
    quantity: int = 3,
    days: int = 12,
    substitution: str = "exact_only",
) -> dict:
    due = date.today() + timedelta(days=days)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": product_id,
            "quantity": quantity,
            "cadence_days": 30,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": min(days, 14),
            "routine_lead_days": min(days, 11),
            "min_savings_pct": 15,
            "max_spend_cents": 12000,
            "substitution": substitution,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client: TestClient) -> dict:
    response = client.post("/api/agent/run", json={"trigger": "member_scan"})
    assert response.status_code == 200, response.text
    return response.json()


def _report(client: TestClient, run_id: str, household_id: str) -> dict:
    return client.get(
        f"/api/runs/{run_id}/report", params={"household_id": household_id}
    ).json()


def _one(client: TestClient, household_id: str) -> dict:
    """Declare, run, and hand back the single result for that declaration."""
    run = _run(client)
    report = _report(client, run["run_id"], household_id)
    assert report["is_mine"] is True
    assert len(report["results"]) == 1, report["results"]
    return report["results"][0]


def _pools(client: TestClient) -> list[dict]:
    return client.get("/api/state").json()["pools"]


# ------------------------------------------------------------------ forms and joins


def test_whey_forms_and_the_member_is_in_it(client):
    household = _onboard(client)
    chosen = _search(client, "vanilla whey")[0]
    assert chosen["sourceable"] is True
    _declare(client, household, chosen["product_id"], quantity=2)

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["product_id"] == "prod_whey_vanilla"
    assert result["units"] == 2
    assert result["is_exact_product"] is True

    opportunity = client.get(f"/api/members/{household}").json()["opportunity"]
    assert opportunity["pool_id"] == result["pool_id"]
    # The lineage that makes it theirs, read from the membership row.
    assert opportunity["need_id"] == result["need_id"]
    assert [p["product_id"] for p in _pools(client)] == ["prod_whey_vanilla"]


def test_coffee_forms_and_is_not_the_whey_pool(client):
    """The reported bug, closed end to end through the interface a person uses.

    Typing the category finds the sourceable coffee, and the member's own button forms a
    *coffee* order — not the community's larger whey opportunity.
    """
    household = _onboard(client)
    chosen = _search(client, "coffee")[0]
    assert chosen["sourceable"] is True
    _declare(client, household, chosen["product_id"], quantity=3, days=30)

    run = _run(client)
    products = {p["product_id"] for p in _pools(client)}
    assert products == {chosen["product_id"]}
    assert "prod_whey_vanilla" not in products

    report = _report(client, run["run_id"], household)
    assert report["evaluated_product_ids"] == [chosen["product_id"]]
    assert report["results"][0]["product_id"] == chosen["product_id"]


def test_energy_drinks_are_a_third_independent_opportunity(client):
    household = _onboard(client)
    chosen = _search(client, "energy drink")[0]
    assert chosen["product_id"] == "prod_energy_drink"
    _declare(client, household, chosen["product_id"], quantity=2, days=14)

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["product_id"] == "prod_energy_drink"


# ------------------------------------------------------------------- truthful refusals


def test_detergent_is_refused_on_economics_and_says_so(client):
    """"Not enough of you yet" is an invitation to wait. "This would cost you more" is
    not, and the two must not read the same."""
    household = _onboard(client)
    chosen = _search(client, "laundry")[0]
    assert chosen["product_id"] == "prod_detergent_pods"
    _declare(client, household, chosen["product_id"], quantity=4, days=20)

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_NOT_CHEAPER
    assert "cost" in result["headline"]
    assert _pools(client) == []


def test_paper_towels_are_refused_on_the_supplier_minimum(client):
    household = _onboard(client)
    chosen = _search(client, "paper towels")[0]
    assert chosen["product_id"] == "prod_paper_towels"
    _declare(client, household, chosen["product_id"], quantity=2, days=14)

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_BELOW_MINIMUM
    assert "48" in result["headline"]
    assert _pools(client) == []


def test_a_product_with_no_bulk_quote_says_there_is_no_supplier(client):
    """Chocolate whey has a shelf price and no bulk tier. Exact-only, so the vanilla
    order Pool *can* buy is not an answer for this member."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_chocolate", quantity=2)

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_NO_BULK_OFFER
    assert result["product_id"] == "prod_whey_chocolate"
    assert _pools(client) == []


def test_an_unsourceable_catalogue_product_stays_what_was_chosen(client):
    household = _onboard(client)
    chosen = next(r for r in _search(client, "coffee") if not r["sourceable"])
    need = _declare(client, household, chosen["product_id"])

    result = _one(client, household)
    assert result["product_id"] == chosen["product_id"]
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] in {
        coord.REASON_NO_BULK_OFFER,
        coord.REASON_NO_RETAIL_BASELINE,
    }
    # Nothing was formed, nothing was substituted, and the declaration is untouched.
    assert _pools(client) == []
    stored = [n for n in client.get("/api/needs").json()["needs"] if n["need_id"] == need["need_id"]]
    assert stored[0]["product_id"] == chosen["product_id"]
    assert stored[0]["substitution"] == "exact_only"


def test_a_custom_product_never_borrows_another_products_offer(client):
    household = _onboard(client)
    custom = client.post("/api/products/custom", json={"name": "Cardamom pods, 500g"}).json()
    _declare(client, household, custom["product_id"])

    result = _one(client, household)
    assert result["product_id"] == custom["product_id"]
    assert result["result"] == run_report.RESULT_DECLINED
    assert _pools(client) == []


# ------------------------------------------------------------------- substitution


def test_an_authorised_substitute_participates_and_is_disclosed(client):
    """A member may be served by something other than what they typed — only under a
    rule they set, and never silently."""
    household = _onboard(client)
    _declare(
        client,
        household,
        "prod_whey_chocolate",
        quantity=2,
        substitution="same_product_other_variant",
    )

    result = _one(client, household)
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["product_id"] == "prod_whey_vanilla"
    assert result["is_exact_product"] is False
    assert result["declared_product_name"]

    opportunity = client.get(f"/api/members/{household}").json()["opportunity"]
    assert opportunity["is_exact_product"] is False
    assert opportunity["declared_product_id"] == "prod_whey_chocolate"
    assert opportunity["product_id"] == "prod_whey_vanilla"


# ------------------------------------------------------------------ several at once


def test_two_declarations_get_one_order_and_a_verdict_each(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2, days=12)
    _declare(client, household, "prod_paper_towels", quantity=2, days=14)

    run = _run(client)
    report = _report(client, run["run_id"], household)
    by_product = {r["product_id"]: r for r in report["results"]}
    assert set(by_product) == {"prod_whey_vanilla", "prod_paper_towels"}
    assert by_product["prod_whey_vanilla"]["result"] == run_report.RESULT_FORMED_INCLUDED
    assert by_product["prod_paper_towels"]["result"] == run_report.RESULT_DECLINED
    assert by_product["prod_paper_towels"]["reason_code"] == coord.REASON_BELOW_MINIMUM

    # One order per run, and the membership names the declaration that caused it.
    assert len(_pools(client)) == 1
    opportunity = client.get(f"/api/members/{household}").json()["opportunity"]
    assert opportunity["need_id"] == by_product["prod_whey_vanilla"]["need_id"]


def test_a_retired_declaration_is_excluded_everywhere(client):
    household = _onboard(client)
    need = _declare(client, household, "prod_whey_vanilla", quantity=2)
    client.post(
        f"/api/needs/{need['need_id']}",
        json={
            "household_id": household,
            "product_id": "prod_whey_vanilla",
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "flexibility_days": 11,
            "routine_lead_days": 11,
            "min_savings_pct": 15,
            "max_spend_cents": 12000,
            "substitution": "exact_only",
            "active": False,
        },
    )

    assert _run(client)["outcome"] == "no_action"
    member = client.get(f"/api/members/{household}").json()
    assert member["opportunity"] is None
    assert member["standing_demand"] == []
    # And the community's own scan, which does form the whey pool, must not count them.
    client.post("/api/agent/run", json={"trigger": "manual_scan"})
    for pool in _pools(client):
        detail = client.get(f"/api/pools/{pool['pool_id']}").json()
        assert household not in {m["household_id"] for m in detail["members"]}


def test_an_existing_community_pool_never_becomes_the_personal_answer(client):
    """A pool that was already there is not an answer to a button pressed afterwards."""
    household = _onboard(client)
    client.post("/api/agent/run", json={"trigger": "manual_scan"})  # forms the whey pool
    assert _pools(client)

    _declare(client, household, "prod_paper_towels", quantity=2, days=14)
    result = _one(client, household)

    assert result["product_id"] == "prod_paper_towels"
    assert result["result"] == run_report.RESULT_DECLINED
    assert client.get(f"/api/members/{household}").json()["opportunity"] is None
    # It is still visible — as the community's, with a count and no claim on this member.
    run = _run(client)
    elsewhere = _report(client, run["run_id"], household)["elsewhere"]
    assert [e["product_name"] for e in elsewhere]
    assert all(e["buyer_count"] > 0 for e in elsewhere)


# ------------------------------------------------------------------- pressing twice


def test_pressing_the_button_twice_produces_one_order_and_a_current_report(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)

    first = _run(client)
    second = _run(client)
    assert first["run_id"] != second["run_id"]
    assert len(_pools(client)) == 1

    report = _report(client, second["run_id"], household)
    assert report["run_id"] == second["run_id"]
    assert [r["result"] for r in report["results"]] == [
        run_report.RESULT_ALREADY_COORDINATED
    ]
    # The older run's report is still readable and still describes the older run — it
    # simply is not what the screen asks for.
    assert _report(client, first["run_id"], household)["run_id"] == first["run_id"]


def test_the_operator_stepping_into_another_member_sees_only_their_stake(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    mine = client.get(f"/api/members/{household}").json()["opportunity"]
    theirs = client.get("/api/members/hh_okafor").json()["opportunity"]
    assert mine and theirs
    assert theirs["pool_id"] == mine["pool_id"]
    assert theirs["need_id"] != mine["need_id"]
    # A member in nothing gets nothing, even while somebody else's order exists.
    assert client.get("/api/members/hh_whitfield").json()["opportunity"] is None
    # And the run report is refused for anybody the run was not about.
    assert _report(client, run["run_id"], "hh_okafor")["is_mine"] is False
    assert _report(client, run["run_id"], "hh_okafor")["results"] == []
