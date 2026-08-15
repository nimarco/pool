"""Public HTTP API.

Serverless-friendly: a plain FastAPI app that runs under uvicorn locally and under
API Gateway + Lambda in the cloud via Mangum. The browser never holds AWS credentials
and never calls an AWS service directly — it only talks to this API (brief §29).

Workspaces give each visitor an isolated dataset so two judges cannot corrupt each
other's demo. A workspace is a plain string supplied by the client; server-side it only
ever selects a DynamoDB partition, and demo partitions carry a TTL.

Privacy: no endpoint ever returns a household's precise coordinates. Map positions are
snapped to a ~110 m grid before they leave the process (AGENTS.md §4).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..adapters.repository import Repository, build_repository
from ..adapters.routing import build_routing
from ..agent.coordinator import PoolCoordinator
from ..config import get_settings
from ..data.seed import seed
from ..domain.models import DecisionState, MembershipState
from ..domain.money import bps_to_pct_str, format_cents
from ..services import coordination as coord
from ..services.demo import run_showcase

logger = logging.getLogger(__name__)

WORKSPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
GRID_DECIMALS = 3  # ~110 m — enough for neighbourhood context, not enough to find a door

app = FastAPI(
    title="Pool API",
    version="0.1.0",
    description="Autonomous neighbourhood group-buying coordinator. All data is synthetic.",
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


def repo() -> Repository:
    return _repo


def check_workspace(ws: str) -> str:
    if not WORKSPACE_RE.match(ws):
        raise HTTPException(400, "invalid workspace identifier")
    return ws


def coarse(lat: float, lon: float) -> tuple[float, float]:
    """Snap a coordinate to a grid before it leaves the server."""
    return round(lat, GRID_DECIMALS), round(lon, GRID_DECIMALS)


def ensure_seeded(ws: str) -> None:
    if not repo().list_households(ws):
        seed(repo(), ws)


# --------------------------------------------------------------------------- models


class RunRequest(BaseModel):
    trigger: str = Field(default="manual_demo", max_length=60)


class DecisionResponse(BaseModel):
    approve: bool


# --------------------------------------------------------------------------- health


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "repository": _settings.repository,
        "routing_provider": _settings.routing_provider,
        "model_provider": _settings.model_provider,
        "model_id": _settings.bedrock_model_id if _settings.model_provider == "bedrock" else "offline",
        "schedules_enabled": _settings.schedules_enabled,
        "bounds": {
            "max_iterations": _settings.bounds.max_iterations,
            "max_tool_calls": _settings.bounds.max_tool_calls,
            "max_duplicate_tool_calls": _settings.bounds.max_duplicate_tool_calls,
            "workflow_timeout_seconds": _settings.bounds.workflow_timeout_seconds,
        },
    }


# --------------------------------------------------------------------------- state


def _pool_view(ws: str, pool) -> dict[str, Any]:
    r = repo()
    product = r.get_product(ws, pool.product_id)
    site = r.get_site(ws, pool.pickup_site_id)
    offer = r.get_offer(ws, pool.offer_id)
    members = r.list_memberships(ws, pool.id)
    live = [m for m in members if m.state != MembershipState.WITHDRAWN]
    committed = [m for m in members if m.state == MembershipState.COMMITTED]
    committed_units = sum(m.allocated_units for m in committed)
    baseline = sum(m.baseline_cents for m in committed)
    cost = sum(m.cost_cents for m in committed)
    travel = [m.travel_minutes for m in committed] or [0]

    households = {h.id: h for h in r.list_households(ws)}
    return {
        "pool_id": pool.id,
        "product_id": pool.product_id,
        "product_name": product.name if product else pool.product_id,
        "unit": product.unit if product else "unit",
        "supplier": offer.supplier if offer else "",
        "status": pool.status.value,
        "pickup_site": site.name if site else "",
        "pickup_is_public": site.is_public if site else True,
        "deadline": pool.deadline.isoformat(),
        "threshold_units": pool.threshold_units,
        "committed_units": committed_units,
        "progress_pct": min(100, round(committed_units * 100 / pool.threshold_units))
        if pool.threshold_units
        else 0,
        "member_count": len(live),
        "committed_count": len(committed),
        "baseline_cents": baseline,
        "cost_cents": cost,
        "savings_cents": baseline - cost,
        "savings_display": format_cents(baseline - cost),
        "savings_pct": bps_to_pct_str(committed[0].savings_bps) if committed else "0.0%",
        "avg_travel_minutes": round(sum(travel) / len(travel)),
        "members": [
            {
                # Privacy-safe identity: a display name, never an address.
                "household_id": m.household_id,
                "display_name": households[m.household_id].display_name
                if m.household_id in households
                else m.household_id,
                "neighborhood": households[m.household_id].neighborhood
                if m.household_id in households
                else "",
                "units": m.allocated_units,
                "cost_display": format_cents(m.cost_cents),
                "baseline_display": format_cents(m.baseline_cents),
                "savings_pct": bps_to_pct_str(m.savings_bps),
                "travel_minutes": m.travel_minutes,
                "state": m.state.value,
                "path": m.path.value,
            }
            for m in members
        ],
    }


@app.get("/api/state")
def get_state(workspace: str = Query("demo")) -> dict[str, Any]:
    """Everything the dashboard needs in one round trip."""
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    pools = [_pool_view(ws, p) for p in r.list_pools(ws)]
    decisions = [
        {
            "decision_id": d.id,
            "household_id": d.household_id,
            "household_name": (
                (r.get_household(ws, d.household_id).display_name)
                if r.get_household(ws, d.household_id)
                else d.household_id
            ),
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
        "pools": pools,
        "decisions": decisions,
        "activity": [e.to_dict() for e in r.list_activity(ws, limit=60)],
        "metrics": coord.impact_metrics(r, ws),
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
            "households": len(r.list_households(ws)),
            "needs": len([n for n in r.list_needs(ws) if n.active]),
            "products": len(r.list_products(ws)),
        },
        "is_demo_data": True,
    }


@app.get("/api/pools/{pool_id}")
def get_pool(pool_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    pool = repo().get_pool(ws, pool_id)
    if pool is None:
        raise HTTPException(404, "pool not found")
    return _pool_view(ws, pool)


@app.get("/api/map")
def get_map(workspace: str = Query("demo")) -> dict[str, Any]:
    """Neighbourhood view.

    Household positions are snapped to a coarse grid and carry no address. Pickup
    sites are public places, so those are exact.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()

    pooled: dict[str, str] = {}
    for p in r.list_pools(ws):
        for m in r.list_memberships(ws, p.id):
            if m.state in {MembershipState.COMMITTED, MembershipState.INVITED}:
                pooled[m.household_id] = p.id

    need_counts: dict[str, int] = {}
    for n in r.list_needs(ws):
        if n.active:
            need_counts[n.household_id] = need_counts.get(n.household_id, 0) + 1

    households = []
    for h in r.list_households(ws):
        lat, lon = coarse(h.lat, h.lon)
        households.append(
            {
                "id": h.id,
                "lat": lat,
                "lon": lon,
                "neighborhood": h.neighborhood,
                "active_needs": need_counts.get(h.id, 0),
                "in_pool": h.id in pooled,
                "pool_id": pooled.get(h.id),
            }
        )

    return {
        "households": households,
        "sites": [
            {"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon,
             "is_public": s.is_public, "kind": s.kind}
            for s in r.list_sites(ws)
            if s.is_public
        ],
        "position_precision_m": 110,
        "note": "Household positions are approximate by design and contain no address.",
    }


@app.get("/api/needs")
def get_needs(workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    r = repo()
    products = {p.id: p for p in r.list_products(ws)}
    households = {h.id: h for h in r.list_households(ws)}
    return {
        "needs": [
            {
                "need_id": n.id,
                "household_id": n.household_id,
                "household_name": households[n.household_id].display_name
                if n.household_id in households
                else n.household_id,
                "product_id": n.product_id,
                "product_name": products[n.product_id].name if n.product_id in products else "",
                "unit": products[n.product_id].unit if n.product_id in products else "",
                "quantity": n.quantity,
                "cadence_days": n.cadence_days,
                "needed_by": n.needed_by.isoformat(),
                "min_savings_pct": n.min_savings_pct,
                "max_spend_display": format_cents(n.max_spend_cents),
                "accept_substitutes": n.accept_substitutes,
                "active": n.active,
            }
            for n in r.list_needs(ws)
        ]
    }


@app.get("/api/households/{household_id}")
def get_household(household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    ws = check_workspace(workspace)
    h = repo().get_household(ws, household_id)
    if h is None:
        raise HTTPException(404, "household not found")
    return {
        "id": h.id,
        "display_name": h.display_name,
        "neighborhood": h.neighborhood,
        "is_host_willing": h.is_host_willing,
        "autonomy": h.autonomy.to_dict(),
        "autonomy_display": {
            "mode": h.autonomy.mode.value,
            "min_savings": f"{h.autonomy.min_savings_pct}%",
            "max_spend": format_cents(h.autonomy.max_total_cost_cents),
            "max_travel": f"{h.autonomy.max_travel_minutes} min",
            "allow_substitutes": h.autonomy.allow_substitutes,
            "public_pickup_only": h.autonomy.public_pickup_only,
        },
    }


# --------------------------------------------------------------------------- actions


@app.post("/api/agent/run")
def trigger_run(
    body: RunRequest = Body(default=RunRequest()), workspace: str = Query("demo")
) -> dict[str, Any]:
    """Run the coordinator once.

    This is the *same* code path the EventBridge schedule invokes — there is no
    separate demo path (brief §10). One run per request; nothing recurring is started.
    """
    ws = check_workspace(workspace)
    ensure_seeded(ws)
    run = PoolCoordinator(repo(), settings=_settings, routing=_routing).run(
        ws, trigger=body.trigger
    )
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
    try:
        decision = coord.respond_to_decision(
            repo=repo(), ws=ws, decision_id=decision_id, approve=body.approve
        )
    except coord.CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc
    pool = repo().get_pool(ws, decision.pool_id)
    return {
        "decision_id": decision.id,
        "state": decision.state.value,
        "pool_status": pool.status.value if pool else None,
        "committed_units": coord.committed_units(repo(), ws, decision.pool_id),
    }


@app.post("/api/pools/{pool_id}/withdraw/{household_id}")
def withdraw(pool_id: str, household_id: str, workspace: str = Query("demo")) -> dict[str, Any]:
    """Simulate a participant dropping out. Demo control for the recovery scenario."""
    ws = check_workspace(workspace)
    try:
        return coord.withdraw_household(
            repo=repo(), ws=ws, pool_id=pool_id, household_id=household_id
        )
    except coord.CoordinationError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/demo/reset")
def reset(workspace: str = Query("demo")) -> dict[str, Any]:
    """Reset a workspace to the seeded starting state."""
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


# Lambda entry point. Imported lazily so local uvicorn does not require mangum.
def lambda_handler(event, context):  # pragma: no cover - exercised in deployment
    from mangum import Mangum

    return Mangum(app, lifespan="off")(event, context)
