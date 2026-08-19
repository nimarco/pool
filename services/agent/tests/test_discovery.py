"""Discovery and evaluation must agree about who counts as demand.

The bug this file exists to stop: latent-demand discovery bucketed declarations by
substitute *group* and reported the whole bucket as the demand behind the group's
largest product. The matcher then applied each member's own substitution policy and
rejected some of them. So a visitor who declared one coffee **exact-only** inflated the
apparent supply for a different coffee — the listing proposed an opportunity, and the
evaluation it led to found fewer units than the listing had promised.

The invariant, stated once:

    a declaration contributes to the actionable demand estimate for product X only if
    ``domain.substitution`` — the same pure function the matcher calls — would let X
    serve it.

Both halves therefore read one implementation. These tests check the two halves against
each other for every substitution shape the model supports, rather than checking either
against a number written here.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

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
from pool.services import coordination as coord
from pool.services import discovery

from .conftest import LAT, LON, WS

COFFEE = "prod_coffee_beans"


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
    quantity: int = 6,
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY,
    active: bool = True,
    approved_brands: tuple[str, ...] = (),
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
        substitution=substitution,
        approved_brands=list(approved_brands),
        active=active,
    )
    ctx.repo.put_need(WS, need)
    return need


def _other_coffee(ctx, product_id: str = "prod_other_coffee", brand: str = "Death Wish"):
    """A real catalogue-shaped coffee Pool holds no bulk quote for."""
    from pool.domain.models import Product

    product = Product(
        product_id, f"{brand} Dark Roast", "beverage", "bag", "coffee", brand=brand
    )
    ctx.repo.put_product(WS, product)
    return product


def _listed(ctx, product_id: str, objective=None) -> dict:
    for row in discovery.latent_demand(ctx, COMMUNITY_ID, objective)["opportunities"]:
        if row["product_id"] == product_id:
            return row
    raise AssertionError(f"{product_id} not in the listing")


def _matcher_units(ctx, product_id: str) -> int:
    """The units the *evaluation* finds, across every public site in the Community.

    The union rather than one site's answer, because discovery does not decide
    geography — so comparing at a single site would compare two different questions.
    """
    seen: dict[str, int] = {}
    for site in ctx.repo.list_sites(WS):
        if not site.is_public:
            continue
        assessment = coord.evaluate_opportunity(
            ctx=ctx, community_id=COMMUNITY_ID, product_id=product_id, pickup_site_id=site.id
        )
        for candidate in assessment.candidates:
            seen[candidate.need_id] = candidate.units
    return sum(seen.values())


# ------------------------------------------------------------------- the drift


def test_an_exact_only_declaration_for_another_brand_inflates_nothing(seeded_ctx):
    """The reported case, in its general form.

    Somebody declares a coffee Pool cannot source and will accept nothing else. They are
    interested in coffee; their standing authority cannot be used for the coffee Pool
    *can* source, and the estimate must not imply otherwise.
    """
    _other_coffee(seeded_ctx)
    _add_member(seeded_ctx, "hh_deathwish")
    _declare(
        seeded_ctx,
        "need_deathwish",
        "hh_deathwish",
        "prod_other_coffee",
        quantity=9,
        substitution=SubstitutionPolicy.EXACT_ONLY,
    )

    row = _listed(seeded_ctx, COFFEE)
    assert row["unserved_units"] == _matcher_units(seeded_ctx, COFFEE)
    # The interest is still visible — under its own name, as the wider category.
    assert row["group_interest_units"] == row["unserved_units"] + 9
    assert row["group_interest_members"] == row["member_count"] + 1


def test_an_authorised_substitute_does_count(seeded_ctx):
    """The mirror image. A member who explicitly allowed this brand is real supply, and
    excluding them would understate the opportunity just as badly."""
    product = _other_coffee(seeded_ctx)
    sourceable = seeded_ctx.repo.get_product(WS, COFFEE)
    # Same substitute group already; the member names the brand Pool can source.
    _add_member(seeded_ctx, "hh_flexible")
    _declare(
        seeded_ctx,
        "need_flexible",
        "hh_flexible",
        product.id,
        quantity=9,
        substitution=SubstitutionPolicy.APPROVED_BRANDS,
        approved_brands=(sourceable.brand,),
    )

    row = _listed(seeded_ctx, COFFEE)
    assert row["unserved_units"] == _matcher_units(seeded_ctx, COFFEE)
    assert "need_flexible" in {
        c.need_id
        for c in coord.evaluate_opportunity(
            ctx=seeded_ctx,
            community_id=COMMUNITY_ID,
            product_id=COFFEE,
            pickup_site_id="site_union",
        ).candidates
    }


def test_a_retired_declaration_contributes_nothing_to_the_estimate(seeded_ctx):
    """`active=False` is how somebody says they stopped buying it. The matcher already
    refuses them; discovery must not have counted them in the first place."""
    before = _listed(seeded_ctx, COFFEE)["unserved_units"]
    _add_member(seeded_ctx, "hh_retired")
    _declare(
        seeded_ctx, "need_retired", "hh_retired", COFFEE, quantity=9, active=False
    )
    assert _listed(seeded_ctx, COFFEE)["unserved_units"] == before


def test_an_unresolved_custom_product_combines_with_nothing(seeded_ctx):
    """A product with no substitute group is compatible with itself and nothing else, so
    it can neither borrow another product's demand nor lend it any."""
    from pool.domain.models import Product

    seeded_ctx.repo.put_product(
        WS, Product("prod_custom_x", "Cardamom pods, 500g", "other", "unit", "")
    )
    _add_member(seeded_ctx, "hh_custom")
    _declare(seeded_ctx, "need_custom", "hh_custom", "prod_custom_x", quantity=9)

    assert _listed(seeded_ctx, "prod_custom_x")["unserved_units"] == 9
    for row in discovery.latent_demand(seeded_ctx, COMMUNITY_ID)["opportunities"]:
        if row["product_id"] != "prod_custom_x":
            assert "need_custom" not in str(row)


@pytest.mark.parametrize("product_id", ["prod_whey_vanilla", COFFEE, "prod_energy_drink"])
def test_every_listed_opportunity_survives_its_own_evaluation(seeded_ctx, product_id):
    """The general consistency claim over the seeded world: what discovery promises,
    evaluation finds. Not "approximately" — the same declarations."""
    row = _listed(seeded_ctx, product_id)
    assert row["unserved_units"] == _matcher_units(seeded_ctx, product_id)


def test_the_listing_names_the_product_its_own_demand_actually_supports(seeded_ctx):
    """Target selection reads actionable demand, not raw declared quantity.

    A group whose largest declared quantity sits on an unsourceable, exact-only product
    used to name *that* product as the opportunity, and the evaluation then found
    nothing behind it.
    """
    _other_coffee(seeded_ctx)
    _add_member(seeded_ctx, "hh_bulkexact")
    _declare(
        seeded_ctx,
        "need_bulkexact",
        "hh_bulkexact",
        "prod_other_coffee",
        quantity=40,
        substitution=SubstitutionPolicy.EXACT_ONLY,
    )
    listing = discovery.latent_demand(seeded_ctx, COMMUNITY_ID)["opportunities"]
    coffee_rows = [r for r in listing if r["substitute_group"] == "coffee"]
    assert [r["product_id"] for r in coffee_rows] == [COFFEE]


def test_members_already_being_served_are_not_counted_again(seeded_ctx):
    """Somebody inside a live pool for this product is spoken for; proposing their units
    a second time would build a pool out of demand that is already committed."""
    before = _listed(seeded_ctx, "prod_whey_vanilla")
    assessment = coord.evaluate_opportunity(
        ctx=seeded_ctx,
        community_id=COMMUNITY_ID,
        product_id="prod_whey_vanilla",
        pickup_site_id=before["suggested_pickup_site_id"],
    )
    coord.create_candidate_pool(ctx=seeded_ctx, assessment=assessment, idempotency_key="k")

    after = _listed(seeded_ctx, "prod_whey_vanilla")
    assert after["unserved_units"] < before["unserved_units"]
    assert after["member_count"] < before["member_count"]
