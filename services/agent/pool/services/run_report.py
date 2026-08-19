"""What a run did about *your* declarations, in facts it actually established.

The consumer answer to **Run Pool now**. Not a developer console and not a trace: it
leads with what happened to the things this member told Pool they buy, and explains it
from :class:`~pool.domain.models.RunEvaluation` rows the run wrote down while it was
running (``agent/evidence.py``).

Four rules hold this together, and each of them is a way the feature could have been a
lie instead:

**Only this run.** Every fact is keyed to one ``run_id``. A report is refused for a run
that was not this member's, so a previous run — or somebody else's — can never become
the answer on their screen.

**Only what was evaluated.** If a run never costed detergent, no line about detergent
appears, however good it would look. "Not investigated" is a real, distinct outcome from
"investigated and declined", and a member with more declarations than one run takes on
is told which is which.

**Ownership is read, not inferred.** Whether the member is *in* the pool a run formed
comes from ``services.relevance`` — membership plus ``need_id`` lineage — exactly as it
does everywhere else. This module never decides it from a product name.

**No arithmetic invented here.** Every quantity and every sum below was computed by a
deterministic service during the run and stored. This assembles sentences around them;
it never derives a new one, and it never asks a model to write one (AGENTS.md §5, §24).
"""

from __future__ import annotations

from typing import Any

from ..domain.models import LIVE_PARTICIPATION_STATES, AgentRun, RunEvaluation
from ..domain.money import bps_to_pct_str, format_cents
from . import coordination as coord
from . import relevance
from .context import PoolContext

#: What a run concluded about one of this member's declarations.
RESULT_FORMED_INCLUDED = "formed_included"      # a pool formed and they are in it
RESULT_FORMED_EXCLUDED = "formed_excluded"      # it formed for this product, without them
RESULT_DECLINED = "declined"                    # investigated, and not worth doing
RESULT_NOT_INVESTIGATED = "not_investigated"    # the run did not reach it
RESULT_ALREADY_COORDINATED = "already_coordinated"  # its answer is a pool that exists
#: Worth doing, and not done *this* run. Pool forms at most one order per run so that
#: members hear from it rarely, so a second viable objective is genuinely next in line —
#: which is a different thing from being declined, and used to be reported as one.
RESULT_VIABLE_NOT_ACTED = "viable_not_acted"


def _unit_word(unit: str, count: int) -> str:
    return unit if count == 1 else f"{unit}s"


def _tier_facts(evaluation: RunEvaluation) -> list[str]:
    """The supplier comparison, when there was genuinely more than one tier."""
    tiers = evaluation.offers_considered or []
    if len(tiers) < 2 or not evaluation.bulk_offer_id:
        return []
    won = next((t for t in tiers if t.get("offer_id") == evaluation.bulk_offer_id), None)
    if won is None:
        return []
    others = [t for t in tiers if t.get("offer_id") != evaluation.bulk_offer_id]
    return [
        f"Pool compared {len(tiers)} supplier prices and took the one at "
        f"{format_cents(int(won.get('unit_price_cents', 0)))} a unit, ahead of "
        f"{format_cents(int(others[0].get('unit_price_cents', 0)))}."
    ]


def _why_it_worked(evaluation: RunEvaluation, unit: str) -> list[str]:
    """The four to six lines that make a formed order checkable rather than asserted."""
    facts: list[str] = []
    current, future = evaluation.current_units, evaluation.future_units
    # Three cases, not two. An order made entirely of demand brought forward is a real
    # and interesting outcome — and "0 bags were already due, and 18 more were bought
    # early" is a sentence that opens by telling somebody nothing.
    if current and future:
        facts.append(
            f"{current} {_unit_word(unit, current)} were already due, and {future} more "
            "were bought early under permission those members had already given."
        )
    elif future:
        facts.append(
            f"All {future} {_unit_word(unit, future)} were bought ahead of when those "
            "members actually need them — every one of them had authorised an early "
            "purchase if it saved money."
        )
    elif current:
        facts.append(
            f"{current} {_unit_word(unit, current)} were already due around now."
        )
    if evaluation.minimum_units:
        facts.append(
            f"Together that reached the supplier's {evaluation.minimum_units}-unit minimum."
        )
    if evaluation.cases:
        facts.append(
            f"It fills {evaluation.cases} complete "
            f"{'case' if evaluation.cases == 1 else 'cases'}"
            + (
                " with nothing left over."
                if evaluation.surplus_units == 0
                else f", leaving {evaluation.surplus_units} spare."
            )
        )
    facts.extend(_tier_facts(evaluation))
    if evaluation.pickup_site_name:
        covered = (
            f" — the best of {evaluation.sites_considered} pickup points for this group"
            if evaluation.sites_considered > 1
            else ""
        )
        facts.append(f"Collect from {evaluation.pickup_site_name}{covered}.")
    if evaluation.net_savings_cents > 0:
        facts.append(
            f"All in, {format_cents(evaluation.all_in_cents)} against "
            f"{format_cents(evaluation.retail_baseline_cents)} buying separately — "
            f"{bps_to_pct_str(evaluation.net_savings_bps)} less."
        )
    return facts


def _declined_headline(evaluation: RunEvaluation, unit: str) -> str:
    """Why this was not worth doing, from the deterministic reason code."""
    code = evaluation.reason_code
    if code == coord.REASON_BELOW_MINIMUM:
        return (
            f"{evaluation.matched_units} compatible "
            f"{_unit_word(unit, evaluation.matched_units)} were declared near you, and "
            f"the supplier will not sell fewer than {evaluation.minimum_units}."
        )
    if code == coord.REASON_NOT_CHEAPER:
        return (
            "There is enough demand, but buying it together would cost "
            f"{format_cents(evaluation.all_in_cents)} against "
            f"{format_cents(evaluation.retail_baseline_cents)} buying it alone."
        )
    if code == coord.REASON_NO_BULK_OFFER:
        return "No supplier Pool has verified sells this in bulk yet."
    if code == coord.REASON_NO_RETAIL_BASELINE:
        return "Pool has no verified shelf price to measure a bulk order against yet."
    if code == coord.REASON_NO_COMPATIBLE_DEMAND:
        return "Nobody near you has declared anything this order could be shared with."
    if code == coord.REASON_ROUTING_UNAVAILABLE:
        return "Pool could not work out travel times for this one, so it did not act."
    return evaluation.reason or "Pool found nothing worth coordinating for this one."


def _verdict_for(evaluation: RunEvaluation, need_id: str) -> dict[str, Any] | None:
    for row in evaluation.need_verdicts:
        if row.get("need_id") == need_id:
            return row
    return None


def _result_for_need(
    ctx: PoolContext,
    *,
    need,
    product,
    evaluations: list[RunEvaluation],
    personal: dict[str, Any],
) -> dict[str, Any]:
    """One declaration's outcome in this run."""
    unit = product.unit if product else "unit"
    name = product.name if product else need.product_id
    base = {
        "need_id": need.id,
        "product_id": need.product_id,
        "product_name": name,
        "quantity": need.quantity,
        "unit": unit,
        "pool_id": "",
        "units": 0,
        "reason_code": "",
        "is_exact_product": True,
        "declared_product_name": "",
        "facts": [],
    }

    mine = personal.get(need.id)
    if mine is not None:
        pool, membership = mine
        evaluation = next((e for e in evaluations if e.product_id == pool.product_id), None)
        substitute = pool.product_id != need.product_id
        return {
            **base,
            "result": RESULT_FORMED_INCLUDED,
            "pool_id": pool.id,
            "product_id": pool.product_id,
            "product_name": (
                ctx.repo.get_product(ctx.ws, pool.product_id).name
                if ctx.repo.get_product(ctx.ws, pool.product_id)
                else pool.product_id
            ),
            "units": membership.allocated_units,
            "participation_state": membership.state.value,
            "status": pool.status.value,
            "is_exact_product": membership.is_exact_product,
            "declared_product_name": name if substitute else "",
            "headline": (
                f"Pool put your {membership.allocated_units} "
                f"{_unit_word(unit, membership.allocated_units)} into a group order."
            ),
            "facts": _why_it_worked(evaluation, unit) if evaluation else [],
        }

    # Investigated, and this member is not in the result.
    for evaluation in evaluations:
        if need.id not in evaluation.need_ids:
            continue
        verdict = _verdict_for(evaluation, need.id)
        if evaluation.pool_id and verdict is not None and not verdict.get("included"):
            reason = relevance.plain_reason(str(verdict.get("reason", "")))
            return {
                **base,
                "result": RESULT_FORMED_EXCLUDED,
                "pool_id": evaluation.pool_id,
                "reason_code": evaluation.reason_code,
                "headline": (
                    f"Pool formed an order for {evaluation.product_name}, and your units "
                    "were not in this one."
                ),
                "facts": [
                    reason
                    or (
                        f"It filled {evaluation.cases} complete "
                        f"{'case' if evaluation.cases == 1 else 'cases'} exactly, and "
                        "your units did not fit inside the boundary."
                    ),
                    "Nothing was charged, and your declaration stays standing.",
                ],
            }
        if evaluation.viable:
            # Costed, worth doing, and not the one this run acted on. Reporting it as
            # "declined" would be false, and reporting the evaluator's own internal
            # sentence — "viable bulk opportunity" — would be worse.
            return {
                **base,
                "result": RESULT_VIABLE_NOT_ACTED,
                "reason_code": evaluation.reason_code,
                "headline": (
                    "Pool can form this one too, and forms one order at a time — so it "
                    "is next."
                ),
                "facts": [
                    f"{evaluation.selected_member_count} compatible members and "
                    f"{evaluation.selected_units} {_unit_word(unit, evaluation.selected_units)} "
                    f"are ready, against a {evaluation.minimum_units}-unit minimum."
                ]
                if evaluation.selected_units
                else [],
            }
        return {
            **base,
            "result": RESULT_DECLINED,
            "reason_code": evaluation.reason_code,
            "headline": _declined_headline(evaluation, unit),
            "facts": (
                [relevance.plain_reason(str(verdict.get("reason", "")))]
                if verdict is not None and verdict.get("reason")
                else []
            )
            + ["Your declaration stays standing, and Pool keeps watching."],
        }

    return {
        **base,
        "result": RESULT_NOT_INVESTIGATED,
        "headline": "Pool did not get to this one in this run.",
        "facts": [
            "It takes the most pressing few each time. This one stays standing for the "
            "next run."
        ],
    }


def build(
    ctx: PoolContext, community_id: str, run: AgentRun, household_id: str
) -> dict[str, Any]:
    """The consumer report for one run, for one member.

    ``is_mine`` is false when this run was not anchored to this member. The results list
    is then empty by construction: a community-wide scan answers nobody's button, and
    presenting its findings as a personal report is the failure this whole layer exists
    to prevent.
    """
    is_mine = bool(
        run.objective_kind == "member"
        and household_id
        and run.objective_household_id == household_id
    )
    report: dict[str, Any] = {
        "run_id": run.id,
        "trigger": run.trigger,
        "objective_kind": run.objective_kind,
        "outcome": run.outcome.value,
        "at": run.started_at,
        "model_provider": run.model_provider,
        "is_mine": is_mine,
        "results": [],
        "evaluated_product_ids": [],
    }
    evaluations = ctx.repo.list_run_evaluations(ctx.ws, run.id)
    report["evaluated_product_ids"] = sorted({e.product_id for e in evaluations})
    if not is_mine:
        return report

    # Which of this member's declarations ended up in a pool, and which pool — read from
    # membership and need lineage, never from what the run happened to touch.
    personal: dict[str, Any] = {
        p.need.id: (p.pool, p.membership)
        for p in relevance.personal_pools(ctx, community_id, household_id)
    }

    needs = {n.id: n for n in ctx.repo.list_needs(ctx.ws) if n.household_id == household_id}
    results: list[dict[str, Any]] = []
    for need_id in run.objective_need_ids:
        need = needs.get(need_id)
        if need is None:
            continue
        results.append(
            _result_for_need(
                ctx,
                need=need,
                product=ctx.repo.get_product(ctx.ws, need.product_id),
                evaluations=evaluations,
                personal=personal,
            )
        )

    for need_id in run.deferred_need_ids:
        need = needs.get(need_id)
        if need is None:
            continue
        product = ctx.repo.get_product(ctx.ws, need.product_id)
        results.append(
            {
                "need_id": need.id,
                "product_id": need.product_id,
                "product_name": product.name if product else need.product_id,
                "quantity": need.quantity,
                "unit": product.unit if product else "unit",
                "result": RESULT_NOT_INVESTIGATED,
                "pool_id": "",
                "units": 0,
                "reason_code": "",
                "is_exact_product": True,
                "declared_product_name": "",
                "headline": "Pool did not look at this one in this run.",
                "facts": [
                    "One run takes on the few things you need soonest. This one stays "
                    "standing for the next."
                ],
            }
        )

    for need_id in run.served_need_ids:
        need = needs.get(need_id)
        if need is None:
            continue
        product = ctx.repo.get_product(ctx.ws, need.product_id)
        pooled = personal.get(need.id)
        results.append(
            {
                "need_id": need.id,
                "product_id": need.product_id,
                "product_name": product.name if product else need.product_id,
                "quantity": need.quantity,
                "unit": product.unit if product else "unit",
                "result": RESULT_ALREADY_COORDINATED,
                "pool_id": pooled[0].id if pooled else "",
                "units": pooled[1].allocated_units if pooled else 0,
                "reason_code": "",
                "is_exact_product": pooled[1].is_exact_product if pooled else True,
                "declared_product_name": "",
                "headline": "Pool is already coordinating this one.",
                "facts": [],
            }
        )

    report["results"] = results
    # What this run evaluated that was nobody's declaration. Empty for a member run by
    # construction, and present so a surface can prove that rather than assume it (§13).
    report["also_evaluated"] = [
        {
            "product_id": e.product_id,
            "product_name": e.product_name,
            "viable": e.viable,
            "reason_code": e.reason_code,
        }
        for e in evaluations
        if not e.need_ids
    ]
    return report


def community_pools_elsewhere(
    ctx: PoolContext, community_id: str, household_id: str
) -> list[dict[str, Any]]:
    """Pools in this Community that are genuinely not this member's.

    Real work, worth seeing — never as their result. The exclusion set is every pool
    ``relevance`` says is theirs, not merely the one being led with, so a member in two
    orders is not told one of them belongs to somebody else.
    """
    mine = {p.pool.id for p in relevance.personal_pools(ctx, community_id, household_id)}
    out: list[dict[str, Any]] = []
    for pool in ctx.repo.list_pools(ctx.ws):
        if pool.community_id != community_id or pool.id in mine:
            continue
        product = ctx.repo.get_product(ctx.ws, pool.product_id)
        buyers = sum(
            1
            for m in ctx.repo.list_memberships(ctx.ws, pool.id)
            if m.state in LIVE_PARTICIPATION_STATES
        )
        out.append(
            {
                "pool_id": pool.id,
                "product_name": product.name if product else pool.product_id,
                "status": pool.status.value,
                "buyer_count": buyers,
            }
        )
    return out
