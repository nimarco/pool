"""Authoritative product facts, and the typed member policy that reads them (§21).

``domain/substitution.py`` already refused to let a model decide two products are
interchangeable. What it could not express is *why* a member would accept one and refuse
another when both sit in the same curated family. "Coffee" is the example that breaks it:
whole bean and ground are the same product at different grind, caffeinated and decaf are
not the same product at all, and a member who buys whole-bean caffeinated beans has said
something far more specific than "I buy coffee" — something the existing policies had no
field for.

Three pieces, and the boundary between them is the whole design.

:class:`ProductFamilySchema`
    What attributes exist for one curated family, what values they may take, and which
    of them a product must carry before it can be reasoned about at all. **Versioned**,
    because a member's stored policy was written against one reading of the world and
    must not be silently reinterpreted under another.

:class:`ProductAttributeFact`
    What is actually true of one product, with its provenance and verification state
    attached. Curated data. **The model is never the source of a fact** — there is no
    path by which a model-authored value can arrive here, which is the point of making
    facts a separate object with a provenance field rather than more columns on
    ``Product``.

:class:`AttributeConstraint`
    One member's deterministic policy over that schema: hard requirements, hard
    exclusions, and — kept rigorously separate — soft preferences that may order a
    choice and may never create or remove one.

Everything below fails closed. An unknown fact, an unverified fact, a fact written
against a different schema version, a policy naming an attribute the schema does not
define — every one of them makes the product *incompatible*, never compatible. A
compatibility layer that guesses in the member's favour is not a compatibility layer; it
is Pool deciding what somebody will accept on their behalf.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class AttributeValueType(str, Enum):
    """How a value may be compared.

    One member, deliberately. ``ENUM`` is a closed set of curated tokens compared for
    equality, which is the only comparison this build can perform deterministically and
    the only one the curated family needs. A numeric or ranged attribute would need its
    own ordering, its own units, and its own fail-closed rules; declaring one before
    those exist would produce a schema the evaluator cannot honour. Any other type
    therefore fails closed rather than being approximated (see
    :data:`AttributeOutcome.UNSUPPORTED_ATTRIBUTE_TYPE`).
    """

    ENUM = "enum"


class FactProvenance(str, Enum):
    """Where a product fact came from. Never "the model" — there is no such member.

    Deliberately a different axis from :class:`~pool.domain.models.ProductSource`, which
    records where a product's *consumer identity* came from. A product's name may be
    read off a public catalogue while the facts Pool computes compatibility from are
    curated by hand, and the interface has to be able to say exactly that.
    """

    #: Hand-authored for this build and committed to the repository. Synthetic.
    CURATED_SYNTHETIC = "curated_synthetic"
    #: Entered by a human operator against a real product. None exist yet.
    OPERATOR_VERIFIED = "operator_verified"


class FactVerification(str, Enum):
    """Whether a fact may be relied on.

    Only ``VERIFIED`` is evidence. ``UNVERIFIED`` is a value somebody wrote down and
    nobody confirmed; ``CONFLICTED`` is two sources disagreeing. Both are *more*
    dangerous than an absent fact, because they look like data — so both are refused
    with their own reason code rather than being folded into "unknown".
    """

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"


# --------------------------------------------------------------------------- schema


@dataclass(frozen=True)
class AttributeDefinition:
    """One attribute a curated family's products may carry.

    ``required_for_compatibility`` is the strong flag and it is not about the member. It
    says: *no product in this family may be matched by attribute policy at all unless it
    carries a verified value for this.* It belongs on the attributes that decide what a
    product physically **is** — grind, caffeine — rather than the ones that decide
    whether somebody likes it. A member who never mentions roast can still be served a
    product whose roast nobody has confirmed; a member cannot be served something whose
    grind nobody has confirmed, whatever their policy says, because the family's own
    definition says that fact is load-bearing.
    """

    key: str
    value_type: AttributeValueType
    allowed_values: frozenset[str]
    required_for_compatibility: bool = False

    def permits(self, value: str) -> bool:
        return value in self.allowed_values

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value_type": self.value_type.value,
            # Sorted, so two equal schemas serialise identically and a stored policy can
            # be compared against a shipped one without set-ordering noise.
            "allowed_values": sorted(self.allowed_values),
            "required_for_compatibility": self.required_for_compatibility,
        }


@dataclass(frozen=True)
class ProductFamilySchema:
    """The authoritative definition of one curated family's attributes.

    ``version`` is load-bearing rather than decorative. A member's stored
    :class:`AttributeConstraint` records the version it was written against, and a fact
    records the version it was curated under. When either disagrees with the shipped
    schema the evaluator refuses instead of reinterpreting — because "whole bean" meaning
    something slightly different after a re-curation is precisely the kind of drift that
    would broaden somebody's consent without anybody deciding to.

    Attribute order is the declaration order and is honoured everywhere the evaluator
    iterates, so the reason code a refusal produces is stable across runs and processes.
    """

    family: str
    version: int
    attributes: tuple[AttributeDefinition, ...] = ()

    def definition(self, key: str) -> AttributeDefinition | None:
        return next((a for a in self.attributes if a.key == key), None)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(a.key for a in self.attributes)

    @property
    def required_attributes(self) -> tuple[AttributeDefinition, ...]:
        return tuple(a for a in self.attributes if a.required_for_compatibility)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "version": self.version,
            "attributes": [a.to_dict() for a in self.attributes],
        }


# ---------------------------------------------------------------------------- facts


@dataclass(frozen=True)
class ProductAttributeFact:
    """One authoritative statement about one product.

    Deterministic data with its provenance attached, not an inference. ``family`` and
    ``schema_version`` travel with the value so a fact curated under one reading of a
    family cannot be silently consumed under another.
    """

    product_id: str
    family: str
    attribute: str
    value: str
    provenance: FactProvenance
    verification: FactVerification
    schema_version: int
    #: Where the curation is recorded, e.g. a file and date. Never a URL with a credential.
    source_ref: str = ""

    @property
    def is_authoritative(self) -> bool:
        return self.verification is FactVerification.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "family": self.family,
            "attribute": self.attribute,
            "value": self.value,
            "provenance": self.provenance.value,
            "verification": self.verification.value,
            "schema_version": self.schema_version,
            "source_ref": self.source_ref,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ProductAttributeFact:
        return cls(
            product_id=str(d["product_id"]),
            family=str(d["family"]),
            attribute=str(d["attribute"]),
            value=str(d["value"]),
            provenance=FactProvenance(d.get("provenance", "curated_synthetic")),
            verification=FactVerification(d.get("verification", "unverified")),
            schema_version=int(d.get("schema_version", 0)),
            source_ref=str(d.get("source_ref", "")),
        )


@runtime_checkable
class ProductFactSource(Protocol):
    """Where the evaluator reads authority from.

    A protocol rather than a module-level lookup so the authority is *injected* and
    therefore visible: a service can be handed a different curated set in a test, and no
    code path can reach for facts it was not given. ``PoolContext`` carries the one the
    application uses, alongside the repository and the payment provider, because it is
    the same kind of thing — a collaborator whose reach should be explicit.
    """

    def family_schema(self, family: str) -> ProductFamilySchema | None:
        """The shipped schema for a family, or ``None`` if the family is not curated."""

    def facts_for(self, product_id: str) -> Mapping[str, ProductAttributeFact]:
        """Every authoritative fact held for one product, keyed by attribute."""


class EmptyFactSource:
    """A source that knows nothing. The default, and it authorises nothing.

    Constrained matching without an injected source must refuse rather than fall back to
    structural comparison, so "nobody wired the facts in" and "the member's policy is
    satisfied" can never produce the same answer.
    """

    def family_schema(self, family: str) -> ProductFamilySchema | None:
        return None

    def facts_for(self, product_id: str) -> Mapping[str, ProductAttributeFact]:
        return {}


NO_FACTS = EmptyFactSource()


# ----------------------------------------------------------------------- the policy


class ConstraintError(ValueError):
    """A member policy the schema will not accept. Carries a human reason."""


def _frozen(values: Iterable[str]) -> frozenset[str]:
    return frozenset(str(v) for v in values)


@dataclass(frozen=True)
class AttributeConstraint:
    """One member's deterministic policy over a curated family (the CONSTRAINED case).

    Three fields, and the split between the first two and the third is the entire point:

    ``requires``
        attribute → the values that are acceptable. **Hard.** One value is a
        requirement ("must be whole bean"); several are an acceptable range ("medium or
        dark"). They are the same statement — "the value must be one of these" — so they
        are one field rather than two that could disagree.
    ``excludes``
        attribute → values that are refused outright. **Hard.** Not redundant with
        ``requires``: excluding ``DECAF`` says something about a fact the member insists
        on knowing, and stays true if the schema later gains a fourth roast.
    ``prefers``
        attribute → values in preference order. **Soft, and structurally inert.** Nothing
        in :func:`check_product_attributes` reads it. It exists so a later stage can
        *order* choices the member has already authorised, and it can never create or
        remove one.

    Frozen because it is a record of consent. It is not hashable — the mappings are
    ordinary dicts — and nothing hashes it.
    """

    family: str
    schema_version: int
    requires: Mapping[str, frozenset[str]] = field(default_factory=dict)
    excludes: Mapping[str, frozenset[str]] = field(default_factory=dict)
    prefers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def has_hard_rule(self) -> bool:
        return any(self.requires.values()) or any(self.excludes.values())

    def to_dict(self) -> dict[str, Any]:
        """A stable, DynamoDB-safe shape: sorted lists, no sets, no tuples.

        Sets do not survive the resource API's serialiser as written and their iteration
        order is not stable across processes, so a stored policy would otherwise differ
        byte-for-byte between two writes of the same consent.
        """
        return {
            "family": self.family,
            "schema_version": self.schema_version,
            "requires": {k: sorted(v) for k, v in sorted(self.requires.items())},
            "excludes": {k: sorted(v) for k, v in sorted(self.excludes.items())},
            # Preference order is meaningful, so it is emitted as given, not sorted.
            "prefers": {k: list(v) for k, v in sorted(self.prefers.items())},
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> AttributeConstraint:
        return cls(
            family=str(d.get("family", "")),
            schema_version=int(d.get("schema_version", 0)),
            requires={
                str(k): _frozen(v) for k, v in dict(d.get("requires") or {}).items()
            },
            excludes={
                str(k): _frozen(v) for k, v in dict(d.get("excludes") or {}).items()
            },
            prefers={
                str(k): tuple(str(x) for x in v)
                for k, v in dict(d.get("prefers") or {}).items()
            },
        )


def validate_constraint(
    constraint: AttributeConstraint, schema: ProductFamilySchema | None
) -> None:
    """Refuse a policy the schema cannot honour. Raises :class:`ConstraintError`.

    Called at the edge, when a member writes a declaration, so a policy that could never
    match anything is rejected while somebody is still there to be told why. The
    evaluator re-runs the same check on every stored policy rather than trusting that
    this ran: a schema version can be superseded after a declaration was written, and a
    policy that was valid then must not be quietly reinterpreted now.
    """
    if schema is None:
        raise ConstraintError("no curated attribute schema exists for that product family")
    if schema.family != constraint.family:
        raise ConstraintError("that policy was written for a different product family")
    if schema.version != constraint.schema_version:
        raise ConstraintError(
            "that policy was written against a different version of the product schema"
        )
    if not constraint.has_hard_rule:
        # A "constrained" policy with nothing hard in it is not a narrower statement
        # than declaring the family — it is the same statement wearing a stricter name,
        # and it would authorise the whole family while reading as a restriction.
        raise ConstraintError(
            "a constrained declaration must state at least one requirement or exclusion"
        )

    for label, mapping in (
        ("requires", constraint.requires),
        ("excludes", constraint.excludes),
        ("prefers", constraint.prefers),
    ):
        for key, values in mapping.items():
            definition = schema.definition(key)
            if definition is None:
                raise ConstraintError(f"{key!r} is not an attribute of that product family")
            if definition.value_type is not AttributeValueType.ENUM:
                raise ConstraintError(f"{key!r} cannot be compared deterministically")
            if label != "prefers" and not values:
                raise ConstraintError(f"{key!r} was given no acceptable values")
            for value in values:
                if not definition.permits(value):
                    raise ConstraintError(f"{value!r} is not a value {key!r} may take")

    for key, required in constraint.requires.items():
        excluded = constraint.excludes.get(key, frozenset())
        if required & excluded:
            raise ConstraintError(
                f"{key!r} both requires and excludes the same value"
            )


# ------------------------------------------------------------------- the evaluation


class AttributeOutcome(str, Enum):
    """Why an attribute policy accepted or refused one product.

    Stable machine-readable tokens, not human copy. They are what a later stage counts
    ("eleven members excluded on ``caffeine``"), what an audit trail stores, and what a
    refusal is explained from — so they name the *cause*, and the sentence a person reads
    is composed somewhere else.
    """

    SATISFIED = "attribute_policy_satisfied"
    #: The declaration claims a constrained policy and carries none.
    POLICY_MISSING = "attribute_policy_missing"
    #: The stored policy no longer type-checks against the shipped schema.
    POLICY_INVALID = "attribute_policy_invalid"
    #: No curated schema exists for the family the policy names.
    UNKNOWN_FAMILY_SCHEMA = "unknown_product_family_schema"
    #: The policy, the fact, or the product was written against another schema version.
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    #: The candidate product is not in the family the policy governs.
    WRONG_PRODUCT_FAMILY = "wrong_product_family"
    #: No authoritative fact is held for an attribute the decision needs.
    ATTRIBUTE_UNKNOWN = "attribute_unknown"
    #: A fact exists and nobody confirmed it.
    ATTRIBUTE_UNVERIFIED = "attribute_unverified"
    #: Sources disagree about the value.
    ATTRIBUTE_CONFLICTED = "attribute_conflicted"
    #: A fact holds a value the schema does not define.
    ATTRIBUTE_VALUE_NOT_IN_SCHEMA = "attribute_value_not_in_schema"
    #: The attribute cannot be compared deterministically at all.
    UNSUPPORTED_ATTRIBUTE_TYPE = "unsupported_attribute_type"
    #: The product's value is not one this member accepts.
    REQUIRED_ATTRIBUTE_MISMATCH = "required_attribute_mismatch"
    #: The product's value is one this member refused outright.
    EXCLUDED_ATTRIBUTE_VALUE = "excluded_attribute_value"


@dataclass(frozen=True)
class AttributeCheck:
    """The verdict of one attribute-policy evaluation.

    ``attribute`` names the field that decided it, which is what makes the refusal
    actionable later: a cohort that fails on ``roast`` is a different problem from one
    that fails on ``form``, and a code alone cannot tell them apart.
    """

    ok: bool
    outcome: AttributeOutcome
    attribute: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "outcome": self.outcome.value, "attribute": self.attribute}


_SATISFIED = AttributeCheck(True, AttributeOutcome.SATISFIED)


def _fact_problem(
    fact: ProductAttributeFact | None,
    definition: AttributeDefinition,
    *,
    product_id: str,
    family: str,
    schema_version: int,
) -> AttributeOutcome | None:
    """Why this fact may not be relied on, or ``None`` if it may.

    Every branch here is a refusal. There is deliberately no path that returns "usable
    enough": an unverified value and a value curated under a different schema version are
    both things somebody might reasonably have meant, and acting on either would be Pool
    deciding what a member accepts from evidence it does not have.
    """
    if fact is None:
        return AttributeOutcome.ATTRIBUTE_UNKNOWN
    if fact.product_id != product_id or fact.attribute != definition.key:
        # A fact filed under the wrong key. The curated registry cannot produce this,
        # because it indexes by the fact's own fields — but a fact source is an injected
        # collaborator and a hand-built one could, and mis-attributing one bag's grind to
        # another is the exact failure this layer exists to make impossible. Reported as
        # unknown, which is what it is: no usable fact for this attribute of this product.
        return AttributeOutcome.ATTRIBUTE_UNKNOWN
    if fact.family != family or fact.schema_version != schema_version:
        return AttributeOutcome.SCHEMA_VERSION_MISMATCH
    if fact.verification is FactVerification.CONFLICTED:
        return AttributeOutcome.ATTRIBUTE_CONFLICTED
    if fact.verification is not FactVerification.VERIFIED:
        return AttributeOutcome.ATTRIBUTE_UNVERIFIED
    if not definition.permits(fact.value):
        return AttributeOutcome.ATTRIBUTE_VALUE_NOT_IN_SCHEMA
    return None


def check_product_attributes(
    *,
    product_id: str,
    product_family: str,
    constraint: AttributeConstraint | None,
    source: ProductFactSource,
) -> AttributeCheck:
    """Does this exact product satisfy this member's attribute policy?

    Pure. No I/O, no clock, no model. Given the same policy, the same product and the
    same facts it returns the same answer in every process, which is what lets a refusal
    be re-derived later and checked.

    The order is the order of a fail-closed gate, widest doubt first: is there a policy
    at all, does a schema exist for it, does the policy still type-check, is this product
    even in that family, does the product carry the facts the *family* says are
    load-bearing, and only then — do the member's own rules pass. Soft preferences are
    not consulted anywhere in it.
    """
    if constraint is None:
        return AttributeCheck(False, AttributeOutcome.POLICY_MISSING)

    schema = source.family_schema(constraint.family)
    if schema is None:
        return AttributeCheck(False, AttributeOutcome.UNKNOWN_FAMILY_SCHEMA)
    if schema.version != constraint.schema_version:
        return AttributeCheck(False, AttributeOutcome.SCHEMA_VERSION_MISMATCH)

    # A whole family refuses if any one of its attributes is a type this build cannot
    # compare. Checked here rather than only where the member's policy mentions one,
    # because the family's *required* attributes are read whatever the policy says — so
    # a required attribute with an unimplemented type would otherwise be compared for
    # equality anyway, which is the approximation the type field exists to prevent.
    unsupported = next(
        (a for a in schema.attributes if a.value_type is not AttributeValueType.ENUM), None
    )
    if unsupported is not None:
        return AttributeCheck(
            False, AttributeOutcome.UNSUPPORTED_ATTRIBUTE_TYPE, unsupported.key
        )

    try:
        validate_constraint(constraint, schema)
    except ConstraintError:
        return AttributeCheck(False, AttributeOutcome.POLICY_INVALID)

    # Cross-family substitution is refused before any fact is read. A policy about
    # coffee says nothing whatsoever about shampoo, and the family gate is what
    # guarantees that rather than a promise in the copy.
    if product_family != constraint.family:
        return AttributeCheck(False, AttributeOutcome.WRONG_PRODUCT_FAMILY)

    facts = source.facts_for(product_id)

    # The family's own floor. Iterated in schema order so the code is reproducible.
    for definition in schema.required_attributes:
        problem = _fact_problem(
            facts.get(definition.key),
            definition,
            product_id=product_id,
            family=constraint.family,
            schema_version=constraint.schema_version,
        )
        if problem is not None:
            return AttributeCheck(False, problem, definition.key)

    for definition in schema.attributes:
        key = definition.key
        acceptable = constraint.requires.get(key)
        forbidden = constraint.excludes.get(key)
        if not acceptable and not forbidden:
            continue

        fact = facts.get(key)
        problem = _fact_problem(
            fact,
            definition,
            product_id=product_id,
            family=constraint.family,
            schema_version=constraint.schema_version,
        )
        if problem is not None or fact is None:
            # ``fact is None`` is already ATTRIBUTE_UNKNOWN above; the second test is
            # here so this stays correct rather than merely true, and so the narrowing
            # is visible to a reader and a type checker instead of assumed.
            return AttributeCheck(
                False, problem or AttributeOutcome.ATTRIBUTE_UNKNOWN, key
            )

        # Exclusion first: a value the member refused outright cannot be rescued by
        # also appearing in an acceptable set, and reporting the refusal is more useful
        # than reporting the mismatch it would otherwise produce.
        if forbidden and fact.value in forbidden:
            return AttributeCheck(False, AttributeOutcome.EXCLUDED_ATTRIBUTE_VALUE, key)
        if acceptable and fact.value not in acceptable:
            return AttributeCheck(False, AttributeOutcome.REQUIRED_ATTRIBUTE_MISMATCH, key)

    return _SATISFIED


def preference_rank(
    *,
    constraint: AttributeConstraint,
    schema: ProductFamilySchema,
    facts: Mapping[str, ProductAttributeFact],
) -> tuple[int, ...]:
    """How well an already-authorised product matches the member's soft preferences.

    Lower is better; a plain ``min`` or ``sort`` over this tuple orders a set of products
    the member has *already* been found compatible with. One position per schema
    attribute in declaration order, so two products are always compared on the same axes
    in the same order.

    An attribute the member expressed no preference about scores 0 and therefore never
    separates anything. A value outside their preference list, or one nobody has
    verified, sorts last rather than being refused — this function has no authority to
    refuse and is not consulted by :func:`check_product_attributes`. That separation is
    the invariant: a soft preference can reorder what a member may be given and can never
    change what they may be given.
    """
    ranks: list[int] = []
    for definition in schema.attributes:
        order = constraint.prefers.get(definition.key, ())
        if not order:
            ranks.append(0)
            continue
        fact = facts.get(definition.key)
        if fact is None or not fact.is_authoritative or fact.value not in order:
            ranks.append(len(order))
            continue
        ranks.append(order.index(fact.value))
    return tuple(ranks)
