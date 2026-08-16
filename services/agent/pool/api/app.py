"""Public HTTP API.

Serverless-friendly: a plain FastAPI app that runs under uvicorn locally and under API
Gateway + Lambda in the cloud via Mangum. The browser never holds AWS credentials, never
holds a payment secret, and never calls an AWS service directly — it only talks to this
API (§84).

Workspaces give each visitor an isolated dataset so two judges cannot corrupt each
other's demo (§92). A workspace is a plain string supplied by the client; server-side it
only ever selects a DynamoDB partition, and demo partitions carry a TTL.

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
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..adapters.payments import build_payment_provider
from ..adapters.purchase import build_purchase_executor
from ..adapters.repository import Repository, build_repository
from ..adapters.routing import build_routing
from ..adapters.sourcing import SyntheticCatalogProvider
from ..agent.coordinator import PoolCoordinator
from ..config import get_settings
from ..data.seed import COMMUNITY_ID, seed
from ..domain.models import (
    AllocationState,
    AnnouncementKind,
    DecisionState,
    ExceptionKind,
    HostProfile,
    IssueKind,
    ParticipationState,
    PickupPermission,
    PoolStatus,
    utcnow,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.viability import ViabilityStage
from ..services import communication, fulfillment, hosting
from ..services import coordination as coord
from ..services import payments as payment_service
from ..services.context import CoordinationError, PoolContext
from ..services.demo import run_showcase

logger = logging.getLogger(__name__)

WORKSPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
GRID_DECIMALS = 3  # ~110 m — enough for community context, not enough to find a door

app = FastAPI(
    title="Pool API",
    version="0.2.0",
    description=(
        "Autonomous collective-purchasing coordinator. All data is synthetic; payments "
        "are simulated or Stripe TEST mode; the supplier purchase is simulated."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public read-only demo over synthetic data
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_settings = get_settings()
_repo: Repository = build_repository(
    _settings.repository, _settings.dynamodb_table, _settings.aws_region
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
    return ws


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
    if not repo().list_communities(ws):
        seed(repo(), ws)


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
    }


# --------------------------------------------------------------------------- views


def _member_name(ws: str, household_id: str) -> str:
    h = repo().get_household(ws, household_id)
    return h.display_name if h else household_id


def _pool_view(ws: str, pool, *, detail: bool = False) -> dict[str, Any]:
    r = repo()
    ctx = ctx_for(ws)
    product = r.get_product(ws, pool.product_id)
    site = r.get_site(ws, pool.pickup_site_id)
    offer = r.get_offer(ws, pool.offer_id)
    supplier = r.get_supplier(ws, offer.supplier_id) if offer else None
    assignment = r.get_host_assignment(ws, pool.id)
    members = r.list_memberships(ws, pool.id)
    live = [m for m in members if m.state not in {
        ParticipationState.WITHDRAWN, ParticipationState.DECLINED
    }]
    econ = pool.final_economics or {}

    view: dict[str, Any] = {
        "pool_id": pool.id,
        "community_id": pool.community_id,
        "product_id": pool.product_id,
        "product_name": product.name if product else pool.product_id,
        "unit": product.unit if product else "unit",
        "brand": product.brand if product else "",
        "supplier": supplier.name if supplier else "",
        "status": pool.status.value,
        "pickup_site": site.name if site else "",
        "pickup_is_public": site.is_public if site else True,
        "pickup_permission": site.permission.value if site else "",
        "threshold_units": pool.threshold_units,
        "provisional_units": coord.provisional_units(ctx, pool.id),
        "funded_units": coord.funded_units(ctx, pool.id),
        "member_count": len(live),
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
            }
            if community
            else None
        ),
        "pools": [_pool_view(ws, p) for p in r.list_pools(ws)],
        "decisions": decisions,
        "activity": [e.to_dict() for e in r.list_activity(ws, limit=80)],
        "metrics": coord.impact_metrics(ctx),
        "runs": [
            {
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
            for run in r.list_runs(ws, limit=12)
        ],
        "counts": {
            "members": len(r.list_households(ws)),
            "needs": len([n for n in r.list_needs(ws) if n.active]),
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
            if m.state not in {ParticipationState.WITHDRAWN, ParticipationState.DECLINED}:
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


@app.get("/api/needs")
def get_needs(workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    products = {p.id: p for p in r.list_products(ws)}
    return {
        "needs": [
            {
                "need_id": n.id,
                "household_id": n.household_id,
                "household_name": _member_name(ws, n.household_id),
                "product_id": n.product_id,
                "product_name": products[n.product_id].name if n.product_id in products else "",
                "unit": products[n.product_id].unit if n.product_id in products else "",
                "quantity": n.quantity,
                "cadence_days": n.cadence_days,
                "expected_next_need_date": n.expected_next_need_date.isoformat(),
                "earliest_purchase_date": n.earliest.isoformat(),
                "latest_purchase_date": n.latest.isoformat(),
                "flexibility_days": n.flexibility_days,
                "routine_lead_days": n.routine_lead_days,
                "min_savings_pct": n.min_savings_pct,
                "max_spend_display": format_cents(n.max_spend_cents),
                "substitution": n.substitution.value,
                "active": n.active,
            }
            for n in r.list_needs(ws)
        ]
    }


@app.get("/api/members/{household_id}")
def get_member(household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """One member's own view. Contact details and payment references never leave here."""
    ws = check_workspace(workspace)
    r = repo()
    h = r.get_household(ws, household_id)
    if h is None:
        raise HTTPException(404, "member not found")
    membership = r.get_community_membership(ws, COMMUNITY_ID, household_id)
    profile = r.get_host_profile(ws, COMMUNITY_ID, household_id)
    return {
        "id": h.id,
        "display_name": h.display_name,
        "zone": h.neighborhood,
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
    ensure_seeded(ws)
    run = PoolCoordinator(
        repo(), settings=_settings, routing=_routing, payments=_payments,
        purchaser=_purchaser, sourcing=_sourcing,
    ).run(ws, trigger=body.trigger, instruction=body.instruction, community_id=COMMUNITY_ID)
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
    counts = seed(repo(), ws)
    return {"workspace": ws, "reset": True, "seeded": counts}


@app.post("/api/demo/scenario")
def scenario(workspace: str = Query("demo")) -> dict[str, Any]:
    """Run the full showcase end to end and return the transcript."""
    ws = check_workspace(workspace)
    result = run_showcase(repo(), ws, settings=_settings, routing=_routing)
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


# Lambda entry point. Imported lazily so local uvicorn does not require mangum.
def lambda_handler(event, context):  # pragma: no cover - exercised in deployment
    from mangum import Mangum

    return Mangum(app, lifespan="off")(event, context)
