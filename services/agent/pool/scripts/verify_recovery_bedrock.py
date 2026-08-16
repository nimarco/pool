"""Real Bedrock verification of Pool's consequential recovery branch.

    AWS_PROFILE=pool-dev AWS_REGION=us-east-1 \
      .venv/bin/python -m pool.scripts.verify_recovery_bedrock

**(COSTS MONEY — a small amount.)** Two bounded runs against a real Bedrock model,
capped by the same iteration, tool-call, duplicate-call, and wall-clock bounds as every
other entrypoint. No AWS resource is created; the only paid call is
``bedrock-runtime:ConverseStream``.

``verify_bedrock`` proved the *discovery* leg is real. This proves the leg that carries
the product's harder claim: a funded pool loses committed demand, and a real model —
not a script — has to notice, decide how to repair it, and know whether the repaired
pool may lock.

The scenario, the state snapshot, and every lifecycle invariant asserted below live in
``recovery_scenario``, and ``tests/test_recovery_lifecycle.py`` runs the identical
assertions against the offline planner for free. This script adds exactly one thing: the
evidence that a real Bedrock model made the decisions.

Evidence captured, in the order the chain must actually occur:
  1. a real bedrock-runtime HTTPS call (botocore wire log)
  2. Strands dispatching tools the model chose, in the order it chose them
  3. an existing Pool inspection tool grounding the pool id the model then repairs
  4. the deterministic recovery service executing
  5. the resulting authoritative state
  6. the model's next decision, and whether the lock rules were respected
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

# Configure before importing pool.config, which snapshots the environment. Identical to
# verify_bedrock: only the model leg is real, every adapter stays free and offline.
os.environ.setdefault("AWS_PROFILE", "pool-dev")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ["MODEL_PROVIDER"] = "bedrock"
os.environ.setdefault("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
os.environ["POOL_REPOSITORY"] = "memory"
os.environ["ROUTING_PROVIDER"] = "deterministic"
os.environ["PAYMENT_PROVIDER"] = "simulated"

from pool.adapters.repository import InMemoryRepository  # noqa: E402
from pool.agent.coordinator import PoolCoordinator  # noqa: E402
from pool.config import get_settings  # noqa: E402
from pool.data.seed import COMMUNITY_ID  # noqa: E402
from pool.domain.models import DecisionKind, DecisionState  # noqa: E402
from pool.scripts.recovery_scenario import (  # noqa: E402
    RECOVERY_INSTRUCTION,
    bound_checks,
    build_pre_recovery_state,
    lock_semantics,
    projection_faithfulness,
    recovery_semantics,
    snapshot,
)
from pool.scripts.verify_bedrock import BedrockWireLog  # noqa: E402
from pool.services import coordination as coord  # noqa: E402

WS = "bedrock_recovery_verify"


# --------------------------------------------------------------------------- reporting


def print_state(label: str, state: dict[str, Any]) -> None:
    print(f"\n  {label}")
    print(f"    status            : {state['status']}")
    print(
        f"    units             : priced {state['priced_units']} "
        f"(threshold {state['threshold_units']}, {state['case_units']}-unit cases, "
        f"surplus {state['surplus_units']})"
    )
    print(
        f"    funded / in play  : {state['funded_units']} funded, "
        f"{state['in_play_units']} in play, {state['lost_units']} lost, "
        f"{state['awaiting_units']} awaiting a human"
    )
    print(
        f"    buyers            : {state['members_total']} total, "
        f"{state['authorized']} authorised, {state['awaiting_decision']} awaiting, "
        f"{state['authorization_failed']} failed"
    )
    print(f"    pending decisions : {state['pending_decisions']} {state['pending_households']}")
    if state["captured_payments"]:
        print(
            f"    captured          : {state['captured_payments']} payments, "
            f"{state['captured_cents']} cents"
        )


def print_run(run, wire_before: int, wire: BedrockWireLog, settings) -> None:
    print(f"\n  run_id           : {run.id}")
    print(f"  model            : {run.model_provider} / {run.model_id}")
    print(f"  outcome          : {run.outcome.value}")
    print(f"  termination      : {run.termination_reason}")
    print(f"  iterations       : {run.iterations} (bound {settings.bounds.max_iterations})")
    print(f"  tool calls       : {len(run.tool_calls)} (bound {settings.bounds.max_tool_calls})")
    print(f"  wall clock       : {run.duration_ms} ms")
    print(f"  input tokens     : {run.input_tokens}")
    print(f"  output tokens    : {run.output_tokens}")
    print("  bedrock requests : "
          f"{len(wire.calls) - wire_before} (botocore wire log, not our own logging)")
    for i, call in enumerate(wire.calls[wire_before:], 1):
        print(f"      [{i}] {call}")
    if run.notes:
        print(f"  notes            : {run.notes}")
    print("\n  tool sequence the model chose:")
    for i, t in enumerate(run.tool_calls, 1):
        mark = "" if t.ok else "  << REJECTED by deterministic code"
        print(f"    [{i}] {t.name}  (args {t.arguments_digest}, ok={t.ok}){mark}")
        print(f"        -> {t.summary[:150]}")


def print_verdict(title: str, checks: dict[str, bool], problems: list[str]) -> bool:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    for problem in problems:
        print(f"        projection problem: {problem}")
    return all(checks.values())


# --------------------------------------------------------------------------- main


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
    print(f"  payment_provider : {settings.payment_provider}  (simulated; no Stripe, no money)")
    print(f"  purchase_executor: {settings.purchase_executor}  (simulated)")
    print(
        "  bounds           : "
        f"iterations={settings.bounds.max_iterations} "
        f"tool_calls={settings.bounds.max_tool_calls} "
        f"duplicates={settings.bounds.max_duplicate_tool_calls} "
        f"timeout={settings.bounds.workflow_timeout_seconds}s"
    )

    repo = InMemoryRepository()
    coordinator = PoolCoordinator(repo, settings=settings)
    model, _model_id, provider = coordinator._build_model()
    print(f"\n  constructed model: {type(model).__name__}")
    print(f"  resolved model_id: {model.get_config().get('model_id')}")
    if provider != "bedrock" or type(model).__name__ != "BedrockModel":
        print("\nFAIL: the coordinator did not construct a real BedrockModel")
        return 1

    print("\n" + "=" * 78)
    print("SETUP — deterministic services only, no model involved")
    print("=" * 78)
    setup_ctx, pool, final = build_pre_recovery_state(coordinator, repo, WS)
    print(f"  pool             : {pool.id}")
    print(f"  auto-authorised  : {len(final.auto_authorised)} buyer(s)")
    print(f"  awaiting a human : {len(final.awaiting_decision)} buyer(s)")
    print(f"  card declined    : {len(final.authorisation_failures)} buyer(s) — demand now lost")

    before = snapshot(setup_ctx, pool.id)
    print_state("STARTING STATE (the triggering failure has already happened)", before)
    lost, awaiting = before["lost_units"], before["awaiting_units"]
    print(
        f"\n  the discriminating fact: {lost} unit(s) are gone and {awaiting} unit(s) are "
        f"merely unanswered.\n  Correct recovery replaces {lost}, not {lost + awaiting}."
    )

    # ---------------------------------------------------------------- phase 1
    print("\n" + "=" * 78)
    print("PHASE 1 — real Bedrock model decides how to recover the pool")
    print("=" * 78)
    print(f"  instruction: {RECOVERY_INSTRUCTION}")
    wire_before = len(wire.calls)
    run1 = coordinator.run(
        WS,
        trigger="bedrock_recovery_verification",
        community_id=COMMUNITY_ID,
        instruction=RECOVERY_INSTRUCTION,
    )
    ctx1 = coordinator.last_tool_context
    print_run(run1, wire_before, wire, settings)
    after = snapshot(setup_ctx, pool.id)
    print_state("ENDING STATE", after)

    for event in repo.list_activity(WS, limit=500):
        if event.kind in {"pool_recovered", "recovery_pending", "recovery_failed"}:
            print(f"\n  activity: {event.kind} — {event.summary[:100]}")
            print(f"            facts: {event.facts}")

    problems1 = projection_faithfulness(ctx1, run1)
    checks1: dict[str, bool] = {
        # The only checks that depend on the model being Bedrock. Everything below is
        # the same lifecycle assertion the free offline test makes.
        "real BedrockModel constructed": type(model).__name__ == "BedrockModel",
        "model_id is the configured one": model.get_config().get("model_id")
        == settings.bedrock_model_id,
        "real bedrock-runtime HTTPS calls made": len(wire.calls) > wire_before,
        "run recorded as bedrock provider": run1.model_provider == "bedrock",
        "model consumed and produced tokens": bool(run1.input_tokens and run1.output_tokens),
        **recovery_semantics(before, after, run1, problems1),
        **bound_checks(run1, settings),
    }
    phase1_ok = print_verdict("PHASE 1 VERDICT", checks1, problems1)
    if not phase1_ok:
        print("\n  PHASE 1 NOT VERIFIED — stopping before spending on phase 2")
        return 1

    # ---------------------------------------------------------------- phase 2
    #
    # Only far enough to prove the coordinator knows when a lock IS allowed. The
    # deterministic rules stay authoritative: the humans answer (a scripted *input*,
    # like every other human answer in the showcase), and nothing about the lock is
    # forced. If the pool still could not lock, that would be the honest result.
    print("\n" + "=" * 78)
    print("PHASE 2 — the buyers who were still deciding answer; is a lock allowed now?")
    print("=" * 78)
    answered = 0
    for d in list(repo.list_decisions(WS)):
        if d.state == DecisionState.PENDING and d.kind == DecisionKind.APPROVE_FINAL_OFFER:
            coord.respond_to_decision(ctx=setup_ctx, decision_id=d.id, approve=True)
            answered += 1
    mid = snapshot(setup_ctx, pool.id)
    print(f"  {answered} buyer(s) approved their exact price from the Decision Inbox")
    print_state("STATE BEFORE PHASE 2 RUN", mid)

    wire_before = len(wire.calls)
    run2 = coordinator.run(
        WS,
        trigger="bedrock_recovery_verification",
        community_id=COMMUNITY_ID,
        instruction=RECOVERY_INSTRUCTION,
    )
    ctx2 = coordinator.last_tool_context
    print_run(run2, wire_before, wire, settings)
    final_state = snapshot(setup_ctx, pool.id)
    print_state("FINAL STATE", final_state)

    problems2 = projection_faithfulness(ctx2, run2)
    checks2: dict[str, bool] = {
        "real bedrock-runtime HTTPS calls made": len(wire.calls) > wire_before,
        **lock_semantics(mid, final_state, run2, problems2),
        **bound_checks(run2, settings),
    }
    phase2_ok = print_verdict("PHASE 2 VERDICT", checks2, problems2)

    # ---------------------------------------------------------------- summary
    print("\n" + "=" * 78)
    print("COST AND BOUNDS SUMMARY")
    print("=" * 78)
    print("  run  iters  tools  in_tok   out_tok  ms      outcome")
    for label, run in (("1", run1), ("2", run2)):
        print(
            f"  {label}    {run.iterations:<6} {len(run.tool_calls):<6} "
            f"{run.input_tokens:<8} {run.output_tokens:<8} {run.duration_ms:<7} "
            f"{run.outcome.value}"
        )
    print(
        f"  totals: {run1.iterations + run2.iterations} iterations, "
        f"{run1.input_tokens + run2.input_tokens} in / "
        f"{run1.output_tokens + run2.output_tokens} out tokens, "
        f"{len(wire.calls)} real bedrock-runtime requests"
    )
    print("  AWS resources created: none")

    ok = phase1_ok and phase2_ok
    print(f"\n  {'VERIFIED' if ok else 'NOT VERIFIED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
