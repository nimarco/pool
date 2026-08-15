"""End-to-end proof of the showcase.

One command has to demonstrate that the central claim is real: Pool discovers latent
overlap, forms a group, asks only where it must, and repairs itself after a dropout.
If any of that stops being true, this test fails rather than the demo quietly lying.
"""

from __future__ import annotations

from pool.adapters.repository import InMemoryRepository
from pool.domain.models import (
    AutonomyPath,
    MembershipState,
    PoolStatus,
    RunOutcome,
)
from pool.services import coordination as coord
from pool.services.demo import run_showcase

WS = "demo"


def steps_by_name(result) -> dict:
    return {s.name: s for s in result.steps}


class TestShowcase:
    def test_the_whole_scenario_succeeds(self, repo: InMemoryRepository):
        result = run_showcase(repo, WS)
        assert result.ok, result.failure

    def test_agent_discovered_the_opportunity_itself(self, repo):
        """Nobody told the agent which product to look at."""
        s = steps_by_name(run_showcase(repo, WS))["background_scan"]
        assert s.facts["outcome"] == RunOutcome.POOL_CREATED.value
        assert s.facts["tools_called"][0] == "list_unmet_demand"
        assert "evaluate_opportunity" in s.facts["tools_called"]
        assert "create_buying_pool" in s.facts["tools_called"]

    def test_run_is_bounded(self, repo):
        s = steps_by_name(run_showcase(repo, WS))["background_scan"]
        assert 0 < s.facts["iterations"] <= 8

    def test_a_real_group_formed_with_meaningful_savings(self, repo):
        s = steps_by_name(run_showcase(repo, WS))["pool_formed"]
        assert s.facts["households"] >= 8
        assert s.facts["committed_units"] > 0
        # The savings figure is whatever the arithmetic produced; assert only that it
        # is a genuinely worthwhile deal rather than pinning a marketing number.
        pct = float(s.facts["savings_pct"].rstrip("%"))
        assert pct >= 25.0

    def test_both_autonomy_paths_are_exercised(self, repo):
        """Smart Join households join silently; Ask Me households are asked."""
        s = steps_by_name(run_showcase(repo, WS))["pool_formed"]
        assert s.facts["auto_joined_via_smart_join"] > 0
        assert s.facts["approval_requested"] > 0

    def test_threshold_reached_only_after_human_approvals(self, repo):
        result = run_showcase(repo, WS)
        formed = steps_by_name(result)["pool_formed"]
        approvals = steps_by_name(result)["approvals"]
        assert formed.facts["committed_units"] < formed.facts["threshold_units"]
        assert approvals.facts["committed_units"] >= approvals.facts["threshold_units"]
        assert approvals.facts["status"] == PoolStatus.THRESHOLD_MET.value

    def test_dropout_genuinely_breaks_the_pool(self, repo):
        s = steps_by_name(run_showcase(repo, WS))["dropout"]
        assert s.facts["below_threshold"] is True
        assert s.facts["committed_units"] < s.facts["threshold_units"]
        assert s.facts["status"] == PoolStatus.RECOVERING.value

    def test_recovery_is_performed_by_a_real_agent_run(self, repo):
        s = steps_by_name(run_showcase(repo, WS))["recovery"]
        assert s.facts["outcome"] == RunOutcome.POOL_RECOVERED.value
        assert s.facts["tools_called"] == ["list_pools_needing_attention", "recover_pool"]

    def test_recovery_restores_the_threshold(self, repo):
        s = steps_by_name(run_showcase(repo, WS))["recovery"]
        assert s.facts["committed_units"] >= s.facts["threshold_units"]
        assert s.facts["status"] == PoolStatus.THRESHOLD_MET.value
        assert s.facts["replacements"], "a replacement household should have been found"

    def test_recovery_does_not_disturb_existing_members(self, repo):
        """The headline claim is 'no action required' for everyone else."""
        result = run_showcase(repo, WS)
        pool = repo.list_pools(WS)[0]
        replacements = set(steps_by_name(result)["recovery"].facts["replacements"])
        for m in repo.list_memberships(WS, pool.id):
            if m.household_id in replacements:
                continue
            assert m.state != MembershipState.INVITED, (
                f"{m.household_id} was re-asked during recovery"
            )

    def test_replacement_joined_under_its_own_smart_join_policy(self, repo):
        result = run_showcase(repo, WS)
        pool = repo.list_pools(WS)[0]
        for hid in steps_by_name(result)["recovery"].facts["replacements"]:
            m = repo.get_membership(WS, pool.id, hid)
            assert m.state == MembershipState.COMMITTED
            assert m.path == AutonomyPath.SMART_JOIN

    def test_impact_metrics_trace_to_stored_state(self, repo):
        result = run_showcase(repo, WS)
        reported = steps_by_name(result)["impact"].facts
        recomputed = coord.impact_metrics(repo, WS)
        assert reported["collective_savings_cents"] == recomputed["collective_savings_cents"]
        assert reported["pools_recovered"] == 1
        assert reported["commitments_without_asking"] > 0
        assert reported["is_demo_data"] is True

    def test_activity_feed_tells_the_story(self, repo):
        run_showcase(repo, WS)
        kinds = [e.kind for e in repo.list_activity(WS, limit=100)]
        for expected in ("pool_created", "threshold_met", "participant_withdrew", "pool_recovered"):
            assert expected in kinds, f"missing activity event: {expected}"

    def test_no_model_tokens_were_spent_offline(self, repo):
        """The whole scenario must be runnable for free, or it will not get run."""
        run_showcase(repo, WS)
        for run in repo.list_runs(WS):
            assert run.model_provider == "offline"
            assert (run.input_tokens or 0) == 0
            assert (run.output_tokens or 0) == 0

    def test_scenario_is_repeatable(self, repo):
        """A judge must be able to reset and re-run and see the same thing."""
        first = run_showcase(repo, WS)
        second = run_showcase(repo, WS)  # reseeds
        assert first.ok and second.ok
        f = steps_by_name(first)["pool_formed"].facts
        s = steps_by_name(second)["pool_formed"].facts
        assert f["households"] == s["households"]
        assert f["savings_pct"] == s["savings_pct"]
        assert f["threshold_units"] == s["threshold_units"]

    def test_isolated_workspaces_do_not_interfere(self, repo):
        a = run_showcase(repo, "judge_a")
        b = run_showcase(repo, "judge_b")
        assert a.ok and b.ok
        assert len(repo.list_pools("judge_a")) == 1
        assert len(repo.list_pools("judge_b")) == 1
