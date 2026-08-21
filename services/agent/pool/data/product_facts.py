"""Curated authoritative product facts for one deliberately narrow family.

Everything in this file is **synthetic and hand-authored**. No real brand, roaster,
barcode, or package is represented, and nothing here was read off a public catalogue —
which is the point. A product fact is what Pool computes compatibility from, so a wrong
value does not look wrong; it silently makes two people's purchases interchangeable when
they are not. The same rule the seed applies to case sizes and package weights applies
here, and more strictly (AGENTS.md §5, §48).

Why a new family instead of the existing ``coffee`` group
---------------------------------------------------------

The bundled catalogue's ``coffee`` family has 26 members and includes cold brew in a
bottle, instant granules, a vanilla creamer, and a chilled Frappuccino alongside bags of
beans. As a *declarable family* that is defensible — somebody who says "I buy coffee" and
is handed any of them has not been wronged in a way the interface cannot explain. As a
basis for **attribute** reasoning it is not: there is no honest value of ``form`` for a
creamer, and a schema that pretends otherwise would be inventing facts to fit a model.

``roast_coffee`` is therefore a separate curated family: roasted coffee sold as beans or
as ground, and nothing else. Whole bean and ground are the same product at different
grind, which is exactly the distinction ``form`` exists to carry. Instant, ready-to-drink
and creamer are not in the family at all, so they carry no facts and fail closed rather
than being classified.

What this file does **not** do
------------------------------

It holds no price, no case size, no supplier and no minimum, and the ordinary demo seed
does not install any of it. These products exist so the compatibility model can be
proved against realistic heterogeneous demand; wiring them into a scenario — supplier
quotes, households, declarations — is a later decision with its own evidence, and
installing them by default would put six unsourceable rows into every demo workspace for
no one's benefit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..domain.attributes import (
    AttributeDefinition,
    AttributeValueType,
    FactProvenance,
    FactVerification,
    ProductAttributeFact,
    ProductFamilySchema,
)
from ..domain.models import Product, ProductSource

#: The curated family this module is authoritative for. Matches ``Product.substitute_group``.
FAMILY = "roast_coffee"

#: What to call this family when speaking to a member. The slug above is an identifier
#: and reads like one; a screen that asked "only this exact roast_coffee" would be
#: showing somebody the database. Curated here beside the questions rather than derived
#: in a browser, for the same reason every other word a member reads is: the wording of
#: a consent question is not something to generate at runtime.
FAMILY_NOUN = "coffee"

#: Bumped whenever the meaning of an attribute changes, not merely when a product is
#: added. A stored member policy records the version it was written against and is
#: refused rather than reinterpreted when the two disagree.
SCHEMA_VERSION = 1

#: Where these facts are recorded, for provenance. Not a URL, and not a real source.
SOURCE_REF = "pool:curated-synthetic:2026-08-20"


# --------------------------------------------------------------------------- values
# Tokens, not sentences. They are stored in member policies and in facts, so they are
# part of the persisted contract and are never localised or reworded in place.

FORM_WHOLE_BEAN = "WHOLE_BEAN"
FORM_GROUND = "GROUND"

CAFFEINE_CAFFEINATED = "CAFFEINATED"
CAFFEINE_DECAF = "DECAF"

ROAST_LIGHT = "LIGHT"
ROAST_MEDIUM = "MEDIUM"
ROAST_DARK = "DARK"


SCHEMA = ProductFamilySchema(
    family=FAMILY,
    version=SCHEMA_VERSION,
    attributes=(
        # Grind and caffeine are what the product *is*. A member cannot be matched
        # against a bag whose grind or caffeine state nobody has confirmed, whatever
        # their own policy happens to mention — so both are required by the family.
        AttributeDefinition(
            key="form",
            value_type=AttributeValueType.ENUM,
            allowed_values=frozenset({FORM_WHOLE_BEAN, FORM_GROUND}),
            required_for_compatibility=True,
        ),
        AttributeDefinition(
            key="caffeine",
            value_type=AttributeValueType.ENUM,
            allowed_values=frozenset({CAFFEINE_CAFFEINATED, CAFFEINE_DECAF}),
            required_for_compatibility=True,
        ),
        # Roast is taste. Somebody who never mentions it can be served a bag whose roast
        # nobody has confirmed; somebody who constrains it cannot, because their own
        # policy then makes the fact load-bearing. That asymmetry is the reason the
        # family-level flag and the member-level policy are separate mechanisms.
        AttributeDefinition(
            key="roast",
            value_type=AttributeValueType.ENUM,
            allowed_values=frozenset({ROAST_LIGHT, ROAST_MEDIUM, ROAST_DARK}),
            required_for_compatibility=False,
        ),
    ),
)


# ------------------------------------------------------------------------- products
# Invented names. Six bags rather than four: heterogeneous demand only becomes an
# interesting search problem when more than one grouping is defensible, and a family
# with a single acceptable answer would let a later stage look like it was choosing
# while having nothing to choose between.

PRODUCTS: tuple[Product, ...] = (
    Product(
        "prod_rc_kestrel_medium", "Whole bean coffee, 2 lb", "beverage", "bag", FAMILY,
        brand="Kestrel Roastworks", variant="medium roast", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
    Product(
        "prod_rc_kestrel_light", "Whole bean coffee, 2 lb", "beverage", "bag", FAMILY,
        brand="Kestrel Roastworks", variant="light roast", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
    Product(
        "prod_rc_harbourstone_dark", "Whole bean coffee, 2 lb", "beverage", "bag", FAMILY,
        brand="Harbourstone Coffee", variant="dark roast", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
    Product(
        "prod_rc_stillfield_decaf", "Whole bean coffee, decaf, 2 lb", "beverage", "bag", FAMILY,
        brand="Stillfield Coffee", variant="medium roast, decaf", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
    Product(
        "prod_rc_millgate_ground", "Ground coffee, 2 lb", "beverage", "bag", FAMILY,
        brand="Millgate Coffee", variant="medium roast, ground", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
    # Deliberately incomplete, and shipped that way. Its grind and caffeine state are
    # confirmed; its roast is a value somebody wrote down and nobody checked. This is the
    # ordinary condition of real product data, and a fixture in which every fact is
    # verified would prove the happy path and quietly leave the fail-closed path
    # untested against anything a person could actually declare.
    Product(
        "prod_rc_beacon_unverified", "Whole bean coffee, 2 lb", "beverage", "bag", FAMILY,
        brand="Beacon Row Coffee", variant="", unit_weight_grams=907,
        source=ProductSource.CURATED, source_ref=SOURCE_REF,
    ),
)


def _fact(
    product_id: str,
    attribute: str,
    value: str,
    verification: FactVerification = FactVerification.VERIFIED,
) -> ProductAttributeFact:
    return ProductAttributeFact(
        product_id=product_id,
        family=FAMILY,
        attribute=attribute,
        value=value,
        provenance=FactProvenance.CURATED_SYNTHETIC,
        verification=verification,
        schema_version=SCHEMA_VERSION,
        source_ref=SOURCE_REF,
    )


FACTS: tuple[ProductAttributeFact, ...] = (
    # A — caffeinated whole bean, medium.
    _fact("prod_rc_kestrel_medium", "form", FORM_WHOLE_BEAN),
    _fact("prod_rc_kestrel_medium", "caffeine", CAFFEINE_CAFFEINATED),
    _fact("prod_rc_kestrel_medium", "roast", ROAST_MEDIUM),
    # A′ — the same roaster, light. Gives a roast-range policy something to exclude
    # without excluding a whole brand.
    _fact("prod_rc_kestrel_light", "form", FORM_WHOLE_BEAN),
    _fact("prod_rc_kestrel_light", "caffeine", CAFFEINE_CAFFEINATED),
    _fact("prod_rc_kestrel_light", "roast", ROAST_LIGHT),
    # B — caffeinated whole bean, dark.
    _fact("prod_rc_harbourstone_dark", "form", FORM_WHOLE_BEAN),
    _fact("prod_rc_harbourstone_dark", "caffeine", CAFFEINE_CAFFEINATED),
    _fact("prod_rc_harbourstone_dark", "roast", ROAST_DARK),
    # C — decaf whole bean, medium. Right grind, right roast, wrong thing entirely for
    # somebody who requires caffeine.
    _fact("prod_rc_stillfield_decaf", "form", FORM_WHOLE_BEAN),
    _fact("prod_rc_stillfield_decaf", "caffeine", CAFFEINE_DECAF),
    _fact("prod_rc_stillfield_decaf", "roast", ROAST_MEDIUM),
    # D — caffeinated ground, medium. Everything a bean drinker asked for except the one
    # thing that makes it usable to them.
    _fact("prod_rc_millgate_ground", "form", FORM_GROUND),
    _fact("prod_rc_millgate_ground", "caffeine", CAFFEINE_CAFFEINATED),
    _fact("prod_rc_millgate_ground", "roast", ROAST_MEDIUM),
    # E — the incomplete one. Note what is *absent* as much as what is unverified: this
    # row asserts a roast nobody confirmed, and the evaluator must treat that as less
    # than no information rather than more.
    _fact("prod_rc_beacon_unverified", "form", FORM_WHOLE_BEAN),
    _fact("prod_rc_beacon_unverified", "caffeine", CAFFEINE_CAFFEINATED),
    _fact(
        "prod_rc_beacon_unverified", "roast", ROAST_MEDIUM,
        verification=FactVerification.UNVERIFIED,
    ),
)


# ------------------------------------------------------------------------- registry


def _index() -> dict[str, dict[str, ProductAttributeFact]]:
    out: dict[str, dict[str, ProductAttributeFact]] = {}
    for fact in FACTS:
        out.setdefault(fact.product_id, {})[fact.attribute] = fact
    return out


class CuratedProductFacts:
    """The committed fact set, behind :class:`~pool.domain.attributes.ProductFactSource`.

    Built once from module-level constants and never mutated, so there is no writable
    path a running process — least of all a model — could reach. Adding a fact means
    editing this file and committing it, which is the whole reason facts are a separate
    object rather than fields somebody could set on a ``Product`` at runtime.
    """

    def __init__(
        self,
        schemas: Mapping[str, ProductFamilySchema] | None = None,
        facts: Mapping[str, Mapping[str, ProductAttributeFact]] | None = None,
    ) -> None:
        self._schemas: dict[str, ProductFamilySchema] = dict(
            schemas if schemas is not None else {FAMILY: SCHEMA}
        )
        self._facts: dict[str, dict[str, ProductAttributeFact]] = {
            pid: dict(attrs)
            for pid, attrs in (facts if facts is not None else _index()).items()
        }

    def family_schema(self, family: str) -> ProductFamilySchema | None:
        return self._schemas.get(family)

    def facts_for(self, product_id: str) -> Mapping[str, ProductAttributeFact]:
        return self._facts.get(product_id, {})


#: The one the application uses. Injected through ``PoolContext`` rather than imported by
#: the domain, so the authority a compatibility decision rests on is visible at the seam.
REGISTRY = CuratedProductFacts()


def install(repo, workspace: str) -> dict[str, object]:
    """Write the curated family's products into one workspace.

    Not called by :func:`pool.data.seed.seed`. The facts are compiled in and need no
    installation; only the ``Product`` rows do, and only where something is actually
    going to reason about them. Returns what it wrote so a caller can report it rather
    than assert it.
    """
    for product in PRODUCTS:
        repo.put_product(workspace, product)
    return {"products": len(PRODUCTS), "facts": len(FACTS), "family": FAMILY}


# --------------------------------------------------------------- declarable questions
#
# The consumer wording for the dimensions above. Curated here, beside the schema, for the
# same reason the facts are: a question a member answers becomes a hard constraint on what
# Pool may buy for them, so its meaning cannot be authored at runtime by anything —
# including a model. This table is the *approved set*; a later phase may let a bounded
# agent choose which of these to ask and in what order, and it will still be choosing
# from here.
#
# Nothing in this table decides compatibility. It decides how a dimension is *spoken*,
# and `services/needs.py` maps an answer back onto the typed policy deterministically.


#: Bumped when the *approved set of questions or their meaning* changes — not when a
#: label is reworded. A stored clarification plan records the version it was planned
#: against and is regenerated rather than reinterpreted when the two disagree, for the
#: same reason a member policy is (``domain/attributes``).
QUESTION_DEFINITION_VERSION = 1


@dataclass(frozen=True)
class AttributeQuestion:
    """One thing a member can be asked about a product, in their own words.

    **This is the ceiling, not a suggestion.** A later stage may choose *which* of these
    to ask and in what order; it may not add one, reword one, or change what an answer
    means. The id is stable and family-scoped so a plan can name a question without
    carrying its wording, and so renaming a prompt cannot silently repoint a stored plan
    at a different question.

    ``kind`` is what the control has to be, not what it looks like:

    ``keep``
        A single fact about the product they picked that they may insist on — "it has to
        be whole bean". Derived from an attribute the family marks
        ``required_for_compatibility``, because those are what a product *is*.
    ``choose``
        A dimension where several answers are genuinely acceptable — "medium or dark".

    A question is only ever offered for an attribute the *selected product* carries a
    verified fact for. Asking somebody to insist on a value Pool cannot establish would
    produce a rule that refuses everything, and asking about a fact nobody has confirmed
    would be asking them to guess.
    """

    #: Stable, family-scoped, and the only thing a plan stores.
    id: str
    attribute: str
    kind: str
    #: The question, as a person reads it. ``{value}`` is substituted with the label of
    #: the selected product's own value where the wording needs it.
    prompt: str
    #: Short helper text, or empty. Never a justification for saying yes.
    hint: str = ""


QUESTION_KIND_KEEP = "keep"
QUESTION_KIND_CHOOSE = "choose"

#: Consumer labels for every token the schema defines. Exhaustive by construction — a
#: value with no label would reach a screen as ``WHOLE_BEAN``.
VALUE_LABELS: dict[str, dict[str, str]] = {
    "form": {FORM_WHOLE_BEAN: "Whole bean", FORM_GROUND: "Ground"},
    "caffeine": {CAFFEINE_CAFFEINATED: "Caffeinated", CAFFEINE_DECAF: "Decaf"},
    "roast": {ROAST_LIGHT: "Light", ROAST_MEDIUM: "Medium", ROAST_DARK: "Dark"},
}

QUESTIONS: dict[str, AttributeQuestion] = {
    "form": AttributeQuestion(
        id=f"{FAMILY}.form",
        attribute="form",
        kind=QUESTION_KIND_KEEP,
        prompt="It has to be {value}",
        hint="Ground coffee and whole beans are not the same thing to most people.",
    ),
    "caffeine": AttributeQuestion(
        id=f"{FAMILY}.caffeine",
        attribute="caffeine",
        kind=QUESTION_KIND_KEEP,
        prompt="It has to be {value}",
    ),
    "roast": AttributeQuestion(
        id=f"{FAMILY}.roast",
        attribute="roast",
        kind=QUESTION_KIND_CHOOSE,
        prompt="Roasts that work for you",
        hint="Pick every roast you would be happy with.",
    ),
}

#: By id, so a plan can be validated against the approved set without knowing which
#: attribute an id belongs to.
QUESTIONS_BY_ID: dict[str, AttributeQuestion] = {q.id: q for q in QUESTIONS.values()}


def question_for(attribute: str) -> AttributeQuestion | None:
    return QUESTIONS.get(attribute)


def question_by_id(question_id: str) -> AttributeQuestion | None:
    """The approved definition for one id, or ``None``. There is no other way in."""
    return QUESTIONS_BY_ID.get(question_id)


def label_for(attribute: str, value: str) -> str:
    return VALUE_LABELS.get(attribute, {}).get(value, value)


#: Curated consumer nouns, one per family. A family with no entry has no noun rather than
#: a guessed one — the screens fall back to "product", which is true of everything.
FAMILY_NOUNS: dict[str, str] = {FAMILY: FAMILY_NOUN}


def family_noun(family: str) -> str:
    return FAMILY_NOUNS.get(family, "")
