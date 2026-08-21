"""Bounded deterministic cohort-strategy search.

When every member who buys a thing buys the *same* thing, there is one question — is
this worth doing — and the deterministic engines already answer it. Heterogeneous demand
is a different problem. Nine people buy coffee; three named a bag, two wrote allowlists,
four stated typed rules over curated facts (§21, ``domain/attributes``). There is no
single "the" order to evaluate. There are several defensible ones, they serve overlapping
but different groups of people, and they are not equally good in ways nothing knows until
each has been costed.

This module produces those options and evaluates them. Two stages, and the line between
them is the whole design.

**Generation** answers *who could join*. Compatibility and timing are pure functions of
one declaration against one SKU on one date — they do not depend on who else is in. It
is cheap, it is bounded at :data:`MAX_COHORT_STRATEGIES`, and it deliberately does not
know what a group would pay.

**Evaluation** answers *what the group is and what it costs*. Which site, who is inside
the radius, which supplier tier wins, whether the demand lands on whole cases, what the
landed price is, whether that beats buying alone, and who Smart Join would admit without
asking. All of it is set-level: it changes when the set changes.

That is not a device to make a later decision look harder than it is. It is where the
architecture already drew the line — ``discovery.compatible_needs`` has said so since it
was written: *"Timing, geography, case fitting and economics are not decided here — they
are what evaluation is for, and pretending to know them would be the opposite mistake."*
The consequence is that a strategy summary genuinely cannot carry a verdict, because at
that point no verdict exists.

**Nothing here re-implements viability.** Evaluation calls
``coordination.evaluate_opportunity`` — the same function that costs an ordinary
opportunity — and records what it returned. A second implementation of "is this
worthwhile" would be a second answer to the only question that matters.

What this module does not do: it calls no model, registers no tool, and creates no pool.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..domain.models import (
    MAX_STRATEGY_NEED_REFS,
    MAX_STRATEGY_TIERS,
    CohortStrategy,
    Community,
    NeedDeclaration,
    PickupSite,
    Product,
    StrategyEvaluation,
    SubstitutionPolicy,
    new_id,
)
from ..domain.money import bps_to_pct_str, format_cents
from ..domain.substitution import evaluate_compatibility
from ..domain.timing import evaluate_timing, next_pool_day
from . import coordination as coord
from . import discovery
from .context import CoordinationError, PoolContext

#: A hard ceiling on how many options one objective may produce. A search space the
#: size of the catalogue is not a decision, it is a cost (AGENTS.md §3.3), and every
#: strategy beyond a handful is one nobody will ever investigate.
MAX_COHORT_STRATEGIES = 6

#: Exclusions this module decides itself, as values rather than prose. Compatibility
#: refusals arrive already coded from ``domain.substitution``; these are the ones the
#: generator adds. Timing collapses to a single token deliberately: ``TimingEligibility``
#: explains itself in a sentence written for a human, and parsing prose back into a
#: taxonomy is how a second, wrong taxonomy gets built.
EXCLUDED_RETIRED = "declaration_retired"
EXCLUDED_UNKNOWN_PRODUCT = "unknown_product"
EXCLUDED_ALREADY_POOLED = "already_in_pool"
EXCLUDED_TIMING = "timing_not_eligible"
EXCLUDED_FUTURE_NOT_REQUESTED = "future_demand_not_requested"
GENERATOR_EXCLUSION_CODES = frozenset(
    {
        EXCLUDED_RETIRED,
        EXCLUDED_UNKNOWN_PRODUCT,
        EXCLUDED_ALREADY_POOLED,
        EXCLUDED_TIMING,
        EXCLUDED_FUTURE_NOT_REQUESTED,
    }
)

#: Why a strategy is not actionable. The first four are this module's; the rest are
#: ``coordination``'s own opportunity reasons, reused rather than restated so a refusal
#: means the same thing whichever path reached it.
BLOCKER_NONE = ""
BLOCKER_TARGET_MISSING = "target_product_missing"
BLOCKER_SITE_MISSING = "pickup_site_missing"
BLOCKER_QUOTE_STALE = "quote_stale"
#: Deliberately no blocker for staleness. An evaluation computed from current state is an
#: honest verdict about now whatever happened to the listing that led to it, so what
#: expired is reported on ``StrategyEvaluation.stale`` and the verdict stands on its own.
#: Whether *stored* evidence may still be acted on is a different question, asked by
#: :func:`ensure_actionable` at the moment somebody wants to act.
STRATEGY_BLOCKER_CODES = frozenset(
    {BLOCKER_TARGET_MISSING, BLOCKER_SITE_MISSING, BLOCKER_QUOTE_STALE}
) | coord.OPPORTUNITY_REASON_CODES

OBJECTIVE_MEMBER = "member"
OBJECTIVE_COMMUNITY = "community"


@dataclass(frozen=True)
class StrategyObjective:
    """What question a set of strategies is answering.

    The same two triggers ``AgentRun`` already records. A **member** objective is
    anchored to one household's own declaration and asks "what could be done for the
    person who asked"; a **community** objective is the pool-day scan and has no subject.
    The anchor sets the question and never the answer — a member-anchored strategy can
    still evaluate to an order that does not include them, and that is a real outcome
    which must be reported rather than suppressed (AGENTS.md §8).
    """

    kind: str
    community_id: str
    household_id: str = ""
    need_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in (OBJECTIVE_MEMBER, OBJECTIVE_COMMUNITY):
            raise CoordinationError(f"unknown objective kind: {self.kind!r}")
        if self.kind == OBJECTIVE_MEMBER and not self.household_id:
            raise CoordinationError("a member objective needs the household it is anchored to")


# --------------------------------------------------------------------- fingerprinting


def _digest(payload: Any) -> str:
    """A stable digest of canonical JSON. Same world in, same string out."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def in_scope(ctx: PoolContext, need: NeedDeclaration, target: Product) -> bool:
    """Could this declaration *ever* be admitted for this SKU, under any policy?

    There are exactly two doors into compatibility (``domain/substitution``), so there
    are exactly two clauses:

    * the **substitute group** — every policy but one is gated on the target and the
      declared product sharing a curated family, and cross-family substitution is
      refused before any other rule is consulted;
    * the **explicit allowlist** — ``APPROVED_PRODUCTS`` is checked *before* that gate,
      because naming a product id outright is a stronger statement than any structural
      inference, and is deliberately allowed to cross a family boundary.

    Everything outside those two doors is refused by construction, whatever else is true
    of it. That makes this the honest scope for two different jobs: what the staleness
    fingerprint has to cover, and which refusals are worth counting. A household who buys
    whey was never a candidate for a coffee order, and reporting them as "excluded" would
    turn a summary into a census of unrelated demand — a number that reads as information
    and carries none (AGENTS.md §4).
    """
    declared = ctx.repo.get_product(ctx.ws, need.product_id)
    if declared is not None and target.substitute_group and (
        declared.substitute_group == target.substitute_group
    ):
        return True
    return (
        need.substitution == SubstitutionPolicy.APPROVED_PRODUCTS
        and target.id in need.approved_product_ids
    )


def relevant_declarations(
    ctx: PoolContext, community_id: str, target: Product
) -> list[NeedDeclaration]:
    """The active in-scope declarations, in id order. What the fingerprint is taken over.

    Completeness matters here: a declaration that could join but is not hashed is a
    change the evaluator would not notice.
    """
    return sorted(
        (
            n
            for n in ctx.repo.list_needs(ctx.ws)
            if n.active and n.community_id == community_id and in_scope(ctx, n, target)
        ),
        key=lambda n: n.id,
    )


def input_fingerprint(
    ctx: PoolContext, *, community: Community, target: Product, site: PickupSite
) -> str:
    """A digest of everything a verdict about this strategy depends on.

    Deliberately not a general versioning system (§9). It is one hash over the actual
    authoritative inputs — the declarations that could join, the curated facts and the
    schema they were read under, the product row, every offer for it including when each
    was last verified, the site, and the Community's own fee configuration, because the
    fee configuration is an input to landed economics like any other.

    Coarse by construction: any change to any of them invalidates. That over-fires
    slightly — amending a quantity by one unit invalidates a strategy whose verdict would
    not have moved — and the alternative is a per-field dependency graph that would be
    wrong in the dangerous direction the first time somebody added a field to it.
    """
    facts = ctx.product_facts.facts_for(target.id)
    schema = ctx.product_facts.family_schema(target.substitute_group)
    offers = sorted(
        (o for o in ctx.repo.list_offers(ctx.ws) if o.product_id == target.id),
        key=lambda o: o.id,
    )
    return _digest(
        {
            "community": community.id,
            "platform_fee": community.platform_fee.to_dict(),
            "processing_fee": community.processing_fee.to_dict(),
            "host_reward": community.host_reward.to_dict(),
            "quote_max_age_hours": community.quote_max_age_hours,
            "radius_km": community.radius_km,
            "schedule": community.schedule.to_dict(),
            "product": target.to_dict(),
            "attribute_schema_version": schema.version if schema else 0,
            "facts": [facts[k].to_dict() for k in sorted(facts)],
            "offers": [o.to_dict() for o in offers],
            "site": {
                "id": site.id,
                "community_id": site.community_id,
                "lat": site.lat,
                "lon": site.lon,
                "is_public": site.is_public,
            },
            "declarations": [
                n.to_dict() for n in relevant_declarations(ctx, community.id, target)
            ],
        }
    )


def _strategy_id(
    *,
    community_id: str,
    objective: StrategyObjective,
    target_product_id: str,
    pickup_site_id: str,
    include_future_demand: bool,
) -> str:
    """A digest of what the strategy *is*, never of the world it was generated from.

    Identity and freshness are separate on purpose. If the id moved whenever a quantity
    changed, a stored evaluation would point at nothing and the only available answer
    would be "unknown strategy" — which is indistinguishable from a caller inventing an
    id. Keeping identity stable means a strategy whose world moved can be recognised and
    reported as stale, which is a different and far more useful sentence.
    """
    return "strat_" + _digest(
        {
            "community": community_id,
            "objective_kind": objective.kind,
            "objective_household": objective.household_id,
            "objective_need": objective.need_id,
            "target": target_product_id,
            "site": pickup_site_id,
            "future": include_future_demand,
        }
    )[:16]


# ------------------------------------------------------------------------ generation


@dataclass(frozen=True)
class _Envelope:
    """Who this SKU could serve, and who it could not, before anything is costed."""

    needs: list[NeedDeclaration]
    exclusions: dict[str, int]
    excluded_count: int
    current_units: int
    future_units: int


def _envelope(
    ctx: PoolContext,
    *,
    community_id: str,
    target: Product,
    purchase_date: date,
    include_future_demand: bool,
    already_pooled: frozenset[str],
) -> _Envelope:
    """Per-declaration authority only: may this member have this SKU, on this date?

    Not ``discovery.compatible_needs``, and the difference is the refusal codes. That
    function returns survivors, which is all a costing pass needs; a strategy summary has
    to be able to say *eleven were refused, nine of them on grind*, and a count of
    survivors cannot say that. The authority is identical — the same pure
    ``evaluate_compatibility`` and ``evaluate_timing`` the matcher calls — so this
    aggregates differently, it does not decide differently.

    A declaration from another Community is skipped rather than counted as an exclusion:
    it was never a candidate, and reporting it would leak that a neighbouring Community
    has demand at all (§9).
    """
    kept: list[NeedDeclaration] = []
    exclusions: dict[str, int] = {}
    excluded = 0
    current = 0
    future = 0

    def refuse(code: str) -> None:
        nonlocal excluded
        excluded += 1
        exclusions[code] = exclusions.get(code, 0) + 1

    for need in sorted(ctx.repo.list_needs(ctx.ws), key=lambda n: n.id):
        if need.community_id != community_id:
            continue
        if not in_scope(ctx, need, target):
            # Never a candidate under any policy, so not an exclusion either. See
            # :func:`in_scope` — counting these would report the size of the Community's
            # unrelated demand as though it were a fact about this option.
            continue
        if not need.active:
            refuse(EXCLUDED_RETIRED)
            continue
        if need.household_id in already_pooled:
            refuse(EXCLUDED_ALREADY_POOLED)
            continue
        declared = ctx.repo.get_product(ctx.ws, need.product_id)
        if declared is None:
            refuse(EXCLUDED_UNKNOWN_PRODUCT)
            continue

        verdict = evaluate_compatibility(
            target=target,
            candidate=declared,
            need=need,
            # No price is applied here. A member's per-unit ceiling is a rule about a
            # specific tier's price, and which tier wins is evaluation's answer — so
            # applying one tier's price now would refuse people on the strength of an
            # offer that may not be the one they are measured against.
            facts=ctx.product_facts,
        )
        if not verdict.compatible:
            refuse(verdict.code.value)
            continue

        timing = evaluate_timing(need, purchase_date)
        if not timing.eligible:
            refuse(EXCLUDED_TIMING)
            continue
        if timing.is_future_pull_forward and not include_future_demand:
            refuse(EXCLUDED_FUTURE_NOT_REQUESTED)
            continue

        kept.append(need)
        if timing.is_future_pull_forward:
            future += need.quantity
        else:
            current += need.quantity

    return _Envelope(kept, exclusions, excluded, current, future)


def _candidate_targets(ctx: PoolContext, objective: StrategyObjective) -> list[str]:
    """Every exact SKU worth building a strategy around, in a stable order.

    For a **member** objective the authority is the member's own declarations: a target
    is a candidate only when that member's stated rule already permits it, which is
    ``coordination.sourceable_targets_for_need`` and nothing new. For a **community**
    scan there is no anchor, so the candidates are every product this deployment can
    actually source and something in the Community has declared against.
    """
    if objective.kind == OBJECTIVE_MEMBER:
        needs = [
            n
            for n in sorted(ctx.repo.list_needs(ctx.ws), key=lambda n: n.id)
            if n.active
            and n.household_id == objective.household_id
            and n.community_id == objective.community_id
            and (not objective.need_id or n.id == objective.need_id)
        ]
        out: list[str] = []
        for need in needs:
            for target_id in coord.sourceable_targets_for_need(ctx, need):
                if target_id not in out:
                    out.append(target_id)
        return out

    out = []
    for product in sorted(ctx.repo.list_products(ctx.ws), key=lambda p: p.id):
        if coord.offers_for(ctx, product.id)[1]:
            out.append(product.id)
    return out


def _build(
    ctx: PoolContext,
    *,
    objective: StrategyObjective,
    community: Community,
    target_id: str,
    purchase_date: date,
    include_future_demand: bool,
) -> CohortStrategy | None:
    """One strategy, or ``None`` when this SKU is not a coordination option at all.

    Three ways to be no option, and each is a fact known here rather than a verdict
    withheld from evaluation: nothing to buy it against, nobody it may be bought for, or
    nowhere to hand it over. Generating a strategy in any of those states would be
    offering an investigation whose answer is already on the table.
    """
    target = ctx.repo.get_product(ctx.ws, target_id)
    if target is None:
        return None
    retail, bulk = coord.offers_for(ctx, target_id)
    if retail is None or not bulk:
        return None

    envelope = _envelope(
        ctx,
        community_id=community.id,
        target=target,
        purchase_date=purchase_date,
        include_future_demand=include_future_demand,
        already_pooled=frozenset(
            coord.pooled_household_ids(ctx, community.id, target_id)
        ),
    )
    if not envelope.needs:
        return None

    households = sorted({n.household_id for n in envelope.needs})
    site_id, site_name = discovery.suggest_site(ctx, community.id, households)
    if not site_id:
        return None
    site = ctx.repo.get_site(ctx.ws, site_id)
    if site is None:
        return None

    schema = ctx.product_facts.family_schema(target.substitute_group)
    facts = ctx.product_facts.facts_for(target.id)

    return CohortStrategy(
        id=_strategy_id(
            community_id=community.id,
            objective=objective,
            target_product_id=target_id,
            pickup_site_id=site_id,
            include_future_demand=include_future_demand,
        ),
        community_id=community.id,
        objective_kind=objective.kind,
        objective_household_id=objective.household_id,
        objective_need_id=objective.need_id,
        target_product_id=target.id,
        target_product_name=target.display_name,
        product_family=target.substitute_group,
        attribute_schema_version=schema.version if schema else 0,
        # Verified facts only. An unverified value is not evidence anywhere else in this
        # system and does not become evidence by being put in a summary (§21).
        target_attributes={
            key: fact.value for key, fact in sorted(facts.items()) if fact.is_authoritative
        },
        pickup_site_id=site_id,
        pickup_site_name=site_name,
        include_future_demand=include_future_demand,
        candidate_need_ids=[n.id for n in envelope.needs][:MAX_STRATEGY_NEED_REFS],
        compatible_declaration_count=len(envelope.needs),
        household_count=len(households),
        compatible_units=sum(n.quantity for n in envelope.needs),
        current_units=envelope.current_units,
        future_units=envelope.future_units,
        excluded_declaration_count=envelope.excluded_count,
        exclusion_codes=dict(sorted(envelope.exclusions.items())),
        bulk_tier_count=len(bulk),
        lowest_minimum_units=min(o.min_units for o in bulk),
        input_fingerprint=input_fingerprint(
            ctx, community=community, target=target, site=site
        ),
    )


def _rank(strategy: CohortStrategy) -> tuple:
    """Stable ordering, and deliberately not a judgement.

    Larger envelopes first, because that is the only thing knowable here that correlates
    with a strategy being worth anything at all, and the cap has to cut somewhere. It
    orders; it does not score. Two strategies with the same envelope are separated by the
    product id so the sequence is reproducible across processes.
    """
    return (
        -strategy.compatible_units,
        -strategy.compatible_declaration_count,
        strategy.target_product_id,
    )


def generate_strategies(
    *,
    ctx: PoolContext,
    objective: StrategyObjective,
    include_future_demand: bool = True,
    limit: int = MAX_COHORT_STRATEGIES,
    persist: bool = True,
) -> list[CohortStrategy]:
    """Every bounded coordination option this objective has, ranked and capped.

    Deterministic in the strong sense: the same authoritative state produces the same
    strategies, in the same order, with the same ids. Nothing here is sampled, and
    nothing is invented — every SKU comes from the product table, every member from a
    declaration they wrote, every attribute from a committed fact, and every supplier
    minimum from a stored offer.
    """
    community = ctx.community(objective.community_id)
    purchase_date = next_pool_day(ctx.now.date(), community.schedule)
    built: list[CohortStrategy] = []
    for target_id in _candidate_targets(ctx, objective):
        strategy = _build(
            ctx,
            objective=objective,
            community=community,
            target_id=target_id,
            purchase_date=purchase_date,
            include_future_demand=include_future_demand,
        )
        if strategy is not None:
            built.append(strategy)

    built.sort(key=_rank)
    kept = built[: max(0, min(limit, MAX_COHORT_STRATEGIES))]
    if len(built) > len(kept):
        # Never a silent truncation: a listing that quietly drops options reads as "these
        # are all the options", which is a different and false claim (AGENTS.md §8).
        ctx.log(
            "strategies_generated",
            f"{len(kept)} of {len(built)} coordination options kept",
            {
                "objective_kind": objective.kind,
                "generated": len(built),
                "kept": len(kept),
                "dropped": len(built) - len(kept),
            },
        )
    if persist:
        for strategy in kept:
            ctx.repo.put_cohort_strategy(ctx.ws, strategy)
    return kept


# ------------------------------------------------------------------------ evaluation


def evaluate_strategy(*, ctx: PoolContext, strategy_id: str) -> StrategyEvaluation:
    """Cost one strategy against **current** authoritative state, and store the evidence.

    Nothing stored on the strategy is trusted. The product, the site, the offers, the
    declarations, the curated facts and the Community's own fee configuration are all
    reloaded, and the strategy contributes exactly two things: which SKU and site to ask
    about, and the fingerprint of the world it was generated from — which is compared,
    not believed.

    Read-only. It contacts nobody, commits no money and creates no pool.
    """
    strategy = ctx.repo.get_cohort_strategy(ctx.ws, strategy_id)
    if strategy is None:
        raise CoordinationError(f"unknown strategy: {strategy_id}")
    community = ctx.community(strategy.community_id)

    evaluation = StrategyEvaluation(
        id=new_id("seval"),
        strategy_id=strategy.id,
        community_id=strategy.community_id,
        target_product_id=strategy.target_product_id,
        target_product_name=strategy.target_product_name,
        objective_need_id=strategy.objective_need_id,
        strategy_fingerprint=strategy.input_fingerprint,
        pickup_site_id=strategy.pickup_site_id,
        pickup_site_name=strategy.pickup_site_name,
        quote_max_age_hours=community.quote_max_age_hours,
        radius_km=coord.formation_radius_km(community),
    )

    target = ctx.repo.get_product(ctx.ws, strategy.target_product_id)
    site = ctx.repo.get_site(ctx.ws, strategy.pickup_site_id)
    if target is None:
        return _store(ctx, _blocked(evaluation, BLOCKER_TARGET_MISSING, "product no longer exists"))
    if site is None or site.community_id != strategy.community_id:
        return _store(
            ctx, _blocked(evaluation, BLOCKER_SITE_MISSING, "pickup site no longer available")
        )

    current = input_fingerprint(ctx, community=community, target=target, site=site)
    evaluation.input_fingerprint = current
    evaluation.stale = current != strategy.input_fingerprint
    if evaluation.stale:
        # Reported, not fatal. The verdict below is still an honest answer about the
        # world as it is now; what has expired is the *summary* somebody chose from, and
        # saying so is more useful than refusing to look.
        evaluation.stale_reason = "authoritative inputs changed since this option was listed"

    assessment = coord.evaluate_opportunity(
        ctx=ctx,
        community_id=strategy.community_id,
        product_id=target.id,
        pickup_site_id=site.id,
        include_future_demand=strategy.include_future_demand,
        exclude_household_ids=frozenset(
            coord.pooled_household_ids(ctx, strategy.community_id, target.id)
        ),
    )
    _record(
        evaluation,
        assessment,
        in_scope_need_ids=frozenset(
            n.id
            for n in ctx.repo.list_needs(ctx.ws)
            if n.community_id == strategy.community_id and in_scope(ctx, n, target)
        ),
    )

    if assessment.viable:
        # Freshness is checked against the tier that actually won, because that is the
        # quote a buyer would be charged against. `offers_for` already drops offers past
        # their stated expiry; this is the Community's own maximum age, which is the rule
        # a final offer is held to (§43) and therefore the rule an option has to meet
        # before it is worth taking to a human.
        offer = next(
            (o for o in ctx.repo.list_offers(ctx.ws) if o.id == assessment.bulk_offer_id), None
        )
        age = offer.age_hours(ctx.now) if offer is not None else None
        evaluation.quote_age_hours = round(age, 3) if age is not None else 0.0
        if offer is None or age is None or age > community.quote_max_age_hours:
            return _store(
                ctx,
                _blocked(
                    evaluation,
                    BLOCKER_QUOTE_STALE,
                    "the supplier quote is older than this community allows",
                ),
            )

    evaluation.viable = assessment.viable
    evaluation.blocker_code = BLOCKER_NONE if assessment.viable else assessment.reason_code
    evaluation.blocker_reason = "" if assessment.viable else assessment.reason
    return _store(ctx, evaluation)


def _blocked(evaluation: StrategyEvaluation, code: str, reason: str) -> StrategyEvaluation:
    evaluation.viable = False
    evaluation.blocker_code = code
    evaluation.blocker_reason = reason
    return evaluation


def _store(ctx: PoolContext, evaluation: StrategyEvaluation) -> StrategyEvaluation:
    ctx.repo.put_strategy_evaluation(ctx.ws, evaluation)
    return evaluation


def _record(
    evaluation: StrategyEvaluation,
    assessment: coord.OpportunityAssessment,
    *,
    in_scope_need_ids: frozenset[str],
) -> None:
    """Copy the deterministic services' own figures onto the stored evidence.

    Copies. Nothing here recomputes money, units, or a verdict — every number below was
    produced by ``economics.price_pool`` or ``fit_to_cases`` or the matcher, and the only
    arithmetic performed is counting things that are already decided (AGENTS.md §5).
    """
    econ = assessment.economics
    evaluation.distribution_day = assessment.distribution_day
    evaluation.routing_provider = assessment.routing_provider
    evaluation.avg_travel_minutes = assessment.avg_travel_minutes
    evaluation.max_travel_minutes = assessment.max_travel_minutes
    evaluation.retail_offer_id = assessment.retail_offer_id or ""
    evaluation.bulk_offer_id = assessment.bulk_offer_id or ""
    evaluation.offers_considered = assessment.offers_considered[:MAX_STRATEGY_TIERS]
    evaluation.matched_units = assessment.matched_units
    evaluation.minimum_units = assessment.minimum_units
    evaluation.current_units = assessment.current_units
    evaluation.future_units = assessment.future_units

    if econ is not None:
        evaluation.selected_units = econ.packages.units_purchased
        evaluation.cases = econ.packages.cases
        evaluation.case_units = econ.packages.case_units
        evaluation.surplus_units = econ.packages.surplus_units
        evaluation.all_in_cents = econ.all_in_cents
        evaluation.retail_baseline_cents = econ.retail_baseline_cents
        evaluation.net_savings_cents = econ.net_savings_cents
        evaluation.net_savings_bps = econ.net_savings_bps
        evaluation.host_compensation_cents = econ.host_compensation_cents
        evaluation.platform_fee_cents = econ.platform_fee_cents
        evaluation.processing_fee_cents = econ.payment_processing_cents

    evaluation.auto_join_count = sum(
        1 for c in assessment.candidates if c.verdict.eligible_for_auto_join
    )
    evaluation.approval_required_count = (
        len(assessment.candidates) - evaluation.auto_join_count
    )

    # Who would have been in the order. Candidate assessments only exist once pricing
    # succeeded, and a refusal on landed economics happens *after* a buyer set was
    # chosen and costed — so on that path the buyer lines are the honest answer and an
    # empty list would report "nobody was in it", which is a different and false claim.
    # Smart Join is not evaluated on that path at all, which is why the two counts above
    # stay zero rather than being inferred from the lines.
    if assessment.candidates:
        eligible = [c.need_id for c in assessment.candidates]
    elif econ is not None:
        eligible = [line.need_id for line in econ.lines]
    else:
        eligible = []
    evaluation.selected_member_count = len(eligible)
    evaluation.eligible_need_count = len(eligible)
    evaluation.eligible_need_ids = eligible[:MAX_STRATEGY_NEED_REFS]
    evaluation.includes_objective_need = bool(evaluation.objective_need_id) and (
        evaluation.objective_need_id in eligible
    )

    codes: dict[str, int] = {}
    excluded: list[dict[str, Any]] = []
    for row in assessment.rejected:
        # In-scope only, for the reason :func:`in_scope` gives: a declaration no policy
        # could ever admit is not an exclusion, it is somebody else's shopping.
        if row.get("need_id") not in in_scope_need_ids:
            continue
        code = row.get("code") or "other"
        codes[code] = codes.get(code, 0) + 1
        # Need id and code only. Which household was refused, and for what, is that
        # member's business and not a readout for whoever asked the question (§4).
        excluded.append(
            {
                "need_id": row.get("need_id", ""),
                "code": code,
                "attribute": row.get("attribute", ""),
            }
        )
    evaluation.excluded_count = len(excluded)
    evaluation.excluded = excluded[:MAX_STRATEGY_NEED_REFS]
    evaluation.exclusion_codes = dict(sorted(codes.items()))


# ------------------------------------------------------------------------ staleness


@dataclass(frozen=True)
class ActionableCheck:
    """Whether one stored evaluation may still be acted on.

    The guard a mutation has to pass. Evidence is a snapshot, and a snapshot taken before
    a supplier requoted or a member amended their rule is not authority for spending
    anybody's money — however recently it was computed and however viable it said things
    were.
    """

    ok: bool
    code: str
    reason: str
    strategy_id: str = ""
    evaluation_id: str = ""


ACTIONABLE_UNKNOWN_STRATEGY = "unknown_strategy"
ACTIONABLE_UNKNOWN_EVALUATION = "unknown_evaluation"
ACTIONABLE_MISMATCHED = "evaluation_is_for_another_strategy"
ACTIONABLE_NOT_VIABLE = "evaluation_refused"
ACTIONABLE_STALE = "evidence_stale"


def ensure_actionable(
    *, ctx: PoolContext, strategy_id: str, evaluation_id: str
) -> ActionableCheck:
    """Re-derive, from scratch, whether stored evidence still describes the world.

    Deliberately a separate read rather than a flag on the evaluation. A boolean written
    at evaluation time answers "was this true then", and the only question a mutation
    cares about is "is this true now" — so the fingerprint is recomputed here against
    current state, and an evaluation that was viable an hour ago fails this check the
    moment anything it depended on moved.

    Phase 3 composes this with ``coordination.create_candidate_pool``. It is deliberately
    not composed here: this phase creates no pools, and a mutation nobody asked for is a
    mutation nobody reviewed.
    """
    strategy = ctx.repo.get_cohort_strategy(ctx.ws, strategy_id)
    if strategy is None:
        return ActionableCheck(False, ACTIONABLE_UNKNOWN_STRATEGY, "no such strategy")

    evaluation = ctx.repo.get_strategy_evaluation(ctx.ws, evaluation_id)
    if evaluation is None:
        return ActionableCheck(
            False, ACTIONABLE_UNKNOWN_EVALUATION, "no such evaluation", strategy_id
        )
    if evaluation.strategy_id != strategy_id:
        return ActionableCheck(
            False,
            ACTIONABLE_MISMATCHED,
            "that evaluation is evidence about a different option",
            strategy_id,
            evaluation_id,
        )
    if not evaluation.viable:
        return ActionableCheck(
            False,
            ACTIONABLE_NOT_VIABLE,
            evaluation.blocker_reason or "this option was refused",
            strategy_id,
            evaluation_id,
        )

    community = ctx.community(strategy.community_id)
    target = ctx.repo.get_product(ctx.ws, strategy.target_product_id)
    site = ctx.repo.get_site(ctx.ws, strategy.pickup_site_id)
    if target is None or site is None:
        return ActionableCheck(
            False, ACTIONABLE_STALE, "the option no longer resolves", strategy_id, evaluation_id
        )
    if input_fingerprint(ctx, community=community, target=target, site=site) != (
        evaluation.input_fingerprint
    ):
        return ActionableCheck(
            False,
            ACTIONABLE_STALE,
            "the world changed after this evidence was recorded",
            strategy_id,
            evaluation_id,
        )
    return ActionableCheck(True, "", "", strategy_id, evaluation_id)


# ----------------------------------------------------------------------- projections


def strategy_summary(strategy: CohortStrategy) -> dict[str, Any]:
    """The compact form of one option, for a caller choosing what to investigate.

    Selects and aggregates; it computes nothing (AGENTS.md §5). It carries every fact
    generation actually established — the SKU and its curated attributes, how much
    demand its own authority admits, how that demand splits between now and pulled
    forward, how many declarations it refused and under which codes, where it would be
    handed over, and the lowest minimum any supplier will sell at.

    It does not carry a verdict, because at this point there is no verdict to carry:
    which tier wins, whether the demand fills whole cases, what the landed price is and
    whether that beats buying alone are set-level facts nothing here has computed. It
    also carries no price, since a price with no case structure or host estimate beside
    it is a number that invites exactly the arithmetic §5 forbids.

    No household ids, no need ids, no names, no coordinates.
    """
    return {
        "strategy_id": strategy.id,
        "product_id": strategy.target_product_id,
        "product": strategy.target_product_name,
        "product_family": strategy.product_family,
        "attributes": dict(strategy.target_attributes),
        "compatible_declarations": strategy.compatible_declaration_count,
        "compatible_units": strategy.compatible_units,
        "current_units": strategy.current_units,
        "future_units": strategy.future_units,
        "relies_on_pull_forward": strategy.future_units > 0,
        "excluded_declarations": strategy.excluded_declaration_count,
        "exclusion_codes": dict(strategy.exclusion_codes),
        "pickup_site": strategy.pickup_site_name,
        "bulk_tiers": strategy.bulk_tier_count,
        "lowest_supplier_minimum_units": strategy.lowest_minimum_units,
        "includes_objective_declaration": strategy.includes_objective_need,
    }


def evaluation_summary(evaluation: StrategyEvaluation) -> dict[str, Any]:
    """The compact form of one authoritative verdict.

    Every decision-critical fact survives: the verdict, the blocking code, how much
    demand there was against how much the supplier required, the case structure, the
    money, how many buyers Smart Join would admit without asking, and whether the
    declaration that triggered the question is inside the result. Dropping any of those
    to save tokens would buy the saving with wrong decisions (§5).

    Counts, never a roster. Which specific neighbour was excluded is not an answer to
    anybody else's question.
    """
    return {
        "strategy_id": evaluation.strategy_id,
        "evaluation_id": evaluation.id,
        "viable": evaluation.viable,
        "blocker_code": evaluation.blocker_code,
        "blocker_reason": evaluation.blocker_reason,
        "stale": evaluation.stale,
        "product": evaluation.target_product_name,
        "pickup_site": evaluation.pickup_site_name,
        "distribution_day": evaluation.distribution_day,
        "matched_units": evaluation.matched_units,
        "minimum_units": evaluation.minimum_units,
        "selected_units": evaluation.selected_units,
        "selected_members": evaluation.selected_member_count,
        "cases": evaluation.cases,
        "case_units": evaluation.case_units,
        "surplus_units": evaluation.surplus_units,
        "all_in_display": format_cents(evaluation.all_in_cents),
        "retail_baseline_display": format_cents(evaluation.retail_baseline_cents),
        "net_savings_display": format_cents(evaluation.net_savings_cents),
        "net_savings_pct": bps_to_pct_str(evaluation.net_savings_bps),
        "auto_join_count": evaluation.auto_join_count,
        "approval_required_count": evaluation.approval_required_count,
        "includes_objective_declaration": evaluation.includes_objective_need,
        "excluded_declarations": evaluation.excluded_count,
        "exclusion_codes": dict(evaluation.exclusion_codes),
    }
