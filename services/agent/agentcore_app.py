"""Amazon Bedrock AgentCore Runtime entrypoint for the Pool coordinator.

Deployed with the official AgentCore CLI (``@aws/agentcore``) rather than a hand-rolled
container path. The project config lives in ``agentcore/`` at the repository root and
points its ``codeLocation`` at this directory, so the file is deployed where it sits:

    agentcore validate
    agentcore deploy --dry-run
    agentcore deploy

The older starter-toolkit flow (``agentcore configure`` / ``agentcore launch``) is
retired; that CLI is legacy and shares the ``agentcore`` command name with this one.

The entrypoint is deliberately thin. It validates the incoming payload, selects a
workspace, and hands off to :class:`~pool.agent.coordinator.PoolCoordinator` — the same
class the local API and the test suite drive. There is no AgentCore-specific
orchestration logic, so a run here and a run locally are the same run.

**The runtime coordinates inside a workspace; it never creates or destroys one.**
With ``POOL_REPOSITORY=dynamodb`` this process writes to the same table, and the same
partition, that the public API serves the browser from — so the pool a visitor sees was
genuinely built by this agent rather than replayed from its answer. That sharing is only
safe with a boundary, and this is it:

* the workspace arrives in the payload and nothing else may name one — no tool takes a
  workspace argument, and the model is never shown the value (AGENTS.md §4);
* only one principal can invoke this runtime at all (``AWS_IAM`` inbound auth, and the
  demo Lambda's role is the only one granted ``InvokeAgentRuntime`` on this ARN), so the
  payload is server-built by definition;
* the workspace must already exist. Seeding is a workspace-creating act and belongs to
  whoever owns the workspace, so on a shared store this refuses rather than seeds — the
  execution role has no ``DeleteItem`` or ``BatchWriteItem`` and could not complete
  ``seed()``'s reset anyway (``services/agent/iam/agentcore-dynamodb.json``).

Cost note: this process is invoked per request. It starts nothing recurring, holds no
background loop, and inherits the same iteration, tool-call, and wall-clock bounds as
every other entrypoint (AGENTS.md §3.1).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from pool.adapters.payments import build_payment_provider
from pool.adapters.purchase import build_purchase_executor
from pool.adapters.repository import build_repository
from pool.adapters.routing import build_routing
from pool.agent.coordinator import PoolCoordinator
from pool.config import get_settings
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import ToolCallRecord

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("pool.agentcore")

app = BedrockAgentCoreApp()

#: The same shape ``pool/api/app.py`` accepts, stated as a pattern rather than as
#: ``str.isalnum()`` on a stripped string — that idiom accepts every Unicode letter and
#: digit, so ``café`` and ``١٢٣`` were both valid workspace names. Not reachable (only
#: the Lambda can invoke this), but a partition key is not a place for surprises.
WORKSPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")

# Built once per container so repeated invocations reuse the clients rather than
# re-creating a boto3 session on every request.
_settings = get_settings()
_repo = build_repository(
    _settings.repository,
    _settings.dynamodb_table,
    _settings.aws_region,
    consistent_reads=_settings.dynamodb_consistent_reads,
)
#: True when this runtime is reading and writing a store somebody else also writes.
#: The one behavioural difference it makes is that this process will not bootstrap a
#: workspace — see the module docstring.
_shared_store = _settings.repository != "memory"
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

def tool_call_view(record: ToolCallRecord) -> dict[str, Any]:
    """One tool call, reduced to what an operator needs from outside the runtime.

    `ok` and `summary` are the fields that separate work the coordinator actually did
    from a call deterministic code refused before touching any state. Without them a
    `recover_pool` rejected for an invented pool id is indistinguishable, in the
    response, from one that repaired a pool — which is precisely the Q16 behaviour a
    deployed run has to be able to prove (BUILD_HISTORY #0021).

    Deliberately excluded: `arguments_digest`, which is a hash and tells a reader
    nothing, and `at`, which duplicates the run's own timing. No model reasoning text
    ever reaches this dict (AGENTS.md §9). `summary` is the coordinator's own one-line
    result description, already capped at 180 characters at the point it is recorded.

    Same shape as the API's run detail (`pool/api/app.py`), so the hosted runtime and
    the local API describe a run identically.
    """
    return {"name": record.name, "ok": record.ok, "summary": record.summary}


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
    if not WORKSPACE_RE.match(workspace):
        return {"error": "invalid workspace identifier"}

    trigger = str(payload.get("trigger") or "scheduled_scan")
    if trigger not in ALLOWED_TRIGGERS:
        return {"error": f"unknown trigger: {trigger}", "allowed": sorted(ALLOWED_TRIGGERS)}

    instruction = payload.get("instruction")
    if instruction is not None:
        instruction = str(instruction)[:2000]

    community_id = str(payload.get("community_id") or COMMUNITY_ID)

    # A cold workspace has no Community, so a run would have nothing to coordinate.
    #
    # On this runtime's *own* in-memory store, seeding the synthetic dataset here keeps a
    # one-shot invocation meaningful without a separate bootstrap step. On a store the
    # API also owns, it would be this process reaching outside its remit: `seed()` opens
    # with `repo.reset()`, which deletes every row in the partition — so a stale or
    # misdirected invocation could wipe a live visitor's session. The execution role
    # holds no delete permission, so the attempt would fail mid-way and leave a
    # half-emptied workspace behind; refusing before touching anything is both safer and
    # a clearer error to read.
    if not _repo.list_communities(workspace):
        if _shared_store:
            logger.warning("refusing to seed shared workspace=%s", workspace)
            return {"error": "workspace has no community; this runtime does not create one"}
        counts = seed(_repo, workspace)
        logger.info("seeded empty workspace=%s %s", workspace, counts)

    logger.info("coordination run starting workspace=%s trigger=%s", workspace, trigger)
    run = _coordinator.run(
        workspace, trigger=trigger, instruction=instruction, community_id=community_id
    )
    logger.info(
        "coordination run finished run_id=%s outcome=%s iterations=%d tools=%d "
        "refused=%d reason=%s",
        run.id, run.outcome.value, run.iterations, len(run.tool_calls),
        sum(1 for t in run.tool_calls if not t.ok), run.termination_reason,
    )

    # Structured, safe to log and to show a judge: tool names and counters, never
    # model reasoning (AGENTS.md §9).
    return {
        "run_id": run.id,
        "workspace": workspace,
        "outcome": run.outcome.value,
        "iterations": run.iterations,
        "tool_calls": [tool_call_view(t) for t in run.tool_calls],
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
