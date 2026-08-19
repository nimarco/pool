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
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..adapters.payments import build_payment_provider
from ..adapters.purchase import build_purchase_executor
from ..adapters.repository import Repository, build_repository
from ..adapters.routing import build_routing
from ..adapters.sourcing import SyntheticCatalogProvider
from ..agent.coordinator import PoolCoordinator
from ..agent.tools import TOOL_SURFACE
from ..config import get_settings
from ..data import catalog
from ..data.seed import COMMUNITY_ID, seed
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
from ..services import communication, fulfillment, hosting, onboarding, relevance
from ..services import coordination as coord
from ..services import needs as needs_service
from ..services import payments as payment_service
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
#: this API to twenty-four allowlisted paths with no prompt surface. See
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


class NeedRequest(BaseModel):
    """One standing declaration, as a member states it.

    Every field maps to something ``NeedDeclaration`` already holds and something a
    deterministic engine already reads. There is deliberately nothing here for Smart
    Join mode: that is a standing property of the *account*, not of one need, and
    exposing it from this form would make a preferences product out of the one screen
    that should stay a single honest sentence about what you buy.
    """

    household_id: str = Field(max_length=60)
    product_id: str = Field(max_length=60)
    quantity: int = Field(ge=1, le=100)
    cadence_days: int = Field(ge=1, le=365)
    expected_next_need_date: str = Field(max_length=10)
    flexibility_days: int = Field(default=0, ge=0, le=365)
    routine_lead_days: int = Field(default=7, ge=0, le=365)
    min_savings_pct: int = Field(default=20, ge=0, le=90)
    max_spend_cents: int = Field(ge=1, le=500_000)
    substitution: str = Field(default="exact_only", max_length=40)
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
        return needs_service.NeedInput(
            household_id=self.household_id,
            product_id=self.product_id,
            quantity=self.quantity,
            cadence_days=self.cadence_days,
            expected_next_need_date=due,
            flexibility_days=self.flexibility_days,
            routine_lead_days=self.routine_lead_days,
            min_savings_pct=self.min_savings_pct,
            max_spend_cents=self.max_spend_cents,
            substitution=substitution,
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
    check_workspace(workspace)
    found = catalog.search(q, limit)
    return {
        "query": q.strip(),
        "results": [e.view() for e in found],
        # So the client can render the licence obligation next to what it obliges.
        "attribution": catalog.attribution().to_dict(),
    }


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
                "active": n.active,
            }
            for n in r.list_needs(ws)
        ],
    }


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
    try:
        need = needs_service.declare_need(
            ctx=ctx, community_id=COMMUNITY_ID, data=body.to_input()
        )
    except needs_service.NeedError as exc:
        raise HTTPException(400, str(exc)) from exc
    return needs_service.need_view(ctx, need)


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
    try:
        need = needs_service.amend_need(
            ctx=ctx, community_id=COMMUNITY_ID, need_id=need_id, data=body.to_input()
        )
    except needs_service.NeedError as exc:
        raise HTTPException(400, str(exc)) from exc
    return needs_service.need_view(ctx, need)


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
        # Why each standing declaration has not produced a pool, in checkable facts.
        # Read-only: the same deterministic evaluator the coordinator's own tool uses.
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


@app.post("/api/demo/scenario")
def scenario(workspace: str = Query("demo")) -> dict[str, Any]:
    """Run the full showcase end to end and return the transcript."""
    ws = check_workspace(workspace)
    # The showcase reseeds the workspace and then drives the entire lifecycle through
    # it — several hundred writes. A live agent run, a reset, or a second tab's scenario
    # landing anywhere inside that produces a workspace that is inconsistent without
    # looking broken, so it holds the lease for the whole thing.
    with _public.workspace_mutation(ws, public_demo.WORKSPACE_BUSY):
        _public.spend_action(ws)
        # Reseeding wipes the workspace, and that used to include the account the person
        # at the screen had just set up — they would finish onboarding, replay the
        # lifecycle to see it end to end, and be thrown back to "what should Pool call
        # you?" with their own declaration gone. So the replay only starts from a clean
        # fixture when there is nothing of theirs to lose.
        me = onboarding.consumer_household(ctx_for(ws))
        result = run_showcase(
            repo(),
            ws,
            settings=_settings,
            routing=_routing,
            reseed=not (me and me.is_onboarded),
        )
    return result.to_dict()


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
