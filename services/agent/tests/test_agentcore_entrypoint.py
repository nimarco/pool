"""What the hosted AgentCore runtime tells the outside world about a run.

The runtime returns one JSON object per invocation and stores nothing durable — with
`POOL_REPOSITORY=memory` the run record dies with the microVM. So that object is the
only evidence a caller gets, and the question these tests answer is narrow: can someone
reading the response tell the difference between a tool that did work and a tool that
deterministic code refused?

That distinction is the whole point of the Q16 follow-up (BUILD_HISTORY #0021). A real
Bedrock run opened a turn with `recover_pool(pool_id="short_of_demand_pool")` — an
identifier the model invented. The guard refused it before touching state, and
`tests/test_recovery_lifecycle.py` already proves nothing moved. What was missing is
that the *response* said only "recover_pool was called", which reads identically to a
successful repair. After deployment that would make the safety property unobservable.

Runs entirely offline and free — deterministic planner, simulated payments, in-memory
store. No credentials, no AWS call, no token spend (AGENTS.md §3.6).
"""

from __future__ import annotations

import pytest

from agentcore_app import tool_call_view
from pool.adapters.repository import InMemoryRepository
from pool.agent.coordinator import PoolCoordinator
from pool.agent.offline_model import DeterministicPlannerModel, _tool_event
from pool.config import AgentBounds, Settings
from pool.data.seed import COMMUNITY_ID
from pool.domain.models import RunOutcome, ToolCallRecord
from pool.scripts.recovery_scenario import RECOVERY_INSTRUCTION, build_pre_recovery_state

WS = "agentcore_entrypoint"

#: The complete contract for one reported tool call. Asserted as an exact set, so
#: widening it later is a deliberate act rather than an accident — this dict crosses the
#: runtime boundary and lands in CloudWatch.
TOOL_CALL_KEYS = {"name", "ok", "summary"}


@pytest.fixture
def settings() -> Settings:
    """Explicit offline settings, so no stray environment variable can steer this file
    at a paid model."""
    return Settings(
        model_provider="offline",
        repository="memory",
        routing_provider="deterministic",
        payment_provider="simulated",
        purchase_executor="simulated",
        bounds=AgentBounds(),
    )


@pytest.fixture
def scenario(settings):
    """The #0021 pre-recovery situation: 2 units lost, 4 units merely unanswered."""
    repo = InMemoryRepository()
    coordinator = PoolCoordinator(repo, settings=settings)
    _ctx, pool, _final = build_pre_recovery_state(coordinator, repo, WS)
    return repo, pool


class HallucinatingPlanner(DeterministicPlannerModel):
    """The planner, but it opens with the invented identifier the real model used.

    Mirrors the class in ``tests/test_recovery_lifecycle.py``: the same observed
    behaviour, asserted here against the response shape rather than against stored state.
    """

    def _decide(self, view):
        if not view.calls:
            return _tool_event("recover_pool", {"pool_id": "short_of_demand_pool"})
        return super()._decide(view)


def _run(coordinator):
    return coordinator.run(
        WS,
        trigger="recovery_test",
        community_id=COMMUNITY_ID,
        instruction=RECOVERY_INSTRUCTION,
    )


# ------------------------------------------------------------------ the projection


def test_a_tool_call_view_carries_name_ok_and_summary_and_nothing_else():
    """The digest and timestamp stay out: one is a hash a reader cannot use, the other
    duplicates the run's own timing."""
    view = tool_call_view(
        ToolCallRecord(name="lock_pool", arguments_digest="a1b2c3", ok=False, summary="not viable")
    )
    assert view == {"name": "lock_pool", "ok": False, "summary": "not viable"}
    assert set(view) == TOOL_CALL_KEYS


def test_the_view_matches_the_api_run_detail_shape():
    """The hosted runtime and the local API must describe a run the same way, or the
    demo and the deployed system disagree about what happened."""
    record = ToolCallRecord(name="inspect_pool", arguments_digest="d4", ok=True, summary="ok")
    api_shape = {"name": record.name, "ok": record.ok, "summary": record.summary}
    assert tool_call_view(record) == api_shape


# ------------------------------------------------------------------ accepted work


def test_a_clean_run_reports_every_tool_call_as_ok(settings, scenario):
    repo, _pool = scenario
    run = _run(PoolCoordinator(repo, settings=settings))
    views = [tool_call_view(t) for t in run.tool_calls]

    assert views, "the scenario is supposed to exercise tools"
    assert all(set(v) == TOOL_CALL_KEYS for v in views)
    assert all(v["ok"] is True for v in views), [v for v in views if not v["ok"]]
    assert all(isinstance(v["summary"], str) and v["summary"] for v in views)
    assert run.outcome == RunOutcome.POOL_RECOVERED
    assert run.termination_reason == "completed"


# ------------------------------------------------------------------ refused work


def test_an_invented_consequential_identifier_is_reported_as_a_refusal(settings, scenario):
    """The Q16 property, stated as an assertion about what a deployed run reports.

    Not "recover_pool was called" — that is true in both the good and the bad case. The
    response has to carry `ok=False` and a summary naming the reason, or the refusal is
    invisible from outside the runtime.
    """
    repo, _pool = scenario
    run = _run(PoolCoordinator(repo, settings=settings, model=HallucinatingPlanner()))
    views = [tool_call_view(t) for t in run.tool_calls]

    refused = [v for v in views if not v["ok"]]
    assert len(refused) == 1, views
    assert refused[0]["name"] == "recover_pool"
    assert "unknown pool" in refused[0]["summary"]

    # The same tool name also appears as accepted work later in the run, which is
    # exactly why the name alone cannot carry this signal.
    accepted_recoveries = [v for v in views if v["name"] == "recover_pool" and v["ok"]]
    assert accepted_recoveries, "the run should still repair the real pool"


def test_the_refusal_does_not_corrupt_the_overall_run_result(settings, scenario):
    """Surfacing the refusal must not change what the coordinator decided. The run still
    repairs the real pool and terminates normally — only the reporting is richer."""
    repo, _pool = scenario
    run = _run(PoolCoordinator(repo, settings=settings, model=HallucinatingPlanner()))

    assert run.outcome == RunOutcome.POOL_RECOVERED
    assert run.termination_reason == "completed"
    assert run.iterations <= settings.bounds.max_iterations
    assert len(run.tool_calls) <= settings.bounds.max_tool_calls


def test_a_refused_call_still_counts_against_the_tool_budget(settings, scenario):
    """A refusal is a call that happened. Reporting it as one keeps the bound honest —
    an invented identifier must not buy the model a free retry (AGENTS.md §3.1)."""
    repo, _pool = scenario
    clean = _run(PoolCoordinator(repo, settings=settings))

    repo2 = InMemoryRepository()
    coordinator2 = PoolCoordinator(repo2, settings=settings)
    build_pre_recovery_state(coordinator2, repo2, WS)
    hallucinating = _run(
        PoolCoordinator(repo2, settings=settings, model=HallucinatingPlanner())
    )

    assert len(hallucinating.tool_calls) == len(clean.tool_calls) + 1


# ------------------------------------------------------------------ the real response


def test_the_entrypoint_response_carries_the_expanded_tool_calls():
    """End to end through the actual entrypoint, not just the projection helper.

    `agentcore_app` builds its coordinator at import time from the environment; the
    defaults are the offline planner and the in-memory store, so this costs nothing and
    needs no credentials.
    """
    from agentcore_app import invoke

    body = invoke({"trigger": "manual", "workspace": "entrypoint_response"})

    assert set(body) == {
        "run_id", "workspace", "outcome", "iterations", "tool_calls",
        "termination_reason", "model_provider", "model_id", "duration_ms",
        "input_tokens", "output_tokens", "hitl_decisions_created",
    }
    assert body["tool_calls"], "the seeded workspace should give the agent work to do"
    for call in body["tool_calls"]:
        assert set(call) == TOOL_CALL_KEYS
        assert isinstance(call["name"], str) and call["name"]
        assert isinstance(call["ok"], bool)
        assert isinstance(call["summary"], str)


def test_a_rejected_payload_still_returns_an_error_not_a_run():
    """Payload validation is unchanged by the reporting work."""
    from agentcore_app import invoke

    assert "error" in invoke({"trigger": "drop_everything"})
    assert "error" in invoke({"workspace": "../../etc"})


# ------------------------------------------------------------------ no leakage


def test_no_summary_carries_a_credential_or_contact_detail(settings, scenario):
    """Summaries cross into CloudWatch, so they are held to the same bar as any other
    log line: identifiers yes, personal contact details and secrets no
    (AGENTS.md §4, §9)."""
    repo, _pool = scenario
    run = _run(PoolCoordinator(repo, settings=settings, model=HallucinatingPlanner()))

    blob = " ".join(tool_call_view(t)["summary"] for t in run.tool_calls)
    for forbidden in ("sk_test_", "sk_live_", "whsec_", "AKIA", "ASIA", "@", "Bearer "):
        assert forbidden not in blob, f"{forbidden!r} reached a tool-call summary"
