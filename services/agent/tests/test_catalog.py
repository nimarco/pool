"""The catalogue, the search above it, and the boundary neither may cross.

Three separate things are protected here, and the third is the one that matters most.

1. **The snapshot loads and behaves the same every time.** A demo that ranks results
   differently on the tenth rehearsal than the first is not a demo.

2. **Search finds what a person would actually type.** "vanilla whey" has to reach the
   product a member recognises, or the first interaction in the product is broken.

3. **Identity never becomes structure.** Public catalogue data supplies names, brands
   and photographs. It must never supply a package size, a case size, a minimum, or a
   substitute group — because those are what Pool multiplies money by, and because a
   product whose category was never reviewed must be able to combine with nothing but
   itself. That is asserted directly rather than assumed.
"""

from __future__ import annotations

import socket

import pytest

from pool.data import catalog
from pool.data.seed import PRODUCTS, seed
from pool.domain.models import NeedDeclaration, Product, ProductSource, SubstitutionPolicy
from pool.domain.substitution import CompatibilityReason, evaluate_compatibility
from pool.services import needs as needs_service
from tests.conftest import WS

CANONICAL = "prod_whey_vanilla"


# --------------------------------------------------------------------------- loading


def test_the_catalogue_is_present_and_non_trivial():
    entries = catalog.entries()
    assert len(entries) > 100, "a catalogue this small would feel like a hidden fixture"
    groups = {e.substitute_group for e in entries if e.substitute_group}
    assert len(groups) >= 10


def test_loading_is_stable_across_calls():
    """Same objects, same order — the ranking downstream inherits this."""
    assert catalog.entries() is catalog.entries()
    assert [e.product_id for e in catalog.entries()] == sorted(
        e.product_id for e in catalog.entries()
    )


def test_every_entry_carries_its_provenance():
    for e in catalog.entries():
        assert e.source in {s.value for s in ProductSource}
        assert e.source_ref, f"{e.product_id} does not say where it came from"


def test_the_attribution_the_licence_requires_is_available():
    a = catalog.attribution()
    assert a.data_license and a.image_license and a.source_url and a.snapshot
    # ODbL and CC-BY-SA both require the credit to be reachable from the display.
    assert "Open Food Facts" in a.source


def test_a_missing_catalogue_file_degrades_instead_of_breaking(monkeypatch):
    """The seeded products still work; search simply finds nothing."""
    monkeypatch.setattr(catalog, "CATALOG_PATH", "/nonexistent/catalog.json")
    catalog.reset_cache()
    try:
        assert catalog.entries() == ()
        assert catalog.search("whey") == []
        assert catalog.get(CANONICAL) is None
    finally:
        # Every cache, not most of them — the search index is a fourth one over the same
        # file, and leaving it holding an empty snapshot silently breaks later tests.
        monkeypatch.undo()
        catalog.reset_cache()


# --------------------------------------------------------------------------- search


@pytest.mark.parametrize(
    "query",
    ["vanilla whey", "whey vanilla", "ON whey", "optimum nutrition", "vanilla protein"],
)
def test_the_words_a_member_would_type_reach_the_canonical_product(query):
    found = [e.product_id for e in catalog.search(query, 6)]
    assert CANONICAL in found, f"{query!r} did not surface the flagship product"


def test_the_flagship_query_ranks_it_first():
    """The demo's opening move. If this slips, the first interaction looks broken."""
    assert catalog.search("vanilla whey", 6)[0].product_id == CANONICAL


def test_curated_synonyms_reach_things_their_names_do_not_contain():
    assert any(e.substitute_group == "toilet_paper" for e in catalog.search("tp", 6))
    assert any(e.substitute_group == "detergent" for e in catalog.search("laundry", 6))


def test_ranking_is_deterministic():
    for query in ("coffee", "protein", "paper towels", "energy"):
        runs = [[e.product_id for e in catalog.search(query, 8)] for _ in range(5)]
        assert all(r == runs[0] for r in runs), f"{query!r} ranked differently"


def test_a_query_too_short_to_mean_anything_returns_nothing():
    assert catalog.search("") == []
    assert catalog.search("v") == []


def test_nonsense_returns_nothing_rather_than_a_wrong_guess():
    assert catalog.search("zzzzqqqq") == []


def test_the_result_count_is_bounded():
    assert len(catalog.search("protein", 999)) <= catalog.MAX_LIMIT


def test_search_makes_no_network_call(monkeypatch):
    """The whole reason the catalogue is a committed file (docs/CATALOG_RESEARCH.md §5.1).

    Open Food Facts documents ten searches a minute and returned 503 while this was being
    built. A demo whose first interaction depends on that is a demo that breaks in front
    of judges — so the ban is asserted, not merely intended.
    """

    def forbidden(*_args, **_kwargs):
        raise AssertionError("product search attempted a network connection")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert catalog.search("vanilla whey", 6)


# ------------------------------------------------------- identity is not structure


def test_no_catalogue_entry_carries_economics():
    """Not one price, case size, minimum or supplier anywhere in the snapshot."""
    banned = {
        "price", "price_cents", "unit_price_cents", "case_units", "moq", "moq_amount",
        "supplier", "supplier_id", "offer", "wholesale",
    }
    for row in catalog._payload().get("products", []):
        assert not banned & set(row), f"{row.get('product_id')} carries economics"


def test_package_size_is_text_and_never_a_number():
    """Open Food Facts sizes are absent, malformed, or a serving rather than a package.

    ``display_size`` exists so a card can say "2.03 lbs" to a human. Nothing parses it,
    and this asserts it never becomes a quantity Pool could multiply money by (§48).
    """
    for e in catalog.entries():
        assert isinstance(e.display_size, str)
    for e in catalog.entries():
        product = e.to_product()
        # Host capacity is computed from this. The catalogue never supplies it.
        assert product.unit_weight_grams == 0


def test_a_materialised_catalogue_product_has_no_offer(seeded_ctx):
    """Declared demand is allowed to outrun Pool's ability to source it."""
    entry = next(e for e in catalog.entries() if e.product_id.startswith("prod_") and
                 e.product_id not in {p.id for p in PRODUCTS})
    seeded_ctx.repo.put_product(WS, entry.to_product())
    assert [o for o in seeded_ctx.repo.list_offers(WS) if o.product_id == entry.product_id] == []


# --------------------------------------------------------- compatibility fails closed


def _need(product_id: str, policy: SubstitutionPolicy) -> NeedDeclaration:
    from datetime import date

    return NeedDeclaration(
        id="n", household_id="h", community_id="c", product_id=product_id,
        quantity=1, cadence_days=30, expected_next_need_date=date.today(),
        substitution=policy,
    )


@pytest.mark.parametrize("policy", list(SubstitutionPolicy))
def test_an_unmapped_product_combines_with_nothing_but_itself(policy):
    """The safe direction, asserted for every policy that exists.

    A catalogue entry whose category was never curated arrives with no substitute group.
    If that ever became "matches anything in the same category", an unreviewed import
    could silently make two people's purchases interchangeable — which is the one thing
    the substitution seam exists to prevent (§21).

    ``ATTRIBUTE_CONSTRAINED`` is the one policy for which "itself" is not automatically
    enough, and the exception strengthens the claim rather than weakening it. That policy
    says "I accept a product **when its facts say X**", so a declaration carrying no such
    rule — as this one does not — authorises nothing at all, not even the row it names.
    Every other policy behaves exactly as it did before this one existed.
    """
    unmapped = Product("p_new", "Something", "", "unit", "")
    other = Product("p_other", "Something else", "", "unit", "")
    verdict = evaluate_compatibility(
        target=unmapped, candidate=other, need=_need("p_other", policy)
    )
    assert not verdict.compatible

    same = evaluate_compatibility(
        target=unmapped, candidate=unmapped, need=_need("p_new", policy)
    )
    if policy is SubstitutionPolicy.ATTRIBUTE_CONSTRAINED:
        assert not same.compatible
        assert same.code is CompatibilityReason.ATTRIBUTE_POLICY_MISSING
        # Still an honest report of the two product ids: `is_exact` is stored on the
        # membership and has to keep meaning literally what it says.
        assert same.is_exact
    else:
        assert same.compatible and same.is_exact


def test_every_catalogue_group_is_one_a_human_wrote():
    """Groups come from the curated table in the build script and from nowhere else."""
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "build_catalog.py"
    text = script.read_text(encoding="utf-8")
    for group in {e.substitute_group for e in catalog.entries() if e.substitute_group}:
        assert f'"{group}"' in text, f"{group!r} is not in the curated category table"


# --------------------------------------------------------------- materialisation


def test_declaring_against_a_catalogue_product_materialises_it(seeded_ctx):
    """A workspace holds what somebody declared, not the whole catalogue."""
    entry = next(
        e for e in catalog.entries()
        if e.product_id not in {p.id for p in PRODUCTS} and e.substitute_group
    )
    assert seeded_ctx.repo.get_product(WS, entry.product_id) is None

    from datetime import date, timedelta

    need = needs_service.declare_need(
        ctx=seeded_ctx,
        community_id="comm_demo_university",
        data=needs_service.NeedInput(
            household_id="hh_navarro",
            product_id=entry.product_id,
            quantity=1,
            cadence_days=30,
            expected_next_need_date=date.today() + timedelta(days=14),
            flexibility_days=14,
        ),
    )
    stored = seeded_ctx.repo.get_product(WS, entry.product_id)
    assert stored is not None
    assert need.product_id == entry.product_id
    # Identity crossed over; structure did not.
    assert stored.brand == entry.brand
    assert stored.substitute_group == entry.substitute_group
    assert stored.unit_weight_grams == 0


def test_declaring_against_something_that_does_not_exist_is_still_refused(seeded_ctx):
    from datetime import date, timedelta

    with pytest.raises(needs_service.NeedError, match="unknown product"):
        needs_service.declare_need(
            ctx=seeded_ctx,
            community_id="comm_demo_university",
            data=needs_service.NeedInput(
                household_id="hh_navarro",
                product_id="prod_not_a_real_id",
                quantity=1,
                cadence_days=30,
                expected_next_need_date=date.today() + timedelta(days=14),
            ),
        )


# ------------------------------------------------------------- the seeded products


def test_the_seeded_products_keep_their_ids(repo):
    """Every canonical id survives, so the scenario's economics cannot move."""
    seed(repo, WS)
    stored = {p.id for p in repo.list_products(WS)}
    assert {p.id for p in PRODUCTS} <= stored


def test_the_flagship_product_reads_as_something_a_person_buys(repo):
    seed(repo, WS)
    product = repo.get_product(WS, CANONICAL)
    assert product.brand and product.name
    # Invented brands were the thing this replaced.
    assert product.brand not in {"Northfield", "Voltside", "Ridgeline", "Clearwash", "Mapleline"}
    assert product.image_ref, "the flagship product needs a photograph"
    assert product.image_attribution, "a CC-BY-SA image has to carry its credit"


def test_the_seed_keeps_curated_structure_even_when_identity_comes_from_outside(repo):
    """The boundary, at the exact place the two meet."""
    seed(repo, WS)
    for curated in PRODUCTS:
        stored = repo.get_product(WS, curated.id)
        assert stored.unit == curated.unit
        assert stored.substitute_group == curated.substitute_group
        assert stored.unit_weight_grams == curated.unit_weight_grams


def test_a_product_pool_quotes_a_synthetic_price_for_claims_no_barcode(repo):
    """Pool's offers for these six are invented, so they identify no retail SKU.

    A barcode names one specific package. Printing a real one beside a case structure
    that was made up for the scenario would assert a correspondence that does not exist —
    and it is exactly the field a careful judge would check.
    """
    seed(repo, WS)
    for curated in PRODUCTS:
        stored = repo.get_product(WS, curated.id)
        offers = [o for o in repo.list_offers(WS) if o.product_id == curated.id]
        if offers:
            assert not stored.gtin, f"{curated.id} publishes a barcode beside a synthetic quote"
            assert not stored.display_size
