"""Timing: Pool Days, lifecycle deadlines, and flexible future demand (§22, §23, §24).

Two rules matter more than the arithmetic:

1. **Pool does not buy the instant MOQ is touched.** A pool has explicit deadlines —
   formation, host acceptance, final offer, authorisation, lock, distribution — and
   they come from the Community's own schedule, not from a global constant.

2. **Future demand may only be pulled forward inside a window the member authorised.**
   The agent may *decide to investigate* whether more demand exists; this module
   decides *which members are actually eligible*. A need whose owner did not permit
   an early purchase is not a candidate no matter how convenient it would be.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from .models import Community, NeedDeclaration, PoolDaySchedule, PoolTiming, iso


def next_weekday_on_or_after(start: date, weekday: int) -> date:
    """The first date on or after ``start`` falling on ``weekday`` (Mon=0)."""
    return start + timedelta(days=(weekday - start.weekday()) % 7)


def _at(day: date, hour: int) -> str:
    return iso(datetime.combine(day, time(hour=hour, tzinfo=UTC)))


def next_pool_day(today: date, schedule: PoolDaySchedule) -> date:
    """The next distribution day for a Community.

    If today *is* the distribution day the cycle has already run, so the next one is
    a week out — a pool cannot form and distribute within the same few hours.
    """
    candidate = next_weekday_on_or_after(today, schedule.distribution_weekday)
    return candidate + timedelta(days=7) if candidate == today else candidate


def build_timing(
    *,
    community: Community,
    today: date | None = None,
    distribution_day: date | None = None,
) -> PoolTiming:
    """Derive one pool's explicit deadlines from the Community's weekly rhythm.

    Every deadline is anchored backwards from the distribution day, so the sequence
    host → quote refresh → final offer → authorisation → lock always holds (§35).
    """
    today = today or date.today()
    schedule = community.schedule
    dist = distribution_day or next_pool_day(today, schedule)

    def _back_to(weekday: int) -> date:
        """The most recent ``weekday`` strictly before the distribution day."""
        delta = (dist.weekday() - weekday) % 7
        return dist - timedelta(days=delta or 7)

    formation_cutoff = _back_to(schedule.formation_cutoff_weekday)
    host_deadline = _back_to(schedule.host_deadline_weekday)
    final_offer = _back_to(schedule.final_offer_weekday)
    lock_day = _back_to(schedule.lock_weekday)

    return PoolTiming(
        formation_opens_at=_at(today, 0),
        host_recruiting_opens_at=_at(formation_cutoff, 9),
        host_acceptance_deadline=_at(host_deadline, 12),
        final_offer_at=_at(final_offer, 14),
        authorization_deadline=_at(lock_day, 20),
        lock_at=_at(lock_day, 21),
        purchase_by=_at(dist, schedule.distribution_start_hour - 1),
        distribution_starts_at=_at(dist, schedule.distribution_start_hour),
        distribution_ends_at=_at(dist, schedule.distribution_end_hour),
    )


@dataclass(frozen=True)
class TimingEligibility:
    """Why one need is or is not usable for a purchase on a given date."""

    need_id: str
    household_id: str
    eligible: bool
    reason: str
    is_future_pull_forward: bool = False
    days_early: int = 0

    def to_dict(self) -> dict:
        return {
            "need_id": self.need_id,
            "household_id": self.household_id,
            "eligible": self.eligible,
            "reason": self.reason,
            "is_future_pull_forward": self.is_future_pull_forward,
            "days_early": self.days_early,
        }


def evaluate_timing(need: NeedDeclaration, purchase_date: date) -> TimingEligibility:
    """Decide whether ``need`` may be served by a purchase on ``purchase_date``.

    Three outcomes, and the distinction between the last two is the whole point of §24:

    * **Ineligible** — the purchase falls outside the window this member authorised.
      No amount of convenience to the case count changes that.
    * **Routine** — the purchase lands inside the member's ordinary restock lead. They
      were going to buy about now anyway.
    * **Pull-forward** — the purchase is earlier than they ordinarily restock, but no
      earlier than the date they explicitly said was acceptable. This is demand Pool may
      bring forward to complete an order, and *only* because they permitted it.
    """
    if not need.active:
        return TimingEligibility(need.id, need.household_id, False, "need_inactive")

    if purchase_date > need.latest:
        return TimingEligibility(
            need.id, need.household_id, False, "purchase lands after the member's latest useful date"
        )

    if purchase_date < need.earliest:
        return TimingEligibility(
            need.id,
            need.household_id,
            False,
            "purchase is earlier than the member authorised",
        )

    days_early = (need.expected_next_need_date - purchase_date).days
    if days_early > need.routine_lead_days:
        return TimingEligibility(
            need.id,
            need.household_id,
            True,
            "earlier than they normally restock, but inside the window they authorised",
            is_future_pull_forward=True,
            days_early=days_early,
        )

    return TimingEligibility(
        need.id,
        need.household_id,
        True,
        "purchase falls inside the member's ordinary restock window",
        days_early=max(0, days_early),
    )


def pickup_day_acceptable(weekdays: list[int], distribution_day: date) -> bool:
    """Whether a member can collect on the pool's distribution day. Empty means any."""
    return not weekdays or distribution_day.weekday() in weekdays
