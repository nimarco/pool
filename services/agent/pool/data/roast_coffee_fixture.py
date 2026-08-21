"""A heterogeneous coffee community, for strategies to be searched over.

Everything here is invented. No real person, roaster, product or price is represented,
and the households are synthetic neighbours of a made-up campus (AGENTS.md §4, §8).

**Why this exists separately from the seed.** The demo seed proves one shape: many
people buy the *same* tub of whey, so there is one order to evaluate and the only
question is whether it is worth doing. That shape cannot exercise a strategy search,
because a search with one option is not a search. This fixture is the other shape —
twelve households who all buy coffee and disagree about which coffee — and it is a
separate, explicitly-installed dataset precisely so it cannot drift into the workspaces
whose canonical numbers the rest of the suite pins.

**What is arranged and what is not.** The demand and the supplier terms are arranged;
that is legitimate scripting of a scenario. The outcomes are not. No row below says
which strategy wins, none is tagged as the one that should fail, and nothing in the
generator or the evaluator reads anything from this module. Which option survives, and
which is refused for what, is whatever ``economics.price_pool`` and ``fit_to_cases``
produce from these numbers — and both of those were written long before this fixture and
know nothing about it.

Installing
----------

    seed(repo, ws)                 # community, sites, schedule, fee configuration
    install_roast_coffee(repo, ws) # this fixture on top of it

The seed is a prerequisite rather than a convenience: the Community's pool-day schedule,
its formation radius, its public pickup sites and its fee configuration are all inputs to
the economics below, and a fixture that invented its own copy of them would be measuring
a different world from the one the rest of the system runs in.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..domain.attributes import AttributeConstraint
from ..domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    CommunityMembership,
    Household,
    MembershipStatus,
    MoqKind,
    NeedDeclaration,
    Offer,
    OfferKind,
    OfferSource,
    SubstitutionPolicy,
    Supplier,
    VerificationMethod,
    iso,
    utcnow,
)
from . import product_facts as pf
from .seed import CENTER_LAT, CENTER_LON, COMMUNITY_ID

#: Shorthand for the six curated SKUs, so the demand table below reads as a claim about
#: coffee rather than as a wall of identifiers.
A_MEDIUM = "prod_rc_kestrel_medium"
A_LIGHT = "prod_rc_kestrel_light"
B_DARK = "prod_rc_harbourstone_dark"
C_DECAF = "prod_rc_stillfield_decaf"
D_GROUND = "prod_rc_millgate_ground"
E_UNVERIFIED_ROAST = "prod_rc_beacon_unverified"

#: The declaration a member-scoped objective is anchored to, and the household holding
#: it. A parameter of the scenario rather than a property of the engine: Phase 4 can
#: anchor a run on whichever household a real person is using.
ANCHOR_HOUSEHOLD = "hh_rc_anchor"
ANCHOR_NEED = "need_rc_anchor"


def _fresh() -> str:
    return iso(utcnow())


# ------------------------------------------------------------------------ suppliers


SUPPLIERS = [
    Supplier("sup_rc_market", "Corner Market", CENTER_LAT + 0.003, CENTER_LON + 0.002),
    Supplier("sup_rc_beanline", "Beanline Wholesale", CENTER_LAT - 0.048, CENTER_LON + 0.031),
]


def build_offers() -> list[Offer]:
    """Retail baselines, and the bulk tiers each is measured against.

    The terms differ per SKU because real supplier terms do: a roaster's flagship bag is
    discounted thinly and sold in small cases, while a slower-moving dark roast is
    discounted hard to move it and sold in sixes. Nothing here is tuned to a target
    verdict — a discount is a discount, and whether it survives host pay, processing and
    Pool's fee is arithmetic this file does not perform.
    """
    fresh = _fresh()

    def retail(oid: str, product: str, cents: int, ref: str) -> Offer:
        return Offer(oid, "sup_rc_market", product, OfferKind.RETAIL, cents, 1,
                     MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, ref)

    def bulk(oid: str, product: str, cents: int, case: int, moq: int, ref: str) -> Offer:
        return Offer(oid, "sup_rc_beanline", product, OfferKind.BULK, cents, case,
                     MoqKind.UNITS, moq, fresh, "", OfferSource.SYNTHETIC, ref)

    return [
        # The flagship. Barely discounted and sold in fives — the shape of a bag a
        # wholesaler has no trouble moving at close to shelf price.
        retail("off_rc_kestrel_medium_retail", A_MEDIUM, 1800, "SKU-RC-KM"),
        bulk("off_rc_kestrel_medium_bulk", A_MEDIUM, 1570, 5, 15, "CASE-RC-KM-5"),

        # A light roast almost nobody in this community buys, quoted at a real discount
        # and a minimum that reflects how rarely it moves.
        retail("off_rc_kestrel_light_retail", A_LIGHT, 1800, "SKU-RC-KL"),
        bulk("off_rc_kestrel_light_bulk", A_LIGHT, 1290, 6, 24, "CASE-RC-KL-6"),

        # Discounted hard, in sixes, with a low minimum.
        retail("off_rc_harbourstone_dark_retail", B_DARK, 1850, "SKU-RC-HD"),
        bulk("off_rc_harbourstone_dark_bulk", B_DARK, 1150, 6, 12, "CASE-RC-HD-6"),

        retail("off_rc_stillfield_decaf_retail", C_DECAF, 1900, "SKU-RC-SD"),
        bulk("off_rc_stillfield_decaf_bulk", C_DECAF, 1350, 6, 18, "CASE-RC-SD-6"),

        retail("off_rc_millgate_ground_retail", D_GROUND, 1450, "SKU-RC-MG"),
        bulk("off_rc_millgate_ground_bulk", D_GROUND, 1020, 8, 24, "CASE-RC-MG-8"),

        retail("off_rc_beacon_retail", E_UNVERIFIED_ROAST, 1750, "SKU-RC-BR"),
        bulk("off_rc_beacon_bulk", E_UNVERIFIED_ROAST, 1220, 6, 12, "CASE-RC-BR-6"),
    ]


# ------------------------------------------------------------------------- the rules
# The typed policies (§21). Written once here and referenced by the demand table, so the
# same rule is literally the same object wherever two members happen to share one.


def _rule(
    prefers: dict[str, tuple[str, ...]] | None = None, **requires: set[str]
) -> AttributeConstraint:
    return AttributeConstraint(
        family=pf.FAMILY,
        schema_version=pf.SCHEMA_VERSION,
        requires={k: frozenset(v) for k, v in requires.items()},
        prefers=dict(prefers or {}),
    )


#: "Whole bean, caffeinated, and medium or dark." The commonest real shape, and the one
#: no policy before ``ATTRIBUTE_CONSTRAINED`` could express.
BEANS_MEDIUM_OR_DARK = _rule(
    form={pf.FORM_WHOLE_BEAN},
    caffeine={pf.CAFFEINE_CAFFEINATED},
    roast={pf.ROAST_MEDIUM, pf.ROAST_DARK},
)

#: Whole bean and caffeinated, with no *requirement* about roast — and a stated liking
#: for medium. The preference is carried, stored, and structurally inert: it may order
#: options this member has already been found compatible with and can never add one or
#: remove one, which is asserted rather than asserted-to.
#:
#: Wider than the rule above, and consequently the only rule here that a bag whose roast
#: nobody has verified can satisfy — because a fact is only load-bearing when somebody's
#: policy makes it so (§21).
BEANS_ANY_ROAST = _rule(
    prefers={"roast": (pf.ROAST_MEDIUM,)},
    form={pf.FORM_WHOLE_BEAN},
    caffeine={pf.CAFFEINE_CAFFEINATED},
)

#: Decaf, and it has to be beans. Structurally incapable of joining a caffeinated order,
#: which is the point: this member is not a near miss, they are buying something else.
BEANS_DECAF = _rule(form={pf.FORM_WHOLE_BEAN}, caffeine={pf.CAFFEINE_DECAF})

#: Ground, caffeinated. Same distance from the bean drinkers, in the other direction.
GROUND_CAFFEINATED = _rule(form={pf.FORM_GROUND}, caffeine={pf.CAFFEINE_CAFFEINATED})


# -------------------------------------------------------------------------- the demand
# (household, name, dlat, dlon, autonomy, need id, product, units, due days, earliest
#  days before due, routine lead days, policy, constraint, allowlist)
#
# Twelve households who all buy coffee. Read down the policy column rather than the
# product column: the interesting thing about this table is not that they named six
# different bags, it is that they authorised six different *kinds* of substitution, and
# every one of those authorisations is a sentence a real person would recognise as theirs.

_DEMAND: list[tuple] = [
    # --- The anchor. Placed closest to the centre because a member-triggered run is
    #     sited around the person who asked, and their own coordinates are part of that.
    (ANCHOR_HOUSEHOLD, "Rowan A.", 0.0002, 0.0001, AutonomyMode.SMART_JOIN,
     ANCHOR_NEED, A_MEDIUM, 3, 12, 12, 12,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, BEANS_MEDIUM_OR_DARK, ()),

    # --- Same rule, different bag on the shelf at home. These are the members exact-only
    #     declarations would have fragmented into three incompatible groups.
    ("hh_rc_okonjo", "Ify O.", 0.0007, -0.0004, AutonomyMode.SMART_JOIN,
     "need_rc_okonjo", B_DARK, 3, 13, 13, 13,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, BEANS_MEDIUM_OR_DARK, ()),
    ("hh_rc_lindholm", "Tove L.", -0.0009, 0.0006, AutonomyMode.SMART_JOIN,
     "need_rc_lindholm", A_MEDIUM, 2, 11, 11, 11,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, BEANS_MEDIUM_OR_DARK, ()),

    # --- Whole bean and caffeinated, no opinion about roast. The widest rule here, and
    #     the only one a bag with an unverified roast can serve.
    ("hh_rc_varga", "Máté V.", 0.0011, 0.0008, AutonomyMode.SMART_JOIN,
     "need_rc_varga", E_UNVERIFIED_ROAST, 3, 14, 14, 14,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, BEANS_ANY_ROAST, ()),

    # --- Exact-only. They named a bag and meant it; no rule widens them.
    ("hh_rc_ashworth", "Nell A.", -0.0013, -0.0007, AutonomyMode.SMART_JOIN,
     "need_rc_ashworth", A_MEDIUM, 3, 12, 12, 12,
     SubstitutionPolicy.EXACT_ONLY, None, ()),
    ("hh_rc_baptiste", "Yannick B.", 0.0016, -0.0011, AutonomyMode.ASK_ME,
     "need_rc_baptiste", B_DARK, 3, 13, 13, 13,
     SubstitutionPolicy.EXACT_ONLY, None, ()),
    ("hh_rc_castellan", "Rhea C.", -0.0018, 0.0012, AutonomyMode.SMART_JOIN,
     "need_rc_castellan", A_LIGHT, 2, 12, 12, 12,
     SubstitutionPolicy.EXACT_ONLY, None, ()),

    # --- Exact-only, and not due for another five weeks — but willing to buy that early
    #     if it saves money. The only pull-forward demand in the fixture, so "does this
    #     option depend on buying somebody's coffee early" is a real question about it.
    ("hh_rc_holt", "Piers H.", 0.0021, 0.0004, AutonomyMode.SMART_JOIN,
     "need_rc_holt", A_MEDIUM, 3, 36, 36, 7,
     SubstitutionPolicy.EXACT_ONLY, None, ()),

    # --- Flexible by allowlist: two specific bags they have tried and would buy again.
    #     The model may never add to this list, and nothing in this repository can.
    ("hh_rc_delgado", "Sol D.", 0.0009, 0.0017, AutonomyMode.SMART_JOIN,
     "need_rc_delgado", A_LIGHT, 3, 13, 13, 13,
     SubstitutionPolicy.APPROVED_PRODUCTS, None, (A_MEDIUM, B_DARK)),

    # --- Buying something else, and structurally so. Decaf and ground are not near
    #     misses for a caffeinated bean order; they are different products, and the
    #     curated facts are what say so rather than anybody's judgement.
    ("hh_rc_engstrom", "Alva E.", -0.0006, -0.0016, AutonomyMode.SMART_JOIN,
     "need_rc_engstrom", C_DECAF, 4, 15, 15, 15,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, BEANS_DECAF, ()),
    ("hh_rc_fairbairn", "Cass F.", 0.0014, 0.0019, AutonomyMode.SMART_JOIN,
     "need_rc_fairbairn", D_GROUND, 4, 14, 14, 14,
     SubstitutionPolicy.ATTRIBUTE_CONSTRAINED, GROUND_CAFFEINATED, ()),
    ("hh_rc_gallardo", "Bruno G.", -0.0021, -0.0014, AutonomyMode.ASK_ME,
     "need_rc_gallardo", D_GROUND, 3, 16, 16, 16,
     SubstitutionPolicy.EXACT_ONLY, None, ()),
]


def build_households() -> list[Household]:
    return [
        Household(
            id=hid,
            display_name=name,
            lat=CENTER_LAT + dlat,
            lon=CENTER_LON + dlon,
            neighborhood="Campus core",
            autonomy=AutonomyPolicy(
                mode=mode,
                min_savings_pct=10,
                max_total_cost_cents=20_000,
                max_travel_minutes=30,
                public_pickup_only=True,
            ),
            # Stored privately for notifications; never emitted by a serializer (§82).
            contact_email=f"{hid}@demo.invalid",
            payment_method_ref=f"pm_sim_{hid}",
            synthetic=True,
        )
        for hid, name, dlat, dlon, mode, *_ in _DEMAND
    ]


def build_needs(today: date | None = None) -> list[NeedDeclaration]:
    """The twelve declarations, rebuilt relative to *today* so the fixture never expires."""
    today = today or date.today()
    out: list[NeedDeclaration] = []
    for (
        hid, _name, _dlat, _dlon, _mode,
        nid, product, units, due_days, flex_days, lead_days,
        policy, constraint, allowlist,
    ) in _DEMAND:
        due = today + timedelta(days=due_days)
        out.append(
            NeedDeclaration(
                id=nid,
                household_id=hid,
                community_id=COMMUNITY_ID,
                product_id=product,
                quantity=units,
                cadence_days=30,
                expected_next_need_date=due,
                earliest_acceptable_purchase_date=due - timedelta(days=flex_days),
                latest_acceptable_purchase_date=due,
                routine_lead_days=lead_days,
                min_savings_pct=10,
                max_spend_cents=20_000,
                substitution=policy,
                approved_product_ids=list(allowlist),
                attribute_policy=constraint,
                active=True,
            )
        )
    return out


def install_roast_coffee(repo, workspace: str, today: date | None = None) -> dict[str, int]:
    """Add the heterogeneous coffee community to an already-seeded workspace.

    Idempotent: every entity has a fixed id, so re-installing overwrites rather than
    duplicating. Additive: it removes nothing and touches no seeded row, so a workspace
    that had the whey scenario still has it — which is what lets a community-wide scan in
    this workspace have more than six things to choose between, and therefore lets the
    strategy cap be tested against a real world rather than a contrived one.
    """
    pf.install(repo, workspace)
    for supplier in SUPPLIERS:
        repo.put_supplier(workspace, supplier)
    for offer in build_offers():
        repo.put_offer(workspace, offer)

    households = build_households()
    for household in households:
        repo.put_household(workspace, household)
        repo.put_community_membership(
            workspace,
            CommunityMembership(
                community_id=COMMUNITY_ID,
                household_id=household.id,
                status=MembershipStatus.VERIFIED,
                verification_method=VerificationMethod.DEMO,
                verified_at=iso(utcnow()),
                verification_metadata={"demo": True, "synthetic": True},
            ),
        )

    needs = build_needs(today)
    for need in needs:
        repo.put_need(workspace, need)

    return {
        "products": len(pf.PRODUCTS),
        "suppliers": len(SUPPLIERS),
        "offers": len(build_offers()),
        "households": len(households),
        "needs": len(needs),
    }
