"""Deterministic synthetic dataset for the demo.

Everything here is invented. No real person, address, supplier, or institution is
represented; the Community is called **Demo University** precisely so nothing implies
an endorsement that does not exist (§9), and the coordinates are scattered around a
made-up campus centroid rather than being anyone's room (AGENTS.md §4).

The dataset is *arranged* so an interesting situation exists — that is legitimate
scripting of the scenario. What must never be scripted is the outcome: the agent has to
actually find the overlap, the economics tools have to actually compute the landed
price, the host evaluator has to actually rank the candidates, and the recovery has to
actually re-solve the funding. No number below is a target the code is nudged toward;
the showcase figures are whatever the arithmetic produces (AGENTS.md §8).

The showcase (whey protein)
---------------------------
Students independently declare recurring protein needs. Individually they pay campus
retail. Aggregated, the inner ring clears a supplier's 24-unit minimum — but the
supplier sells 12-unit cases, so the demand has to land on a case boundary or Pool
would be buying speculative stock (§48). Reaching that boundary requires pulling
forward demand from students who *explicitly authorised an early purchase*, which is
the mechanic §24 exists for. One host volunteers from inside the pool while two
standing hosts also qualify, so the ranking has something real to decide. One student's
saved card is set up to decline, so the payment-failure recovery branch is genuine
rather than narrated.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..adapters.repository import Repository
from ..domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    Community,
    CommunityKind,
    CommunityMembership,
    HostProfile,
    Household,
    MembershipStatus,
    MoqKind,
    Offer,
    OfferKind,
    OfferSource,
    PickupPermission,
    PickupSite,
    PlatformFeeConfig,
    PoolDaySchedule,
    Product,
    Supplier,
    VerificationMethod,
    iso,
    utcnow,
)
from ..domain.models import NeedDeclaration as Need
from ..domain.timing import next_pool_day

# A made-up campus centroid. Not a real institution's coordinates.
CENTER_LAT = 38.6488
CENTER_LON = -90.3108

COMMUNITY_ID = "comm_demo_university"

#: The simulated provider declines any method reference containing this marker, which
#: is how the payment-failure branch is triggered deterministically (§60).
DECLINING_METHOD = "pm_sim_declines_demo"


def _d(days: int) -> date:
    return date.today() + timedelta(days=days)


def _fresh() -> str:
    """A quote verified just now — freshness is load-bearing, so it is explicit (§43)."""
    return iso(utcnow())


# --------------------------------------------------------------------------- community

SCHEDULE = PoolDaySchedule(
    formation_cutoff_weekday=3,   # Thursday: candidate pools evaluated
    host_deadline_weekday=4,      # Friday: hosts confirmed
    final_offer_weekday=4,        # Friday: final offers and authorisations
    lock_weekday=4,               # Friday evening: pool locks
    distribution_weekday=5,       # Saturday: supplier pickup and distribution
    distribution_start_hour=14,
    distribution_end_hour=17,
)


def build_community() -> Community:
    return Community(
        id=COMMUNITY_ID,
        name="Demo University",
        kind=CommunityKind.UNIVERSITY,
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        radius_km=2.5,
        timezone="America/Chicago",
        # Demo verification only: this Community is synthetic, so there is no real
        # domain to prove control of and no institution to imply a relationship with.
        verification_methods=[VerificationMethod.DEMO],
        email_domains=[],
        schedule=SCHEDULE,
        platform_fee=PlatformFeeConfig(mode="percent_of_savings", bps=1000),
        quote_max_age_hours=48,
        synthetic=True,
    )


# --------------------------------------------------------------------------- catalogue

PRODUCTS = [
    Product(
        "prod_whey_vanilla", "Whey protein, vanilla", "nutrition", "tub", "whey_protein",
        brand="Northfield", variant="vanilla", unit_weight_grams=2270,
    ),
    Product(
        "prod_whey_chocolate", "Whey protein, chocolate", "nutrition", "tub", "whey_protein",
        brand="Northfield", variant="chocolate", unit_weight_grams=2270,
    ),
    Product(
        "prod_energy_drink", "Energy drink, 12-pack", "beverage", "pack", "energy_drink",
        brand="Voltside", variant="original", unit_weight_grams=4400,
    ),
    Product(
        "prod_coffee_beans", "Whole bean coffee, 2 lb", "beverage", "bag", "coffee",
        brand="Ridgeline", variant="medium roast", unit_weight_grams=907,
    ),
    Product(
        "prod_detergent_pods", "Laundry pods, 96 count", "household", "tub", "detergent",
        brand="Clearwash", variant="fresh", unit_weight_grams=2400,
    ),
    Product(
        "prod_paper_towels", "Paper towels, 6 rolls", "household", "pack", "paper_towels",
        brand="Mapleline", variant="select-a-size", unit_weight_grams=1200,
    ),
]

SUPPLIERS = [
    Supplier("sup_riverbend", "Riverbend Wholesale", CENTER_LAT + 0.041, CENTER_LON - 0.028),
    Supplier("sup_campusmart", "Campus Mart", CENTER_LAT + 0.004, CENTER_LON + 0.003),
    Supplier("sup_ridgeline", "Ridgeline Roasters", CENTER_LAT - 0.052, CENTER_LON + 0.037),
]


def build_offers() -> list[Offer]:
    """Retail baselines and the bulk tiers they are measured against.

    Retail is what one student pays buying alone at the campus store. Bulk tiers only
    open once aggregate demand clears ``moq_amount``, and every case must be filled —
    which is what makes the case structure matter rather than being decoration.
    """
    fresh = _fresh()
    return [
        # --- Showcase. Retail $46.99/tub; bulk 12-tub cases at $31.50, 24-unit minimum.
        #     The case size is the interesting constraint: demand must land on a
        #     multiple of 12 or the pool would be buying stock nobody ordered.
        Offer("off_whey_retail", "sup_campusmart", "prod_whey_vanilla", OfferKind.RETAIL,
              4699, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-WHEY-V"),
        Offer("off_whey_bulk", "sup_riverbend", "prod_whey_vanilla", OfferKind.BULK,
              3150, 12, MoqKind.UNITS, 24, fresh, "", OfferSource.SYNTHETIC, "CASE-WHEY-V-12"),
        # A second, worse bulk tier — the agent has a genuine comparison to make.
        Offer("off_whey_bulk_small", "sup_riverbend", "prod_whey_vanilla", OfferKind.BULK,
              3980, 6, MoqKind.UNITS, 12, fresh, "", OfferSource.SYNTHETIC, "CASE-WHEY-V-6"),

        Offer("off_whey_choc_retail", "sup_campusmart", "prod_whey_chocolate", OfferKind.RETAIL,
              4699, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-WHEY-C"),

        # --- Energy drinks: a second real opportunity that can form on its own.
        Offer("off_energy_retail", "sup_campusmart", "prod_energy_drink", OfferKind.RETAIL,
              1899, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-ENERGY"),
        Offer("off_energy_bulk", "sup_riverbend", "prod_energy_drink", OfferKind.BULK,
              1240, 8, MoqKind.UNITS, 16, fresh, "", OfferSource.SYNTHETIC, "CASE-ENERGY-8"),

        # --- Coffee.
        Offer("off_coffee_retail", "sup_campusmart", "prod_coffee_beans", OfferKind.RETAIL,
              2450, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-COFFEE"),
        Offer("off_coffee_bulk", "sup_ridgeline", "prod_coffee_beans", OfferKind.BULK,
              1690, 6, MoqKind.UNITS, 18, fresh, "", OfferSource.SYNTHETIC, "CASE-COFFEE-6"),

        # --- Detergent: real demand, but the bulk tier barely beats retail. Once host
        #     pay, processing, and Pool's fee are included the saving disappears, so the
        #     correct behaviour is to bother nobody.
        Offer("off_detergent_retail", "sup_campusmart", "prod_detergent_pods", OfferKind.RETAIL,
              2299, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-PODS"),
        Offer("off_detergent_bulk", "sup_riverbend", "prod_detergent_pods", OfferKind.BULK,
              2180, 4, MoqKind.UNITS, 12, fresh, "", OfferSource.SYNTHETIC, "CASE-PODS-4"),

        # --- Paper towels: demand exists but cannot reach the supplier minimum.
        Offer("off_towels_retail", "sup_campusmart", "prod_paper_towels", OfferKind.RETAIL,
              1249, 1, MoqKind.UNITS, 1, fresh, "", OfferSource.SYNTHETIC, "SKU-TOWELS"),
        Offer("off_towels_bulk", "sup_riverbend", "prod_paper_towels", OfferKind.BULK,
              820, 12, MoqKind.CASES, 4, fresh, "", OfferSource.SYNTHETIC, "CASE-TOWELS-12"),
    ]


# --------------------------------------------------------------------------- sites
# Public campus locations only. Every one is marked DEMO: nothing here asserts that a
# real university space has authorised commercial pickup (§67).

SITES = [
    PickupSite("site_union", "Student Union — north entrance", COMMUNITY_ID,
               CENTER_LAT + 0.0016, CENTER_LON + 0.0011, True, "campus_common",
               PickupPermission.DEMO, "Synthetic demo location."),
    PickupSite("site_quad", "Central Quad pavilion", COMMUNITY_ID,
               CENTER_LAT - 0.0021, CENTER_LON + 0.0026, True, "campus_common",
               PickupPermission.DEMO, "Synthetic demo location."),
    PickupSite("site_northhall", "North Hall lobby", COMMUNITY_ID,
               CENTER_LAT + 0.0078, CENTER_LON - 0.0042, True, "residence_hall",
               PickupPermission.DEMO, "Synthetic demo location."),
    PickupSite("site_westapts", "Westgate Apartments common room", COMMUNITY_ID,
               CENTER_LAT - 0.0091, CENTER_LON - 0.0067, True, "apartment_common",
               PickupPermission.DEMO, "Synthetic demo location."),
]


# --------------------------------------------------------------------------- members
# (id, name, dlat, dlon, mode, min savings %, max spend cents, max travel min, substitution)

_MEMBERS: list[tuple] = [
    # --- Inner ring, near the Student Union. The protein pool forms here.
    ("hh_okafor",     "Ada O.",      0.0008,  0.0004, AutonomyMode.SMART_JOIN, 20,  9000, 12),
    ("hh_bergstrom",  "Nils B.",     0.0019, -0.0007, AutonomyMode.SMART_JOIN, 18, 13000, 10),
    ("hh_navarro",    "Rosa N.",    -0.0011,  0.0015, AutonomyMode.ASK_ME,     20,  9000, 15),
    ("hh_thibault",   "Léo T.",      0.0024,  0.0018, AutonomyMode.SMART_JOIN, 15, 13000, 14),
    ("hh_rasmussen",  "Ingrid R.",  -0.0016, -0.0012, AutonomyMode.SMART_JOIN, 22,  9000, 11),
    ("hh_delacroix",  "Yves D.",     0.0004,  0.0023, AutonomyMode.ASK_ME,     18,  9500, 18),
    ("hh_marchetti",  "Gio M.",     -0.0022,  0.0007, AutonomyMode.SMART_JOIN, 20,  9000, 13),
    ("hh_villanueva", "Pia V.",      0.0013, -0.0019, AutonomyMode.SMART_JOIN, 17,  9000, 12),
    ("hh_sandoval",   "Emi S.",      0.0031,  0.0009, AutonomyMode.SMART_JOIN, 18, 13000, 14),
    ("hh_kowalski",   "Jan K.",     -0.0028,  0.0021, AutonomyMode.SMART_JOIN, 20, 13000, 13),

    # --- Middle ring: outside the tight formation radius, inside the recovery radius.
    #     This is where a payment failure finds its replacement.
    ("hh_amadi",      "Chidi A.",    0.0142, -0.0098, AutonomyMode.SMART_JOIN, 15, 13000, 20),
    ("hh_lindqvist",  "Freja L.",   -0.0128, -0.0116, AutonomyMode.SMART_JOIN, 18,  9500, 18),
    ("hh_petrov",     "Mira P.",     0.0163,  0.0074, AutonomyMode.SMART_JOIN, 16,  9500, 22),
    ("hh_castellanos", "Tomás C.",  -0.0151,  0.0132, AutonomyMode.ASK_ME,     18,  9500, 24),

    # --- Wider community: other products, texture, and honest impact metrics.
    ("hh_whitfield",  "Ruth W.",     0.0096,  0.0168, AutonomyMode.SMART_JOIN, 20,  9000, 16),
    ("hh_ferraro",    "Ana F.",     -0.0084,  0.0151, AutonomyMode.SMART_JOIN, 22,  9000, 15),
    ("hh_odonnell",   "Sean O.",     0.0177, -0.0083, AutonomyMode.ASK_ME,     18,  9500, 20),
    ("hh_bhatt",      "Nita B.",    -0.0139, -0.0172, AutonomyMode.SMART_JOIN, 20,  9000, 18),
    ("hh_lindgren",   "Sven L.",     0.0061,  0.0192, AutonomyMode.SMART_JOIN, 18,  9000, 19),
    ("hh_moreau",     "Cléo M.",    -0.0047,  0.0186, AutonomyMode.ASK_ME,     20,  9500, 21),
    ("hh_espinoza",   "Rafa E.",     0.0119,  0.0032, AutonomyMode.SMART_JOIN, 16,  9000, 17),
    ("hh_novak",      "Eva N.",     -0.0126,  0.0044, AutonomyMode.SMART_JOIN, 21,  9000, 14),
    ("hh_quintero",   "Luz Q.",     -0.0103,  0.0119, AutonomyMode.SMART_JOIN, 19,  9000, 16),
    ("hh_soderberg",  "Elin S.",     0.0048, -0.0161, AutonomyMode.SMART_JOIN, 18,  9000, 18),
]

#: Members who set up a saved payment method. Everyone in the showcase ring has one;
#: one of them has a card that will decline, which is how the recovery branch is real.
_NO_PAYMENT_METHOD = {"hh_moreau"}
#: Pia is in the inner ring with current demand, so she is reliably selected into the
#: showcase pool — which is what makes the payment-failure branch fire every run instead
#: of only when the geometry happens to include her.
_DECLINING_CARD = {"hh_villanueva"}


def _zone(dlat: float, dlon: float) -> str:
    if abs(dlat) < 0.005 and abs(dlon) < 0.005:
        return "Campus core"
    if dlat >= 0:
        return "North campus"
    return "South campus"


def build_households() -> list[Household]:
    out: list[Household] = []
    for hid, name, dlat, dlon, mode, min_pct, max_spend, max_travel in _MEMBERS:
        if hid in _NO_PAYMENT_METHOD:
            method = ""
        elif hid in _DECLINING_CARD:
            method = DECLINING_METHOD
        else:
            method = f"pm_sim_{hid}"
        out.append(
            Household(
                id=hid,
                display_name=name,
                lat=CENTER_LAT + dlat,
                lon=CENTER_LON + dlon,
                neighborhood=_zone(dlat, dlon),
                autonomy=AutonomyPolicy(
                    mode=mode,
                    min_savings_pct=min_pct,
                    max_total_cost_cents=max_spend,
                    max_travel_minutes=max_travel,
                    public_pickup_only=True,
                ),
                # Stored privately for notifications; never emitted by a serializer (§82).
                contact_email=f"{hid}@demo.invalid",
                payment_method_ref=method,
                synthetic=True,
            )
        )
    return out


# --------------------------------------------------------------------------- hosts
# (household, has vehicle, max orders, max weight kg, max supplier km, min comp cents)

_STANDING_HOSTS: list[tuple] = [
    ("hh_marchetti", True, 40, 90, 14.0, 4000),
    ("hh_whitfield", True, 30, 70, 12.0, 5500),
    # Willing, but without a vehicle — correctly ineligible for a heavy run, which is
    # what makes the eligibility check visible rather than theoretical.
    ("hh_ferraro", False, 20, 20, 5.0, 2500),
]


def build_host_profiles() -> list[HostProfile]:
    return [
        HostProfile(
            household_id=hid,
            community_id=COMMUNITY_ID,
            willing_to_host=True,
            willing_to_run=True,
            has_vehicle=vehicle,
            vehicle_capacity_units=60 if vehicle else 0,
            max_orders=max_orders,
            max_weight_kg=max_weight,
            max_supplier_distance_km=max_km,
            available_weekdays=[SCHEDULE.distribution_weekday],
            minimum_compensation_cents=min_comp,
            public_pickup_only=True,
            standing=True,
        )
        for hid, vehicle, max_orders, max_weight, max_km, min_comp in _STANDING_HOSTS
    ]


# --------------------------------------------------------------------------- needs
# (need id, member, product, qty, cadence days, days until needed, earliest-buy days
#  before that, routine restock lead days, min savings %, max spend cents)
#
# Two timing numbers do different jobs. ``routine lead`` is how far ahead someone
# ordinarily restocks — a purchase inside it is business as usual. ``earliest`` is how
# far ahead they are *willing* to buy if it saves money, and it is the only thing that
# makes pulling future demand forward legitimate rather than presumptuous. A member
# whose earliest equals their need date cannot be pulled in early no matter how
# convenient it would be for the case count (§24).

_NEEDS: list[tuple] = [
    # --- Whey protein, inner ring. Due within the fortnight and restocking routinely:
    #     18 tubs across 8 students — short of the 24-unit supplier minimum, and short
    #     of a clean 12-unit case boundary.
    ("need_whey_okafor",     "hh_okafor",     "prod_whey_vanilla", 2, 45, 12, 12, 12, 20,  9000),
    ("need_whey_bergstrom",  "hh_bergstrom",  "prod_whey_vanilla", 3, 60, 13, 13, 13, 18, 13000),
    ("need_whey_navarro",    "hh_navarro",    "prod_whey_vanilla", 2, 40, 11, 11, 11, 20,  9000),
    ("need_whey_thibault",   "hh_thibault",   "prod_whey_vanilla", 3, 50, 14, 14, 14, 15, 13000),
    ("need_whey_rasmussen",  "hh_rasmussen",  "prod_whey_vanilla", 2, 45, 12, 12, 12, 22,  9000),
    ("need_whey_delacroix",  "hh_delacroix",  "prod_whey_vanilla", 2, 35, 10, 10, 10, 18,  9500),
    ("need_whey_marchetti",  "hh_marchetti",  "prod_whey_vanilla", 2, 55, 14, 14, 14, 20,  9000),
    ("need_whey_villanueva", "hh_villanueva", "prod_whey_vanilla", 2, 40, 11, 11, 11, 17,  9000),
    # --- Flexible future demand. These two do not run out for another month and would
    #     normally restock a week ahead — but both explicitly authorised buying up to
    #     five weeks early if it saves money. That authorisation is the only reason Pool
    #     may count them, and it is exactly what lets the pool reach 24 units on an
    #     exact case boundary instead of buying stock nobody ordered.
    ("need_whey_sandoval",   "hh_sandoval",   "prod_whey_vanilla", 3, 45, 34, 34,  7, 18, 13000),
    ("need_whey_kowalski",   "hh_kowalski",   "prod_whey_vanilla", 3, 50, 32, 32,  7, 20, 13000),
    # --- Replacement demand in the middle ring, available when an authorisation fails.
    #     Chidi's 3 tubs exactly replace Jan's, which keeps the case count clean.
    ("need_whey_amadi",      "hh_amadi",      "prod_whey_vanilla", 3, 40, 24, 24,  7, 15, 13000),
    ("need_whey_lindqvist",  "hh_lindqvist",  "prod_whey_vanilla", 2, 45, 21, 21,  7, 18,  9500),
    ("need_whey_petrov",     "hh_petrov",     "prod_whey_vanilla", 2, 42, 26, 26,  7, 16,  9500),

    # --- Energy drinks: a second genuine opportunity. Everyone here restocks about a
    #     week ahead but would go earlier for a discount, which is the ordinary shape of
    #     a recurring need — the two timing numbers are not the same thing.
    ("need_energy_espinoza", "hh_espinoza",   "prod_energy_drink", 2, 21, 10, 10,  6, 16, 9000),
    ("need_energy_whitfield","hh_whitfield",  "prod_energy_drink", 2, 28, 12, 12,  7, 20, 9000),
    ("need_energy_lindgren", "hh_lindgren",   "prod_energy_drink", 2, 21, 11, 11,  6, 18, 9000),
    ("need_energy_novak",    "hh_novak",      "prod_energy_drink", 2, 30, 13, 13,  8, 21, 9000),
    ("need_energy_quintero", "hh_quintero",   "prod_energy_drink", 2, 24, 11, 11,  6, 19, 9000),
    ("need_energy_soderberg","hh_soderberg",  "prod_energy_drink", 2, 28, 14, 14,  8, 18, 9000),
    ("need_energy_bhatt",    "hh_bhatt",      "prod_energy_drink", 2, 25, 12, 12,  7, 20, 9000),
    ("need_energy_ferraro",  "hh_ferraro",    "prod_energy_drink", 2, 30, 15, 15,  9, 22, 9000),

    # --- Coffee.
    ("need_coffee_lindgren", "hh_lindgren",   "prod_coffee_beans", 3, 30, 13, 13,  7, 18, 9000),
    ("need_coffee_quintero", "hh_quintero",   "prod_coffee_beans", 3, 28, 12, 12,  7, 19, 9000),
    ("need_coffee_moreau",   "hh_moreau",     "prod_coffee_beans", 3, 35, 16, 16,  9, 20, 9500),
    ("need_coffee_odonnell", "hh_odonnell",   "prod_coffee_beans", 3, 32, 14, 14,  8, 18, 9500),
    ("need_coffee_petrov",   "hh_petrov",     "prod_coffee_beans", 3, 30, 15, 15,  8, 16, 9500),
    ("need_coffee_amadi",    "hh_amadi",      "prod_coffee_beans", 3, 28, 13, 13,  7, 15, 13000),

    # --- Detergent: real demand, but the bulk tier barely beats retail. Once host pay,
    #     processing, and Pool's fee are included the saving is gone, so the correct
    #     behaviour is to bother nobody.
    ("need_deter_novak",     "hh_novak",      "prod_detergent_pods", 4, 90, 20, 20, 10, 21, 9000),
    ("need_deter_moreau",    "hh_moreau",     "prod_detergent_pods", 4, 90, 22, 22, 10, 20, 9500),
    ("need_deter_bhatt",     "hh_bhatt",      "prod_detergent_pods", 4, 80, 18, 18, 10, 20, 9000),

    # --- Paper towels: demand exists, but never enough to clear the minimum.
    ("need_towels_okafor",   "hh_okafor",     "prod_paper_towels", 2, 30, 14, 14,  7, 20, 9000),
    ("need_towels_navarro",  "hh_navarro",    "prod_paper_towels", 2, 30, 15, 15,  7, 20, 9000),
    ("need_towels_castellanos", "hh_castellanos", "prod_paper_towels", 2, 35, 16, 16, 8, 18, 9500),
]


def build_needs(today: date | None = None) -> list[Need]:
    today = today or date.today()
    out: list[Need] = []
    for nid, hh, prod, qty, cadence, due_days, flex, lead, min_pct, max_spend in _NEEDS:
        due = today + timedelta(days=due_days)
        out.append(
            Need(
                id=nid,
                household_id=hh,
                community_id=COMMUNITY_ID,
                product_id=prod,
                quantity=qty,
                cadence_days=cadence,
                expected_next_need_date=due,
                earliest_acceptable_purchase_date=due - timedelta(days=flex),
                latest_acceptable_purchase_date=due,
                routine_lead_days=lead,
                min_savings_pct=min_pct,
                max_spend_cents=max_spend,
                active=True,
            )
        )
    return out


# --------------------------------------------------------------------------- seed


def seed(repo: Repository, workspace: str) -> dict[str, int]:
    """Populate a workspace with the deterministic demo dataset.

    Idempotent by construction: every entity has a fixed id, so re-seeding overwrites
    rather than duplicating. Needs are rebuilt relative to *today*, so the dataset stays
    interesting whenever the demo is run rather than expiring quietly (§92).
    """
    repo.reset(workspace)
    community = build_community()
    repo.put_community(workspace, community)

    for p in PRODUCTS:
        repo.put_product(workspace, p)
    for s in SUPPLIERS:
        repo.put_supplier(workspace, s)
    for o in build_offers():
        repo.put_offer(workspace, o)
    for site in SITES:
        repo.put_site(workspace, site)

    households = build_households()
    for h in households:
        repo.put_household(workspace, h)
        # Demo Community: membership is verified immediately and says so. Nothing here
        # claims a real institution verified anybody (§10).
        repo.put_community_membership(
            workspace,
            CommunityMembership(
                community_id=COMMUNITY_ID,
                household_id=h.id,
                status=MembershipStatus.VERIFIED,
                verification_method=VerificationMethod.DEMO,
                verified_at=iso(utcnow()),
                verification_metadata={"demo": True, "synthetic": True},
            ),
        )

    for profile in build_host_profiles():
        repo.put_host_profile(workspace, profile)

    needs = build_needs()
    for n in needs:
        repo.put_need(workspace, n)

    return {
        "communities": 1,
        "products": len(PRODUCTS),
        "suppliers": len(SUPPLIERS),
        "offers": len(build_offers()),
        "sites": len(SITES),
        "members": len(households),
        "host_profiles": len(_STANDING_HOSTS),
        "needs": len(needs),
        "next_pool_day": next_pool_day(date.today(), SCHEDULE).isoformat(),
    }
