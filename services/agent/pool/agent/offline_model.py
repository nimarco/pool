"""An offline, deterministic stand-in for the Bedrock model.

**What this replaces:** the LLM, and only the LLM.

Everything else in the run is the real thing — the real Strands event loop, the real
tool implementations, the real deterministic domain math, the real state machine, the
real Smart Join policy engine, and the real human-in-the-loop boundary. The planner
below chooses the next tool from structured tool results exactly where the model
would, using the same tool schemas.

**Why it exists:** the whole test suite and the local demo can then exercise the true
orchestration path at zero token cost (AGENTS.md §3.3, §3.6). Cheap tests are tests
that actually get run.

**What it is not:** it is not a substitute for evidence that Bedrock works, and it must
never be presented as one. Any run using it is labelled ``model_provider="offline"``
in the run record and in the UI, so a demo can always show which runs were model-driven.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable
from typing import Any

from strands.models import Model

MAX_PRODUCTS_TO_INVESTIGATE = 4


def _tool_event(name: str, payload: dict[str, Any]) -> list[dict]:
    """Build the Bedrock-shaped stream events for a single tool call."""
    tool_use_id = f"tooluse_{uuid.uuid4().hex[:16]}"
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
    ]


def _text_event(text: str) -> list[dict]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"delta": {"text": text}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


def _metadata_event() -> dict:
    # Explicitly zero: no tokens were purchased to produce this turn.
    return {
        "metadata": {
            "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
            "metrics": {"latencyMs": 0},
        }
    }


class TranscriptView:
    """Reads the conversation the way the planner needs it: tools called, results seen."""

    def __init__(self, messages: list[dict]) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.results: list[dict] = []
        self.user_text = ""

        for message in messages:
            role = message.get("role")
            for block in message.get("content", []) or []:
                if not isinstance(block, dict):
                    continue
                if role == "user" and "text" in block and not self.user_text:
                    self.user_text = str(block["text"])
                if "toolUse" in block:
                    tu = block["toolUse"]
                    self.calls.append((str(tu.get("name", "")), tu.get("input") or {}))
                if "toolResult" in block:
                    parsed = self._parse_result(block["toolResult"])
                    if parsed is not None:
                        self.results.append(parsed)

    @staticmethod
    def _parse_result(tool_result: dict) -> dict | None:
        for block in tool_result.get("content", []) or []:
            if isinstance(block, dict) and "text" in block:
                try:
                    return json.loads(block["text"])
                except (TypeError, ValueError):
                    return {"_raw": block["text"]}
        return None

    def called(self, name: str) -> bool:
        return any(c[0] == name for c in self.calls)

    def count(self, name: str) -> int:
        return sum(1 for c in self.calls if c[0] == name)

    def last_result_of(self, name: str) -> dict | None:
        """The result of the most recent call to ``name`` (results run parallel to calls)."""
        for i in range(len(self.calls) - 1, -1, -1):
            if self.calls[i][0] == name and i < len(self.results):
                return self.results[i]
        return None

    def results_of(self, name: str) -> list[dict]:
        out = []
        for i, (call_name, _) in enumerate(self.calls):
            if call_name == name and i < len(self.results):
                out.append(self.results[i])
        return out

    def args_of(self, name: str) -> list[dict]:
        return [args for call_name, args in self.calls if call_name == name]


class DeterministicPlannerModel(Model):
    """Chooses the next tool from structured state. No network, no tokens, no cost."""

    provider_name = "offline"

    def __init__(self) -> None:
        self._config: dict[str, Any] = {"model_id": "offline-deterministic-planner"}

    # -- Model interface ---------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("the offline planner does not produce structured output")

    async def stream(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict]:
        view = TranscriptView(messages)
        events = self._decide(view)
        for event in events:
            yield event
        yield _metadata_event()

    # -- planning ----------------------------------------------------------

    def _decide(self, view: TranscriptView) -> list[dict]:
        intent = "recovery" if "recover" in view.user_text.lower() else "scan"
        if intent == "recovery":
            return self._plan_recovery(view)
        return self._plan_scan(view)

    def _plan_recovery(self, view: TranscriptView) -> list[dict]:
        # record_no_action is terminal. Without this the planner re-issues it forever;
        # the run-level bound caught exactly that during development, which is what the
        # bound is for — but a planner that needs the safety net every run is a bug.
        if view.called("record_no_action"):
            return _text_event("No pool needed attention.")

        if not view.called("list_pools_needing_attention"):
            return _tool_event("list_pools_needing_attention", {})

        listing = view.last_result_of("list_pools_needing_attention") or {}
        pools = listing.get("pools", [])
        attempted = {a.get("pool_id") for a in view.args_of("recover_pool")}
        for pool in pools:
            if pool.get("pool_id") not in attempted:
                return _tool_event("recover_pool", {"pool_id": pool["pool_id"]})

        if not pools:
            return _tool_event(
                "record_no_action", {"reason": "no pool is currently below its threshold"}
            )
        outcomes = view.results_of("recover_pool")
        recovered = sum(1 for o in outcomes if o.get("recovered"))
        return _text_event(
            f"Reviewed {len(pools)} pool(s) below threshold; {recovered} restored."
        )

    def _plan_scan(self, view: TranscriptView) -> list[dict]:
        # 0. record_no_action is terminal — say so and stop (see _plan_recovery).
        if view.called("record_no_action"):
            return _text_event("Nothing worth acting on this cycle.")

        # 1. Establish what demand exists that no pool is serving.
        if not view.called("list_unmet_demand"):
            return _tool_event("list_unmet_demand", {})

        demand = view.last_result_of("list_unmet_demand") or {}
        opportunities = demand.get("opportunities", [])

        evaluated = view.args_of("evaluate_opportunity")
        evaluated_products = {a.get("product_id") for a in evaluated}
        assessments = view.results_of("evaluate_opportunity")

        # 2. If the most recent assessment is viable, act on it.
        if assessments:
            latest = assessments[-1]
            if latest.get("viable") and not view.called("create_buying_pool"):
                return _tool_event(
                    "create_buying_pool",
                    {
                        "product_id": latest["product_id"],
                        "pickup_site_id": latest["pickup_site_id"],
                        "pickup_in_days": 14,
                    },
                )

        # 3. A pool was created — report and stop. One good pool per run keeps the
        #    run bounded and the neighbourhood un-spammed.
        if view.called("create_buying_pool"):
            created = view.last_result_of("create_buying_pool") or {}
            if created.get("created"):
                return _text_event(
                    f"Formed a buying pool for {created.get('product_name', 'a product')} "
                    f"with {created.get('member_count', 0)} households."
                )
            return _text_event("An equivalent pool already existed; no duplicate was created.")

        # 4. Otherwise investigate the next unexplored product.
        for opp in opportunities[:MAX_PRODUCTS_TO_INVESTIGATE]:
            if opp.get("product_id") in evaluated_products:
                continue
            return _tool_event(
                "evaluate_opportunity",
                {
                    "product_id": opp["product_id"],
                    "pickup_site_id": opp["suggested_pickup_site_id"],
                    "pickup_in_days": 14,
                },
            )

        # 5. Nothing worthwhile. Terminate cleanly without bothering anyone.
        reasons = [a.get("reason", "") for a in assessments if not a.get("viable")]
        return _tool_event(
            "record_no_action",
            {
                "reason": (
                    "; ".join(r for r in reasons if r)[:400]
                    or "no product had compatible demand worth pooling"
                )
            },
        )
