"""Which of the approved questions are worth asking about one product.

Every product in a curated family *could* be asked about every dimension the family
defines. Doing that is a settings form: three controls, the same three every time,
regardless of whether any answer would change what Pool can do for the person filling it
in. The interesting question is the other one — **which of these actually matter here** —
and it depends on the world rather than on the schema.

So this module answers two things, and the split between them is the whole design.

**What the facts are.** For each approved question: the selected product's own verified
value, the answers the schema permits, and — the decision-critical part — how many
products this deployment can actually source, and how much standing demand, each answer
would let the member combine with. Those are counts over stored rows. Nothing here scores,
ranks, recommends, or labels a winner.

**Which to ask.** Not decided here. A bounded run reads the facts above and returns an
ordered subset of approved question *ids* (``agent/tools.set_preference_question_plan``).
It cannot add a question, reword one, or change what an answer means, because the only
thing it supplies is a list of ids that must already be in the approved set.

The reason the model gets this at all is that "which uncertainty is worth a person's
attention" is a judgement, and "what counts as compatible" is not (AGENTS.md §5).

**Cost.** A plan is identified by a digest of the household, the product and the world it
was made against, so reopening a form in an unchanged world is a primary-key read and buys
no model call. Editing answers never replans. Nothing here runs on render, on reload, or
on a checkbox (§3.3).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from ..data import product_facts
from ..domain.models import (
    MAX_CLARIFICATION_QUESTIONS,
    ClarificationPlan,
    ClarificationPlanStatus,
    iso,
    utcnow,
)
from . import coordination as coord
from .context import PoolContext


class ClarificationError(ValueError):
    """A plan the approved set will not accept. Carries a human reason."""


@dataclass(frozen=True)
class QuestionCandidate:
    """One approved question, with the facts that make it worth asking — or not.

    ``answers`` carries, per approved answer, how much of the world that answer would
    let this member combine with. Two counts and no verdict: a reader has to weigh
    "narrowing this excludes three of the six things Pool can buy" against "narrowing
    this excludes one", and nothing here does that weighing for them.
    """

    question_id: str
    attribute: str
    kind: str
    prompt: str
    hint: str
    product_value: str
    product_value_label: str
    #: ``{answer -> {"values": [...], "sourceable_products": n, "standing_requests": n,
    #: "standing_units": n}}`` — the narrow answer and the widest one.
    answers: dict[str, dict[str, Any]]
    #: The same figures for each individual allowed value, so a member weighing "would
    #: dark do as well?" can be shown what that one answer reaches without any screen
    #: computing it. Stored aggregates, never a prediction.
    options: dict[str, dict[str, Any]]
    #: Whether the products this deployment can source actually differ on this dimension.
    #: When they do not, the answer cannot change anybody's cohort.
    varies_among_sourceable: bool
    schema_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "attribute": self.attribute,
            "kind": self.kind,
            "product_value": self.product_value,
            "answers": self.answers,
            "options": self.options,
            "varies_among_sourceable": self.varies_among_sourceable,
            "schema_required": self.schema_required,
        }


ANSWER_KEEP = "keep"
ANSWER_ANY = "any"


def candidates(
    ctx: PoolContext, community_id: str, product_id: str, household_id: str = ""
) -> list[QuestionCandidate]:
    """Every approved question this product can be asked, with its factual context.

    Only attributes the selected product carries a **verified** fact for. Asking somebody
    to insist on a value Pool cannot establish would build a rule that refuses everything,
    and asking about a fact nobody has confirmed would be asking them to guess (§21).

    Order is the schema's declaration order, which is stable and is deliberately *not* a
    ranking — a caller that wanted the most consequential question first would have to
    read the counts and decide, which is the point.

    ``household_id`` is excluded from the demand counts, and both reasons matter. It is
    circular — the questions exist to establish what *this* member will accept, so their
    own standing request is not evidence about which question to ask them. And it is what
    keeps the plan stable across their own edits: the fingerprint is taken over these
    counts, so a member who narrows and re-widens would otherwise move the world they are
    being asked about and buy a second model call for an answer that cannot have changed.
    """
    product = ctx.repo.get_product(ctx.ws, product_id)
    if product is None:
        return []
    schema = ctx.product_facts.family_schema(product.substitute_group)
    if schema is None:
        return []
    facts = ctx.product_facts.facts_for(product_id)

    sourceable = _sourceable_in_family(ctx, product.substitute_group)
    demand = _standing_requests_by_product(
        ctx, community_id, product.substitute_group, exclude_household=household_id
    )

    out: list[QuestionCandidate] = []
    for definition in schema.attributes:
        fact = facts.get(definition.key)
        if fact is None or not fact.is_authoritative:
            continue
        question = product_facts.question_for(definition.key)
        if question is None:
            continue

        keep_values = (fact.value,)
        any_values = tuple(sorted(definition.allowed_values))
        answers = {
            ANSWER_KEEP: _reach(ctx, sourceable, demand, definition.key, keep_values),
            ANSWER_ANY: _reach(ctx, sourceable, demand, definition.key, any_values),
        }
        answers[ANSWER_KEEP]["values"] = list(keep_values)
        answers[ANSWER_ANY]["values"] = list(any_values)

        # One entry per allowed value, so the *consequence of each choice* is a stored
        # figure rather than something a screen adds up. A member ticking two roasts is
        # not reaching the sum of two rows — a product can only carry one value for an
        # attribute here, so per-value rows do compose, but the composing is the server's
        # to state and a client that summed them would be re-deriving demand.
        options = {
            value: _reach(ctx, sourceable, demand, definition.key, (value,))
            for value in sorted(definition.allowed_values)
        }

        values_present = {
            v
            for pid in sourceable
            if (v := _value_of(ctx, pid, definition.key)) is not None
        }
        label = product_facts.label_for(definition.key, fact.value)
        out.append(
            QuestionCandidate(
                question_id=question.id,
                attribute=definition.key,
                kind=question.kind,
                prompt=question.prompt.replace("{value}", label.lower()),
                hint=question.hint,
                product_value=fact.value,
                product_value_label=label,
                answers=answers,
                options=options,
                varies_among_sourceable=len(values_present) > 1,
                schema_required=definition.required_for_compatibility,
            )
        )
    return out


def _value_of(ctx: PoolContext, product_id: str, attribute: str) -> str | None:
    fact = ctx.product_facts.facts_for(product_id).get(attribute)
    return fact.value if fact is not None and fact.is_authoritative else None


def _sourceable_in_family(ctx: PoolContext, family: str) -> list[str]:
    """Products in this family the deployment holds a usable bulk quote for.

    The same ``offers_for`` the evaluator consults, so a product counted here is one an
    opportunity assessment could genuinely price. Nothing is fabricated to make a count
    larger.
    """
    return sorted(
        p.id
        for p in ctx.repo.list_products(ctx.ws)
        if p.substitute_group == family and coord.offers_for(ctx, p.id)[1]
    )


def _standing_requests_by_product(
    ctx: PoolContext, community_id: str, family: str, exclude_household: str = ""
) -> dict[str, dict[str, int]]:
    """Standing demand in this Community for each product in the family.

    Two aggregates per product, because they answer different questions: how many
    *people* are asking, and how many *units* they are asking for. A supplier minimum is
    denominated in units, so the second is the one a member weighing "would another roast
    do?" is actually deciding about — and the first is the one that says whether that
    demand is one household or six.

    Counts, and only counts. Which household declared what is that household's business
    and is never returned from here (AGENTS.md §4).
    """
    out: dict[str, dict[str, int]] = {}
    for need in ctx.repo.list_needs(ctx.ws):
        if not need.active or need.community_id != community_id:
            continue
        if exclude_household and need.household_id == exclude_household:
            continue
        declared = ctx.repo.get_product(ctx.ws, need.product_id)
        if declared is None or declared.substitute_group != family:
            continue
        row = out.setdefault(declared.id, {"requests": 0, "units": 0})
        row["requests"] += 1
        row["units"] += max(0, int(need.quantity))
    return out


def _reach(
    ctx: PoolContext,
    sourceable: list[str],
    demand: dict[str, dict[str, int]],
    attribute: str,
    values: tuple[str, ...],
) -> dict[str, Any]:
    """What one answer would let this member reach: products, and the demand behind them.

    Deliberately several numbers rather than one. "Three of the six things Pool can buy"
    and "eleven of the fourteen standing requests" can point in different directions, and
    collapsing them into a score would be this module deciding which mattered.

    Every figure is a count over stored rows at this moment. None of them is a prediction:
    whether an order forms depends on prices, case sizes and supplier minimums that the
    evaluator checks against a chosen buyer set, long after this.
    """
    allowed = set(values)
    products = [p for p in sourceable if _value_of(ctx, p, attribute) in allowed]
    rows = [demand.get(p, {}) for p in products]
    return {
        "sourceable_products": len(products),
        "standing_requests": sum(int(r.get("requests", 0)) for r in rows),
        "standing_units": sum(int(r.get("units", 0)) for r in rows),
    }


# ------------------------------------------------------------------------ the plan


def plan_fingerprint(
    ctx: PoolContext, community_id: str, product_id: str, offered: list[QuestionCandidate]
) -> str:
    """A digest of everything that could change *which question is worth asking*.

    Not the same inputs a compatibility fingerprint covers, and deliberately narrower: a
    supplier changing a price does not change which uncertainty matters to a person, and
    replanning for it would buy a model call for nothing. What does change it is the
    product, the schema, the approved question set, and the shape of what is sourceable
    and declared around it — which is exactly what the candidates already summarise.
    """
    return hashlib.sha256(
        json.dumps(
            {
                "community": community_id,
                "product": product_id,
                "questions_version": product_facts.QUESTION_DEFINITION_VERSION,
                "candidates": [c.to_dict() for c in offered],
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]


def plan_id_for(household_id: str, product_id: str, fingerprint: str) -> str:
    return "cpl_" + hashlib.sha256(
        f"{household_id}|{product_id}|{fingerprint}".encode()
    ).hexdigest()[:16]


def existing_plan(
    ctx: PoolContext, community_id: str, household_id: str, product_id: str
) -> tuple[ClarificationPlan | None, list[QuestionCandidate]]:
    """The still-valid plan for this member and product, and the candidates it was made from.

    A primary-key read. Reopening a form in an unchanged world finds this and spends
    nothing; a world that moved enough to change which question matters produces a
    different id and finds nothing, which is when — and only when — a run is warranted.
    """
    offered = candidates(ctx, community_id, product_id, household_id)
    if not offered:
        return None, offered
    fingerprint = plan_fingerprint(ctx, community_id, product_id, offered)
    plan = ctx.repo.get_clarification_plan(
        ctx.ws, plan_id_for(household_id, product_id, fingerprint)
    )
    if plan is None or not plan.is_active:
        return None, offered
    return plan, offered


def supersede_others(
    ctx: PoolContext, household_id: str, product_id: str, keep_id: str
) -> None:
    """Retire this member's older plans for the same product. Kept, never deleted."""
    for plan in ctx.repo.list_clarification_plans(ctx.ws):
        if (
            plan.household_id == household_id
            and plan.product_id == product_id
            and plan.id != keep_id
            and plan.is_active
        ):
            plan.status = ClarificationPlanStatus.SUPERSEDED.value
            ctx.repo.put_clarification_plan(ctx.ws, plan)


def record_plan(
    ctx: PoolContext,
    *,
    community_id: str,
    household_id: str,
    product_id: str,
    question_ids: list[str],
    run_id: str = "",
) -> ClarificationPlan:
    """Store an ordered subset of approved question ids. Raises on anything else.

    Every clause below refuses a way of getting a question into a plan that the approved
    set did not put there: an invented id, one from another family, one for an attribute
    this product carries no verified fact for, a repeat, or more than the cap. The plan is
    the only thing a model writes in this phase, and this is the whole of what makes that
    safe.
    """
    offered = candidates(ctx, community_id, product_id, household_id)
    if not offered:
        raise ClarificationError("this product has nothing that can be clarified")
    allowed = {c.question_id: c for c in offered}

    if len(question_ids) > MAX_CLARIFICATION_QUESTIONS:
        raise ClarificationError(
            f"a plan may name at most {MAX_CLARIFICATION_QUESTIONS} questions"
        )
    seen: set[str] = set()
    for question_id in question_ids:
        if question_id not in allowed:
            raise ClarificationError(f"{question_id!r} is not a question this product offers")
        if question_id in seen:
            raise ClarificationError(f"{question_id!r} appears twice")
        seen.add(question_id)

    product = ctx.repo.get_product(ctx.ws, product_id)
    schema = ctx.product_facts.family_schema(product.substitute_group) if product else None
    if product is None or schema is None:  # unreachable while candidates exist
        raise ClarificationError("this product is not in a curated family")

    fingerprint = plan_fingerprint(ctx, community_id, product_id, offered)
    plan = ClarificationPlan(
        id=plan_id_for(household_id, product_id, fingerprint),
        community_id=community_id,
        household_id=household_id,
        product_id=product_id,
        family=schema.family,
        schema_version=schema.version,
        question_definition_version=product_facts.QUESTION_DEFINITION_VERSION,
        input_fingerprint=fingerprint,
        question_ids=list(question_ids),
        candidate_question_ids=[c.question_id for c in offered],
        run_id=run_id,
        created_at=iso(utcnow()),
    )
    supersede_others(ctx, household_id, product_id, plan.id)
    ctx.repo.put_clarification_plan(ctx.ws, plan)
    return plan


# ------------------------------------------------------------------- consequences


def flexibility_context(
    ctx: PoolContext, community_id: str, household_id: str, product_id: str
) -> dict[str, Any]:
    """What each side of the exact-versus-alternatives choice would actually reach.

    Two counts over stored rows, and no prediction. Pool does not have a model of whether
    an order will form — the deterministic evaluator answers that only after a buyer set
    has been costed — so nothing here says "more likely" with a number attached. What it
    can say truthfully is how much *current* demand each choice could combine with, which
    is the fact a person is actually weighing.

    Aggregates only. No household, no name, no identifier of anybody else (§4).
    """
    product = ctx.repo.get_product(ctx.ws, product_id)
    if product is None:
        return {"exact_requests": 0, "compatible_requests": 0, "sourceable_alternatives": 0}

    exact = 0
    compatible = 0
    for need in ctx.repo.list_needs(ctx.ws):
        if not need.active or need.community_id != community_id:
            continue
        if need.household_id == household_id:
            continue
        declared = ctx.repo.get_product(ctx.ws, need.product_id)
        if declared is None:
            continue
        if declared.id == product_id:
            exact += 1
        if product.substitute_group and declared.substitute_group == product.substitute_group:
            compatible += 1

    alternatives = [
        p
        for p in _sourceable_in_family(ctx, product.substitute_group)
        if p != product_id
    ]
    return {
        "exact_requests": exact,
        # Everything in the family, including the exact product: "requests Pool could
        # potentially combine you with" is the honest reading, and excluding the exact
        # ones would make the broader number look smaller than it is.
        "compatible_requests": compatible,
        "sourceable_alternatives": len(alternatives),
    }
