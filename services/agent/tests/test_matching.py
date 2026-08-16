"""Demand matching: Community scoping, verification, substitution, timing, geography.

The boundaries asserted here are the ones that would be embarrassing to get wrong in
public: demand leaking between Communities, an unverified account being counted, or a
product substituted that the member never authorised.
"""

from __future__ import annotations

from datetime import date, timedelta

from pool.domain.matching import find_candidates, haversine_km
from pool.domain.models import SubstitutionPolicy
from pool.domain.substitution import evaluate_compatibility
from tests.conftest import COMM, OTHER_COMM, make_member, make_membership, make_need


def _find(products, needs, members, memberships, target, **kwargs):
    defaults = {
        "community_id": COMM,
        "target_product": target,
        "needs": needs,
        "households": {m.id: m for m in members},
        "products": {p.id: p for p in products},
        "memberships": {m.key: m for m in memberships},
        "pickup_lat": members[0].lat if members else 38.6488,
        "pickup_lon": members[0].lon if members else -90.3108,
        "purchase_date": date.today() + timedelta(days=7),
        "max_radius_km": 5.0,
    }
    defaults.update(kwargs)
    return find_candidates(**defaults)


# --------------------------------------------------------------------- community


def test_demand_from_another_community_never_joins_this_pool(protein):
    mine = make_member("m_mine")
    theirs = make_member("m_theirs")
    needs = [
        make_need("n1", "m_mine", "p_protein", 5, community_id=COMM),
        make_need("n2", "m_theirs", "p_protein", 5, community_id=OTHER_COMM),
    ]
    result = _find(
        [protein], needs, [mine, theirs],
        [make_membership("m_mine"), make_membership("m_theirs", OTHER_COMM)],
        protein,
    )
    assert [c.household.id for c in result.candidates] == ["m_mine"]
    assert any(r.reason == "other_community" for r in result.rejections)


def test_unverified_membership_is_excluded(protein):
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 5)]
    result = _find(
        [protein], needs, [member], [make_membership("m1", verified=False)], protein
    )
    assert result.candidates == []
    assert any("not_verified" in r.reason for r in result.rejections)


def test_missing_membership_is_excluded(protein):
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 5)]
    result = _find([protein], needs, [member], [], protein)
    assert result.candidates == []


def test_verification_can_be_relaxed_for_deterministic_fixtures(protein):
    """Local fixtures must not need a verification dance to be usable (§10)."""
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 5)]
    result = _find(
        [protein], needs, [member], [], protein, require_verified_membership=False
    )
    assert [c.household.id for c in result.candidates] == ["m1"]


# ------------------------------------------------------------------- substitution


def test_exact_only_blocks_a_different_flavour(protein, protein_chocolate):
    member = make_member("m1")
    needs = [
        make_need(
            "n1", "m1", "p_protein_choc", 5, substitution=SubstitutionPolicy.EXACT_ONLY
        )
    ]
    result = _find(
        [protein, protein_chocolate], needs, [member], [make_membership("m1")], protein
    )
    assert result.candidates == []


def test_same_product_other_variant_allows_a_flavour_swap(protein, protein_chocolate):
    member = make_member("m1")
    needs = [
        make_need(
            "n1", "m1", "p_protein_choc", 5,
            substitution=SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT,
        )
    ]
    result = _find(
        [protein, protein_chocolate], needs, [member], [make_membership("m1")], protein
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].is_exact_product is False


def test_same_product_other_variant_still_blocks_another_brand(protein, protein_rival):
    need = make_need(
        "n1", "m1", "p_protein_rival", 5,
        substitution=SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT,
    )
    verdict = evaluate_compatibility(target=protein, candidate=protein_rival, need=need)
    assert verdict.compatible is False


def test_approved_products_is_an_explicit_allowlist(protein, protein_rival):
    allowed = make_need(
        "n1", "m1", "p_protein_rival", 5,
        substitution=SubstitutionPolicy.APPROVED_PRODUCTS,
        approved_product_ids=["p_protein"],
    )
    denied = make_need(
        "n2", "m2", "p_protein_rival", 5,
        substitution=SubstitutionPolicy.APPROVED_PRODUCTS,
        approved_product_ids=["p_something_else"],
    )
    assert evaluate_compatibility(
        target=protein, candidate=protein_rival, need=allowed
    ).compatible
    assert not evaluate_compatibility(
        target=protein, candidate=protein_rival, need=denied
    ).compatible


def test_approved_brands_matches_on_brand(protein, protein_rival):
    need = make_need(
        "n1", "m1", "p_protein_rival", 5,
        substitution=SubstitutionPolicy.APPROVED_BRANDS,
        approved_brands=["Northfield"],
    )
    assert evaluate_compatibility(
        target=protein, candidate=protein_rival, need=need
    ).compatible


def test_category_match_is_the_loosest_rule_and_still_structural(protein, towels):
    need = make_need(
        "n1", "m1", "p_towels", 5,
        substitution=SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH,
    )
    # Different substitute group entirely — no policy makes these interchangeable.
    assert not evaluate_compatibility(
        target=protein, candidate=towels, need=need
    ).compatible


def test_price_ceiling_blocks_an_expensive_substitute(protein, protein_rival):
    need = make_need(
        "n1", "m1", "p_protein_rival", 5,
        substitution=SubstitutionPolicy.APPROVED_BRANDS,
        approved_brands=["Northfield"],
        max_unit_price_cents=500,
    )
    verdict = evaluate_compatibility(
        target=protein, candidate=protein_rival, need=need, offer_unit_price_cents=900
    )
    assert verdict.compatible is False
    assert "ceiling" in verdict.reason


def test_exact_match_short_circuits_every_other_rule(protein):
    need = make_need(
        "n1", "m1", "p_protein", 5,
        substitution=SubstitutionPolicy.EXACT_ONLY, max_unit_price_cents=1,
    )
    verdict = evaluate_compatibility(
        target=protein, candidate=protein, need=need, offer_unit_price_cents=99_999
    )
    assert verdict.compatible and verdict.is_exact


# ------------------------------------------------------------------------ timing


def test_current_and_pull_forward_demand_are_counted_separately(protein):
    now_member = make_member("m_now")
    later_member = make_member("m_later")
    needs = [
        make_need("n1", "m_now", "p_protein", 4, days_out=10, flexibility_days=10,
                  routine_lead_days=10),
        make_need("n2", "m_later", "p_protein", 6, days_out=40, flexibility_days=40,
                  routine_lead_days=7),
    ]
    result = _find(
        [protein], needs, [now_member, later_member],
        [make_membership("m_now"), make_membership("m_later")], protein,
    )
    assert result.current_units == 4
    assert result.future_units == 6
    assert result.total_units == 10


def test_future_demand_can_be_excluded_on_request(protein):
    member = make_member("m1")
    needs = [
        make_need("n1", "m1", "p_protein", 6, days_out=40, flexibility_days=40,
                  routine_lead_days=7)
    ]
    result = _find(
        [protein], needs, [member], [make_membership("m1")], protein,
        include_future_demand=False,
    )
    assert result.candidates == []
    assert any("future_demand_not_requested" in r.reason for r in result.rejections)


def test_a_member_who_authorised_no_early_purchase_is_never_pulled_forward(protein):
    """Convenience to the case count does not create consent (§24)."""
    member = make_member("m1")
    needs = [
        make_need("n1", "m1", "p_protein", 6, days_out=40, flexibility_days=0)
    ]
    result = _find([protein], needs, [member], [make_membership("m1")], protein)
    assert result.candidates == []
    assert any("earlier than the member authorised" in r.reason for r in result.rejections)


def test_demand_needed_before_the_purchase_date_is_excluded(protein):
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 6, days_out=2)]
    result = _find([protein], needs, [member], [make_membership("m1")], protein)
    assert result.candidates == []


def test_inactive_need_is_excluded(protein):
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 6, active=False)]
    result = _find([protein], needs, [member], [make_membership("m1")], protein)
    assert result.candidates == []


# --------------------------------------------------------------------- geography


def test_members_outside_the_radius_are_excluded(protein):
    near = make_member("m_near")
    far = make_member("m_far", dlat=0.5)
    needs = [
        make_need("n1", "m_near", "p_protein", 5),
        make_need("n2", "m_far", "p_protein", 5),
    ]
    result = _find(
        [protein], needs, [near, far],
        [make_membership("m_near"), make_membership("m_far")], protein,
        max_radius_km=2.0,
    )
    assert [c.household.id for c in result.candidates] == ["m_near"]


def test_already_pooled_members_are_not_re_recruited(protein):
    member = make_member("m1")
    needs = [make_need("n1", "m1", "p_protein", 5)]
    result = _find(
        [protein], needs, [member], [make_membership("m1")], protein,
        exclude_household_ids=frozenset({"m1"}),
    )
    assert result.candidates == []


def test_candidate_order_puts_current_demand_before_pull_forward(protein):
    members = [make_member(f"m{i}", dlat=i * 0.001) for i in range(3)]
    needs = [
        make_need("n0", "m0", "p_protein", 2, days_out=40, flexibility_days=40,
                  routine_lead_days=7),
        make_need("n1", "m1", "p_protein", 2, days_out=10, flexibility_days=10,
                  routine_lead_days=10),
        make_need("n2", "m2", "p_protein", 2, days_out=10, flexibility_days=10,
                  routine_lead_days=10),
    ]
    result = _find(
        [protein], needs, members, [make_membership(m.id) for m in members], protein
    )
    assert result.candidates[0].is_future_pull_forward is False
    assert result.candidates[-1].is_future_pull_forward is True


def test_haversine_is_symmetric_and_zero_at_a_point():
    assert haversine_km(38.6, -90.3, 38.6, -90.3) == 0
    assert round(haversine_km(38.6, -90.3, 38.7, -90.4), 6) == round(
        haversine_km(38.7, -90.4, 38.6, -90.3), 6
    )
