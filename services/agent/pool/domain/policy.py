"""Smart Join — the deterministic autonomy boundary.

This module decides whether Pool may commit a household's money without asking.
It is the single most safety-critical piece of the system, so it is a pure function
over explicit numbers: no model call, no prose, no "seems close enough".

The agent may *ask* whether a household qualifies. It cannot *decide* that they do
(AGENTS.md §5).

Rule of thumb encoded here: where a household's standing policy and the specific
need disagree, the **stricter** value wins. A household that set a 30% floor on one
need and 20% globally gets 30% for that need.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import AutonomyMode, AutonomyPolicy, NeedDeclaration
from .money import format_cents, pct_to_bps


@dataclass(frozen=True)
class PolicyCheck:
    rule: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class PolicyVerdict:
    """The result of evaluating one household's Smart Join policy against one offer."""

    household_id: str
    eligible_for_auto_join: bool
    mode: AutonomyMode
    checks: list[PolicyCheck] = field(default_factory=list)

    @property
    def failed_rules(self) -> list[str]:
        return [c.rule for c in self.checks if not c.passed]

    @property
    def blocking_reason(self) -> str:
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return ""
        return failed[0].detail

    def to_dict(self) -> dict:
        return {
            "household_id": self.household_id,
            "eligible_for_auto_join": self.eligible_for_auto_join,
            "mode": self.mode.value,
            "failed_rules": self.failed_rules,
            "checks": [c.to_dict() for c in self.checks],
        }


def evaluate_smart_join(
    *,
    household_id: str,
    policy: AutonomyPolicy,
    need: NeedDeclaration,
    cost_cents: int,
    savings_bps_value: int,
    travel_minutes: int,
    is_exact_product: bool,
    pickup_is_public: bool,
) -> PolicyVerdict:
    """Evaluate every Smart Join rule. Returns a verdict with a full audit trail.

    All checks are evaluated (not short-circuited) so the UI and the activity feed can
    show precisely which rule blocked an auto-join, not merely the first one.
    """
    checks: list[PolicyCheck] = []

    # 1. Autonomy mode. Ask Me means Pool may organise but never commit.
    mode_ok = policy.mode == AutonomyMode.SMART_JOIN
    checks.append(
        PolicyCheck(
            rule="autonomy_mode",
            passed=mode_ok,
            detail=(
                "Smart Join is enabled"
                if mode_ok
                else "Household is on Ask Me — commitment requires explicit approval"
            ),
        )
    )

    # 2. Minimum savings — stricter of the standing policy and this specific need.
    required_bps = max(pct_to_bps(policy.min_savings_pct), pct_to_bps(need.min_savings_pct))
    savings_ok = savings_bps_value >= required_bps
    checks.append(
        PolicyCheck(
            rule="min_savings",
            passed=savings_ok,
            detail=(
                f"savings {savings_bps_value / 100:.1f}% "
                f"{'meets' if savings_ok else 'below'} required {required_bps / 100:.1f}%"
            ),
        )
    )

    # 3. Spend ceiling — stricter of the two again.
    max_spend = min(policy.max_total_cost_cents, need.max_spend_cents)
    spend_ok = cost_cents <= max_spend
    checks.append(
        PolicyCheck(
            rule="max_spend",
            passed=spend_ok,
            detail=(
                f"share {format_cents(cost_cents)} "
                f"{'within' if spend_ok else 'exceeds'} cap {format_cents(max_spend)}"
            ),
        )
    )

    # 4. Travel burden.
    travel_ok = travel_minutes <= policy.max_travel_minutes
    checks.append(
        PolicyCheck(
            rule="max_travel",
            passed=travel_ok,
            detail=(
                f"pickup {travel_minutes} min "
                f"{'within' if travel_ok else 'exceeds'} limit {policy.max_travel_minutes} min"
            ),
        )
    )

    # 5. Substitutions are a consequential change — both the standing policy and the
    #    specific need must permit them before Pool may act unattended.
    if is_exact_product:
        checks.append(
            PolicyCheck(rule="substitution", passed=True, detail="exact product requested")
        )
    else:
        sub_ok = policy.allow_substitutes and need.accept_substitutes
        checks.append(
            PolicyCheck(
                rule="substitution",
                passed=sub_ok,
                detail=(
                    "substitute pre-authorised"
                    if sub_ok
                    else "substitute requires explicit approval"
                ),
            )
        )

    # 6. Public-pickup preference. Naming a private residence is consequential.
    if policy.public_pickup_only and not pickup_is_public:
        checks.append(
            PolicyCheck(
                rule="public_pickup",
                passed=False,
                detail="household requires a public pickup site",
            )
        )
    else:
        checks.append(PolicyCheck(rule="public_pickup", passed=True, detail="pickup site acceptable"))

    return PolicyVerdict(
        household_id=household_id,
        eligible_for_auto_join=all(c.passed for c in checks),
        mode=policy.mode,
        checks=checks,
    )


# Actions Pool may take unattended vs. actions that always need a human, unless the
# household's Smart Join policy explicitly pre-authorised that exact class.
# Mirrors AGENTS.md §5 and is asserted in tests so the two cannot drift apart.
AUTONOMOUS_ACTIONS = frozenset(
    {
        "evaluate_demand",
        "compare_offers",
        "calculate_routes",
        "form_candidate_pool",
        "send_status_notification",
        "search_replacement",
        "update_internal_plan",
    }
)

CONSEQUENTIAL_ACTIONS = frozenset(
    {
        "commit_money",
        "increase_budget",
        "accept_substitute",
        "offer_residence_as_pickup",
        "accept_worse_terms",
        "change_user_preferences",
    }
)


def requires_human_approval(action: str) -> bool:
    """True when an action must not happen without approval or explicit preauthorisation.

    Unknown actions are treated as consequential. An action nobody classified is not
    evidence that it is safe — so this deliberately tests membership of the *safe* set
    rather than the consequential one, which fails closed as the action vocabulary grows.
    """
    return action not in AUTONOMOUS_ACTIONS
