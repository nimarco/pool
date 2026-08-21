"""Domain entities.

These are plain dataclasses with explicit `to_dict`/`from_dict` so the same shapes
travel to DynamoDB, the HTTP API, and the agent's tool results without a second
schema drifting out of sync.

Locations are stored as approximate coordinates only. Pool never holds a precise
street address for a member (AGENTS.md §4) — the demo dataset is synthetic and
jittered, and the UI is only ever shown community-level context.

Vocabulary note
---------------
``Community`` is the fundamental trust + density boundary (a campus, an apartment
complex, a neighbourhood, a workplace). ``Household`` is the *account* unit inside
one or more Communities — on a campus that is usually one student, in a residential
Community it may be a family. The name is retained from the first build because it
is the account unit either way; Community membership is a separate entity so one
account can belong to several Communities.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from .attributes import AttributeConstraint


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def parse_iso(text: str) -> datetime:
    """Parse an ISO timestamp, assuming UTC when no offset is present."""
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# --------------------------------------------------------------------------- enums


class CommunityKind(str, Enum):
    """A Community is the local boundary Pool coordinates inside.

    Campus is the go-to-market wedge, not a special case in the domain.
    """

    UNIVERSITY = "university"
    APARTMENT = "apartment"
    NEIGHBORHOOD = "neighborhood"
    WORKPLACE = "workplace"
    ORGANIZATION = "organization"


class MembershipStatus(str, Enum):
    """Whether an account is a verified member of a Community."""

    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    LEFT = "left"


class VerificationMethod(str, Enum):
    DEMO = "demo"                    # synthetic Community; no real-world claim
    EMAIL_DOMAIN = "email_domain"    # proved control of an address on an allowed domain
    INSTITUTIONAL_SSO = "institutional_sso"  # not implemented; reserved


class AutonomyMode(str, Enum):
    """How much authority an account has granted Pool."""

    ASK_ME = "ask_me"
    SMART_JOIN = "smart_join"


class SubstitutionPolicy(str, Enum):
    """Structured product-substitution authority.

    Deterministic by construction. The model never decides that two products are
    "close enough" — it reads the verdict of ``domain.substitution`` (§21).

    ``GROUP_DECLARED`` is the one member that is not a *substitution* rule at all. The
    others answer "I named this product — what else may serve it?". That one answers "I
    named a family, and any member of it is what I asked for." The distinction is not
    cosmetic: it decides whether the interface owes the member a disclosure, because
    being handed Pike Place is a substitution only if you asked for something else.

    ``ATTRIBUTE_CONSTRAINED`` is the second such member, and the narrower one. It answers
    "I named a *rule*": the member accepts any product in one curated family whose
    authoritative attribute facts satisfy a policy they stated —
    ``NeedDeclaration.attribute_policy``, evaluated by ``domain.attributes``. It is what
    the three shapes a real household has need to be expressible as three different
    things rather than one blunt one:

    * **exact** — ``EXACT_ONLY``: this SKU and nothing else.
    * **flexible** — ``APPROVED_PRODUCTS``: an allowlist the member wrote. The model may
      never add to it.
    * **constrained** — ``ATTRIBUTE_CONSTRAINED``: a typed rule over curated product
      facts, satisfied by products the member has never seen and could not have listed.
    """

    EXACT_ONLY = "exact_only"
    SAME_PRODUCT_OTHER_VARIANT = "same_product_other_variant"
    APPROVED_PRODUCTS = "approved_products"
    APPROVED_BRANDS = "approved_brands"
    STRUCTURED_CATEGORY_MATCH = "structured_category_match"
    GROUP_DECLARED = "group_declared"
    ATTRIBUTE_CONSTRAINED = "attribute_constrained"


class PoolStatus(str, Enum):
    """Canonical lifecycle of one buying pool (§18).

    Transitions are enforced deterministically in ``pool.domain.state`` — the model
    never picks a transition directly (AGENTS.md §5).
    """

    FORMING = "forming"                  # candidate pool; demand accumulating, no host yet
    HOST_RECRUITING = "host_recruiting"  # MOQ reachable; fulfilment being recruited
    HOST_SELECTED = "host_selected"      # a host accepted the job
    FINAL_OFFER = "final_offer"          # quote refreshed; exact landed economics issued
    FUNDING = "funding"                  # authorisations being collected
    RECOVERING = "recovering"            # funding or viability broke; agent is repairing
    LOCKED = "locked"                    # every viability condition passed; captures run
    PURCHASE_READY = "purchase_ready"    # payments captured; supplier purchase pending
    PURCHASED = "purchased"              # purchase executed (simulated in this build)
    DISTRIBUTING = "distributing"        # host holds the goods; pickup window open
    COMPLETED = "completed"
    FAILED = "failed"                    # could not become viable
    EXPIRED = "expired"                  # a deadline passed while still forming


TERMINAL_POOL_STATUSES = {PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED}

#: Past this point buyers have been charged and the supplier order is committed.
#: Leaving is no longer a one-click action (§59).
COMMITTED_POOL_STATUSES = {
    PoolStatus.LOCKED,
    PoolStatus.PURCHASE_READY,
    PoolStatus.PURCHASED,
    PoolStatus.DISTRIBUTING,
    PoolStatus.COMPLETED,
}


class ParticipationState(str, Enum):
    """A buyer's relationship to one pool (§25).

    Provisional participation is *not* financial commitment. Only ``AUTHORIZED``
    and beyond count toward the funded threshold.
    """

    ELIGIBLE = "eligible"                    # matched, not yet counted
    PROVISIONAL = "provisional"              # counted for discovery only
    FINAL_OFFERED = "final_offered"          # exact landed price issued, awaiting answer
    AUTHORIZED = "authorized"                # payment authorised for the exact amount
    LOCKED = "locked"                        # captured at pool lock
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    AUTHORIZATION_FAILED = "authorization_failed"


#: States whose units count toward the *funded* threshold.
FUNDED_PARTICIPATION_STATES = {ParticipationState.AUTHORIZED, ParticipationState.LOCKED}
#: States whose units count toward *provisional* (discovery) demand.
PROVISIONAL_PARTICIPATION_STATES = {
    ParticipationState.PROVISIONAL,
    ParticipationState.FINAL_OFFERED,
    ParticipationState.AUTHORIZED,
    ParticipationState.LOCKED,
}
#: States in which the member is no longer part of the pool at all — they said no, or
#: they left. Everything else, including a *failed* authorisation, is still a live
#: relationship: the row stays on the record, the member still needs to know about it,
#: and the recovery branch is built on being able to see it.
#:
#: Stated once because four different places were deciding "is this person still in
#: this pool" with their own inline copy of this set, and a pool card, a map pin and a
#: re-recruitment guard disagreeing about that is exactly how somebody ends up being
#: shown an order they had already withdrawn from.
LEFT_PARTICIPATION_STATES = {ParticipationState.DECLINED, ParticipationState.WITHDRAWN}
#: The complement: the member is genuinely in this pool right now.
LIVE_PARTICIPATION_STATES = frozenset(set(ParticipationState) - LEFT_PARTICIPATION_STATES)


class AutonomyPath(str, Enum):
    """How a buyer came to be committed — the audit trail for §5 HITL."""

    SMART_JOIN = "smart_join"
    HUMAN_APPROVED = "human_approved"
    PENDING_APPROVAL = "pending_approval"


class DecisionKind(str, Enum):
    JOIN_POOL = "join_pool"                # provisional join needs a human
    APPROVE_FINAL_OFFER = "approve_final_offer"  # exact landed price needs a human
    ACCEPT_SUBSTITUTE = "accept_substitute"
    HOST_OFFER = "host_offer"              # a host has been offered the job
    PRICE_CHANGED = "price_changed"        # material change before lock


class DecisionState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OfferKind(str, Enum):
    RETAIL = "retail"  # the per-buyer baseline someone would pay alone
    BULK = "bulk"


class MoqKind(str, Enum):
    """What the supplier's minimum is measured in."""

    UNITS = "units"
    CASES = "cases"


class OfferSource(str, Enum):
    """Provenance of a supplier offer (§41, §42). Never presented as more than it is."""

    SYNTHETIC = "synthetic"                  # generated demo catalogue
    MANUAL_VERIFIED = "manual_verified"      # an operator entered and verified it
    SUPPLIER_SUBMITTED = "supplier_submitted"
    LIVE_RETAILER = "live_retailer"          # reserved; not implemented


class ProductSource(str, Enum):
    """Where a product's *consumer identity* came from — never where its price came from.

    This is deliberately a different axis from :class:`OfferSource`. A product can be a
    real, verifiable item off a public catalogue while the only quote Pool holds for it
    is synthetic, and the interface has to be able to say exactly that (§41). Collapsing
    the two would let a real brand name lend credibility to an invented price.
    """

    CURATED = "curated"                      # hand-authored, e.g. the demo seed
    OPEN_FOOD_FACTS = "open_food_facts"      # Open Food Facts snapshot (ODbL)
    MEMBER_SUBMITTED = "member_submitted"    # a member described it; awaiting curation


class HostCandidateSource(str, Enum):
    STANDING = "standing"                    # previously registered as willing to host
    POOL_MEMBER_VOLUNTEER = "pool_member_volunteer"  # clicked "Offer to host" on this pool


class HostCandidateState(str, Enum):
    """Bounded host offer states (§34). 'Offer to host' never claims the job (§28)."""

    CANDIDATE = "candidate"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    INELIGIBLE = "ineligible"
    UNAVAILABLE = "unavailable"


class FulfillerRole(str, Enum):
    """Runner and pickup host are modelled separately so a future split is possible (§39)."""

    RUNNER = "runner"      # supplier -> pickup site
    HOST = "host"          # pickup site -> buyers
    FULFILLER = "fulfiller"  # both; the only role used in v1


class PaymentState(str, Enum):
    """Internal payment state, mapped carefully to provider state (§57).

    There is deliberately no ``paid`` boolean anywhere in this system.
    """

    NONE = "none"
    PAYMENT_METHOD_REQUIRED = "payment_method_required"
    AUTHORIZATION_PENDING = "authorization_pending"
    AUTHORIZED = "authorized"
    AUTHORIZATION_FAILED = "authorization_failed"
    CAPTURE_PENDING = "capture_pending"
    CAPTURED = "captured"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class AllocationState(str, Enum):
    """Physical fulfilment state of one buyer's units (§73)."""

    PENDING_PURCHASE = "pending_purchase"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP = "picked_up"
    NO_SHOW = "no_show"
    SECONDARY_PICKUP = "secondary_pickup"
    UNCLAIMED = "unclaimed"
    ISSUE_REVIEW = "issue_review"


class PickupPermission(str, Enum):
    """Whether a pickup location is actually authorised for this use (§67)."""

    DEMO = "demo"                                # synthetic; no real-world permission implied
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    RESTRICTED = "restricted"


class AnnouncementKind(str, Enum):
    """Structured operational messages (§78, §79). Not a group chat."""

    SYSTEM = "system"
    HOST_ARRIVED = "host_arrived"
    HOST_RUNNING_LATE = "host_running_late"
    LOCATION_CHANGED = "location_changed"
    PICKUP_ENDING_SOON = "pickup_ending_soon"
    HOST_CUSTOM = "host_custom"


class ExceptionKind(str, Enum):
    """Structured buyer exceptions, offered before free-text messaging (§81)."""

    RUNNING_LATE = "running_late"
    NEED_ALTERNATE_PICKUP = "need_alternate_pickup"
    CANNOT_PICK_UP = "cannot_pick_up"
    PROBLEM_WITH_ORDER = "problem_with_order"
    OTHER = "other"


class IssueKind(str, Enum):
    WRONG_ITEM = "wrong_item"
    DAMAGED_ITEM = "damaged_item"
    MISSING_ITEM = "missing_item"
    SUPPLIER_FAILURE = "supplier_failure"
    RECALL = "recall"
    PICKUP_DISPUTE = "pickup_dispute"
    REFUND_REQUEST = "refund_request"


class IssueState(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RunOutcome(str, Enum):
    POOL_CREATED = "pool_created"
    POOL_ADVANCED = "pool_advanced"
    POOL_RECOVERED = "pool_recovered"
    NO_ACTION = "no_action"
    LOOP_FAULT = "loop_fault"
    ERROR = "error"


# --------------------------------------------------------------------------- config


@dataclass(frozen=True)
class PoolDaySchedule:
    """Concentrated weekly rhythm for one Community (§23).

    Weekdays are Python's convention: Monday is 0. Nothing here is hardcoded to a
    particular day globally — a Community that distributes on Wednesday simply
    configures Wednesday.
    """

    formation_cutoff_weekday: int = 3   # Thursday: candidate pools evaluated
    host_deadline_weekday: int = 4      # Friday: hosts confirmed
    final_offer_weekday: int = 4        # Friday: final offers + authorisations
    lock_weekday: int = 4               # Friday evening: pool locks
    distribution_weekday: int = 5       # Saturday: supplier pickup + distribution
    distribution_start_hour: int = 14
    distribution_end_hour: int = 17

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PoolDaySchedule:
        base = cls()
        return cls(**{f: int(d.get(f, getattr(base, f))) for f in base.__dataclass_fields__})


@dataclass(frozen=True)
class PlatformFeeConfig:
    """Pool's own transparent take (§49).

    Default is a share of the savings the group actually achieved: Pool earns only
    when the buyers are better off, and the fee is always shown as a line item.
    This is provisional business configuration, not domain truth.
    """

    mode: str = "percent_of_savings"  # percent_of_savings | percent_of_merchandise | fixed_per_buyer
    bps: int = 1000                   # 10.00%
    fixed_cents_per_buyer: int = 0
    minimum_cents: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlatformFeeConfig:
        return cls(
            mode=str(d.get("mode", "percent_of_savings")),
            bps=int(d.get("bps", 1000)),
            fixed_cents_per_buyer=int(d.get("fixed_cents_per_buyer", 0)),
            minimum_cents=int(d.get("minimum_cents", 0)),
        )


@dataclass(frozen=True)
class ProcessingFeeConfig:
    """Payment processing, modelled explicitly rather than absorbed (§50).

    Defaults mirror a common card-processing shape. The exact schedule belongs to
    whatever processor a real pilot signs with; it is configuration, not truth.
    """

    bps: int = 290           # 2.90%
    fixed_cents: int = 30    # per authorised buyer

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProcessingFeeConfig:
        return cls(bps=int(d.get("bps", 290)), fixed_cents=int(d.get("fixed_cents", 30)))


@dataclass(frozen=True)
class HostRewardConfig:
    """Deterministic, configurable host compensation formula (§37).

    Compensation scales with the work actually done: a 30-order run pays more than
    a 5-order run. Buyers fund all of it (§36); Pool never subsidises it.
    """

    base_cents: int = 1500
    per_order_cents: int = 120
    per_km_cents: int = 95
    per_kg_over_threshold_cents: int = 8
    weight_threshold_kg: int = 25
    merchandise_bps: int = 0          # optional share of merchandise value
    handoff_bonus_cents: int = 500    # contingent on verified pickups (§38)
    minimum_cents: int = 2000
    maximum_cents: int = 25_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostRewardConfig:
        base = cls()
        return cls(**{f: int(d.get(f, getattr(base, f))) for f in base.__dataclass_fields__})


# --------------------------------------------------------------------------- entities


@dataclass
class Community:
    """The local trust + density boundary Pool coordinates inside (§9)."""

    id: str
    name: str
    kind: CommunityKind
    center_lat: float
    center_lon: float
    radius_km: float = 3.0
    timezone: str = "America/Chicago"
    verification_methods: list[VerificationMethod] = field(
        default_factory=lambda: [VerificationMethod.DEMO]
    )
    email_domains: list[str] = field(default_factory=list)
    schedule: PoolDaySchedule = field(default_factory=PoolDaySchedule)
    platform_fee: PlatformFeeConfig = field(default_factory=PlatformFeeConfig)
    processing_fee: ProcessingFeeConfig = field(default_factory=ProcessingFeeConfig)
    host_reward: HostRewardConfig = field(default_factory=HostRewardConfig)
    #: Minimum platform contribution for a pool to be worth running at all (§52).
    min_platform_contribution_cents: int = 100
    #: How long a supplier quote may be used before a final offer must refresh it (§43).
    quote_max_age_hours: int = 48
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["verification_methods"] = [m.value for m in self.verification_methods]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Community:
        return cls(
            id=d["id"],
            name=d["name"],
            kind=CommunityKind(d["kind"]),
            center_lat=float(d["center_lat"]),
            center_lon=float(d["center_lon"]),
            radius_km=float(d.get("radius_km", 3.0)),
            timezone=d.get("timezone", "America/Chicago"),
            verification_methods=[
                VerificationMethod(m) for m in d.get("verification_methods", ["demo"])
            ],
            email_domains=list(d.get("email_domains", [])),
            schedule=PoolDaySchedule.from_dict(d.get("schedule", {})),
            platform_fee=PlatformFeeConfig.from_dict(d.get("platform_fee", {})),
            processing_fee=ProcessingFeeConfig.from_dict(d.get("processing_fee", {})),
            host_reward=HostRewardConfig.from_dict(d.get("host_reward", {})),
            min_platform_contribution_cents=int(d.get("min_platform_contribution_cents", 100)),
            quote_max_age_hours=int(d.get("quote_max_age_hours", 48)),
            synthetic=bool(d.get("synthetic", True)),
        )


@dataclass
class CommunityMembership:
    """Account authentication and Community membership are separate concerns (§10).

    Keyed on (community_id, household_id), so one account belonging to several
    Communities is a schema fact rather than a future migration.
    """

    community_id: str
    household_id: str
    status: MembershipStatus
    verification_method: VerificationMethod
    verified_at: str = ""
    #: Only non-identifying verification evidence is ever stored — e.g. the *domain*
    #: an address belonged to, never the address itself (AGENTS.md §4).
    verification_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.community_id}#{self.household_id}"

    @property
    def is_verified(self) -> bool:
        return self.status == MembershipStatus.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["verification_method"] = self.verification_method.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CommunityMembership:
        return cls(
            community_id=d["community_id"],
            household_id=d["household_id"],
            status=MembershipStatus(d["status"]),
            verification_method=VerificationMethod(d["verification_method"]),
            verified_at=d.get("verified_at", ""),
            verification_metadata=d.get("verification_metadata", {}),
        )


@dataclass
class AutonomyPolicy:
    """An account's Smart Join rules (§53).

    Machine-verifiable by construction: every field is a number, a boolean, or a
    structured enum that ``pool.domain.policy`` compares deterministically. The
    model never interprets this — it only reads the verdict (AGENTS.md §5).
    """

    mode: AutonomyMode = AutonomyMode.ASK_ME
    min_savings_pct: int = 20
    max_total_cost_cents: int = 5000
    max_travel_minutes: int = 15
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY
    public_pickup_only: bool = True
    #: Weekdays (Mon=0) this account can collect an order. Empty means "any day".
    available_pickup_weekdays: list[int] = field(default_factory=list)

    @property
    def allow_substitutes(self) -> bool:
        return self.substitution != SubstitutionPolicy.EXACT_ONLY

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        d["substitution"] = self.substitution.value
        d["allow_substitutes"] = self.allow_substitutes
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AutonomyPolicy:
        return cls(
            mode=AutonomyMode(d.get("mode", "ask_me")),
            min_savings_pct=int(d.get("min_savings_pct", 20)),
            max_total_cost_cents=int(d.get("max_total_cost_cents", 5000)),
            max_travel_minutes=int(d.get("max_travel_minutes", 15)),
            substitution=SubstitutionPolicy(d.get("substitution", "exact_only")),
            public_pickup_only=bool(d.get("public_pickup_only", True)),
            available_pickup_weekdays=[int(x) for x in d.get("available_pickup_weekdays", [])],
        )


@dataclass
class Household:
    """The account unit. On a campus this is usually one student."""

    id: str
    display_name: str
    lat: float
    lon: float
    neighborhood: str = ""       # display-level locality inside the Community
    autonomy: AutonomyPolicy = field(default_factory=AutonomyPolicy)
    #: Stored privately for notifications. Never emitted by any serializer (§82).
    contact_email: str = ""
    #: Opaque provider reference for a saved payment method (§55). Not a card number.
    payment_method_ref: str = ""
    synthetic: bool = True
    #: When the person using this account finished setting it up, if they ever did.
    #:
    #: Exactly one household per workspace is the *consumer* — the person actually at
    #: the screen — and everybody else is a synthetic neighbour who exists so there is
    #: something to coordinate with. This is what tells them apart, and it lives here
    #: rather than in the browser for two reasons: the display name and payment state it
    #: gates are authoritative server state, and a demo reset has to be able to clear it.
    onboarded_at: str = ""

    @property
    def is_onboarded(self) -> bool:
        return bool(self.onboarded_at)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["autonomy"] = self.autonomy.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Household:
        return cls(
            id=d["id"],
            display_name=d["display_name"],
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            neighborhood=d.get("neighborhood", ""),
            autonomy=AutonomyPolicy.from_dict(d.get("autonomy", {})),
            contact_email=d.get("contact_email", ""),
            payment_method_ref=d.get("payment_method_ref", ""),
            synthetic=bool(d.get("synthetic", True)),
            onboarded_at=d.get("onboarded_at", ""),
        )


@dataclass
class Product:
    """What a member believes they are buying.

    Two groups of fields, and the boundary between them is load-bearing.

    The first group is **structure Pool computes with**: ``unit`` is the sealed consumer
    unit an offer is priced against, ``unit_weight_grams`` feeds host capacity, and
    ``substitute_group`` is the only thing that lets one member's demand combine with
    another's. Every one of them is curated, because a wrong value here does not look
    wrong — it silently produces a confident, incorrect price.

    The second group is **identity a person recognises**: brand, variant, GTIN, image,
    search aliases. These may come from a public catalogue, because being wrong about
    them is visible to the member the moment they look at the card.

    Public product data is emphatically not admitted to the first group. Open Food Facts
    package sizes, for instance, are frequently absent, expressed in a serving rather
    than a package, or free text ("I tablesp") — so ``display_size`` is a string for
    humans and nothing multiplies it (§48).
    """

    id: str
    name: str
    category: str
    unit: str                 # the sealed consumer unit: "tub", "can", "roll", "bottle"
    substitute_group: str     # products sharing a group are structurally related
    brand: str = ""
    variant: str = ""         # flavour / scent / size descriptor
    unit_weight_grams: int = 0
    #: Sealed consumer units only. Pool does not open, divide, or repackage (§47).
    individually_sealed: bool = True

    # --- consumer identity. Optional by construction: a product with none of this is
    #     still a perfectly valid Pool product, which is what keeps the seed and every
    #     stored row from before this existed readable.
    gtin: str = ""            # GTIN/UPC/EAN as printed. Identity only; never arithmetic.
    #: Slug of a *bundled* image asset. Deliberately not a URL — the demo may not depend
    #: on a third-party image host being alive, and the CSP is ``img-src 'self'``.
    image_ref: str = ""
    image_attribution: str = ""
    #: Package size **as text**, for recognition on a product card. Never parsed.
    display_size: str = ""
    #: Extra words a member might type. Curated, not inferred.
    synonyms: list[str] = field(default_factory=list)
    source: ProductSource = ProductSource.CURATED
    source_ref: str = ""      # snapshot provenance, e.g. "openfoodfacts:2026-08-19"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Product:
        return cls(
            id=d["id"],
            name=d["name"],
            category=d["category"],
            unit=d["unit"],
            substitute_group=d["substitute_group"],
            brand=d.get("brand", ""),
            variant=d.get("variant", ""),
            unit_weight_grams=int(d.get("unit_weight_grams", 0)),
            individually_sealed=bool(d.get("individually_sealed", True)),
            gtin=d.get("gtin", ""),
            image_ref=d.get("image_ref", ""),
            image_attribution=d.get("image_attribution", ""),
            display_size=d.get("display_size", ""),
            synonyms=list(d.get("synonyms", [])),
            source=ProductSource(d.get("source", "curated")),
            source_ref=d.get("source_ref", ""),
        )

    @property
    def display_name(self) -> str:
        """Brand and variant folded into one line, the way a card shows it."""
        parts = [p for p in (self.brand, self.name) if p]
        base = " ".join(parts) if parts else self.name
        return f"{base} — {self.variant}" if self.variant else base


@dataclass
class NeedDeclaration:
    """A standing statement of recurring need — the only thing a member must do (§20).

    Timing is first-class: Pool may only pull a future need forward inside the window
    the member themselves authorised (§24).
    """

    id: str
    household_id: str
    community_id: str
    product_id: str
    quantity: int
    cadence_days: int
    #: When this member next expects to need the item.
    expected_next_need_date: date
    #: The window inside which a purchase is acceptable. ``earliest`` is what makes
    #: pulling future demand forward legitimate rather than presumptuous.
    earliest_acceptable_purchase_date: date | None = None
    latest_acceptable_purchase_date: date | None = None
    #: How many days before the need date this member ordinarily restocks. A purchase
    #: inside this lead is *routine*; anything earlier is a genuine pull-forward and is
    #: only permitted because ``earliest_acceptable_purchase_date`` says so (§24).
    routine_lead_days: int = 7
    min_savings_pct: int = 20
    max_spend_cents: int = 5000
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY
    approved_product_ids: list[str] = field(default_factory=list)
    approved_brands: list[str] = field(default_factory=list)
    #: The typed rule an ``ATTRIBUTE_CONSTRAINED`` declaration carries, and the only
    #: policy that reads it. Absent everywhere else, including on every row written
    #: before this field existed — which is why the compatibility layer treats a missing
    #: policy as authorising nothing rather than as authorising the family.
    attribute_policy: AttributeConstraint | None = None
    max_unit_price_cents: int = 0  # 0 = no explicit cap
    active: bool = True
    #: How many times a member has materially changed this declaration. Not a version
    #: number for optimistic locking and not an audit trail — it exists so that going
    #: back to something you said before is a *new* thing to have said. Coordination is
    #: keyed on the content of a declaration (``services/events.declaration_digest``),
    #: and without this a member who narrows their rules and then widens them again
    #: lands on the digest of the first version, whose coordination already ran and
    #: whose outcome no longer describes a world they were withdrawn from in between.
    #: ``amend_need`` moves it only when the content actually changed, so re-saving an
    #: unchanged form still costs nothing.
    revision: int = 0

    @property
    def accept_substitutes(self) -> bool:
        return self.substitution != SubstitutionPolicy.EXACT_ONLY

    @property
    def earliest(self) -> date:
        """Earliest date this member permits a purchase. Defaults to 'today or later'."""
        return self.earliest_acceptable_purchase_date or date.min

    @property
    def latest(self) -> date:
        """Latest useful purchase date. Defaults to the expected need date."""
        return self.latest_acceptable_purchase_date or self.expected_next_need_date

    @property
    def flexibility_days(self) -> int:
        """How many days early this member is willing to buy."""
        if self.earliest_acceptable_purchase_date is None:
            return 0
        return max(0, (self.expected_next_need_date - self.earliest_acceptable_purchase_date).days)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["expected_next_need_date"] = self.expected_next_need_date.isoformat()
        d["earliest_acceptable_purchase_date"] = (
            self.earliest_acceptable_purchase_date.isoformat()
            if self.earliest_acceptable_purchase_date
            else None
        )
        d["latest_acceptable_purchase_date"] = (
            self.latest_acceptable_purchase_date.isoformat()
            if self.latest_acceptable_purchase_date
            else None
        )
        d["substitution"] = self.substitution.value
        # `asdict` recurses into the constraint and leaves frozensets and tuples behind,
        # neither of which DynamoDB's serialiser accepts and neither of which has a
        # stable iteration order. The constraint's own `to_dict` emits sorted lists, so
        # the same consent always serialises to the same bytes.
        d["attribute_policy"] = (
            self.attribute_policy.to_dict() if self.attribute_policy else None
        )
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NeedDeclaration:
        def _date(key: str) -> date | None:
            raw = d.get(key)
            return date.fromisoformat(raw) if raw else None

        return cls(
            id=d["id"],
            household_id=d["household_id"],
            community_id=d["community_id"],
            product_id=d["product_id"],
            quantity=int(d["quantity"]),
            cadence_days=int(d["cadence_days"]),
            expected_next_need_date=date.fromisoformat(d["expected_next_need_date"]),
            earliest_acceptable_purchase_date=_date("earliest_acceptable_purchase_date"),
            latest_acceptable_purchase_date=_date("latest_acceptable_purchase_date"),
            routine_lead_days=int(d.get("routine_lead_days", 7)),
            min_savings_pct=int(d.get("min_savings_pct", 20)),
            max_spend_cents=int(d.get("max_spend_cents", 5000)),
            substitution=SubstitutionPolicy(d.get("substitution", "exact_only")),
            approved_product_ids=list(d.get("approved_product_ids", [])),
            approved_brands=list(d.get("approved_brands", [])),
            # A row written before this field existed has no key, and a row whose policy
            # was cleared has an explicit null. Both mean the same thing and both must
            # keep meaning it: no attribute authority whatsoever.
            attribute_policy=(
                AttributeConstraint.from_dict(d["attribute_policy"])
                if d.get("attribute_policy")
                else None
            ),
            max_unit_price_cents=int(d.get("max_unit_price_cents", 0)),
            active=bool(d.get("active", True)),
            # Absent on every row written before revisions existed. Zero is the right
            # reading: those declarations have been amended zero times *as far as this
            # field is concerned*, and the first material amendment moves them to one.
            revision=int(d.get("revision", 0)),
        )


@dataclass
class Supplier:
    id: str
    name: str
    lat: float
    lon: float
    community_id: str = ""   # empty = serves any Community
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Supplier:
        return cls(
            id=d["id"],
            name=d["name"],
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            community_id=d.get("community_id", ""),
            synthetic=bool(d.get("synthetic", True)),
        )


@dataclass
class Offer:
    """A normalized supplier offer (§42).

    Freshness is explicit and load-bearing: a final buyer offer may never rest on a
    quote older than the Community's ``quote_max_age_hours`` (§43).
    """

    id: str
    supplier_id: str
    product_id: str
    kind: OfferKind
    unit_price_cents: int         # price per sealed consumer unit at this tier
    case_units: int = 1           # sealed units per purchasable case
    moq_kind: MoqKind = MoqKind.UNITS
    moq_amount: int = 1           # supplier minimum, in ``moq_kind``
    verified_at: str = ""         # when this quote was last confirmed
    valid_until: str = ""         # provider-stated expiry, if any
    source: OfferSource = OfferSource.SYNTHETIC
    supplier_reference: str = ""  # SKU / UPC / quote number where available
    active: bool = True

    @property
    def case_price_cents(self) -> int:
        return self.unit_price_cents * self.case_units

    @property
    def min_units(self) -> int:
        """The supplier minimum expressed in sealed units, whatever it was quoted in."""
        if self.moq_kind == MoqKind.CASES:
            return self.moq_amount * self.case_units
        return self.moq_amount

    @property
    def is_synthetic(self) -> bool:
        return self.source == OfferSource.SYNTHETIC

    def age_hours(self, now: datetime | None = None) -> float | None:
        """Hours since this quote was verified, or None if it never was."""
        if not self.verified_at:
            return None
        delta = (now or utcnow()) - parse_iso(self.verified_at)
        return delta.total_seconds() / 3600.0

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.valid_until:
            return False
        return (now or utcnow()) > parse_iso(self.valid_until)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["moq_kind"] = self.moq_kind.value
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Offer:
        return cls(
            id=d["id"],
            supplier_id=d["supplier_id"],
            product_id=d["product_id"],
            kind=OfferKind(d["kind"]),
            unit_price_cents=int(d["unit_price_cents"]),
            case_units=int(d.get("case_units", 1)),
            moq_kind=MoqKind(d.get("moq_kind", "units")),
            moq_amount=int(d.get("moq_amount", 1)),
            verified_at=d.get("verified_at", ""),
            valid_until=d.get("valid_until", ""),
            source=OfferSource(d.get("source", "synthetic")),
            supplier_reference=d.get("supplier_reference", ""),
            active=bool(d.get("active", True)),
        )


@dataclass
class PickupSite:
    """A pickup location is an entity with a permission status, not a free string (§67)."""

    id: str
    name: str
    community_id: str
    lat: float
    lon: float
    is_public: bool = True
    kind: str = "campus_common"  # campus_common | library | residence_hall | apartment_common
    permission: PickupPermission = PickupPermission.DEMO
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["permission"] = self.permission.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PickupSite:
        return cls(
            id=d["id"],
            name=d["name"],
            community_id=d["community_id"],
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            is_public=bool(d.get("is_public", True)),
            kind=d.get("kind", "campus_common"),
            permission=PickupPermission(d.get("permission", "demo")),
            notes=d.get("notes", ""),
        )


@dataclass
class HostProfile:
    """Standing willingness to take fulfilment jobs (§29).

    A profile is created either by opting in ahead of time, or on the spot when a
    pool member clicks "Offer to host" — the same shape either way.
    """

    household_id: str
    community_id: str
    willing_to_host: bool = True
    willing_to_run: bool = True
    has_vehicle: bool = False
    vehicle_capacity_units: int = 0
    max_orders: int = 40
    max_weight_kg: int = 60
    max_supplier_distance_km: float = 15.0
    available_weekdays: list[int] = field(default_factory=list)  # empty = any
    minimum_compensation_cents: int = 2000
    public_pickup_only: bool = True
    preferred_pickup_site_ids: list[str] = field(default_factory=list)
    standing: bool = True  # False when created ad hoc for a single pool

    @property
    def key(self) -> str:
        return f"{self.community_id}#{self.household_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostProfile:
        return cls(
            household_id=d["household_id"],
            community_id=d["community_id"],
            willing_to_host=bool(d.get("willing_to_host", True)),
            willing_to_run=bool(d.get("willing_to_run", True)),
            has_vehicle=bool(d.get("has_vehicle", False)),
            vehicle_capacity_units=int(d.get("vehicle_capacity_units", 0)),
            max_orders=int(d.get("max_orders", 40)),
            max_weight_kg=int(d.get("max_weight_kg", 60)),
            max_supplier_distance_km=float(d.get("max_supplier_distance_km", 15.0)),
            available_weekdays=[int(x) for x in d.get("available_weekdays", [])],
            minimum_compensation_cents=int(d.get("minimum_compensation_cents", 2000)),
            public_pickup_only=bool(d.get("public_pickup_only", True)),
            preferred_pickup_site_ids=list(d.get("preferred_pickup_site_ids", [])),
            standing=bool(d.get("standing", True)),
        )


@dataclass
class HostCandidate:
    """One evaluated host option for one pool.

    Being a candidate is not holding the job: several people can offer at once, the
    deterministic evaluator ranks them, and only the offered candidate can accept (§28).
    """

    pool_id: str
    household_id: str
    source: HostCandidateSource
    state: HostCandidateState
    eligible: bool = True
    ineligible_reasons: list[str] = field(default_factory=list)
    score: int = 0
    score_components: dict[str, int] = field(default_factory=dict)
    estimated_reward_cents: int = 0
    supplier_distance_km: float = 0.0
    buyer_travel_penalty_minutes: int = 0
    offered_at: str = ""
    responded_at: str = ""
    expires_at: str = ""

    @property
    def key(self) -> str:
        return f"{self.pool_id}#{self.household_id}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostCandidate:
        return cls(
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            source=HostCandidateSource(d["source"]),
            state=HostCandidateState(d["state"]),
            eligible=bool(d.get("eligible", True)),
            ineligible_reasons=list(d.get("ineligible_reasons", [])),
            score=int(d.get("score", 0)),
            score_components={k: int(v) for k, v in (d.get("score_components") or {}).items()},
            estimated_reward_cents=int(d.get("estimated_reward_cents", 0)),
            supplier_distance_km=float(d.get("supplier_distance_km", 0.0)),
            buyer_travel_penalty_minutes=int(d.get("buyer_travel_penalty_minutes", 0)),
            offered_at=d.get("offered_at", ""),
            responded_at=d.get("responded_at", ""),
            expires_at=d.get("expires_at", ""),
        )


@dataclass
class HostAssignment:
    """The accepted fulfilment job, with its compensation broken out line by line.

    Buyer allocation and host compensation are separate ledger events even when the
    same person is both (§30) — they are never netted together invisibly.
    """

    pool_id: str
    household_id: str
    role: FulfillerRole
    pickup_site_id: str
    supplier_distance_km: float
    handled_orders: int
    handled_units: int
    estimated_weight_kg: int
    reward_breakdown: dict[str, int] = field(default_factory=dict)
    reward_total_cents: int = 0
    #: Earned once fulfilment responsibility is discharged, regardless of no-shows (§38).
    reward_earned_cents: int = 0
    #: Contingent on verified handoffs.
    reward_contingent_cents: int = 0
    reward_paid_cents: int = 0
    accepted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HostAssignment:
        return cls(
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            role=FulfillerRole(d.get("role", "fulfiller")),
            pickup_site_id=d["pickup_site_id"],
            supplier_distance_km=float(d.get("supplier_distance_km", 0.0)),
            handled_orders=int(d.get("handled_orders", 0)),
            handled_units=int(d.get("handled_units", 0)),
            estimated_weight_kg=int(d.get("estimated_weight_kg", 0)),
            reward_breakdown={k: int(v) for k, v in (d.get("reward_breakdown") or {}).items()},
            reward_total_cents=int(d.get("reward_total_cents", 0)),
            reward_earned_cents=int(d.get("reward_earned_cents", 0)),
            reward_contingent_cents=int(d.get("reward_contingent_cents", 0)),
            reward_paid_cents=int(d.get("reward_paid_cents", 0)),
            accepted_at=d.get("accepted_at", ""),
        )


@dataclass
class Membership:
    """One buyer's participation in one pool.

    ``estimated_*`` fields hold the pre-host, pre-final-offer range shown on a
    candidate pool; ``final_*`` fields are only populated once a host is selected and
    the supplier quote has been refreshed (§35).
    """

    pool_id: str
    household_id: str
    need_id: str
    requested_units: int
    allocated_units: int
    state: ParticipationState
    path: AutonomyPath
    estimated_cost_cents: int = 0
    baseline_cents: int = 0
    travel_minutes: int = 0
    final_cost_cents: int = 0
    final_savings_cents: int = 0
    final_savings_bps: int = 0
    final_offer_at: str = ""
    payment_id: str = ""
    is_exact_product: bool = True
    #: Set only when *Pool* took this member out of the pool because their own amended
    #: rules stopped permitting it — it holds the compatibility reason code. Empty when a
    #: person left of their own accord, and the difference is load-bearing: widening your
    #: preferences again may undo something Pool did to you, and must never undo
    #: something you did yourself. Somebody who leaves an order stays gone.
    withdrawn_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.pool_id}#{self.household_id}"

    @property
    def counts_as_funded(self) -> bool:
        return self.state in FUNDED_PARTICIPATION_STATES

    @property
    def counts_as_provisional(self) -> bool:
        return self.state in PROVISIONAL_PARTICIPATION_STATES

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["path"] = self.path.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Membership:
        return cls(
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            need_id=d["need_id"],
            requested_units=int(d["requested_units"]),
            allocated_units=int(d["allocated_units"]),
            state=ParticipationState(d["state"]),
            path=AutonomyPath(d["path"]),
            estimated_cost_cents=int(d.get("estimated_cost_cents", 0)),
            baseline_cents=int(d.get("baseline_cents", 0)),
            travel_minutes=int(d.get("travel_minutes", 0)),
            final_cost_cents=int(d.get("final_cost_cents", 0)),
            final_savings_cents=int(d.get("final_savings_cents", 0)),
            final_savings_bps=int(d.get("final_savings_bps", 0)),
            final_offer_at=d.get("final_offer_at", ""),
            payment_id=d.get("payment_id", ""),
            is_exact_product=bool(d.get("is_exact_product", True)),
            # Absent on rows written before reconciliation existed. Empty is the safe
            # reading: nobody is re-admitted to a pool on the strength of a missing key.
            withdrawn_reason=d.get("withdrawn_reason", ""),
        )


@dataclass
class PoolTiming:
    """Explicit lifecycle deadlines (§22). Pool never buys the instant MOQ is touched."""

    formation_opens_at: str = ""
    host_recruiting_opens_at: str = ""
    host_acceptance_deadline: str = ""
    final_offer_at: str = ""
    authorization_deadline: str = ""
    lock_at: str = ""
    purchase_by: str = ""
    distribution_starts_at: str = ""
    distribution_ends_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PoolTiming:
        base = cls()
        return cls(**{f: str(d.get(f, "")) for f in base.__dataclass_fields__})


@dataclass
class Pool:
    id: str
    community_id: str
    product_id: str
    offer_id: str
    pickup_site_id: str
    status: PoolStatus
    threshold_units: int          # supplier MOQ in sealed units
    timing: PoolTiming = field(default_factory=PoolTiming)
    created_by_run: str = ""
    created_at: str = field(default_factory=lambda: iso(utcnow()))
    idempotency_key: str = ""
    #: Snapshot of the economics issued as the final offer. Empty until §35 completes.
    final_economics: dict[str, Any] = field(default_factory=dict)
    #: The quote timestamp the final offer relies on — the anti-stale-price anchor.
    quote_verified_at: str = ""
    host_household_id: str = ""
    failure_reason: str = ""

    @property
    def has_final_offer(self) -> bool:
        return bool(self.final_economics)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["timing"] = self.timing.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pool:
        return cls(
            id=d["id"],
            community_id=d["community_id"],
            product_id=d["product_id"],
            offer_id=d["offer_id"],
            pickup_site_id=d["pickup_site_id"],
            status=PoolStatus(d["status"]),
            threshold_units=int(d["threshold_units"]),
            timing=PoolTiming.from_dict(d.get("timing", {})),
            created_by_run=d.get("created_by_run", ""),
            created_at=d.get("created_at", iso(utcnow())),
            idempotency_key=d.get("idempotency_key", ""),
            final_economics=d.get("final_economics", {}),
            quote_verified_at=d.get("quote_verified_at", ""),
            host_household_id=d.get("host_household_id", ""),
            failure_reason=d.get("failure_reason", ""),
        )


@dataclass
class PaymentRecord:
    """Pool's internal view of one buyer's money for one pool.

    Never authoritative on its own: the provider is the source of truth for provider
    facts, and this record maps them onto explicit internal states (§57).
    """

    id: str
    pool_id: str
    household_id: str
    amount_cents: int
    state: PaymentState
    provider: str = "simulated"
    provider_mode: str = "simulated"     # simulated | test  — never "live" in this build
    provider_ref: str = ""
    payment_method_ref: str = ""
    idempotency_key: str = ""
    authorized_at: str = ""
    captured_at: str = ""
    cancelled_at: str = ""
    failure_code: str = ""
    failure_message: str = ""
    #: Provider event ids already applied, so a replayed webhook is a no-op (§61).
    applied_event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PaymentRecord:
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            amount_cents=int(d["amount_cents"]),
            state=PaymentState(d["state"]),
            provider=d.get("provider", "simulated"),
            provider_mode=d.get("provider_mode", "simulated"),
            provider_ref=d.get("provider_ref", ""),
            payment_method_ref=d.get("payment_method_ref", ""),
            idempotency_key=d.get("idempotency_key", ""),
            authorized_at=d.get("authorized_at", ""),
            captured_at=d.get("captured_at", ""),
            cancelled_at=d.get("cancelled_at", ""),
            failure_code=d.get("failure_code", ""),
            failure_message=d.get("failure_message", ""),
            applied_event_ids=list(d.get("applied_event_ids", [])),
        )


@dataclass
class PurchaseRecord:
    """Provenance for the bulk purchase (§65).

    In this build ``simulated`` is always True and the UI says so. A pilot swaps the
    executor, not the record.
    """

    id: str
    pool_id: str
    supplier_id: str
    offer_snapshot: dict[str, Any]
    units_purchased: int
    cases_purchased: int
    total_cents: int
    supplier_reference: str
    executed_at: str
    executor: str = "simulated"
    simulated: bool = True
    receipt_reference: str = ""
    lot_reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PurchaseRecord:
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            supplier_id=d["supplier_id"],
            offer_snapshot=d.get("offer_snapshot", {}),
            units_purchased=int(d["units_purchased"]),
            cases_purchased=int(d["cases_purchased"]),
            total_cents=int(d["total_cents"]),
            supplier_reference=d.get("supplier_reference", ""),
            executed_at=d["executed_at"],
            executor=d.get("executor", "simulated"),
            simulated=bool(d.get("simulated", True)),
            receipt_reference=d.get("receipt_reference", ""),
            lot_reference=d.get("lot_reference", ""),
        )


@dataclass
class FulfillmentRun:
    """One physical supplier trip.

    In v1 a run contains exactly one pool. The list shape exists so batching several
    pools into one trip is a later optimisation rather than a migration (§66).
    """

    id: str
    community_id: str
    pool_ids: list[str]
    fulfiller_household_id: str
    pickup_site_id: str
    starts_at: str
    ends_at: str
    state: str = "scheduled"  # scheduled | collected | distributing | complete
    created_at: str = field(default_factory=lambda: iso(utcnow()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FulfillmentRun:
        return cls(
            id=d["id"],
            community_id=d["community_id"],
            pool_ids=list(d["pool_ids"]),
            fulfiller_household_id=d["fulfiller_household_id"],
            pickup_site_id=d["pickup_site_id"],
            starts_at=d["starts_at"],
            ends_at=d["ends_at"],
            state=d.get("state", "scheduled"),
            created_at=d.get("created_at", iso(utcnow())),
        )


@dataclass
class PickupAllocation:
    """One buyer's physical units in one pool."""

    pool_id: str
    household_id: str
    units: int
    state: AllocationState = AllocationState.PENDING_PURCHASE
    picked_up_at: str = ""
    picked_up_via: str = ""   # qr | code | operator_override
    override_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.pool_id}#{self.household_id}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PickupAllocation:
        return cls(
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            units=int(d["units"]),
            state=AllocationState(d.get("state", "pending_purchase")),
            picked_up_at=d.get("picked_up_at", ""),
            picked_up_via=d.get("picked_up_via", ""),
            override_reason=d.get("override_reason", ""),
        )


@dataclass
class PickupToken:
    """A one-time pickup credential (§69, §70).

    Only *hashes* are stored. The plaintext token and short code exist exactly once,
    in the response that issued them; re-issuing invalidates the previous pair. The
    credential carries no payment details, phone number, or email — it is an opaque
    random value bound server-side to one pool and one buyer.
    """

    id: str
    pool_id: str
    household_id: str
    token_hash: str
    code_hash: str
    issued_at: str
    redeemed_at: str = ""
    revoked: bool = False

    @property
    def key(self) -> str:
        return f"{self.pool_id}#{self.household_id}"

    @property
    def is_redeemable(self) -> bool:
        return not self.revoked and not self.redeemed_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PickupToken:
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            token_hash=d["token_hash"],
            code_hash=d["code_hash"],
            issued_at=d["issued_at"],
            redeemed_at=d.get("redeemed_at", ""),
            revoked=bool(d.get("revoked", False)),
        )


@dataclass
class Announcement:
    """A structured, pool-scoped operational message. Reaches the pool once (§79)."""

    id: str
    pool_id: str
    kind: AnnouncementKind
    body: str
    author_household_id: str = ""  # empty means system-generated
    created_at: str = field(default_factory=lambda: iso(utcnow()))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Announcement:
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            kind=AnnouncementKind(d["kind"]),
            body=d["body"],
            author_household_id=d.get("author_household_id", ""),
            created_at=d.get("created_at", iso(utcnow())),
        )


@dataclass
class MessageThread:
    """A private, transaction-scoped buyer <-> assigned-host thread (§80).

    Not a social DM system: a thread exists only for one pool and one buyer, and a
    host can never open one with an unrelated account.
    """

    id: str
    pool_id: str
    buyer_household_id: str
    host_household_id: str
    exception_kind: ExceptionKind | None = None
    state: str = "open"  # open | resolved | archived
    created_at: str = field(default_factory=lambda: iso(utcnow()))

    @property
    def key(self) -> str:
        return f"{self.pool_id}#{self.buyer_household_id}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["exception_kind"] = self.exception_kind.value if self.exception_kind else None
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MessageThread:
        kind = d.get("exception_kind")
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            buyer_household_id=d["buyer_household_id"],
            host_household_id=d["host_household_id"],
            exception_kind=ExceptionKind(kind) if kind else None,
            state=d.get("state", "open"),
            created_at=d.get("created_at", iso(utcnow())),
        )


@dataclass
class Message:
    id: str
    thread_id: str
    sender_household_id: str
    body: str
    at: str = field(default_factory=lambda: iso(utcnow()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(**d)


@dataclass
class IssueCase:
    """Lightweight product/fulfilment issue tracking (§75).

    The host is not customer support for a manufacturer defect; an issue routes to
    operator review instead of landing on whoever carried the box.
    """

    id: str
    pool_id: str
    household_id: str
    kind: IssueKind
    state: IssueState
    detail: str = ""
    created_at: str = field(default_factory=lambda: iso(utcnow()))
    resolved_at: str = ""
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IssueCase:
        return cls(
            id=d["id"],
            pool_id=d["pool_id"],
            household_id=d["household_id"],
            kind=IssueKind(d["kind"]),
            state=IssueState(d["state"]),
            detail=d.get("detail", ""),
            created_at=d.get("created_at", iso(utcnow())),
            resolved_at=d.get("resolved_at", ""),
            resolution=d.get("resolution", ""),
        )


@dataclass
class DecisionRequest:
    """A question that genuinely needs a human. The Decision Inbox is built from these."""

    id: str
    household_id: str
    pool_id: str
    kind: DecisionKind
    state: DecisionState
    facts: dict[str, Any]
    created_at: str = field(default_factory=lambda: iso(utcnow()))
    expires_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DecisionRequest:
        return cls(
            id=d["id"],
            household_id=d["household_id"],
            pool_id=d["pool_id"],
            kind=DecisionKind(d["kind"]),
            state=DecisionState(d["state"]),
            facts=d.get("facts", {}),
            created_at=d.get("created_at", iso(utcnow())),
            expires_at=d.get("expires_at", ""),
        )


@dataclass
class ActivityEvent:
    """User-visible structured audit record. Never contains model reasoning text."""

    id: str
    kind: str
    summary: str
    facts: dict[str, Any] = field(default_factory=dict)
    pool_id: str | None = None
    household_id: str | None = None
    run_id: str | None = None
    at: str = field(default_factory=lambda: iso(utcnow()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ActivityEvent:
        return cls(**d)


@dataclass
class ToolCallRecord:
    name: str
    arguments_digest: str
    ok: bool
    summary: str
    at: str = field(default_factory=lambda: iso(utcnow()))


@dataclass
class AgentRun:
    """Operational metadata for one coordinator run.

    Deliberately excludes any model reasoning text — tool names, structured results,
    counters, and a termination reason only (AGENTS.md §9, brief §96).
    """

    id: str
    trigger: str
    model_id: str
    model_provider: str
    started_at: str
    ended_at: str | None = None
    outcome: RunOutcome = RunOutcome.NO_ACTION
    iterations: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    termination_reason: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    hitl_decisions_created: int = 0
    notes: list[str] = field(default_factory=list)
    #: What this run was *asked* — the objective the coordinator derived from stored
    #: state before it began (``agent/objective.py``). Recorded because a run report has
    #: to distinguish "investigated and declined" from "never investigated", and the
    #: difference is not visible anywhere in what the run did.
    #: The coordination event that caused this run, when one did. Lineage in the
    #: direction a question is actually asked: a member changed a declaration, an event
    #: recorded that work was owed, and this run answered it.
    event_id: str = ""
    objective_kind: str = "community"
    #: The member a member-triggered run belongs to. A synthetic household id, never a
    #: name or a contact detail; it is what stops one member's report being served for
    #: another member's run.
    objective_household_id: str = ""
    #: Declarations the run took on, held back by the per-run cap, and already inside a
    #: live pool. Ids only.
    objective_need_ids: list[str] = field(default_factory=list)
    deferred_need_ids: list[str] = field(default_factory=list)
    served_need_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentRun:
        return cls(
            id=d["id"],
            trigger=d["trigger"],
            model_id=d["model_id"],
            model_provider=d["model_provider"],
            started_at=d["started_at"],
            ended_at=d.get("ended_at"),
            outcome=RunOutcome(d.get("outcome", "no_action")),
            iterations=int(d.get("iterations", 0)),
            tool_calls=[ToolCallRecord(**t) for t in d.get("tool_calls", [])],
            termination_reason=d.get("termination_reason", ""),
            input_tokens=d.get("input_tokens"),
            output_tokens=d.get("output_tokens"),
            hitl_decisions_created=int(d.get("hitl_decisions_created", 0)),
            notes=list(d.get("notes", [])),
            event_id=d.get("event_id", ""),
            objective_kind=d.get("objective_kind", "community"),
            objective_household_id=d.get("objective_household_id", ""),
            objective_need_ids=list(d.get("objective_need_ids", [])),
            deferred_need_ids=list(d.get("deferred_need_ids", [])),
            served_need_ids=list(d.get("served_need_ids", [])),
        )

    @property
    def duration_ms(self) -> int | None:
        if not self.ended_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        return int((end - start).total_seconds() * 1000)


#: What one run actually established about one product. Deliberately bounded on every
#: axis — a fixed field set, a capped list of supplier tiers, a capped list of per-need
#: verdicts — because an explanation feature that grows with community size is a storage
#: bill wearing a product's clothes.
MAX_EVALUATION_TIERS = 6
MAX_EVALUATION_NEED_VERDICTS = 8


@dataclass
class RunEvaluation:
    """One deterministic evaluation a run performed, kept so it can be explained later.

    **Why this is a stored row rather than a derived answer.** The facts a member wants
    after pressing the button — how many compatible units existed, what the supplier
    minimum was, which tier won and what lost to it, whether the case filled, why *they*
    were left out — are all computed during the run and were all discarded the moment it
    ended. What survived was a count. Recomputing them afterwards would answer a
    different question: current state, not what the run found, and the two diverge the
    instant anything else changes.

    **What is deliberately not here.** No model reasoning, no scratchpad, no free text
    the model authored — the fields below are the deterministic services' own values
    (AGENTS.md §9). No contact details, no names, no payment references, and no roster
    of who was excluded and why: ``need_verdicts`` carries only the declarations the run
    was *asked* about, so one member's report cannot become a readout of another
    member's policy failures (§4).
    """

    id: str
    run_id: str
    community_id: str
    product_id: str
    product_name: str
    #: Which of the run's objectives this evaluation served. Empty for a community scan.
    need_ids: list[str] = field(default_factory=list)
    viable: bool = False
    #: One of ``coordination.OPPORTUNITY_REASON_CODES``.
    reason_code: str = ""
    reason: str = ""
    pickup_site_id: str = ""
    pickup_site_name: str = ""
    sites_considered: int = 0
    distribution_day: str = ""
    matched_units: int = 0
    minimum_units: int = 0
    current_units: int = 0
    future_units: int = 0
    selected_units: int = 0
    selected_member_count: int = 0
    cases: int = 0
    case_units: int = 0
    surplus_units: int = 0
    auto_join_count: int = 0
    approval_required_count: int = 0
    bulk_offer_id: str = ""
    retail_offer_id: str = ""
    #: The supplier tiers this evaluation compared: ``{offer_id, unit_price_cents,
    #: min_units, case_units, matched_units, outcome}``.
    offers_considered: list[dict[str, Any]] = field(default_factory=list)
    all_in_cents: int = 0
    retail_baseline_cents: int = 0
    net_savings_cents: int = 0
    net_savings_bps: int = 0
    host_compensation_cents: int = 0
    platform_fee_cents: int = 0
    processing_fee_cents: int = 0
    #: Per-declaration outcome, for the declarations this run was asked about only:
    #: ``{need_id, included, units, reason}``.
    need_verdicts: list[dict[str, Any]] = field(default_factory=list)
    #: The pool this evaluation led to, when the run went on to form one.
    pool_id: str = ""
    at: str = field(default_factory=lambda: iso(utcnow()))

    @property
    def key(self) -> str:
        return f"{self.run_id}#{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunEvaluation:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


#: Bounds on what one strategy and one evaluation may store. Same reasoning as
#: :data:`MAX_EVALUATION_TIERS`: evidence that grows with community size is a storage
#: bill wearing a product's clothes, and the counts beside these lists stay exact.
MAX_STRATEGY_NEED_REFS = 40
MAX_STRATEGY_TIERS = 6


@dataclass
class CohortStrategy:
    """One concrete way Pool *could* coordinate a group, before anyone has costed it.

    A strategy names an exact SKU, a pickup site, and the declarations whose own stated
    authority permits that SKU. It is a **candidate**, not a verdict: nothing here knows
    whether the demand clears a supplier minimum after timing and geography, whether it
    lands on whole cases, what the landed price is, or whether it beats buying alone.
    Those are set-level facts and they belong to :class:`StrategyEvaluation`.

    That split is not a device for making a later decision look harder than it is — it
    is where the existing architecture already draws the line. ``discovery.compatible_
    needs`` has always said so in as many words: "Timing, geography, case fitting and
    economics are not decided here — they are what evaluation is for, and pretending to
    know them would be the opposite mistake."

    **Identity is deterministic.** ``id`` is a digest of what the strategy *is* — the
    community, the objective it answers, the target SKU, the site, and whether future
    demand is in scope — so regenerating from the same world produces the same id and a
    stored evaluation keeps pointing at something real. ``input_fingerprint`` is a
    separate digest of the authoritative *state* it was generated from, so a strategy
    whose world has moved is detectable rather than quietly stale.

    **No PII.** Declarations are referenced by need id. Household names, contact details
    and coordinates are not stored here; ``household_count`` is a number, and everything
    else the evaluator needs it reloads for itself (§4).
    """

    id: str
    community_id: str
    #: ``member`` or ``community`` — the same vocabulary ``AgentRun`` already uses.
    objective_kind: str
    #: The household a member-scoped objective is anchored to. Empty for a scan.
    objective_household_id: str = ""
    #: The declaration that anchored it, when there is one. Its inclusion in the final
    #: buyer set is the question a member-triggered run actually asked.
    objective_need_id: str = ""

    target_product_id: str = ""
    target_product_name: str = ""
    #: The curated family and schema the target's attribute facts were read under, so a
    #: re-curation is visible rather than silently reinterpreted.
    product_family: str = ""
    attribute_schema_version: int = 0
    #: Authoritative curated facts for the target SKU, ``attribute -> value``. Verified
    #: values only; an unverified fact is not evidence and is not carried here.
    target_attributes: dict[str, str] = field(default_factory=dict)

    pickup_site_id: str = ""
    pickup_site_name: str = ""
    include_future_demand: bool = True

    #: Declarations whose own authority permits this SKU on this purchase date. Capped;
    #: ``compatible_declaration_count`` stays exact. The evaluator never consumes this —
    #: it reloads state — so a truncated list costs evidence, never correctness.
    candidate_need_ids: list[str] = field(default_factory=list)
    compatible_declaration_count: int = 0
    household_count: int = 0
    compatible_units: int = 0
    current_units: int = 0
    future_units: int = 0

    #: How many declarations this SKU was refused by, and why, as counts per stable code
    #: (``domain.substitution.CompatibilityReason`` and timing reasons). Counts only: who
    #: was refused, and for what, is one member's business and not another's (§4).
    excluded_declaration_count: int = 0
    exclusion_codes: dict[str, int] = field(default_factory=dict)

    #: Sourceability, as presence rather than terms. Prices are deliberately absent:
    #: what a group would actually pay is landed economics, and landed economics is
    #: evaluation's answer.
    bulk_tier_count: int = 0
    #: The lowest supplier minimum any tier will sell at, so "how far off is this" is
    #: answerable without a price. Clearing it is necessary and nowhere near sufficient.
    lowest_minimum_units: int = 0

    input_fingerprint: str = ""
    #: The run that listed this option. Lineage in the direction somebody reads it: a
    #: member opens the order, the order names the run, the run names the options it
    #: considered. Empty when generated outside a run.
    run_id: str = ""
    generated_at: str = field(default_factory=lambda: iso(utcnow()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CohortStrategy:
        known = {f.name for f in fields(cls)}
        out = {k: v for k, v in d.items() if k in known}
        out["exclusion_codes"] = {
            str(k): int(v) for k, v in dict(out.get("exclusion_codes") or {}).items()
        }
        out["target_attributes"] = {
            str(k): str(v) for k, v in dict(out.get("target_attributes") or {}).items()
        }
        return cls(**out)

    @property
    def includes_objective_need(self) -> bool:
        """Whether the declaration that triggered this run is in the envelope at all."""
        return bool(self.objective_need_id) and self.objective_need_id in self.candidate_need_ids


@dataclass
class StrategyEvaluation:
    """Authoritative evidence about one strategy, at one moment, from reloaded state.

    Everything here was computed by the same deterministic services that price a real
    pool — ``coordination.evaluate_opportunity`` and what it calls. There is no separate
    "strategy result" arithmetic, because a second implementation of viability is a
    second answer to the only question that matters.

    ``stale`` is the one field that is about the *evidence* rather than the world. An
    evaluation is a snapshot; a snapshot taken before a supplier requoted or a member
    amended their rule is not authority for acting now, and Phase 3's mutation path has
    to be able to tell the difference.
    """

    id: str
    strategy_id: str
    community_id: str
    target_product_id: str = ""
    target_product_name: str = ""
    objective_need_id: str = ""
    #: The run that costed this option, so an explanation can be scoped to one run
    #: rather than to whatever evidence happens to be in the workspace.
    run_id: str = ""

    #: The fingerprint the strategy carried, and the one its world has now. Equal means
    #: nothing decision-relevant moved between generation and this evaluation.
    strategy_fingerprint: str = ""
    input_fingerprint: str = ""
    stale: bool = False
    stale_reason: str = ""

    viable: bool = False
    #: One of ``services.strategy.STRATEGY_BLOCKER_CODES``. Empty when viable.
    blocker_code: str = ""
    blocker_reason: str = ""

    pickup_site_id: str = ""
    pickup_site_name: str = ""
    distribution_day: str = ""
    radius_km: float = 0.0
    avg_travel_minutes: int = 0
    max_travel_minutes: int = 0
    routing_provider: str = ""

    retail_offer_id: str = ""
    bulk_offer_id: str = ""
    quote_age_hours: float = 0.0
    quote_max_age_hours: int = 0
    #: Every bulk tier compared and what happened to it. Capped at
    #: :data:`MAX_STRATEGY_TIERS`.
    offers_considered: list[dict[str, Any]] = field(default_factory=list)

    matched_units: int = 0
    minimum_units: int = 0
    current_units: int = 0
    future_units: int = 0
    selected_units: int = 0
    selected_member_count: int = 0
    cases: int = 0
    case_units: int = 0
    surplus_units: int = 0

    all_in_cents: int = 0
    retail_baseline_cents: int = 0
    net_savings_cents: int = 0
    net_savings_bps: int = 0
    host_compensation_cents: int = 0
    platform_fee_cents: int = 0
    processing_fee_cents: int = 0

    auto_join_count: int = 0
    approval_required_count: int = 0
    #: Whether the declaration that triggered a member-scoped run survived every gate.
    #: Distinct from "a pool formed": an order that excluded the person who asked for it
    #: is a real outcome and must not be reported as their order (§8).
    includes_objective_need: bool = False

    #: The declarations that survived, and the ones that did not with their stable code.
    #: Both capped at :data:`MAX_STRATEGY_NEED_REFS`; the counts beside them are exact.
    #: The excluded list is internal evidence — projections carry counts, never a roster.
    eligible_need_ids: list[str] = field(default_factory=list)
    eligible_need_count: int = 0
    excluded: list[dict[str, Any]] = field(default_factory=list)
    excluded_count: int = 0
    exclusion_codes: dict[str, int] = field(default_factory=dict)

    at: str = field(default_factory=lambda: iso(utcnow()))

    @property
    def key(self) -> str:
        return f"{self.strategy_id}#{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StrategyEvaluation:
        known = {f.name for f in fields(cls)}
        out = {k: v for k, v in d.items() if k in known}
        out["exclusion_codes"] = {
            str(k): int(v) for k, v in dict(out.get("exclusion_codes") or {}).items()
        }
        out["radius_km"] = float(out.get("radius_km", 0.0) or 0.0)
        out["quote_age_hours"] = float(out.get("quote_age_hours", 0.0) or 0.0)
        return cls(**out)


class CoordinationEventKind(str, Enum):
    """Why coordination work is owed.

    One member today. The type exists rather than a bare string because the dispatcher
    branches on it, and a second kind — a pool-day sweep, a supplier requote — is a row
    here and a branch there rather than a new mechanism.
    """

    #: A member wrote or meaningfully changed a standing declaration.
    NEED_DECLARED = "need_declared"


class CoordinationEventStatus(str, Enum):
    """Where one unit of coordination work has got to.

    Four states, and the distinction between the last two is the one that matters to a
    member: ``completed`` means a run reached a verdict, which may perfectly well have
    been "nothing worth doing". ``failed`` means the run did not get to a verdict at all.
    Collapsing them would let a bug read as a considered refusal.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CoordinationEvent:
    """One durable unit of coordination work, owed because state changed.

    **Why this exists at all.** Declaring a need and coordinating one are different
    transactions with different failure modes. A declaration must persist whether or not
    an agent is available; a run must be attributable to the thing that caused it, must
    happen once per cause, and must survive being asked for twice. An event is the row
    that holds those two apart — the write side records that work is owed, and a
    dispatcher decides when it happens (AGENTS.md §3.2: event-driven, never polled).

    **Identity is the dedupe key.** ``id`` is a digest of the kind, the declaration, and
    that declaration's material content, so re-submitting the same form, reloading the
    page, or saving an edit that changed nothing all resolve to the *same* event — which
    is already there, and is not run again. A change that actually alters what Pool
    would coordinate produces a different digest and therefore a different event. Dedupe
    is a primary-key lookup rather than a scan, in both backends.

    **What it deliberately does not carry.** No prompt, no model text, no reasoning, and
    nothing about the member beyond the two identifiers a run needs to resolve its own
    objective from stored state (§4).
    """

    id: str
    kind: str
    community_id: str
    household_id: str = ""
    need_id: str = ""
    status: str = CoordinationEventStatus.PENDING.value
    #: The run this event caused, once one has been claimed. One event, one run.
    run_id: str = ""
    #: How many times a dispatcher has claimed it. A claim that fails leaves the event
    #: ``failed`` with the count intact, so a retry is a decision somebody makes rather
    #: than something that happens on its own (§3.1).
    attempts: int = 0
    #: The run's own outcome value, copied so the member-facing state does not depend on
    #: joining to a run record that a workspace reset may have swept.
    outcome: str = ""
    #: Why it ended, in the run's own vocabulary: ``completed``, a bound name, or an
    #: error class. Never model prose.
    terminal_reason: str = ""
    #: The candidate pool this event produced, when it produced one.
    pool_id: str = ""
    created_at: str = field(default_factory=lambda: iso(utcnow()))
    claimed_at: str = ""
    ended_at: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            CoordinationEventStatus.COMPLETED.value,
            CoordinationEventStatus.FAILED.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CoordinationEvent:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


#: How many targeted questions one plan may contain. Small on purpose: the point of
#: planning is to ask the *fewest* things that change what Pool can do for somebody, and
#: a plan that asks everything the family permits is a settings form with extra steps.
MAX_CLARIFICATION_QUESTIONS = 3


class ClarificationPlanStatus(str, Enum):
    ACTIVE = "active"
    #: The world it was planned against moved. Kept rather than deleted, because "what
    #: did Pool decide was worth asking, and when" is audit material.
    SUPERSEDED = "superseded"


@dataclass
class ClarificationPlan:
    """Which approved questions Pool decided were worth asking about one product.

    **Not compatibility authority.** A plan records a *decision about attention* — which
    of the finitely many approved questions (``data/product_facts.QUESTIONS``) would
    materially clarify what this member will accept. What an answer then *means* is the
    deterministic mapper's, and what a member currently accepts is their stored
    declaration's. A plan that named a question nobody answered changes nothing.

    That separation is why a model may write this row and may not write a policy. The
    only field it supplies is ``question_ids``, every entry of which must already exist
    in the approved set, belong to this family and schema, and be applicable to this
    product's verified facts — checked on write.

    **Identity is the fingerprint.** ``id`` is a digest of the household, the product and
    the world the plan was made against, so reopening a form for the same product in an
    unchanged world finds the same plan and buys no model call. A change that would make
    a different question worth asking produces a different id, and the old row is
    superseded rather than rewritten.
    """

    id: str
    community_id: str
    household_id: str
    product_id: str
    family: str
    schema_version: int
    question_definition_version: int
    input_fingerprint: str
    #: Ordered. The order is the model's, bounded by
    #: :data:`MAX_CLARIFICATION_QUESTIONS` and validated against the approved set.
    question_ids: list[str] = field(default_factory=list)
    #: Every approved question that was *available* when the plan was made, so a reader
    #: can see what was passed over as well as what was chosen.
    candidate_question_ids: list[str] = field(default_factory=list)
    #: The bounded run that chose them. Empty when no run was needed.
    run_id: str = ""
    status: str = ClarificationPlanStatus.ACTIVE.value
    created_at: str = field(default_factory=lambda: iso(utcnow()))

    @property
    def is_active(self) -> bool:
        return self.status == ClarificationPlanStatus.ACTIVE.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClarificationPlan:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
