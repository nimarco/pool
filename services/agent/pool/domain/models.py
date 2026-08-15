"""Domain entities.

These are plain dataclasses with explicit `to_dict`/`from_dict` so the same shapes
travel to DynamoDB, the HTTP API, and the agent's tool results without a second
schema drifting out of sync.

Locations are stored as approximate coordinates only. Pool never holds a precise
street address for a household (AGENTS.md §4) — the demo dataset is synthetic and
jittered, and the UI is only ever shown neighbourhood-level context.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


# --------------------------------------------------------------------------- enums


class AutonomyMode(str, Enum):
    """How much authority a household has granted Pool."""

    ASK_ME = "ask_me"
    SMART_JOIN = "smart_join"


class PoolStatus(str, Enum):
    """Lifecycle of one buying pool.

    Transitions are enforced deterministically in ``pool.domain.state`` — the model
    never picks a transition directly (AGENTS.md §5).
    """

    CANDIDATE = "candidate"          # formed by the agent, nobody contacted yet
    INVITING = "inviting"            # invitations / decision requests outstanding
    THRESHOLD_MET = "threshold_met"  # committed units clear the supplier minimum
    CONFIRMED = "confirmed"          # locked; order would be placed here
    RECOVERING = "recovering"        # a dropout put it below threshold; agent is repairing
    FAILED = "failed"                # could not reach threshold before the deadline
    EXPIRED = "expired"              # deadline passed while still forming
    COMPLETED = "completed"          # picked up and settled (simulated in the demo)


TERMINAL_POOL_STATUSES = {PoolStatus.FAILED, PoolStatus.EXPIRED, PoolStatus.COMPLETED}


class MembershipState(str, Enum):
    INVITED = "invited"      # decision request outstanding
    COMMITTED = "committed"  # counts toward the threshold
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"  # committed, then dropped out


class AutonomyPath(str, Enum):
    """How a household came to be in a pool — the audit trail for §5 HITL."""

    SMART_JOIN = "smart_join"      # deterministic policy passed; joined without asking
    HUMAN_APPROVED = "human_approved"
    PENDING_APPROVAL = "pending_approval"


class DecisionKind(str, Enum):
    JOIN_POOL = "join_pool"
    ACCEPT_SUBSTITUTE = "accept_substitute"
    HOST_PICKUP = "host_pickup"


class DecisionState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OfferKind(str, Enum):
    RETAIL = "retail"  # the per-household baseline a family would pay alone
    BULK = "bulk"


class RunOutcome(str, Enum):
    POOL_CREATED = "pool_created"
    POOL_RECOVERED = "pool_recovered"
    NO_ACTION = "no_action"
    LOOP_FAULT = "loop_fault"
    ERROR = "error"


# --------------------------------------------------------------------------- entities


@dataclass
class AutonomyPolicy:
    """A household's Smart Join rules.

    Machine-verifiable by construction: every field is a number or a boolean that
    ``pool.domain.policy`` compares deterministically. The model never interprets
    this — it only reads the verdict (AGENTS.md §5).
    """

    mode: AutonomyMode = AutonomyMode.ASK_ME
    min_savings_pct: int = 20
    max_total_cost_cents: int = 5000
    max_travel_minutes: int = 15
    allow_substitutes: bool = False
    public_pickup_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AutonomyPolicy:
        return cls(
            mode=AutonomyMode(d.get("mode", "ask_me")),
            min_savings_pct=int(d.get("min_savings_pct", 20)),
            max_total_cost_cents=int(d.get("max_total_cost_cents", 5000)),
            max_travel_minutes=int(d.get("max_travel_minutes", 15)),
            allow_substitutes=bool(d.get("allow_substitutes", False)),
            public_pickup_only=bool(d.get("public_pickup_only", True)),
        )


@dataclass
class Household:
    id: str
    display_name: str
    neighborhood: str
    lat: float
    lon: float
    is_host_willing: bool = False
    autonomy: AutonomyPolicy = field(default_factory=AutonomyPolicy)
    synthetic: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["autonomy"] = self.autonomy.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Household:
        return cls(
            id=d["id"],
            display_name=d["display_name"],
            neighborhood=d["neighborhood"],
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            is_host_willing=bool(d.get("is_host_willing", False)),
            autonomy=AutonomyPolicy.from_dict(d.get("autonomy", {})),
            synthetic=bool(d.get("synthetic", True)),
        )


@dataclass
class Product:
    id: str
    name: str
    category: str
    unit: str  # "lb", "roll", "count", "oz"
    substitute_group: str  # products sharing a group are interchangeable-ish


@dataclass
class NeedDeclaration:
    """A standing statement of recurring need. The only thing a household must do."""

    id: str
    household_id: str
    product_id: str
    quantity: int
    cadence_days: int
    needed_by: date
    min_savings_pct: int = 20
    max_spend_cents: int = 5000
    accept_substitutes: bool = False
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["needed_by"] = self.needed_by.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NeedDeclaration:
        return cls(
            id=d["id"],
            household_id=d["household_id"],
            product_id=d["product_id"],
            quantity=int(d["quantity"]),
            cadence_days=int(d["cadence_days"]),
            needed_by=date.fromisoformat(d["needed_by"]),
            min_savings_pct=int(d.get("min_savings_pct", 20)),
            max_spend_cents=int(d.get("max_spend_cents", 5000)),
            accept_substitutes=bool(d.get("accept_substitutes", False)),
            active=bool(d.get("active", True)),
        )


@dataclass
class Offer:
    """A supplier price. Synthetic in the demo; a sourcing adapter can replace it."""

    id: str
    supplier: str
    product_id: str
    kind: OfferKind
    unit_price_cents: int      # price per single unit at this tier
    case_units: int = 1        # units per purchasable case
    min_units: int = 1         # supplier minimum to unlock this price
    valid_until: date | None = None

    @property
    def case_price_cents(self) -> int:
        return self.unit_price_cents * self.case_units

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["valid_until"] = self.valid_until.isoformat() if self.valid_until else None
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Offer:
        return cls(
            id=d["id"],
            supplier=d["supplier"],
            product_id=d["product_id"],
            kind=OfferKind(d["kind"]),
            unit_price_cents=int(d["unit_price_cents"]),
            case_units=int(d.get("case_units", 1)),
            min_units=int(d.get("min_units", 1)),
            valid_until=date.fromisoformat(d["valid_until"]) if d.get("valid_until") else None,
        )


@dataclass
class PickupSite:
    id: str
    name: str
    lat: float
    lon: float
    is_public: bool
    kind: str = "library"  # library | community_center | school | residence


@dataclass
class Membership:
    pool_id: str
    household_id: str
    need_id: str
    requested_units: int
    allocated_units: int
    cost_cents: int
    baseline_cents: int
    savings_cents: int
    savings_bps: int
    travel_minutes: int
    state: MembershipState
    path: AutonomyPath

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
            cost_cents=int(d["cost_cents"]),
            baseline_cents=int(d["baseline_cents"]),
            savings_cents=int(d["savings_cents"]),
            savings_bps=int(d["savings_bps"]),
            travel_minutes=int(d["travel_minutes"]),
            state=MembershipState(d["state"]),
            path=AutonomyPath(d["path"]),
        )


@dataclass
class Pool:
    id: str
    product_id: str
    offer_id: str
    pickup_site_id: str
    status: PoolStatus
    threshold_units: int
    deadline: date
    created_by_run: str
    created_at: str = field(default_factory=lambda: iso(utcnow()))
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["deadline"] = self.deadline.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pool:
        return cls(
            id=d["id"],
            product_id=d["product_id"],
            offer_id=d["offer_id"],
            pickup_site_id=d["pickup_site_id"],
            status=PoolStatus(d["status"]),
            threshold_units=int(d["threshold_units"]),
            deadline=date.fromisoformat(d["deadline"]),
            created_by_run=d.get("created_by_run", ""),
            created_at=d.get("created_at", iso(utcnow())),
            idempotency_key=d.get("idempotency_key", ""),
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
    counters, and a termination reason only (AGENTS.md §9, §16 of the brief).
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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        return d

    @property
    def duration_ms(self) -> int | None:
        if not self.ended_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        return int((end - start).total_seconds() * 1000)
