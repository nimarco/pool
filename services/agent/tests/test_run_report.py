"""What a run wrote down, and what a member is told it found.

Two claims, tested together because one is worthless without the other:

**The facts survive the run.** A coordination run computes a great deal and used to keep
almost none of it — the complete tool results lived on an in-process object, and after an
AgentCore run that object is inside a microVM that no longer exists. These tests read the
evidence back through the repository, which is the only path both deployments share.

**The report describes that run.** Not current state, not a recomputation, and never a
product the run did not look at. "Investigated and declined" and "never investigated" are
different answers and a member gets the true one.
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
    return TestClient(api.app)


def _onboard(client: TestClient) -> str:
    client.get("/api/state")
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "smart_join"})
    client.post("/api/onboarding/payment-method")
    return client.get("/api/state").json()["consumer"]["household_id"]


def _declare(client, household_id, product_id, *, quantity=2, days=12, substitution="exact_only"):
    due = date.today() + timedelta(days=days)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "product_id": product_id,
            "quantity": quantity,
            "cadence_days": 40,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": min(days, 11),
            "routine_lead_days": min(days, 11),
            "min_savings_pct": 20,
            "max_spend_cents": 9000,
            "substitution": substitution,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, trigger="member_scan"):
    r = client.post("/api/agent/run", json={"trigger": trigger})
    assert r.status_code == 200, r.text
    return r.json()


def _report(client, run_id, household_id):
    r = client.get(f"/api/runs/{run_id}/report", params={"household_id": household_id})
    assert r.status_code == 200, r.text
    return r.json()


def _evaluations(run_id):
    return api._repo.list_run_evaluations("demo", run_id)


# ------------------------------------------------------------------ persistence


def test_a_run_writes_down_what_it_evaluated(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    stored = _evaluations(run["run_id"])
    assert stored, "the run recorded nothing it could later explain"
    whey = next(e for e in stored if e.product_id == "prod_whey_vanilla")
    assert whey.viable is True
    assert whey.run_id == run["run_id"]
    # The facts that make a formed order checkable, all read back from storage.
    assert whey.minimum_units > 0
    assert whey.selected_units >= whey.minimum_units
    assert whey.cases > 0
    assert whey.surplus_units == 0
    assert whey.current_units + whey.future_units > 0
    assert whey.pickup_site_name
    assert whey.net_savings_cents > 0
    assert whey.pool_id, "the evaluation is linked to the pool it produced"


def test_the_supplier_tiers_a_run_compared_are_recorded(client):
    """Whey has two bulk tiers. Which one won, and what lost to it, is one of the few
    genuinely interesting things a run establishes, and it existed nowhere durable."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    whey = next(e for e in _evaluations(run["run_id"]) if e.product_id == "prod_whey_vanilla")
    assert len(whey.offers_considered) == 2
    outcomes = {t["offer_id"]: t["outcome"] for t in whey.offers_considered}
    assert outcomes[whey.bulk_offer_id] == coord.TIER_SELECTED
    assert set(outcomes.values()) <= coord.TIER_OUTCOMES
    assert len([o for o in outcomes.values() if o == coord.TIER_SELECTED]) == 1


def test_a_refused_evaluation_is_recorded_with_its_reason_code(client):
    household = _onboard(client)
    _declare(client, household, "prod_paper_towels", quantity=2)
    run = _run(client)

    towels = next(e for e in _evaluations(run["run_id"]) if e.product_id == "prod_paper_towels")
    assert towels.viable is False
    assert towels.reason_code == coord.REASON_BELOW_MINIMUM
    assert 0 < towels.matched_units < towels.minimum_units


def test_evidence_survives_a_run_that_hit_a_safety_bound(client):
    """A run stopped by a bound still did real work first, and what it established is
    exactly what somebody will want to read afterwards.

    Driven through the coordinator rather than the endpoint because ``Settings`` is
    frozen — which is the right shape for a configuration object that decides how much
    money a run may spend.
    """
    import dataclasses

    from pool.agent.coordinator import PoolCoordinator
    from pool.config import AgentBounds

    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    bounded = dataclasses.replace(api._settings, bounds=AgentBounds(max_iterations=3))
    run = PoolCoordinator(
        api._repo, settings=bounded, routing=api._routing,
        payments=api._payments, purchaser=api._purchaser, sourcing=api._sourcing,
    ).run("demo", trigger="member_scan", community_id=api.COMMUNITY_ID)

    assert run.outcome.value == "loop_fault"
    assert api._repo.list_run_evaluations("demo", run.id), (
        "the bound erased the run's own findings"
    )
    assert run.objective_household_id == household


# ----------------------------------------------------------------- attribution


def test_a_report_is_refused_for_a_run_that_was_not_this_members(client):
    """The guard against a stale or foreign run becoming somebody's personal answer."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    community = _run(client, trigger="manual_scan")

    report = _report(client, community["run_id"], household)
    assert report["is_mine"] is False
    assert report["results"] == []
    # It still says what that run looked at — that is public, community-level fact.
    assert report["evaluated_product_ids"]


def test_a_newer_run_does_not_inherit_an_older_runs_findings(client):
    household = _onboard(client)
    _declare(client, household, "prod_paper_towels", quantity=2)
    first = _run(client)
    second = _run(client)

    assert first["run_id"] != second["run_id"]
    assert {e.run_id for e in _evaluations(first["run_id"])} == {first["run_id"]}
    assert {e.run_id for e in _evaluations(second["run_id"])} == {second["run_id"]}
    assert _report(client, second["run_id"], household)["run_id"] == second["run_id"]


def test_the_report_never_lists_a_product_the_run_did_not_evaluate(client):
    """The credibility rule. Detergent is a real seeded opportunity with a genuinely
    interesting refusal, and a report that claimed the run weighed it would be a lie."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    report = _report(client, run["run_id"], household)
    named = {r["product_id"] for r in report["results"]} | {
        r["product_id"] for r in report.get("also_evaluated", [])
    }
    assert "prod_detergent_pods" not in named
    assert named <= set(report["evaluated_product_ids"]) | {"prod_whey_vanilla"}


# --------------------------------------------------------------- result states


def test_a_formed_order_explains_itself_from_stored_facts(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    result = _report(client, run["run_id"], household)["results"][0]
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["units"] == 2
    assert result["pool_id"]
    assert result["is_exact_product"] is True
    assert len(result["facts"]) >= 4
    evaluation = next(
        e for e in _evaluations(run["run_id"]) if e.product_id == "prod_whey_vanilla"
    )
    # Every figure in the sentences is one the run stored, not one assembled here.
    assert f"{evaluation.minimum_units}-unit minimum" in " ".join(result["facts"])
    assert evaluation.pickup_site_name in " ".join(result["facts"])


def test_a_declined_need_keeps_its_declaration_and_says_the_numbers(client):
    household = _onboard(client)
    need = _declare(client, household, "prod_paper_towels", quantity=2)
    run = _run(client)

    result = _report(client, run["run_id"], household)["results"][0]
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_BELOW_MINIMUM
    assert "48" in result["headline"]
    assert any("stays standing" in f for f in result["facts"])
    assert any(
        n["need_id"] == need["need_id"] and n["active"]
        for n in client.get("/api/needs").json()["needs"]
    )


def test_bad_economics_reads_as_price_and_not_as_shortage(client):
    """"Not enough of you yet" is an invitation to wait. "This would cost you more" is
    not, and a member has to be able to tell them apart."""
    household = _onboard(client)
    _declare(client, household, "prod_detergent_pods", quantity=4)
    run = _run(client)

    result = _report(client, run["run_id"], household)["results"][0]
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] == coord.REASON_NOT_CHEAPER
    assert "cost" in result["headline"]


def test_an_unsourceable_product_says_there_is_no_supplier(client):
    household = _onboard(client)
    custom = client.post("/api/products/custom", json={"name": "Cardamom pods, 500g"}).json()
    _declare(client, household, custom["product_id"])
    run = _run(client)

    result = _report(client, run["run_id"], household)["results"][0]
    assert result["result"] == run_report.RESULT_DECLINED
    assert result["reason_code"] in {
        coord.REASON_NO_BULK_OFFER,
        coord.REASON_NO_RETAIL_BASELINE,
    }
    assert result["product_id"] == custom["product_id"]


def test_a_declaration_the_run_did_not_reach_says_so(client):
    """Four declarations, three taken on. The fourth is "not investigated", which is a
    different sentence from "not worth it" and must not be dressed as one."""
    household = _onboard(client)
    for i, product in enumerate(
        ["prod_whey_vanilla", "prod_coffee_beans", "prod_energy_drink", "prod_paper_towels"]
    ):
        _declare(client, household, product, quantity=2, days=10 + i)
    run = _run(client)

    results = _report(client, run["run_id"], household)["results"]
    deferred = [r for r in results if r["result"] == run_report.RESULT_NOT_INVESTIGATED]
    assert len(deferred) == 1
    assert deferred[0]["product_id"] == "prod_paper_towels"
    assert "did not look at this one" in deferred[0]["headline"]


def test_a_second_run_reports_the_pool_it_is_already_in_rather_than_re_deciding(client):
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    _run(client)
    second = _run(client)

    results = _report(client, second["run_id"], household)["results"]
    assert [r["result"] for r in results] == [run_report.RESULT_ALREADY_COORDINATED]
    assert results[0]["pool_id"]


def test_an_authorised_substitute_is_disclosed_in_the_report(client):
    household = _onboard(client)
    _declare(
        client,
        household,
        "prod_whey_chocolate",
        quantity=2,
        substitution="same_product_other_variant",
    )
    run = _run(client)

    result = _report(client, run["run_id"], household)["results"][0]
    assert result["result"] == run_report.RESULT_FORMED_INCLUDED
    assert result["product_id"] == "prod_whey_vanilla"
    assert result["is_exact_product"] is False
    assert result["declared_product_name"]


def test_a_pool_for_other_people_is_reported_separately_and_never_as_theirs(client):
    household = _onboard(client)
    _declare(client, household, "prod_paper_towels", quantity=2)
    _run(client, trigger="manual_scan")  # forms the community's whey pool
    run = _run(client)

    report = _report(client, run["run_id"], household)
    assert all(r["result"] != run_report.RESULT_FORMED_INCLUDED for r in report["results"])
    elsewhere = report["elsewhere"]
    assert [e["product_name"] for e in elsewhere]
    assert all(e["buyer_count"] > 0 for e in elsewhere)


# -------------------------------------------------------------------- privacy


def test_evidence_carries_no_contact_details_names_or_payment_references(client):
    """An evaluation touches every declaration in the Community. What it keeps must not
    become a readout of the neighbours (AGENTS.md §4)."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    blob = str([e.to_dict() for e in _evaluations(run["run_id"])])
    households = api._repo.list_households("demo")
    for member in households:
        assert member.contact_email not in blob
        if member.payment_method_ref:
            assert member.payment_method_ref not in blob
        if member.id != household:
            # Nobody else's display name, and no roster of who was excluded and why.
            assert member.id not in blob


def test_evidence_carries_no_model_text(client):
    """Structured domain facts only. No scratchpad, no narration, nothing the model
    wrote — the boundary between "AI decides what to investigate" and "deterministic
    code decides what is true" is the product (AGENTS.md §9)."""
    household = _onboard(client)
    _declare(client, household, "prod_whey_vanilla", quantity=2)
    run = _run(client)

    for evaluation in _evaluations(run["run_id"]):
        d = evaluation.to_dict()
        assert set(d) == {f for f in d}
        # The only free text is the deterministic evaluator's own one-line reason.
        text_fields = {k: v for k, v in d.items() if isinstance(v, str)}
        assert "I " not in text_fields.get("reason", "")
        assert len(text_fields.get("reason", "")) <= 300


def test_the_evaluation_record_is_bounded(client):
    """One button press must not be able to write an unbounded amount of storage."""
    from pool.agent import evidence
    from pool.domain.models import MAX_EVALUATION_NEED_VERDICTS, MAX_EVALUATION_TIERS

    household = _onboard(client)
    for i, product in enumerate(["prod_whey_vanilla", "prod_coffee_beans", "prod_energy_drink"]):
        _declare(client, household, product, quantity=2, days=10 + i)
    run = _run(client)

    stored = _evaluations(run["run_id"])
    assert len(stored) <= evidence.MAX_EVALUATIONS_PER_RUN
    for evaluation in stored:
        assert len(evaluation.offers_considered) <= MAX_EVALUATION_TIERS
        assert len(evaluation.need_verdicts) <= MAX_EVALUATION_NEED_VERDICTS


def test_a_declaration_with_two_targets_is_explained_by_the_order_that_formed(client):
    """One declaration, two sourceable targets, two different verdicts.

    ``coordination.sourceable_targets`` deliberately widens the search to the declared
    product *and* any permitted substitute Pool holds a bulk quote for, so a run can cost
    two products on one declaration's behalf. When one of them formed an order this
    member did not fit inside and the other simply had no demand, the report used to name
    whichever was evaluated first: "nobody near you has declared anything this order could
    be shared with" — true of the target with none, and no answer at all to what happened,
    on a screen also showing the order that did form.

    Latent in the shipped catalogue, where every substitute group holds exactly one
    bulk-quoted product. So the second offer is added here, which is what makes the case
    reachable and is the change that would make it real.
    """
    from pool.domain.models import MoqKind, Offer, OfferKind, iso, utcnow

    household = _onboard(client)
    # A bulk tier for chocolate whey that its own demand can never clear. Now a member
    # who authorises the same-brand variant has two targets: this one, and vanilla.
    api._repo.put_offer(
        "demo",
        Offer(
            id="off_choc_bulk",
            supplier_id="sup_bulkline",
            product_id="prod_whey_chocolate",
            kind=OfferKind.BULK,
            unit_price_cents=3000,
            case_units=12,
            moq_kind=MoqKind.UNITS,
            moq_amount=500,
            verified_at=iso(utcnow()),
        ),
    )
    # Needed far enough out that the case fitter prefers members whose whey is already
    # due, so the vanilla order forms without these units.
    _declare(
        client,
        household,
        "prod_whey_chocolate",
        quantity=3,
        days=40,
        substitution="same_product_other_variant",
    )

    run = _run(client)
    evaluated = {
        e.product_id: e for e in api._repo.list_run_evaluations("demo", run["run_id"])
    }
    # Both targets really were costed, and they really do disagree.
    assert set(evaluated) == {"prod_whey_chocolate", "prod_whey_vanilla"}
    assert evaluated["prod_whey_chocolate"].viable is False
    assert evaluated["prod_whey_chocolate"].pool_id == ""
    assert evaluated["prod_whey_vanilla"].pool_id

    result = _report(client, run["run_id"], household)["results"][0]

    assert result["result"] == run_report.RESULT_FORMED_EXCLUDED
    assert result["pool_id"] == evaluated["prod_whey_vanilla"].pool_id
    # The declaration is still the member's own product; the order names the one bought.
    assert result["product_id"] == "prod_whey_chocolate"
    assert "100% Whey Protein" in result["headline"]
    assert "not in this one" in result["headline"]
    assert any("Nothing was charged" in f for f in result["facts"])
    # And it is genuinely not theirs, by the same lineage every other surface reads.
    assert client.get(f"/api/members/{household}").json()["opportunity"] is None
