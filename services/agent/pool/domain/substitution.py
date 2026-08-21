"""Structured product substitution (§21).

The model is never allowed to decide that two vaguely similar products are
interchangeable. Compatibility is a pure function of a member's declared policy and
structured product attributes, and anything outside that authority becomes a human
decision rather than an assumption.

Policies, from strictest to loosest:

``EXACT_ONLY``
    Only the identical product id.
``SAME_PRODUCT_OTHER_VARIANT``
    Same brand and same substitute group; flavour/scent/variant may differ.
``APPROVED_PRODUCTS``
    An explicit allowlist of product ids the member named.
``APPROVED_BRANDS``
    Same substitute group, and the brand is on the member's allowlist.
``STRUCTURED_CATEGORY_MATCH``
    Same substitute group and same category — the loosest substitution rule, and still
    structural.
``GROUP_DECLARED``
    Not a substitution rule. The member declared the *family*, and the stored
    ``product_id`` is only the exemplar that carries the group. Any structural member of
    that group is the thing they asked for, so the match is authoritative and owes no
    disclosure — see ``requires_disclosure``.
``ATTRIBUTE_CONSTRAINED``
    Also not a substitution rule, and the narrowest way to say something wide. The member
    stated a typed policy over one curated family's authoritative attribute facts
    (``domain.attributes``), and any product whose facts satisfy it is what they asked
    for. This is the only policy that does **not** short-circuit on an identical product
    id: "I accept this only when the facts say X" has to keep being true of the exemplar
    too, or a curated fact corrected after the declaration was written would be ignored
    by exactly the product it was corrected about.

Every policy above ``EXACT_ONLY`` additionally honours a per-unit price ceiling when
the member set one.

Reason codes
------------

Each verdict carries a ``code`` from :class:`CompatibilityReason` alongside its human
``reason``. The code is the stable one: it is what an audit trail stores, what an
aggregate exclusion count groups by, and what a later stage would use to tell "eleven
members refused this on caffeine" apart from "eleven members refused it on grind". The
sentence a person reads is composed elsewhere and may be rewritten freely; the code may
not, because things downstream compare it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .attributes import (
    NO_FACTS,
    AttributeOutcome,
    ProductFactSource,
    check_product_attributes,
)
from .models import NeedDeclaration, Product, SubstitutionPolicy


class CompatibilityReason(str, Enum):
    """Why a product may or may not serve a declaration. Stable, machine-readable."""

    # --- permitted
    EXACT_PRODUCT = "exact_product"
    PRODUCT_ALLOWED = "product_allowed"
    SAME_BRAND_OTHER_VARIANT = "same_brand_other_variant"
    BRAND_ALLOWED = "brand_allowed"
    CATEGORY_MATCH = "category_match"
    FAMILY_DECLARED = "family_declared"
    ATTRIBUTE_POLICY_SATISFIED = "attribute_policy_satisfied"

    # --- refused
    EXACT_PRODUCT_REQUIRED = "exact_product_required"
    PRODUCT_NOT_ALLOWED = "product_not_allowed"
    BRAND_NOT_ALLOWED = "brand_not_allowed"
    WRONG_PRODUCT_FAMILY = "wrong_product_family"
    WRONG_CATEGORY = "wrong_category"
    UNIT_PRICE_CEILING_EXCEEDED = "unit_price_ceiling_exceeded"
    UNRECOGNISED_POLICY = "unrecognised_policy"

    # --- refused by the attribute layer. Mirrors `AttributeOutcome` one-for-one so a
    #     refusal keeps its cause rather than being flattened into "constraint failed".
    ATTRIBUTE_POLICY_MISSING = "attribute_policy_missing"
    ATTRIBUTE_POLICY_INVALID = "attribute_policy_invalid"
    UNKNOWN_PRODUCT_FAMILY_SCHEMA = "unknown_product_family_schema"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    ATTRIBUTE_UNKNOWN = "attribute_unknown"
    ATTRIBUTE_UNVERIFIED = "attribute_unverified"
    ATTRIBUTE_CONFLICTED = "attribute_conflicted"
    ATTRIBUTE_VALUE_NOT_IN_SCHEMA = "attribute_value_not_in_schema"
    UNSUPPORTED_ATTRIBUTE_TYPE = "unsupported_attribute_type"
    REQUIRED_ATTRIBUTE_MISMATCH = "required_attribute_mismatch"
    EXCLUDED_ATTRIBUTE_VALUE = "excluded_attribute_value"


#: `AttributeOutcome` is the attribute layer's own vocabulary and this is the
#: compatibility layer's. They are kept as two enums rather than one because the
#: attribute evaluator must stay usable without knowing anything about substitution
#: policies — but every outcome maps, and a missing entry fails closed below.
_ATTRIBUTE_CODES: dict[AttributeOutcome, CompatibilityReason] = {
    AttributeOutcome.SATISFIED: CompatibilityReason.ATTRIBUTE_POLICY_SATISFIED,
    AttributeOutcome.POLICY_MISSING: CompatibilityReason.ATTRIBUTE_POLICY_MISSING,
    AttributeOutcome.POLICY_INVALID: CompatibilityReason.ATTRIBUTE_POLICY_INVALID,
    AttributeOutcome.UNKNOWN_FAMILY_SCHEMA: CompatibilityReason.UNKNOWN_PRODUCT_FAMILY_SCHEMA,
    AttributeOutcome.SCHEMA_VERSION_MISMATCH: CompatibilityReason.SCHEMA_VERSION_MISMATCH,
    AttributeOutcome.WRONG_PRODUCT_FAMILY: CompatibilityReason.WRONG_PRODUCT_FAMILY,
    AttributeOutcome.ATTRIBUTE_UNKNOWN: CompatibilityReason.ATTRIBUTE_UNKNOWN,
    AttributeOutcome.ATTRIBUTE_UNVERIFIED: CompatibilityReason.ATTRIBUTE_UNVERIFIED,
    AttributeOutcome.ATTRIBUTE_CONFLICTED: CompatibilityReason.ATTRIBUTE_CONFLICTED,
    AttributeOutcome.ATTRIBUTE_VALUE_NOT_IN_SCHEMA: (
        CompatibilityReason.ATTRIBUTE_VALUE_NOT_IN_SCHEMA
    ),
    AttributeOutcome.UNSUPPORTED_ATTRIBUTE_TYPE: CompatibilityReason.UNSUPPORTED_ATTRIBUTE_TYPE,
    AttributeOutcome.REQUIRED_ATTRIBUTE_MISMATCH: CompatibilityReason.REQUIRED_ATTRIBUTE_MISMATCH,
    AttributeOutcome.EXCLUDED_ATTRIBUTE_VALUE: CompatibilityReason.EXCLUDED_ATTRIBUTE_VALUE,
}

#: The sentence a person reads for an attribute refusal. Deliberately says what Pool
#: could not establish rather than naming the member's rule back at them, because a
#: refusal is a result and not an accusation (PRODUCT.md, voice).
_ATTRIBUTE_SENTENCES: dict[AttributeOutcome, str] = {
    AttributeOutcome.POLICY_MISSING: "declaration carries no attribute policy to check",
    AttributeOutcome.POLICY_INVALID: "this member's attribute policy no longer fits the product schema",
    AttributeOutcome.UNKNOWN_FAMILY_SCHEMA: "no curated attribute schema for this product family",
    AttributeOutcome.SCHEMA_VERSION_MISMATCH: "product facts were curated under a different schema version",
    AttributeOutcome.WRONG_PRODUCT_FAMILY: "different product family",
    AttributeOutcome.ATTRIBUTE_UNKNOWN: "a required product fact is not known",
    AttributeOutcome.ATTRIBUTE_UNVERIFIED: "a required product fact is not verified",
    AttributeOutcome.ATTRIBUTE_CONFLICTED: "sources disagree about a required product fact",
    AttributeOutcome.ATTRIBUTE_VALUE_NOT_IN_SCHEMA: "a product fact holds an unrecognised value",
    AttributeOutcome.UNSUPPORTED_ATTRIBUTE_TYPE: "this attribute cannot be compared deterministically",
    AttributeOutcome.REQUIRED_ATTRIBUTE_MISMATCH: "product does not meet this member's requirement",
    AttributeOutcome.EXCLUDED_ATTRIBUTE_VALUE: "product carries a value this member excluded",
}


@dataclass(frozen=True)
class CompatibilityVerdict:
    """Whether a target product may serve a declaration, and what the member is owed.

    ``is_exact`` is a fact about the two product ids and nothing else. It is stored on
    ``Membership.is_exact_product``, so it has to keep meaning literally what it says.

    ``requires_disclosure`` is a fact about the *member's expectation*. It used to be
    read off ``is_exact``, which worked only while every non-identical match was a
    substitution. A group-level declaration breaks that: the product differs from the
    stored exemplar and yet nothing was substituted, because the member never named the
    exemplar. Telling them "a substitute for the Pike Place you declared" would be an
    apology for doing exactly what they asked. An attribute-constrained declaration is
    the same case for the same reason — they named a rule, and this product satisfies it.

    ``code`` is the stable machine-readable form of ``reason``; ``attribute`` names the
    schema field that decided an attribute verdict, and is empty for every other policy.
    """

    compatible: bool
    is_exact: bool
    reason: str
    code: CompatibilityReason
    requires_disclosure: bool = False
    attribute: str = ""

    def to_dict(self) -> dict:
        return {
            "compatible": self.compatible,
            "is_exact": self.is_exact,
            "reason": self.reason,
            "code": self.code.value,
            "requires_disclosure": self.requires_disclosure,
            "attribute": self.attribute,
        }


def _substitute(
    compatible: bool, reason: str, code: CompatibilityReason
) -> CompatibilityVerdict:
    """A verdict about a product the member did not name. Disclosed when it is used."""
    return CompatibilityVerdict(
        compatible, False, reason, code, requires_disclosure=compatible
    )


_EXACT = CompatibilityVerdict(
    True, True, "exact product requested", CompatibilityReason.EXACT_PRODUCT
)


def _attribute_verdict(
    *,
    target: Product,
    need: NeedDeclaration,
    facts: ProductFactSource,
    is_exact: bool,
) -> CompatibilityVerdict:
    """Evaluate an ``ATTRIBUTE_CONSTRAINED`` declaration against one exact product.

    Nothing here is a substitution, so nothing is disclosed as one — the member stated
    the rule and this product satisfies it. ``is_exact`` still reports the product ids
    honestly, because ``Membership.is_exact_product`` is stored from it.

    An unmapped outcome fails closed. That branch should be unreachable while
    ``_ATTRIBUTE_CODES`` is complete, and it exists because the alternative to an
    unreachable refusal is an unreachable *acceptance*.
    """
    check = check_product_attributes(
        product_id=target.id,
        product_family=target.substitute_group,
        constraint=need.attribute_policy,
        source=facts,
    )
    if check.ok:
        return CompatibilityVerdict(
            True,
            is_exact,
            "product facts satisfy this member's stated requirements",
            CompatibilityReason.ATTRIBUTE_POLICY_SATISFIED,
            requires_disclosure=False,
            attribute=check.attribute,
        )
    return CompatibilityVerdict(
        False,
        is_exact,
        _ATTRIBUTE_SENTENCES.get(check.outcome, "product facts do not satisfy this member"),
        _ATTRIBUTE_CODES.get(check.outcome, CompatibilityReason.UNRECOGNISED_POLICY),
        requires_disclosure=False,
        attribute=check.attribute,
    )


def evaluate_compatibility(
    *,
    target: Product,
    candidate: Product,
    need: NeedDeclaration,
    offer_unit_price_cents: int | None = None,
    facts: ProductFactSource | None = None,
) -> CompatibilityVerdict:
    """Decide whether ``need`` (declared for ``candidate``) may be served by ``target``.

    ``target`` is the product the pool would actually buy; ``candidate`` is what the
    member declared. An exact match short-circuits every other rule — except under
    ``ATTRIBUTE_CONSTRAINED``, where the member's consent is a statement about facts
    rather than about a product id and therefore has to be checked even when the ids
    agree.

    ``facts`` is the authority an attribute policy is evaluated against. It defaults to
    knowing nothing, so a caller that has not wired a fact source in gets refusals rather
    than structural fallbacks: "nobody supplied the facts" and "the member's rule passes"
    must never produce the same answer.
    """
    policy = need.substitution

    if policy == SubstitutionPolicy.ATTRIBUTE_CONSTRAINED:
        # Deliberately before the exact-id short-circuit. A stored declaration names an
        # exemplar for lineage, and a curated fact corrected after it was written — this
        # bag turned out to be decaf — must be able to refuse that exemplar too.
        is_exact = target.id == candidate.id
        if not is_exact:
            # Same ordering as every other policy: the ceiling is a rule about what the
            # member will pay for something they did not name, so it is asked first and
            # the exemplar is exempt from it exactly as an exact match always was.
            ceiling = _ceiling_refusal(need, offer_unit_price_cents)
            if ceiling is not None:
                return ceiling
        return _attribute_verdict(
            target=target,
            need=need,
            facts=facts if facts is not None else NO_FACTS,
            is_exact=is_exact,
        )

    if target.id == candidate.id:
        return _EXACT

    if policy == SubstitutionPolicy.EXACT_ONLY:
        return CompatibilityVerdict(
            False,
            False,
            "member accepts the exact product only",
            CompatibilityReason.EXACT_PRODUCT_REQUIRED,
        )

    # A member's price ceiling applies to every non-exact substitution.
    ceiling = _ceiling_refusal(need, offer_unit_price_cents)
    if ceiling is not None:
        return ceiling

    if policy == SubstitutionPolicy.APPROVED_PRODUCTS:
        ok = target.id in need.approved_product_ids
        return _substitute(
            ok,
            "product is on the member's allowlist" if ok else "product not approved",
            CompatibilityReason.PRODUCT_ALLOWED if ok else CompatibilityReason.PRODUCT_NOT_ALLOWED,
        )

    same_group = bool(target.substitute_group) and target.substitute_group == candidate.substitute_group
    if not same_group:
        return CompatibilityVerdict(
            False, False, "different product family", CompatibilityReason.WRONG_PRODUCT_FAMILY
        )

    if policy == SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT:
        ok = bool(target.brand) and target.brand == candidate.brand
        return _substitute(
            ok,
            "same product, different variant" if ok else "different brand requires broader authority",
            CompatibilityReason.SAME_BRAND_OTHER_VARIANT
            if ok
            else CompatibilityReason.BRAND_NOT_ALLOWED,
        )

    if policy == SubstitutionPolicy.APPROVED_BRANDS:
        ok = bool(target.brand) and target.brand in need.approved_brands
        return _substitute(
            ok,
            "brand is on the member's allowlist" if ok else "brand not approved",
            CompatibilityReason.BRAND_ALLOWED if ok else CompatibilityReason.BRAND_NOT_ALLOWED,
        )

    if policy == SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH:
        ok = target.category == candidate.category
        return _substitute(
            ok,
            "same category and product family" if ok else "different category",
            CompatibilityReason.CATEGORY_MATCH if ok else CompatibilityReason.WRONG_CATEGORY,
        )

    if policy == SubstitutionPolicy.GROUP_DECLARED:
        # The group gate above is the whole test: the member declared this family, so a
        # structural member of it is what they asked for rather than a stand-in for it.
        # No disclosure is owed, and `is_exact` still reports the product ids honestly.
        return CompatibilityVerdict(
            True,
            False,
            "member declared this product family",
            CompatibilityReason.FAMILY_DECLARED,
            requires_disclosure=False,
        )

    # Unknown policies fail closed: an unclassified rule is not evidence of consent.
    return CompatibilityVerdict(
        False, False, "unrecognised substitution policy", CompatibilityReason.UNRECOGNISED_POLICY
    )


def _ceiling_refusal(
    need: NeedDeclaration, offer_unit_price_cents: int | None
) -> CompatibilityVerdict | None:
    """The member's per-unit price ceiling, or ``None`` when it does not bite.

    Applies to every product the member did not name, under every policy that permits
    one. A constrained declaration names no product at all, so it is subject to the same
    ceiling on everything except the exemplar it stores for lineage.
    """
    if (
        need.max_unit_price_cents
        and offer_unit_price_cents is not None
        and offer_unit_price_cents > need.max_unit_price_cents
    ):
        return CompatibilityVerdict(
            False,
            False,
            "substitute exceeds the member's per-unit price ceiling",
            CompatibilityReason.UNIT_PRICE_CEILING_EXCEEDED,
        )
    return None
