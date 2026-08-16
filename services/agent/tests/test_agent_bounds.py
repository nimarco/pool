"""Loop guards.

These are the tests that protect the AWS credits. Each one drives the real Strands
event loop with a model designed to misbehave, and asserts the run stops.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable

import pytest
from strands.models import Model

from pool.adapters.repository import InMemoryRepository
from pool.agent.bounds import BoundedRun, BoundExceeded, RunTelemetry, digest_arguments
from pool.agent.coordinator import PoolCoordinator
from pool.config import AgentBounds, Settings
from pool.data.seed import seed
from pool.domain.models import RunOutcome

WS = "test"


def _tool_call(name: str, payload: dict) -> list[dict]:
    tid = f"tooluse_{uuid.uuid4().hex[:12]}"
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tid, "name": name}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
    ]


class BrokenRecordModel(Model):
    """Always requests the same tool with the same arguments. Never stops."""

    provider_name = "test-broken-record"

    def __init__(self, name: str = "list_latent_demand", payload: dict | None = None):
        self.name = name
        self.payload = payload or {}
        self.turns = 0

    def get_config(self) -> dict:
        return {"model_id": "broken-record"}

    def update_config(self, **kw) -> None:
        pass

    async def structured_output(self, *a, **k):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw) -> AsyncIterable[dict]:
        self.turns += 1
        for event in _tool_call(self.name, self.payload):
            yield event
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                            "metrics": {"latencyMs": 1}}}


class VariedLoopModel(Model):
    """Calls the same tool but with different arguments each turn, so duplicate
    detection cannot catch it — only the iteration cap can."""

    provider_name = "test-varied-loop"

    def __init__(self):
        self.turns = 0

    def get_config(self) -> dict:
        return {"model_id": "varied-loop"}

    def update_config(self, **kw) -> None:
        pass

    async def structured_output(self, *a, **k):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw) -> AsyncIterable[dict]:
        self.turns += 1
        for event in _tool_call("evaluate_pool_economics", {
            "product_id": "prod_whey_vanilla",
            "pickup_site_id": "site_union",
            "include_future_demand": self.turns % 2 == 0,
        }):
            yield event
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                            "metrics": {"latencyMs": 1}}}


def coordinator(repo, model, **bound_kw) -> PoolCoordinator:
    bounds = AgentBounds(**{
        "max_iterations": 5, "max_tool_calls": 20, "max_tool_retries": 3,
        "max_duplicate_tool_calls": 2, "workflow_timeout_seconds": 60, **bound_kw,
    })
    settings = Settings(bounds=bounds, model_provider="offline", routing_provider="deterministic")
    return PoolCoordinator(repo, settings=settings, model=model)


@pytest.fixture
def world():
    repo = InMemoryRepository()
    seed(repo, WS)
    return repo


class TestIterationCap:
    def test_a_model_that_never_stops_is_stopped(self, world):
        model = VariedLoopModel()
        run = coordinator(world, model, max_iterations=4).run(WS, trigger="test")
        assert run.outcome == RunOutcome.LOOP_FAULT
        assert run.termination_reason == "bound:max_iterations"

    def test_the_cap_is_actually_the_configured_number(self, world):
        model = VariedLoopModel()
        run = coordinator(world, model, max_iterations=3).run(WS, trigger="test")
        assert run.iterations == 4  # the 4th call is the one that trips the bound
        assert model.turns == 3     # the model was never invoked a 4th time

    def test_the_fault_is_recorded_not_swallowed(self, world):
        """A bound must produce a loud, stored outcome — never a silent truncation
        that looks like a normal result."""
        run = coordinator(world, VariedLoopModel(), max_iterations=2).run(WS, trigger="test")
        stored = world.get_run(WS, run.id)
        assert stored is not None
        assert stored.outcome == RunOutcome.LOOP_FAULT
        assert stored.notes  # carries the detail of which bound and why
        assert any(e.kind == "agent_run" for e in world.list_activity(WS))


class TestDuplicateDetection:
    def test_identical_repeated_calls_are_cancelled(self, world):
        model = BrokenRecordModel()
        run = coordinator(world, model, max_duplicate_tool_calls=2, max_iterations=6).run(
            WS, trigger="test"
        )
        # It still ends via the iteration cap, but duplicates were cancelled on the way.
        assert run.outcome == RunOutcome.LOOP_FAULT
        failed = [t for t in run.tool_calls if not t.ok]
        assert failed, "repeated identical tool calls should have been cancelled"

    def test_argument_digest_is_stable_and_order_independent(self):
        assert digest_arguments({"a": 1, "b": 2}) == digest_arguments({"b": 2, "a": 1})

    def test_argument_digest_distinguishes_different_inputs(self):
        assert digest_arguments({"a": 1}) != digest_arguments({"a": 2})

    def test_digest_does_not_leak_the_arguments(self):
        """The run log is an artifact we may publish; it must not carry raw inputs."""
        d = digest_arguments({"household_id": "hh_okafor", "address": "12 Elm St"})
        assert "okafor" not in d and "Elm" not in d
        assert len(d) == 12


class TestToolBudget:
    def test_global_tool_budget_cancels_further_calls(self, world):
        model = VariedLoopModel()
        run = coordinator(world, model, max_tool_calls=3, max_iterations=20).run(WS, trigger="test")
        # Once the budget is spent every further call is cancelled, so the run cannot
        # keep spending regardless of what the model asks for.
        cancelled = [t for t in run.tool_calls if not t.ok]
        assert cancelled


class TestTelemetry:
    def test_usage_is_accumulated(self, world):
        run = coordinator(world, VariedLoopModel(), max_iterations=3).run(WS, trigger="test")
        assert run.input_tokens and run.input_tokens > 0
        assert run.output_tokens and run.output_tokens > 0

    def test_tool_calls_are_recorded_with_names(self, world):
        run = coordinator(world, VariedLoopModel(), max_iterations=3).run(WS, trigger="test")
        assert [t.name for t in run.tool_calls]
        assert all(t.name == "evaluate_pool_economics" for t in run.tool_calls)

    def test_no_reasoning_text_is_stored(self, world):
        """The run record is explainability, not chain-of-thought exposure."""
        run = coordinator(world, VariedLoopModel(), max_iterations=3).run(WS, trigger="test")
        blob = json.dumps(run.to_dict())
        assert "thinking" not in blob.lower()
        assert "reasoning" not in blob.lower()


class TestTimeout:
    def test_clock_bound_raises(self):
        bounded = BoundedRun(AgentBounds(workflow_timeout_seconds=0), RunTelemetry())
        with pytest.raises(BoundExceeded, match="workflow_timeout_seconds"):
            bounded._check_clock()


class TestErrorHandling:
    def test_a_model_that_throws_is_recorded_as_an_error(self, world):
        class ExplodingModel(Model):
            provider_name = "test-exploding"

            def get_config(self):
                return {"model_id": "exploding"}

            def update_config(self, **kw):
                pass

            async def structured_output(self, *a, **k):
                raise NotImplementedError

            async def stream(self, *a, **k):
                raise RuntimeError("model unavailable")
                yield  # pragma: no cover

        run = coordinator(world, ExplodingModel()).run(WS, trigger="test")
        assert run.outcome == RunOutcome.ERROR
        assert run.termination_reason == "error"
        assert any("model unavailable" in n for n in run.notes)
