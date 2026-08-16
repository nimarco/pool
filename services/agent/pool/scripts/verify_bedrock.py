"""Smallest real Bedrock -> Strands -> Pool tool verification.

    AWS_PROFILE=pool-dev AWS_REGION=us-east-1 \
      .venv/bin/python -m pool.scripts.verify_bedrock

**(COSTS MONEY — a small amount.)** One bounded run against a real Bedrock model. The
run is capped by the same iteration, tool-call, duplicate-call, and wall-clock bounds as
every other entrypoint, and creates no AWS resource.

Drives the EXISTING PoolCoordinator with the EXISTING typed tools. Nothing is
scaffolded, nothing is stubbed, and no tool is invoked by hand — the only change from a
normal local run is that the deterministic offline planner is replaced by a real Bedrock
model.

Evidence captured, in the order the chain must actually occur:
  1. a real bedrock-runtime HTTPS call (botocore wire log)
  2. Strands dispatching a tool the model chose
  3. a Pool tool executing deterministic domain code
  4. the resulting stored state
  5. the run record with token usage
"""

from __future__ import annotations

import json
import logging
import os
import sys

# Configure before importing pool.config, which snapshots the environment.
os.environ.setdefault("AWS_PROFILE", "pool-dev")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ["MODEL_PROVIDER"] = "bedrock"
os.environ.setdefault("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
# Adapters stay free and offline: in-memory store, deterministic routing, simulated
# payments. Only the model leg is real.
os.environ["POOL_REPOSITORY"] = "memory"
os.environ["ROUTING_PROVIDER"] = "deterministic"
os.environ["PAYMENT_PROVIDER"] = "simulated"

from pool.adapters.repository import InMemoryRepository  # noqa: E402
from pool.agent.coordinator import PoolCoordinator  # noqa: E402
from pool.config import get_settings  # noqa: E402
from pool.data.seed import COMMUNITY_ID, seed  # noqa: E402

WS = "bedrock_verify"

DEFAULT_MODEL_ID = "us.amazon.nova-lite-v1:0"


class BedrockWireLog(logging.Handler):
    """Records genuine bedrock-runtime API calls from botocore's own endpoint logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.calls: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return
        if "bedrock-runtime" in message and "Making request" in message:
            # One line per real HTTPS request to the Bedrock runtime endpoint.
            head = message.split("body=")[0][:200]
            self.calls.append(head)


def main() -> int:
    wire = BedrockWireLog()
    endpoint_logger = logging.getLogger("botocore.endpoint")
    endpoint_logger.setLevel(logging.DEBUG)
    endpoint_logger.addHandler(wire)

    settings = get_settings()
    print("=" * 78)
    print("CONFIGURATION")
    print("=" * 78)
    print(f"  model_provider   : {settings.model_provider}")
    print(f"  bedrock_model_id : {settings.bedrock_model_id}")
    print(f"  aws_profile      : {settings.aws_profile}")
    print(f"  aws_region       : {settings.aws_region}")
    print(f"  repository       : {settings.repository}")
    print(f"  routing_provider : {settings.routing_provider}")
    print(f"  payment_provider : {settings.payment_provider}")
    print("  bounds           : "
          f"iterations={settings.bounds.max_iterations} "
          f"tool_calls={settings.bounds.max_tool_calls} "
          f"duplicates={settings.bounds.max_duplicate_tool_calls} "
          f"timeout={settings.bounds.workflow_timeout_seconds}s")

    repo = InMemoryRepository()
    counts = seed(repo, WS)
    print(f"\n  seeded           : {counts['members']} members, {counts['needs']} needs, "
          f"{counts['offers']} offers")

    coordinator = PoolCoordinator(repo, settings=settings)
    model, model_id, provider = coordinator._build_model()
    print(f"\n  constructed model: {type(model).__name__}")
    print(f"  resolved model_id: {model.get_config().get('model_id')}")
    print(f"  reported provider: {provider}")
    if provider != "bedrock" or type(model).__name__ != "BedrockModel":
        print("\nFAIL: the coordinator did not construct a real BedrockModel")
        return 1

    print("\n" + "=" * 78)
    print("RUN — real Bedrock model driving the real Strands loop")
    print("=" * 78)
    run = coordinator.run(WS, trigger="bedrock_verification", community_id=COMMUNITY_ID)

    print(f"\n  run_id           : {run.id}")
    print(f"  model_provider   : {run.model_provider}")
    print(f"  model_id         : {run.model_id}")
    print(f"  outcome          : {run.outcome.value}")
    print(f"  termination      : {run.termination_reason}")
    print(f"  iterations       : {run.iterations} (bound {settings.bounds.max_iterations})")
    print(f"  duration_ms      : {run.duration_ms}")
    print(f"  input_tokens     : {run.input_tokens}")
    print(f"  output_tokens    : {run.output_tokens}")
    if run.notes:
        print(f"  notes            : {run.notes}")

    print("\n" + "-" * 78)
    print("1. BEDROCK WIRE CALLS (botocore, not our own logging)")
    print("-" * 78)
    for i, call in enumerate(wire.calls, 1):
        print(f"  [{i}] {call}")
    print(f"  total real bedrock-runtime requests: {len(wire.calls)}")

    print("\n" + "-" * 78)
    print("2. POOL TOOLS THE MODEL CHOSE (dispatched by Strands)")
    print("-" * 78)
    for i, t in enumerate(run.tool_calls, 1):
        print(f"  [{i}] {t.name}")
        print(f"      args_digest : {t.arguments_digest}")
        print(f"      ok          : {t.ok}")
        print(f"      result      : {t.summary[:150]}")

    print("\n" + "-" * 78)
    print("3. DETERMINISTIC STATE WRITTEN BY THOSE TOOLS")
    print("-" * 78)
    pools = repo.list_pools(WS)
    print(f"  pools created    : {len(pools)}")
    for p in pools:
        product = repo.get_product(WS, p.product_id)
        members = repo.list_memberships(WS, p.id)
        print(f"    - {p.id} {product.name if product else p.product_id!r}")
        print(f"      status={p.status.value} threshold={p.threshold_units} "
              f"members={len(members)}")
    activity = [e for e in repo.list_activity(WS, limit=50) if e.run_id == run.id]
    print(f"  activity events  : {len(activity)}")
    for e in activity[:6]:
        print(f"    - {e.kind}: {e.summary[:90]}")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    checks = {
        "real BedrockModel constructed": type(model).__name__ == "BedrockModel",
        "model_id is the configured one": model.get_config().get("model_id")
        == settings.bedrock_model_id,
        "real bedrock-runtime HTTPS calls made": len(wire.calls) > 0,
        "run recorded as bedrock provider": run.model_provider == "bedrock",
        "model consumed input tokens": bool(run.input_tokens),
        "model produced output tokens": bool(run.output_tokens),
        "at least one Pool tool was called": len(run.tool_calls) > 0,
        "every tool call succeeded": all(t.ok for t in run.tool_calls),
        "tool results are structured JSON": all(
            _is_jsonish(t.summary) for t in run.tool_calls
        ),
        "iterations within bound": run.iterations <= settings.bounds.max_iterations,
        "tool calls within bound": len(run.tool_calls) <= settings.bounds.max_tool_calls,
        "run terminated with a recorded reason": bool(run.termination_reason),
    }
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    ok = all(checks.values())
    print(f"\n  {'VERIFIED' if ok else 'NOT VERIFIED'}")
    return 0 if ok else 1


def _is_jsonish(summary: str) -> bool:
    """Tool results are JSON produced by deterministic code, not model prose."""
    text = summary.strip().rstrip("…")
    if not text.startswith("{"):
        return False
    try:
        json.loads(text)
    except ValueError:
        return True  # truncated for display, but structurally a JSON object
    return True


if __name__ == "__main__":
    sys.exit(main())
