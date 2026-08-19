"""Smart Join — the deterministic autonomy boundary (§53).

This module decides whether Pool may commit a member's money without asking. It is
the single most safety-critical piece of the system, so it is a pure function over
explicit numbers: no model call, no prose, no "seems close enough".

The agent may *ask* whether a member qualifies. It cannot *decide* that they do
(AGENTS.md §5).

Two rules govern the arithmetic:

* **Savings are always net landed savings.** The figure compared against a member's
  floor is the price after merchandise, host compensation, processing, and Pool's own
  fee. Advertising gross savings while hiding operating costs is forbidden (§50).
* **Where a standing policy and a specific need disagree, the stricter value wins.**
  A member with a 30% floor on one need and 20% globally gets 30% for that need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .models import AutonomyMode, AutonomyPolicy, NeedDeclaration, SubstitutionPolicy
from .money import format_cents, pct_to_bps
from .timing import pickup_day_acceptable


class JoinVerdictKind(str, Enum):
    """The three possible answers (§53). 'Close enough' is not among them."""

    AUTO_APPROVED = "auto_approved"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    NOT_ALLOWED = "not_allowed"


@dataclass(frozen=True)
class PolicyCheck:
    rule: str
    passed: bool
    detail: str
    #: A hard rule can never be waived by a human answering a prompt — the situation
    #: itself is outside what this member authorised.
    hard: bool = False

    def to_dict(self) -> dict:
        return {"rule": self.rule, "passed": self.passed, "detail": self.detail, "hard": self.hard}


@dataclass(frozen=True)
class PolicyVerdict:
    """The result of evaluating one member's Smart Join policy against one final price."""

    household_id: str
    kind: JoinVerdictKind
    mode: AutonomyMode
    checks: list[PolicyCheck] = field(default_factory=list)

    @property
    def eligible_for_auto_join(self) -> bool:
        return self.kind == JoinVerdictKind.AUTO_APPROVED

    @property
    def failed_rules(self) -> list[str]:
        return [c.rule for c in self.checks if not c.passed]

    @property
    def blocking_reason(self) -> str:
        failed = [c for c in self.checks if not c.passed]
        return failed[0].detail if failed else ""

    def to_dict(self) -> dict:
        return {
            "household_id": self.household_id,
            "verdict": self.kind.value,
            "eligible_for_auto_join": self.eligible_for_auto_join,
            "mode": self.mode.value,
            "failed_rules": self.failed_rules,
            "blocking_reason": self.blocking_reason,
            "checks": [c.to_dict() for c in self.checks],
        }


def evaluate_smart_join(
    *,
    household_id: str,
    policy: AutonomyPolicy,
    need: NeedDeclaration,
    landed_cost_cents: int,
    net_savings_bps: int,
    travel_minutes: int,
    is_exact_product: bool,
    substitution_authorised: bool,
    pickup_is_public: bool,
    distribution_day: date | None = None,
) -> PolicyVerdict:
    """Evaluate every Smart Join rule against the exact landed price.

    All checks are evaluated (not short-circuited) so the UI and the activity feed can
    show precisely which rule blocked an auto-join, not merely the first one.

    Returns one of three verdicts:

    * ``AUTO_APPROVED`` — every rule passes; Pool may authorise without asking.
    * ``HUMAN_APPROVAL_REQUIRED`` — a soft rule failed; the member decides.
    * ``NOT_ALLOWED`` — a hard rule failed; this member cannot be in this pool at all.
    """
    checks: list[PolicyCheck] = []

    # 1. Autonomy mode. Ask Me means Pool may organise but never commit.
    mode_ok = policy.mode == AutonomyMode.SMART_JOIN
    checks.append(
        PolicyCheck(
            "autonomy_mode",
            mode_ok,
            "Smart Join is enabled"
            if mode_ok
            else "member is on Ask Me — commitment requires explicit approval",
        )
    )

    # 2. Minimum net savings — stricter of the standing policy and this specific need.
    required_bps = max(pct_to_bps(policy.min_savings_pct), pct_to_bps(need.min_savings_pct))
    savings_ok = net_savings_bps >= required_bps
    checks.append(
        PolicyCheck(
            "min_net_savings",
            savings_ok,
            f"net landed savings {net_savings_bps / 100:.1f}% "
            f"{'meets' if savings_ok else 'below'} required {required_bps / 100:.1f}%",
        )
    )

    # 3. Spend ceiling — stricter of the two again, against the exact final amount.
    max_spend = min(policy.max_total_cost_cents, need.max_spend_cents)
    spend_ok = landed_cost_cents <= max_spend
    checks.append(
        PolicyCheck(
            "max_spend",
            spend_ok,
            f"final price {format_cents(landed_cost_cents)} "
            f"{'within' if spend_ok else 'exceeds'} cap {format_cents(max_spend)}",
        )
    )

    # 4. Travel burden.
    travel_ok = travel_minutes <= policy.max_travel_minutes
    checks.append(
        PolicyCheck(
            "max_travel",
            travel_ok,
            f"pickup {travel_minutes} min "
            f"{'within' if travel_ok else 'exceeds'} limit {policy.max_travel_minutes} min",
        )
    )

    # 5. Substitution. A product outside the member's structured authority is a *hard*
    #    failure: they told Pool which products are acceptable, and this is not one.
    if is_exact_product:
        checks.append(PolicyCheck("substitution", True, "exact product requested"))
    elif not substitution_authorised:
        checks.append(
            PolicyCheck(
                "substitution",
                False,
                "product is outside this member's substitution authority",
                hard=True,
            )
        )
    elif need.substitution == SubstitutionPolicy.GROUP_DECLARED:
        # Nothing was substituted. The member declared the family, so the standing
        # substitution rule — which governs stand-ins for a product they *named* — has
        # no subject here, and asking them to approve their own declaration would be a
        # question with only one answer.
        checks.append(
            PolicyCheck("substitution", True, "member declared this product family")
        )
    else:
        standing_allows = policy.substitution != SubstitutionPolicy.EXACT_ONLY
        checks.append(
            PolicyCheck(
                "substitution",
                standing_allows,
                "substitute pre-authorised"
                if standing_allows
                else "substitute is acceptable but needs explicit approval",
            )
        )

    # 6. Public-pickup preference. Naming a private residence is consequential.
    pickup_ok = pickup_is_public or not policy.public_pickup_only
    checks.append(
        PolicyCheck(
            "public_pickup",
            pickup_ok,
            "pickup site acceptable" if pickup_ok else "member requires a public pickup site",
        )
    )

    # 7. Pickup day. If they cannot collect on the pool's distribution day, they cannot
    #    be in this pool — no prompt can fix a scheduling conflict.
    if distribution_day is not None:
        day_ok = pickup_day_acceptable(policy.available_pickup_weekdays, distribution_day)
        checks.append(
            PolicyCheck(
                "pickup_day",
                day_ok,
                "member is available on the distribution day"
                if day_ok
                else "member cannot collect on the pool's distribution day",
                hard=True,
            )
        )

    failed = [c for c in checks if not c.passed]
    if any(c.hard for c in failed):
        kind = JoinVerdictKind.NOT_ALLOWED
    elif failed:
        kind = JoinVerdictKind.HUMAN_APPROVAL_REQUIRED
    else:
        kind = JoinVerdictKind.AUTO_APPROVED

    return PolicyVerdict(household_id=household_id, kind=kind, mode=policy.mode, checks=checks)


# Actions Pool may take unattended vs. actions that always need a human, unless the
# member's Smart Join policy explicitly pre-authorised that exact class.
# Mirrors AGENTS.md §5 and is asserted in tests so the two cannot drift apart.
AUTONOMOUS_ACTIONS = frozenset(
    {
        "evaluate_demand",
        "compare_offers",
        "refresh_quote",
        "calculate_routes",
        "form_candidate_pool",
        "recruit_hosts",
        "rank_hosts",
        "send_status_notification",
        "search_replacement",
        "update_internal_plan",
    }
)

CONSEQUENTIAL_ACTIONS = frozenset(
    {
        "commit_money",
        "authorize_payment",
        "capture_payment",
        "increase_budget",
        "accept_substitute",
        "offer_residence_as_pickup",
        "accept_worse_terms",
        "change_user_preferences",
        "assign_host",
        "execute_purchase",
        "override_pickup",
    }
)


def requires_human_approval(action: str) -> bool:
    """True when an action must not happen without approval or explicit preauthorisation.

    Unknown actions are treated as consequential. An action nobody classified is not
    evidence that it is safe — so this deliberately tests membership of the *safe* set
    rather than the consequential one, which fails closed as the vocabulary grows.
    """
    return action not in AUTONOMOUS_ACTIONS
