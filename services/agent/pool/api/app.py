"""Public HTTP API.

Serverless-friendly: a plain FastAPI app that runs under uvicorn locally and under API
Gateway + Lambda in the cloud via Mangum. The browser never holds AWS credentials, never
holds a payment secret, and never calls an AWS service directly — it only talks to this
API (§84).

Workspaces give each visitor an isolated dataset so two judges cannot corrupt each
other's demo (§92). A workspace is a plain string supplied by the client; server-side it
only ever selects a DynamoDB partition, and demo partitions carry a TTL.

In judge mode that workspace is also what the deployed AgentCore coordinator is bound to,
so the agent on AWS writes the partition this API serves. The rule that makes it safe is
stated once, here: **a workspace is only ever the value this module validated.** Nothing
downstream re-derives it, no tool takes it as an argument, and the model never sees it.
See ``pool/api/public_demo.py`` for the binding and the lease that serialises it.

Privacy (AGENTS.md §4, §82). Three rules hold across every endpoint:

* No response ever contains a member's precise coordinates. Map positions are snapped
  to a ~110 m grid before they leave the process.
* No response ever contains a phone number, an email address, or a payment method
  reference. Members are identified to each other by display name only, and there is a
  test asserting that.
* A pickup credential is returned exactly once, to the buyer who owns it, and only its
  hash is stored.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any, ClassVar

from fastapi import Body, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..adapters.payments import build_payment_provider
from ..adapters.purchase import build_purchase_executor
from ..adapters.repository import Repository, build_repository
from ..adapters.routing import build_routing
from ..adapters.sourcing import SyntheticCatalogProvider
from ..agent.coordinator import PoolCoordinator
from ..agent.tools import STRATEGY_TOOL_SURFACE, TOOL_SURFACE
from ..config import get_settings
from ..data import catalog
from ..data.roast_coffee_fixture import install_roast_coffee
from ..data.seed import COMMUNITY_ID, seed
from ..domain.attributes import AttributeConstraint
from ..domain.models import (
    LEFT_PARTICIPATION_STATES,
    AllocationState,
    AnnouncementKind,
    DecisionState,
    ExceptionKind,
    HostProfile,
    IssueKind,
    ParticipationState,
    PickupPermission,
    PoolStatus,
    Product,
    ProductSource,
    SubstitutionPolicy,
    new_id,
    utcnow,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.state import IllegalTransition
from ..domain.viability import ViabilityStage
from ..services import clarification as clarify_service
from ..services import (
    communication,
    discovery,
    fulfillment,
    hosting,
    onboarding,
    relevance,
    run_report,
    supplier_import,
)
from ..services import coordination as coord
from ..services import events as events_service
from ..services import needs as needs_service
from ..services import payments as payment_service
from ..services import supplier_updates as supplier_updates_svc
from ..services.context import CoordinationError, PoolContext
from ..services.demo import run_showcase
from . import public_demo

logger = logging.getLogger(__name__)

WORKSPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
GRID_DECIMALS = 3  # ~110 m — enough for community context, not enough to find a door

#: How often a request waiting on someone else's seed re-reads the store. Short
#: enough that a first page load does not feel stalled, long enough that waiting
#: costs a handful of reads rather than a spin.
_SEED_POLL_SECONDS = 0.15

# Written onto the existing run record only after the AgentCore bridge has returned that
# exact id and the API has read the record from the shared workspace. The model has no
# tool that can write run metadata, so this is persistent execution-origin evidence, not
# a frontend inference or a model-authored claim.
_AGENTCORE_ORIGIN_PREFIX = "execution_origin=bedrock_agentcore_runtime:"

#: Judge mode. Off by default, so a local run is the full application; on, it reduces
#: this API to a small allowlist of paths with no prompt surface. See
#: ``pool/api/public_demo.py``. Built before the app because it decides two of its
#: constructor arguments.
_public = public_demo.PublicDemoGuard()

app = FastAPI(
    title="Pool API",
    version="0.2.0",
    description=(
        "Autonomous collective-purchasing coordinator. All data is synthetic; payments "
        "are simulated or Stripe TEST mode; the supplier purchase is simulated."
    ),
    # The interactive docs and the OpenAPI schema live *outside* `/api/`, so the
    # public allowlist — which only guards that prefix — never saw them. Left on, they
    # published a machine-readable map of all 42 routes, including the 30-odd that
    # judge mode exists to make unreachable. The routes were still refused; the map was
    # the leak. Found by probing the deployed URL, not by a test (#0024).
    docs_url=None if _public.enabled else "/docs",
    redoc_url=None if _public.enabled else "/redoc",
    openapi_url=None if _public.enabled else "/openapi.json",
)

if not _public.enabled:
    # Development convenience: the web app runs on :5173 and the API on :8000. In
    # public mode the SPA is served from this same origin, so there is no cross-origin
    # request to permit and the header is left off entirely.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

@app.exception_handler(IllegalTransition)
def _illegal_transition(_request: Request, exc: IllegalTransition) -> JSONResponse:
    """A refused lifecycle move is a conflict, not a server fault.

    `assert_transition` raises this, and it is a `ValueError` — so any route that did
    not name it explicitly turned a correct refusal into a 500. That is a public
    surface: opening distribution twice on a finished pool returned one. Handling it
    once, here, means no route can miss it and no future route has to remember.
    """
    return JSONResponse(
        {"detail": f"this pool cannot go from {exc.current.value} to {exc.requested.value}"},
        status_code=409,
    )


_settings = get_settings()
_repo: Repository = build_repository(
    _settings.repository,
    _settings.dynamodb_table,
    _settings.aws_region,
    consistent_reads=_settings.dynamodb_consistent_reads,
)
_routing = build_routing(
    _settings.routing_provider, _settings.aws_region, _settings.max_route_matrix_cells
)
_payments = build_payment_provider(_settings.payment_provider, _settings.stripe_api_key)
_purchaser = build_purchase_executor(_settings.purchase_executor)
_sourcing = SyntheticCatalogProvider()


def repo() -> Repository:
    return _repo


def check_workspace(ws: str) -> str:
    if not WORKSPACE_RE.match(ws):
        raise HTTPException(400, "invalid workspace identifier")
    # Public mode narrows this further to browser-generated session ids, which keeps
    # anonymous visitors out of each other's data and out of ``primary``.
    return _public.check_workspace(ws)


def ctx_for(ws: str) -> PoolContext:
    return PoolContext(
        repo=repo(),
        ws=ws,
        routing=_routing,
        payments=_payments,
        purchaser=_purchaser,
        sourcing=_sourcing,
        now=utcnow(),
    )


def coarse(lat: float, lon: float) -> tuple[float, float]:
    """Snap a coordinate to a grid before it leaves the server."""
    return round(lat, GRID_DECIMALS), round(lon, GRID_DECIMALS)


def ensure_seeded(ws: str) -> None:
    """Populate a cold workspace, exactly once, however many requests arrive at once.

    The browser opens with ``Promise.all([state(), map()])`` and both call this, so the
    first load of a session is *always* a race — and ``seed()`` opens by deleting every
    row in the partition. Two unsynchronised seeds therefore do not merely duplicate
    work: the second one's reset deletes rows the first has already written, and
    whichever request read in between renders a half-built community.

    So the check and the seed happen under the workspace mutation lease, and are
    re-checked once it is held: the request that waited for the lease usually finds the
    world already there and writes nothing. A request that cannot get the lease waits
    for the holder rather than seeding over the top — a bounded wait, because rendering
    an empty community is a better failure than blocking a page load indefinitely.
    """
    if repo().list_communities(ws):
        return
    if not _public.hold_workspace(ws):
        _wait_for_seed(ws)
        return
    try:
        # Re-read under the lease. The common case for the second tab is that the first
        # one seeded while this request was waiting, and re-seeding would destroy it.
        if repo().list_communities(ws):
            return
        # Seeding writes ~100 rows, and any read endpoint triggers it for a workspace
        # it has not seen. Public mode rations how many cold sessions a day can open.
        _public.spend_new_session()
        seed(repo(), ws)
        if public_demo.is_verify_workspace(ws):
            # The heterogeneous coffee community, on top of the canonical seed and only
            # here. It brings its own products, suppliers, offers, households and
            # declarations — but deliberately *not* a coffee declaration for the visitor,
            # and *not* the resulting order. Those are what their own save has to cause,
            # or the walkthrough would be showing them a world that was already finished
            # (AGENTS.md §8).
            install_roast_coffee(repo(), ws)
    finally:
        _public.release_workspace(ws)


def _wait_for_seed(ws: str) -> None:
    """Wait, briefly, for whoever holds the lease to finish seeding this workspace.

    Polls the authoritative store rather than the lease, because the lease may be held
    for something else entirely — a coordinator run on an already-seeded workspace — and
    the only question here is whether there is a community to render.
    """
    deadline = time.monotonic() + _public.settings.seed_wait_seconds
    while time.monotonic() < deadline:
        time.sleep(_SEED_POLL_SECONDS)
        if repo().list_communities(ws):
            return


# --------------------------------------------------------------------------- models


class RunRequest(BaseModel):
    trigger: str = Field(default="manual_demo", max_length=60)
    instruction: str | None = Field(default=None, max_length=600)


class DecisionResponse(BaseModel):
    approve: bool


class HostVolunteerRequest(BaseModel):
    has_vehicle: bool = False
    max_orders: int = Field(default=40, ge=1, le=200)
    max_weight_kg: int = Field(default=60, ge=1, le=500)
    max_supplier_distance_km: float = Field(default=15.0, ge=0.1, le=200.0)
    minimum_compensation_cents: int = Field(default=2000, ge=0, le=100_000)


class HostOfferResponse(BaseModel):
    accept: bool


class AnnouncementRequest(BaseModel):
    kind: str = Field(default="host_custom")
    body: str = Field(default="", max_length=400)


class ExceptionRequest(BaseModel):
    kind: str
    detail: str = Field(default="", max_length=600)


class MessageRequest(BaseModel):
    body: str = Field(max_length=1000)


class RedeemRequest(BaseModel):
    value: str = Field(max_length=200)
    is_code: bool = False


class OverrideRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class IssueRequest(BaseModel):
    kind: str
    detail: str = Field(default="", max_length=600)


class AttributeConstraintRequest(BaseModel):
    """Typed product requirements, as a member states them.

    Bounded on every axis a request can grow along, because this is the one field on a
    declaration whose *shape* is caller-supplied. The values are checked against the
    curated schema in ``services/needs`` — an attribute the family does not define, or a
    value it does not allow, is refused there rather than stored and quietly ignored.

    ``prefers`` is accepted and is deliberately inert: it orders choices the member has
    already authorised and can never create or remove one, which is asserted by
    ``domain.attributes`` and by test rather than promised here.
    """

    family: str = Field(max_length=60)
    schema_version: int = Field(ge=1, le=1_000)
    requires: dict[str, list[str]] = Field(default_factory=dict)
    excludes: dict[str, list[str]] = Field(default_factory=dict)
    prefers: dict[str, list[str]] = Field(default_factory=dict)

    #: Small on purpose. A curated family has a handful of attributes with a handful of
    #: values each; anything larger is not a member expressing a preference.
    MAX_ATTRIBUTES: ClassVar[int] = 12
    MAX_VALUES: ClassVar[int] = 24
    MAX_TOKEN: ClassVar[int] = 60

    def to_constraint(self) -> AttributeConstraint:
        for mapping in (self.requires, self.excludes, self.prefers):
            if len(mapping) > self.MAX_ATTRIBUTES:
                raise HTTPException(400, "too many product requirements")
            for key, values in mapping.items():
                if len(key) > self.MAX_TOKEN or len(values) > self.MAX_VALUES:
                    raise HTTPException(400, "that requirement is not one this demo accepts")
                if any(len(v) > self.MAX_TOKEN for v in values):
                    raise HTTPException(400, "that requirement is not one this demo accepts")
        return AttributeConstraint(
            family=self.family,
            schema_version=self.schema_version,
            requires={k: frozenset(v) for k, v in self.requires.items()},
            excludes={k: frozenset(v) for k, v in self.excludes.items()},
            prefers={k: tuple(v) for k, v in self.prefers.items()},
        )


class PreferenceRequest(BaseModel):
    """A member's answers to the product-specific questions, as the form collects them.

    Deliberately *not* a policy. The browser sends what somebody said about the product
    they picked; ``services/needs.policy_from_answers`` decides what that means, so the
    narrowest-reading rules live in one testable place and a client cannot assemble a
    permission the questions never offered.
    """

    flexibility: str = Field(default=needs_service.Flexibility.EXACT, max_length=20)
    keep: list[str] = Field(default_factory=list)
    accept: dict[str, list[str]] = Field(default_factory=dict)

    #: Small on purpose. A curated family has a handful of dimensions with a handful of
    #: values each; anything larger is not somebody answering a form.
    MAX_ATTRIBUTES: ClassVar[int] = 12
    MAX_VALUES: ClassVar[int] = 24
    MAX_TOKEN: ClassVar[int] = 60

    def to_answers(self) -> needs_service.PreferenceAnswers:
        if self.flexibility not in (
            needs_service.Flexibility.EXACT,
            needs_service.Flexibility.SIMILAR,
        ):
            raise HTTPException(400, "that is not an answer this form offers")
        if len(self.keep) > self.MAX_ATTRIBUTES or len(self.accept) > self.MAX_ATTRIBUTES:
            raise HTTPException(400, "too many product preferences")
        for key, values in self.accept.items():
            if len(key) > self.MAX_TOKEN or len(values) > self.MAX_VALUES:
                raise HTTPException(400, "that preference is not one this demo accepts")
            if any(len(v) > self.MAX_TOKEN for v in values):
                raise HTTPException(400, "that preference is not one this demo accepts")
        return needs_service.PreferenceAnswers(
            flexibility=self.flexibility,
            keep=tuple(self.keep),
            accept={k: tuple(v) for k, v in self.accept.items()},
        )


class NeedRequest(BaseModel):
    """One standing declaration, as a member states it.

    Every field maps to something ``NeedDeclaration`` already holds and something a
    deterministic engine already reads. There is deliberately nothing here for Smart
    Join mode: that is a standing property of the *account*, not of one need, and
    exposing it from this form would make a preferences product out of the one screen
    that should stay a single honest sentence about what you buy.
    """

    household_id: str = Field(max_length=60)
    #: Exactly one of ``product_id`` or ``group`` — a member either names the product or
    #: names the family, and those are different statements.
    product_id: str = Field(default="", max_length=60)
    group: str = Field(default="", max_length=40)
    quantity: int = Field(ge=1, le=100)
    cadence_days: int = Field(ge=1, le=365)
    expected_next_need_date: str = Field(max_length=10)
    flexibility_days: int = Field(default=0, ge=0, le=365)
    routine_lead_days: int = Field(default=7, ge=0, le=365)
    min_savings_pct: int = Field(default=20, ge=0, le=90)
    max_spend_cents: int = Field(ge=1, le=500_000)
    substitution: str = Field(default="exact_only", max_length=40)
    #: Present only on an ``attribute_constrained`` declaration. Absent everywhere else,
    #: and refused rather than ignored when it turns up beside another policy — silently
    #: dropping stated requirements is how a member ends up with authority they did not
    #: intend and no way to see it.
    constraint: AttributeConstraintRequest | None = None
    #: The member-facing form's answers. Mutually exclusive with ``constraint``: one is
    #: a policy and the other is what somebody said, and accepting both would mean two
    #: sources for one permission.
    preferences: PreferenceRequest | None = None
    #: The clarification plan whose questions the form actually put in front of this
    #: member, as returned by ``POST /api/products/{id}/clarification``.
    #:
    #: Lineage, not authority. It cannot widen a rule, name a question, or change what an
    #: answer means — it is recorded on the coordination event so historical proof can
    #: name the plan submitted with this revision instead of searching for one afterwards
    #: and finding whichever is newest. Checked against the declaration: a plan belonging
    #: to another member, another product or another Community is refused rather than
    #: ignored, as is one that did not ask about something these answers explicitly say.
    #: An absent one records no lineage rather than a guessed one.
    clarification_plan_id: str = Field(default="", max_length=60)
    active: bool = True

    def to_input(self) -> needs_service.NeedInput:
        try:
            due = date.fromisoformat(self.expected_next_need_date)
        except ValueError as exc:
            raise HTTPException(400, "that is not a valid date") from exc
        try:
            substitution = SubstitutionPolicy(self.substitution)
        except ValueError as exc:
            raise HTTPException(400, "unknown substitution preference") from exc

        product_id = self.product_id
        if self.group:
            if product_id:
                raise HTTPException(
                    400, "name a product or a product family, not both"
                )
            family = catalog.group(self.group)
            if family is None:
                raise HTTPException(400, "unknown product family")
            # The family decides both fields. Naming the family is the whole of the
            # request, and the exemplar is looked up here rather than accepted, so the
            # authority a group declaration carries can only ever come from a family a
            # human put in the catalogue.
            product_id = family.exemplar_product_id
            substitution = SubstitutionPolicy.GROUP_DECLARED
        elif substitution == SubstitutionPolicy.GROUP_DECLARED:
            # Otherwise a caller could claim family-wide authority while naming one
            # product, which is a wider permission than any screen asked for.
            raise HTTPException(
                400, "declaring a product family means naming the family"
            )
        if not product_id:
            raise HTTPException(400, "name a product or a product family")

        # Constrained declarations name a *product* — the exemplar their lineage
        # resolves to — and carry the rule that decides what else may serve it. Naming a
        # family instead would be two statements of authority on one row, and the wider
        # of them would win: the family gate would already have set `group_declared`.
        if self.group and self.constraint is not None:
            raise HTTPException(
                400, "product requirements go with a product, not with a family"
            )
        if self.preferences is not None:
            if self.constraint is not None:
                raise HTTPException(
                    400, "send the answers or the policy, not both"
                )
            if self.group:
                raise HTTPException(
                    400, "product preferences go with a product, not with a family"
                )

        return needs_service.NeedInput(
            household_id=self.household_id,
            product_id=product_id,
            quantity=self.quantity,
            cadence_days=self.cadence_days,
            expected_next_need_date=due,
            flexibility_days=self.flexibility_days,
            routine_lead_days=self.routine_lead_days,
            min_savings_pct=self.min_savings_pct,
            max_spend_cents=self.max_spend_cents,
            substitution=substitution,
            attribute_policy=(
                self.constraint.to_constraint() if self.constraint is not None else None
            ),
            active=self.active,
        )


class OfferUpsertRequest(BaseModel):
    """Operator-entered supplier offer (§45)."""

    offer_id: str = Field(max_length=60)
    supplier_id: str = Field(max_length=60)
    product_id: str = Field(max_length=60)
    unit_price_cents: int = Field(ge=1, le=1_000_000)
    case_units: int = Field(default=1, ge=1, le=1000)
    moq_amount: int = Field(default=1, ge=1, le=100_000)
    moq_kind: str = Field(default="units")
    supplier_reference: str = Field(default="", max_length=120)
    active: bool = True


# --------------------------------------------------------------------------- health


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "repository": _settings.repository,
        "routing_provider": _settings.routing_provider,
        "model_provider": _settings.model_provider,
        "model_id": (
            _settings.bedrock_model_id if _settings.model_provider == "bedrock" else "offline"
        ),
        "payment_provider": _payments.name,
        # Never "live". The Stripe adapter refuses to construct with a non-test key.
        "payment_mode": _payments.mode,
        "purchase_executor": _purchaser.name,
        "purchase_simulated": _purchaser.simulated,
        "schedules_enabled": _settings.schedules_enabled,
        "bounds": {
            "max_iterations": _settings.bounds.max_iterations,
            "max_tool_calls": _settings.bounds.max_tool_calls,
            "max_duplicate_tool_calls": _settings.bounds.max_duplicate_tool_calls,
            "workflow_timeout_seconds": _settings.bounds.workflow_timeout_seconds,
        },
        # The whole surface the model can reach, alongside the bounds it runs under —
        # both answer "what shape is this agent". Served from the single definition in
        # `agent/tools.py` so the UI cannot show a tool list that has drifted from the
        # one Strands is actually given.
        "agent_tools": [{"name": name, "kind": kind} for name, kind in TOOL_SURFACE],
        # The second surface, published separately because it is offered *instead of*
        # the first and never alongside it (``objective.searches_strategies``). Two lists
        # rather than one, because merging them would say a run holds fifteen tools when
        # no run ever holds more than twelve.
        "agent_strategy_tools": [
            {"name": name, "kind": kind} for name, kind in STRATEGY_TOOL_SURFACE
        ],
    }


# --------------------------------------------------------------------------- views


def _member_name(ws: str, household_id: str) -> str:
    h = repo().get_household(ws, household_id)
    return h.display_name if h else household_id


def _run_view(run) -> dict[str, Any]:
    """The compact, non-reasoning execution record exposed to the browser."""
    return {
        "run_id": run.id,
        "trigger": run.trigger,
        "outcome": run.outcome.value,
        "iterations": run.iterations,
        "tool_calls": [t.name for t in run.tool_calls],
        "termination_reason": run.termination_reason,
        "model_provider": run.model_provider,
        "model_id": run.model_id,
        "duration_ms": run.duration_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "started_at": run.started_at,
    }


def _execution_proof(ws: str, pool) -> dict[str, Any] | None:
    """Prove a pool/run relationship by reading both records from one workspace.

    The browser must not guess that the latest run created the first pool. The domain
    write stores ``created_by_run`` on the pool; this projection follows that exact id
    back to the authoritative run record in the same repository partition. A missing
    or dangling id is rendered as no proof, never as a weaker causal claim.
    """
    if not pool.created_by_run:
        return None
    run = repo().get_run(ws, pool.created_by_run)
    if run is None or run.id != pool.created_by_run:
        return None
    origin = next(
        (note for note in run.notes if note.startswith(_AGENTCORE_ORIGIN_PREFIX)), None
    )
    agentcore_live = origin is not None
    origin_region = origin.removeprefix(_AGENTCORE_ORIGIN_PREFIX) if origin else "local"
    return {
        "pool_id": pool.id,
        "created_by_run": pool.created_by_run,
        "run_id": run.id,
        "relation_verified": True,
        "execution": {
            "service": (
                "Amazon Bedrock AgentCore Runtime"
                if agentcore_live
                else "In-process Strands coordinator"
            ),
            "live": agentcore_live,
            "region": origin_region,
        },
        "workspace_readback": {
            "run_recorded": True,
            "pool_recorded": True,
            "same_workspace": True,
        },
        "run": _run_view(run),
    }


def _pool_view(ws: str, pool, *, detail: bool = False) -> dict[str, Any]:
    r = repo()
    ctx = ctx_for(ws)
    product = r.get_product(ws, pool.product_id)
    site = r.get_site(ws, pool.pickup_site_id)
    offer = r.get_offer(ws, pool.offer_id)
    supplier = r.get_supplier(ws, offer.supplier_id) if offer else None
    assignment = r.get_host_assignment(ws, pool.id)
    members = r.list_memberships(ws, pool.id)
    live = [m for m in members if m.state not in LEFT_PARTICIPATION_STATES]
    econ = pool.final_economics or {}

    view: dict[str, Any] = {
        "pool_id": pool.id,
        "created_by_run": pool.created_by_run,
        "execution_proof": _execution_proof(ws, pool),
        "community_id": pool.community_id,
        "product_id": pool.product_id,
        "product_name": product.name if product else pool.product_id,
        "unit": product.unit if product else "unit",
        "brand": product.brand if product else "",
        "variant": product.variant if product else "",
        # So the pool card can show the same photograph the member chose from.
        "image_ref": product.image_ref if product else "",
        "supplier": supplier.name if supplier else "",
        # Where this pool's *price* came from, which is a different question from where
        # the product's identity came from. Real brands appear beside these figures now,
        # so the interface has to be able to say that the quote behind them is invented
        # (§41, §42). `Product.source` answers the identity half separately.
        "offer_source": offer.source.value if offer else "",
        "status": pool.status.value,
        "pickup_site": site.name if site else "",
        "pickup_is_public": site.is_public if site else True,
        "pickup_permission": site.permission.value if site else "",
        "threshold_units": pool.threshold_units,
        "provisional_units": coord.provisional_units(ctx, pool.id),
        "funded_units": coord.funded_units(ctx, pool.id),
        # Two different counts, because they genuinely differ once a payment fails and a
        # replacement joins: `member_count` is every membership still on the record,
        # including one whose card was declined; `buyer_count` is how many people are
        # actually going to receive something. A UI that shows only the first makes a
        # judge reconcile "11 members" against "10 handoffs" on their own.
        "member_count": len(live),
        "buyer_count": sum(
            1
            for m in live
            if m.state
            in {
                ParticipationState.AUTHORIZED,
                ParticipationState.LOCKED,
                ParticipationState.FINAL_OFFERED,
                ParticipationState.PROVISIONAL,
                ParticipationState.ELIGIBLE,
            }
        ),
        "progress_pct": (
            min(100, round(coord.provisional_units(ctx, pool.id) * 100 / pool.threshold_units))
            if pool.threshold_units
            else 0
        ),
        "has_final_offer": pool.has_final_offer,
        "quote_verified_at": pool.quote_verified_at,
        "failure_reason": pool.failure_reason,
        "timing": pool.timing.to_dict(),
        "host": (
            {
                "household_id": assignment.household_id,
                "display_name": _member_name(ws, assignment.household_id),
                "reward_display": format_cents(assignment.reward_total_cents),
                "handled_orders": assignment.handled_orders,
                "supplier_distance_km": round(assignment.supplier_distance_km, 1),
            }
            if assignment
            else None
        ),
        "economics": econ or None,
        "savings_display": format_cents(econ["net_savings_cents"]) if econ else "",
        "savings_pct": bps_to_pct_str(econ["net_savings_bps"]) if econ else "",
        "is_estimate": not pool.has_final_offer,
    }

    if detail:
        view["members"] = [
            {
                # Privacy-safe identity: a display name, never contact details (§82).
                "household_id": m.household_id,
                "display_name": _member_name(ws, m.household_id),
                "units": m.allocated_units,
                "state": m.state.value,
                "path": m.path.value,
                "estimated_cost_display": format_cents(m.estimated_cost_cents),
                "final_cost_display": (
                    format_cents(m.final_cost_cents) if m.final_cost_cents else ""
                ),
                "baseline_display": format_cents(m.baseline_cents),
                "savings_pct": bps_to_pct_str(m.final_savings_bps) if m.final_cost_cents else "",
                "travel_minutes": m.travel_minutes,
                "is_host": bool(assignment and assignment.household_id == m.household_id),
            }
            for m in members
        ]
        view["host_candidates"] = [
            {
                "household_id": c.household_id,
                "display_name": _member_name(ws, c.household_id),
                "source": c.source.value,
                "state": c.state.value,
                "eligible": c.eligible,
                "ineligible_reasons": c.ineligible_reasons,
                "score": c.score,
                "score_components": c.score_components,
                "estimated_reward_display": format_cents(c.estimated_reward_cents),
                "supplier_distance_km": round(c.supplier_distance_km, 1),
            }
            for c in r.list_host_candidates(ws, pool.id)
        ]
        view["announcements"] = [
            {
                "id": a.id,
                "kind": a.kind.value,
                "body": a.body,
                "author": _member_name(ws, a.author_household_id) if a.author_household_id
                else "Pool",
                "created_at": a.created_at,
            }
            for a in r.list_announcements(ws, pool.id)
        ]
        try:
            stage = (
                ViabilityStage.FINAL_LOCK
                if pool.status in {PoolStatus.FUNDING, PoolStatus.RECOVERING}
                else ViabilityStage.PRE_FUNDING
            )
            view["viability"] = coord.check_viability(
                ctx=ctx, pool_id=pool.id, stage=stage
            ).to_dict()
        except CoordinationError as exc:  # a pool referencing missing data still renders
            view["viability"] = {"viable": False, "blocking_reason": str(exc), "checks": []}
    return view


@app.get("/api/state")
def get_state(workspace: str = Query("demo")) -> dict[str, Any]:
    """Everything the dashboard needs in one round trip."""
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    ctx = ctx_for(ws)
    community = r.get_community(ws, COMMUNITY_ID) or (r.list_communities(ws) or [None])[0]
    community_memberships = (
        r.list_community_memberships(ws, community.id) if community else []
    )
    active_needs = [n for n in r.list_needs(ws) if n.active]
    community_sites = (
        [s for s in r.list_sites(ws) if s.community_id == community.id] if community else []
    )

    decisions = [
        {
            "decision_id": d.id,
            "household_id": d.household_id,
            "household_name": _member_name(ws, d.household_id),
            "pool_id": d.pool_id,
            "kind": d.kind.value,
            "state": d.state.value,
            "facts": d.facts,
            "created_at": d.created_at,
            "expires_at": d.expires_at,
        }
        for d in r.list_decisions(ws)
        if d.state == DecisionState.PENDING
    ]

    return {
        "workspace": ws,
        "community": (
            {
                "id": community.id,
                "name": community.name,
                "kind": community.kind.value,
                "schedule": community.schedule.to_dict(),
                "platform_fee": community.platform_fee.to_dict(),
                "quote_max_age_hours": community.quote_max_age_hours,
                "synthetic": community.synthetic,
                # These facts are read from the Community's own server-side records.
                # A DEMO permission or verification method stays labelled demo: it is
                # evidence that the product models the boundary, not an endorsement by
                # the fictional institution represented by the fixture.
                "enablement": {
                    "verified_members": sum(
                        1 for membership in community_memberships if membership.is_verified
                    ),
                    "total_memberships": len(community_memberships),
                    "verification_methods": sorted(
                        {membership.verification_method.value for membership in community_memberships}
                    ),
                    "independent_need_declarers": len(
                        {need.household_id for need in active_needs}
                    ),
                    "designated_pickup_sites": [
                        {
                            "id": site.id,
                            "name": site.name,
                            "is_public": site.is_public,
                            "permission": site.permission.value,
                        }
                        for site in community_sites
                    ],
                },
            }
            if community
            else None
        ),
        "pools": [_pool_view(ws, p) for p in r.list_pools(ws)],
        # Who the client should present as "you", and whether setup is still outstanding.
        # Served here rather than from its own route so a fresh workspace can be routed
        # into onboarding on the first read the app already makes.
        "consumer": onboarding.consumer_view(ctx),
        "decisions": decisions,
        "activity": [e.to_dict() for e in r.list_activity(ws, limit=80)],
        "metrics": coord.impact_metrics(ctx),
        "runs": [_run_view(run) for run in r.list_runs(ws, limit=12)],
        "counts": {
            "members": len(r.list_households(ws)),
            "needs": len(active_needs),
            "products": len(r.list_products(ws)),
            "standing_hosts": len(r.list_host_profiles(ws, COMMUNITY_ID)),
            "open_issues": len(r.list_issues(ws)),
        },
        "is_demo_data": True,
    }


@app.get("/api/pools/{pool_id}")
def get_pool(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    pool = repo().get_pool(ws, pool_id)
    if pool is None:
        raise HTTPException(404, "pool not found")
    return _pool_view(ws, pool, detail=True)


@app.get("/api/map")
def get_map(workspace: str = Query("demo")) -> dict[str, Any]:
    """Community view.

    Member positions are snapped to a coarse grid and carry no address. Pickup sites are
    public places, so those are exact — and each carries its permission status, because
    "we could use this space" is a claim that has to be checked, not assumed (§67).
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()

    pooled: dict[str, str] = {}
    for p in r.list_pools(ws):
        for m in r.list_memberships(ws, p.id):
            if m.state not in LEFT_PARTICIPATION_STATES:
                pooled[m.household_id] = p.id

    need_counts: dict[str, int] = {}
    for n in r.list_needs(ws):
        if n.active:
            need_counts[n.household_id] = need_counts.get(n.household_id, 0) + 1

    members = []
    for h in r.list_households(ws):
        lat, lon = coarse(h.lat, h.lon)
        members.append(
            {
                "id": h.id,
                "lat": lat,
                "lon": lon,
                "zone": h.neighborhood,
                "active_needs": need_counts.get(h.id, 0),
                "in_pool": h.id in pooled,
                "pool_id": pooled.get(h.id),
            }
        )

    return {
        "members": members,
        "sites": [
            {
                "id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon,
                "is_public": s.is_public, "kind": s.kind, "permission": s.permission.value,
            }
            for s in r.list_sites(ws)
            if s.is_public
        ],
        "suppliers": [
            {"id": s.id, "name": s.name, "lat": round(s.lat, GRID_DECIMALS),
             "lon": round(s.lon, GRID_DECIMALS)}
            for s in r.list_suppliers(ws)
        ],
        "position_precision_m": 110,
        # The constraint the matcher actually applies, so the map can draw the question
        # it answers — "could these people reach one pickup point" — rather than
        # scattering dots on a grey rectangle. Read from `coordination`, not restated
        # here, because a map showing a radius the matcher does not use would be worse
        # than a map showing none.
        "walkable_km": coord.WALKABLE_PICKUP_KM,
        "note": "Member positions are approximate by design and contain no address.",
    }


@app.get("/api/products/search")
def search_products(
    q: str = Query("", max_length=80),
    limit: int = Query(catalog.DEFAULT_LIMIT, ge=1, le=catalog.MAX_LIMIT),
    workspace: str = Query("demo"),
) -> dict[str, Any]:
    """Resolve what a member typed into products they might mean.

    The layer that was missing. Everything downstream of a ``product_id`` was already
    deterministic; there was simply no way to *reach* one except a dropdown of six
    invented brands.

    Read-only, free, and offline: it ranks a bundled snapshot with a pure function. No
    model is called — not here and nowhere else on this path — because a language model
    on the keystroke path would cost money per character, make the ranking
    irreproducible, and put an LLM one step away from deciding which product somebody
    is buying (AGENTS.md §3.3, §5). Interpretation is allowed to be forgiving; the
    member still confirms, and compatibility is decided later by
    ``domain.substitution`` from structure alone.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    # What Pool can actually buy right now, read from this workspace's own offers. It is
    # a deployment fact, not a product fact, so it is computed here rather than baked
    # into the snapshot — and it is the reason a broad query like "coffee" surfaces the
    # coffee Pool holds a quote for instead of burying it under eight it does not.
    sourceable = _sourceable_product_ids(ws)
    found = catalog.search(q, limit, sourceable_ids=sourceable)
    # Families first, because "coffee" is usually a statement about coffee rather than a
    # half-remembered brand. A family is sourceable when Pool holds a bulk quote for
    # anything inside it — which is the honest reading: the member is declaring the
    # family, so what matters is whether the family can be bought, not whether the
    # exemplar row happens to be the one quoted.
    families = catalog.search_groups(q)
    in_group: dict[str, bool] = {}
    if families:
        wanted = {g.group for g in families}
        by_group: dict[str, bool] = {g: False for g in wanted}
        for p in repo().list_products(ws):
            if p.substitute_group in wanted and p.id in sourceable:
                by_group[p.substitute_group] = True
        in_group = by_group
    results = [e.view(sourceable=e.product_id in sourceable) for e in found]
    # Then this Community's own products, for anything the bundled snapshot does not
    # carry. A curated family installed into one workspace is a real thing a real member
    # of that community buys, and a search that could not find it would leave them unable
    # to declare it — which is the one action the whole product is built around.
    #
    # Appended rather than merged into the ranking: the snapshot's ordering is a pure
    # function a test can pin, and these rows have no ranking of their own. Deduped
    # against what the catalogue already returned, and capped by the same limit.
    seen = {r["product_id"] for r in results}
    if len(results) < limit:
        for product in _local_matches(ws, q):
            if product.id in seen:
                continue
            results.append(
                {
                    "product_id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "variant": product.variant,
                    "display_size": product.display_size,
                    "unit": product.unit,
                    "category": product.category,
                    "image_ref": product.image_ref,
                    "sourceable": product.id in sourceable,
                }
            )
            seen.add(product.id)
            if len(results) >= limit:
                break
    return {
        "query": q.strip(),
        "groups": [g.view(sourceable=in_group.get(g.group, False)) for g in families],
        "results": results,
        # So the client can render the licence obligation next to what it obliges.
        "attribution": catalog.attribution().to_dict(),
    }


def _local_matches(ws: str, query: str) -> list[Any]:
    """Products this workspace holds that a query plainly names.

    Deliberately blunt — whole-word substring over brand, name and variant, ordered by
    product id. The catalogue's ranking is a tuned, tested, pure function over a fixed
    snapshot; these rows are whatever a community happens to have, and inventing a second
    scoring system for them would be two rankings that disagree. Anything subtler belongs
    in the snapshot.
    """
    words = [w for w in re.split(r"[^a-z0-9]+", query.casefold()) if len(w) >= 2]
    if not words:
        return []
    out = []
    for product in sorted(repo().list_products(ws), key=lambda p: p.id):
        haystack = " ".join(
            (product.brand, product.name, product.variant, product.category)
        ).casefold()
        if all(word in haystack for word in words):
            out.append(product)
    return out


def _sourceable_product_ids(ws: str) -> frozenset[str]:
    """Products this workspace holds a usable bulk quote for.

    Truthful by construction: it is the same ``offers_for`` the evaluator consults, so a
    product marked sourceable is one an opportunity assessment could genuinely price.
    No offer is fabricated for a catalogue product to make this list longer.
    """
    ctx = ctx_for(ws)
    return frozenset(
        p.id for p in repo().list_products(ws) if coord.offers_for(ctx, p.id)[1]
    )


class OnboardingRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=onboarding.MAX_NAME_LENGTH)
    autonomy_mode: str = Field(max_length=20)


@app.post("/api/onboarding/payment-method")
def onboarding_payment_method(workspace: str = Query("demo")) -> dict[str, Any]:
    """Save a simulated payment method for *this* account, during setup.

    Deliberately separate from ``/api/members/{id}/payment-method`` rather than a public
    alias for it. That route takes an id, and the only reason setup needs it is for the
    caller's own household — so exposing the general form publicly would hand out a
    capability nobody uses. It is not merely untidy: one synthetic household is seeded
    with a card that declines on purpose, and giving it a working one would silently
    remove the payment-failure branch the recovery story is built on.

    Here the household is a server constant. There is no field to point it elsewhere.
    Creates no charge and no hold (§55).
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    ctx = ctx_for(ws)
    me = onboarding.consumer_household(ctx)
    if me is None:
        raise HTTPException(404, "this workspace has no account to set up")
    return payment_service.setup_payment_method(ctx=ctx, household_id=me.id)


@app.post("/api/onboarding")
def complete_onboarding(
    body: OnboardingRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Finish setting up the account of the person at the screen.

    Writes a display name and an autonomy mode onto the one household that is *theirs*.
    The household id is a server constant and is not accepted from the client, so this
    cannot be pointed at a synthetic neighbour, and the name is presentational
    everywhere — matching, economics and the state machine all key off the id, which
    never changes.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    try:
        return onboarding.complete_onboarding(
            ctx=ctx_for(ws),
            display_name=body.display_name,
            autonomy_mode=body.autonomy_mode,
        )
    except onboarding.OnboardingError as exc:
        raise HTTPException(400, str(exc)) from exc


class CustomProductRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)


@app.post("/api/products/custom")
def create_custom_product(
    body: CustomProductRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Record something a member buys that the catalogue does not know about.

    A product Pool cannot source is still a thing somebody buys, and telling them they
    may not want it would be the wrong answer. So the declaration is allowed and the
    *pool* is what waits: the product is stored with **no substitute group**, which
    ``domain.substitution`` treats as compatible with nothing but itself, and no
    ``Offer`` exists for it, so ``evaluate_opportunity`` reports that there is no
    supplier and forms nothing. Demand can be declared before Pool knows how to buy it;
    money cannot move until an operator has curated the product and verified a quote.

    Deliberately not doing more: no model is asked to guess a category or a substitute
    group. Guessing the group is precisely the decision that would let two unrelated
    purchases be combined, and it is the one thing this seam exists to prevent (§21).
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    name = " ".join(body.name.split())
    product = Product(
        id=new_id("prod_custom"),
        name=name,
        category="",
        unit="unit",
        # Empty on purpose. Fails closed under every substitution policy.
        substitute_group="",
        source=ProductSource.MEMBER_SUBMITTED,
        source_ref="member",
    )
    repo().put_product(ws, product)
    return {
        "product_id": product.id,
        "name": product.name,
        "brand": "",
        "variant": "",
        "display_size": "",
        "unit": product.unit,
        "category": "",
        "image_ref": "",
        "sourceable": False,
        "note": "Pool has no supplier for this yet, so it cannot form a group order "
                "for it. Your declaration is stored.",
    }


@app.get("/api/needs")
def get_needs(workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    ctx = ctx_for(ws)
    products = {p.id: p for p in r.list_products(ws)}
    return {
        # The catalogue a member can declare against, alongside their declarations, so
        # the Needs view can offer a picker without a second round trip. Not a shop:
        # these are the things this community's suppliers stock, and choosing one states
        # a need rather than placing an order.
        "products": [
            {"product_id": p.id, "name": p.name, "unit": p.unit, "brand": p.brand}
            for p in sorted(products.values(), key=lambda p: p.name)
        ],
        "limits": {
            "max_quantity": needs_service.MAX_QUANTITY,
            "max_cadence_days": needs_service.MAX_CADENCE_DAYS,
            "max_min_savings_pct": needs_service.MAX_MIN_SAVINGS_PCT,
            "max_spend_cents": needs_service.MAX_SPEND_CENTS,
            "max_horizon_days": needs_service.MAX_HORIZON_DAYS,
        },
        "needs": [
            {
                "need_id": n.id,
                "household_id": n.household_id,
                "household_name": _member_name(ws, n.household_id),
                "product_id": n.product_id,
                "product_name": products[n.product_id].name if n.product_id in products else "",
                "unit": products[n.product_id].unit if n.product_id in products else "",
                # Enough identity for the row to render the same card the search did.
                # A member who declared "Optimum Nutrition — Vanilla Ice Cream" should
                # see that again, not a bare internal name.
                "brand": products[n.product_id].brand if n.product_id in products else "",
                "variant": products[n.product_id].variant if n.product_id in products else "",
                "category": products[n.product_id].category if n.product_id in products else "",
                "image_ref": products[n.product_id].image_ref if n.product_id in products else "",
                "quantity": n.quantity,
                "cadence_days": n.cadence_days,
                "expected_next_need_date": n.expected_next_need_date.isoformat(),
                "earliest_purchase_date": n.earliest.isoformat(),
                "latest_purchase_date": n.latest.isoformat(),
                "flexibility_days": n.flexibility_days,
                "routine_lead_days": n.routine_lead_days,
                "min_savings_pct": n.min_savings_pct,
                # Both forms: the display string for the table, the integer for the
                # edit form. A client that had to parse "$45.00" back into cents
                # would be re-deriving money on the browser, which is the one place
                # this project never computes it.
                "max_spend_display": format_cents(n.max_spend_cents),
                "max_spend_cents": n.max_spend_cents,
                "substitution": n.substitution.value,
                # Server-owned, as stored. A client never re-derives what a member
                # required; it reads it, or it reads that they required nothing.
                "attribute_policy": (
                    n.attribute_policy.to_dict() if n.attribute_policy else None
                ),
                # The same rule as the answers that produced it, so *Edit preferences*
                # opens on what this member said rather than on a fresh set of defaults.
                "preferences": needs_service.current_answers(ctx, n),
                "active": n.active,
                "revision": n.revision,
            }
            for n in r.list_needs(ws)
        ],
    }


def _should_dispatch(ws: str) -> bool:
    """Whether saving a declaration also runs the coordination it owes, in this request.

    Two ways to be true, and neither of them is "always". A deployment may turn it on
    globally; the verification partition has it on because that walkthrough is the one
    place the causal chain — save, event, run, order — is the whole point.

    Everywhere else it is off, and the reason is cost rather than caution: seeding a
    workspace writes dozens of rows and the showcase declares a need of its own, so a
    global switch would turn opening a page into a model call (AGENTS.md §3.3). Note
    that seeding could not dispatch even if it were on — it writes declarations straight
    to the repository, and only the HTTP write path records events at all.
    """
    return _settings.auto_dispatch_declaration_events or public_demo.is_verify_workspace(ws)


def _need_input(ctx: PoolContext, body: NeedRequest) -> needs_service.NeedInput:
    """The declaration a request describes, with its answers already interpreted.

    The mapping happens here rather than on ``NeedRequest`` because it needs the
    workspace: which questions a product can even be asked, and what its own verified
    values are, are facts about stored state. A browser that guessed them would be
    guessing at somebody's consent.
    """
    data = body.to_input()
    if body.preferences is None:
        return data
    data.substitution, data.attribute_policy = needs_service.policy_from_answers(
        ctx, data.product_id, body.preferences.to_answers()
    )
    return data


@app.get("/api/products/{product_id}/preferences")
def product_preferences(product_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """The product-specific questions this item can be asked about.

    Read-only. The dimensions come from the curated family schema and the wording from
    the curated table beside it (``data/product_facts.py``) — nothing here is generated,
    and no model is involved in deciding what a member may be asked or what their answer
    would mean. A product outside a curated family returns no questions, and the form
    then offers only "this exact product", which is what Pool can actually honour for it.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    return needs_service.preference_questions(ctx_for(ws), product_id)


@app.post("/api/products/{product_id}/clarification")
def product_clarification(product_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """The questions Pool decided are worth asking about this product, and what each
    side of the flexibility choice would reach.

    **Get-or-create, and the "get" is the common case.** A plan is identified by a digest
    of the household, the product and the shape of the world around it, so reopening this
    form — on an edit, on a Back, on a second look — finds the existing plan and spends
    nothing. A run happens only when there is no valid plan, which means the member picked
    a different product or the world moved enough to change which question matters
    (AGENTS.md §3.3).

    A ``POST`` rather than a ``GET`` because it can, on that first call, cost a bounded
    model call — and a read that sometimes spends money is a read nobody can budget for.
    The client calls it when somebody *chooses* to allow alternatives, never on render and
    never on a reload.

    Planning is gated by the same rule as coordination dispatch: on in the verification
    partition, off everywhere else. A workspace that will not run the planner still gets
    every approved question, in the schema's own order — the form works, it is simply not
    targeted.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    ctx = ctx_for(ws)

    consumer = onboarding.consumer_household(ctx)
    household_id = consumer.id if consumer else ""
    plan, offered = clarify_service.existing_plan(
        ctx, COMMUNITY_ID, household_id, product_id
    )

    ran = False
    if plan is None and offered and household_id and _should_dispatch(ws):
        _public.spend_action(ws)
        coordinator = PoolCoordinator(
            repo(), settings=_settings, routing=_routing, payments=_payments,
            purchaser=_purchaser, sourcing=_sourcing,
        )
        with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
            coordinator.run(
                ws,
                trigger="clarify_need_preferences",
                community_id=COMMUNITY_ID,
                clarify=(household_id, product_id),
            )
        ran = True
        plan, offered = clarify_service.existing_plan(
            ctx, COMMUNITY_ID, household_id, product_id
        )

    rendered = needs_service.preference_questions(ctx, product_id)
    by_attribute = {q["attribute"]: q for q in rendered["questions"]}

    # The consequence of each answer, attached to the question it is about. Counted from
    # stored rows by `services/clarification`, never computed in a browser and never a
    # prediction — it says what current demand each answer could combine with, and the
    # deterministic evaluator is still the only thing that decides whether an order
    # forms. Attached *here* rather than in `preference_questions`, because that read
    # serves the form before anybody has agreed to alternatives, and demand figures have
    # no business on a screen where the answer is still "only this exact one".
    for candidate in offered:
        question = by_attribute.get(candidate.attribute)
        if question is None:
            continue
        question["reach"] = {
            "keep": candidate.answers[clarify_service.ANSWER_KEEP],
            "any": candidate.answers[clarify_service.ANSWER_ANY],
            "options": candidate.options,
            "varies": candidate.varies_among_sourceable,
        }

    by_id = {
        c.question_id: by_attribute.get(c.attribute)
        for c in offered
        if by_attribute.get(c.attribute)
    }
    if plan is not None:
        # The model's order, and only the questions it chose. A question it passed over
        # is not hidden from the record — the plan stores what was offered — it is simply
        # not put in front of the member.
        questions = [by_id[q] for q in plan.question_ids if q in by_id]
    else:
        questions = rendered["questions"]

    return {
        "product_id": product_id,
        "family": rendered["family"],
        "family_noun": rendered["family_noun"],
        "schema_version": rendered["schema_version"],
        "questions": questions,
        "plan_id": plan.id if plan is not None else "",
        "planned": plan is not None,
        "planned_now": ran,
        "questions_offered": [c.question_id for c in offered],
        # Aggregate, deterministic, and about the world rather than about anybody: what
        # each side of the exact-versus-alternatives choice could currently combine with.
        # No prediction and no percentage — Pool has no model of whether an order forms,
        # and the evaluator only answers that after a buyer set has been costed.
        "flexibility": clarify_service.flexibility_context(
            ctx, COMMUNITY_ID, household_id, product_id
        ),
    }


def _declaring_household(ctx: PoolContext, claimed: str) -> str:
    """Whose declaration this request is allowed to write.

    On the **public** surface the answer is the server's and never the client's. Judge
    mode has no authentication (``docs/PILOT_READINESS.md``) and every workspace is
    seeded with synthetic neighbours whose ids are visible on the community screen, so a
    ``household_id`` in a request body was an anonymous visitor's choice of *whose*
    standing rules to write — and amending a seeded member's declaration moves the demand
    every other number in that session is computed from. The consumer household is a
    server constant (``services/onboarding``), exactly as it already is for
    ``/api/onboarding/payment-method``, so there is no longer a field to point anywhere
    else.

    Overridden rather than rejected, for the same reason that endpoint takes no id: a
    refusal would have to say whether the named household exists, and the honest reading
    of "a member declaring what they buy" is that they are declaring it for themselves.
    An *update* naming somebody else's declaration still fails, because ``amend_need``
    compares the stored owner against this resolved identity and refuses the mismatch.

    Off the public surface this is the identity the caller named. The local API is the
    four-surface development and operator application (``api/public_demo``), and its
    regression harnesses legitimately declare on behalf of synthetic participants.
    """
    if not _public.enabled:
        return claimed
    consumer = onboarding.consumer_household(ctx)
    if consumer is None:
        raise HTTPException(409, "this session has no member account yet")
    return consumer.id


def _lineage_for(ctx: PoolContext, body: NeedRequest, data: needs_service.NeedInput) -> str:
    """The clarification plan this save may record, checked before anything is written.

    Validated here rather than at the point of writing the event so a bad reference costs
    a ``400`` and leaves no declaration behind: the declaration is stored first, and a
    refusal after it would be a member's input accepted and their proof rejected.

    **This is also the only layer that can check answer-consistency**, which is why the
    check lives here rather than in ``record_declaration_event``. That function receives a
    stored ``NeedDeclaration``, and a declaration cannot say which of its requirements
    were *answered*: ``policy_from_answers`` reads an unanswered question as unchanged, so
    every applicable attribute appears in ``requires`` either way. Only the raw answers
    distinguish "kept because they said so" from "kept because nobody asked", and they
    exist here and nowhere downstream.

    Only an ``attribute_constrained`` declaration can carry a reference. Exact-only and
    family declarations answered no questions, so their lineage is empty — which is a fact
    about them, not a missing record. A request carrying a typed ``constraint`` instead of
    answers passes ``None``: there is nothing to be consistent with, and inventing a
    constraint for the privileged path would be a check applied where its premise does not
    hold.
    """
    if data.substitution != SubstitutionPolicy.ATTRIBUTE_CONSTRAINED:
        return ""
    answered: set[str] | None = None
    if body.preferences is not None:
        # What the member explicitly said: the attributes they were asked to keep, and
        # those they chose values for. The form emits these only for questions it
        # displayed, which is what makes the check free of false refusals.
        answers = body.preferences.to_answers()
        answered = set(answers.keep) | set(answers.accept)
    try:
        return clarify_service.lineage_reference(
            ctx,
            community_id=COMMUNITY_ID,
            household_id=data.household_id,
            product_id=data.product_id,
            plan_id=body.clarification_plan_id,
            answered_attributes=answered,
        )
    except clarify_service.ClarificationError as exc:
        raise HTTPException(400, str(exc)) from exc


def _coordination_for(
    ctx: PoolContext, ws: str, need, clarification_plan_id: str = ""
) -> dict[str, Any] | None:
    """Record that this declaration owes coordination, and dispatch it if configured.

    Two writes, in this order and never the other: the declaration is already stored by
    the time this runs, so a crash here leaves a member's input intact and coordination
    merely not yet owed. The reverse ordering would leave an event pointing at a
    declaration that does not exist, which is the failure worth designing against
    (``services/events.py``).

    Dispatch is off by default. A declaration always produces a durable event; whether a
    model call happens in the same request is a deployment decision, and making it the
    default would turn seeding a workspace into a bill (AGENTS.md §3.3).
    """
    event = events_service.record_declaration_event(
        ctx, need, COMMUNITY_ID, clarification_plan_id=clarification_plan_id
    )
    if event is None:
        return None
    if not _should_dispatch(ws):
        return events_service.view(event)

    coordinator = PoolCoordinator(
        repo(), settings=_settings, routing=_routing, payments=_payments,
        purchaser=_purchaser, sourcing=_sourcing,
    )
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        dispatched = events_service.dispatch(
            ctx,
            event,
            run=lambda e: coordinator.run(
                ws, trigger="need_declared", community_id=COMMUNITY_ID, event_id=e.id
            ),
        )
    return events_service.view(dispatched.event)


@app.post("/api/needs")
def create_need(body: NeedRequest, workspace: str = Query("demo")) -> dict[str, Any]:
    """Declare a standing need. **The primary user action of the product.**

    Nothing about this creates or joins a group: it records what one household routinely
    buys and the terms they will accept, which is the whole of what a member is ever
    asked to do (AGENTS.md §1, canonical invariant 1). Whether that demand ever becomes
    a pool is the agent's problem, discovered from the overlap between declarations
    nobody coordinated.

    No lease. A declaration is a single row keyed by its own id — the same class of
    participant action as answering a decision or offering to host — and none of those
    take the workspace lease. Refusing a member's own primary action for the 45 seconds
    an agent run takes would be a worse product than the race it would prevent, and
    there is no race: the coordinators that scan-then-write are the ones that need
    serialising.
    """
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    ensure_seeded(ws)
    ctx = ctx_for(ws)
    data = _need_input(ctx, body)
    data.household_id = _declaring_household(ctx, data.household_id)
    plan_id = _lineage_for(ctx, body, data)
    try:
        need = needs_service.declare_need(ctx=ctx, community_id=COMMUNITY_ID, data=data)
    except needs_service.NeedError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        **needs_service.need_view(ctx, need),
        "coordination": _coordination_for(ctx, ws, need, plan_id),
    }


@app.post("/api/needs/{need_id}")
def update_need(
    need_id: str, body: NeedRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Change or retire one standing need.

    The service refuses when ``household_id`` does not match the stored declaration, so
    a member cannot rewrite somebody else's rules by sending their own id.
    """
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    ensure_seeded(ws)
    ctx = ctx_for(ws)
    data = _need_input(ctx, body)
    data.household_id = _declaring_household(ctx, data.household_id)
    plan_id = _lineage_for(ctx, body, data)
    try:
        need = needs_service.amend_need(
            ctx=ctx, community_id=COMMUNITY_ID, need_id=need_id, data=data
        )
    except needs_service.NeedError as exc:
        raise HTTPException(400, str(exc)) from exc
    # Before the new run looks at anything. A member whose amended rules no longer permit
    # an order they were provisionally in is detached from it first, so what coordination
    # sees — and what their own screen shows a moment later — is the world their current
    # preferences describe rather than the one the old ones did (§21).
    reconciled = coord.reconcile_after_declaration_change(ctx=ctx, need=need)
    return {
        **needs_service.need_view(ctx, need),
        "coordination": _coordination_for(ctx, ws, need, plan_id),
        "reconciled": reconciled,
    }


@app.get("/api/members/{household_id}")
def get_member(household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """One member's own view. Contact details and payment references never leave here.

    Also the one endpoint that answers "what of this is *mine*". A consumer surface must
    not decide that for itself: Home used to lead with the first pool in the workspace,
    which is how somebody who had declared coffee was shown a whey protein order formed
    out of ten other students' declarations. ``opportunity`` is the server's answer,
    computed by ``services.relevance`` from membership and need lineage, and ``null``
    when this member is genuinely in nothing — which is a first-class answer, not a gap
    to fill with somebody else's pool.
    """
    ws = check_workspace(workspace)
    r = repo()
    h = r.get_household(ws, household_id)
    if h is None:
        raise HTTPException(404, "member not found")
    # Read-only for its whole length, so the repository reads are memoised: the outlook
    # evaluates every sourceable product against every pickup site, and without this one
    # member view costs four times what `/api/state` does.
    ctx = relevance.read_only(ctx_for(ws))
    membership = r.get_community_membership(ws, COMMUNITY_ID, household_id)
    profile = r.get_host_profile(ws, COMMUNITY_ID, household_id)
    personal = relevance.personal_pools(ctx, COMMUNITY_ID, household_id)
    in_pool = {p.need.id: p.pool.id for p in personal}
    mine = [n for n in r.list_needs(ws) if n.household_id == household_id and n.active]
    return {
        "id": h.id,
        "display_name": h.display_name,
        "zone": h.neighborhood,
        # The pool this member is actually in, if any, with the declaration that put
        # them there. Everything else about relevance is derived from this.
        "opportunity": personal[0].to_dict() if personal else None,
        "other_pool_ids": [p.pool.id for p in personal[1:]],
        # What already exists around each declaration, before anything is evaluated:
        # how much compatible demand has independently accumulated, and the smallest
        # quantity the supplier will sell. Inputs, deliberately without a verdict — the
        # pre-run screen poses the question the run is about to answer (§8).
        "standing_demand": [
            discovery.standing_demand_for(ctx, COMMUNITY_ID, need) for need in mine
        ],
        # Why each standing declaration has not produced a pool, in checkable facts.
        # Read-only: the same deterministic evaluator the coordinator's own tool uses,
        # and labelled everywhere it is shown as a *current outlook* rather than as
        # something a run concluded.
        "needs_outlook": [
            relevance.need_outlook(ctx, COMMUNITY_ID, need, in_pool=in_pool).to_dict()
            for need in mine
        ],
        "community_membership": (
            {
                "community_id": membership.community_id,
                "status": membership.status.value,
                "verification_method": membership.verification_method.value,
                "verified_at": membership.verified_at,
            }
            if membership
            else None
        ),
        # A boolean, not the reference: the browser has no business seeing either the
        # provider token or the card.
        "has_payment_method": bool(h.payment_method_ref),
        "autonomy": h.autonomy.to_dict(),
        "autonomy_display": {
            "mode": h.autonomy.mode.value,
            "min_savings": f"{h.autonomy.min_savings_pct}%",
            "max_spend": format_cents(h.autonomy.max_total_cost_cents),
            "max_travel": f"{h.autonomy.max_travel_minutes} min",
            "substitution": h.autonomy.substitution.value,
            "public_pickup_only": h.autonomy.public_pickup_only,
        },
        "host_profile": profile.to_dict() if profile else None,
    }


@app.get("/api/hosting/opportunities")
def host_opportunities(
    household_id: str = Query(...), workspace: str = Query("demo")
) -> dict[str, Any]:
    """What this member has been offered, and what they are currently fulfilling (§89)."""
    ws = check_workspace(workspace)
    r = repo()
    offers = []
    for c in r.list_host_candidates(ws):
        if c.household_id != household_id or c.state.value != "offered":
            continue
        pool = r.get_pool(ws, c.pool_id)
        product = r.get_product(ws, pool.product_id) if pool else None
        site = r.get_site(ws, pool.pickup_site_id) if pool else None
        offers.append(
            {
                "pool_id": c.pool_id,
                "product_name": product.name if product else "",
                "orders": len(
                    [m for m in r.list_memberships(ws, c.pool_id) if m.counts_as_provisional]
                ),
                "units": coord.provisional_units(ctx_for(ws), c.pool_id),
                "supplier_distance_km": round(c.supplier_distance_km, 1),
                "estimated_earnings_display": format_cents(c.estimated_reward_cents),
                "pickup_site": site.name if site else "",
                "distribution_starts_at": pool.timing.distribution_starts_at if pool else "",
                "distribution_ends_at": pool.timing.distribution_ends_at if pool else "",
                "expires_at": c.expires_at,
            }
        )

    active = []
    for a in r.list_host_assignments(ws):
        if a.household_id != household_id:
            continue
        pool = r.get_pool(ws, a.pool_id)
        if pool is None or pool.status in {PoolStatus.FAILED, PoolStatus.EXPIRED}:
            continue
        active.append(fulfillment.host_checklist(ctx=ctx_for(ws), pool_id=a.pool_id))

    return {"household_id": household_id, "offers": offers, "active_jobs": active}


@app.get("/api/pools/{pool_id}/checklist")
def get_checklist(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        return fulfillment.host_checklist(ctx=ctx_for(ws), pool_id=pool_id)
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/operator")
def operator_console(workspace: str = Query("demo")) -> dict[str, Any]:
    """Lightweight operator view (§90). Functional, not sprawling."""
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    ctx = ctx_for(ws)
    suppliers = {s.id: s.name for s in r.list_suppliers(ws)}
    return {
        "offers": [
            {
                "offer_id": o.id,
                "supplier": suppliers.get(o.supplier_id, o.supplier_id),
                "product_id": o.product_id,
                "kind": o.kind.value,
                "unit_price_display": format_cents(o.unit_price_cents),
                "case_units": o.case_units,
                "moq": f"{o.moq_amount} {o.moq_kind.value}",
                "min_units": o.min_units,
                "verified_at": o.verified_at,
                "age_hours": round(o.age_hours() or 0, 1),
                "source": o.source.value,
                "active": o.active,
                "expired": o.is_expired(),
            }
            for o in r.list_offers(ws)
        ],
        "pools": [
            {
                **_pool_view(ws, p),
                "payments": [
                    {
                        "payment_id": pay.id,
                        "household_name": _member_name(ws, pay.household_id),
                        "amount_display": format_cents(pay.amount_cents),
                        "state": pay.state.value,
                        "provider": pay.provider,
                        "provider_mode": pay.provider_mode,
                        "failure_code": pay.failure_code,
                    }
                    for pay in r.list_payments(ws, p.id)
                ],
                "purchase": (
                    r.get_purchase_for_pool(ws, p.id).to_dict()
                    if r.get_purchase_for_pool(ws, p.id)
                    else None
                ),
            }
            for p in r.list_pools(ws)
        ],
        "issues": [
            {
                **i.to_dict(),
                "household_name": _member_name(ws, i.household_id) if i.household_id else "",
            }
            for i in r.list_issues(ws)
        ],
        "failed_runs": [
            {"run_id": run.id, "outcome": run.outcome.value,
             "termination_reason": run.termination_reason, "notes": run.notes}
            for run in r.list_runs(ws, limit=25)
            if run.outcome.value in {"error", "loop_fault"}
        ],
        "metrics": coord.impact_metrics(ctx),
    }


# --------------------------------------------------------------------------- actions


@app.post("/api/agent/run")
def trigger_run(
    body: RunRequest = Body(default=RunRequest()), workspace: str = Query("demo")
) -> dict[str, Any]:
    """Run the coordinator once.

    This is the *same* code path the EventBridge schedule invokes — there is no separate
    demo path (AGENTS.md §8). One run per request; nothing recurring is started.
    """
    ws = check_workspace(workspace)
    # In public mode the client selects a trigger name and the *server* supplies the
    # prompt: `PoolCoordinator.run()` substitutes `instruction` for the entire run
    # prompt, so forwarding a client string would hand a stranger the agent's
    # instructions. Off, this is the identity function.
    trigger, instruction = _public.resolve_run(body.trigger, body.instruction)
    # This coordinator writes the same partition the deployed one does, and it forms
    # pools by reading "does one exist yet" and then creating one. Two of these, or one
    # of these against a live AgentCore run, is the duplicate-pool race — so a local run
    # takes the same lease the live action does. The lease is taken before the quota for
    # the same reason as in the live path: losing a race should not also cost the loser
    # one of their actions.
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        _public.spend_action(ws)
        ensure_seeded(ws)
        run = PoolCoordinator(
            repo(), settings=_settings, routing=_routing, payments=_payments,
            purchaser=_purchaser, sourcing=_sourcing,
        ).run(ws, trigger=trigger, instruction=instruction, community_id=COMMUNITY_ID)
    return {
        "run_id": run.id,
        "outcome": run.outcome.value,
        "iterations": run.iterations,
        "tool_calls": [
            {"name": t.name, "ok": t.ok, "summary": t.summary} for t in run.tool_calls
        ],
        "termination_reason": run.termination_reason,
        "model_provider": run.model_provider,
        "model_id": run.model_id,
        "duration_ms": run.duration_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "notes": run.notes,
    }


@app.get("/api/events")
def list_coordination_events(workspace: str = Query("demo")) -> dict[str, Any]:
    """Coordination work this workspace owes, is doing, or has finished.

    Read-only, and it starts nothing. This is the server-owned state a surface needs to
    say truthfully what Pool is doing about a declaration — waiting to be looked at,
    being looked at, an order formed, looked at and nothing worth doing, stopped by a
    safety bound, or failed. Six real situations, each read from a stored row rather
    than animated (AGENTS.md §8).
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    events = repo().list_coordination_events(ws)
    return {
        "events": [events_service.view(e) for e in events],
        "pending": sum(1 for e in events if e.status == "pending"),
        "count": len(events),
        # Whether writing a declaration also runs its coordination in the same request.
        # Stated rather than inferred: a pending event means something different when
        # nothing will ever pick it up on its own.
        "auto_dispatch": _settings.auto_dispatch_declaration_events,
    }


@app.get("/api/needs/{need_id}/coordination")
def need_coordination(need_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """Everything one declaration caused, read from stored rows.

    The single source behind both member-facing surfaces: *Why this order?* reads the
    order, the options and the verdicts; *Technical proof for this run* reads the run,
    the tool sequence and the bounds. They cannot disagree, because they are the same
    rows at two levels of detail — which is the property that makes the second one proof
    of the first rather than a parallel story.

    Reload-safe: nothing is reconstructed from what a browser saw. Counts, never a
    roster — which neighbour was excluded is not an answer to anybody else's question.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    explained = events_service.explain(ctx_for(ws), need_id)
    if explained is None:
        # Not an error: a declaration Pool has not looked at yet is an ordinary state,
        # and the surface reading this needs to be able to say so.
        return {"need_id": need_id, "event": None, "run": None, "order": None}
    return explained


@app.post("/api/events/{event_id}/dispatch")
def dispatch_coordination_event(
    event_id: str, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Run the bounded coordinator for one pending coordination event.

    One event, one run. Claiming is a state transition, so a second request for an event
    already running or already finished does nothing and says so — which is the same
    answer a duplicate form submission gets, for the same reason.

    Nothing recurring is started, and no schedule exists: an event is dispatched because
    something asked for it (AGENTS.md §3.2).
    """
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    ensure_seeded(ws)
    ctx = ctx_for(ws)
    event = repo().get_coordination_event(ws, event_id)
    if event is None:
        raise HTTPException(404, "no such coordination event")

    coordinator = PoolCoordinator(
        repo(), settings=_settings, routing=_routing, payments=_payments,
        purchaser=_purchaser, sourcing=_sourcing,
    )
    # The same lease every other run takes: two coordinators writing one partition is
    # the duplicate-pool race, and an event dispatch is a run like any other.
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        dispatched = events_service.dispatch(
            ctx,
            event,
            run=lambda e: coordinator.run(
                ws, trigger="need_declared", community_id=COMMUNITY_ID, event_id=e.id
            ),
        )
    return {
        **events_service.view(dispatched.event),
        "ran": dispatched.ran,
        "skipped_reason": dispatched.reason,
    }


@app.post("/api/decisions/{decision_id}/respond")
def respond(
    decision_id: str, body: DecisionResponse, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    ctx = ctx_for(ws)
    try:
        decision = coord.respond_to_decision(
            ctx=ctx, decision_id=decision_id, approve=body.approve
        )
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc
    pool = repo().get_pool(ws, decision.pool_id)
    return {
        "decision_id": decision.id,
        "state": decision.state.value,
        "pool_status": pool.status.value if pool else None,
        "funded_units": coord.funded_units(ctx, decision.pool_id),
    }


@app.post("/api/pools/{pool_id}/join/{household_id}")
def join_pool(
    pool_id: str, household_id: str, need_id: str = Query(...), workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        m = coord.join_pool_provisionally(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id, need_id=need_id
        )
    except CoordinationError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"pool_id": pool_id, "household_id": household_id, "state": m.state.value}


@app.post("/api/pools/{pool_id}/host-offer/{household_id}")
def volunteer_host(
    pool_id: str,
    household_id: str,
    body: HostVolunteerRequest = Body(default=HostVolunteerRequest()),
    workspace: str = Query("demo"),
) -> dict[str, Any]:
    """"Offer to host this pool" — adds this member to the candidate set (§28).

    It does not claim the job. Pool evaluates every candidate and offers the work to the
    best-ranked eligible one.
    """
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    ctx = ctx_for(ws)
    pool = repo().get_pool(ws, pool_id)
    if pool is None:
        raise HTTPException(404, "pool not found")
    try:
        hosting.volunteer_to_host(
            ctx=ctx,
            pool_id=pool_id,
            household_id=household_id,
            profile=HostProfile(
                household_id=household_id,
                community_id=pool.community_id,
                has_vehicle=body.has_vehicle,
                vehicle_capacity_units=60 if body.has_vehicle else 0,
                max_orders=body.max_orders,
                max_weight_kg=body.max_weight_kg,
                max_supplier_distance_km=body.max_supplier_distance_km,
                minimum_compensation_cents=body.minimum_compensation_cents,
                standing=False,
            ),
        )
        result = hosting.evaluate_host_candidates(ctx=ctx, pool_id=pool_id)
    except CoordinationError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "pool_id": pool_id,
        "household_id": household_id,
        "note": "You are in the candidate set. Pool ranks every candidate and offers "
                "the job to the best fit.",
        "candidates": result.candidates,
    }


@app.post("/api/pools/{pool_id}/host-response/{household_id}")
def respond_host(
    pool_id: str, household_id: str, body: HostOfferResponse, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    try:
        return hosting.respond_to_host_offer(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id, accept=body.accept
        )
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/pools/{pool_id}/withdraw/{household_id}")
def withdraw(pool_id: str, household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """Leave a pool. Refused after lock — the money is captured and the order placed."""
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    try:
        return coord.withdraw_participant(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id
        )
    except CoordinationError as exc:
        # A post-lock withdrawal is a rule, not a missing object.
        status = 409 if "locked" in str(exc) else 404
        raise HTTPException(status, str(exc)) from exc


@app.post("/api/members/{household_id}/payment-method")
def setup_payment_method(household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """Save a payment method for future use. Creates no charge and no hold (§55)."""
    ws = check_workspace(workspace)
    try:
        return payment_service.setup_payment_method(ctx=ctx_for(ws), household_id=household_id)
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/pools/{pool_id}/lock")
def lock(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        return coord.lock_pool(ctx=ctx_for(ws), pool_id=pool_id)
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/pools/{pool_id}/purchase")
def purchase(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        return fulfillment.execute_purchase(ctx=ctx_for(ws), pool_id=pool_id)
    except (CoordinationError, fulfillment.FulfillmentError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/pools/{pool_id}/open-distribution")
def open_distribution(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    try:
        return fulfillment.open_distribution(ctx=ctx_for(ws), pool_id=pool_id)
    except (CoordinationError, fulfillment.FulfillmentError) as exc:
        raise HTTPException(400, str(exc)) from exc


# --------------------------------------------------------------------------- pickup


@app.post("/api/pools/{pool_id}/pickup-credential/{household_id}")
def issue_credential(
    pool_id: str, household_id: str, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Issue this buyer's one-time pickup credential.

    The plaintext is returned exactly once, here. Only its hash is stored, and issuing
    again invalidates the previous pair — so a screenshot shared earlier is worthless.
    """
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    try:
        credential = fulfillment.issue_pickup_credential(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id
        )
    except fulfillment.FulfillmentError as exc:
        raise HTTPException(400, str(exc)) from exc
    return credential.to_dict()


@app.post("/api/pools/{pool_id}/redeem")
def redeem(pool_id: str, body: RedeemRequest, workspace: str = Query("demo")) -> dict[str, Any]:
    """The host scans a QR or types a short code. The server decides, not the host."""
    ws = check_workspace(workspace)
    _public.spend_action(ws)
    result = fulfillment.redeem_pickup(
        ctx=ctx_for(ws), pool_id=pool_id, presented=body.value, is_code=body.is_code
    )
    return result.to_dict()


@app.post("/api/pools/{pool_id}/close-pickup")
def close_pickup(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    return fulfillment.close_pickup_window(ctx=ctx_for(ws), pool_id=pool_id)


@app.post("/api/pools/{pool_id}/override/{household_id}")
def override_pickup(
    pool_id: str, household_id: str, body: OverrideRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Operator-only pickup override. Requires a reason and is fully audited (§72)."""
    ws = check_workspace(workspace)
    try:
        return fulfillment.operator_override_pickup(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id, reason=body.reason
        )
    except fulfillment.FulfillmentError as exc:
        raise HTTPException(400, str(exc)) from exc


# --------------------------------------------------------------------- communication


@app.post("/api/pools/{pool_id}/announce/{household_id}")
def announce(
    pool_id: str, household_id: str, body: AnnouncementRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        kind = AnnouncementKind(body.kind)
    except ValueError as exc:
        raise HTTPException(400, f"unknown announcement kind: {body.kind}") from exc
    try:
        a = communication.announce_as_host(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id,
            kind=kind, body=body.body,
        )
    except communication.CommunicationError as exc:
        raise HTTPException(403, str(exc)) from exc
    return a.to_dict()


@app.post("/api/pools/{pool_id}/exception/{household_id}")
def report_exception(
    pool_id: str, household_id: str, body: ExceptionRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """A structured buyer exception. Pool resolves what it can without messaging (§81)."""
    ws = check_workspace(workspace)
    try:
        kind = ExceptionKind(body.kind)
    except ValueError as exc:
        raise HTTPException(400, f"unknown exception kind: {body.kind}") from exc
    try:
        return communication.report_exception(
            ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id,
            kind=kind, detail=body.detail,
        )
    except communication.CommunicationError as exc:
        raise HTTPException(403, str(exc)) from exc


@app.get("/api/threads/{thread_id}")
def get_thread(thread_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    r = repo()
    thread = r.get_thread(ws, thread_id)
    if thread is None:
        raise HTTPException(404, "thread not found")
    return {
        **thread.to_dict(),
        "buyer_name": _member_name(ws, thread.buyer_household_id),
        "host_name": _member_name(ws, thread.host_household_id),
        "messages": [
            {
                "id": m.id,
                "sender_name": _member_name(ws, m.sender_household_id),
                "sender_household_id": m.sender_household_id,
                "body": m.body,
                "at": m.at,
            }
            for m in r.list_messages(ws, thread_id)
        ],
    }


@app.post("/api/threads/{thread_id}/messages/{household_id}")
def post_message(
    thread_id: str, household_id: str, body: MessageRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        m = communication.post_message(
            ctx=ctx_for(ws), thread_id=thread_id, sender_household_id=household_id,
            body=body.body,
        )
    except communication.CommunicationError as exc:
        raise HTTPException(403, str(exc)) from exc
    except CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc
    return m.to_dict()


@app.post("/api/pools/{pool_id}/issues/{household_id}")
def open_issue(
    pool_id: str, household_id: str, body: IssueRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        kind = IssueKind(body.kind)
    except ValueError as exc:
        raise HTTPException(400, f"unknown issue kind: {body.kind}") from exc
    issue = fulfillment.open_issue(
        ctx=ctx_for(ws), pool_id=pool_id, household_id=household_id,
        kind=kind, detail=body.detail,
    )
    return issue.to_dict()


# --------------------------------------------------------------------------- operator


@app.post("/api/operator/offers")
def upsert_offer(body: OfferUpsertRequest, workspace: str = Query("demo")) -> dict[str, Any]:
    """Create or update a manually verified supplier offer (§45).

    An operator-entered offer is stamped ``manual_verified`` with the moment a human
    confirmed it, because quote freshness is load-bearing at final-offer time (§43).
    """
    from ..domain.models import MoqKind, Offer, OfferKind, OfferSource, iso

    ws = check_workspace(workspace)
    r = repo()
    if r.get_product(ws, body.product_id) is None:
        raise HTTPException(400, "unknown product")
    if r.get_supplier(ws, body.supplier_id) is None:
        raise HTTPException(400, "unknown supplier")
    try:
        moq_kind = MoqKind(body.moq_kind)
    except ValueError as exc:
        raise HTTPException(400, f"unknown moq kind: {body.moq_kind}") from exc

    offer = Offer(
        id=body.offer_id,
        supplier_id=body.supplier_id,
        product_id=body.product_id,
        kind=OfferKind.BULK,
        unit_price_cents=body.unit_price_cents,
        case_units=body.case_units,
        moq_kind=moq_kind,
        moq_amount=body.moq_amount,
        verified_at=iso(utcnow()),
        source=OfferSource.MANUAL_VERIFIED,
        supplier_reference=body.supplier_reference,
        active=body.active,
    )
    r.put_offer(ws, offer)
    return offer.to_dict()


@app.post("/api/operator/offers/{offer_id}/disable")
def disable_offer(offer_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    offer = repo().get_offer(ws, offer_id)
    if offer is None:
        raise HTTPException(404, "offer not found")
    offer.active = False
    repo().put_offer(ws, offer)
    return offer.to_dict()


@app.post("/api/operator/issues/{issue_id}/resolve")
def resolve_issue(
    issue_id: str, body: MessageRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    ws = check_workspace(workspace)
    try:
        issue = fulfillment.resolve_issue(
            ctx=ctx_for(ws), issue_id=issue_id, resolution=body.body
        )
    except fulfillment.FulfillmentError as exc:
        raise HTTPException(404, str(exc)) from exc
    return issue.to_dict()


# --------------------------------------------------------------------------- webhooks


@app.post("/api/webhooks/payments")
async def payment_webhook(request: Request, workspace: str = Query("demo")) -> dict[str, Any]:
    """Provider webhook endpoint.

    The signature is verified against the configured secret before anything is read, the
    event id is deduplicated, and a replay is a no-op. A client-submitted "payment
    succeeded" is never trusted (§61).
    """
    ws = check_workspace(workspace)
    secret = _settings.stripe_webhook_secret
    if not secret:
        raise HTTPException(503, "no webhook secret is configured in this environment")
    payload = (await request.body()).decode("utf-8")
    signature = request.headers.get("stripe-signature", "")
    result = payment_service.handle_provider_event(
        ctx=ctx_for(ws), payload=payload, signature_header=signature, webhook_secret=secret
    )
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return result


# --------------------------------------------------------------------------- demo


@app.post("/api/demo/reset")
def reset(workspace: str = Query("demo")) -> dict[str, Any]:
    """Reset a workspace to the seeded starting state. A judge can always start over."""
    ws = check_workspace(workspace)
    # `seed()` opens by deleting every row in the partition, and the deployed agent now
    # writes that same partition from a different compute environment. Landing this
    # between a pool being created and its members being written leaves a workspace that
    # is internally inconsistent without looking broken, so reset waits its turn.
    #
    # The lease covers the quota check and the entire destructive reset/reseed, not just
    # an initial idle check. A check followed by an early release leaves a gap in which
    # another coordinator can start while `seed()` is deleting and rewriting rows.
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        _public.spend_action(ws)
        counts = seed(repo(), ws)
    return {"workspace": ws, "reset": True, "seeded": counts}


class SupplierQuoteRequest(BaseModel):
    """The whole of what a caller may say. A key, from a server-owned allowlist.

    Deliberately has no price, minimum, case size, product or supplier field. There is
    nothing to validate a range on, because there is no number here to validate — the
    terms live in ``services/supplier_updates.py`` and the client selects between two
    fixed quotes it cannot edit.

    ``extra="forbid"`` so a request that *tries* to send economics is refused rather than
    quietly stripped, for the same reason a supplied ``instruction`` is refused rather
    than dropped (``api/public_demo.resolve_run``): a silently ignored field looks like it
    worked, and the first person to notice would be someone testing whether the price can
    be steered.
    """

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(max_length=64)


@app.get("/api/demo/supplier-updates")
def supplier_updates(workspace: str = Query("demo")) -> dict[str, Any]:
    """The operator's view of what could arrive, and what already has.

    Read-only. Carries the standing demand behind the product as well as the quotes,
    because "six households already buy this" is the fact that makes recording a quote a
    meaningful act rather than a button.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    ctx = relevance.read_only(ctx_for(ws))
    product = ctx.repo.get_product(ws, supplier_updates_svc.PRODUCT_ID)
    declared = [
        n
        for n in ctx.repo.list_needs(ws)
        if n.product_id == supplier_updates_svc.PRODUCT_ID and n.active
    ]
    held = supplier_updates_svc.recorded_keys(ctx)
    _, bulk = coord.offers_for(ctx, supplier_updates_svc.PRODUCT_ID)
    return {
        "product_id": supplier_updates_svc.PRODUCT_ID,
        "product_name": product.name if product else supplier_updates_svc.PRODUCT_ID,
        "unit": product.unit if product else "unit",
        # Inputs, not a verdict. Whether an order works is a run's answer, and this
        # screen does not pre-empt it (§8).
        "declared_members": len({n.household_id for n in declared}),
        "declared_units": sum(n.quantity for n in declared),
        "has_bulk_offer": bool(bulk),
        "quotes": [
            {**quote.to_dict(), "recorded": quote.key in held}
            for quote in supplier_updates_svc.QUOTES.values()
        ],
    }


@app.get("/api/demo/supplier-file")
def supplier_file() -> dict[str, Any]:
    """What the committed quote sheet is, before anybody uploads anything.

    So the operator screen can name the file it expects. Carries the digest rather than
    the contents: this is a description of what will be accepted, and serving the bytes
    from here would invite the mistake of thinking the server made them up.

    **Not on the public allowlist**, and the operator console tolerates its absence. The
    browser does not need it — the path is a constant and the digests are committed where
    a judge reads them, in the repository — so exposing it publicly would add a door for
    convenience rather than for capability. Fewer reachable endpoints is the whole posture
    (``api/public_demo.py``), and this is one that can simply not be one.
    """
    entries = supplier_import.manifest()
    return {
        "path": "demo-data/",
        "columns": list(supplier_import.REQUIRED_COLUMNS),
        # In the order the sequence uses them, because which sheet arrives first is the
        # whole point: the split-case programme clears the supplier minimum and is still
        # refused, and a demo that imported the good one first would look like a switch.
        "allowlisted": [
            {"filename": name, **{k: v for k, v in entry.items()}}
            for name in supplier_import.fixture_order()
            if (entry := entries.get(name))
        ],
        # True where any file is accepted, which is only ever a local process.
        "accepts_any_file": not _public.enabled,
        "synthetic": True,
    }


@app.post("/api/demo/supplier-import")
async def import_supplier_quotes(
    file: UploadFile = File(...), workspace: str = Query("demo")
) -> dict[str, Any]:
    """Read a supplier's quote sheet, and write what it says.

    The bytes are read, the CSV parser runs, the schema is checked and malformed rows are
    counted and named — on every deployment, for every upload, before anything about
    permission is consulted. What is gated is only the *write*: on a deployment strangers
    can reach, the digest has to be in ``demo-data/MANIFEST.json``, because a stranger who
    can set a price can poison every figure the site derives from it. Locally, where
    whoever runs the process already owns the database, any file is accepted.

    A refusal still reports what the file contained. "Your file was rejected" and "your
    file was unreadable" are different facts, and the second one is not true.

    Takes the workspace lease, for the same reason recording one quote does: a supplier
    price landing halfway through a coordinator run would leave that run's stored evidence
    describing a world that never existed. Refused against a showcase partition, which is
    a recording rather than a community.
    """
    ws = check_workspace(workspace)
    if public_demo.is_showcase_workspace(ws):
        raise HTTPException(
            400,
            "The showcase replays one recorded lifecycle. Supplier facts are recorded "
            "against a live community — leave showcase mode to change the world.",
        )
    data = await file.read()
    return _ingest_supplier_bytes(ws, data, file.filename or "upload.csv")


def _ingest_supplier_bytes(ws: str, data: bytes, filename: str) -> dict[str, Any]:
    """Read a quote sheet's bytes and write what they say.

    Everything after "the bytes arrived" lives here, so there is exactly one ingestion
    path and no caller can acquire a cheaper one. An upload reaches it with a judge's
    bytes; ``/api/demo/supplier-sample`` reaches it with the committed fixture's bytes.
    Both then run the same parser, the same digest allowlist, the same workspace lease,
    the same action quota and the same offer write, and get the same body back.

    The digest check is inside this function on purpose. A convenience control that
    skipped it would be a second, weaker door onto the one endpoint whose whole design is
    that a stranger cannot set a price.
    """
    try:
        parsed = supplier_import.parse(data, filename=filename)
    except supplier_import.SupplierImportError as exc:
        raise HTTPException(400, str(exc)) from exc

    matched = supplier_import.allowlisted(data)
    if _public.enabled and not matched:
        # Named, not vague. Somebody who edited a price should be told that is what was
        # detected, and somebody who uploaded the wrong file should be told that too.
        return {
            "recorded": False,
            "refused": "not_allowlisted",
            "reason": (
                "This deployment records supplier quotes only from the fixtures committed "
                "in demo-data/, so a price nobody can audit cannot become an offer here. "
                "The file was read and parsed — the records below are what it contained."
            ),
            **parsed.to_dict(),
            "offers": [],
        }

    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        _public.spend_action(ws)
        ensure_seeded(ws)
        ctx = ctx_for(ws)
        usable, unresolvable = supplier_import.resolvable(ctx, parsed.rows)
        offers = supplier_import.record(ctx, usable)
    body = parsed.to_dict()
    # Rows the schema accepted but this community cannot hold are rejections too, and
    # they belong in the same count rather than disappearing between two numbers.
    body["rejections"] = body["rejections"] + [r.to_dict() for r in unresolvable]
    body["valid"] = len(usable)
    body["rejected"] = len(body["rejections"])
    return {
        "recorded": True,
        "allowlisted_as": matched,
        **body,
        "offers": [
            {
                "offer_id": o.id,
                "product_id": o.product_id,
                "unit_price_display": format_cents(o.unit_price_cents),
                "case_units": o.case_units,
                "min_units": o.min_units,
                "supplier_reference": o.supplier_reference,
                "source": o.source.value,
                "verified_at": o.verified_at,
                "synthetic": True,
            }
            for o in offers
        ],
    }


@app.post("/api/demo/supplier-sample")
def import_supplier_sample(
    name: str = Query(...), workspace: str = Query("demo")
) -> dict[str, Any]:
    """Import one of the committed quote sheets, by name, without a file picker.

    For the judge walkthrough. A first-time visitor with four minutes cannot be asked to
    find a repository, download a CSV and come back — but the sequence those two sheets
    demonstrate is the whole argument, so it cannot be faked either.

    So this is a *door*, not a shortcut: it reads the bytes committed at
    ``demo-data/<name>`` and hands them to :func:`_ingest_supplier_bytes`, which is the
    same function an upload reaches. The parser runs on real bytes, the digest is checked
    against ``MANIFEST.json`` exactly as it is for a stranger's upload, and the offer row
    is written by the same code under the same lease and quota. Nothing is precomputed:
    whether either sheet is *worth acting on* is still the evaluator's answer, produced
    when somebody asks for it.

    ``name`` is checked against the manifest's own order rather than joined onto a path,
    so this cannot be pointed at a file the repository did not commit.
    """
    ws = check_workspace(workspace)
    if public_demo.is_showcase_workspace(ws):
        raise HTTPException(
            400,
            "The showcase replays one recorded lifecycle. Supplier facts are recorded "
            "against a live community — leave showcase mode to change the world.",
        )
    allowed = supplier_import.fixture_order()
    if name not in allowed:
        raise HTTPException(
            400,
            f"{name!r} is not one of the committed sheets. "
            f"Expected one of: {', '.join(allowed)}.",
        )
    path = supplier_import.fixture_path(name)
    if not path.is_file():
        raise HTTPException(500, f"the committed sheet {name!r} is missing from the build")
    return _ingest_supplier_bytes(ws, path.read_bytes(), name)


@app.post("/api/demo/supplier-updates")
def record_supplier_update(
    body: SupplierQuoteRequest, workspace: str = Query("demo")
) -> dict[str, Any]:
    """Record one predetermined supplier quote against this workspace.

    An **operator** action: a member cannot conjure a wholesale quote, and this is not on
    a consumer screen. What it changes is one offer row — the deterministic outlook that
    every member surface recomputes then changes with it, and the record of any run that
    already happened does not, because that run happened in a world where this quote did
    not exist.

    Takes the workspace lease. Recording a supplier price is exactly the kind of write
    that must not land halfway through a coordinator run: the run would price part of
    its work against one set of supply facts and part against another, and its stored
    evidence would describe a world that never existed.
    """
    ws = check_workspace(workspace)
    # Never against the showcase partition. The showcase is a fixed recording of one
    # lifecycle, and every figure quoted about it — 24 units, 2 cases, $861.44 — is a
    # claim about *that* world. Writing a rice quote into it changes the product universe
    # the recording is a recording of, and it would do so invisibly: the Operations
    # console was reachable from inside showcase mode, so a presenter could contaminate
    # the canonical copy between two takes and find out from a number that no longer
    # matched.
    if public_demo.is_showcase_workspace(ws):
        raise HTTPException(
            400,
            "The showcase replays one recorded lifecycle. Supplier facts are recorded "
            "against a live community — leave showcase mode to change the world.",
        )
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        _public.spend_action(ws)
        ensure_seeded(ws)
        try:
            offer = supplier_updates_svc.record(ctx_for(ws), body.quote)
        except supplier_updates_svc.SupplierUpdateError as exc:
            raise HTTPException(400, str(exc)) from exc
    return {
        "recorded": True,
        "quote": body.quote,
        "offer_id": offer.id,
        "product_id": offer.product_id,
        "unit_price_display": format_cents(offer.unit_price_cents),
        "case_units": offer.case_units,
        "min_units": offer.min_units,
        "verified_at": offer.verified_at,
        "source": offer.source.value,
        "synthetic": True,
    }


@app.post("/api/demo/scenario")
def scenario(workspace: str = Query("demo")) -> dict[str, Any]:
    """Run the full canonical showcase end to end, in its own workspace.

    **The showcase never touches the visitor's account.** It declares a flagship whey
    need, drives host recruitment, a payment failure, a recovery, a lock, a purchase and
    ten pickups — as its own scripted consumer, in a partition derived from the caller's
    session and reserved for exactly this. A coffee-only visitor who watches the scripted
    lifecycle does not come back to a Needs page saying they also buy whey.

    It used to run in the visitor's own workspace and skip the reseed when they had
    onboarded, which was an attempt to avoid wiping their account and instead wrote the
    canonical declaration *into* it. Labelling the row ``declared_by: scenario`` did not
    make that acceptable product behaviour; separating the state does.

    So the replay always starts from a known clean fixture, which is also what makes the
    copy — "this starts the community over" — literally true.
    """
    visitor = check_workspace(workspace)
    ws = public_demo.showcase_workspace(visitor)
    # The lease is taken on the showcase partition, because that is the one being
    # rewritten. A visitor's own coordinator run is now free to proceed alongside it:
    # they are different partitions, and that is the whole point.
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        # The quota is spent against the *visitor*, though. Session caps exist to bound
        # what one person can start, not what one partition can absorb.
        _public.spend_action(visitor)
        result = run_showcase(repo(), ws, settings=_settings, routing=_routing)
    return {**result.to_dict(), "workspace": ws}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """Full agent trace for one run. Tool names and outcomes only — no reasoning text."""
    ws = check_workspace(workspace)
    run = repo().get_run(ws, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    d = run.to_dict()
    d["duration_ms"] = run.duration_ms
    return d


@app.get("/api/runs/{run_id}/report")
def get_run_report(
    run_id: str, household_id: str = Query(""), workspace: str = Query("demo")
) -> dict[str, Any]:
    """What one run did about one member's own declarations.

    The consumer answer to **Run Pool now**, assembled server-side from the evaluation
    records that run wrote while it was running — so it describes what the coordinator
    actually established rather than what is true now, and it cannot drift into
    describing a product the run never looked at.

    ``is_mine`` is false when the run was not anchored to this member. That is the guard
    against a previous run, or a community-wide scan, becoming the answer on somebody's
    home screen.
    """
    ws = check_workspace(workspace)
    run = repo().get_run(ws, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    # Read-only for its whole length, like the member view, and for the same reason: it
    # re-reads the same few tables once per declaration.
    ctx = relevance.read_only(ctx_for(ws))
    report = run_report.build(ctx, COMMUNITY_ID, run, household_id)
    if household_id:
        report["elsewhere"] = run_report.community_pools_elsewhere(
            ctx, COMMUNITY_ID, household_id
        )
    return report


@app.get("/api/pools/{pool_id}/allocations")
def get_allocations(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    r = repo()
    return {
        "pool_id": pool_id,
        "allocations": [
            {
                "household_id": a.household_id,
                "display_name": _member_name(ws, a.household_id),
                "units": a.units,
                "state": a.state.value,
                "picked_up_at": a.picked_up_at,
                "via": a.picked_up_via,
                "override_reason": a.override_reason,
            }
            for a in r.list_allocations(ws, pool_id)
        ],
        "picked_up": sum(
            1 for a in r.list_allocations(ws, pool_id) if a.state == AllocationState.PICKED_UP
        ),
    }


@app.get("/api/pickup-sites")
def pickup_sites(workspace: str = Query("demo")) -> dict[str, Any]:
    """Pickup locations and their permission status.

    ``DEMO`` means synthetic. Nothing here asserts that a real space has authorised
    commercial pickup — that is a conversation with a building, not a database flag.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    return {
        "sites": [
            {**s.to_dict(), "lat": round(s.lat, GRID_DECIMALS), "lon": round(s.lon, GRID_DECIMALS)}
            for s in repo().list_sites(ws)
        ],
        "permission_legend": {p.value: p.name for p in PickupPermission},
    }


@app.get("/api/demo/config")
def demo_config() -> dict[str, Any]:
    """What this deployment can actually do. The UI labels itself from this.

    Answers in *every* mode, not only in public mode. It used to exist only when
    ``POOL_PUBLIC_DEMO`` was set, so a local run answered 404 and the client swallowed
    it — which worked, but put a red line in the console of anyone who opened dev tools
    on a demo whose whole pitch is that it is honest about what it is. There is nothing
    to hide here: the payload is a capability description, and off is a real answer.
    """
    return _public.config_view()


def observe_live_run(ws: str, run_id: str) -> dict[str, Any]:
    """What the deployed agent left behind, read out of the authoritative store.

    The live endpoint returns this instead of describing the runtime's own response. The
    distinction is the whole point of pointing AgentCore at this table: a run summary is
    the agent's account of what it did, and these facts are what the database
    says is true — read by the same code path, from the same partition, that serves the
    browser its next page.
    """
    r = repo()
    run = r.get_run(ws, run_id) if run_id else None
    if run is not None:
        marker = f"{_AGENTCORE_ORIGIN_PREFIX}{_public.settings.region}"
        if marker not in run.notes:
            run.notes.append(marker)
            r.put_run(ws, run)
    pools = r.list_pools(ws)
    created_pool_ids = [pool.id for pool in pools if pool.created_by_run == run_id]
    return {
        "run_recorded": run is not None,
        "pools": len(pools),
        "created_pool_ids": created_pool_ids,
        "run_pool_links_verified": run is not None and bool(created_pool_ids),
        "pending_decisions": sum(
            1 for d in r.list_decisions(ws) if d.state == DecisionState.PENDING
        ),
    }


# Registered last so the public allowlist sees every route above it, and so the SPA
# catch-all cannot shadow an API path. A no-op unless POOL_PUBLIC_DEMO is set.
public_demo.install(app, _public, observe=observe_live_run)


# Lambda entry point. Imported lazily so local uvicorn does not require mangum.
def lambda_handler(event, context):  # pragma: no cover - exercised in deployment
    from mangum import Mangum

    return Mangum(app, lifespan="off")(event, context)
