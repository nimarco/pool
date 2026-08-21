"""The ordinary member product, doing the thing the architecture claims.

Three phases built a causal chain — a typed policy, a bounded search, a durable event —
and none of it was reachable by using Pool. This is the phase where saving a declaration
is the only thing anybody does, and the tests here are about that boundary rather than
about the engine underneath it.

What is proved:

**The questions are the schema's and the answers are the server's.** A member is asked
about coffee, not about ``SubstitutionPolicy``; the dimensions come from the curated
family schema and the wording from the curated table beside it, and what an answer *means*
is decided in one place where every default is the narrowest reading. An omitted answer
can never widen a rule.

**Saving is the cause, and the only cause.** Not a button, not a page render, not a
reload, and not the same form submitted twice.

**Everything shown afterwards is stored.** The explanation and the proof are one server
read of the same rows, so a refresh cannot lose the story and no screen can invent one.

**The refusal is a first-class outcome.** A declaration Pool looked at and declined reads
as a considered answer with a deterministic reason, not as an error and not as silence.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.adapters.repository import InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.api import app as api
from pool.api import public_demo
from pool.data import product_facts as pf
from pool.data.roast_coffee_fixture import A_MEDIUM, C_DECAF, E_UNVERIFIED_ROAST
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import ParticipationState, SubstitutionPolicy
from pool.services import needs as needs_service
from pool.services.context import PoolContext

from .conftest import WS

VERIFY_WS = "wphase4demo01-verify"
PLAIN_WS = "wphase4demo01"


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def client() -> TestClient:
    api._repo.reset(VERIFY_WS)
    api._repo.reset(PLAIN_WS)
    return TestClient(api.app)


def onboard(client: TestClient, ws: str = VERIFY_WS) -> str:
    client.get(f"/api/state?workspace={ws}")
    client.post(
        f"/api/onboarding?workspace={ws}",
        json={"display_name": "Judge", "autonomy_mode": "smart_join"},
    )
    return client.get(f"/api/state?workspace={ws}").json()["consumer"]["household_id"]


def declare(
    client: TestClient,
    household_id: str,
    *,
    ws: str = VERIFY_WS,
    product_id: str = A_MEDIUM,
    quantity: int = 3,
    preferences: dict | None = None,
):
    body = {
        "household_id": household_id,
        "product_id": product_id,
        "quantity": quantity,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "flexibility_days": 11,
        "max_spend_cents": 20_000,
    }
    if preferences is not None:
        body["preferences"] = preferences
    return client.post(f"/api/needs?workspace={ws}", json=body)


SIMILAR = {
    "flexibility": "similar",
    "keep": ["form", "caffeine"],
    "accept": {"roast": ["MEDIUM", "DARK"]},
}


def ctx_for(ws: str = VERIFY_WS) -> PoolContext:
    return PoolContext(
        repo=api._repo, ws=ws, routing=CachingRouting(DeterministicRouting(max_cells=400))
    )


# ------------------------------------------------------- the isolated coffee world


def test_the_coffee_community_exists_only_where_it_was_asked_for(client):
    """Two partitions, one seed, one extra fixture — and the canonical world untouched."""
    client.get(f"/api/state?workspace={VERIFY_WS}")
    client.get(f"/api/state?workspace={PLAIN_WS}")

    verify = {p.id for p in api._repo.list_products(VERIFY_WS)}
    plain = {p.id for p in api._repo.list_products(PLAIN_WS)}
    curated = {p.id for p in pf.PRODUCTS}

    assert curated <= verify
    assert not (curated & plain)
    # The canonical seed is underneath it, not replaced by it.
    assert "prod_whey_vanilla" in verify and "prod_rice_jasmine" in verify


def test_the_visitors_own_coffee_declaration_is_not_pre_made(client):
    """The interesting state transition has to be caused by them, not found by them."""
    household_id = onboard(client)
    needs = client.get(f"/api/needs?workspace={VERIFY_WS}").json()["needs"]
    mine = [n for n in needs if n["household_id"] == household_id]
    assert mine == []
    # And no order is waiting for them either.
    assert client.get(f"/api/state?workspace={VERIFY_WS}").json()["pools"] == []


def test_seeding_a_workspace_never_runs_the_agent(client):
    """Bootstrap writes a hundred rows and must not buy a model call for any of them."""
    client.get(f"/api/state?workspace={VERIFY_WS}")
    client.get(f"/api/map?workspace={VERIFY_WS}")
    client.get(f"/api/needs?workspace={VERIFY_WS}")
    assert api._repo.list_runs(VERIFY_WS) == []
    assert api._repo.list_coordination_events(VERIFY_WS) == []


# ------------------------------------------------- the questions and what they mean


def test_the_questions_come_from_the_curated_schema(client):
    client.get(f"/api/state?workspace={VERIFY_WS}")
    body = client.get(
        f"/api/products/{A_MEDIUM}/preferences?workspace={VERIFY_WS}"
    ).json()

    assert body["family"] == pf.FAMILY
    assert body["schema_version"] == pf.SCHEMA_VERSION
    assert [q["attribute"] for q in body["questions"]] == ["form", "caffeine", "roast"]
    # Consumer words, not tokens. The member never meets WHOLE_BEAN.
    prompts = " ".join(q["prompt"] for q in body["questions"])
    assert "whole bean" in prompts and "caffeinated" in prompts
    for token in ("WHOLE_BEAN", "CAFFEINATED", "attribute_constrained", "substitute_group"):
        assert token not in prompts


def test_a_product_with_an_unverified_fact_is_not_asked_about_it(client):
    """Asking somebody to insist on a value Pool cannot establish would be asking them
    to guess, and would build a rule that refuses everything."""
    client.get(f"/api/state?workspace={VERIFY_WS}")
    body = client.get(
        f"/api/products/{E_UNVERIFIED_ROAST}/preferences?workspace={VERIFY_WS}"
    ).json()
    assert [q["attribute"] for q in body["questions"]] == ["form", "caffeine"]


def test_a_product_outside_a_curated_family_is_asked_nothing(client):
    client.get(f"/api/state?workspace={VERIFY_WS}")
    body = client.get(
        f"/api/products/prod_rice_jasmine/preferences?workspace={VERIFY_WS}"
    ).json()
    assert body["questions"] == []
    assert body["family"] == ""


@pytest.mark.parametrize(
    ("answers", "expected_policy", "expected_requires"),
    [
        # Exact-only is the default and produces no attribute policy at all.
        ({"flexibility": "exact", "keep": [], "accept": {}}, "exact_only", None),
        # "Similar is fine" with nothing else said: everything the product already is.
        (
            {"flexibility": "similar", "keep": [], "accept": {}},
            "attribute_constrained",
            {"caffeine": ["CAFFEINATED"], "form": ["WHOLE_BEAN"], "roast": ["MEDIUM"]},
        ),
        # The canonical member: whole bean, caffeinated, medium or dark.
        (
            SIMILAR,
            "attribute_constrained",
            {
                "caffeine": ["CAFFEINATED"],
                "form": ["WHOLE_BEAN"],
                "roast": ["DARK", "MEDIUM"],
            },
        ),
        # Dropping a requirement has to be said out loud, and then it is honoured.
        (
            {"flexibility": "similar", "keep": ["form"], "accept": {"caffeine": [], "roast": ["MEDIUM"]}},
            "attribute_constrained",
            {"form": ["WHOLE_BEAN"], "roast": ["MEDIUM"]},
        ),
    ],
)
def test_every_answer_maps_to_exactly_one_policy(
    client, answers, expected_policy, expected_requires
):
    household_id = onboard(client)
    stored = declare(client, household_id, preferences=answers).json()

    assert stored["substitution"] == expected_policy
    if expected_requires is None:
        assert stored["attribute_policy"] is None
    else:
        assert stored["attribute_policy"]["requires"] == expected_requires
        assert stored["attribute_policy"]["family"] == pf.FAMILY
        assert stored["attribute_policy"]["excludes"] == {}


def test_silence_never_widens_a_rule(client):
    """The property the whole mapping exists for.

    A member who says "similar is fine" and answers nothing else gets the narrowest rule
    that can be written — everything about the product they picked, kept. Widening is
    something they do, one control at a time.
    """
    household_id = onboard(client)
    silent = declare(
        client, household_id, preferences={"flexibility": "similar", "keep": [], "accept": {}}
    ).json()
    assert silent["attribute_policy"]["requires"]["roast"] == ["MEDIUM"]
    assert silent["attribute_policy"]["requires"]["form"] == ["WHOLE_BEAN"]
    assert silent["attribute_policy"]["requires"]["caffeine"] == ["CAFFEINATED"]


def test_answers_and_a_raw_policy_cannot_both_be_sent(client):
    """Two sources for one permission is one too many."""
    household_id = onboard(client)
    response = client.post(
        f"/api/needs?workspace={VERIFY_WS}",
        json={
            "household_id": household_id,
            "product_id": A_MEDIUM,
            "quantity": 3,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "max_spend_cents": 20_000,
            "preferences": SIMILAR,
            "constraint": {
                "family": pf.FAMILY,
                "schema_version": pf.SCHEMA_VERSION,
                "requires": {"form": ["GROUND"]},
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "send the answers or the policy, not both"


@pytest.mark.parametrize(
    "answers",
    [
        {"flexibility": "whatever", "keep": [], "accept": {}},
        {"flexibility": "similar", "keep": [], "accept": {f"a{i}": ["X"] for i in range(20)}},
        {"flexibility": "similar", "keep": [], "accept": {"roast": ["X"] * 40}},
    ],
)
def test_a_malformed_answer_is_refused(client, answers):
    household_id = onboard(client)
    assert declare(client, household_id, preferences=answers).status_code == 400


def test_an_answer_about_a_dimension_this_product_has_no_fact_for_is_ignored_safely(client):
    """Not silently honoured, and not a crash. The questions are the offered set."""
    household_id = onboard(client)
    stored = declare(
        client,
        household_id,
        product_id=E_UNVERIFIED_ROAST,
        preferences={"flexibility": "similar", "keep": [], "accept": {"roast": ["LIGHT"]}},
    ).json()
    assert "roast" not in stored["attribute_policy"]["requires"]
    assert set(stored["attribute_policy"]["requires"]) == {"form", "caffeine"}


# ------------------------------------------------------------- saving is the cause


def test_saving_a_declaration_is_the_only_thing_that_causes_a_run(client):
    household_id = onboard(client)
    assert api._repo.list_runs(VERIFY_WS) == []

    saved = declare(client, household_id, preferences=SIMILAR).json()
    assert saved["coordination"]["status"] == "completed"
    assert len(api._repo.list_runs(VERIFY_WS)) == 1

    # Reading anything, repeatedly, causes nothing.
    for _ in range(3):
        client.get(f"/api/state?workspace={VERIFY_WS}")
        client.get(f"/api/needs?workspace={VERIFY_WS}")
        client.get(f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}")
    assert len(api._repo.list_runs(VERIFY_WS)) == 1


def test_the_same_declaration_twice_causes_one_run(client):
    household_id = onboard(client)
    declare(client, household_id, preferences=SIMILAR)
    duplicate = declare(client, household_id, preferences=SIMILAR)

    assert duplicate.status_code == 400
    assert len(api._repo.list_runs(VERIFY_WS)) == 1
    assert len(api._repo.list_coordination_events(VERIFY_WS)) == 1


def test_an_unchanged_edit_causes_nothing_and_a_real_one_causes_a_look(client):
    household_id = onboard(client)
    saved = declare(client, household_id, preferences=SIMILAR).json()
    need_id = saved["need_id"]
    first_event = saved["coordination"]["event_id"]

    body = {
        "household_id": household_id,
        "product_id": A_MEDIUM,
        "quantity": 3,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "flexibility_days": 11,
        "max_spend_cents": 20_000,
        "preferences": SIMILAR,
    }
    same = client.post(f"/api/needs/{need_id}?workspace={VERIFY_WS}", json=body).json()
    assert same["coordination"]["event_id"] == first_event
    assert len(api._repo.list_coordination_events(VERIFY_WS)) == 1

    changed = client.post(
        f"/api/needs/{need_id}?workspace={VERIFY_WS}", json={**body, "quantity": 4}
    ).json()
    assert changed["coordination"]["event_id"] != first_event
    assert len(api._repo.list_coordination_events(VERIFY_WS)) == 2


def test_declaring_outside_the_verification_world_records_but_does_not_run(client):
    """The cost decision, checked. Every other workspace records the event and stops."""
    household_id = onboard(client, ws=PLAIN_WS)
    # The plain workspace has no curated coffee, so declare something it does have.
    saved = declare(
        client, household_id, ws=PLAIN_WS, product_id="prod_rice_jasmine", preferences=None
    ).json()
    assert saved["coordination"]["status"] == "pending"
    assert api._repo.list_runs(PLAIN_WS) == []


# -------------------------------------------------------------- what the member gets


@pytest.fixture
def declared(client):
    household_id = onboard(client)
    saved = declare(client, household_id, preferences=SIMILAR).json()
    return client, household_id, saved


def test_the_order_that_forms_is_provisional_and_includes_them(declared):
    client, household_id, saved = declared
    pool_id = saved["coordination"]["pool_id"]
    assert pool_id

    memberships = api._repo.list_memberships(VERIFY_WS, pool_id)
    assert household_id in {m.household_id for m in memberships}
    assert {m.state for m in memberships} == {ParticipationState.PROVISIONAL}
    # Nothing was charged, authorised, or even asked for.
    assert api._repo.list_payments(VERIFY_WS, pool_id) == []
    assert api._repo.get_host_assignment(VERIFY_WS, pool_id) is None


def test_the_order_is_the_one_the_evaluator_adapted_to(declared):
    """Kestrel refused, Harbourstone formed — the Phase 3 result, reached by a member."""
    client, _household_id, saved = declared
    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    ).json()

    verdicts = {v["product"].split(" Whole")[0]: v for v in explained["investigated"]}
    assert verdicts["Kestrel Roastworks"]["viable"] is False
    assert verdicts["Kestrel Roastworks"]["blocker_code"] == "not_cheaper"
    assert verdicts["Harbourstone Coffee"]["viable"] is True
    assert explained["order"]["product"].startswith("Harbourstone")
    assert explained["order"]["surplus_units"] == 0
    assert (
        explained["order"]["cases"] * explained["order"]["case_units"]
        == explained["order"]["units"]
    )


def test_the_member_is_never_told_a_substitute_was_accepted(declared):
    """They named a rule, and this satisfies it. An apology would be for doing what they
    asked (§21)."""
    client, household_id, _saved = declared
    member = client.get(f"/api/members/{household_id}?workspace={VERIFY_WS}").json()
    opportunity = member["opportunity"]
    assert opportunity["is_exact_product"] is False
    assert opportunity["substitution_disclosed"] is False


def test_a_member_who_named_one_bag_and_got_another_is_still_told(declared):
    """The other half of the rule, checked on somebody in the same order.

    The allowlist member declared the light roast and their list admits the dark one, so
    what they are getting genuinely *is* a stand-in for what they typed — and the
    interface owes them that sentence. Same order, same code path, opposite answer.
    """
    client, _household_id, _saved = declared
    from pool.services import relevance

    ctx = ctx_for()
    theirs = relevance.personal_pool(ctx, COMMUNITY_ID, "hh_rc_delgado")
    assert theirs is not None
    projected = theirs.to_dict()
    assert projected["is_exact_product"] is False
    assert projected["substitution_disclosed"] is True
    assert projected["declared_product_name"]


# ------------------------------------------------------------- the explanation


def test_the_explanation_is_the_same_run_at_two_levels_of_detail(declared):
    client, _household_id, saved = declared
    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    ).json()

    assert explained["event"]["event_id"] == saved["coordination"]["event_id"]
    assert explained["run"]["run_id"] == saved["coordination"]["run_id"]
    assert explained["order"]["pool_id"] == saved["coordination"]["pool_id"]
    assert [t["name"] for t in explained["run"]["tool_calls"]] == [
        "list_cohort_strategies",
        "evaluate_cohort_strategy",
        "evaluate_cohort_strategy",
        "create_candidate_pool_from_strategy",
    ]
    assert explained["run"]["model_provider"] == "offline"
    assert explained["run"]["bounds"]["max_strategy_evaluations"] == 3
    assert explained["not_yet"] == {
        "host_accepted": False,
        "final_price_issued": False,
        "card_authorised": False,
        "purchased": False,
    }


def test_the_explanation_survives_a_reload(declared):
    client, _household_id, saved = declared
    path = f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    first = client.get(path).json()
    client.get(f"/api/state?workspace={VERIFY_WS}")
    second = client.get(path).json()
    first["run"].pop("duration_ms", None)
    second["run"].pop("duration_ms", None)
    assert first == second


def test_the_explanation_names_no_one(declared):
    client, _household_id, saved = declared
    blob = json.dumps(
        client.get(
            f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
        ).json()
    )
    households = api._repo.list_households(VERIFY_WS)
    for secret in (
        {h.display_name for h in households}
        | {h.contact_email for h in households if h.contact_email}
        | {h.id for h in households}
    ):
        assert secret not in blob, secret
    assert "lat" not in blob and "lon" not in blob


def test_exclusions_are_counted_and_not_listed(declared):
    client, _household_id, saved = declared
    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    ).json()
    assert explained["exclusion_codes"]
    assert all(isinstance(v, int) for v in explained["exclusion_codes"].values())


def test_a_declaration_nobody_has_looked_at_says_so(client):
    household_id = onboard(client, ws=PLAIN_WS)
    saved = declare(
        client, household_id, ws=PLAIN_WS, product_id="prod_rice_jasmine"
    ).json()
    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={PLAIN_WS}"
    ).json()
    assert explained["event"]["status"] == "pending"
    assert explained["run"] is None
    assert explained["order"] is None


# --------------------------------------------------------------------- refusal


def test_a_declaration_pool_declines_stays_a_considered_answer(client):
    """Not an error screen, not silence. Four bags of decaf against an 18-bag minimum."""
    household_id = onboard(client)
    saved = declare(
        client,
        household_id,
        product_id=C_DECAF,
        quantity=2,
        preferences={"flexibility": "exact", "keep": [], "accept": {}},
    ).json()

    assert saved["coordination"]["status"] == "completed"
    assert saved["coordination"]["outcome"] == "no_action"
    assert saved["coordination"]["pool_id"] == ""
    assert api._repo.list_pools(VERIFY_WS) == []

    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    ).json()
    assert [v["blocker_code"] for v in explained["investigated"]] == ["below_minimum"]
    assert explained["order"] is None


def test_an_order_that_would_leave_the_member_out_is_not_formed_as_theirs(client):
    """Two bags cannot land on a six-bag case boundary in this community.

    The order remains perfectly viable for the neighbours, and the member-scoped rule
    refuses to present it as an answer to the person who asked (§8). The honest outcome is
    no action, and the explanation says which option was refused and why.
    """
    household_id = onboard(client)
    saved = declare(client, household_id, quantity=2, preferences=SIMILAR).json()

    assert saved["coordination"]["outcome"] == "no_action"
    assert api._repo.list_pools(VERIFY_WS) == []
    explained = client.get(
        f"/api/needs/{saved['need_id']}/coordination?workspace={VERIFY_WS}"
    ).json()
    # Harbourstone was found viable for the Community, and still no order formed.
    assert any(v["viable"] for v in explained["investigated"])
    assert explained["order"] is None


# ------------------------------------------------------- the public safety surface


def test_the_browser_cannot_dispatch_an_arbitrary_event(client):
    """Auto-dispatch removes the need, so the general dispatcher is not exposed.

    A public caller with a guessed event id would otherwise be able to spend a model call
    on it, for no product benefit at all.
    """
    assert "/api/events" not in public_demo.ALLOWED_GET
    assert not any(p.match("/api/events") for p in public_demo.ALLOWED_GET_PATTERNS)
    assert "/api/events/cev_anything/dispatch" not in public_demo.ALLOWED_POST
    assert not any(
        p.match("/api/events/cev_anything/dispatch")
        for p in public_demo.ALLOWED_POST_PATTERNS
    )
    # And the door really is shut, not merely absent from a list.
    assert client.post(f"/api/events/cev_x/dispatch?workspace={VERIFY_WS}").status_code == 404


def test_the_two_new_reads_are_the_minimum_and_are_safe(client):
    """Both are pure reads over the caller's own workspace, and both are on the list."""

    def allowed(path: str) -> bool:
        return any(p.match(path) for p in public_demo.ALLOWED_GET_PATTERNS)

    assert allowed(f"/api/products/{A_MEDIUM}/preferences")
    assert allowed("/api/needs/need_x/coordination")
    # Reads, proved by their effect rather than by their name: neither writes a row.
    client.get(f"/api/state?workspace={VERIFY_WS}")
    before = len(api._repo.list_coordination_events(VERIFY_WS)), len(
        api._repo.list_runs(VERIFY_WS)
    )
    client.get(f"/api/products/{A_MEDIUM}/preferences?workspace={VERIFY_WS}")
    client.get(f"/api/needs/need_missing/coordination?workspace={VERIFY_WS}")
    assert before == (
        len(api._repo.list_coordination_events(VERIFY_WS)),
        len(api._repo.list_runs(VERIFY_WS)),
    )


def test_a_verification_workspace_is_a_partition_a_stranger_cannot_guess(client):
    assert public_demo.is_verify_workspace(VERIFY_WS)
    assert not public_demo.is_verify_workspace(PLAIN_WS)
    # Derived from the session, and idempotent, exactly as the showcase suffix is.
    assert public_demo.verify_workspace(PLAIN_WS) == VERIFY_WS
    assert public_demo.verify_workspace(VERIFY_WS) == VERIFY_WS
    # And it can never collide with the showcase partition for the same session.
    assert public_demo.showcase_workspace(PLAIN_WS) != VERIFY_WS


# --------------------------------------------------------------- nothing else moved


def test_the_canonical_seed_is_still_the_canonical_seed():
    repo = InMemoryRepository()
    seed(repo, WS)
    products = {p.id for p in repo.list_products(WS)}
    assert not (products & {p.id for p in pf.PRODUCTS})
    rice = [n for n in repo.list_needs(WS) if n.product_id == "prod_rice_jasmine"]
    assert len({n.household_id for n in rice}) == 6
    assert sum(n.quantity for n in rice) == 22


def test_declaring_without_answers_behaves_exactly_as_it_did(client):
    """Every path that existed before this phase still sends what it always sent."""
    household_id = onboard(client, ws=PLAIN_WS)
    stored = client.post(
        f"/api/needs?workspace={PLAIN_WS}",
        json={
            "household_id": household_id,
            "product_id": "prod_rice_jasmine",
            "quantity": 4,
            "cadence_days": 45,
            "expected_next_need_date": (date.today() + timedelta(days=14)).isoformat(),
            "max_spend_cents": 9000,
            "substitution": "structured_category_match",
        },
    ).json()
    assert stored["substitution"] == "structured_category_match"
    assert stored["attribute_policy"] is None


def test_search_finds_a_communitys_own_products_without_touching_the_snapshot(client):
    """The curated coffee is in one workspace and in no catalogue, and a member of that
    community still has to be able to declare it."""
    client.get(f"/api/state?workspace={VERIFY_WS}")
    client.get(f"/api/state?workspace={PLAIN_WS}")

    found = client.get(
        f"/api/products/search?q=Kestrel&workspace={VERIFY_WS}"
    ).json()["results"]
    assert {r["product_id"] for r in found} == {
        "prod_rc_kestrel_medium",
        "prod_rc_kestrel_light",
    }
    # And nowhere else, because the snapshot does not carry them.
    assert client.get(
        f"/api/products/search?q=Kestrel&workspace={PLAIN_WS}"
    ).json()["results"] == []
    # The snapshot's own ranking is untouched.
    whey = client.get(
        f"/api/products/search?q=vanilla whey&workspace={PLAIN_WS}"
    ).json()["results"]
    assert whey[0]["product_id"] == "prod_whey_vanilla"


def test_the_preference_mapping_is_a_pure_function_of_stored_state(client):
    """No clock, no randomness, no request. The same answers give the same policy."""
    client.get(f"/api/state?workspace={VERIFY_WS}")
    ctx = ctx_for()
    answers = needs_service.PreferenceAnswers(
        flexibility=needs_service.Flexibility.SIMILAR,
        keep=("form", "caffeine"),
        accept={"roast": ("MEDIUM", "DARK")},
    )
    first = needs_service.policy_from_answers(ctx, A_MEDIUM, answers)
    second = needs_service.policy_from_answers(ctx, A_MEDIUM, answers)
    assert first == second
    assert first[0] is SubstitutionPolicy.ATTRIBUTE_CONSTRAINED
