"""Finding a product Pool can actually buy, without pretending about the ones it cannot.

The catalogue holds hundreds of real consumer identities. Pool holds a synthetic verified
bulk quote for a handful of them. Those are two different facts about two different
things, kept in two different files on purpose (§41, §48) — and the search that turns
typing into a product id sat between them saying nothing about either.

The consequence was a quiet dead end. Typing `coffee` returned eight real coffees ranked
by how well the word matched, and the one Pool could genuinely source was not among them:
"Death Wish Coffee Co" scored higher purely because the noun appears in its brand name.
A member picked one, kept `exact_only`, and Pool correctly told them nothing could be
done — an honest answer to a question the interface had steered them into asking.

The fix is a ranking and a label, not a rewrite:

* a product Pool holds a quote for is *favoured* for a query it already matches;
* it is *marked*, so the reason it is first is visible rather than mysterious;
* nothing is renamed, merged, or substituted, and a member who deliberately picks an
  unsourceable product keeps exactly what they picked.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.data import catalog
from pool.services import coordination as coord
from pool.services import run_report

SOURCEABLE_COFFEE = "prod_coffee_beans"


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    return c


def _search(client: TestClient, query: str) -> list[dict]:
    return client.get("/api/products/search", params={"q": query}).json()["results"]


def _onboard(client: TestClient) -> str:
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    client.post("/api/onboarding/payment-method")
    return client.get("/api/state").json()["consumer"]["household_id"]


def _declare(client, household_id, product_id, *, substitution="exact_only", quantity=3):
    due = date.today() + timedelta(days=12)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": product_id,
            "quantity": quantity,
            "cadence_days": 30,
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


# --------------------------------------------------------------------- discoverable


def test_a_broad_query_surfaces_what_pool_can_actually_source(client):
    """`coffee` is the commonest thing a person types, and it used to bury the answer."""
    results = _search(client, "coffee")
    assert results[0]["product_id"] == SOURCEABLE_COFFEE
    assert results[0]["sourceable"] is True
    # And the rest of the catalogue is still there. This is a ranking, not a filter.
    assert len(results) > 1
    assert any(not r["sourceable"] for r in results)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("coffee", SOURCEABLE_COFFEE),
        ("whey", "prod_whey_vanilla"),
        ("energy drink", "prod_energy_drink"),
        ("laundry", "prod_detergent_pods"),
        ("paper towels", "prod_paper_towels"),
    ],
)
def test_every_sourceable_product_leads_its_own_generic_query(client, query, expected):
    """The demo does not depend on remembering a magic phrase. Typing the category does
    it, for every product this deployment can genuinely buy."""
    results = _search(client, query)
    assert results[0]["product_id"] == expected
    assert results[0]["sourceable"] is True


def test_a_specific_brand_still_wins_over_a_sourceable_one(client):
    """The boost is bounded on purpose. Somebody who names a brand gets that brand —
    favouring what Pool can sell would be the search deciding what they buy."""
    assert _search(client, "death wish")[0]["brand"].lower().startswith("death wish")
    folgers = _search(client, "folgers coffee")
    assert folgers[0]["brand"] == "Folgers"
    assert SOURCEABLE_COFFEE not in {r["product_id"] for r in folgers[:3]}


def test_the_boost_cannot_invent_a_match(client):
    """A product the query does not hit is excluded before any of this applies, so a
    sourceable product can never appear for something unrelated."""
    ids = {r["product_id"] for r in _search(client, "shampoo")}
    assert SOURCEABLE_COFFEE not in ids
    assert "prod_whey_vanilla" not in ids


def test_sourceability_is_read_from_the_offers_the_evaluator_uses(client):
    """Truthful by construction: the flag is the same ``offers_for`` an opportunity
    assessment consults, so nothing can be marked sourceable that could not be priced."""
    ctx = api.ctx_for("demo")
    for query in ("coffee", "whey", "protein", "energy", "towels"):
        for result in _search(client, query):
            has_bulk = bool(coord.offers_for(ctx, result["product_id"])[1])
            assert result["sourceable"] is has_bulk, result["product_id"]


def test_no_bulk_offer_is_fabricated_for_a_catalogue_product(client):
    """The separation these two files exist to keep. A real brand name must never lend
    credibility to an invented quote."""
    ctx = api.ctx_for("demo")
    seeded = {p.id for p in api._repo.list_products("demo")}
    for entry in catalog.entries():
        if entry.product_id in seeded:
            continue
        assert coord.offers_for(ctx, entry.product_id) == (None, [])


# ------------------------------------------------------------------- still honest


def test_an_unsourceable_choice_stays_exactly_what_the_member_picked(client):
    """The declaration is theirs. Pool may not quietly resolve it into the neighbouring
    product it happens to be able to buy."""
    household = _onboard(client)
    typed = next(r for r in _search(client, "coffee") if not r["sourceable"])
    need = _declare(client, household, typed["product_id"])

    stored = client.get("/api/needs").json()["needs"]
    mine = [n for n in stored if n["need_id"] == need["need_id"]]
    assert mine and mine[0]["product_id"] == typed["product_id"]
    assert mine[0]["substitution"] == "exact_only"

    run = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
    report = client.get(
        f"/api/runs/{run['run_id']}/report", params={"household_id": household}
    ).json()
    result = report["results"][0]
    assert result["product_id"] == typed["product_id"]
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] in {
        coord.REASON_NO_BULK_OFFER,
        coord.REASON_NO_RETAIL_BASELINE,
    }
    assert client.get("/api/state").json()["pools"] == []


def test_declared_authority_is_what_widens_the_search_never_the_ranking(client):
    """A member who *authorises* the neighbouring brand can be served by it. One who
    does not, cannot — and the search ranking has no say in either."""
    household = _onboard(client)
    unsourceable = next(r for r in _search(client, "coffee") if not r["sourceable"])
    _declare(client, household, unsourceable["product_id"], substitution="structured_category_match")

    ctx = api.ctx_for("demo")
    need = next(
        n for n in api._repo.list_needs("demo") if n.household_id == household and n.active
    )
    permitted = coord.sourceable_targets_for_need(ctx, need)
    assert SOURCEABLE_COFFEE in permitted

    need.substitution = type(need.substitution)("exact_only")
    api._repo.put_need("demo", need)
    assert coord.sourceable_targets_for_need(ctx, need) == []


def test_a_custom_product_is_declarable_and_openly_unsourceable(client):
    """Something Pool has never heard of is still a thing somebody buys."""
    body = client.post("/api/products/custom", json={"name": "Cardamom pods, 500g"}).json()
    assert body["sourceable"] is False
    assert "no supplier" in body["note"]
    ctx = api.ctx_for("demo")
    assert coord.offers_for(ctx, body["product_id"]) == (None, [])
