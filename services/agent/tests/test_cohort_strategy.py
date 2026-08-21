"""Several defensible orders, and the deterministic evidence that separates them.

The whey scenario proves Pool can answer *is this worth doing*. It cannot prove anything
about *which of these is worth doing*, because when everybody buys the same tub there is
only one candidate and the question does not arise. Heterogeneous demand is the case
where it does: twelve households buy coffee, they authorised six different kinds of
substitution, and there are several real orders Pool could assemble from them.

The claim this module tests is that the search space is real. Concretely:

* **generation invents nothing** — every SKU comes from the product table, every member
  from a declaration they wrote, every attribute from a committed curated fact, and every
  supplier minimum from a stored offer;
* **the two stages genuinely know different things** — a summary carries who could join,
  and evaluation carries what the group costs, because the second is not computable from
  the first;
* **and the difference is load-bearing** — the option with the largest cohort and the
  most comfortable margin over its supplier minimum is the one that turns out not to be
  cheaper, which is a fact nothing in the listing could have contained.

That last property is the one worth stating plainly, because it is the difference between
a search and a formality. If a summary already implied the answer, a later model choosing
from those summaries would be decorative — so the strongest test here is
:func:`test_the_listing_cannot_tell_the_refused_option_from_the_viable_one`.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from pool.adapters.repository import DynamoDBRepository, InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.data import product_facts as pf
from pool.data.roast_coffee_fixture import (
    A_LIGHT,
    A_MEDIUM,
    ANCHOR_HOUSEHOLD,
    ANCHOR_NEED,
    B_DARK,
    C_DECAF,
    D_GROUND,
    E_UNVERIFIED_ROAST,
    install_roast_coffee,
)
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import (
    AutonomyMode,
    CohortStrategy,
    StrategyEvaluation,
    SubstitutionPolicy,
    iso,
    utcnow,
)
from pool.services import coordination as coord
from pool.services import discovery
from pool.services import strategy as st
from pool.services.context import PoolContext

from .conftest import WS
from .test_public_demo import FakeDynamoTable

WHOLE_BEAN_STRATEGIES = (A_MEDIUM, B_DARK)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def coffee_ctx() -> PoolContext:
    """A seeded Community with the heterogeneous coffee fixture installed on top.

    The seed stays: its schedule, radius, public sites and fee configuration are inputs
    to every number below, and a coffee community that invented its own copy of them
    would be measuring a different world from the one the product runs in. It also means
    a Community-wide scan here has more than six things to choose between, which is what
    makes the strategy cap testable against a real world rather than a contrived one.
    """
    repo = InMemoryRepository()
    seed(repo, WS)
    install_roast_coffee(repo, WS)
    return PoolContext(
        repo=repo, ws=WS, routing=CachingRouting(DeterministicRouting(max_cells=400))
    )


def member_objective(household_id: str = ANCHOR_HOUSEHOLD, need_id: str = ANCHOR_NEED):
    return st.StrategyObjective(
        kind=st.OBJECTIVE_MEMBER,
        community_id=COMMUNITY_ID,
        household_id=household_id,
        need_id=need_id,
    )


def community_objective():
    return st.StrategyObjective(kind=st.OBJECTIVE_COMMUNITY, community_id=COMMUNITY_ID)


def by_product(strategies: list[CohortStrategy]) -> dict[str, CohortStrategy]:
    return {s.target_product_id: s for s in strategies}


def evaluate_all(ctx: PoolContext, strategies: list[CohortStrategy]):
    return {s.target_product_id: st.evaluate_strategy(ctx=ctx, strategy_id=s.id) for s in strategies}


# ------------------------------------------------------------------------ determinism


def test_the_same_world_produces_the_same_strategies_in_the_same_order(coffee_ctx):
    first = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    second = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    assert [s.id for s in first] == [s.id for s in second]
    assert [s.target_product_id for s in first] == [s.target_product_id for s in second]
    assert [s.input_fingerprint for s in first] == [s.input_fingerprint for s in second]
    assert [s.compatible_units for s in first] == [s.compatible_units for s in second]


def test_strategy_ids_survive_a_separate_process_and_a_separate_repository():
    """Stable because they are digests of what the strategy *is*, not of when it was made.

    Two independently built worlds, no shared objects. A random id would pass every test
    above this one and fail this one, which is the point: an id Phase 3 stores has to
    still mean something after a restart.
    """
    ids = []
    for _ in range(2):
        repo = InMemoryRepository()
        seed(repo, WS)
        install_roast_coffee(repo, WS)
        ctx = PoolContext(
            repo=repo, ws=WS, routing=CachingRouting(DeterministicRouting(max_cells=400))
        )
        ids.append([s.id for s in st.generate_strategies(ctx=ctx, objective=member_objective())])
    assert ids[0] == ids[1]
    assert all(i.startswith("strat_") for i in ids[0])


def test_no_two_strategies_describe_the_same_order(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=community_objective())
    assert len({s.id for s in strategies}) == len(strategies)
    # One SKU at one site is one order however many ways you arrive at it.
    assert len({(s.target_product_id, s.pickup_site_id) for s in strategies}) == len(strategies)


def test_the_search_space_is_capped_and_the_cut_is_recorded(coffee_ctx):
    """Eleven candidates, six options, and a log line saying so.

    A listing that silently drops options reads as "these are all the options", which is
    a different and false claim (AGENTS.md §8).
    """
    candidates = st._candidate_targets(coffee_ctx, community_objective())
    assert len(candidates) > st.MAX_COHORT_STRATEGIES

    strategies = st.generate_strategies(ctx=coffee_ctx, objective=community_objective())
    assert len(strategies) == st.MAX_COHORT_STRATEGIES

    logged = [e for e in coffee_ctx.repo.list_activity(WS) if e.kind == "strategies_generated"]
    assert logged, "a truncated search must say it was truncated"
    assert logged[0].facts["kept"] == st.MAX_COHORT_STRATEGIES
    assert logged[0].facts["dropped"] > 0

    # The cap is a ceiling, not a default a caller can raise.
    assert len(
        st.generate_strategies(
            ctx=coffee_ctx, objective=community_objective(), limit=99, persist=False
        )
    ) == st.MAX_COHORT_STRATEGIES


def test_every_exclusion_code_the_generator_emits_is_a_declared_one(coffee_ctx):
    """The vocabulary is a closed set, so a histogram can be grouped rather than parsed.

    Compatibility refusals arrive already coded from ``domain.substitution``; the rest are
    this module's own, and a new one appearing without being declared would be a token
    nothing downstream knows how to count.
    """
    from pool.domain.substitution import CompatibilityReason

    known = st.GENERATOR_EXCLUSION_CODES | {r.value for r in CompatibilityReason}
    seen: set[str] = set()
    for strategy in st.generate_strategies(ctx=coffee_ctx, objective=community_objective()):
        seen |= set(strategy.exclusion_codes)
    for household, need in (("hh_rc_varga", "need_rc_varga"), (ANCHOR_HOUSEHOLD, ANCHOR_NEED)):
        for strategy in st.generate_strategies(
            ctx=coffee_ctx, objective=member_objective(household, need)
        ):
            seen |= set(strategy.exclusion_codes)
    assert seen, "the fixture should refuse somebody somewhere"
    assert seen <= known, seen - known


def test_ranking_is_by_envelope_and_is_not_a_verdict(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=community_objective())
    units = [s.compatible_units for s in strategies]
    assert units == sorted(units, reverse=True)


# ------------------------------------------------------------- compatibility is honoured


def test_the_anchor_only_sees_options_their_own_rule_permits(coffee_ctx):
    """Whole bean, caffeinated, medium or dark — so two SKUs, and not the other four.

    Light roast, decaf, ground and the bag whose roast nobody verified are all absent,
    and each for its own reason. A member-anchored search may not offer an option that
    member never authorised, whatever it would do for the neighbours.
    """
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    assert [s.target_product_id for s in strategies] == list(WHOLE_BEAN_STRATEGIES)


def test_a_wider_rule_produces_a_wider_search_space(coffee_ctx):
    """The same fixture, anchored on the member who stated no roast requirement.

    Four options instead of two, and the two extra ones are exactly the SKUs the first
    member's roast requirement refused. The search space is a function of stated consent
    and of nothing else.
    """
    strategies = st.generate_strategies(
        ctx=coffee_ctx, objective=member_objective("hh_rc_varga", "need_rc_varga")
    )
    assert set(s.target_product_id for s in strategies) == {
        A_MEDIUM, B_DARK, A_LIGHT, E_UNVERIFIED_ROAST,
    }


@pytest.mark.parametrize(
    ("target", "expected_needs"),
    [
        # Constrained members, both exact-only members who named it, and the allowlist
        # member who listed it — plus the member with no roast requirement.
        (A_MEDIUM, {
            "need_rc_anchor", "need_rc_okonjo", "need_rc_lindholm", "need_rc_varga",
            "need_rc_ashworth", "need_rc_holt", "need_rc_delgado",
        }),
        (B_DARK, {
            "need_rc_anchor", "need_rc_okonjo", "need_rc_lindholm", "need_rc_varga",
            "need_rc_baptiste", "need_rc_delgado",
        }),
        # Light roast: the three medium-or-dark members are refused; the member with no
        # roast requirement, the member who named it, and the allowlist member who
        # declared it are not.
        (A_LIGHT, {"need_rc_varga", "need_rc_castellan", "need_rc_delgado"}),
        # Decaf and ground are different products, not near misses.
        (C_DECAF, {"need_rc_engstrom"}),
        (D_GROUND, {"need_rc_fairbairn", "need_rc_gallardo"}),
        # A bag whose roast nobody verified serves only the member whose rule never
        # made roast load-bearing (§21).
        (E_UNVERIFIED_ROAST, {"need_rc_varga"}),
    ],
)
def test_each_sku_admits_exactly_the_declarations_that_authorised_it(
    coffee_ctx, target, expected_needs
):
    # Built directly rather than read off a listing: the Community ranking caps at six,
    # and the small cohorts this asserts about are exactly the ones it cuts.
    product = coffee_ctx.repo.get_product(WS, target)
    community = coffee_ctx.community(COMMUNITY_ID)
    from pool.domain.timing import next_pool_day

    envelope = st._envelope(
        coffee_ctx,
        community_id=COMMUNITY_ID,
        target=product,
        purchase_date=next_pool_day(coffee_ctx.now.date(), community.schedule),
        include_future_demand=True,
        already_pooled=frozenset(),
    )
    assert {n.id for n in envelope.needs} == expected_needs


def test_decaf_and_ground_are_refused_on_the_fact_that_makes_them_different(coffee_ctx):
    strategies = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )
    codes = strategies[A_MEDIUM].exclusion_codes
    # Two members buying something else — one decaf, one ground — and both refused on a
    # curated attribute rather than on anybody's judgement about similarity.
    assert codes["required_attribute_mismatch"] == 2
    # And three exact-only members who named other bags.
    assert codes["exact_product_required"] == 3


def test_an_unverified_fact_fails_closed_in_the_search_too(coffee_ctx):
    """Phase 1's rule, still true one layer up. The three members who require a roast
    range cannot be offered a bag whose roast nobody confirmed."""
    product = coffee_ctx.repo.get_product(WS, E_UNVERIFIED_ROAST)
    community = coffee_ctx.community(COMMUNITY_ID)
    from pool.domain.timing import next_pool_day

    envelope = st._envelope(
        coffee_ctx, community_id=COMMUNITY_ID, target=product,
        purchase_date=next_pool_day(coffee_ctx.now.date(), community.schedule),
        include_future_demand=True, already_pooled=frozenset(),
    )
    assert envelope.exclusions["attribute_unverified"] == 3


def test_a_soft_preference_never_changes_who_is_in_the_envelope(coffee_ctx):
    """The member with a stated liking for medium is in every option their hard rule
    allows, including the dark and light ones."""
    need = coffee_ctx.repo.get_need(WS, "need_rc_varga")
    assert need.attribute_policy.prefers["roast"] == (pf.ROAST_MEDIUM,)
    strategies = st.generate_strategies(
        ctx=coffee_ctx, objective=member_objective("hh_rc_varga", "need_rc_varga")
    )
    for strategy in strategies:
        assert "need_rc_varga" in strategy.candidate_need_ids, strategy.target_product_id


def test_an_allowlist_is_not_widened_by_the_search(coffee_ctx):
    """The flexible member listed two bags. The search offers them those two and the one
    they declared, and never a fourth — the model may not add to a list a person wrote."""
    need = coffee_ctx.repo.get_need(WS, "need_rc_delgado")
    assert need.substitution is SubstitutionPolicy.APPROVED_PRODUCTS
    strategies = st.generate_strategies(
        ctx=coffee_ctx, objective=member_objective("hh_rc_delgado", "need_rc_delgado")
    )
    assert {s.target_product_id for s in strategies} <= {A_MEDIUM, B_DARK, A_LIGHT}


def test_demand_from_another_community_is_never_counted_at_all(coffee_ctx):
    """Not as a candidate and not as an exclusion. A neighbouring Community's demand is
    not a fact about this option, and reporting its size would leak that it exists (§9)."""
    outsider = coffee_ctx.repo.get_need(WS, "need_rc_okonjo")
    outsider.community_id = "comm_elsewhere"
    coffee_ctx.repo.put_need(WS, outsider)

    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[A_MEDIUM]
    assert "need_rc_okonjo" not in strategy.candidate_need_ids
    assert strategy.compatible_declaration_count == 6
    assert sum(strategy.exclusion_codes.values()) == strategy.excluded_declaration_count
    assert strategy.excluded_declaration_count == 5


def test_unrelated_demand_is_not_reported_as_an_exclusion(coffee_ctx):
    """Thirty-odd households in this workspace buy whey, rice and paper towels.

    None of them was ever a candidate for a coffee order — cross-family substitution is
    refused before any other rule — so counting them would turn an exclusion histogram
    into a census of the Community's unrelated shopping. The scope is proved complete by
    the test below rather than assumed.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[A_MEDIUM]
    assert strategy.excluded_declaration_count < 10
    assert sum(strategy.exclusion_codes.values()) == strategy.excluded_declaration_count


def test_the_scope_rule_admits_everything_compatibility_could_admit(coffee_ctx):
    """The completeness claim ``in_scope`` rests on, checked against every declaration.

    If a declaration outside the scope could ever be compatible, the fingerprint would
    not cover it and a change to it would not make anything stale — so this is a
    staleness test wearing a compatibility test's clothes.
    """
    from pool.domain.substitution import evaluate_compatibility

    for target in coffee_ctx.repo.list_products(WS):
        for need in coffee_ctx.repo.list_needs(WS):
            declared = coffee_ctx.repo.get_product(WS, need.product_id)
            if declared is None:
                continue
            verdict = evaluate_compatibility(
                target=target, candidate=declared, need=need, facts=coffee_ctx.product_facts
            )
            if verdict.compatible:
                assert st.in_scope(coffee_ctx, need, target), (need.id, target.id)


# --------------------------------------------------------------------- strategy diversity


def test_the_two_options_differ_in_ways_that_matter(coffee_ctx):
    """Not two names for one order. Different SKU, different people, different supplier
    terms, and — once evaluated — a different case structure and a different answer."""
    strategies = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )
    medium, dark = strategies[A_MEDIUM], strategies[B_DARK]

    assert medium.target_product_id != dark.target_product_id
    assert medium.target_attributes["roast"] != dark.target_attributes["roast"]
    assert set(medium.candidate_need_ids) != set(dark.candidate_need_ids)
    assert medium.compatible_units != dark.compatible_units
    assert medium.lowest_minimum_units != dark.lowest_minimum_units
    # One depends on buying somebody's coffee five weeks early; the other does not.
    assert medium.future_units > 0 and dark.future_units == 0

    evaluations = evaluate_all(coffee_ctx, list(strategies.values()))
    assert evaluations[A_MEDIUM].case_units != evaluations[B_DARK].case_units
    assert evaluations[A_MEDIUM].viable != evaluations[B_DARK].viable


# ------------------------------------------------------- the listing does not pre-solve


def test_the_listing_cannot_tell_the_refused_option_from_the_viable_one(coffee_ctx):
    """The property that makes a later strategy choice a real one.

    Both summaries describe an option with more compatible demand than its supplier will
    sell below, from a supplier this deployment holds a quote for, at a public site the
    cohort can reach. On the facts generation established, both are worth investigating —
    and evaluation says one is not cheaper than buying alone.

    That is not a fact withheld. It is a fact that does not exist yet: which tier wins,
    which buyers fill whole cases, what a host would be paid for that many orders, and
    what processing costs on that many authorisations are all set-level, and the set is
    what evaluation chooses.
    """
    strategies = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )
    summaries = {pid: st.strategy_summary(s) for pid, s in strategies.items()}

    for summary in summaries.values():
        assert summary["compatible_units"] >= summary["lowest_supplier_minimum_units"]
        assert summary["bulk_tiers"] >= 1
        assert summary["includes_objective_declaration"] is True

    evaluations = evaluate_all(coffee_ctx, list(strategies.values()))
    assert evaluations[A_MEDIUM].viable is False
    assert evaluations[B_DARK].viable is True

    # And the option that looks *better* on every fact the listing carries is the one
    # that fails. If it were the other way round the listing would be a ranking with
    # extra steps.
    assert summaries[A_MEDIUM]["compatible_units"] > summaries[B_DARK]["compatible_units"]
    assert (
        summaries[A_MEDIUM]["compatible_declarations"]
        > summaries[B_DARK]["compatible_declarations"]
    )


def test_a_summary_carries_no_verdict_and_no_price(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    for summary in (st.strategy_summary(s) for s in strategies):
        keys = set(summary)
        assert not keys & {
            "viable", "winner", "recommended", "score", "rank", "blocker_code",
            "net_savings_bps", "all_in_cents", "unit_price_cents", "cases",
        }
        blob = json.dumps(summary)
        assert "cents" not in blob and "$" not in blob


def test_a_summary_carries_no_personal_data(coffee_ctx):
    """Product facts, counts, and a public place. Nothing about who anybody is (§4)."""
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    households = coffee_ctx.repo.list_households(WS)
    forbidden = {h.id for h in households}
    forbidden |= {h.display_name for h in households}
    forbidden |= {h.contact_email for h in households if h.contact_email}
    forbidden |= {n.id for n in coffee_ctx.repo.list_needs(WS)}

    for summary in (st.strategy_summary(s) for s in strategies):
        blob = json.dumps(summary)
        for secret in forbidden:
            assert secret not in blob, secret
        assert "lat" not in blob and "lon" not in blob


def test_a_summary_carries_what_a_choice_actually_needs(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    summary = st.strategy_summary(strategies[0])
    assert summary["strategy_id"].startswith("strat_")
    assert summary["attributes"] == {
        "caffeine": pf.CAFFEINE_CAFFEINATED,
        "form": pf.FORM_WHOLE_BEAN,
        "roast": pf.ROAST_MEDIUM,
    }
    for key in (
        "compatible_declarations", "compatible_units", "current_units", "future_units",
        "excluded_declarations", "exclusion_codes", "lowest_supplier_minimum_units",
        "pickup_site", "relies_on_pull_forward",
    ):
        assert key in summary, key


# ------------------------------------------------------------- authoritative evaluation


def test_the_refusal_is_computed_from_the_supplier_terms_and_nothing_else(coffee_ctx):
    """A real refusal, on a real number, from code that predates this fixture.

    Twenty units against a fifteen-unit minimum, four whole cases, no surplus — and once
    the host is paid for seven orders, the processor takes its cut of seven
    authorisations and Pool takes its share, the group pays more than the seven of them
    would pay separately. The correct behaviour is to bother nobody.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[A_MEDIUM]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)

    assert evaluation.viable is False
    assert evaluation.blocker_code == coord.REASON_NOT_CHEAPER
    assert evaluation.matched_units == 20 >= evaluation.minimum_units == 15
    assert evaluation.cases * evaluation.case_units == evaluation.selected_units
    assert evaluation.surplus_units == 0
    # The refusal is the arithmetic, not a flag: all-in exceeds what buying alone costs.
    assert evaluation.net_savings_cents < 0
    assert evaluation.all_in_cents > evaluation.retail_baseline_cents
    assert (
        evaluation.all_in_cents
        == evaluation.retail_baseline_cents - evaluation.net_savings_cents
    )
    assert evaluation.host_compensation_cents > 0
    assert evaluation.processing_fee_cents > 0


def test_the_viable_option_fills_whole_cases_and_leaves_no_surplus(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)

    assert evaluation.viable is True
    assert evaluation.blocker_code == ""
    # Invariant 6 does not get a discount for arriving through a strategy search.
    assert evaluation.surplus_units == 0
    assert evaluation.selected_units == evaluation.cases * evaluation.case_units
    assert evaluation.selected_units % evaluation.case_units == 0
    assert evaluation.selected_units >= evaluation.minimum_units
    # Some compatible demand did not fit, and that is reported rather than hidden.
    assert evaluation.matched_units > evaluation.selected_units
    assert evaluation.net_savings_cents > 0
    assert evaluation.auto_join_count + evaluation.approval_required_count == (
        evaluation.selected_member_count
    )
    assert evaluation.approval_required_count >= 1, "the ask-me member is still asked"
    assert evaluation.includes_objective_need is True
    assert evaluation.routing_provider


def test_evaluation_reloads_state_rather_than_trusting_the_strategy(coffee_ctx):
    """Retire two declarations after listing, and the verdict moves.

    Nothing stored on the strategy is consulted for the answer — the strategy still lists
    those two among its candidates, and the evaluation does not.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    before = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert before.viable is True

    for need_id in ("need_rc_okonjo", "need_rc_baptiste", "need_rc_delgado"):
        need = coffee_ctx.repo.get_need(WS, need_id)
        need.active = False
        coffee_ctx.repo.put_need(WS, need)

    after = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert after.matched_units < before.matched_units
    assert after.viable is False
    assert after.blocker_code == coord.REASON_BELOW_MINIMUM
    # The stale summary still names them. The verdict does not.
    stored = coffee_ctx.repo.get_cohort_strategy(WS, strategy.id)
    assert "need_rc_okonjo" in stored.candidate_need_ids
    assert "need_rc_okonjo" not in after.eligible_need_ids


def test_a_member_outside_the_formation_radius_is_excluded_by_evaluation(coffee_ctx):
    """Geography is a set-level fact and belongs to evaluation, so the summary counts a
    member the evaluation then drops. That is the two stages disagreeing correctly."""
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    assert "need_rc_okonjo" in strategy.candidate_need_ids

    household = coffee_ctx.repo.get_household(WS, "hh_rc_okonjo")
    household.lat += 0.6  # tens of kilometres away, far outside the Community
    coffee_ctx.repo.put_household(WS, household)

    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert evaluation.exclusion_codes.get("outside_radius") == 1
    assert "need_rc_okonjo" not in evaluation.eligible_need_ids


def test_a_stale_supplier_quote_refuses_however_good_the_economics_are(coffee_ctx):
    """Freshness is checked against the tier that actually won, because that is the quote
    a buyer would be charged against (§43)."""
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    assert st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id).viable is True

    community = coffee_ctx.community(COMMUNITY_ID)
    offer = coffee_ctx.repo.get_offer(WS, "off_rc_harbourstone_dark_bulk")
    offer.verified_at = iso(
        utcnow() - timedelta(hours=community.quote_max_age_hours + 6)
    )
    coffee_ctx.repo.put_offer(WS, offer)

    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert evaluation.viable is False
    assert evaluation.blocker_code == st.BLOCKER_QUOTE_STALE
    assert evaluation.quote_age_hours > community.quote_max_age_hours
    # The economics were still computed and are still recorded: the refusal is about the
    # age of the quote, not about the deal being bad.
    assert evaluation.net_savings_cents > 0


def test_a_missing_product_or_site_refuses_rather_than_raising(coffee_ctx):
    """A world that moved under a stored option is a refusal, never a traceback."""
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]

    site_id = strategy.pickup_site_id
    coffee_ctx.repo.store(WS).sites.pop(site_id)
    gone = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert gone.viable is False
    assert gone.blocker_code == st.BLOCKER_SITE_MISSING
    assert st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=gone.id
    ).ok is False

    coffee_ctx.repo.store(WS).products.pop(B_DARK)
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert evaluation.viable is False
    assert evaluation.blocker_code == st.BLOCKER_TARGET_MISSING


def test_every_blocker_a_strategy_can_report_is_a_declared_code(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=community_objective())
    for strategy in strategies:
        evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
        assert evaluation.blocker_code in st.STRATEGY_BLOCKER_CODES


def test_an_evaluation_summary_keeps_every_decision_critical_fact(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    summary = st.evaluation_summary(st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id))
    for key in (
        "viable", "blocker_code", "stale", "matched_units", "minimum_units",
        "selected_units", "cases", "case_units", "surplus_units", "net_savings_pct",
        "auto_join_count", "approval_required_count", "includes_objective_declaration",
        "exclusion_codes", "evaluation_id",
    ):
        assert key in summary, key

    households = coffee_ctx.repo.list_households(WS)
    blob = json.dumps(summary)
    for secret in {h.display_name for h in households} | {h.id for h in households}:
        assert secret not in blob, secret


def test_an_order_that_forms_without_the_member_who_asked_says_so(coffee_ctx):
    """A real outcome, and one that must never be reported as their order (§8).

    The anchor withdraws their declaration. The dark-roast order still forms for the
    neighbours — six people are not refused because a seventh left — and the evaluation
    records that the declaration which triggered the question is not in it.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    need = coffee_ctx.repo.get_need(WS, ANCHOR_NEED)
    need.active = False
    coffee_ctx.repo.put_need(WS, need)

    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert evaluation.viable is True
    assert evaluation.includes_objective_need is False


# ------------------------------------------- product consent is not financial consent


def _anchor_verdict(ctx: PoolContext, strategy: CohortStrategy):
    """The triggering member's own Smart Join verdict inside the winning order."""
    assessment = coord.evaluate_opportunity(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        product_id=strategy.target_product_id,
        pickup_site_id=strategy.pickup_site_id,
    )
    return next(c for c in assessment.candidates if c.need_id == ANCHOR_NEED).verdict


def test_a_stated_product_rule_is_not_permission_to_spend(coffee_ctx):
    """The Phase 1 boundary, checked from the other side.

    A constrained declaration says *which products are acceptable*, and Phase 1 stopped
    asking a member to re-approve a product their own rule already admits. It did not,
    and must not, say anything about money. Ask Me still means Pool may organise and
    never commit; a spend ceiling still bites at the exact landed price.

    Both are asserted on the same member and the same order, with the substitution check
    passing throughout — so the two consents are visibly separate rather than separately
    described.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]

    baseline = _anchor_verdict(coffee_ctx, strategy)
    assert baseline.eligible_for_auto_join is True
    assert next(c for c in baseline.checks if c.rule == "substitution").passed is True

    # Ask Me. The product rule is unchanged and still passes; the commitment does not.
    household = coffee_ctx.repo.get_household(WS, ANCHOR_HOUSEHOLD)
    household.autonomy.mode = AutonomyMode.ASK_ME
    coffee_ctx.repo.put_household(WS, household)
    asked = _anchor_verdict(coffee_ctx, strategy)
    assert asked.eligible_for_auto_join is False
    assert "autonomy_mode" in asked.failed_rules
    assert next(c for c in asked.checks if c.rule == "substitution").passed is True

    # Back to Smart Join, and a spend ceiling below the landed price instead.
    household.autonomy.mode = AutonomyMode.SMART_JOIN
    coffee_ctx.repo.put_household(WS, household)
    need = coffee_ctx.repo.get_need(WS, ANCHOR_NEED)
    need.max_spend_cents = 1
    coffee_ctx.repo.put_need(WS, need)
    capped = _anchor_verdict(coffee_ctx, strategy)
    assert capped.eligible_for_auto_join is False
    assert "max_spend" in capped.failed_rules
    assert next(c for c in capped.checks if c.rule == "substitution").passed is True


def test_no_household_carries_a_constrained_standing_autonomy_policy(coffee_ctx):
    """``AutonomyPolicy`` shares the ``SubstitutionPolicy`` enum with a declaration.

    A standing value of ``ATTRIBUTE_CONSTRAINED`` would read as "substitutes are
    pre-authorised" in the Smart Join branch that governs *other* policies, while
    carrying no rule to check — a widening with nothing behind it. Nothing writes that
    value today and this phase adds no path that could; pinned here so a future one
    cannot arrive unnoticed.
    """
    for household in coffee_ctx.repo.list_households(WS):
        assert household.autonomy.substitution is SubstitutionPolicy.EXACT_ONLY, household.id


# ------------------------------------------------------------------------- staleness


def test_fresh_evidence_about_an_unchanged_world_is_actionable(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    check = st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=evaluation.id
    )
    assert check.ok is True
    assert evaluation.stale is False


@pytest.mark.parametrize(
    "disturb",
    [
        pytest.param(
            lambda ctx: _requote(ctx, "off_rc_harbourstone_dark_bulk", 1_090),
            id="supplier_requotes",
        ),
        pytest.param(
            lambda ctx: _amend_units(ctx, "need_rc_baptiste", 5), id="member_amends_units"
        ),
        pytest.param(
            lambda ctx: _retire(ctx, "need_rc_delgado"), id="member_retires_declaration"
        ),
        pytest.param(lambda ctx: _widen_rule(ctx, "need_rc_okonjo"), id="member_changes_rule"),
        pytest.param(lambda ctx: _recurate_fact(ctx), id="product_fact_recurated"),
    ],
)
def test_stale_evidence_is_refused_after_any_decision_relevant_change(coffee_ctx, disturb):
    """Evidence is a snapshot, and a snapshot is not authority for spending money.

    Each case changes one authoritative input the verdict depended on, and each makes the
    stored evaluation unusable — without anything having been re-evaluated, and without
    the evaluation itself being edited. The check re-derives the fingerprint from current
    state, which is the only version of the question a mutation cares about.
    """
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=evaluation.id
    ).ok

    disturb(coffee_ctx)

    check = st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=evaluation.id
    )
    assert check.ok is False
    assert check.code == st.ACTIONABLE_STALE
    # The stored evaluation is untouched — it is still true about the world it described.
    assert coffee_ctx.repo.get_strategy_evaluation(WS, evaluation.id).viable is True


def test_regenerating_keeps_the_id_and_moves_the_fingerprint(coffee_ctx):
    """Identity and freshness are separate on purpose.

    If the id moved whenever a quantity did, a stored evaluation would point at nothing
    and the only available answer would be "unknown strategy" — indistinguishable from a
    caller inventing one.
    """
    before = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    _amend_units(coffee_ctx, "need_rc_baptiste", 4)
    after = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]

    assert after.id == before.id
    assert after.input_fingerprint != before.input_fingerprint


def test_a_re_evaluation_after_a_change_is_current_and_says_the_listing_was_not(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    _requote(coffee_ctx, "off_rc_harbourstone_dark_bulk", 1_090)

    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert evaluation.stale is True
    assert evaluation.stale_reason
    # Stale about the *listing*, and still an honest verdict about now — so the fresh
    # evidence is immediately actionable.
    assert evaluation.viable is True
    assert st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=evaluation.id
    ).ok is True


def test_evidence_that_does_not_exist_is_not_authority(coffee_ctx):
    """An id nobody issued must not be indistinguishable from one that expired."""
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]

    assert (
        st.ensure_actionable(
            ctx=coffee_ctx, strategy_id="strat_nope", evaluation_id="seval_nope"
        ).code
        == st.ACTIONABLE_UNKNOWN_STRATEGY
    )
    # A real strategy, and evidence that was never recorded for it.
    check = st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id="seval_nope"
    )
    assert check.ok is False
    assert check.code == st.ACTIONABLE_UNKNOWN_EVALUATION


def test_evidence_about_another_option_is_not_authority_for_this_one(coffee_ctx):
    strategies = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )
    other = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategies[A_MEDIUM].id)
    check = st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategies[B_DARK].id, evaluation_id=other.id
    )
    assert check.ok is False
    assert check.code == st.ACTIONABLE_MISMATCHED


def test_a_refused_evaluation_is_not_authority_for_anything(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[A_MEDIUM]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    check = st.ensure_actionable(
        ctx=coffee_ctx, strategy_id=strategy.id, evaluation_id=evaluation.id
    )
    assert check.ok is False
    assert check.code == st.ACTIONABLE_NOT_VIABLE


def _requote(ctx: PoolContext, offer_id: str, cents: int) -> None:
    offer = ctx.repo.get_offer(WS, offer_id)
    offer.unit_price_cents = cents
    offer.verified_at = iso(utcnow())
    ctx.repo.put_offer(WS, offer)


def _amend_units(ctx: PoolContext, need_id: str, units: int) -> None:
    need = ctx.repo.get_need(WS, need_id)
    need.quantity = units
    ctx.repo.put_need(WS, need)


def _retire(ctx: PoolContext, need_id: str) -> None:
    need = ctx.repo.get_need(WS, need_id)
    need.active = False
    ctx.repo.put_need(WS, need)


def _widen_rule(ctx: PoolContext, need_id: str) -> None:
    from pool.domain.attributes import AttributeConstraint

    need = ctx.repo.get_need(WS, need_id)
    need.attribute_policy = AttributeConstraint(
        family=pf.FAMILY,
        schema_version=pf.SCHEMA_VERSION,
        requires={"form": frozenset({pf.FORM_WHOLE_BEAN})},
    )
    ctx.repo.put_need(WS, need)


def _recurate_fact(ctx: PoolContext) -> None:
    """A curated fact is corrected. The evidence that read the old one is now history."""
    from pool.domain.attributes import (
        FactProvenance,
        FactVerification,
        ProductAttributeFact,
    )

    facts = {p.id: dict(pf.REGISTRY.facts_for(p.id)) for p in pf.PRODUCTS}
    facts[B_DARK]["roast"] = ProductAttributeFact(
        product_id=B_DARK, family=pf.FAMILY, attribute="roast", value=pf.ROAST_MEDIUM,
        provenance=FactProvenance.CURATED_SYNTHETIC,
        verification=FactVerification.VERIFIED, schema_version=pf.SCHEMA_VERSION,
    )
    ctx.product_facts = pf.CuratedProductFacts(facts=facts)


# ------------------------------------------------------------------------ persistence


def test_both_entities_round_trip_through_dynamodb_shaped_storage(coffee_ctx):
    """Through the real adapter and boto3's own serialiser, and in the same order.

    The public-demo parity guard compares every list method across both backends, but the
    showcase is homogeneous and searches no strategies — so their ordering contract is
    proved here, against a populated world.
    """
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=community_objective())
    evaluations = [st.evaluate_strategy(ctx=coffee_ctx, strategy_id=s.id) for s in strategies]

    dynamo = DynamoDBRepository("pool-demo-state", table=FakeDynamoTable())
    for strategy in strategies:
        dynamo.put_cohort_strategy(WS, strategy)
    for evaluation in evaluations:
        dynamo.put_strategy_evaluation(WS, evaluation)

    assert [s.id for s in dynamo.list_cohort_strategies(WS)] == [
        s.id for s in coffee_ctx.repo.list_cohort_strategies(WS)
    ]
    assert [e.id for e in dynamo.list_strategy_evaluations(WS)] == [
        e.id for e in coffee_ctx.repo.list_strategy_evaluations(WS)
    ]

    restored = dynamo.get_cohort_strategy(WS, strategies[0].id)
    assert restored.to_dict() == strategies[0].to_dict()
    stored_eval = dynamo.get_strategy_evaluation(WS, evaluations[0].id)
    assert stored_eval.to_dict() == evaluations[0].to_dict()

    # One strategy's evidence is a scoped query rather than a scan of the workspace.
    scoped = dynamo.list_strategy_evaluations(WS, strategies[0].id)
    assert [e.id for e in scoped] == [evaluations[0].id]


def test_a_stored_strategy_holds_no_personal_data(coffee_ctx):
    strategies = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    households = coffee_ctx.repo.list_households(WS)
    blob = json.dumps([s.to_dict() for s in strategies])
    for secret in {h.display_name for h in households} | {
        h.contact_email for h in households if h.contact_email
    }:
        assert secret not in blob, secret


def test_an_evaluation_records_need_ids_and_never_a_roster_of_who_failed(coffee_ctx):
    strategy = by_product(
        st.generate_strategies(ctx=coffee_ctx, objective=member_objective())
    )[B_DARK]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    for row in evaluation.excluded:
        assert set(row) == {"need_id", "code", "attribute"}
        assert "household" not in json.dumps(row)


# ----------------------------------------------------------- nothing else moved


def test_the_ordinary_seed_still_contains_none_of_this():
    """The coffee fixture is installed, never seeded. A workspace nobody asked for it in
    has no roast-coffee product, no Beanline offer and no coffee household."""
    repo = InMemoryRepository()
    seed(repo, WS)
    products = {p.id for p in repo.list_products(WS)}
    assert not (products & {p.id for p in pf.PRODUCTS})
    assert not any(o.id.startswith("off_rc_") for o in repo.list_offers(WS))
    assert not any(h.id.startswith("hh_rc_") for h in repo.list_households(WS))
    assert repo.list_cohort_strategies(WS) == []


def test_the_canonical_rice_demand_is_untouched_by_the_fixture(coffee_ctx):
    """Six households, twenty-two bags, still no supplier. Installing a coffee community
    beside it must not move a number the rest of the suite pins."""
    rice = [n for n in coffee_ctx.repo.list_needs(WS) if n.product_id == "prod_rice_jasmine"]
    assert len({n.household_id for n in rice}) == 6
    assert sum(n.quantity for n in rice) == 22
    assert coord.offers_for(coffee_ctx, "prod_rice_jasmine")[1] == []


def test_homogeneous_discovery_still_works_beside_the_search(coffee_ctx):
    """The existing latent-demand path is unchanged and still finds the whey opportunity,
    in a workspace that now also contains a heterogeneous coffee community."""
    listing = discovery.latent_demand(ctx=coffee_ctx, community_id=COMMUNITY_ID)
    products = {row["product_id"] for row in listing["opportunities"]}
    assert "prod_whey_vanilla" in products

    outcome = coord.evaluate_opportunity(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        product_id="prod_whey_vanilla",
        pickup_site_id="site_union",
    )
    assert outcome.viable is True
    assert outcome.economics.packages.surplus_units == 0


def test_a_group_declaration_is_still_a_group_declaration(coffee_ctx):
    """``GROUP_DECLARED`` keeps meaning what it meant, including inside a search: a
    member who declared the family is offered every SKU in it, ground and decaf included."""
    need = coffee_ctx.repo.get_need(WS, "need_rc_gallardo")
    need.substitution = SubstitutionPolicy.GROUP_DECLARED
    need.attribute_policy = None
    coffee_ctx.repo.put_need(WS, need)

    strategies = st.generate_strategies(
        ctx=coffee_ctx, objective=member_objective("hh_rc_gallardo", "need_rc_gallardo")
    )
    assert {s.target_product_id for s in strategies} == {
        A_MEDIUM, A_LIGHT, B_DARK, C_DECAF, D_GROUND, E_UNVERIFIED_ROAST,
    }


def test_the_agent_package_is_not_involved(coffee_ctx):
    """Phase 2 builds the substrate and wires nothing to the model.

    Asserted structurally rather than promised: the strategy module imports no agent
    module, and no strategy function is reachable from the tool surface.
    """
    import inspect

    from pool.agent.tools import TOOL_SURFACE

    source = inspect.getsource(st)
    assert "pool.agent" not in source and "..agent" not in source

    names = {name for name, _kind in TOOL_SURFACE}
    assert len(names) == 12, "the tool surface itself must not have moved"
    assert not any("strategy" in name or "cohort" in name for name in names)


def test_a_strategy_evaluation_is_a_separate_entity_from_a_run_evaluation(coffee_ctx):
    """Different questions, different rows. A run evaluation records what one agent run
    established about one product; this records what one *option* costs."""
    strategy = st.generate_strategies(ctx=coffee_ctx, objective=member_objective())[0]
    evaluation = st.evaluate_strategy(ctx=coffee_ctx, strategy_id=strategy.id)
    assert isinstance(evaluation, StrategyEvaluation)
    assert coffee_ctx.repo.list_run_evaluations(WS) == []
