"""Whose account this is, and what Pool is allowed to assume about them.

The product used to answer "who are you?" by casting the visitor as a seeded student.
Everything here protects the replacement, and the invariants fall into three groups.

**Nothing is known before it is told.** A fresh workspace has no name, no card, no
declarations and no completed setup for the person at the screen. Anything Pool appears
to know about them on first run is something it made up.

**A name is only a name.** Matching, economics, case fitting and every asserted figure in
the canonical scenario key off the household *id*, which onboarding never changes. Typing
a different name must produce a byte-identical outcome, and that is checked by running the
whole scenario twice rather than by reading the code and believing it.

**The account is the caller's own.** The household id is a server constant. No request
body names it, so no request can point this at a synthetic neighbour.
"""

from __future__ import annotations

import pytest

from pool.data.seed import CONSUMER_HOUSEHOLD, seed
from pool.domain.models import FUNDED_PARTICIPATION_STATES, AutonomyMode, ParticipationState
from pool.services import onboarding
from pool.services.demo import run_showcase
from tests.conftest import WS

# --------------------------------------------------------------- nothing is known


def test_a_fresh_workspace_has_no_completed_account(seeded_ctx):
    view = onboarding.consumer_view(seeded_ctx)
    assert view["household_id"] == CONSUMER_HOUSEHOLD
    assert view["onboarded"] is False
    assert view["has_payment_method"] is False


def test_the_place_is_described_without_a_coordinate(seeded_ctx):
    """Location is answered, not collected.

    Pool never asks the browser for a position — the deployed ``Permissions-Policy``
    denies geolocation and this keeps it honest — and it never claims the member is near
    the synthetic campus. So what onboarding can say about where somebody is contains no
    latitude, no longitude and nothing derived from one.
    """
    place = onboarding.describe_place(seeded_ctx).to_dict()
    assert place["community_name"]
    assert place["member_count"] > 0
    assert place["pickup_site_count"] > 0
    assert place["synthetic"] is True
    for banned in ("lat", "lon", "latitude", "longitude", "coordinates", "address"):
        assert not any(banned in key for key in place), f"{banned} leaked into the place"


# ------------------------------------------------------------------ what it writes


def test_the_name_a_person_types_is_the_name_pool_uses(seeded_ctx):
    onboarding.complete_onboarding(
        ctx=seeded_ctx, display_name="Jordan", autonomy_mode="ask_me"
    )
    me = seeded_ctx.repo.get_household(WS, CONSUMER_HOUSEHOLD)
    assert me.display_name == "Jordan"
    assert me.is_onboarded


@pytest.mark.parametrize("name", ["Alex", "Marco", "Jordan Q", "Ada L.", "Zoë"])
def test_any_ordinary_name_works(seeded_ctx, name):
    """No name is special. The product must not be built around one person's."""
    view = onboarding.complete_onboarding(
        ctx=seeded_ctx, display_name=name, autonomy_mode="ask_me"
    )
    assert view["display_name"] == name


def test_surrounding_whitespace_is_not_part_of_a_name(seeded_ctx):
    view = onboarding.complete_onboarding(
        ctx=seeded_ctx, display_name="  Sam   Rae  ", autonomy_mode="ask_me"
    )
    assert view["display_name"] == "Sam Rae"


@pytest.mark.parametrize("mode", ["ask_me", "smart_join"])
def test_the_autonomy_choice_reaches_the_deterministic_policy(seeded_ctx, mode):
    onboarding.complete_onboarding(ctx=seeded_ctx, display_name="Sam", autonomy_mode=mode)
    me = seeded_ctx.repo.get_household(WS, CONSUMER_HOUSEHOLD)
    assert me.autonomy.mode is AutonomyMode(mode)


def test_setup_does_not_invent_limits_on_somebody_s_behalf(seeded_ctx):
    """Only the master switch moves.

    The four numbers underneath it are real constraints the policy engine compares money
    against. Setup asks one question and must not quietly answer four more.
    """
    before = seeded_ctx.repo.get_household(WS, CONSUMER_HOUSEHOLD).autonomy
    limits = (
        before.min_savings_pct,
        before.max_total_cost_cents,
        before.max_travel_minutes,
        before.substitution,
        before.public_pickup_only,
    )
    onboarding.complete_onboarding(
        ctx=seeded_ctx, display_name="Sam", autonomy_mode="smart_join"
    )
    after = seeded_ctx.repo.get_household(WS, CONSUMER_HOUSEHOLD).autonomy
    assert (
        after.min_savings_pct,
        after.max_total_cost_cents,
        after.max_travel_minutes,
        after.substitution,
        after.public_pickup_only,
    ) == limits


def test_running_setup_again_updates_rather_than_duplicates(seeded_ctx):
    onboarding.complete_onboarding(ctx=seeded_ctx, display_name="First", autonomy_mode="ask_me")
    onboarding.complete_onboarding(
        ctx=seeded_ctx, display_name="Second", autonomy_mode="smart_join"
    )
    households = [h for h in seeded_ctx.repo.list_households(WS) if h.id == CONSUMER_HOUSEHOLD]
    assert len(households) == 1
    assert households[0].display_name == "Second"


@pytest.mark.parametrize(
    ("name", "mode"),
    [("", "ask_me"), ("   ", "ask_me"), ("x" * 200, "ask_me"), ("Sam", "whatever")],
)
def test_input_the_domain_will_not_accept_is_refused(seeded_ctx, name, mode):
    with pytest.raises(onboarding.OnboardingError):
        onboarding.complete_onboarding(ctx=seeded_ctx, display_name=name, autonomy_mode=mode)


def test_a_refused_setup_leaves_the_account_untouched(seeded_ctx):
    with pytest.raises(onboarding.OnboardingError):
        onboarding.complete_onboarding(ctx=seeded_ctx, display_name="", autonomy_mode="ask_me")
    me = seeded_ctx.repo.get_household(WS, CONSUMER_HOUSEHOLD)
    assert not me.is_onboarded


# -------------------------------------------------------------- a name is only a name


def _outcome(repo, result):
    """Everything about a finished pool that anybody is ever shown.

    ``need_id`` is stripped from the per-buyer lines: declarations get a fresh uuid every
    run, so comparing it would only ever prove that two uuids differ. The money on those
    lines is kept, which is the part a rename could conceivably move.
    """
    members = repo.list_memberships(WS, result.pool_id)
    funded = [m for m in members if m.state in FUNDED_PARTICIPATION_STATES]
    pool = repo.get_pool(WS, result.pool_id)
    economics = dict(pool.final_economics)
    economics["lines"] = [
        {k: v for k, v in line.items() if k != "need_id"}
        for line in economics.get("lines", [])
    ]
    return {
        "rows": len(members),
        "buyers": len(funded),
        "units": sum(m.allocated_units for m in funded),
        "failed": sum(1 for m in members if m.state is ParticipationState.AUTHORIZATION_FAILED),
        "households": tuple(sorted(m.household_id for m in members)),
        "costs": tuple(sorted((m.household_id, m.final_cost_cents) for m in funded)),
        "economics": economics,
    }


@pytest.mark.parametrize("name", ["Marco", "Jordan", "Priyanka Raghunathan"])
def test_the_display_name_cannot_change_a_single_number(repo, name):
    """The property the whole identity design rests on.

    Renaming an account must be presentational, so this runs the entire scenario with a
    name applied and compares every membership, every per-buyer cent and the complete
    economics against a run without one. Reading `display_name` usages and concluding
    "presentational" would be an argument; this is a measurement.
    """
    from pool.adapters.repository import InMemoryRepository

    baseline_repo = InMemoryRepository()
    baseline = _outcome(baseline_repo, run_showcase(baseline_repo, WS))

    seed(repo, WS)
    named = InMemoryRepository()
    seed(named, WS)
    me = named.get_household(WS, CONSUMER_HOUSEHOLD)
    me.display_name = name
    named.put_household(WS, me)
    renamed = _outcome(named, run_showcase(named, WS, reseed=False))

    assert renamed == baseline


# ----------------------------------------------------------------- the whole flow


def test_setting_up_then_running_reproduces_the_canonical_scenario(repo):
    """A person sets their account up, then Pool runs. Nothing about that is special.

    This is the acceptance test for the pass: the scenario a judge records has to work
    from state a human produced, not from a fixture that resembles it.
    """
    from datetime import date, timedelta

    from pool.data.seed import COMMUNITY_ID
    from pool.services import needs as needs_service
    from pool.services import payments as payment_service
    from tests.conftest import WS as ws

    seed(repo, ws)
    from pool.adapters.payments import LocalSimulatedPaymentProvider
    from pool.adapters.purchase import SimulatedPurchaseExecutor
    from pool.adapters.routing import CachingRouting, DeterministicRouting
    from pool.adapters.sourcing import SyntheticCatalogProvider
    from pool.domain.models import utcnow
    from pool.services.context import PoolContext

    ctx = PoolContext(
        repo=repo,
        ws=ws,
        routing=CachingRouting(DeterministicRouting(max_cells=100)),
        payments=LocalSimulatedPaymentProvider(),
        purchaser=SimulatedPurchaseExecutor(),
        sourcing=SyntheticCatalogProvider(),
        now=utcnow(),
    )

    # Exactly what the four setup screens do, through exactly the same services.
    payment_service.setup_payment_method(ctx=ctx, household_id=CONSUMER_HOUSEHOLD)
    needs_service.declare_need(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        data=needs_service.NeedInput(
            household_id=CONSUMER_HOUSEHOLD,
            product_id="prod_whey_vanilla",
            quantity=2,
            cadence_days=30,
            expected_next_need_date=date.today() + timedelta(days=14),
            flexibility_days=14,
        ),
    )
    onboarding.complete_onboarding(ctx=ctx, display_name="Jordan", autonomy_mode="ask_me")

    result = run_showcase(repo, ws, reseed=False)
    assert result.ok, result.failure

    outcome = _outcome(repo, result)
    assert outcome["buyers"] == 10
    assert outcome["rows"] == 11
    assert outcome["failed"] == 1
    assert outcome["units"] == 24
    assert CONSUMER_HOUSEHOLD in outcome["households"]

    packages = outcome["economics"]["packages"]
    assert (packages["cases"], packages["units_purchased"], packages["surplus_units"]) == (
        2,
        24,
        0,
    )

    # And the setup survived the run: a member should not have to introduce themselves
    # twice because the coordinator did some work.
    me = repo.get_household(ws, CONSUMER_HOUSEHOLD)
    assert me.display_name == "Jordan"
    assert me.is_onboarded


def test_an_automated_replay_leaves_an_account_somebody_could_be_in(repo):
    """The scripted showcase has to produce a state a person could have produced.

    Half-set-up — holding a saved card while still being asked for a name — is not one
    of those, and it is what an earlier version of this left behind.
    """
    result = run_showcase(repo, WS)
    assert result.ok, result.failure
    me = repo.get_household(WS, CONSUMER_HOUSEHOLD)
    assert me.is_onboarded
    assert me.payment_method_ref, "a member who authorised payments has a saved method"
