"""The flagship end-to-end scenario, run for real and asserted on.

This is the single most important test in the repository: it is the same code path a
judge watches, so if the demo would be dishonest, this fails.

It runs entirely offline and free — deterministic planner, simulated payments,
simulated purchase, deterministic routing. No AWS call, no token spend (AGENTS.md §3.6).
"""

from __future__ import annotations

from pool.adapters.repository import InMemoryRepository
from pool.domain.models import (
    AllocationState,
    AutonomyPath,
    ParticipationState,
    PaymentState,
    PoolStatus,
    parse_iso,
)
from pool.domain.timing import evaluate_timing
from pool.services.demo import run_showcase
from tests.conftest import WS


def _run(repo: InMemoryRepository):
    return run_showcase(repo, WS)


def _ctx(repo):
    from pool.adapters.payments import LocalSimulatedPaymentProvider
    from pool.adapters.purchase import SimulatedPurchaseExecutor
    from pool.adapters.routing import CachingRouting, DeterministicRouting
    from pool.adapters.sourcing import SyntheticCatalogProvider
    from pool.domain.models import utcnow
    from pool.services.context import PoolContext

    return PoolContext(
        repo=repo,
        ws=WS,
        routing=CachingRouting(DeterministicRouting(max_cells=100)),
        payments=LocalSimulatedPaymentProvider(),
        purchaser=SimulatedPurchaseExecutor(),
        sourcing=SyntheticCatalogProvider(),
        now=utcnow(),
    )


def _step(result, name: str) -> dict:
    return next(s.facts for s in result.steps if s.name == name)


def test_the_whole_lifecycle_completes(repo):
    result = _run(repo)
    assert result.ok, result.failure
    names = [s.name for s in result.steps]
    assert names == [
        "seed",
        # The scenario begins where the product begins: a member says what she buys.
        # The fixture no longer seeds it, so this step is the declaration being made
        # through the real service rather than a row appearing from nowhere.
        "member_declared_need",
        "latent_demand_discovered",
        "host_candidates_evaluated",
        "host_accepted",
        "final_offer",
        "payment_failure",
        "decision_inbox",
        "recovery",
        "locked_and_captured",
        "purchase",
        "distribution_open",
        "pickup",
        "impact",
    ]


def test_nobody_created_the_group(repo):
    """The core product claim: the agent discovered the pool from standing needs."""
    result = _run(repo)
    facts = _step(result, "latent_demand_discovered")
    assert facts["outcome"] == "pool_created"
    assert "list_latent_demand" in facts["tools_called"]
    assert facts["members"] >= 5
    assert facts["provisional_units"] >= facts["threshold_units"]


def test_the_pool_is_split_into_due_now_and_pulled_forward(repo):
    """The headline arithmetic, and it has to add up.

    The landing page draws this split and *The run* prints it, so the two halves must
    account for every member and every unit of the pool — otherwise the interface is
    telling a story the transcript does not support.
    """
    facts = _step(_run(repo), "latent_demand_discovered")
    assert facts["due_now_members"] + facts["pulled_forward_members"] == facts["members"]
    assert (
        facts["due_now_units"] + facts["pulled_forward_units"] == facts["provisional_units"]
    )
    # And the point of the scenario: due demand alone does not clear the supplier's
    # minimum. If it ever did, the pull-forward mechanic would stop being load-bearing
    # and both the figure and the demo script would be overclaiming.
    assert facts["due_now_units"] < facts["threshold_units"]
    assert facts["pulled_forward_members"] >= 1


def test_the_convergence_figure_matches_the_seed(repo):
    """The landing page's figure claims to be this arithmetic drawn. Hold it to that.

    ``ConvergenceFigure`` in ``apps/web/src/brand.tsx`` says in its own docstring that it
    is "not an illustration of the general idea — it is the arithmetic of the pool this
    community actually forms". A drawing that says that has to be checked, and until
    #0030 it was not: it drew eleven people, one of whom "authorised nothing", and no
    such person exists — every household with a whey need is timing-eligible. It was
    right about 8/18 and 2/6 and wrong about why the rest sat it out, which is the more
    interesting half of the picture.

    So this recomputes the populations from the seed and compares them with the rows the
    figure actually draws. It reads the TSX because the coupling that broke is exactly
    the one between that file and this data.

    **The figure draws discovery, not the finished pool,** and the difference is not
    cosmetic: the scenario later declines a card and recruits a replacement, which moves
    a third member into the pulled-forward column. Discovery is 8/18 + 2/6; the pool that
    completes is 7/16 + 3/8 over its ten buyers. Both are true of different moments, and
    reading one as the other is the mistake this test now makes impossible.
    """
    import pathlib
    import re

    result = _run(repo)
    pool = repo.get_pool(WS, result.pool_id)
    day = parse_iso(pool.timing.distribution_starts_at).date()
    discovery = _step(result, "latent_demand_discovered")

    routine, pulled_eligible = [], []
    for need in repo.list_needs(WS):
        if need.product_id != pool.product_id:
            continue
        verdict = evaluate_timing(need, day)
        assert verdict.eligible, (
            f"{need.household_id} is timing-ineligible; the figure draws nobody in that "
            "state, so either the seed or the figure has moved"
        )
        (pulled_eligible if verdict.is_future_pull_forward else routine).append(need)

    # Who the pool took *at discovery*, which is the moment the figure depicts.
    taken = discovery["pulled_forward_members"]
    spare = len(pulled_eligible) - taken

    assert discovery["due_now_members"] == len(routine)
    assert discovery["due_now_units"] == sum(n.quantity for n in routine)
    # The claim the caption rests on: the taken pull-forwards close the gap *exactly*.
    assert discovery["due_now_units"] + discovery["pulled_forward_units"] == (
        pool.threshold_units
    ), "the figure says six units close the gap exactly; they no longer do"
    assert spare > 0, (
        "with nobody left over, the surplus rule the caption cites is invisible — the "
        "figure would be claiming a restraint the data never exercises"
    )

    source = (
        pathlib.Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "brand.tsx"
    ).read_text()
    block = re.search(r"const rows:[^=]+=\s*\[(.*?)\];", source, re.S)
    assert block, "could not find the figure's rows array"
    drawn = re.findall(r'kind:\s*"(due|pulled|spare)"', block.group(1))

    assert drawn.count("due") == len(routine), (drawn.count("due"), len(routine))
    assert drawn.count("pulled") == taken, (drawn.count("pulled"), taken)
    assert drawn.count("spare") == spare, (drawn.count("spare"), spare)


def test_the_count_reconciles_after_a_declined_card(repo):
    """Ten matched, one declined, one replacement — ten buyers, eleven memberships.

    A judge stepping through sees "10 people", then "1 declined", then a pool page
    listing 11. The transcript has to carry the reconciliation itself rather than
    leaving three screens to be squared by hand.
    """
    result = _run(repo)
    facts = _step(result, "recovery")
    assert facts["memberships_on_record"] == (
        facts["buyers_after_recovery"] + facts["memberships_that_failed"]
    )
    assert facts["memberships_that_failed"] >= 1
    assert facts["buyers_after_recovery"] >= 1
    # The reconciliation the run screen prints, end to end: matched, minus the declined,
    # plus the replacements, equals the people who actually buy.
    matched = facts["members_matched_at_discovery"]
    assert matched == _step(result, "latent_demand_discovered")["members"]
    assert (
        matched - facts["memberships_that_failed"] + facts["replacements_authorised"]
        == facts["buyers_after_recovery"]
    )


def test_the_agent_loop_stayed_bounded(repo):
    result = _run(repo)
    facts = _step(result, "latent_demand_discovered")
    assert facts["iterations"] <= 8
    assert facts["model_provider"] == "offline"


def test_hosts_were_ranked_from_both_sources(repo):
    """Standing hosts and an in-pool volunteer are both considered (§27)."""
    result = _run(repo)
    facts = _step(result, "host_candidates_evaluated")
    assert facts["eligible_count"] >= 1
    sources = {c["household_id"] for c in facts["candidates"]}
    assert facts["volunteer"] in sources
    assert len(sources) > 1
    # At least one candidate is refused for a stated factual reason, not a vibe.
    ineligible = [c for c in facts["candidates"] if not c["eligible"]]
    assert ineligible and all(c["ineligible_reasons"] for c in ineligible)
    # Candidates are named the way members are named everywhere else.
    assert all(c["display_name"] and not c["display_name"].startswith("hh_")
               for c in facts["candidates"])


def test_the_selected_host_is_paid_a_broken_out_reward(repo):
    result = _run(repo)
    facts = _step(result, "host_accepted")
    # A display name, not an identifier: the transcript is read by people, and it should
    # not say more about a member than the rest of the product does.
    assert facts["host"] and not facts["host"].startswith("hh_")
    assert facts["handled_orders"] > 0
    assert sum(facts["reward_breakdown"].values()) > 0
    assert facts["reward_breakdown"]["per_order"] > 0


def test_the_final_price_shows_every_cost(repo):
    """No hidden fees: the four components and the all-in total are all displayed."""
    result = _run(repo)
    facts = _step(result, "final_offer")
    for key in (
        "merchandise", "host_compensation", "payment_processing", "pool_fee", "all_in"
    ):
        assert facts[key].startswith("$")
    assert facts["quote_verified_at"]
    assert facts["authorised_by_smart_join"] > 0
    assert facts["awaiting_human_decision"] > 0


def test_savings_are_real_and_net_of_everything(repo):
    result = _run(repo)
    facts = _step(result, "final_offer")
    all_in = float(facts["all_in"].lstrip("$"))
    retail = float(facts["retail_baseline"].lstrip("$"))
    savings = float(facts["net_savings"].lstrip("$"))
    assert all_in < retail
    assert round(retail - all_in, 2) == round(savings, 2)


def test_a_payment_genuinely_failed_and_was_recovered(repo):
    """The recovery branch is executed, not narrated (AGENTS.md §8)."""
    result = _run(repo)
    failure = _step(result, "payment_failure")
    recovery = _step(result, "recovery")
    assert failure["declined"]
    assert failure["units_lost"] > 0
    assert recovery["recovered"] is True
    assert recovery["replacements_authorised"] > 0
    assert "recover_pool" in recovery["tools_called"]
    assert recovery["funded_units_now"] >= recovery["threshold_units"]


def test_recovery_did_not_over_recruit(repo):
    """Filling a funding hole must not create speculative stock (§48)."""
    result = _run(repo)
    recovery = _step(result, "recovery")
    assert recovery["funded_units_now"] == recovery["threshold_units"]


def test_the_pool_locked_only_after_every_condition_passed(repo):
    result = _run(repo)
    facts = _step(result, "locked_and_captured")
    assert facts["captured_payments"] > 0
    assert facts["provider_mode"] in {"simulated", "test"}
    locked_event = next(event for event in repo.list_activity(WS) if event.kind == "pool_locked")
    assert locked_event.summary.endswith("simulated capture is beginning")
    assert locked_event.facts["provider_mode"] == "simulated"


def test_the_purchase_is_clearly_simulated(repo):
    result = _run(repo)
    facts = _step(result, "purchase")
    assert facts["simulated"] is True
    assert facts["supplier_reference"].startswith("SIMULATED-")
    assert facts["cases"] * 12 == facts["units"]  # whole cases, nothing left over


def test_every_handoff_was_proved_and_no_credential_worked_twice(repo):
    result = _run(repo)
    facts = _step(result, "pickup")
    assert facts["confirmed"] == facts["expected"]
    # The scenario re-scans one credential to demonstrate the property; the exhaustive
    # single-use coverage lives in test_fulfillment.
    assert facts["replay_attempts_rejected"] == 1
    assert "already been used" in facts["replay_rejection_reason"]
    assert facts["status"] == "completed"


def test_impact_is_computed_from_records(repo):
    result = _run(repo)
    facts = _step(result, "impact")
    assert facts["is_demo_data"] is True
    assert facts["collective_saving"].startswith("$")
    assert float(facts["collective_saving"].lstrip("$")) > 0
    assert float(facts["host_earnings"].lstrip("$")) > 0
    confirmed, _, expected = facts["pickups_confirmed"].partition("/")
    assert confirmed == expected
    assert facts["committed_without_asking"] > 0


# ------------------------------------------------------------------- stored state


def test_the_stored_state_matches_the_transcript(repo):
    """A transcript that disagreed with the database would be the worst failure here."""
    result = _run(repo)
    pool = repo.get_pool(WS, result.pool_id)
    assert pool.status == PoolStatus.COMPLETED

    members = repo.list_memberships(WS, pool.id)
    locked = [m for m in members if m.state == ParticipationState.LOCKED]
    assert locked
    assert all(m.final_cost_cents > 0 for m in locked)

    payments = repo.list_payments(WS, pool.id)
    assert all(
        p.state in {PaymentState.CAPTURED, PaymentState.AUTHORIZATION_FAILED}
        for p in payments
    )
    captured = [p for p in payments if p.state == PaymentState.CAPTURED]
    assert sum(p.amount_cents for p in captured) == pool.final_economics["all_in_cents"]

    allocations = repo.list_allocations(WS, pool.id)
    assert allocations
    assert all(a.state == AllocationState.PICKED_UP for a in allocations)

    purchase = repo.get_purchase_for_pool(WS, pool.id)
    assert purchase.simulated is True
    assert purchase.units_purchased == sum(m.allocated_units for m in locked)


def test_the_scenario_is_reproducible(repo):
    """Two runs of the same seed produce the same shape — no hidden randomness."""
    first = _run(repo)
    second = _run(InMemoryRepository())
    assert first.ok and second.ok
    assert [s.name for s in first.steps] == [s.name for s in second.steps]
    assert _step(first, "final_offer")["all_in"] == _step(second, "final_offer")["all_in"]
    assert (
        _step(first, "impact")["collective_saving"]
        == _step(second, "impact")["collective_saving"]
    )


def test_smart_join_and_the_inbox_are_both_exercised(repo):
    result = _run(repo)
    pool = repo.get_pool(WS, result.pool_id)
    paths = {m.path for m in repo.list_memberships(WS, pool.id) if m.counts_as_funded}
    assert AutonomyPath.SMART_JOIN in paths
    assert AutonomyPath.HUMAN_APPROVED in paths


def test_the_activity_feed_tells_the_story_without_reasoning_text(repo):
    result = _run(repo)
    kinds = [e.kind for e in repo.list_activity(WS, limit=200)]
    for expected in (
        "pool_created", "host_offered", "host_accepted", "final_offer_issued",
        "payment_failed", "pool_recovered", "pool_locked", "payment_captured",
        "purchase_executed", "pickup_completed", "pool_completed",
    ):
        assert expected in kinds, f"missing activity event: {expected}"
    blob = str([e.to_dict() for e in repo.list_activity(WS, limit=200)])
    assert "@demo.invalid" not in blob
    assert result.ok


def test_a_fresh_seed_does_not_declare_the_flagship_need_for_rosa(repo):
    """The premise of the whole first-use flow.

    Rosa is the account a visitor acts as. If her whey declaration were seeded, the demo
    would open on a need nobody was shown creating — the pre-populated dashboard this
    design exists to remove — and "Pool found something for you" would be a claim about a
    row that appeared from nowhere.
    """
    from pool.data.seed import seed
    from pool.services.demo import FLAGSHIP_MEMBER, FLAGSHIP_PRODUCT

    seed(repo, WS)
    hers = [
        n
        for n in repo.list_needs(WS)
        if n.household_id == FLAGSHIP_MEMBER and n.product_id == FLAGSHIP_PRODUCT
    ]
    assert hers == [], "the fixture seeded the need the member is supposed to declare"

    # She is still an account with history, not an empty onboarding screen.
    assert [n for n in repo.list_needs(WS) if n.household_id == FLAGSHIP_MEMBER]


def test_the_scenario_declares_it_through_the_real_service(repo):
    """Scripted input, not a fabricated row: the same call the form makes."""
    result = _run(repo)
    facts = _step(result, "member_declared_need")
    assert facts["created_here"] is True
    assert facts["declared_by"] == "scenario"

    stored = repo.get_need(WS, facts["need_id"])
    assert stored is not None and stored.active
    assert stored.product_id == facts["product_id"]
    # The coordinator later reads this exact row.
    assert any(m.need_id == stored.id for m in repo.list_memberships(WS, result.pool_id))


def test_a_member_who_already_declared_is_not_declared_for_twice(repo):
    """A judge declares this in the form a minute before pressing run.

    ``declare_need`` correctly refuses a second active declaration for one product, so
    the scripted path has to notice rather than fail — and must not create a duplicate,
    which matching would count as demand that does not exist.
    """
    from datetime import date, timedelta

    from pool.data.seed import COMMUNITY_ID, seed
    from pool.services import needs as needs_service
    from pool.services.demo import FLAGSHIP_MEMBER, FLAGSHIP_PRODUCT

    seed(repo, WS)
    ctx = _ctx(repo)
    mine = needs_service.declare_need(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        data=needs_service.NeedInput(
            household_id=FLAGSHIP_MEMBER,
            product_id=FLAGSHIP_PRODUCT,
            quantity=2,
            cadence_days=40,
            expected_next_need_date=date.today() + timedelta(days=11),
            flexibility_days=11,
            routine_lead_days=11,
            min_savings_pct=20,
            max_spend_cents=9000,
        ),
    )

    result = run_showcase(repo, WS, reseed=False)
    assert result.ok, result.failure
    facts = _step(result, "member_declared_need")
    assert facts["created_here"] is False
    assert facts["need_id"] == mine.id

    active = [
        n
        for n in repo.list_needs(WS)
        if n.active and n.household_id == FLAGSHIP_MEMBER and n.product_id == FLAGSHIP_PRODUCT
    ]
    assert len(active) == 1, "the scenario created a duplicate declaration"


def test_the_random_declaration_id_does_not_move_the_canonical_outcome(repo):
    """``declare_need`` mints a uuid, and the matcher's last sort key is a need id.

    No two selected candidates tie on the keys ahead of it today, but that is a property
    of the fixture rather than a guarantee — so it is checked rather than assumed.
    """
    from pool.adapters.repository import InMemoryRepository

    signatures = set()
    for _ in range(5):
        fresh = InMemoryRepository()
        outcome = run_showcase(fresh, WS)
        assert outcome.ok, outcome.failure
        members = [
            m
            for m in fresh.list_memberships(WS, outcome.pool_id)
            if m.state is ParticipationState.LOCKED
        ]
        signatures.add(
            (
                len(members),
                sum(m.allocated_units for m in members),
                tuple(sorted(m.household_id for m in members)),
            )
        )
    assert len(signatures) == 1, f"the outcome varied across runs: {signatures}"
