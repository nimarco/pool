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

Every policy above ``EXACT_ONLY`` additionally honours a per-unit price ceiling when
the member set one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import NeedDeclaration, Product, SubstitutionPolicy


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
    apology for doing exactly what they asked.
    """

    compatible: bool
    is_exact: bool
    reason: str
    requires_disclosure: bool = False

    def to_dict(self) -> dict:
        return {
            "compatible": self.compatible,
            "is_exact": self.is_exact,
            "reason": self.reason,
            "requires_disclosure": self.requires_disclosure,
        }


def _substitute(compatible: bool, reason: str) -> CompatibilityVerdict:
    """A verdict about a product the member did not name. Disclosed when it is used."""
    return CompatibilityVerdict(compatible, False, reason, requires_disclosure=compatible)


_EXACT = CompatibilityVerdict(True, True, "exact product requested")


def evaluate_compatibility(
    *,
    target: Product,
    candidate: Product,
    need: NeedDeclaration,
    offer_unit_price_cents: int | None = None,
) -> CompatibilityVerdict:
    """Decide whether ``need`` (declared for ``candidate``) may be served by ``target``.

    ``target`` is the product the pool would actually buy; ``candidate`` is what the
    member declared. An exact match short-circuits every other rule.
    """
    if target.id == candidate.id:
        return _EXACT

    policy = need.substitution
    if policy == SubstitutionPolicy.EXACT_ONLY:
        return CompatibilityVerdict(False, False, "member accepts the exact product only")

    # A member's price ceiling applies to every non-exact substitution.
    if (
        need.max_unit_price_cents
        and offer_unit_price_cents is not None
        and offer_unit_price_cents > need.max_unit_price_cents
    ):
        return CompatibilityVerdict(
            False, False, "substitute exceeds the member's per-unit price ceiling"
        )

    if policy == SubstitutionPolicy.APPROVED_PRODUCTS:
        ok = target.id in need.approved_product_ids
        return _substitute(
            ok, "product is on the member's allowlist" if ok else "product not approved"
        )

    same_group = bool(target.substitute_group) and target.substitute_group == candidate.substitute_group
    if not same_group:
        return CompatibilityVerdict(False, False, "different product family")

    if policy == SubstitutionPolicy.SAME_PRODUCT_OTHER_VARIANT:
        ok = bool(target.brand) and target.brand == candidate.brand
        return _substitute(
            ok,
            "same product, different variant" if ok else "different brand requires broader authority",
        )

    if policy == SubstitutionPolicy.APPROVED_BRANDS:
        ok = bool(target.brand) and target.brand in need.approved_brands
        return _substitute(
            ok, "brand is on the member's allowlist" if ok else "brand not approved"
        )

    if policy == SubstitutionPolicy.STRUCTURED_CATEGORY_MATCH:
        ok = target.category == candidate.category
        return _substitute(
            ok, "same category and product family" if ok else "different category"
        )

    if policy == SubstitutionPolicy.GROUP_DECLARED:
        # The group gate above is the whole test: the member declared this family, so a
        # structural member of it is what they asked for rather than a stand-in for it.
        # No disclosure is owed, and `is_exact` still reports the product ids honestly.
        return CompatibilityVerdict(
            True, False, "member declared this product family", requires_disclosure=False
        )

    # Unknown policies fail closed: an unclassified rule is not evidence of consent.
    return CompatibilityVerdict(False, False, "unrecognised substitution policy")
