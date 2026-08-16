"""Compact agent-facing tool results (Q13).

Two things have to stay true at once, and these tests hold both ends:

1. **The model still sees every fact it needs.** A projection that saves tokens by
   dropping a blocking reason, an identifier, or a viability verdict would buy cost
   savings with wrong decisions.
2. **Nothing authoritative is lost.** The complete deterministic result is retained on
   the tool context, and every figure that survives into the projection is the *same*
   figure the service computed — never a re-derived one.

Everything here runs offline against the in-memory repository. No credentials, no
network, no tokens.
"""

from __future__ import annotations

import json

import pytest

from pool.adapters.payments import LocalSimulatedPaymentProvider
from pool.adapters.purchase import SimulatedPurchaseExecutor
from pool.adapters.repository import InMemoryRepository
from pool.adapters.sourcing import SyntheticCatalogProvider
from pool.agent import projection as proj
from pool.agent.coordinator import PoolCoordinator
from pool.agent.tools import ToolContext, build_tools
from pool.config import Settings
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import RunOutcome
from pool.domain.money import format_cents
from pool.services.context import PoolContext

WS = "projection"

#: What one tool result may weigh in the model's context. Strands resends the whole
#: conversation every turn, so a result is billed once per remaining turn — this is the
#: regression guard that keeps a future field from quietly restoring the 9 KB payload
#: that made the first real Bedrock run cost 35.7k input tokens for 418 output tokens.
AGENT_RESULT_BUDGET_BYTES = 1500


@pytest.fixture
def tool_ctx(seeded: InMemoryRepository, routing) -> ToolContext:
    return ToolContext(
        pool=PoolContext(
            repo=seeded,
            ws=WS,
            routing=routing,
            payments=LocalSimulatedPaymentProvider(),
            purchaser=SimulatedPurchaseExecutor(),
            sourcing=SyntheticCatalogProvider(),
            run_id="run_projection",
        ),
        community_id=COMMUNITY_ID,
    )


@pytest.fixture
def tools(tool_ctx: ToolContext) -> dict:
    return {t.tool_name: t for t in build_tools(tool_ctx)}


@pytest.fixture
def seeded(repo: InMemoryRepository) -> InMemoryRepository:
    seed(repo, WS)
    return repo


def _best_opportunity(tools) -> dict:
    demand = json.loads(tools["list_latent_demand"]())
    return demand["opportunities"][0]


def _evaluate(tools, opportunity) -> dict:
    return json.loads(
        tools["evaluate_pool_economics"](
            product_id=opportunity["product_id"],
            pickup_site_id=opportunity["suggested_pickup_site_id"],
        )
    )


# --------------------------------------------------------------- opportunity view


class TestOpportunityProjection:
    def test_keeps_the_identifiers_the_next_tool_call_needs(self, tools):
        opportunity = _best_opportunity(tools)
        view = _evaluate(tools, opportunity)
        # create_candidate_pool takes exactly these two arguments.
        assert view["product_id"] == opportunity["product_id"]
        assert view["pickup_site_id"] == opportunity["suggested_pickup_site_id"]

    def test_keeps_every_decision_critical_fact(self, tools):
        view = _evaluate(tools, _best_opportunity(tools))
        assert view["viable"] is True
        for key in (
            "member_count", "current_units", "future_units", "units",
            "landed_total", "retail_total", "savings_total", "savings_pct",
            "host_pay", "host_pay_is_estimated", "policy",
            "avg_travel_minutes", "max_travel_minutes", "distribution_day",
        ):
            assert key in view, f"projection dropped decision-critical field {key!r}"
        for key in (
            "total_units", "cases", "case_units", "moq_units", "moq_met",
            "surplus_units", "surplus_resolved",
        ):
            assert key in view["units"]

    def test_every_figure_is_the_authoritative_one(self, tools, tool_ctx):
        """No projected number is re-derived — each equals the service's own value."""
        view = _evaluate(tools, _best_opportunity(tools))
        full = tool_ctx.last_full_result("evaluate_pool_economics")
        assert full is not None
        econ = full["economics"]

        assert view["landed_total"] == format_cents(econ["all_in_cents"])
        assert view["retail_total"] == format_cents(econ["retail_baseline_cents"])
        assert view["savings_total"] == format_cents(econ["net_savings_cents"])
        assert view["savings_pct"] == full["estimated_savings_pct"]
        assert view["host_pay"] == format_cents(econ["host_compensation_cents"])
        assert view["units"]["total_units"] == econ["packages"]["total_units"]
        assert view["units"]["surplus_units"] == econ["packages"]["surplus_units"]
        assert view["member_count"] == len(full["candidates"])
        assert view["policy"]["auto_join_count"] == full["auto_join_count"]
        assert view["policy"]["approval_required_count"] == full["approval_required_count"]
        assert view["policy"]["excluded_count"] == full["rejected_count"]

    def test_buyer_policy_failures_survive_as_rules_and_counts(self):
        full = {
            "product_id": "p", "product_name": "P", "pickup_site_id": "s",
            "pickup_site_name": "S", "distribution_day": "2026-09-01", "viable": True,
            "reason": "", "current_units": 10, "future_units": 0,
            "avg_travel_minutes": 3, "max_travel_minutes": 9,
            "auto_join_count": 1, "approval_required_count": 2, "rejected_count": 4,
            "economics": {"packages": {}, "all_in_cents": 100, "net_savings_bps": 0},
            "candidates": [
                {"household_id": "a", "blocking_rule": None},
                {"household_id": "b", "blocking_rule": "max_total_cost"},
                {"household_id": "c", "blocking_rule": "max_total_cost"},
            ],
        }
        view = proj.opportunity_view(full)
        assert view["policy"]["blocking_rules"] == {"max_total_cost": 2}
        assert view["policy"]["approval_required_count"] == 2
        assert view["policy"]["excluded_count"] == 4

    def test_a_refusal_keeps_its_reason(self, tools):
        """The model must be able to say why it moved on, in the tool's own words."""
        views = [_evaluate(tools, o) for o in json.loads(
            tools["list_latent_demand"]())["opportunities"]]
        refusals = [v for v in views if not v["viable"]]
        assert refusals, "expected at least one non-viable product in the seed"
        for view in refusals:
            assert view["reason"]
            assert view["product_id"]

    def test_drops_the_per_household_roster(self, tools, tool_ctx):
        view = _evaluate(tools, _best_opportunity(tools))
        assert "candidates" not in view
        assert "lines" not in json.dumps(view)
        full = tool_ctx.last_full_result("evaluate_pool_economics")
        household_ids = {c["household_id"] for c in full["candidates"]}
        assert household_ids, "seed should produce candidates"
        text = json.dumps(view)
        # Not a byte-saving detail: no tool takes a household id, so ten of them per
        # turn was cost and an unnecessary widening of what reaches the model (§4).
        assert not any(hid in text for hid in household_ids)

    def test_is_materially_smaller_than_the_authoritative_result(self, tools, tool_ctx):
        view = _evaluate(tools, _best_opportunity(tools))
        full = tool_ctx.last_full_result("evaluate_pool_economics")
        assert len(json.dumps(view)) < 0.2 * len(json.dumps(full, default=str))


# --------------------------------------------------------------------- host view


class TestHostProjection:
    def test_keeps_the_offer_the_eligibility_and_the_pay(self, tools, tool_ctx):
        opportunity = _best_opportunity(tools)
        created = json.loads(
            tools["create_candidate_pool"](
                product_id=opportunity["product_id"],
                pickup_site_id=opportunity["suggested_pickup_site_id"],
            )
        )
        view = json.loads(tools["request_host_acceptance"](pool_id=created["pool_id"]))
        full = tool_ctx.last_full_result("request_host_acceptance")

        assert view["offered_household_id"] == full["offered_household_id"]
        assert view["eligible_count"] == full["eligible_count"]
        assert view["status"] == full["status"]
        assert view["candidates_considered"] == len(full["candidates"])
        offered = next(c for c in view["candidates"] if c["eligible"])
        source = next(c for c in full["candidates"] if c["household_id"] == offered["household_id"])
        assert offered["pay"] == format_cents(source["reward_cents"])

    def test_keeps_why_a_candidate_cannot_host(self, tools):
        opportunity = _best_opportunity(tools)
        created = json.loads(
            tools["create_candidate_pool"](
                product_id=opportunity["product_id"],
                pickup_site_id=opportunity["suggested_pickup_site_id"],
            )
        )
        view = json.loads(tools["find_host_candidates"](pool_id=created["pool_id"]))
        ineligible = [c for c in view["candidates"] if not c["eligible"]]
        assert ineligible, "the seed should include at least one ineligible host"
        assert all(c["ineligible_reasons"] for c in ineligible)

    def test_drops_score_components_and_reward_breakdown(self, tools):
        opportunity = _best_opportunity(tools)
        created = json.loads(
            tools["create_candidate_pool"](
                product_id=opportunity["product_id"],
                pickup_site_id=opportunity["suggested_pickup_site_id"],
            )
        )
        view = json.loads(tools["find_host_candidates"](pool_id=created["pool_id"]))
        text = json.dumps(view)
        for dropped in ("components", "capacity_headroom", "handoff_bonus_cents", "reward"):
            assert dropped not in text

    def test_caps_the_candidate_list_and_says_what_it_omitted(self):
        full = {
            "pool_id": "pool_x", "status": "offered", "reason": "",
            "offered_household_id": "hh_0", "eligible_count": 1,
            "candidates": [
                {"household_id": "hh_0", "eligible": True, "score": 10, "reward_cents": 4000}
            ]
            + [
                {
                    "household_id": f"hh_{i}",
                    "eligible": False,
                    "score": -i,
                    "reward_cents": 4000,
                    "ineligible_reasons": ["load needs a vehicle"],
                }
                for i in range(1, 9)
            ],
        }
        view = proj.host_evaluation_view(full)
        assert len(view["candidates"]) == proj.MAX_AGENT_HOST_CANDIDATES
        assert view["candidates_considered"] == 9
        assert view["candidates_omitted"] == 9 - proj.MAX_AGENT_HOST_CANDIDATES
        assert view["omitted_ineligible_reasons"] == ["load needs a vehicle"]
        # The best-ranked candidate is never the one dropped.
        assert view["candidates"][0]["household_id"] == "hh_0"
        assert view["candidates"][0]["rank"] == 1


# -------------------------------------------------------------- final offer view


class TestFinalOfferProjection:
    def test_counts_match_the_authoritative_lists(self):
        full = {
            "pool_id": "pool_x", "issued": True, "reason": "", "status": "funding",
            "surplus_units": 0,
            "auto_authorised": ["a", "b", "c"],
            "awaiting_decision": ["d", "e"],
            "removed": ["f"],
            "authorisation_failures": [],
            "economics": {
                "packages": {"total_units": 24, "cases": 2, "case_units": 12,
                             "moq_units": 24, "moq_met": True, "surplus_units": 0,
                             "surplus_resolved": True},
                "all_in_cents": 86245, "retail_baseline_cents": 112776,
                "net_savings_cents": 26531, "net_savings_bps": 2353,
                "host_compensation_cents": 4580, "host_is_estimated": False,
                "lines": [{"household_id": "a"}] * 10,
            },
        }
        view = proj.final_offer_view(full)
        assert view["auto_authorised_count"] == 3
        assert view["awaiting_decision_count"] == 2
        assert view["removed_count"] == 1
        assert view["authorisation_failure_count"] == 0
        assert view["landed_total"] == format_cents(86245)
        assert view["host_pay_is_estimated"] is False
        assert view["units"]["total_units"] == 24
        assert "lines" not in json.dumps(view)

    def test_a_refusal_keeps_its_reason(self):
        view = proj.final_offer_view(
            {"pool_id": "p", "issued": False, "reason": "no host has accepted this pool yet",
             "status": "host_recruiting"}
        )
        assert view["issued"] is False
        assert view["reason"] == "no host has accepted this pool yet"


# ------------------------------------------------------------ viability and lock


class TestViabilityProjection:
    FULL = {
        "stage": "final_lock",
        "viable": False,
        "failed": ["funding_threshold"],
        "blocking_reason": "funded units below threshold",
        "checks": [
            {"name": "supplier_minimum", "passed": True, "detail": "24 of 24 units"},
            {"name": "funding_threshold", "passed": False,
             "detail": "funded units below threshold"},
        ],
    }

    def test_keeps_the_verdict_and_what_failed(self):
        view = proj.viability_view(self.FULL)
        assert view["viable"] is False
        assert view["failed"] == ["funding_threshold"]
        assert view["blocking_reason"] == "funded units below threshold"
        assert "checks" not in view

    def test_lock_keeps_the_capture_outcome(self):
        view = proj.lock_view(
            {
                "pool_id": "pool_x", "locked": True, "status": "purchase_ready",
                "viability": {**self.FULL, "viable": True, "failed": []},
                "capture": {
                    "pool_id": "pool_x", "captured": ["a", "b"], "failed": [],
                    "captured_cents": 86245, "status": "purchase_ready",
                    "purchase_ready": True,
                },
            }
        )
        assert view["locked"] is True
        assert view["capture"]["captured_count"] == 2
        assert view["capture"]["failed_count"] == 0
        assert view["capture"]["captured_total"] == format_cents(86245)
        assert view["capture"]["purchase_ready"] is True
        assert "checks" not in json.dumps(view)


# ------------------------------------------------------------------ latent demand


class TestDemandProjection:
    def test_caps_the_list_and_reports_the_tail(self):
        opportunities = [
            {
                "product_id": f"p{i}", "product_name": f"Product {i}",
                "substitute_group": f"g{i}", "unserved_units": 30 - i,
                "member_count": 10 - i, "suggested_pickup_site_id": "s",
                "suggested_pickup_site_name": "Site",
            }
            for i in range(proj.MAX_AGENT_OPPORTUNITIES + 3)
        ]
        view = proj.demand_view(opportunities)
        assert len(view["opportunities"]) == proj.MAX_AGENT_OPPORTUNITIES
        assert view["count"] == len(opportunities)
        assert view["omitted_lower_ranked"] == 3
        # The ranking is deterministic, so the cut is always the tail.
        assert view["opportunities"][0]["product_id"] == "p0"

    def test_keeps_what_the_next_call_needs(self, tools):
        view = json.loads(tools["list_latent_demand"]())
        for opportunity in view["opportunities"]:
            assert opportunity["product_id"]
            assert opportunity["suggested_pickup_site_id"]
            assert "member_count" in opportunity
            assert "unserved_units" in opportunity


# ------------------------------------------------- authoritative results are kept


class TestAuthoritativeResultsAreRetained:
    def test_the_full_economics_are_kept_behind_the_projection(self, tools, tool_ctx):
        _evaluate(tools, _best_opportunity(tools))
        full = tool_ctx.last_full_result("evaluate_pool_economics")
        assert full is not None
        # Everything the projection dropped is still here, unchanged.
        assert full["candidates"] and all("household_id" in c for c in full["candidates"])
        assert full["economics"]["lines"]
        assert full["economics"]["host_reward"]["total_cents"]
        assert full["headline"]

    def test_a_run_leaves_its_full_results_reachable(self, seeded, routing):
        coordinator = PoolCoordinator(
            seeded, settings=Settings(), routing=routing
        )
        run = coordinator.run(WS, trigger="test", community_id=COMMUNITY_ID)
        assert run.outcome == RunOutcome.POOL_CREATED
        ctx = coordinator.last_tool_context
        assert ctx is not None
        recorded = [entry.tool for entry in ctx.full_results]
        assert recorded == [t.name for t in run.tool_calls if t.name in set(recorded)]
        economics = ctx.last_full_result("evaluate_pool_economics")
        assert economics["economics"]["lines"], "the authoritative detail must survive"
        assert economics["candidates"]

    def test_retention_is_bounded(self, tools, tool_ctx):
        from pool.agent.tools import MAX_RETAINED_FULL_RESULTS

        for _ in range(MAX_RETAINED_FULL_RESULTS + 5):
            tool_ctx.record_full("t", {}, {"x": 1})
        assert len(tool_ctx.full_results) == MAX_RETAINED_FULL_RESULTS


# --------------------------------------------------------------- context budget


class TestAgentContextBudget:
    def test_no_tool_result_exceeds_the_budget(self, seeded, routing, monkeypatch):
        """The whole canonical lifecycle, measured at the tool boundary.

        This is the Q13 regression guard: every result the model is shown, across
        discovery, hosting, final offer, recovery, lock, and purchase.
        """
        from pool.agent import bounds as bounds_module
        from pool.services import demo

        sizes: list[tuple[str, int]] = []
        original = bounds_module.BoundedRun.on_after_tool

        def record(self, event):
            name = str((event.tool_use or {}).get("name", "?"))
            for block in (event.result or {}).get("content") or []:
                if isinstance(block, dict) and "text" in block:
                    sizes.append((name, len(str(block["text"]))))
            return original(self, event)

        monkeypatch.setattr(bounds_module.BoundedRun, "on_after_tool", record)
        result = demo.run_showcase(seeded, WS, routing=routing)

        assert result.ok, result.failure
        assert sizes
        oversized = [(n, s) for n, s in sizes if s > AGENT_RESULT_BUDGET_BYTES]
        assert not oversized, f"tool results over budget: {oversized}"
