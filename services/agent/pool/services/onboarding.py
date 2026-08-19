"""Setting up the account of the person actually at the screen.

Exactly one household per workspace is *the consumer*. Everybody else in the fixture is
a synthetic neighbour who exists so there is something to coordinate with — and until
this module ran, the product could not tell those two apart. A visitor was dropped into
a seeded persona, greeted by somebody else's name, and shown recurring purchases they
had never made.

What onboarding actually writes is small, and deliberately so:

* the **name** Pool should use, which is presentational everywhere — matching,
  economics and every state transition key off the household *id*, which never changes;
* the **autonomy mode**, which is a real deterministic policy input;
* a **saved payment method**, through the ordinary payment service;
* a completion timestamp, so a refresh returns to the product rather than to setup.

What it deliberately does **not** write is a location. The consumer's coordinates stay
exactly as the fixture placed them, and the reason is in :func:`describe_place`.

Nothing here is a login. There is no credential, no session and no account recovery —
a workspace id in the browser is the whole of it, exactly as before. This is a profile,
not authentication (`docs/PILOT_READINESS.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..data.seed import COMMUNITY_ID, CONSUMER_HOUSEHOLD
from ..domain.models import AutonomyMode, Household, iso, utcnow
from .context import PoolContext

#: Long enough for a real name, short enough that the greeting cannot be vandalised.
MAX_NAME_LENGTH = 40


class OnboardingError(ValueError):
    """Setup input the domain will not accept. Carries a human reason."""


def consumer_household(ctx: PoolContext) -> Household | None:
    """The household the person at the screen is using."""
    return ctx.repo.get_household(ctx.ws, CONSUMER_HOUSEHOLD)


@dataclass(frozen=True)
class Place:
    """What Pool can honestly say about where this member is.

    The demo's community is a made-up campus at made-up coordinates, and a judge running
    it could be anywhere on Earth. Two things follow, and they are the whole reason this
    type exists rather than a latitude and a longitude:

    **Pool never asks the browser for a position.** The deployed
    ``Permissions-Policy`` denies geolocation outright, and that stays true. A coordinate
    Pool would immediately discard is a coordinate it should not collect (AGENTS.md §4).

    **Pool never claims the member is near the synthetic campus.** It says the opposite,
    in the interface: this community is invented, and you are exploring it from inside.
    A demo that quietly mapped a real position onto a fictional campus would be lying
    about the one thing location is for.

    So the location step orients rather than captures. It names the local network, shows
    what being in it is worth — how many neighbours, how many pickup points — and says
    plainly that the network is synthetic.
    """

    community_id: str
    community_name: str
    member_count: int
    pickup_site_count: int
    synthetic: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "community_id": self.community_id,
            "community_name": self.community_name,
            "member_count": self.member_count,
            "pickup_site_count": self.pickup_site_count,
            "synthetic": self.synthetic,
        }


def describe_place(ctx: PoolContext) -> Place:
    """The local network this member coordinates inside, and how big it is."""
    community = ctx.repo.get_community(ctx.ws, COMMUNITY_ID)
    sites = [s for s in ctx.repo.list_sites(ctx.ws) if s.community_id == COMMUNITY_ID]
    return Place(
        community_id=COMMUNITY_ID,
        community_name=community.name if community else "",
        member_count=len(ctx.repo.list_households(ctx.ws)),
        pickup_site_count=len(sites),
        synthetic=bool(community.synthetic) if community else True,
    )


def consumer_view(ctx: PoolContext) -> dict[str, Any]:
    """Who the client should present as "you", and what setup is still outstanding.

    Returned on every state read so the app can route a fresh workspace into setup and a
    returning one straight to the product, without a second round trip and without the
    browser having to remember anything that a reset needs to be able to clear.
    """
    me = consumer_household(ctx)
    if me is None:
        return {"household_id": "", "onboarded": False}
    return {
        "household_id": me.id,
        "display_name": me.display_name,
        "onboarded": me.is_onboarded,
        # A boolean, never the reference. The browser has no business seeing either the
        # provider token or a card.
        "has_payment_method": bool(me.payment_method_ref),
        "autonomy_mode": me.autonomy.mode.value,
        "place": describe_place(ctx).to_dict(),
    }


def complete_onboarding(
    *, ctx: PoolContext, display_name: str, autonomy_mode: str
) -> dict[str, Any]:
    """Record what the member told Pool about themselves, and open the product.

    Idempotent: running it again updates the same household rather than creating a
    second one, so a re-submitted form or a resumed half-finished setup converges
    instead of duplicating.
    """
    me = consumer_household(ctx)
    if me is None:
        raise OnboardingError("this workspace has no account to set up")

    name = " ".join((display_name or "").split())
    if not name:
        raise OnboardingError("Pool needs something to call you")
    if len(name) > MAX_NAME_LENGTH:
        raise OnboardingError(f"that name is longer than {MAX_NAME_LENGTH} characters")

    try:
        mode = AutonomyMode(autonomy_mode)
    except ValueError as exc:
        raise OnboardingError("choose whether Pool may act without asking you") from exc

    me.display_name = name
    # Only the master switch. The four limits underneath it keep whatever the account
    # already had, because they are real constraints the deterministic policy engine
    # reads and setup is not the place to invent numbers on somebody's behalf (§53).
    me.autonomy.mode = mode
    me.onboarded_at = iso(utcnow())
    ctx.repo.put_household(ctx.ws, me)

    ctx.log(
        "member_onboarded",
        f"{name} finished setting up their account",
        {
            "household_id": me.id,
            "autonomy_mode": mode.value,
            "has_payment_method": bool(me.payment_method_ref),
        },
    )
    return consumer_view(ctx)
