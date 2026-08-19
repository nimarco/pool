"""The world changes, and Pool's answer changes with it — for the right reason.

Pool tells a member their declaration "stays standing, and Pool keeps watching". That is
a promise about the future, and the only thing that makes it more than a consolation
sentence is a demonstration that the answer can actually change without anybody being
recruited, persuaded, or asked to buy more.

The demonstration is one row. Six households already declare jasmine rice; Pool holds no
bulk quote for it, so there is nothing to price and no order can form. An operator then
records a quote that a supplier sent — and *nothing about the demand moves*. Same
households, same quantities, same cadences, same substitution rules, same autonomy
policies, same retail baseline.

Three verdicts come out of that, and none of them is written down anywhere:

======================  ==========================================================
no quote                ``no_bulk_offer`` — nothing to evaluate
split-case quote        ``not_cheaper`` — the supplier will sell, and it is still
                        not worth doing
case-programme quote    viable — whole cases, no surplus, a real saving
======================  ==========================================================

The middle row is the one that matters most. A demo where removing the first blocker
always produces a yes is a demo with an answer key; here the first quote is a genuine
offer from a genuine (synthetic) supplier that the evaluator refuses on its own
arithmetic.

The other half of this file is about *evidence*. A run that happened before the quote
arrived must go on saying what it found, because that is what was true when it ran. The
deterministic outlook must move, because that is what is true now. Collapsing those two
is how an agent product starts rewriting its own history to look consistent.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.services import coordination as coord
from pool.services import relevance, run_report
from pool.services import supplier_updates as su

SPLIT = "rice_split_case"
PROGRAM = "rice_case_program"
RICE = su.PRODUCT_ID


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    return c


def _onboard(client: TestClient) -> str:
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    client.post("/api/onboarding/payment-method")
    return client.get("/api/state").json()["consumer"]["household_id"]


def _declare(client: TestClient, household_id: str, quantity: int = 2) -> dict:
    """Exactly what the Needs form posts by default, for the seeded rice product."""
    due = date.today() + timedelta(days=14)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": RICE,
            "quantity": quantity,
            "cadence_days": 30,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": 14,
            "routine_lead_days": 7,
            "min_savings_pct": 15,
            "max_spend_cents": 12000,
            "substitution": "exact_only",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _record(client: TestClient, key: str) -> dict:
    response = client.post("/api/demo/supplier-updates", json={"quote": key})
    assert response.status_code == 200, response.text
    return response.json()


def _assess(client: TestClient) -> coord.OpportunityAssessment:
    """The deterministic verdict at the most favourable public site — the same rule the
    member outlook reports at."""
    ctx = api.ctx_for("demo")
    best = None
    for site in ctx.repo.list_sites("demo"):
        if not site.is_public:
            continue
        a = coord.evaluate_opportunity(
            ctx=ctx, community_id=api.COMMUNITY_ID, product_id=RICE, pickup_site_id=site.id
        )
        if best is None or (a.viable, a.matched_units) > (best.viable, best.matched_units):
            best = a
    assert best is not None
    return best


def _outlook(client: TestClient, household_id: str) -> dict:
    me = client.get(f"/api/members/{household_id}").json()
    return next(o for o in me["needs_outlook"] if o["product_id"] == RICE)


def _snapshot(ws: str = "demo") -> str:
    """Every row in the workspace, as a stable string. Compares the whole store rather
    than a chosen list, so a write nobody thought to check is still caught."""
    store = api._repo.store(ws)
    return json.dumps(
        {
            name: [
                item.to_dict() if hasattr(item, "to_dict") else str(item)
                for item in (value.values() if isinstance(value, dict) else value)
            ]
            for name, value in sorted(vars(store).items())
        },
        sort_keys=True,
        default=str,
    )


# ------------------------------------------------------- the three verdicts


def test_with_no_quote_there_is_nothing_to_evaluate(client):
    _onboard(client)
    assessment = _assess(client)
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_NO_BULK_OFFER
    assert assessment.bulk_offer_id is None
    assert assessment.minimum_units == 0


def test_a_plausible_quote_can_still_be_refused(client):
    """The split-case quote clears every supply objection and loses on arithmetic.

    This is the case a scripted demo would not have. The supplier will sell, twelve bags
    is a minimum this community clears comfortably, the units land on whole cases — and
    once a fulfiller's pay, card processing and Pool's fee are counted the group pays
    more than its members would pay alone. So Pool does not act.
    """
    household = _onboard(client)
    _declare(client, household)
    _record(client, SPLIT)

    assessment = _assess(client)
    assert assessment.bulk_offer_id == su.QUOTES[SPLIT].offer_id
    # The first blocker is gone: supply is now known.
    assert assessment.reason_code != coord.REASON_NO_BULK_OFFER
    # And the answer is still no, for a reason the arithmetic produced.
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_NOT_CHEAPER
    assert assessment.economics is not None
    assert assessment.economics.net_savings_cents < 0
    assert assessment.economics.all_in_cents > assessment.economics.retail_baseline_cents
    # It got that far: demand cleared the minimum and filled whole cases.
    assert assessment.matched_units >= assessment.minimum_units
    assert assessment.economics.packages.surplus_units == 0

    # No pool, and the member is told the economic reason rather than the supply one.
    assert client.get("/api/state").json()["pools"] == []
    outlook = _outlook(client, household)
    assert outlook["state"] == relevance.OUTLOOK_NOT_WORTH_IT


def test_a_better_quote_makes_the_same_demand_viable(client):
    """Same seven declarations, same units, a different supplier fact."""
    household = _onboard(client)
    _declare(client, household)
    _record(client, PROGRAM)

    assessment = _assess(client)
    assert assessment.viable is True
    assert assessment.reason_code == coord.REASON_VIABLE
    assert assessment.bulk_offer_id == su.QUOTES[PROGRAM].offer_id

    economics = assessment.economics
    assert economics is not None
    units = sum(line.units for line in economics.lines)
    # Whole cases, nothing left over, and the arithmetic agrees with itself.
    assert economics.packages.surplus_units == 0
    assert units == economics.packages.cases * su.QUOTES[PROGRAM].case_units
    assert units >= su.QUOTES[PROGRAM].min_units
    assert economics.net_savings_cents > 0
    assert economics.all_in_cents < economics.retail_baseline_cents

    # The member who declared it is genuinely among the buyers, by lineage.
    assert household in {line.household_id for line in economics.lines}
    outlook = _outlook(client, household)
    assert outlook["state"] == relevance.OUTLOOK_READY


def test_the_better_tier_wins_when_both_quotes_are_on_file(client):
    """Two tiers coexist, and the selection is the evaluator's.

    The losing tier is still reported as considered, so the record shows a comparison was
    made rather than one offer being the only one Pool looked at.
    """
    household = _onboard(client)
    _declare(client, household)
    _record(client, SPLIT)
    _record(client, PROGRAM)

    assessment = _assess(client)
    assert assessment.viable is True
    assert assessment.bulk_offer_id == su.QUOTES[PROGRAM].offer_id
    considered = {t["offer_id"] for t in assessment.offers_considered}
    assert considered == {su.QUOTES[SPLIT].offer_id, su.QUOTES[PROGRAM].offer_id}
    # Every figure that reaches a human comes from the tier that won.
    won = next(
        t for t in assessment.offers_considered if t["offer_id"] == assessment.bulk_offer_id
    )
    assert won["unit_price_cents"] == su.QUOTES[PROGRAM].unit_price_cents
    assert assessment.minimum_units == su.QUOTES[PROGRAM].min_units


# ------------------------------------------------------- what may change


def test_recording_a_quote_changes_only_the_offer_table(client):
    """The causal claim, asserted rather than described.

    If anything other than an offer moved, "same people, same demand, changed supply
    fact" would not be a statement about this system.
    """
    household = _onboard(client)
    _declare(client, household)
    client.post("/api/agent/run", json={"trigger": "member_scan"})

    before = json.loads(_snapshot())
    _record(client, PROGRAM)
    after = json.loads(_snapshot())

    changed = {k for k in before if before[k] != after.get(k)}
    assert changed == {"offers"}, changed
    # And within offers, exactly one row appeared; none was edited or removed. The
    # retail baseline in particular is untouched, because a quote that quietly moved the
    # number the saving is measured against would prove nothing at all.
    assert {o["id"] for o in after["offers"]} - {o["id"] for o in before["offers"]} == {
        su.QUOTES[PROGRAM].offer_id
    }
    assert [o for o in before["offers"] if o not in after["offers"]] == []


def test_recording_a_quote_twice_does_not_double_the_supply(client):
    _onboard(client)
    _record(client, PROGRAM)
    first = len(api._repo.list_offers("demo"))
    _record(client, PROGRAM)
    assert len(api._repo.list_offers("demo")) == first


# ------------------------------------- history stays history, outlook moves


def test_the_old_run_report_still_says_what_that_run_found(client):
    """The historical/current distinction, which is the whole point of the sequence.

    A run that refused for want of a supplier refused correctly: there was no supplier.
    Rewriting its stored evaluation once one exists would destroy the only evidence that
    the world changed — and would be the agent editing its own past to agree with its
    present.
    """
    household = _onboard(client)
    _declare(client, household)

    run = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
    run_id = run["run_id"]
    before_report = client.get(
        f"/api/runs/{run_id}/report", params={"household_id": household}
    ).json()
    result = next(r for r in before_report["results"] if r["product_id"] == RICE)
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_NO_BULK_OFFER

    before_rows = [e.to_dict() for e in api._repo.list_run_evaluations("demo", run_id)]

    _record(client, SPLIT)
    _record(client, PROGRAM)

    # The stored evidence is byte-identical.
    after_rows = [e.to_dict() for e in api._repo.list_run_evaluations("demo", run_id)]
    assert after_rows == before_rows

    # And so is the report assembled from it.
    after_report = client.get(
        f"/api/runs/{run_id}/report", params={"household_id": household}
    ).json()
    assert after_report == before_report

    # Meanwhile the *current* outlook has moved on, and says so separately.
    assert _outlook(client, household)["state"] == relevance.OUTLOOK_READY


def test_the_outlook_moves_through_all_three_states_without_a_run(client):
    """No coordinator runs anywhere in this test. The outlook is a recomputation from
    current world state, not a memory of what an agent concluded."""
    household = _onboard(client)
    _declare(client, household)
    runs_before = len(api._repo.list_runs("demo", limit=100))

    assert _outlook(client, household)["state"] == relevance.OUTLOOK_NO_SUPPLY
    _record(client, SPLIT)
    assert _outlook(client, household)["state"] == relevance.OUTLOOK_NOT_WORTH_IT
    _record(client, PROGRAM)
    assert _outlook(client, household)["state"] == relevance.OUTLOOK_READY

    assert len(api._repo.list_runs("demo", limit=100)) == runs_before
    assert client.get("/api/state").json()["pools"] == []


def test_a_second_run_acts_on_the_changed_world_and_says_so(client):
    """The whole sequence, end to end, through the agent both times.

    First run: refused, no supplier. Quote recorded. Second run: the same declaration,
    unchanged, is now in an order — and every other buyer in it is somebody who had
    already declared rice before the visitor arrived. Nobody was recruited and no demand
    was injected; the only thing that happened in between was one supplier fact.
    """
    household = _onboard(client)
    need = _declare(client, household)
    needs_before = client.get("/api/needs").json()["needs"]

    first = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
    first_report = client.get(
        f"/api/runs/{first['run_id']}/report", params={"household_id": household}
    ).json()
    assert next(r for r in first_report["results"] if r["product_id"] == RICE)[
        "reason_code"
    ] == coord.REASON_NO_BULK_OFFER
    assert client.get("/api/state").json()["pools"] == []

    _record(client, PROGRAM)

    second = client.post("/api/agent/run", json={"trigger": "member_scan"}).json()
    second_report = client.get(
        f"/api/runs/{second['run_id']}/report", params={"household_id": household}
    ).json()
    result = next(r for r in second_report["results"] if r["need_id"] == need["need_id"])
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["units"] == 2

    # Same declarations, before and after. No demand was created to make this work.
    assert client.get("/api/needs").json()["needs"] == needs_before

    # The other buyers are the seeded households, not new ones.
    me = client.get(f"/api/members/{household}").json()
    detail = client.get(f"/api/pools/{me['opportunity']['pool_id']}").json()
    buyers = {m["household_id"] for m in detail["members"]}
    assert household in buyers
    assert len(buyers) > 1
    seeded_rice = {
        n["household_id"]
        for n in needs_before
        if n["product_id"] == RICE and n["household_id"] != household
    }
    assert buyers - {household} <= seeded_rice

    # And the first run's report is still the first run's report.
    assert client.get(
        f"/api/runs/{first['run_id']}/report", params={"household_id": household}
    ).json() == first_report


# ----------------------------------------------------------------- authority


def test_the_client_cannot_supply_any_economic_term(client):
    """A key is the entire input, and an attempt to send economics is *refused*.

    Refused rather than stripped, for the same reason a supplied agent ``instruction`` is
    refused rather than dropped: a silently ignored field looks like it worked, and the
    first person to notice would be somebody testing whether the price can be steered.
    """
    _onboard(client)
    response = client.post(
        "/api/demo/supplier-updates",
        json={
            "quote": PROGRAM,
            "unit_price_cents": 1,
            "min_units": 1,
            "case_units": 1,
            "product_id": "prod_whey_vanilla",
            "supplier_id": "sup_campusmart",
        },
    )
    assert response.status_code == 422, response.text
    # And nothing was written on the way to refusing.
    assert su.QUOTES[PROGRAM].offer_id not in {o.id for o in api._repo.list_offers("demo")}

    # The same key on its own lands the server's terms, which are not the caller's.
    _record(client, PROGRAM)
    offer = next(
        o for o in api._repo.list_offers("demo") if o.id == su.QUOTES[PROGRAM].offer_id
    )
    assert offer.unit_price_cents == su.QUOTES[PROGRAM].unit_price_cents
    assert offer.case_units == su.QUOTES[PROGRAM].case_units
    assert offer.min_units == su.QUOTES[PROGRAM].min_units
    assert offer.product_id == RICE
    assert offer.supplier_id == "sup_riverbend"


def test_an_unknown_quote_key_is_refused(client):
    _onboard(client)
    for key in ["", "made_up", "rice_split_case; drop", "prod_whey_vanilla"]:
        response = client.post("/api/demo/supplier-updates", json={"quote": key})
        assert response.status_code == 400, (key, response.status_code)
    assert [o for o in api._repo.list_offers("demo") if o.product_id == RICE
            and o.kind.value == "bulk"] == []


def test_the_quote_is_recorded_as_synthetic_not_as_verified(client):
    """The supplier does not exist and these terms were invented for a demo.

    ``manual_verified`` renders as a green chip on Operations meaning a human confirmed a
    real quote with a real supplier. Using it here would lend that provenance to an
    invented price, which is the confusion `OfferSource` exists to prevent.
    """
    _onboard(client)
    body = _record(client, SPLIT)
    assert body["source"] == "synthetic"
    assert body["synthetic"] is True
    offer = next(o for o in api._repo.list_offers("demo") if o.id == body["offer_id"])
    assert offer.is_synthetic is True
    assert offer.verified_at, "the moment it was recorded is genuinely known"


def test_a_recorded_quote_belongs_to_one_workspace(client):
    """Session isolation: a quote recorded by one visitor is not supply for another."""
    _onboard(client)
    _record(client, PROGRAM)
    assert su.QUOTES[PROGRAM].offer_id in {o.id for o in api._repo.list_offers("demo")}

    other = TestClient(api.app)
    other.get("/api/state", params={"workspace": "wother1234"})
    ids = {o.id for o in api._repo.list_offers("wother1234")}
    assert su.QUOTES[PROGRAM].offer_id not in ids


def test_reset_takes_the_recorded_quotes_away_again(client):
    """The demo has to be repeatable. Reset reseeds the partition, and the seeded world
    holds no bulk quote for this product — so the starting state is the starting state."""
    _onboard(client)
    _record(client, SPLIT)
    _record(client, PROGRAM)
    assert su.recorded_keys(api.ctx_for("demo")) == {SPLIT, PROGRAM}

    client.post("/api/demo/reset")
    assert su.recorded_keys(api.ctx_for("demo")) == set()
    assert _assess(client).reason_code == coord.REASON_NO_BULK_OFFER
