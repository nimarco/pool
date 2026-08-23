"""Which questions are worth asking, and what happens when the answer changes.

Phase 4 asked every approved question about a product, in a fixed order, and that was
the honest thing to build first: the questions come from a curated schema, so asking all
of them is at worst tedious. It is also the shape a product with three attributes can
afford and a product with thirty cannot, and *tedious* is not the only cost — a question
whose answer cannot change anything Pool could buy is a question that spends attention to
learn nothing.

So the choosing became the agent's. The distinction this module exists to hold is narrow
and absolute:

* **The agent chooses which approved questions to ask, and in what order.** It reads a
  listing of candidates with counts attached and no verdict, and writes back a subset.
* **The agent never chooses what a question means.** Every prompt, every value label and
  every mapping from answer to typed policy is in a committed table, and
  :func:`services.needs.policy_from_answers` is the only thing that reads an answer.

The second half of the module is about the answers being *changeable*, which is where a
preference product differs from a checkout. A member who narrows their rules is taken out
of an order those rules forbid; a member who widens them again gets it back. Both are
deterministic reconciliation, and neither is a thing the model decides.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from pool.adapters.repository import InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.data import product_facts as pf
from pool.data.roast_coffee_fixture import (
    A_MEDIUM,
    B_DARK,
    E_UNVERIFIED_ROAST,
    install_roast_coffee,
)
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import (
    MAX_CLARIFICATION_QUESTIONS,
    ClarificationPlanStatus,
    ParticipationState,
)
from pool.services import clarification as clar
from pool.services import coordination as coord
from pool.services import needs as needs_service
from pool.services import strategy as st
from pool.services.context import PoolContext

from .conftest import WS

#: The seed's own first-run member — the one the member demo is about. She starts with
#: no declaration of her own, so everything below is something this test made her say.
MEMBER = "hh_navarro"
#: Somebody already in the coffee fixture, used only to prove that one member's edit is
#: never allowed to move another member's participation.
OTHER = "hh_rc_baptiste"


@pytest.fixture
def coffee_ctx() -> PoolContext:
    repo = InMemoryRepository()
    seed(repo, WS)
    install_roast_coffee(repo, WS)
    return PoolContext(
        repo=repo, ws=WS, routing=CachingRouting(DeterministicRouting(max_cells=400))
    )


def ids(candidates) -> list[str]:
    return [c.question_id for c in candidates]


# ------------------------------------------------------------------ the approved set


def test_the_candidates_are_the_schema_and_nothing_a_caller_invented(coffee_ctx):
    """Every askable question traces to a curated attribute of the product's family."""
    schema = pf.REGISTRY.family_schema(pf.FAMILY)
    assert schema is not None
    keys = {definition.key for definition in schema.attributes}
    offered = clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM)

    assert offered, "a curated product must have something to ask about"
    for candidate in offered:
        assert candidate.attribute in keys
        question = pf.QUESTIONS[candidate.attribute]
        assert candidate.question_id == question.id
        # The wording is curated too — a prompt is a committed template with this
        # product's own value rendered into it, not a sentence assembled out of the
        # attribute name at request time.
        assert candidate.prompt == question.prompt.replace(
            "{value}",
            pf.VALUE_LABELS[candidate.attribute][candidate.product_value].lower(),
        )


def test_a_product_with_an_unverified_fact_is_asked_about_less(coffee_ctx):
    """Targeting is a property of the product, not a constant.

    Beacon's roast is on file but unverified, and an unverified fact authorises nothing.
    Asking somebody to narrow by roast would be collecting a preference Pool could not
    act on for the very product they are looking at.
    """
    kestrel = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM))
    beacon = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, E_UNVERIFIED_ROAST))

    assert "roast_coffee.roast" in kestrel
    assert "roast_coffee.roast" not in beacon
    assert set(beacon) < set(kestrel)


def test_the_listing_states_reach_and_reaches_no_conclusion(coffee_ctx):
    """Counts, not a ranking — and specifically not one number to sort on.

    Two independent quantities per answer, measured over different things: how many
    products Pool could source, and how much standing demand it could combine with. A
    listing carrying `recommended: true`, a score, or a single blended figure would make
    the model's choice arithmetic somebody already did.
    """
    for candidate in clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM):
        payload = candidate.to_dict()
        assert set(payload["answers"]) == {clar.ANSWER_KEEP, clar.ANSWER_ANY}
        for answer in payload["answers"].values():
            assert set(answer) == {
                "values",
                "sourceable_products",
                "standing_requests",
                "standing_units",
            }
            for key in ("sourceable_products", "standing_requests", "standing_units"):
                assert isinstance(answer[key], int)

        # And the same figures per individual value, so the consequence of one choice is
        # a stored number rather than something a screen worked out.
        for reach in payload["options"].values():
            assert set(reach) == {
                "sourceable_products",
                "standing_requests",
                "standing_units",
            }

        flat = str(payload)
        for banned in ("recommend", "score", "rank", "priority", "best", "should_ask"):
            assert banned not in flat


def test_widening_an_answer_never_reaches_less_than_keeping_it(coffee_ctx):
    """The counts are the real world, so the monotonicity is not decoration."""
    for candidate in clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM):
        keep = candidate.answers[clar.ANSWER_KEEP]
        any_ = candidate.answers[clar.ANSWER_ANY]
        assert any_["sourceable_products"] >= keep["sourceable_products"]
        assert any_["standing_requests"] >= keep["standing_requests"]


# ------------------------------------------------------------------------ the plan


def test_a_plan_may_only_contain_questions_the_listing_offered(coffee_ctx):
    with pytest.raises(clar.ClarificationError):
        clar.record_plan(
            ctx=coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=E_UNVERIFIED_ROAST,
            # Real question, real family, and not offered for *this* product.
            question_ids=["roast_coffee.roast"],
        )


def test_a_plan_may_not_ask_the_same_thing_twice_or_ask_too_much(coffee_ctx):
    offered = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM))

    with pytest.raises(clar.ClarificationError):
        clar.record_plan(
            ctx=coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            question_ids=[offered[0], offered[0]],
        )

    with pytest.raises(clar.ClarificationError):
        clar.record_plan(
            ctx=coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            question_ids=offered * (MAX_CLARIFICATION_QUESTIONS + 1),
        )


def test_asking_nothing_is_a_legitimate_plan(coffee_ctx):
    """Fewer questions is the direction the prompt pushes, so zero has to be reachable."""
    plan = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=[],
    )
    assert plan.question_ids == []
    assert plan.status == ClarificationPlanStatus.ACTIVE.value


def test_the_plan_keeps_the_order_it_was_given(coffee_ctx):
    """Order is part of the choice: the first question is the one asked of everybody."""
    offered = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM))
    chosen = [offered[2], offered[0]]
    plan = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=chosen,
    )
    assert plan.question_ids == chosen
    stored, _ = clar.existing_plan(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)
    assert stored is not None and stored.question_ids == chosen


def test_a_plan_is_identified_by_the_world_it_was_made_for(coffee_ctx):
    """Which is what makes reopening a form free, and a moved world replan.

    The id digests the member, the product and the candidate listing — so the same
    question is never asked twice about the same facts, and a listing that changed
    underneath produces a different plan rather than quietly reusing a stale one.
    """
    offered = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM))
    first = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=[offered[0]],
    )
    found, _ = clar.existing_plan(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)
    assert found is not None and found.id == first.id

    # Somebody else declares the same coffee. The counts a reader would weigh move, so
    # what is worth asking is a live question again.
    _declare(coffee_ctx, household=OTHER)
    assert clar.existing_plan(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)[0] is None

    second = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=[offered[1]],
    )
    assert second.id != first.id
    superseded = coffee_ctx.repo.get_clarification_plan(WS, first.id)
    assert superseded is not None
    assert superseded.status == ClarificationPlanStatus.SUPERSEDED.value

    active, _ = clar.existing_plan(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)
    assert active is not None and active.id == second.id


def test_a_member_changing_their_own_mind_does_not_move_the_plan(coffee_ctx):
    """The cost bound that survives A → B → C.

    A plan is keyed on the world the questions are about, and a member's own standing
    request is not part of that world: the questions exist to establish what *they* will
    accept, so counting their own declaration as evidence is circular. It is also what
    keeps the plan stable while they change their mind — otherwise narrowing and
    re-widening moves the counts, invalidates the plan, and buys a second model call for
    an answer that could not have changed.
    """
    plan = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM, MEMBER))[:2],
    )

    for state in ({}, {"exact": True}, {}):
        _declare(coffee_ctx, **state)
        found, _ = clar.existing_plan(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)
        assert found is not None and found.id == plan.id


def test_the_counts_are_about_everybody_else(coffee_ctx):
    _declare(coffee_ctx)
    with_me = clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM)
    without_me = clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM, MEMBER)
    mine = {c.attribute: c for c in with_me}
    for candidate in without_me:
        other = mine[candidate.attribute]
        for key in (clar.ANSWER_KEEP, clar.ANSWER_ANY):
            assert (
                candidate.answers[key]["standing_requests"]
                < other.answers[key]["standing_requests"]
            )


# --------------------------------------------------------- the conservative default


def test_allowing_alternatives_never_pre_selects_a_second_value(coffee_ctx):
    """Opening the brand does not open the roast, however much it would help.

    The temptation is real and specific: the canonical walkthrough forms an order when
    the member accepts a dark roast and truthfully refuses when they do not, so widening
    the default by one value would make the demo succeed every time. It would also be
    Pool consenting on somebody's behalf to drink coffee they did not ask for.
    """
    _, policy = needs_service.policy_from_answers(
        coffee_ctx,
        A_MEDIUM,
        needs_service.PreferenceAnswers(
            flexibility=needs_service.Flexibility.SIMILAR, keep=[], accept={}
        ),
    )
    assert policy is not None
    assert policy.requires["roast"] == frozenset({pf.ROAST_MEDIUM})
    assert pf.ROAST_DARK not in policy.requires["roast"]
    assert policy.requires["form"] == frozenset({pf.FORM_WHOLE_BEAN})
    assert policy.requires["caffeine"] == frozenset({pf.CAFFEINE_CAFFEINATED})


def test_the_narrow_default_is_the_one_that_can_refuse(coffee_ctx):
    """And the refusal is the truthful outcome, not a bug to design around.

    Pinned because it is the thing a demo-shaped instinct would break: a member who keeps
    every default is compatible with strictly fewer products than one who broadens, and
    Pool must be willing to reach the smaller answer.
    """
    narrow = needs_service.PreferenceAnswers(
        flexibility=needs_service.Flexibility.SIMILAR, keep=[], accept={}
    )
    broad = needs_service.PreferenceAnswers(
        flexibility=needs_service.Flexibility.SIMILAR,
        keep=[],
        accept={"roast": [pf.ROAST_MEDIUM, pf.ROAST_DARK]},
    )
    _, narrow_policy = needs_service.policy_from_answers(coffee_ctx, A_MEDIUM, narrow)
    _, broad_policy = needs_service.policy_from_answers(coffee_ctx, A_MEDIUM, broad)
    assert narrow_policy.requires["roast"] < broad_policy.requires["roast"]

    def admits(policy) -> set[str]:
        from pool.domain.substitution import evaluate_compatibility

        declared = coffee_ctx.repo.get_product(WS, A_MEDIUM)
        need = _declare(coffee_ctx)
        need.attribute_policy = policy
        return {
            p.id
            for p in coffee_ctx.repo.list_products(WS)
            if p.substitute_group == pf.FAMILY
            and evaluate_compatibility(
                target=p, candidate=declared, need=need, facts=coffee_ctx.product_facts
            ).compatible
        }

    assert admits(narrow_policy) < admits(broad_policy)


# ------------------------------------------------------------------- the guidance


def test_the_flexibility_numbers_are_counted_rather_than_predicted(coffee_ctx):
    """The honest thing Pool can say is how much demand exists, not what will happen."""
    ctx = coffee_ctx
    facts = clar.flexibility_context(ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)

    others = [
        n
        for n in ctx.repo.list_needs(WS)
        if n.active and n.community_id == COMMUNITY_ID and n.household_id != MEMBER
    ]
    assert facts["exact_requests"] == sum(1 for n in others if n.product_id == A_MEDIUM)
    assert facts["compatible_requests"] >= facts["exact_requests"]
    assert 0 < facts["sourceable_alternatives"] < len(pf.PRODUCTS)

    # No probability, no forecast, nothing a reader could quote back as a promise.
    assert set(facts) == {"exact_requests", "compatible_requests", "sourceable_alternatives"}


def test_every_answer_carries_the_demand_it_would_reach(coffee_ctx):
    """The consequence of a choice is a stored count, not a screen's arithmetic.

    Per allowed value, so a member weighing "would dark do as well?" is shown what that
    one answer reaches. A client summing rows would be re-deriving demand, and a client
    inventing a combined figure would be inventing one.
    """
    for candidate in clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM, MEMBER):
        assert candidate.options, "an answer with no stated consequence explains nothing"
        for value, reach in candidate.options.items():
            assert set(reach) == {
                "sourceable_products",
                "standing_requests",
                "standing_units",
            }
            # Every figure is a count over rows that exist, so none can exceed the total.
            assert reach["sourceable_products"] <= candidate.answers[clar.ANSWER_ANY][
                "sourceable_products"
            ]
            assert reach["standing_units"] <= candidate.answers[clar.ANSWER_ANY][
                "standing_units"
            ]
            assert value in candidate.answers[clar.ANSWER_ANY]["values"]


def test_the_units_behind_an_answer_are_the_units_members_actually_declared(coffee_ctx):
    """Checkable against the store, because a plausible number is not a true one."""
    from pool.data import product_facts as pf_data

    candidates = {c.attribute: c for c in clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM, MEMBER)}
    roast = candidates["roast"]

    for value, reach in roast.options.items():
        products = {
            p.id
            for p in coffee_ctx.repo.list_products(WS)
            if p.substitute_group == pf_data.FAMILY
            and (fact := coffee_ctx.product_facts.facts_for(p.id).get("roast"))
            and fact.is_authoritative
            and fact.value == value
            and coord.offers_for(coffee_ctx, p.id)[1]
        }
        expected_units = sum(
            n.quantity
            for n in coffee_ctx.repo.list_needs(WS)
            if n.active
            and n.community_id == COMMUNITY_ID
            and n.household_id != MEMBER
            and n.product_id in products
        )
        assert reach["standing_units"] == expected_units, value
        assert reach["sourceable_products"] == len(products), value


def test_the_guidance_counts_nobody_twice_and_names_nobody(coffee_ctx):
    facts = clar.flexibility_context(coffee_ctx, COMMUNITY_ID, MEMBER, A_MEDIUM)
    households = {h.id for h in coffee_ctx.repo.list_households(WS)}
    assert facts["compatible_requests"] < len(households)
    assert MEMBER not in str(facts) and OTHER not in str(facts)


# ------------------------------------------------------- consent stays where it was


def test_accepting_alternatives_is_not_accepting_different_coffee(coffee_ctx):
    """The whole point of the gate: brand flexibility is not attribute flexibility.

    Saying "another roaster is fine" must not quietly also say "ground is fine" or
    "decaf is fine". Every question left alone stays at what the chosen product already
    is, which is the narrowest reading of what the member actually agreed to.
    """
    answers = needs_service.PreferenceAnswers(
        flexibility=needs_service.Flexibility.SIMILAR, keep=[], accept={}
    )
    _, policy = needs_service.policy_from_answers(coffee_ctx, A_MEDIUM, answers)
    assert policy is not None
    assert policy.requires["form"] == frozenset({pf.FORM_WHOLE_BEAN})
    assert policy.requires["caffeine"] == frozenset({pf.CAFFEINE_CAFFEINATED})


def test_an_unanswered_question_can_only_narrow_never_widen(coffee_ctx):
    """Omission is not consent. Silence has to read as the strictest available meaning."""
    _, silent = needs_service.policy_from_answers(
        coffee_ctx,
        A_MEDIUM,
        needs_service.PreferenceAnswers(
            flexibility=needs_service.Flexibility.SIMILAR, keep=[], accept={}
        ),
    )
    _, spoken = needs_service.policy_from_answers(
        coffee_ctx,
        A_MEDIUM,
        needs_service.PreferenceAnswers(
            flexibility=needs_service.Flexibility.SIMILAR, keep=[], accept={"form": []}
        ),
    )
    assert silent is not None and spoken is not None
    # Saying nothing keeps the requirement; unticking it is what removes it, and the
    # empty list is how that travels.
    assert silent.requires["form"] == frozenset({pf.FORM_WHOLE_BEAN})
    assert "form" not in spoken.requires


def test_the_saved_declaration_reads_back_as_the_answers_that_made_it(coffee_ctx):
    """Editing has to start from what is stored, not from a fresh set of defaults.

    A form that reopened on defaults would quietly propose widening every rule the member
    had narrowed, and the member would be one *Save* away from consenting to it.
    """
    need = _declare(coffee_ctx, keep=["form"], accept={"caffeine": []})
    answers = needs_service.current_answers(coffee_ctx, need)
    assert answers["flexibility"] == "similar"
    assert "form" in answers["keep"]
    # The dropped requirement comes back as an answer somebody gave, not as a gap.
    assert "caffeine" not in answers["keep"]
    assert answers["accept"]["caffeine"] == []


def test_an_exact_declaration_reads_back_as_exact(coffee_ctx):
    need = _declare(coffee_ctx, exact=True)
    assert needs_service.current_answers(coffee_ctx, need) == {
        "flexibility": "exact",
        "keep": [],
        "accept": {},
    }


@pytest.mark.parametrize(
    "keep,accept",
    [
        ([], {}),
        (["form", "caffeine"], {}),
        (["caffeine"], {"form": []}),
        (["form"], {"caffeine": []}),
        ([], {"form": [], "caffeine": []}),
        (["form", "caffeine"], {"roast": [pf.ROAST_MEDIUM, pf.ROAST_DARK]}),
        ([], {"form": [], "caffeine": [], "roast": [pf.ROAST_LIGHT, pf.ROAST_MEDIUM, pf.ROAST_DARK]}),
    ],
)
def test_opening_the_edit_form_and_saving_it_changes_nothing(coffee_ctx, keep, accept):
    """The fixed point that makes editing safe, over every shape of answer.

    Reversibility is not only about the buttons. A member who dropped a requirement and
    then opens *Edit preferences* for an unrelated reason must not have that requirement
    put back by the act of saving — Pool would be overruling a correction with a default,
    and nothing on the screen would say so.
    """
    need = _declare(coffee_ctx, keep=keep, accept=accept)
    before = need.attribute_policy

    reopened = needs_service.current_answers(coffee_ctx, need)
    saved = _declare(
        coffee_ctx,
        exact=reopened["flexibility"] == "exact",
        keep=reopened["keep"],
        accept=reopened["accept"],
    )

    assert saved.substitution == need.substitution
    assert (saved.attribute_policy.requires if saved.attribute_policy else None) == (
        before.requires if before else None
    )
    # And therefore no new coordination was owed by a save that said nothing new.
    assert saved.revision == need.revision


# ----------------------------------------------------------------- the proof of it


def test_the_technical_record_shows_the_set_as_well_as_the_choice(coffee_ctx):
    """A reader checking that a model chose *within* an approved set needs the set.

    Recording only the questions asked would leave the interesting claim unfalsifiable:
    a plan naming three questions proves nothing about whether a fourth was available and
    passed over, or invented on the spot.
    """
    from pool.services import events as events_service

    offered = ids(clar.candidates(coffee_ctx, COMMUNITY_ID, A_MEDIUM, MEMBER))
    plan = clar.record_plan(
        ctx=coffee_ctx,
        community_id=COMMUNITY_ID,
        household_id=MEMBER,
        product_id=A_MEDIUM,
        question_ids=[offered[-1], offered[0]],
        run_id="run_clarify",
    )
    need = _declare(coffee_ctx)
    events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan.id
    )

    proof = events_service.explain(coffee_ctx, need.id)
    assert proof is not None
    asked = proof["clarification"]
    assert asked["offered"] == offered
    assert asked["asked"] == [offered[-1], offered[0]]
    assert set(asked["asked"]) <= set(asked["offered"])
    assert asked["run_id"] == "run_clarify"
    assert asked["family"] == pf.FAMILY
    assert asked["schema_version"] == pf.SCHEMA_VERSION
    # And it is a *different* run from the one that formed the order. Asking happens
    # while somebody is deciding; coordinating happens after they have decided.
    assert asked["run_id"] != (proof["run"] or {}).get("run_id")


def test_an_exact_only_declaration_reports_that_nothing_was_asked(coffee_ctx):
    from pool.services import events as events_service

    need = _declare(coffee_ctx, exact=True)
    events_service.record_declaration_event(coffee_ctx, need, COMMUNITY_ID)
    proof = events_service.explain(coffee_ctx, need.id)
    assert proof is not None and proof["clarification"] is None


def test_an_exact_only_event_refuses_a_plan_even_when_one_is_offered(coffee_ctx):
    """Naming a plan does not make one apply.

    Exact-only answered no questions, so the lineage is empty *because of what the
    declaration says*, not because the caller happened to leave the field out. A client
    that sends a real plan id beside an exact-only save must not be able to attach
    clarification proof to a declaration nothing clarified.
    """
    from pool.services import events as events_service

    plan = _plan(coffee_ctx)
    need = _declare(coffee_ctx, exact=True)
    event = events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan.id
    )
    assert event is not None and event.clarification_plan_id == ""
    proof = events_service.explain(coffee_ctx, need.id)
    assert proof is not None and proof["clarification"] is None


# ----------------------------------------------------- lineage is frozen, not searched


def _plan(ctx, *, household=MEMBER, product=A_MEDIUM, run_id="run_clarify", question_ids=None):
    """One clarification plan, recorded the way a bounded planner run records it."""
    offered = ids(clar.candidates(ctx, COMMUNITY_ID, product, household))
    return clar.record_plan(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        household_id=household,
        product_id=product,
        question_ids=list(question_ids if question_ids is not None else offered),
        run_id=run_id,
    )


def _replan(ctx, **kwargs):
    """A *second* plan for the same member and product, made after the world moved.

    A plan's id digests the world it was made against, so producing a different one means
    genuinely changing that world. Another member declaring the same coffee moves the
    standing-demand counts the candidates carry, which is exactly the situation the old
    lookup got wrong.
    """
    other = next(
        h.id
        for h in ctx.repo.list_households(WS)
        if h.id not in {MEMBER, OTHER}
        and not any(
            n.active and n.household_id == h.id and n.product_id == A_MEDIUM
            for n in ctx.repo.list_needs(WS)
        )
    )
    needs_service.declare_need(
        ctx=ctx,
        community_id=COMMUNITY_ID,
        data=needs_service.NeedInput(
            household_id=other,
            product_id=A_MEDIUM,
            quantity=4,
            cadence_days=30,
            expected_next_need_date=date.today() + timedelta(days=9),
            flexibility_days=8,
            max_spend_cents=20_000,
        ),
    )
    return _plan(ctx, **kwargs)


def test_a_later_plan_does_not_re_describe_an_earlier_declaration(coffee_ctx):
    """The release-blocking defect, reproduced and refused.

    A declaration saved under plan A, then a plan B for the same member and product.
    Historical proof for A must still be A. The old view searched for the newest plan by
    household and product, so B silently became the record of what shaped A — false
    historical evidence about the one surface whose whole purpose is being checkable.
    """
    from pool.services import events as events_service

    plan_a = _plan(coffee_ctx, run_id="run_plan_a")
    need = _declare(coffee_ctx)
    event = events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan_a.id
    )
    assert event is not None and event.clarification_plan_id == plan_a.id

    plan_b = _replan(coffee_ctx, run_id="run_plan_b")
    assert plan_b.id != plan_a.id

    proof = events_service.explain(coffee_ctx, need.id)
    assert proof is not None
    assert proof["clarification"]["plan_id"] == plan_a.id
    assert proof["clarification"]["run_id"] == "run_plan_a"


def test_the_superseded_plan_is_shown_as_superseded_rather_than_swapped(coffee_ctx):
    """Recording plan A afterwards does not mean pretending A is still current."""
    from pool.services import events as events_service

    plan_a = _plan(coffee_ctx, run_id="run_plan_a")
    need = _declare(coffee_ctx)
    events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan_a.id
    )
    _replan(coffee_ctx, run_id="run_plan_b")

    proof = events_service.explain(coffee_ctx, need.id)
    assert proof is not None
    assert proof["clarification"]["plan_id"] == plan_a.id
    assert proof["clarification"]["status"] == ClarificationPlanStatus.SUPERSEDED.value


def test_reading_the_proof_again_does_not_move_it(coffee_ctx):
    """A pure read, twice, either side of a third plan being made.

    Everything the plan *was* is unchanged: the same row, the same run, the same
    questions offered and asked. The one field that does move is ``status``, and it
    should — the plan has genuinely been superseded since, and saying otherwise would be
    the surface asserting the world had not moved.
    """
    from pool.services import events as events_service

    plan_a = _plan(coffee_ctx, run_id="run_plan_a")
    need = _declare(coffee_ctx)
    events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan_a.id
    )
    first = events_service.explain(coffee_ctx, need.id)
    _replan(coffee_ctx, run_id="run_plan_b")
    second = events_service.explain(coffee_ctx, need.id)

    assert first is not None and second is not None
    assert {k: v for k, v in first["clarification"].items() if k != "status"} == {
        k: v for k, v in second["clarification"].items() if k != "status"
    }
    assert first["clarification"]["status"] == ClarificationPlanStatus.ACTIVE.value
    assert second["clarification"]["status"] == ClarificationPlanStatus.SUPERSEDED.value


def test_every_revision_carries_its_own_lineage(coffee_ctx):
    """A → B → C, each event answering for itself.

    A: flexible under plan A. B: the same member goes exact-only — no plan at all. C:
    flexible again, under a plan made later. Three events, three different answers, and
    none of them moved when the next one was written.
    """
    from pool.services import events as events_service

    plan_a = _plan(coffee_ctx, run_id="run_plan_a")
    a = _declare(coffee_ctx)
    event_a = events_service.record_declaration_event(
        coffee_ctx, a, COMMUNITY_ID, clarification_plan_id=plan_a.id
    )

    b = _declare(coffee_ctx, exact=True)
    event_b = events_service.record_declaration_event(coffee_ctx, b, COMMUNITY_ID)

    plan_c = _replan(coffee_ctx, run_id="run_plan_c")
    c = _declare(coffee_ctx)
    event_c = events_service.record_declaration_event(
        coffee_ctx, c, COMMUNITY_ID, clarification_plan_id=plan_c.id
    )

    assert event_a is not None and event_b is not None and event_c is not None
    # One declaration, three revisions, three distinct events.
    assert len({event_a.id, event_b.id, event_c.id}) == 3
    assert event_a.clarification_plan_id == plan_a.id
    assert event_b.clarification_plan_id == ""
    assert event_c.clarification_plan_id == plan_c.id

    # And each event still answers for itself, read back after all three exist.
    assert _plan_of(coffee_ctx, event_a) == plan_a.id
    assert _plan_of(coffee_ctx, event_b) is None
    assert _plan_of(coffee_ctx, event_c) == plan_c.id


def _plan_of(ctx, event):
    from pool.services import events as events_service

    view = events_service._clarification_view(ctx, event)
    return view["plan_id"] if view else None


def test_a_plan_belonging_to_another_member_cannot_attach(coffee_ctx):
    theirs = _plan(coffee_ctx, household=OTHER)
    with pytest.raises(clar.ClarificationError, match="another member"):
        clar.lineage_reference(
            coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            plan_id=theirs.id,
        )


def test_a_plan_about_another_product_cannot_attach(coffee_ctx):
    other_product = _plan(coffee_ctx, product=B_DARK)
    with pytest.raises(clar.ClarificationError, match="another product"):
        clar.lineage_reference(
            coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            plan_id=other_product.id,
        )


def test_a_plan_from_another_community_cannot_attach(coffee_ctx):
    mine = _plan(coffee_ctx)
    with pytest.raises(clar.ClarificationError, match="another community"):
        clar.lineage_reference(
            coffee_ctx,
            community_id="com_elsewhere",
            household_id=MEMBER,
            product_id=A_MEDIUM,
            plan_id=mine.id,
        )


def test_a_plan_id_that_does_not_exist_is_refused(coffee_ctx):
    with pytest.raises(clar.ClarificationError, match="does not exist"):
        clar.lineage_reference(
            coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            plan_id="cpl_invented",
        )


def test_naming_no_plan_records_no_lineage(coffee_ctx):
    """Absent is absent. Nothing is reconstructed from what happens to be lying around."""
    _plan(coffee_ctx)
    assert (
        clar.lineage_reference(
            coffee_ctx,
            community_id=COMMUNITY_ID,
            household_id=MEMBER,
            product_id=A_MEDIUM,
            plan_id="",
        )
        == ""
    )


def test_lineage_survives_dynamodb_shaped_storage(coffee_ctx):
    """Repository parity: the reference is a field on the row, in both backends.

    A ``CoordinationEvent`` round-trips through ``to_dict``/``from_dict`` on the DynamoDB
    path, and a field that did not survive that would leave the deployed demo silently
    back on the old behaviour — no proof at all, rather than the wrong proof.
    """
    from pool.domain.models import CoordinationEvent
    from pool.services import events as events_service

    plan = _plan(coffee_ctx)
    need = _declare(coffee_ctx)
    event = events_service.record_declaration_event(
        coffee_ctx, need, COMMUNITY_ID, clarification_plan_id=plan.id
    )
    assert event is not None

    restored = CoordinationEvent.from_dict(json.loads(json.dumps(event.to_dict())))
    assert restored.clarification_plan_id == plan.id
    assert _plan_of(coffee_ctx, restored) == plan.id

    # And a row written before the field existed reads as "nothing recorded" rather than
    # raising or falling back to a search.
    legacy = {k: v for k, v in event.to_dict().items() if k != "clarification_plan_id"}
    assert CoordinationEvent.from_dict(legacy).clarification_plan_id == ""
    assert _plan_of(coffee_ctx, CoordinationEvent.from_dict(legacy)) is None


# --------------------------------------------------------------- A → B → C, in full


def _declare(ctx, *, exact=False, keep=None, accept=None, household=MEMBER):
    """One member's declaration, made the way the form makes it."""
    substitution, policy = needs_service.policy_from_answers(
        ctx,
        A_MEDIUM,
        needs_service.PreferenceAnswers(
            flexibility=(
                needs_service.Flexibility.EXACT if exact else needs_service.Flexibility.SIMILAR
            ),
            keep=list(keep if keep is not None else ["form", "caffeine"]),
            accept=dict(
                accept if accept is not None else {"roast": [pf.ROAST_MEDIUM, pf.ROAST_DARK]}
            ),
        ),
    )

    existing = next(
        (
            n
            for n in ctx.repo.list_needs(WS)
            if n.active and n.household_id == household and n.product_id == A_MEDIUM
        ),
        None,
    )
    data = needs_service.NeedInput(
        household_id=household,
        product_id=A_MEDIUM,
        quantity=3,
        cadence_days=30,
        expected_next_need_date=date.today() + timedelta(days=12),
        flexibility_days=11,
        max_spend_cents=20_000,
        substitution=substitution,
        attribute_policy=policy,
    )
    if existing is not None:
        return needs_service.amend_need(
            ctx=ctx, community_id=COMMUNITY_ID, need_id=existing.id, data=data
        )
    return needs_service.declare_need(ctx=ctx, community_id=COMMUNITY_ID, data=data)


def _put_in_pool(ctx, need):
    """Put the member in a dark-roast order their flexible rules permit."""
    strategies = st.generate_strategies(
        ctx=ctx,
        objective=st.StrategyObjective(
            kind=st.OBJECTIVE_MEMBER,
            community_id=COMMUNITY_ID,
            household_id=need.household_id,
            need_id=need.id,
        ),
    )
    dark = next(s for s in strategies if s.target_product_id == B_DARK)
    evaluation = st.evaluate_strategy(ctx=ctx, strategy_id=dark.id)
    result = st.create_candidate_pool_from_strategy(
        ctx=ctx, strategy_id=dark.id, evaluation_id=evaluation.id
    )
    assert result.pool_id, result.refusal_reason
    pool = ctx.repo.get_pool(ctx.ws, result.pool_id)
    assert pool is not None
    coord.join_pool_provisionally(
        ctx=ctx, pool_id=pool.id, household_id=need.household_id, need_id=need.id
    )
    membership = ctx.repo.get_membership(ctx.ws, pool.id, need.household_id)
    assert membership is not None
    # The dark roast is not the coffee they declared, and the record has to say so —
    # it is what the restore path later has to reproduce rather than assume.
    membership.is_exact_product = False
    ctx.repo.put_membership(ctx.ws, membership)
    return pool


def test_narrowing_removes_you_from_an_order_your_rules_no_longer_permit(coffee_ctx):
    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)

    exact = _declare(coffee_ctx, exact=True)
    result = coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=exact)

    assert result == [
        {"pool_id": pool.id, "withdrawn": True, "reason_code": "exact_product_required"}
    ]
    membership = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert membership is not None
    assert membership.state == ParticipationState.WITHDRAWN
    assert membership.withdrawn_reason == "exact_product_required"


def test_widening_again_gives_the_order_back(coffee_ctx):
    """B → C. The canonical reversal, and the reason `revision` exists.

    The declaration in state C is *textually* the declaration in state A, and the world
    is not: the member is out of an order they used to be in. Coordination is keyed on
    the content of a declaration, so without something distinguishing them, C resolves to
    A's already-completed event and the member is left looking at a verdict about a world
    they have since left.
    """
    a = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, a)

    b = _declare(coffee_ctx, exact=True)
    coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=b)

    c = _declare(coffee_ctx)
    result = coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=c)

    assert result == [
        {
            "pool_id": pool.id,
            "restored": True,
            "reason_code": "exact_product_required",
            "state": "provisional",
        }
    ]
    membership = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert membership is not None
    assert membership.state == ParticipationState.PROVISIONAL
    # A substitute has to keep saying it is one, whatever route put them back.
    assert membership.is_exact_product is False


def test_going_back_to_what_you_said_before_is_a_new_thing_to_have_said(coffee_ctx):
    from pool.services.events import event_id_for

    a = _declare(coffee_ctx)
    first = event_id_for(a)
    b = _declare(coffee_ctx, exact=True)
    second = event_id_for(b)
    c = _declare(coffee_ctx)
    third = event_id_for(c)

    assert len({first, second, third}) == 3
    assert c.revision == 2


def test_saving_a_form_that_changed_nothing_is_still_free(coffee_ctx):
    """The dedupe Phase 3 built has to survive the fix above it.

    A revision that moved on every save would buy a model call for every stray click on
    *Save*, which is the cost bound this phase is explicitly held to.
    """
    from pool.services.events import event_id_for

    first = _declare(coffee_ctx)
    before = (first.revision, event_id_for(first))
    again = _declare(coffee_ctx)
    assert (again.revision, event_id_for(again)) == before


def test_an_order_you_left_yourself_stays_left(coffee_ctx):
    """The asymmetry that makes restoring safe.

    Pool may undo something Pool did. It may not undo something the member did — somebody
    who leaves an order and later widens an unrelated preference has not asked to be put
    back into it, and doing so would be Pool overruling a decision with a side effect.
    """
    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)

    coord.withdraw_participant(ctx=coffee_ctx, pool_id=pool.id, household_id=MEMBER)
    assert coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=need) == []

    membership = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert membership is not None and membership.state == ParticipationState.WITHDRAWN


def test_a_retired_declaration_is_not_put_back_into_anything(coffee_ctx):
    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)
    coord.withdraw_participant(
        ctx=coffee_ctx, pool_id=pool.id, household_id=MEMBER, reason="exact_product_required"
    )

    need.active = False
    coffee_ctx.repo.put_need(WS, need)
    assert coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=need) == []


def test_restoring_never_re_authorises_a_payment(coffee_ctx):
    """Editing a preference does not touch a card, in either direction.

    A member who had authorised comes back *provisional*, and is asked again. The
    released authorisation is theirs to give a second time.
    """
    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)
    membership = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert membership is not None
    membership.state = ParticipationState.AUTHORIZED
    coffee_ctx.repo.put_membership(WS, membership)

    coord.withdraw_participant(
        ctx=coffee_ctx, pool_id=pool.id, household_id=MEMBER, reason="exact_product_required"
    )
    coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=need)

    restored = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert restored is not None
    assert restored.state == ParticipationState.PROVISIONAL
    assert restored.payment_id == ""


def test_an_order_already_paid_for_is_reported_rather_than_undone(coffee_ctx):
    """The line a preference edit does not cross.

    Past lock the money is captured and the supplier order is placed, and a standing
    preference is not a cancellation policy — inventing one here would be inventing a
    refund rule. So the membership is left exactly as it is and the refusal is returned,
    which is what lets a caller say so rather than quietly showing the wrong world.
    """
    from pool.domain.models import PoolStatus

    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)
    pool.status = PoolStatus.LOCKED
    coffee_ctx.repo.put_pool(WS, pool)

    result = coord.reconcile_after_declaration_change(
        ctx=coffee_ctx, need=_declare(coffee_ctx, exact=True)
    )
    assert len(result) == 1
    assert result[0]["withdrawn"] is False
    assert result[0]["refused"]

    membership = coffee_ctx.repo.get_membership(WS, pool.id, MEMBER)
    assert membership is not None
    assert membership.state == ParticipationState.PROVISIONAL


def test_another_members_order_is_never_touched_by_your_edit(coffee_ctx):
    need = _declare(coffee_ctx)
    pool = _put_in_pool(coffee_ctx, need)
    other_need = next(
        n for n in coffee_ctx.repo.list_needs(WS) if n.household_id == OTHER and n.active
    )
    coord.join_pool_provisionally(
        ctx=coffee_ctx, pool_id=pool.id, household_id=OTHER, need_id=other_need.id
    )

    coord.reconcile_after_declaration_change(ctx=coffee_ctx, need=_declare(coffee_ctx, exact=True))

    theirs = coffee_ctx.repo.get_membership(WS, pool.id, OTHER)
    assert theirs is not None and theirs.state == ParticipationState.PROVISIONAL
