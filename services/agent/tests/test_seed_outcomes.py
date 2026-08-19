"""The seeded world's outcome taxonomy, pinned.

A demo environment in which every input collapses toward one answer is not evidence that
the product works — it is evidence that one path works. Before this file existed the
seeded Community had exactly one reachable outcome: whey formed, and everything else
failed on geography before its own interesting condition was ever evaluated. Coffee and
energy drinks never reached a supplier minimum; detergent, whose seed comment says in as
many words that it exists to demonstrate bad economics, never reached the economics.

Each assertion below names the deterministic condition that product exists to
demonstrate, so a fixture edit that quietly removes a whole class of outcome fails here
rather than in front of a judge.

Every figure is read from the evaluator; nothing is hardcoded toward a target.
"""

from __future__ import annotations

import pytest

from pool.data.seed import COMMUNITY_ID
from pool.services import coordination as coord

from .conftest import WS


@pytest.fixture
def sites(seeded_ctx):
    return [s for s in seeded_ctx.repo.list_sites(WS) if s.is_public]


def _best(ctx, sites, product_id):
    """The most favourable public site for one product — the same rule the member
    outlook reports at, because "no site works" and "one site works" differ."""
    best = None
    for site in sites:
        assessment = coord.evaluate_opportunity(
            ctx=ctx, community_id=COMMUNITY_ID, product_id=product_id, pickup_site_id=site.id
        )
        rank = (assessment.viable, assessment.matched_units)
        if best is None or rank > (best.viable, best.matched_units):
            best = assessment
    assert best is not None
    return best


# --------------------------------------------------------------- viable outcomes


@pytest.mark.parametrize("product_id", ["prod_whey_vanilla", "prod_coffee_beans", "prod_energy_drink"])
def test_three_independent_products_can_actually_form(seeded_ctx, sites, product_id):
    """Three separate opportunities, each viable on its own facts and its own members.

    Not one flagship plus decoration: each of these clears its own supplier minimum,
    lands on a whole case boundary, and beats retail after host pay, processing and
    Pool's fee are all counted.
    """
    assessment = _best(seeded_ctx, sites, product_id)
    assert assessment.viable, assessment.reason
    assert assessment.reason_code == coord.REASON_VIABLE
    econ = assessment.economics
    assert econ is not None
    assert econ.net_savings_cents > 0
    assert econ.packages.surplus_units == 0
    assert econ.packages.moq_met


def test_the_three_viable_products_are_not_the_same_people(seeded_ctx, sites):
    """Different products, different members — the community has genuine breadth."""
    rosters = {
        pid: {c.household_id for c in _best(seeded_ctx, sites, pid).candidates}
        for pid in ("prod_whey_vanilla", "prod_coffee_beans", "prod_energy_drink")
    }
    assert all(rosters.values())
    whey, coffee, energy = rosters.values()
    assert whey != coffee and coffee != energy and whey != energy


# ------------------------------------------------------------- refusal outcomes


def test_detergent_refuses_on_economics_not_on_demand(seeded_ctx, sites):
    """Enough people, enough units, and pooling it still saves nobody anything.

    This is the outcome the seed comment always intended and the world could not
    previously reach. The distinction matters to a member: "not enough of you yet" is an
    invitation to wait, and "this would cost you more" is not.
    """
    assessment = _best(seeded_ctx, sites, "prod_detergent_pods")
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_NOT_CHEAPER
    assert assessment.matched_units >= assessment.minimum_units
    assert assessment.economics is not None
    assert assessment.economics.net_savings_cents < 0


def test_paper_towels_refuse_on_the_supplier_minimum(seeded_ctx, sites):
    """Real demand, nowhere near a supplier minimum, at any site in the Community."""
    assessment = _best(seeded_ctx, sites, "prod_paper_towels")
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_BELOW_MINIMUM
    assert 0 < assessment.matched_units < assessment.minimum_units


def test_a_product_with_no_bulk_quote_says_exactly_that(seeded_ctx, sites):
    """Chocolate whey is a real product a member could declare. Pool holds a retail
    baseline for it and no bulk tier, so the honest answer is "nothing to buy in bulk"
    rather than an offer belonging to the vanilla one."""
    assessment = _best(seeded_ctx, sites, "prod_whey_chocolate")
    assert assessment.viable is False
    assert assessment.reason_code == coord.REASON_NO_BULK_OFFER
    assert assessment.bulk_offer_id is None


def test_latent_demand_with_no_supplier_is_a_state_of_its_own(seeded_ctx, sites):
    """Jasmine rice: six independent declarations, and nothing to buy them from.

    The reason code it reaches is the same one chocolate whey reaches, and the two are
    not the same product state at all. Chocolate whey has no bulk quote *and* nobody has
    declared it; rice has no bulk quote and twenty-two bags standing behind it. "Pool
    cannot buy this" and "nobody wants this" are different sentences, and only one of
    them is true here.

    So the pair is pinned together. A fixture edit that gives rice a bulk offer, or that
    removes the declarations behind it, takes the whole class away — and the class is
    the only one in this world an outside event can change.
    """
    rice = _best(seeded_ctx, sites, "prod_rice_jasmine")
    assert rice.viable is False
    assert rice.reason_code == coord.REASON_NO_BULK_OFFER
    assert rice.bulk_offer_id is None
    # No supplier means no minimum. Nothing may print a threshold nobody quoted.
    assert rice.minimum_units == 0

    declared = [n for n in seeded_ctx.repo.list_needs(WS) if n.product_id == "prod_rice_jasmine"]
    assert len({n.household_id for n in declared}) == 6
    assert sum(n.quantity for n in declared) == 22

    # The contrast that makes it a distinct class rather than a duplicate.
    choc = [n for n in seeded_ctx.repo.list_needs(WS) if n.product_id == "prod_whey_chocolate"]
    assert choc == []


def test_every_seeded_product_reaches_a_distinct_named_outcome(seeded_ctx, sites):
    """The taxonomy itself, in one assertion.

    Four different deterministic verdicts across seven seeded products. A change that
    collapses two of these classes into one takes a genuine capability out of the demo
    world, and does it silently — so it is pinned as a set rather than product by
    product.

    Two products share ``no_bulk_offer`` and are kept apart by the test above: the code
    is the same, the situation is not.
    """
    verdicts = {
        pid: (lambda a: a.reason_code if not a.viable else coord.REASON_VIABLE)(
            _best(seeded_ctx, sites, pid)
        )
        for pid in sorted(p.id for p in seeded_ctx.repo.list_products(WS))
    }
    assert verdicts == {
        "prod_whey_vanilla": coord.REASON_VIABLE,
        "prod_coffee_beans": coord.REASON_VIABLE,
        "prod_energy_drink": coord.REASON_VIABLE,
        "prod_detergent_pods": coord.REASON_NOT_CHEAPER,
        "prod_paper_towels": coord.REASON_BELOW_MINIMUM,
        "prod_whey_chocolate": coord.REASON_NO_BULK_OFFER,
        "prod_rice_jasmine": coord.REASON_NO_BULK_OFFER,
    }
    assert len(set(verdicts.values())) == 4


# ------------------------------------------------------------------ the radius


def test_formation_searches_the_community_the_member_belongs_to(seeded_ctx):
    """The Community's own radius is the authoritative one, and it is actually read.

    ``Community.radius_km`` used to be a field nothing consulted while a global constant
    decided who could form a pool — so a verified member could sit inside their
    community, outside a rule they were never shown, and never be discoverable.
    """
    community = seeded_ctx.community(COMMUNITY_ID)
    assert coord.formation_radius_km(community) == community.radius_km
    # Repair still reaches further than the Community, deliberately (§27).
    assert coord.recovery_radius_km(community) > community.radius_km


def test_a_member_of_the_community_is_never_excluded_by_geography_alone(seeded_ctx, sites):
    """Every verified member with whey demand is reachable from some public site.

    Their own travel policy still decides whether Pool may commit them without asking —
    that is a rule they stated. A coarse radius they never saw is not.
    """
    whey_households = {
        n.household_id
        for n in seeded_ctx.repo.list_needs(WS)
        if n.product_id == "prod_whey_vanilla" and n.active
    }
    reachable: set[str] = set()
    for site in sites:
        assessment = coord.evaluate_opportunity(
            ctx=seeded_ctx,
            community_id=COMMUNITY_ID,
            product_id="prod_whey_vanilla",
            pickup_site_id=site.id,
        )
        reachable |= {c.household_id for c in assessment.candidates}
        reachable |= {
            r["household_id"]
            for r in assessment.rejected
            if r["reason"] != "outside_radius"
        }
    assert whey_households <= reachable
