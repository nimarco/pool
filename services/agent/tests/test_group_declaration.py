"""Declaring the family, and still buying exactly one product.

The thesis is that Pool notices demand nobody organised. The default configuration
falsified it on its own headline example.

Twelve members who each buy some coffee, three units apiece, against a supplier minimum
of eighteen: thirty-six units of real, standing, independent demand — and no pool. Nine
of the twelve were discarded by ``domain.substitution`` as "member accepts the exact
product only" before timing or geography was consulted, because each had named a
different brand. The demand overlapped in every sense a person would mean and in none
that the matcher could use.

Nothing was wrong with the engine. ``STRUCTURED_CATEGORY_MATCH`` has always pooled a
whole substitute group, and the catalogue has always carried curated groups. What was
missing was a way for a member to *say* "I buy coffee" — so the only expressible
statement was "I buy this exact bag", and the interface then fragmented the demand it
existed to find.

``GROUP_DECLARED`` is that statement. Three properties are load-bearing, and each has a
test below:

* the family is what widens the match, and it is **curated** — a member cannot invent
  one, and the model never decides two products are close enough (§21);
* the pool still buys **one exact product**, chosen because a supplier will sell it;
* nothing was substituted, so nobody is told a substitute was accepted on their behalf,
  and nobody is asked to approve their own declaration.

Exact-only is untouched and remains the default for a member who names a product.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.data import catalog
from pool.data.seed import COMMUNITY_ID
from pool.domain.models import (
    CommunityMembership,
    Household,
    MembershipStatus,
    NeedDeclaration,
    SubstitutionPolicy,
    VerificationMethod,
    iso,
    utcnow,
)
from pool.domain.substitution import evaluate_compatibility
from pool.services import coordination as coord
from pool.services import discovery

from .conftest import LAT, LON, WS

SOURCEABLE_COFFEE = "prod_coffee_beans"
SITE = "site_northhall"
#: Real catalogue coffees, none of which Pool holds any offer for. The point of the
#: fixture: every one of these members is buying coffee, and no two agree on a brand.
OTHER_COFFEES = (
    "prod_0025500304076",   # Folgers Classic Roast
    "prod_0810063343040",   # Death Wish Dark Roast
)


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    return c


def _add_member(ctx, household_id: str, *, dlat: float = 0.001, dlon: float = 0.001):
    ctx.repo.put_household(
        WS,
        Household(
            id=household_id,
            display_name=household_id,
            lat=LAT + dlat,
            lon=LON + dlon,
            neighborhood="Campus core",
            synthetic=True,
        ),
    )
    ctx.repo.put_community_membership(
        WS,
        CommunityMembership(
            community_id=COMMUNITY_ID,
            household_id=household_id,
            status=MembershipStatus.VERIFIED,
            verification_method=VerificationMethod.DEMO,
            verified_at=iso(utcnow()),
        ),
    )


def _declare(
    ctx,
    need_id: str,
    household_id: str,
    product_id: str,
    *,
    quantity: int = 3,
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY,
) -> NeedDeclaration:
    due = date.today() + timedelta(days=12)
    need = NeedDeclaration(
        id=need_id,
        household_id=household_id,
        community_id=COMMUNITY_ID,
        product_id=product_id,
        quantity=quantity,
        cadence_days=30,
        expected_next_need_date=due,
        earliest_acceptable_purchase_date=due - timedelta(days=12),
        latest_acceptable_purchase_date=due,
        routine_lead_days=12,
        min_savings_pct=5,
        max_spend_cents=20_000,
        substitution=substitution,
    )
    ctx.repo.put_need(WS, need)
    return need


def _retire_seeded_coffee(ctx) -> None:
    """Isolate the fixture from the seeded coffee demand, which already works."""
    for need in ctx.repo.list_needs(WS):
        product = ctx.repo.get_product(WS, need.product_id)
        if product is not None and product.substitute_group == "coffee":
            need.active = False
            ctx.repo.put_need(WS, need)


def _twelve_coffee_drinkers(ctx, substitution: SubstitutionPolicy) -> None:
    """Twelve members, three units each, spread across three coffee brands."""
    _retire_seeded_coffee(ctx)
    brands = (SOURCEABLE_COFFEE, *OTHER_COFFEES)
    for i in range(12):
        hid = f"hh_group_{i:02d}"
        _add_member(ctx, hid, dlat=0.001 + i * 0.0001, dlon=0.001)
        product_id = brands[i % len(brands)]
        # Catalogue products are materialised on declaration in the ordinary path; this
        # fixture writes needs directly, so it does the same explicitly.
        if ctx.repo.get_product(WS, product_id) is None:
            entry = catalog.get(product_id)
            assert entry is not None, product_id
            ctx.repo.put_product(WS, entry.to_product())
        _declare(ctx, f"need_group_{i:02d}", hid, product_id, substitution=substitution)


# ------------------------------------------------------- the fragmentation itself


def test_exact_only_declarations_fragment_demand_that_actually_overlaps(seeded_ctx):
    """The baseline this exists to fix. Kept as a test because it is the argument.

    Thirty-six units of standing coffee demand, a minimum of eighteen, and no pool —
    entirely because twelve people who all buy coffee named three different bags.
    """
    _twelve_coffee_drinkers(seeded_ctx, SubstitutionPolicy.EXACT_ONLY)

    outcome = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id=SOURCEABLE_COFFEE,
        pickup_site_id=SITE,
    )

    assert outcome.viable is False
    assert outcome.reason_code == "below_minimum"
    # Four of twelve named the product Pool can source; the other eight are refused for
    # their policy, not for anything about the order.
    assert outcome.matched_units == 12
    assert outcome.minimum_units == 18
    rejections = {
        r.get("reason", "") for r in getattr(outcome, "rejected", []) or []
    }
    assert not rejections or any("exact product only" in r for r in rejections)


def test_declaring_the_family_is_what_makes_the_same_demand_actionable(seeded_ctx):
    """Same twelve members, same units, same supplier, same minimum. One field."""
    _twelve_coffee_drinkers(seeded_ctx, SubstitutionPolicy.GROUP_DECLARED)

    outcome = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id=SOURCEABLE_COFFEE,
        pickup_site_id=SITE,
    )

    assert outcome.viable is True, outcome.reason_code
    assert outcome.matched_units == 36
    assert outcome.minimum_units == 18
    # And it is still one exact product being bought.
    assert outcome.product_id == SOURCEABLE_COFFEE


def test_a_family_order_fills_whole_cases_and_leaves_no_surplus(seeded_ctx):
    """Invariant 6 does not get a discount for arriving through a new policy."""
    _twelve_coffee_drinkers(seeded_ctx, SubstitutionPolicy.GROUP_DECLARED)
    outcome = coord.evaluate_opportunity(
        ctx=seeded_ctx, community_id=COMMUNITY_ID,
        product_id=SOURCEABLE_COFFEE,
        pickup_site_id=SITE,
    )
    assert outcome.viable is True
    packages = outcome.economics.packages
    assert packages.surplus_units == 0
    assert packages.units_purchased % packages.case_units == 0
    assert packages.moq_met is True


# --------------------------------------------------------- authority stays curated


def test_a_family_declaration_combines_only_inside_its_curated_group(seeded_ctx):
    """The widening is the *group*, and the group is written by a human.

    A member who declares coffee has said nothing whatsoever about shampoo, and the
    structural gate is what guarantees it rather than a promise in the copy.
    """
    coffee = seeded_ctx.repo.get_product(WS, SOURCEABLE_COFFEE)
    assert coffee is not None
    need = _declare(
        seeded_ctx, "need_fam", "hh_fam", SOURCEABLE_COFFEE,
        substitution=SubstitutionPolicy.GROUP_DECLARED,
    )

    for entry in catalog.entries():
        if entry.substitute_group == "coffee" or not entry.substitute_group:
            continue
        verdict = evaluate_compatibility(
            target=entry.to_product(), candidate=coffee, need=need
        )
        assert verdict.compatible is False, entry.product_id
        assert verdict.reason == "different product family"


def test_a_product_with_no_curated_family_still_combines_with_nothing(seeded_ctx):
    """An unreviewed category must not become a family by being declared as one.

    The catalogue leaves ``substitute_group`` empty when nobody classified the row, and
    the group gate runs before the policy branch, so the loosest authority in the system
    is still narrower than an unclassified product.
    """
    lonely = catalog.get("prod_coffee_beans")
    assert lonely is not None
    unclassified = lonely.to_product()
    unclassified.id = "prod_unclassified"
    unclassified.substitute_group = ""
    need = _declare(
        seeded_ctx, "need_lonely", "hh_lonely", "prod_unclassified",
        substitution=SubstitutionPolicy.GROUP_DECLARED,
    )
    other = seeded_ctx.repo.get_product(WS, SOURCEABLE_COFFEE)
    assert other is not None
    verdict = evaluate_compatibility(target=other, candidate=unclassified, need=need)
    assert verdict.compatible is False


def test_exact_only_is_still_exact_only(seeded_ctx):
    """The new policy adds an option. It does not loosen the one that was there."""
    coffee = seeded_ctx.repo.get_product(WS, SOURCEABLE_COFFEE)
    other = catalog.get(OTHER_COFFEES[0])
    assert coffee is not None and other is not None
    need = _declare(
        seeded_ctx, "need_exact", "hh_exact", SOURCEABLE_COFFEE)
    verdict = evaluate_compatibility(
        target=other.to_product(), candidate=coffee, need=need
    )
    assert verdict.compatible is False
    assert verdict.reason == "member accepts the exact product only"


# ------------------------------------------------------------ nothing was substituted


def test_a_family_match_is_not_reported_as_a_substitution(seeded_ctx):
    """The distinction the ``requires_disclosure`` split exists for.

    Handing somebody Pike Place is a substitution only if they asked for something else.
    A member who declared *coffee* asked for this, so the interface owes them the name of
    what was bought — not an apology for swapping it.
    """
    coffee = seeded_ctx.repo.get_product(WS, SOURCEABLE_COFFEE)
    other = catalog.get(OTHER_COFFEES[0])
    assert coffee is not None and other is not None

    family = _declare(
        seeded_ctx, "need_g", "hh_g", OTHER_COFFEES[0],
        substitution=SubstitutionPolicy.GROUP_DECLARED,
    )
    substituting = _declare(
        seeded_ctx, "need_s", "hh_s", OTHER_COFFEES[0],
        substitution=SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH,
    )

    as_family = evaluate_compatibility(
        target=coffee, candidate=other.to_product(), need=family
    )
    as_substitute = evaluate_compatibility(
        target=coffee, candidate=other.to_product(), need=substituting
    )

    assert as_family.compatible and as_substitute.compatible
    assert as_family.requires_disclosure is False
    assert as_substitute.requires_disclosure is True
    # `is_exact` keeps reporting the product ids honestly in both cases, because it is
    # stored on the membership and has to keep meaning what it says.
    assert as_family.is_exact is False
    assert as_substitute.is_exact is False


def test_an_exact_match_discloses_nothing_and_says_so(seeded_ctx):
    coffee = seeded_ctx.repo.get_product(WS, SOURCEABLE_COFFEE)
    assert coffee is not None
    need = _declare(
        seeded_ctx, "need_x", "hh_x", SOURCEABLE_COFFEE)
    verdict = evaluate_compatibility(target=coffee, candidate=coffee, need=need)
    assert verdict.is_exact is True
    assert verdict.requires_disclosure is False


def test_a_family_declaration_does_not_need_the_member_to_approve_it(seeded_ctx):
    """Smart Join must not ask a question with only one answer.

    The standing substitution rule governs stand-ins for a product the member *named*.
    A family declaration names no product, so that rule has no subject — and asking
    "will you accept coffee for your coffee?" is the kind of notification this product
    exists to remove.
    """
    from pool.domain.models import AutonomyMode, AutonomyPolicy
    from pool.domain.policy import evaluate_smart_join

    policy = AutonomyPolicy(
        mode=AutonomyMode.SMART_JOIN,
        min_savings_pct=5,
        max_total_cost_cents=20_000,
        max_travel_minutes=30,
        substitution=SubstitutionPolicy.EXACT_ONLY,   # the strict standing default
    )
    need = _declare(
        seeded_ctx, "need_sj", "hh_sj", SOURCEABLE_COFFEE,
        substitution=SubstitutionPolicy.GROUP_DECLARED,
    )
    verdict = evaluate_smart_join(
        household_id="hh_sj",
        policy=policy,
        need=need,
        landed_cost_cents=1_500,
        net_savings_bps=1_500,
        travel_minutes=5,
        is_exact_product=False,       # a different bag in the same family
        substitution_authorised=True,
        pickup_is_public=True,
    )
    substitution_check = next(c for c in verdict.checks if c.rule == "substitution")
    assert substitution_check.passed is True
    assert substitution_check.detail == "member declared this product family"

    # And the same member, on a real substitution, is still asked.
    swapped = _declare(
        seeded_ctx, "need_sub", "hh_sj", OTHER_COFFEES[0],
        substitution=SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH,
    )
    asked = evaluate_smart_join(
        household_id="hh_sj",
        policy=policy,
        need=swapped,
        landed_cost_cents=1_500,
        net_savings_bps=1_500,
        travel_minutes=5,
        is_exact_product=False,
        substitution_authorised=True,
        pickup_is_public=True,
    )
    assert next(c for c in asked.checks if c.rule == "substitution").passed is False


# --------------------------------------------------------------- the declare path


def test_the_family_is_named_and_the_exemplar_is_looked_up(client):
    """A caller names the family. The product it stores is the server's business.

    So the authority a group declaration carries can only come from a family a human put
    in the catalogue — there is no field in which to widen it.
    """
    client.post(
        "/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me"}
    )
    household_id = client.get("/api/state").json()["consumer"]["household_id"]
    due = date.today() + timedelta(days=12)

    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "group": "coffee",
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": 11,
            "max_spend_cents": 9000,
        },
    )
    assert response.status_code == 200, response.text
    stored = response.json()
    assert stored["substitution"] == "group_declared"
    assert stored["product_id"] == catalog.group("coffee").exemplar_product_id
    # Read back authoritatively rather than trusting the write's own echo.
    listing = client.get("/api/needs").json()
    rows = listing["needs"] if isinstance(listing, dict) else listing
    mine = [r for r in rows if r["household_id"] == household_id]
    assert [r["substitution"] for r in mine] == ["group_declared"]


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({"group": "coffee", "product_id": "prod_coffee_beans"},
         "name a product or a product family, not both"),
        ({"group": "not_a_family"}, "unknown product family"),
        ({"product_id": "prod_coffee_beans", "substitution": "group_declared"},
         "declaring a product family means naming the family"),
        ({}, "name a product or a product family"),
    ],
)
def test_family_authority_cannot_be_claimed_sideways(client, payload, detail):
    """Every way of asking for family-wide authority without naming a family."""
    client.post(
        "/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me"}
    )
    household_id = client.get("/api/state").json()["consumer"]["household_id"]
    due = date.today() + timedelta(days=12)

    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": due.isoformat(),
            "max_spend_cents": 9000,
            **payload,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == detail


# ----------------------------------------------------------------- search surface


def test_typing_a_category_offers_the_family_first(client):
    """`coffee` is the commonest thing a person types, and it is a statement about
    coffee rather than a half-remembered brand."""
    body = client.get("/api/products/search", params={"q": "coffee"}).json()
    assert [g["group"] for g in body["groups"]] == ["coffee"]
    assert body["groups"][0]["label"] == "Coffee"
    assert body["groups"][0]["product_count"] == 26
    # The specific products are still all there. This adds a choice; it removes none.
    assert len(body["results"]) > 1
    assert SOURCEABLE_COFFEE in {r["product_id"] for r in body["results"]}


def test_a_family_is_sourceable_when_anything_in_it_is(client):
    """The honest reading of the flag for a family: the member is declaring the family,
    so what matters is whether Pool can buy *something* in it."""
    body = client.get("/api/products/search", params={"q": "coffee"}).json()
    assert body["groups"][0]["sourceable"] is True
    tea = client.get("/api/products/search", params={"q": "tea"}).json()
    assert tea["groups"][0]["group"] == "tea"
    assert tea["groups"][0]["sourceable"] is False


def test_naming_a_brand_offers_no_family(client):
    """Somebody typing a brand has told Pool which product they want. Offering them the
    family there would be the search widening their authority for them."""
    assert client.get(
        "/api/products/search", params={"q": "pike place"}
    ).json()["groups"] == []
    assert client.get(
        "/api/products/search", params={"q": "death wish"}
    ).json()["groups"] == []


def test_a_partial_word_is_still_typing_and_offers_no_family(client):
    """Group matching is whole-word on purpose. A product suggestion a member ignores is
    noise; a family suggestion they accept by mistake widens what Pool may buy."""
    assert client.get("/api/products/search", params={"q": "col"}).json()["groups"] == []


# ------------------------------------------------- discovery names a real target


def test_discovery_proposes_a_target_a_supplier_will_actually_sell(seeded_ctx):
    """Sourceability outranks demand when choosing a family's target.

    Ranking on demand alone named whichever product the family's declarations happened
    to favour, and ``evaluate_opportunity`` then refused it for ``no_retail_baseline`` —
    an opportunity for something no supplier sells. It was survivable while exact-only
    declarations were rare enough to be outvoted; a family declaration makes every
    member of the family compatible, so target choice decides the whole outcome.
    """
    _twelve_coffee_drinkers(seeded_ctx, SubstitutionPolicy.GROUP_DECLARED)
    listing = discovery.latent_demand(ctx=seeded_ctx, community_id=COMMUNITY_ID)
    coffee_rows = [
        row for row in listing["opportunities"]
        if (p := seeded_ctx.repo.get_product(WS, row["product_id"])) is not None
        and p.substitute_group == "coffee"
    ]
    assert coffee_rows, "the family's demand should be proposed at all"
    for row in coffee_rows:
        assert bool(coord.offers_for(seeded_ctx, row["product_id"])[1]), row["product_id"]
