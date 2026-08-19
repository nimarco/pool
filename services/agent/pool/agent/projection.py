"""Compact agent-facing projections of deterministic tool results (Q13).

**The problem this solves.** Strands resends the entire conversation on every turn, so
a tool result is billed once per remaining turn, not once. The first real Bedrock run
(BUILD_HISTORY #0019) measured 35.7k input tokens for 418 output tokens — 85:1 — and
the cause was measured rather than guessed: ``evaluate_pool_economics`` returned 9,015
bytes of per-household detail that was then re-sent on every subsequent turn. The cost
grows with community size, because the payload carried one record per member.

**The rule this must not break.** Trimming what the model *sees* must never move the
source of truth into the model (AGENTS.md §5). So the projections below are pure
selection: they take the authoritative dict a deterministic service already produced
and drop or aggregate fields. They compute no money, no quantity, no verdict, and no
policy decision. Every number that survives is the same number the service computed,
and the full authoritative result is retained on the tool context for application
logic, the API, the operator UI, auditing, and tests.

**What a projection must keep.** Everything the model needs to choose the next valid
step: the verdict, the blocking reason, the identifiers a subsequent tool call takes,
the magnitudes that make an opportunity worth pursuing, and the counts that tell it how
many humans are involved. Everything else — per-household lines, score components,
reward breakdowns, the roster of checks that passed — is audit detail. It belongs in
the record, not in the model's context on every turn.

Household identifiers are deliberately aggregated into counts. No tool takes a
household id as an argument, so they were never decision-critical; sending ten of them
per turn was cost *and* an unnecessary widening of what reaches the model (§4).
"""

from __future__ import annotations

from typing import Any

from ..domain.money import bps_to_pct_str, format_cents

#: Opportunities the model is shown. It investigates the best few and forms at most one
#: pool per run, so a longer list is context the run cannot act on. Ranked, so the cut
#: is always the tail.
MAX_AGENT_OPPORTUNITIES = 6

#: Host candidates shown per evaluation. Ranked best-first; the model only ever acts on
#: the top eligible one, and needs the rest only to understand why nobody qualified.
MAX_AGENT_HOST_CANDIDATES = 5

#: Distinct ineligibility reasons summarised when candidates are omitted.
MAX_AGENT_REASONS = 4


def _money(payload: dict[str, Any], key: str) -> str:
    """Format a cents value the service already computed. Never derives one."""
    value = payload.get(key)
    return format_cents(int(value)) if isinstance(value, int) else ""


def demand_view(
    opportunities: list[dict[str, Any]], objective: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Latent-demand listing, capped and stripped of fields no tool call consumes.

    A member-anchored run's own entries are never trimmed: they are the question the run
    was asked, and dropping one would silently turn "declined" into "not investigated".
    The community tail is what the cap applies to.
    """
    mine = [o for o in opportunities if o.get("for_member")]
    rest = [o for o in opportunities if not o.get("for_member")]
    shown = mine + rest[: max(0, MAX_AGENT_OPPORTUNITIES - len(mine))]
    out: dict[str, Any] = {
        "opportunities": [
            {
                "product_id": o["product_id"],
                "product_name": o["product_name"],
                "unserved_units": o["unserved_units"],
                "member_count": o["member_count"],
                "suggested_pickup_site_id": o["suggested_pickup_site_id"],
                "suggested_pickup_site_name": o["suggested_pickup_site_name"],
                **({"for_member": True} if o.get("for_member") else {}),
                **(
                    {"member_need_ids": o["member_need_ids"]}
                    if o.get("member_need_ids")
                    else {}
                ),
            }
            for o in shown
        ],
        "count": len(opportunities),
    }
    if objective:
        # Product identities and the run's own shape. No household id, no name, no
        # contact detail — the model does not need to know who asked (AGENTS.md §4).
        out["objective"] = {
            "kind": objective.get("kind", ""),
            "declared": [
                {
                    "need_id": n["need_id"],
                    "product_id": n["product_id"],
                    "product_name": n["product_name"],
                    "quantity": n["quantity"],
                }
                for n in objective.get("needs") or []
            ],
        }
    if len(opportunities) > len(shown):
        out["omitted_lower_ranked"] = len(opportunities) - len(shown)
    return out


def _package_view(economics: dict[str, Any]) -> dict[str, Any]:
    packages = economics.get("packages") or {}
    return {
        "total_units": packages.get("total_units", 0),
        "cases": packages.get("cases", 0),
        "case_units": packages.get("case_units", 0),
        "moq_units": packages.get("moq_units", 0),
        "moq_met": packages.get("moq_met", False),
        "surplus_units": packages.get("surplus_units", 0),
        "surplus_resolved": packages.get("surplus_resolved", False),
    }


def _price_view(economics: dict[str, Any]) -> dict[str, Any]:
    """Landed total, the retail comparison, and the saving — as computed, not derived."""
    return {
        "landed_total": _money(economics, "all_in_cents"),
        "retail_total": _money(economics, "retail_baseline_cents"),
        "savings_total": _money(economics, "net_savings_cents"),
        "savings_pct": bps_to_pct_str(int(economics.get("net_savings_bps", 0) or 0)),
        "host_pay": _money(economics, "host_compensation_cents"),
        "host_pay_is_estimated": economics.get("host_is_estimated", False),
    }


def _policy_view(candidates: list[dict[str, Any]], full: dict[str, Any]) -> dict[str, Any]:
    """Who can be auto-joined, who must be asked, and which rule blocked the rest."""
    blocks: dict[str, int] = {}
    for candidate in candidates:
        rule = candidate.get("blocking_rule")
        if rule:
            blocks[str(rule)] = blocks.get(str(rule), 0) + 1
    view = {
        "auto_join_count": full.get("auto_join_count", 0),
        "approval_required_count": full.get("approval_required_count", 0),
        "excluded_count": full.get("rejected_count", 0),
    }
    if blocks:
        view["blocking_rules"] = blocks
    return view


def opportunity_view(full: dict[str, Any]) -> dict[str, Any]:
    """Compact view of an ``OpportunityAssessment``.

    Keeps the verdict, the identifiers ``create_candidate_pool`` needs, the magnitudes
    that decide whether the opportunity is worth pursuing, package/surplus status, and
    the buyer-policy outcome. Drops the per-household candidate roster and the
    per-household economics lines, which are audit detail and scale with the community.
    """
    view: dict[str, Any] = {
        "product_id": full.get("product_id", ""),
        "product_name": full.get("product_name", ""),
        "pickup_site_id": full.get("pickup_site_id", ""),
        "pickup_site_name": full.get("pickup_site_name", ""),
        "distribution_day": full.get("distribution_day", ""),
        "viable": bool(full.get("viable")),
        "member_count": len(full.get("candidates") or []),
        "current_units": full.get("current_units", 0),
        "future_units": full.get("future_units", 0),
    }
    if not full.get("viable"):
        # A refusal only has to explain itself well enough for the model to move on.
        # The key keeps the authoritative name so a consumer reading either shape —
        # projected or full — reads the same field.
        view["reason"] = full.get("reason", "")
        return view

    economics = full.get("economics") or {}
    view["units"] = _package_view(economics)
    view.update(_price_view(economics))
    view["policy"] = _policy_view(full.get("candidates") or [], full)
    view["avg_travel_minutes"] = full.get("avg_travel_minutes", 0)
    view["max_travel_minutes"] = full.get("max_travel_minutes", 0)
    if full.get("headline"):
        # A ready-made sentence built entirely from tool-computed values, so the model
        # can describe the opportunity without assembling numbers itself.
        view["headline"] = full["headline"]
    return view


def host_evaluation_view(full: dict[str, Any]) -> dict[str, Any]:
    """Compact view of a host evaluation or a host offer.

    Keeps who was offered the job, how many are eligible, each shown candidate's
    eligibility, rank and deterministic pay, and the factual reasons anyone is
    ineligible. Drops the score components and the reward breakdown: they explain *how*
    the deterministic ranker scored, which the model never re-derives and never needs
    to restate.
    """
    candidates = full.get("candidates") or []
    shown = candidates[:MAX_AGENT_HOST_CANDIDATES]
    view: dict[str, Any] = {
        "pool_id": full.get("pool_id", ""),
        "status": full.get("status", ""),
        "reason": full.get("reason", ""),
        "offered_household_id": full.get("offered_household_id", ""),
        "eligible_count": full.get("eligible_count", 0),
        "candidates_considered": len(candidates),
        "candidates": [
            {
                "household_id": c.get("household_id", ""),
                "rank": i,
                "eligible": bool(c.get("eligible")),
                "score": c.get("score", 0),
                "pay": _money(c, "reward_cents"),
                **(
                    {"ineligible_reasons": c.get("ineligible_reasons") or []}
                    if not c.get("eligible")
                    else {}
                ),
            }
            for i, c in enumerate(shown, 1)
        ],
    }
    if len(candidates) > len(shown):
        view["candidates_omitted"] = len(candidates) - len(shown)
        reasons: list[str] = []
        for c in candidates[len(shown) :]:
            for reason in c.get("ineligible_reasons") or []:
                if reason not in reasons:
                    reasons.append(str(reason))
        if reasons:
            view["omitted_ineligible_reasons"] = reasons[:MAX_AGENT_REASONS]
    return view


def final_offer_view(full: dict[str, Any]) -> dict[str, Any]:
    """Compact view of a ``FinalOfferResult``.

    Keeps whether the offer issued, the exact landed economics at the summary level,
    package/surplus status, and how many buyers were authorised, asked, removed, or
    failed. Drops the per-household economics lines and the household id lists — no
    tool takes a household id, so they were never actionable by the model.
    """
    view: dict[str, Any] = {
        "pool_id": full.get("pool_id", ""),
        "issued": bool(full.get("issued")),
        "status": full.get("status", ""),
        "reason": full.get("reason", ""),
        "surplus_units": full.get("surplus_units", 0),
        "auto_authorised_count": len(full.get("auto_authorised") or []),
        "awaiting_decision_count": len(full.get("awaiting_decision") or []),
        "removed_count": len(full.get("removed") or []),
        "authorisation_failure_count": len(full.get("authorisation_failures") or []),
    }
    economics = full.get("economics") or {}
    if economics:
        view["units"] = _package_view(economics)
        view.update(_price_view(economics))
    return view


def viability_view(full: dict[str, Any]) -> dict[str, Any]:
    """Verdict, what failed, and why — without the roster of checks that passed."""
    return {
        "stage": full.get("stage", ""),
        "viable": bool(full.get("viable")),
        "failed": full.get("failed") or [],
        "blocking_reason": full.get("blocking_reason", ""),
    }


def lock_view(full: dict[str, Any]) -> dict[str, Any]:
    """Compact view of a lock attempt: the verdict, and what capture actually did."""
    view = {k: v for k, v in full.items() if k not in {"viability", "capture"}}
    if isinstance(full.get("viability"), dict):
        view["viability"] = viability_view(full["viability"])
    capture = full.get("capture")
    if isinstance(capture, dict):
        view["capture"] = {
            "captured_count": len(capture.get("captured") or []),
            "failed_count": len(capture.get("failed") or []),
            "captured_total": _money(capture, "captured_cents"),
            "purchase_ready": capture.get("purchase_ready", False),
            "status": capture.get("status", ""),
        }
    return view


def pool_view(full: dict[str, Any]) -> dict[str, Any]:
    """Compact view of ``inspect_pool``: same facts, viability without the check list."""
    view = dict(full)
    if isinstance(full.get("viability"), dict):
        view["viability"] = viability_view(full["viability"])
    return view
