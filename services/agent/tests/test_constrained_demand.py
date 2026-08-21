"""Typed consent over curated product facts, and the three shapes a household comes in.

Pool could already express two of them. A member says "this exact bag" (``EXACT_ONLY``)
or "any of these bags" (``APPROVED_PRODUCTS``, an allowlist they wrote) or "coffee, I do
not care which" (``GROUP_DECLARED``). What had no field at all is the shape most people
are actually in: *"whole bean, caffeinated, medium or dark — and never ground, never
decaf."* That is not an allowlist, because it is a statement about products the member
has never seen. It is not a family, because a family contains ground and decaf.

``ATTRIBUTE_CONSTRAINED`` is that statement, and this module is the argument that it can
be honoured without ever asking a model whether two bags are basically the same. Three
properties carry the whole design, and each is tested below:

* **facts are curated, versioned, and not inferred** — nothing derives ``form`` from the
  word "bean" in a product name, and there is no writable path a running process could
  use to add one;
* **every doubt refuses** — unknown, unverified, conflicted, wrong family, wrong schema
  version, missing policy, and no fact source at all each produce an incompatible
  verdict with its own machine-readable code;
* **hard and soft never mix** — a preference may order the products a member has already
  been found compatible with, and may never add one or remove one.

The fourth property is the boring one and it is why most of this file is not about
coffee: everything that existed before this policy behaves exactly as it did.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.api import app as api
from pool.data import product_facts as pf
from pool.data.seed import COMMUNITY_ID
from pool.domain.attributes import (
    NO_FACTS,
    AttributeConstraint,
    AttributeDefinition,
    AttributeOutcome,
    AttributeValueType,
    ConstraintError,
    FactProvenance,
    FactVerification,
    ProductAttributeFact,
    ProductFamilySchema,
    check_product_attributes,
    preference_rank,
    validate_constraint,
)
from pool.domain.matching import find_candidates
from pool.domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    NeedDeclaration,
    Product,
    SubstitutionPolicy,
)
from pool.domain.policy import evaluate_smart_join
from pool.domain.substitution import CompatibilityReason, evaluate_compatibility

from .conftest import WS, make_member, make_membership, make_need
from .test_public_demo import FakeDynamoTable

FAMILY = pf.FAMILY
VERSION = pf.SCHEMA_VERSION

A_MEDIUM = "prod_rc_kestrel_medium"
A_LIGHT = "prod_rc_kestrel_light"
B_DARK = "prod_rc_harbourstone_dark"
C_DECAF = "prod_rc_stillfield_decaf"
D_GROUND = "prod_rc_millgate_ground"
E_UNVERIFIED_ROAST = "prod_rc_beacon_unverified"


# --------------------------------------------------------------------------- helpers


def product(product_id: str) -> Product:
    return next(p for p in pf.PRODUCTS if p.id == product_id)


def constraint(
    *,
    requires: dict[str, set[str]] | None = None,
    excludes: dict[str, set[str]] | None = None,
    prefers: dict[str, tuple[str, ...]] | None = None,
    family: str = FAMILY,
    version: int = VERSION,
) -> AttributeConstraint:
    """The canonical member: whole bean, caffeinated, medium or dark, unless overridden."""
    return AttributeConstraint(
        family=family,
        schema_version=version,
        requires={
            k: frozenset(v)
            for k, v in (
                requires
                if requires is not None
                else {
                    "form": {pf.FORM_WHOLE_BEAN},
                    "caffeine": {pf.CAFFEINE_CAFFEINATED},
                    "roast": {pf.ROAST_MEDIUM, pf.ROAST_DARK},
                }
            ).items()
        },
        excludes={k: frozenset(v) for k, v in (excludes or {}).items()},
        prefers=dict(prefers or {}),
    )


def constrained_need(
    policy: AttributeConstraint | None,
    *,
    need_id: str = "need_c",
    product_id: str = A_MEDIUM,
    substitution: SubstitutionPolicy = SubstitutionPolicy.ATTRIBUTE_CONSTRAINED,
    **kwargs,
) -> NeedDeclaration:
    need = make_need(need_id, "hh_c", product_id, 3, substitution=substitution, **kwargs)
    need.attribute_policy = policy
    return need


def verdict_for(
    target_id: str,
    policy: AttributeConstraint | None,
    *,
    declared: str = A_MEDIUM,
    facts=pf.REGISTRY,
    **kwargs,
):
    return evaluate_compatibility(
        target=product(target_id),
        candidate=product(declared),
        need=constrained_need(policy, product_id=declared),
        facts=facts,
        **kwargs,
    )


def facts_source(**overrides: dict[str, ProductAttributeFact]) -> pf.CuratedProductFacts:
    """The curated registry with named products' facts replaced wholesale.

    Used to build the states a *shipped* fixture should not contain — a conflicted fact,
    an absent required one — without putting them in the file the application reads.
    """
    base = {p.id: dict(pf.REGISTRY.facts_for(p.id)) for p in pf.PRODUCTS}
    base.update(overrides)
    return pf.CuratedProductFacts(facts=base)


# ------------------------------------------------------- the curated data itself


def test_the_curated_family_is_narrower_than_the_declarable_coffee_family():
    """The reason this is not just ``substitute_group == "coffee"``.

    The catalogue's coffee family is a fine thing to *declare* — somebody who says "I buy
    coffee" and is handed any of it has not been wronged. It is not a basis for attribute
    reasoning: it contains a creamer, an instant, a bottled cold brew and a chilled
    Frappuccino, and there is no honest value of ``form`` for a creamer. A schema over
    that set would have to invent facts to fit, which is the one thing this layer exists
    to make impossible.
    """
    from pool.data import catalog

    coffee = {e.product_id for e in catalog.entries() if e.substitute_group == "coffee"}
    curated = {p.id for p in pf.PRODUCTS}
    assert coffee, "the broad coffee family should still exist and be declarable"
    assert not (coffee & curated), "the curated family must not overlap the broad one"
    assert all(p.substitute_group == FAMILY for p in pf.PRODUCTS)
    assert FAMILY != "coffee"


def test_every_curated_fact_type_checks_against_the_shipped_schema():
    for fact in pf.FACTS:
        definition = pf.SCHEMA.definition(fact.attribute)
        assert definition is not None, fact.attribute
        assert definition.permits(fact.value), (fact.attribute, fact.value)
        assert fact.family == FAMILY
        assert fact.schema_version == VERSION
        assert fact.provenance is FactProvenance.CURATED_SYNTHETIC
        assert fact.source_ref


def test_every_curated_product_carries_the_facts_the_family_requires():
    """The family-level floor, asserted of the shipped data rather than assumed.

    ``roast`` is deliberately not on this list: it is taste, and a member who never
    mentions it can be served a bag whose roast nobody confirmed. Grind and caffeine are
    what the product *is*, so no product in the family may be matched without them.
    """
    required = {d.key for d in pf.SCHEMA.required_attributes}
    assert required == {"form", "caffeine"}
    for p in pf.PRODUCTS:
        held = pf.REGISTRY.facts_for(p.id)
        for key in required:
            assert key in held, f"{p.id} has no {key}"
            assert held[key].is_authoritative, f"{p.id}'s {key} is not verified"


def test_the_one_incomplete_product_is_incomplete_on_purpose():
    """A fixture where every fact is verified proves only the happy path."""
    held = pf.REGISTRY.facts_for(E_UNVERIFIED_ROAST)
    assert held["roast"].verification is FactVerification.UNVERIFIED
    assert held["form"].is_authoritative and held["caffeine"].is_authoritative


def test_no_product_fact_was_inferred_from_a_product_name():
    """The invariant the whole layer rests on, stated as an executable check.

    Every fact is looked up by product id in a committed table. Nothing reads a name, a
    brand or a variant string — so a bag called "Whole Bean" whose curated ``form`` says
    ``GROUND`` is reported as ground, which is the only safe direction.
    """
    renamed = Product(
        D_GROUND, "Whole bean coffee, definitely beans", "beverage", "bag", FAMILY,
        brand="Millgate Coffee", variant="whole bean whole bean",
    )
    check = check_product_attributes(
        product_id=renamed.id,
        product_family=renamed.substitute_group,
        constraint=constraint(),
        source=pf.REGISTRY,
    )
    assert check.ok is False
    assert check.outcome is AttributeOutcome.REQUIRED_ATTRIBUTE_MISMATCH
    assert check.attribute == "form"


def test_the_ordinary_seed_installs_none_of_this():
    """Six unsourceable bags in every demo workspace would help nobody."""
    repo = InMemoryRepository()
    from pool.data.seed import seed

    seed(repo, WS)
    stored = {p.id for p in repo.list_products(WS)}
    assert not (stored & {p.id for p in pf.PRODUCTS})

    written = pf.install(repo, WS)
    assert written["products"] == len(pf.PRODUCTS)
    assert {p.id for p in repo.list_products(WS)} >= {p.id for p in pf.PRODUCTS}


# ------------------------------------------------------------------------- EXACT


def test_exact_only_accepts_the_same_sku_and_refuses_another():
    need = make_need("n", "hh", A_MEDIUM, 3, substitution=SubstitutionPolicy.EXACT_ONLY)
    same = evaluate_compatibility(
        target=product(A_MEDIUM), candidate=product(A_MEDIUM), need=need
    )
    other = evaluate_compatibility(
        target=product(B_DARK), candidate=product(A_MEDIUM), need=need
    )
    assert same.compatible and same.is_exact
    assert same.code is CompatibilityReason.EXACT_PRODUCT
    assert other.compatible is False
    assert other.code is CompatibilityReason.EXACT_PRODUCT_REQUIRED
    # The sentence a person reads is unchanged from before this phase.
    assert other.reason == "member accepts the exact product only"


# ---------------------------------------------------------------------- FLEXIBLE


def test_an_allowlist_admits_what_the_member_named_and_nothing_else():
    """``APPROVED_PRODUCTS`` is the flexible case, and the list is the member's.

    Nothing widens it. The same neighbouring product in the same curated family, with
    facts that would satisfy any reasonable reading of "similar", is refused — because
    the authority here is an enumeration a person wrote and not a similarity judgement.
    """
    need = make_need(
        "n", "hh", A_MEDIUM, 3,
        substitution=SubstitutionPolicy.APPROVED_PRODUCTS,
        approved_product_ids=[B_DARK],
    )
    allowed = evaluate_compatibility(
        target=product(B_DARK), candidate=product(A_MEDIUM), need=need
    )
    denied = evaluate_compatibility(
        target=product(A_LIGHT), candidate=product(A_MEDIUM), need=need
    )
    assert allowed.compatible and allowed.code is CompatibilityReason.PRODUCT_ALLOWED
    assert allowed.requires_disclosure is True
    assert denied.compatible is False
    assert denied.code is CompatibilityReason.PRODUCT_NOT_ALLOWED


# ------------------------------------------------------------------- CONSTRAINED


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (A_MEDIUM, True),   # whole bean, caffeinated, medium — every requirement met
        (B_DARK, True),     # whole bean, caffeinated, dark — the acceptable range
        (A_LIGHT, False),   # right grind and caffeine, roast outside the range
        (C_DECAF, False),   # right grind and roast, wrong thing entirely
        (D_GROUND, False),  # everything but the one thing that makes it usable
    ],
)
def test_the_canonical_member_gets_exactly_the_products_their_rule_describes(
    target, expected
):
    verdict = verdict_for(target, constraint())
    assert verdict.compatible is expected, verdict.reason


@pytest.mark.parametrize(
    ("target", "code", "attribute"),
    [
        (D_GROUND, CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH, "form"),
        (C_DECAF, CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH, "caffeine"),
        (A_LIGHT, CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH, "roast"),
    ],
)
def test_a_refusal_names_the_attribute_that_caused_it(target, code, attribute):
    """A code alone cannot tell "eleven refused on grind" from "eleven refused on roast".

    That distinction is what makes a refusal actionable rather than merely honest, so it
    is carried on the verdict rather than reconstructed from a sentence.
    """
    verdict = verdict_for(target, constraint())
    assert verdict.compatible is False
    assert verdict.code is code
    assert verdict.attribute == attribute


def test_an_exclusion_is_a_separate_hard_rule_from_a_requirement():
    """Excluding decaf says something a requirement does not: that the fact must be known.

    It also stays true if the schema later gains a value nobody has thought of, which a
    positive requirement written today cannot promise.
    """
    policy = constraint(
        requires={"form": {pf.FORM_WHOLE_BEAN}},
        excludes={"caffeine": {pf.CAFFEINE_DECAF}},
    )
    assert verdict_for(A_MEDIUM, policy).compatible is True
    refused = verdict_for(C_DECAF, policy)
    assert refused.compatible is False
    assert refused.code is CompatibilityReason.EXCLUDED_ATTRIBUTE_VALUE
    assert refused.attribute == "caffeine"


def test_a_constrained_match_is_not_reported_as_a_substitution():
    """The member named a rule, and this product satisfies it. Nothing was swapped.

    ``is_exact`` keeps reporting the two product ids honestly, because it is stored on
    ``Membership.is_exact_product``; ``requires_disclosure`` reports the member's
    expectation, and telling them "we substituted this" would be an apology for doing
    exactly what they asked.
    """
    verdict = verdict_for(B_DARK, constraint())
    assert verdict.compatible is True
    assert verdict.is_exact is False
    assert verdict.requires_disclosure is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_POLICY_SATISFIED


def test_the_exemplar_is_checked_like_everything_else():
    """The one place this policy does not short-circuit on an identical product id.

    A constrained declaration stores a product for lineage. If a curated fact is later
    corrected — this bag turned out to be decaf — the correction has to be able to refuse
    that very product, or the exemplar would be the one thing in the world exempt from
    the member's own rule.
    """
    corrected = facts_source(
        **{
            A_MEDIUM: {
                **pf.REGISTRY.facts_for(A_MEDIUM),
                "caffeine": ProductAttributeFact(
                    product_id=A_MEDIUM, family=FAMILY, attribute="caffeine",
                    value=pf.CAFFEINE_DECAF, provenance=FactProvenance.CURATED_SYNTHETIC,
                    verification=FactVerification.VERIFIED, schema_version=VERSION,
                ),
            }
        }
    )
    verdict = verdict_for(A_MEDIUM, constraint(), declared=A_MEDIUM, facts=corrected)
    assert verdict.compatible is False
    assert verdict.is_exact is True
    assert verdict.code is CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH
    assert verdict.attribute == "caffeine"

    # And every other policy keeps the short-circuit it always had.
    exact = evaluate_compatibility(
        target=product(A_MEDIUM),
        candidate=product(A_MEDIUM),
        need=make_need("n", "hh", A_MEDIUM, 3, substitution=SubstitutionPolicy.EXACT_ONLY),
        facts=corrected,
    )
    assert exact.compatible and exact.is_exact


def test_a_price_ceiling_still_applies_to_a_product_the_member_did_not_name():
    policy = constraint()
    need = constrained_need(policy, product_id=A_MEDIUM, max_unit_price_cents=500)
    refused = evaluate_compatibility(
        target=product(B_DARK), candidate=product(A_MEDIUM), need=need,
        offer_unit_price_cents=900, facts=pf.REGISTRY,
    )
    assert refused.compatible is False
    assert refused.code is CompatibilityReason.UNIT_PRICE_CEILING_EXCEEDED


# ------------------------------------------------------- soft preferences stay soft


def test_a_soft_preference_mismatch_alone_is_never_a_refusal():
    """The invariant that keeps "prefers" from quietly becoming "requires"."""
    policy = constraint(prefers={"roast": (pf.ROAST_MEDIUM,)})
    assert verdict_for(B_DARK, policy).compatible is True     # dark, not preferred
    assert verdict_for(A_MEDIUM, policy).compatible is True   # medium, preferred


def test_a_preference_cannot_admit_something_a_requirement_refused():
    """And the reverse direction, which is the dangerous one.

    Preferring ground coffee while requiring whole bean does not make ground acceptable.
    A soft field that could override a hard one would be a consent hole with a friendly
    name.
    """
    policy = constraint(prefers={"form": (pf.FORM_GROUND,)})
    refused = verdict_for(D_GROUND, policy)
    assert refused.compatible is False
    assert refused.code is CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH


def test_preferences_order_products_that_are_already_authorised():
    policy = constraint(prefers={"roast": (pf.ROAST_MEDIUM, pf.ROAST_DARK)})
    ranked = sorted(
        (A_MEDIUM, B_DARK),
        key=lambda pid: preference_rank(
            constraint=policy, schema=pf.SCHEMA, facts=pf.REGISTRY.facts_for(pid)
        ),
    )
    assert ranked == [A_MEDIUM, B_DARK]
    # An attribute nobody expressed a preference about never separates anything.
    assert preference_rank(
        constraint=constraint(), schema=pf.SCHEMA, facts=pf.REGISTRY.facts_for(A_MEDIUM)
    ) == (0, 0, 0)


def test_an_unverified_value_sorts_last_rather_than_being_refused_here():
    """``preference_rank`` has no authority to refuse and does not acquire one."""
    policy = constraint(prefers={"roast": (pf.ROAST_MEDIUM,)})
    unverified = preference_rank(
        constraint=policy, schema=pf.SCHEMA,
        facts=pf.REGISTRY.facts_for(E_UNVERIFIED_ROAST),
    )
    verified = preference_rank(
        constraint=policy, schema=pf.SCHEMA, facts=pf.REGISTRY.facts_for(A_MEDIUM)
    )
    assert unverified > verified


# ---------------------------------------------------------------------- FAIL CLOSED


def test_a_declaration_with_no_policy_authorises_nothing():
    verdict = verdict_for(A_MEDIUM, None)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_POLICY_MISSING


def test_no_fact_source_at_all_refuses_rather_than_falling_back():
    """"Nobody wired the facts in" and "the rule passes" must never agree."""
    for source in (None, NO_FACTS):
        verdict = evaluate_compatibility(
            target=product(A_MEDIUM),
            candidate=product(A_MEDIUM),
            need=constrained_need(constraint()),
            **({"facts": source} if source is not None else {}),
        )
        assert verdict.compatible is False
        assert verdict.code is CompatibilityReason.UNKNOWN_PRODUCT_FAMILY_SCHEMA


def test_an_unknown_required_attribute_refuses():
    """A product with no ``caffeine`` fact cannot be matched, whatever the member asked.

    The member below constrains only ``form``, so nothing in *their* rule mentions
    caffeine. The family's own definition does, and that is what refuses.
    """
    stripped = facts_source(
        **{
            A_MEDIUM: {
                k: v for k, v in pf.REGISTRY.facts_for(A_MEDIUM).items() if k != "caffeine"
            }
        }
    )
    verdict = verdict_for(
        A_MEDIUM, constraint(requires={"form": {pf.FORM_WHOLE_BEAN}}), facts=stripped
    )
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_UNKNOWN
    assert verdict.attribute == "caffeine"


def test_an_unverified_required_attribute_refuses():
    unverified = facts_source(
        **{
            A_MEDIUM: {
                **pf.REGISTRY.facts_for(A_MEDIUM),
                "form": ProductAttributeFact(
                    product_id=A_MEDIUM, family=FAMILY, attribute="form",
                    value=pf.FORM_WHOLE_BEAN, provenance=FactProvenance.CURATED_SYNTHETIC,
                    verification=FactVerification.UNVERIFIED, schema_version=VERSION,
                ),
            }
        }
    )
    verdict = verdict_for(A_MEDIUM, constraint(), facts=unverified)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_UNVERIFIED
    assert verdict.attribute == "form"


def test_an_unverified_fact_the_member_constrains_refuses_even_when_the_family_does_not():
    """The asymmetry between the family's floor and the member's own rule.

    Nobody has confirmed this bag's roast. A member who never mentions roast may still be
    served it; a member who requires medium may not, because their own policy is what
    makes the fact load-bearing.
    """
    indifferent = constraint(
        requires={"form": {pf.FORM_WHOLE_BEAN}, "caffeine": {pf.CAFFEINE_CAFFEINATED}}
    )
    assert verdict_for(E_UNVERIFIED_ROAST, indifferent).compatible is True

    picky = verdict_for(E_UNVERIFIED_ROAST, constraint())
    assert picky.compatible is False
    assert picky.code is CompatibilityReason.ATTRIBUTE_UNVERIFIED
    assert picky.attribute == "roast"


def test_a_fact_filed_under_the_wrong_key_is_not_evidence():
    """Mis-attributing one bag's grind to another is the failure this layer prevents.

    The curated registry indexes by the fact's own fields and so cannot produce this. A
    fact source is an injected collaborator, though, and a hand-built one could — so the
    fact is checked against the key it was found under rather than trusted for being
    there.
    """
    misfiled = facts_source(
        **{
            A_MEDIUM: {
                **pf.REGISTRY.facts_for(A_MEDIUM),
                # D's grind, filed against A.
                "form": pf.REGISTRY.facts_for(D_GROUND)["form"],
            }
        }
    )
    verdict = verdict_for(A_MEDIUM, constraint(), facts=misfiled)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_UNKNOWN
    assert verdict.attribute == "form"


def test_the_shipped_registry_files_every_fact_under_its_own_key():
    for p in pf.PRODUCTS:
        for key, fact in pf.REGISTRY.facts_for(p.id).items():
            assert fact.product_id == p.id
            assert fact.attribute == key


def test_a_conflicted_fact_refuses_with_its_own_code():
    """Two sources disagreeing is more dangerous than silence, and is named separately."""
    conflicted = facts_source(
        **{
            A_MEDIUM: {
                **pf.REGISTRY.facts_for(A_MEDIUM),
                "form": ProductAttributeFact(
                    product_id=A_MEDIUM, family=FAMILY, attribute="form",
                    value=pf.FORM_WHOLE_BEAN, provenance=FactProvenance.CURATED_SYNTHETIC,
                    verification=FactVerification.CONFLICTED, schema_version=VERSION,
                ),
            }
        }
    )
    verdict = verdict_for(A_MEDIUM, constraint(), facts=conflicted)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_CONFLICTED


def test_a_fact_curated_under_another_schema_version_refuses():
    stale = facts_source(
        **{
            A_MEDIUM: {
                **pf.REGISTRY.facts_for(A_MEDIUM),
                "roast": ProductAttributeFact(
                    product_id=A_MEDIUM, family=FAMILY, attribute="roast",
                    value=pf.ROAST_MEDIUM, provenance=FactProvenance.CURATED_SYNTHETIC,
                    verification=FactVerification.VERIFIED, schema_version=VERSION + 1,
                ),
            }
        }
    )
    verdict = verdict_for(A_MEDIUM, constraint(), facts=stale)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.SCHEMA_VERSION_MISMATCH


def test_a_policy_written_against_another_schema_version_refuses():
    verdict = verdict_for(A_MEDIUM, constraint(version=VERSION + 1))
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.SCHEMA_VERSION_MISMATCH


def test_a_stored_policy_that_no_longer_type_checks_refuses():
    """Validation at the edge is a courtesy; this is the guarantee.

    A schema can be superseded after a declaration was written, so the evaluator re-runs
    the check on every match rather than trusting that the API ran it once.
    """
    invalid = AttributeConstraint(
        family=FAMILY, schema_version=VERSION,
        requires={"grind_size": frozenset({"FINE"})},
    )
    verdict = verdict_for(A_MEDIUM, invalid)
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.ATTRIBUTE_POLICY_INVALID


def test_a_product_outside_the_family_refuses_before_any_fact_is_read(protein):
    """Cross-family substitution is forbidden, and it is refused structurally."""
    verdict = evaluate_compatibility(
        target=protein,
        candidate=product(A_MEDIUM),
        need=constrained_need(constraint()),
        facts=pf.REGISTRY,
    )
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.WRONG_PRODUCT_FAMILY


def test_a_family_with_no_curated_schema_refuses():
    verdict = verdict_for(A_MEDIUM, constraint(family="tea"))
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.UNKNOWN_PRODUCT_FAMILY_SCHEMA


def test_an_attribute_that_cannot_be_compared_deterministically_refuses():
    """The schema may declare a type the evaluator cannot honour. It must not guess."""
    exotic = ProductFamilySchema(
        family=FAMILY,
        version=VERSION,
        attributes=(
            AttributeDefinition(
                key="form",
                value_type="range",  # type: ignore[arg-type]
                allowed_values=frozenset({pf.FORM_WHOLE_BEAN}),
            ),
        ),
    )
    source = pf.CuratedProductFacts(
        schemas={FAMILY: exotic},
        facts={A_MEDIUM: dict(pf.REGISTRY.facts_for(A_MEDIUM))},
    )
    verdict = verdict_for(
        A_MEDIUM, constraint(requires={"form": {pf.FORM_WHOLE_BEAN}}), facts=source
    )
    assert verdict.compatible is False
    assert verdict.code is CompatibilityReason.UNSUPPORTED_ATTRIBUTE_TYPE
    assert verdict.attribute == "form"

    # And the whole family refuses, not only the attribute a member happened to name —
    # a required attribute the evaluator cannot compare would otherwise be compared for
    # equality anyway, which is exactly the approximation the type field forbids.
    assert AttributeValueType.ENUM is pf.SCHEMA.definition("form").value_type


def test_every_attribute_outcome_maps_to_a_compatibility_code():
    """An unmapped outcome would fall through to a generic refusal and lose its cause."""
    from pool.domain.substitution import _ATTRIBUTE_CODES

    assert set(_ATTRIBUTE_CODES) == set(AttributeOutcome)


# ------------------------------------------------------------- policy validation


@pytest.mark.parametrize(
    ("policy", "fragment"),
    [
        (AttributeConstraint(family=FAMILY, schema_version=VERSION), "requirement"),
        (
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION,
                requires={"grind_size": frozenset({"FINE"})},
            ),
            "not an attribute",
        ),
        (
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION,
                requires={"roast": frozenset({"BURNT"})},
            ),
            "not a value",
        ),
        (
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION,
                requires={
                    "form": frozenset({pf.FORM_WHOLE_BEAN}),
                    "roast": frozenset(),
                },
            ),
            "no acceptable values",
        ),
        (
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION + 1,
                requires={"roast": frozenset({pf.ROAST_MEDIUM})},
            ),
            "different version",
        ),
        (
            AttributeConstraint(
                family="tea", schema_version=VERSION,
                requires={"roast": frozenset({pf.ROAST_MEDIUM})},
            ),
            "different product family",
        ),
        (
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION,
                requires={"roast": frozenset({pf.ROAST_MEDIUM})},
                excludes={"roast": frozenset({pf.ROAST_MEDIUM})},
            ),
            "requires and excludes",
        ),
    ],
)
def test_a_policy_the_schema_cannot_honour_is_refused_with_a_reason(policy, fragment):
    with pytest.raises(ConstraintError) as exc:
        validate_constraint(policy, pf.SCHEMA)
    assert fragment in str(exc.value)


def test_a_policy_with_only_preferences_is_refused():
    """It would authorise the whole family while reading as a restriction."""
    with pytest.raises(ConstraintError):
        validate_constraint(
            AttributeConstraint(
                family=FAMILY, schema_version=VERSION,
                prefers={"roast": (pf.ROAST_MEDIUM,)},
            ),
            pf.SCHEMA,
        )


def test_an_uncurated_family_has_no_schema_and_therefore_no_policy():
    with pytest.raises(ConstraintError):
        validate_constraint(constraint(), None)


# ------------------------------------------------------------------- the matcher


def _matched(needs, target_id, facts=pf.REGISTRY):
    households = {n.household_id: make_member(n.household_id) for n in needs}
    return find_candidates(
        community_id=needs[0].community_id,
        target_product=product(target_id),
        needs=list(needs),
        households=households,
        products={p.id: p for p in pf.PRODUCTS},
        memberships={
            f"{n.community_id}#{n.household_id}": make_membership(
                n.household_id, n.community_id
            )
            for n in needs
        },
        pickup_lat=38.6488,
        pickup_lon=-90.3108,
        purchase_date=date.today() + timedelta(days=3),
        facts=facts,
    )


def test_the_matcher_admits_and_refuses_constrained_demand_and_says_why():
    """End to end through the real matcher, not just the pure verdict function."""
    picky = constrained_need(constraint(), need_id="need_picky")
    picky.household_id = "hh_picky"
    bean_only = constrained_need(
        constraint(requires={"form": {pf.FORM_WHOLE_BEAN}}), need_id="need_bean"
    )
    bean_only.household_id = "hh_bean"

    on_beans = _matched([picky, bean_only], A_MEDIUM)
    assert {c.need.id for c in on_beans.candidates} == {"need_picky", "need_bean"}

    on_ground = _matched([picky, bean_only], D_GROUND)
    assert on_ground.candidates == []
    rejected = {r.need_id: r for r in on_ground.rejections}
    assert rejected["need_picky"].code == "required_attribute_mismatch"
    assert rejected["need_picky"].attribute == "form"
    # And the machine-readable form survives the dict projection the agent reads.
    row = next(r for r in on_ground.to_dict()["rejected"] if r["need_id"] == "need_bean")
    assert row["code"] == "required_attribute_mismatch"
    assert row["attribute"] == "form"


# ------------------------------------------------------------------- Smart Join


def _smart_join(need, *, is_exact=False, authorised=True):
    return evaluate_smart_join(
        household_id="hh_c",
        policy=AutonomyPolicy(
            mode=AutonomyMode.SMART_JOIN,
            min_savings_pct=5,
            max_total_cost_cents=20_000,
            max_travel_minutes=30,
            substitution=SubstitutionPolicy.EXACT_ONLY,
        ),
        need=need,
        landed_cost_cents=1_500,
        net_savings_bps=1_500,
        travel_minutes=5,
        is_exact_product=is_exact,
        substitution_authorised=authorised,
        pickup_is_public=True,
    )


def test_a_constrained_member_is_not_asked_to_approve_their_own_rule():
    """Their consent is the rule, and the deterministic layer already proved it holds.

    This is preauthorisation of a specific, machine-checked kind — not Pool deciding that
    a different product is "close enough", which is the thing AGENTS.md §5 keeps for a
    human.
    """
    verdict = _smart_join(constrained_need(constraint()))
    check = next(c for c in verdict.checks if c.rule == "substitution")
    assert check.passed is True
    assert check.detail == "product meets this member's stated requirements"


def test_a_product_outside_the_rule_is_still_a_hard_failure():
    """``substitution_authorised`` is the deterministic verdict, and it is not overridden."""
    verdict = _smart_join(constrained_need(constraint()), authorised=False)
    check = next(c for c in verdict.checks if c.rule == "substitution")
    assert check.passed is False
    assert check.hard is True


def test_the_family_declaration_wording_is_untouched():
    """The existing branch keeps its exact sentence — it is asserted elsewhere too."""
    need = constrained_need(None, substitution=SubstitutionPolicy.GROUP_DECLARED)
    check = next(c for c in _smart_join(need).checks if c.rule == "substitution")
    assert check.passed is True
    assert check.detail == "member declared this product family"


# ------------------------------------------------------------ backward compatibility


@pytest.mark.parametrize(
    ("policy", "reason"),
    [
        (SubstitutionPolicy.EXACT_ONLY, "member accepts the exact product only"),
        (SubstitutionPolicy.APPROVED_PRODUCTS, "product not approved"),
        (SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT, "same product, different variant"),
        (SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH, "same category and product family"),
        (SubstitutionPolicy.GROUP_DECLARED, "member declared this product family"),
    ],
)
def test_existing_policies_keep_the_sentences_they_already_produced(policy, reason):
    """Adding a code must not change the copy anything already displays."""
    need = make_need("n", "hh", A_MEDIUM, 3, substitution=policy)
    verdict = evaluate_compatibility(
        target=product(A_LIGHT), candidate=product(A_MEDIUM), need=need
    )
    assert verdict.reason == reason


def test_a_group_declaration_still_pools_a_whole_curated_family():
    """``GROUP_DECLARED`` keeps meaning exactly what it meant, including for ground.

    Somebody who declares the family gets the family — which is the argument for
    ``ATTRIBUTE_CONSTRAINED`` existing, not against ``GROUP_DECLARED`` being narrowed. No
    stored declaration is reinterpreted here.
    """
    need = make_need("n", "hh", A_MEDIUM, 3, substitution=SubstitutionPolicy.GROUP_DECLARED)
    for target in (B_DARK, C_DECAF, D_GROUND):
        verdict = evaluate_compatibility(
            target=product(target), candidate=product(A_MEDIUM), need=need
        )
        assert verdict.compatible is True, target
        assert verdict.requires_disclosure is False
        assert verdict.code is CompatibilityReason.FAMILY_DECLARED


def test_the_canonical_rice_demand_still_matches_exactly_as_it_did(seeded_ctx):
    """The fixture the rest of the demo rests on, checked from this phase's side.

    Six households, twenty-two bags, all on ``EXACT_ONLY``. If threading a fact source
    through the matcher had changed anything about ordinary exact demand, it would show
    up here as a different count.
    """
    rice = seeded_ctx.repo.get_product(WS, "prod_rice_jasmine")
    assert rice is not None
    needs = [n for n in seeded_ctx.repo.list_needs(WS) if n.product_id == "prod_rice_jasmine"]
    assert len({n.household_id for n in needs}) == 6
    assert sum(n.quantity for n in needs) == 22
    assert all(n.substitution is SubstitutionPolicy.EXACT_ONLY for n in needs)
    assert all(n.attribute_policy is None for n in needs)

    for need in needs:
        verdict = evaluate_compatibility(target=rice, candidate=rice, need=need)
        assert verdict.compatible and verdict.is_exact
        assert verdict.code is CompatibilityReason.EXACT_PRODUCT


# -------------------------------------------------------------------- persistence


def test_a_policy_survives_the_in_memory_repository():
    repo = InMemoryRepository()
    policy = constraint(
        excludes={"caffeine": {pf.CAFFEINE_DECAF}},
        prefers={"roast": (pf.ROAST_MEDIUM, pf.ROAST_DARK)},
    )
    repo.put_need(WS, constrained_need(policy, need_id="need_mem"))
    stored = repo.get_need(WS, "need_mem")
    assert stored is not None
    assert stored.attribute_policy == policy


def test_a_policy_round_trips_through_dynamodb_shaped_storage():
    """Through the real adapter and boto3's own serialiser, which is where sets die.

    A ``frozenset`` is not something the resource API will store, and its iteration order
    is not stable across processes — so the policy is emitted as sorted lists and rebuilt
    on read. Storing consent that differs byte-for-byte between two writes of the same
    thing would make the record unauditable.
    """
    repo = DynamoDBRepository("pool-demo-state", table=FakeDynamoTable())
    policy = constraint(
        excludes={"caffeine": {pf.CAFFEINE_DECAF}},
        prefers={"roast": (pf.ROAST_MEDIUM, pf.ROAST_DARK)},
    )
    original = constrained_need(policy, need_id="need_dynamo")
    repo.put_need(WS, original)

    restored = repo.get_need(WS, "need_dynamo")
    assert restored is not None
    assert restored.attribute_policy == policy
    assert restored.substitution is SubstitutionPolicy.ATTRIBUTE_CONSTRAINED
    # Preference order is meaning, not noise, and survives as given.
    assert restored.attribute_policy.prefers["roast"] == (pf.ROAST_MEDIUM, pf.ROAST_DARK)
    # Identical consent, identical bytes.
    assert restored.to_dict() == original.to_dict()
    assert [n.id for n in repo.list_needs(WS)] == ["need_dynamo"]


def test_a_declaration_written_before_this_field_existed_is_still_readable():
    """Two shapes mean "no attribute authority", and both must keep meaning it.

    A row stored before the field existed has no key at all; a row whose policy was
    cleared has an explicit null. Neither may be read as anything but "none".
    """
    old = {
        "id": "need_old",
        "household_id": "hh_old",
        "community_id": COMMUNITY_ID,
        "product_id": "prod_rice_jasmine",
        "quantity": 4,
        "cadence_days": 45,
        "expected_next_need_date": date.today().isoformat(),
        "substitution": "group_declared",
    }
    without_key = NeedDeclaration.from_dict(old)
    with_null = NeedDeclaration.from_dict({**old, "attribute_policy": None})
    assert without_key.attribute_policy is None
    assert with_null.attribute_policy is None
    assert without_key.substitution is SubstitutionPolicy.GROUP_DECLARED
    # And the round trip out is the explicit null, not a missing key.
    assert without_key.to_dict()["attribute_policy"] is None


def test_a_stored_policy_carries_no_personal_data():
    """Consent about products, and nothing about the person holding it."""
    stored = constraint().to_dict()
    assert set(stored) == {"family", "schema_version", "requires", "excludes", "prefers"}


# --------------------------------------------------------------------------- API


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    pf.install(api._repo, "demo")
    return c


def _declare(client: TestClient, household_id: str, **overrides):
    body = {
        "household_id": household_id,
        "product_id": A_MEDIUM,
        "quantity": 2,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "flexibility_days": 11,
        "max_spend_cents": 9000,
        "substitution": "attribute_constrained",
        "constraint": {
            "family": FAMILY,
            "schema_version": VERSION,
            "requires": {
                "form": [pf.FORM_WHOLE_BEAN],
                "caffeine": [pf.CAFFEINE_CAFFEINATED],
                "roast": [pf.ROAST_MEDIUM, pf.ROAST_DARK],
            },
            "excludes": {},
            "prefers": {"roast": [pf.ROAST_MEDIUM]},
        },
    }
    body.update(overrides)
    return client.post("/api/needs", json=body)


def _onboard(client: TestClient) -> str:
    client.post("/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me"})
    return client.get("/api/state").json()["consumer"]["household_id"]


def test_a_constrained_declaration_is_accepted_and_projected_back(client):
    household_id = _onboard(client)
    response = _declare(client, household_id)
    assert response.status_code == 200, response.text

    stored = response.json()
    assert stored["substitution"] == "attribute_constrained"
    assert stored["attribute_policy"]["family"] == FAMILY
    assert stored["attribute_policy"]["requires"]["roast"] == [pf.ROAST_DARK, pf.ROAST_MEDIUM]
    assert stored["attribute_policy"]["prefers"]["roast"] == [pf.ROAST_MEDIUM]

    # Read back authoritatively rather than trusting the write's own echo.
    rows = client.get("/api/needs").json()["needs"]
    mine = next(r for r in rows if r["household_id"] == household_id)
    assert mine["attribute_policy"] == stored["attribute_policy"]
    # A declaration that has none says so explicitly rather than omitting the field.
    others = [r for r in rows if r["household_id"] != household_id]
    assert others and all(r["attribute_policy"] is None for r in others)


def test_a_constrained_declaration_can_be_amended(client):
    household_id = _onboard(client)
    need_id = _declare(client, household_id).json()["need_id"]

    tighter = {
        "household_id": household_id,
        "product_id": A_MEDIUM,
        "quantity": 3,
        "cadence_days": 30,
        "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
        "max_spend_cents": 9000,
        "substitution": "attribute_constrained",
        "constraint": {
            "family": FAMILY,
            "schema_version": VERSION,
            "requires": {
                "form": [pf.FORM_WHOLE_BEAN],
                "caffeine": [pf.CAFFEINE_CAFFEINATED],
                "roast": [pf.ROAST_MEDIUM],
            },
        },
    }
    response = client.post(f"/api/needs/{need_id}", json=tighter)
    assert response.status_code == 200, response.text
    assert response.json()["attribute_policy"]["requires"]["roast"] == [pf.ROAST_MEDIUM]


def test_dropping_the_policy_drops_the_authority_with_it(client):
    """Amending back to an ordinary declaration must not leave the rule behind."""
    household_id = _onboard(client)
    need_id = _declare(client, household_id).json()["need_id"]
    response = client.post(
        f"/api/needs/{need_id}",
        json={
            "household_id": household_id,
            "product_id": A_MEDIUM,
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "max_spend_cents": 9000,
            "substitution": "exact_only",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["attribute_policy"] is None
    assert api._repo.get_need("demo", need_id).attribute_policy is None


@pytest.mark.parametrize(
    ("overrides", "detail"),
    [
        # Claimed the policy, supplied none.
        ({"constraint": None}, "has to say what they are"),
        # Supplied a policy under a narrower stated rule.
        (
            {"substitution": "exact_only"},
            "only apply to a declaration that states them as its rule",
        ),
        # A family nobody curated a schema for.
        (
            {"constraint": {"family": "tea", "schema_version": 1,
                            "requires": {"roast": [pf.ROAST_MEDIUM]}}},
            "no curated attribute schema",
        ),
        # An attribute the family does not define.
        (
            {"constraint": {"family": FAMILY, "schema_version": VERSION,
                            "requires": {"grind_size": ["FINE"]}}},
            "not an attribute of that product family",
        ),
        # A value the schema does not allow.
        (
            {"constraint": {"family": FAMILY, "schema_version": VERSION,
                            "requires": {"roast": ["BURNT"]}}},
            "not a value",
        ),
        # A superseded schema version.
        (
            {"constraint": {"family": FAMILY, "schema_version": VERSION + 1,
                            "requires": {"roast": [pf.ROAST_MEDIUM]}}},
            "different version",
        ),
        # Nothing hard in it at all.
        (
            {"constraint": {"family": FAMILY, "schema_version": VERSION,
                            "prefers": {"roast": [pf.ROAST_MEDIUM]}}},
            "at least one requirement or exclusion",
        ),
        # A rule the named product itself fails.
        (
            {"constraint": {"family": FAMILY, "schema_version": VERSION,
                            "requires": {"form": [pf.FORM_GROUND]}}},
            "does not meet the requirements you set",
        ),
    ],
)
def test_a_malformed_constrained_declaration_is_refused_with_a_reason(
    client, overrides, detail
):
    household_id = _onboard(client)
    response = _declare(client, household_id, **overrides)
    assert response.status_code == 400, response.text
    assert detail in response.json()["detail"]


def test_requirements_cannot_be_attached_to_a_family_declaration(client):
    """Two statements of authority on one row, and the wider one would win."""
    household_id = _onboard(client)
    response = client.post(
        "/api/needs",
        json={
            "household_id": household_id,
            "group": "coffee",
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": (date.today() + timedelta(days=12)).isoformat(),
            "max_spend_cents": 9000,
            "constraint": {
                "family": FAMILY, "schema_version": VERSION,
                "requires": {"form": [pf.FORM_WHOLE_BEAN]},
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "product requirements go with a product, not with a family"


@pytest.mark.parametrize(
    "constraint_body",
    [
        {"family": FAMILY, "schema_version": VERSION,
         "requires": {f"a{i}": ["X"] for i in range(20)}},
        {"family": FAMILY, "schema_version": VERSION,
         "requires": {"roast": ["X"] * 40}},
        {"family": FAMILY, "schema_version": VERSION,
         "requires": {"roast": ["X" * 200]}},
    ],
)
def test_an_oversized_policy_is_refused_before_it_is_stored(client, constraint_body):
    """The one field on a declaration whose shape a caller controls, so it is bounded."""
    household_id = _onboard(client)
    response = _declare(client, household_id, constraint=constraint_body)
    assert response.status_code == 400


def test_a_declaration_for_a_product_outside_the_policy_family_is_refused(client):
    household_id = _onboard(client)
    response = _declare(client, household_id, product_id="prod_rice_jasmine")
    assert response.status_code == 400
    assert "do not describe the item you chose" in response.json()["detail"]
