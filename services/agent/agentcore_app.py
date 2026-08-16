"""Amazon Bedrock AgentCore Runtime entrypoint for the Pool coordinator.

Deployed with the official AgentCore starter toolkit rather than a hand-rolled
container path:

    cd services/agent
    agentcore configure --entrypoint agentcore_app.py
    agentcore launch

The entrypoint is deliberately thin. It validates the incoming payload, selects a
workspace, and hands off to :class:`~pool.agent.coordinator.PoolCoordinator` — the same
class the local API and the test suite drive. There is no AgentCore-specific
orchestration logic, so a run here and a run locally are the same run.

Cost note: this process is invoked per request. It starts nothing recurring, holds no
background loop, and inherits the same iteration, tool-call, and wall-clock bounds as
every other entrypoint (AGENTS.md §3.1).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from pool.adapters.payments import build_payment_provider
from pool.adapters.purchase import build_purchase_executor
from pool.adapters.repository import build_repository
from pool.adapters.routing import build_routing
from pool.agent.coordinator import PoolCoordinator
from pool.config import get_settings
from pool.data.seed import COMMUNITY_ID, seed

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("pool.agentcore")

app = BedrockAgentCoreApp()

# Built once per container so repeated invocations reuse the clients rather than
# re-creating a boto3 session on every request.
_settings = get_settings()
_repo = build_repository(_settings.repository, _settings.dynamodb_table, _settings.aws_region)
_routing = build_routing(
    _settings.routing_provider, _settings.aws_region, _settings.max_route_matrix_cells
)
_coordinator = PoolCoordinator(
    _repo,
    settings=_settings,
    routing=_routing,
    # Same adapters as every other entrypoint: simulated payments unless a TEST-mode
    # Stripe key is configured, and the clearly-labelled simulated purchase executor.
    payments=build_payment_provider(_settings.payment_provider, _settings.stripe_api_key),
    purchaser=build_purchase_executor(_settings.purchase_executor),
)

ALLOWED_TRIGGERS = {
    "scheduled_scan",
    "manual",
    "advance_pools",
    "dropout_recovery",
    "event",
    "smoke_test",
}


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Run one bounded coordination cycle.

    Payload::

        {
          "workspace": "primary",          # optional, defaults to $POOL_WORKSPACE or "primary"
          "community_id": "comm_...",      # optional, defaults to the demo Community
          "trigger": "scheduled_scan",     # optional, must be a known trigger
          "instruction": "..."             # optional override of the run instruction
        }

    Returns a structured run summary. Payloads are validated here rather than forwarded
    blindly to the agent framework.
    """
    payload = payload or {}

    workspace = str(payload.get("workspace") or os.environ.get("POOL_WORKSPACE", "primary"))
    if not workspace.replace("_", "").replace("-", "").isalnum():
        return {"error": "invalid workspace identifier"}

    trigger = str(payload.get("trigger") or "scheduled_scan")
    if trigger not in ALLOWED_TRIGGERS:
        return {"error": f"unknown trigger: {trigger}", "allowed": sorted(ALLOWED_TRIGGERS)}

    instruction = payload.get("instruction")
    if instruction is not None:
        instruction = str(instruction)[:2000]

    community_id = str(payload.get("community_id") or COMMUNITY_ID)

    # A cold workspace has no Community, so a run would have nothing to coordinate.
    # Seeding the synthetic dataset here keeps a scheduled invocation meaningful without
    # a separate bootstrap step — and the data is the same synthetic set as everywhere.
    if not _repo.list_communities(workspace):
        counts = seed(_repo, workspace)
        logger.info("seeded empty workspace=%s %s", workspace, counts)

    logger.info("coordination run starting workspace=%s trigger=%s", workspace, trigger)
    run = _coordinator.run(
        workspace, trigger=trigger, instruction=instruction, community_id=community_id
    )
    logger.info(
        "coordination run finished run_id=%s outcome=%s iterations=%d tools=%d reason=%s",
        run.id, run.outcome.value, run.iterations, len(run.tool_calls), run.termination_reason,
    )

    # Structured, safe to log and to show a judge: tool names and counters, never
    # model reasoning (AGENTS.md §9).
    return {
        "run_id": run.id,
        "workspace": workspace,
        "outcome": run.outcome.value,
        "iterations": run.iterations,
        "tool_calls": [t.name for t in run.tool_calls],
        "termination_reason": run.termination_reason,
        "model_provider": run.model_provider,
        "model_id": run.model_id,
        "duration_ms": run.duration_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "hitl_decisions_created": run.hitl_decisions_created,
    }


if __name__ == "__main__":  # pragma: no cover
    app.run(port=int(os.environ.get("PORT", "8080")))
