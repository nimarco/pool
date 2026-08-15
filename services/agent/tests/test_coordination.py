"""Pool lifecycle, human-in-the-loop, dropout recovery, and idempotency.

Agent systems retry. Every consequential operation here is called twice on purpose.
"""

from __future__ import annotations

import pytest

from pool.adapters.repository import InMemoryRepository
from pool.domain.models import (
    AutonomyMode,
    AutonomyPath,
    DecisionState,
    MembershipState,
    Offer,
    OfferKind,
    PickupSite,
    PoolStatus,
    Product,
)
from pool.services import coordination as coord

from .conftest import WS, make_household, make_need

SITE_LAT, SITE_LON = 38.6558, -90.3050


def build_world(repo: InMemoryRepository, *, public_site: bool = True) -> None:
    repo.put_product(WS, Product("p_rice", "Rice", "pantry", "lb", "rice"))
    repo.put_product(WS, Product("p_rice_alt", "Other rice", "pantry", "lb", "rice"))
    repo.put_offer(WS, Offer("o_retail", "Grocer", "p_rice", OfferKind.RETAIL, 100, 1, 1, None))
    repo.put_offer(WS, Offer("o_bulk", "Wholesale", "p_rice", OfferKind.BULK, 60, 25, 100, None))
    repo.put_site(WS, PickupSite("s_lib", "Library", SITE_LAT, SITE_LON, public_site, "library"))


def add(repo, hid, units, **hh_kw):
    """Add a household right next to the pickup site with one rice need."""
    kw = dict(lat=SITE_LAT + 0.002, lon=SITE_LON + 0.002)
    kw.update(hh_kw)
    need_kw = {k: kw.pop(k) for k in ("min_savings_pct", "max_spend", "accept_substitutes") if k in kw}
    repo.put_household(WS, make_household(hid, **kw))
    repo.put_need(WS, make_need(f"n_{hid}", hid, "p_rice", units, **need_kw))


def assess(repo, routing, **kw):
    params = dict(repo=repo, ws=WS, routing=routing, product_id="p_rice",
                  pickup_site_id="s_lib", pickup_in_days=10)
    params.update(kw)
    return coord.evaluate_opportunity(**params)


class TestEvaluate:
    def test_viable_opportunity(self, repo, routing):
        build_world(repo)
        for i, units in enumerate([40, 40, 30]):
            add(repo, f"h{i}", units)
        a = assess(repo, routing)
        assert a.viable is True
        assert a.pricing.total_units == 110
        assert a.pricing.threshold_met is True
        assert len(a.candidates) == 3

    def test_below_threshold_is_not_viable(self, repo, routing):
        build_world(repo)
        add(repo, "h0", 40)
        a = assess(repo, routing)
        assert a.viable is False
        assert "below every bulk minimum" in a.reason

    def test_no_demand_is_not_viable(self, repo, routing):
        build_world(repo)
        a = assess(repo, routing)
        assert a.viable is False
        assert "no compatible declared demand" in a.reason

    def test_bulk_that_does_not_beat_retail_is_rejected(self, repo, routing):
        """Correct behaviour when the 'deal' is not a deal: no pool, nobody bothered."""
        build_world(repo)
        repo.put_offer(WS, Offer("o_bulk", "W", "p_rice", OfferKind.BULK, 100, 25, 100, None))
        for i, u in enumerate([60, 60]):
            add(repo, f"h{i}", u)
        a = assess(repo, routing)
        assert a.viable is False
        assert "does not beat the retail baseline" in a.reason

    def test_best_bulk_tier_is_chosen(self, repo, routing):
        build_world(repo)
        repo.put_offer(WS, Offer("o_bulk_worse", "W", "p_rice", OfferKind.BULK, 85, 25, 50, None))
        for i, u in enumerate([60, 60]):
            add(repo, f"h{i}", u)
        a = assess(repo, routing)
        assert a.bulk_offer_id == "o_bulk"  # 60c beats 85c

    def test_unknown_product_raises(self, repo, routing):
        build_world(repo)
        with pytest.raises(coord.CoordinationError):
            assess(repo, routing, product_id="nope")


class TestCreatePool:
    def _viable(self, repo, routing):
        build_world(repo)
        add(repo, "auto1", 40)
        add(repo, "auto2", 40)
        add(repo, "asker", 30, mode=AutonomyMode.ASK_ME)
        return assess(repo, routing)

    def test_creates_pool_with_split_autonomy_paths(self, repo, routing):
        a = self._viable(repo, routing)
        pool, created = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1",
                                          idempotency_key="k1")
        assert created is True
        members = {m.household_id: m for m in repo.list_memberships(WS, pool.id)}
        assert members["auto1"].state == MembershipState.COMMITTED
        assert members["auto1"].path == AutonomyPath.SMART_JOIN
        assert members["asker"].state == MembershipState.INVITED
        assert members["asker"].path == AutonomyPath.PENDING_APPROVAL

    def test_ask_me_household_gets_a_decision_request(self, repo, routing):
        a = self._viable(repo, routing)
        coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k1")
        decisions = repo.list_decisions(WS)
        assert [d.household_id for d in decisions] == ["asker"]
        assert decisions[0].state == DecisionState.PENDING
        # The request carries the facts a human needs, and the policy audit trail.
        assert decisions[0].facts["cost_display"].startswith("$")
        assert any(c["rule"] == "autonomy_mode" for c in decisions[0].facts["policy_checks"])

    def test_create_is_idempotent(self, repo, routing):
        """A retried create must not produce a second pool."""
        a = self._viable(repo, routing)
        p1, c1 = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k1")
        p2, c2 = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k1")
        assert c1 is True and c2 is False
        assert p1.id == p2.id
        assert len(repo.list_pools(WS)) == 1

    def test_cannot_create_from_a_non_viable_assessment(self, repo, routing):
        build_world(repo)
        add(repo, "h0", 10)
        a = assess(repo, routing)
        with pytest.raises(coord.CoordinationError):
            coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r", idempotency_key="k")

    def test_private_site_blocks_auto_join_for_public_only_households(self, repo, routing):
        build_world(repo, public_site=False)
        add(repo, "h0", 60, public_only=True)
        add(repo, "h1", 60, public_only=True)
        a = assess(repo, routing)
        assert a.viable is True
        assert all(not c.verdict.eligible_for_auto_join for c in a.candidates)
        assert all("public_pickup" in c.verdict.failed_rules for c in a.candidates)


class TestHumanInTheLoop:
    def _pool_with_asker(self, repo, routing):
        build_world(repo)
        add(repo, "auto1", 40)
        add(repo, "auto2", 40)
        add(repo, "asker", 30, mode=AutonomyMode.ASK_ME)
        a = assess(repo, routing)
        pool, _ = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        return pool, repo.list_decisions(WS)[0]

    def test_approval_commits_the_household(self, repo, routing):
        pool, decision = self._pool_with_asker(repo, routing)
        coord.respond_to_decision(repo=repo, ws=WS, decision_id=decision.id, approve=True)
        m = repo.get_membership(WS, pool.id, "asker")
        assert m.state == MembershipState.COMMITTED
        assert m.path == AutonomyPath.HUMAN_APPROVED

    def test_rejection_declines_the_household(self, repo, routing):
        pool, decision = self._pool_with_asker(repo, routing)
        coord.respond_to_decision(repo=repo, ws=WS, decision_id=decision.id, approve=False)
        assert repo.get_membership(WS, pool.id, "asker").state == MembershipState.DECLINED

    def test_answering_twice_does_not_double_count(self, repo, routing):
        pool, decision = self._pool_with_asker(repo, routing)
        coord.respond_to_decision(repo=repo, ws=WS, decision_id=decision.id, approve=True)
        before = coord.committed_units(repo, WS, pool.id)
        # A retry, and then a contradictory second answer: both must be no-ops.
        coord.respond_to_decision(repo=repo, ws=WS, decision_id=decision.id, approve=True)
        coord.respond_to_decision(repo=repo, ws=WS, decision_id=decision.id, approve=False)
        assert coord.committed_units(repo, WS, pool.id) == before
        assert repo.get_membership(WS, pool.id, "asker").state == MembershipState.COMMITTED

    def test_unknown_decision_raises(self, repo):
        with pytest.raises(coord.CoordinationError):
            coord.respond_to_decision(repo=repo, ws=WS, decision_id="nope", approve=True)


class TestThresholdAndDropout:
    def _pool(self, repo, routing, units=(60, 60)):
        build_world(repo)
        for i, u in enumerate(units):
            add(repo, f"h{i}", u)
        a = assess(repo, routing)
        pool, _ = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        return repo.get_pool(WS, pool.id)

    def test_threshold_met_on_creation_when_all_auto_join(self, repo, routing):
        pool = self._pool(repo, routing)
        assert pool.status == PoolStatus.THRESHOLD_MET

    def test_withdrawal_below_threshold_moves_to_recovering(self, repo, routing):
        pool = self._pool(repo, routing)
        result = coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        assert result["below_threshold"] is True
        assert result["released_units"] == 60
        assert repo.get_pool(WS, pool.id).status == PoolStatus.RECOVERING

    def test_withdrawal_is_idempotent(self, repo, routing):
        pool = self._pool(repo, routing)
        coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        units_after = coord.committed_units(repo, WS, pool.id)
        again = coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        assert again["already_withdrawn"] is True
        assert coord.committed_units(repo, WS, pool.id) == units_after

    def test_withdrawal_that_keeps_threshold_does_not_downgrade(self, repo, routing):
        pool = self._pool(repo, routing, units=(60, 60, 60))
        coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        assert repo.get_pool(WS, pool.id).status == PoolStatus.THRESHOLD_MET

    def test_withdrawing_a_non_member_raises(self, repo, routing):
        pool = self._pool(repo, routing)
        with pytest.raises(coord.CoordinationError):
            coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="ghost")


class TestRecovery:
    def _broken_pool(self, repo, routing, replacement: dict | None = None):
        build_world(repo)
        add(repo, "h0", 60)
        add(repo, "h1", 60)
        if replacement is not None:
            # A household outside the 2 km formation radius but inside the 8 km
            # recovery radius: ~3.3 km north of the site.
            add(repo, "spare", replacement.pop("units", 60),
                lat=SITE_LAT + 0.030, lon=SITE_LON, **replacement)
        a = assess(repo, routing)
        pool, _ = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        return repo.get_pool(WS, pool.id)

    def test_formation_radius_excludes_the_spare(self, repo, routing):
        """The scenario only means anything if the spare was genuinely not in the pool."""
        pool = self._broken_pool(repo, routing, replacement={})
        assert repo.get_membership(WS, pool.id, "spare") is None

    def test_recovers_automatically_with_a_smart_join_replacement(self, repo, routing):
        pool = self._broken_pool(repo, routing, replacement={})
        result = coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        assert result.recovered is True
        assert result.added_household_ids == ["spare"]
        assert repo.get_pool(WS, pool.id).status == PoolStatus.THRESHOLD_MET
        assert repo.get_membership(WS, pool.id, "spare").path == AutonomyPath.SMART_JOIN

    def test_ask_me_replacement_is_invited_not_committed(self, repo, routing):
        pool = self._broken_pool(repo, routing, replacement={"mode": AutonomyMode.ASK_ME})
        result = coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        assert result.recovered is False
        assert result.invited_household_ids == ["spare"]
        assert repo.get_membership(WS, pool.id, "spare").state == MembershipState.INVITED
        assert any(d.facts.get("context") == "replacement_for_dropout"
                   for d in repo.list_decisions(WS))

    def test_no_replacement_available_fails_gracefully(self, repo, routing):
        pool = self._broken_pool(repo, routing, replacement=None)
        result = coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        assert result.recovered is False
        assert "no compatible replacement" in result.reason
        assert any(e.kind == "recovery_failed" for e in repo.list_activity(WS))

    def test_recovery_on_a_healthy_pool_is_a_noop(self, repo, routing):
        build_world(repo)
        add(repo, "h0", 60)
        add(repo, "h1", 60)
        a = assess(repo, routing)
        pool, _ = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        result = coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        assert result.recovered is True
        assert result.shortfall_units == 0
        assert result.added_household_ids == []

    def test_recovery_is_idempotent(self, repo, routing):
        """A retried recovery must not add the replacement twice."""
        pool = self._broken_pool(repo, routing, replacement={})
        coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        members_after_first = len(repo.list_memberships(WS, pool.id))
        coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r3")
        assert len(repo.list_memberships(WS, pool.id)) == members_after_first

    def test_existing_members_are_not_silently_repriced_worse(self, repo, routing):
        """Raising someone's share past their own cap is 'materially worse terms' and
        must become a question, not a silent edit."""
        build_world(repo)
        add(repo, "h0", 60)
        add(repo, "h1", 60, max_spend=1, min_savings_pct=0)  # cap makes any increase blocking
        add(repo, "spare", 60, lat=SITE_LAT + 0.030, lon=SITE_LON)
        a = assess(repo, routing)
        pool, _ = coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        original = repo.get_membership(WS, pool.id, "h1")
        original_cost = original.cost_cents
        coord.withdraw_household(repo=repo, ws=WS, pool_id=pool.id, household_id="h0")
        result = coord.recover_pool(repo=repo, ws=WS, routing=routing, pool_id=pool.id, run_id="r2")
        after = repo.get_membership(WS, pool.id, "h1")
        if after.cost_cents > original_cost:
            pytest.fail("existing member was silently repriced upward")
        assert "h1" in result.repriced_household_ids or after.cost_cents == original_cost


class TestImpactMetrics:
    def test_metrics_trace_to_stored_state(self, repo, routing):
        build_world(repo)
        add(repo, "h0", 60)
        add(repo, "h1", 60)
        a = assess(repo, routing)
        coord.create_pool(repo=repo, ws=WS, assessment=a, run_id="r1", idempotency_key="k")
        m = coord.impact_metrics(repo, WS)
        assert m["households_participating"] == 2
        assert m["collective_savings_cents"] == a.pricing.total_savings_cents
        assert m["commitments_without_asking"] == 2
        assert m["is_demo_data"] is True

    def test_empty_workspace_metrics_do_not_crash(self, repo):
        m = coord.impact_metrics(repo, WS)
        assert m["households_participating"] == 0
        assert m["collective_savings_cents"] == 0
