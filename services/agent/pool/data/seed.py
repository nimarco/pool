"""Deterministic synthetic dataset for the demo.

Everything here is invented. No real household, address, supplier, or organisation is
represented, and the coordinates are scattered around a neighbourhood centroid rather
than being anyone's home (AGENTS.md §4).

The dataset is *arranged* so an interesting situation exists — that is legitimate
scripting of the scenario. What must never be scripted is the outcome: the agent has
to actually find the overlap, the pricing tools have to actually compute the savings,
and the recovery has to actually re-solve the threshold. No number below is a target
the code is nudged toward; the showcase figures are whatever the arithmetic produces.

Showcase (Jasmine rice)
    8 nearby households declare overlapping rice needs. Individually they pay retail.
    Aggregated they clear a supplier's 120 lb minimum, which unlocks 50 lb sacks.
    One household then withdraws, dropping the pool under the minimum, and a
    compatible household from the wider neighbourhood can restore it.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..adapters.repository import Repository
from ..domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    Household,
    NeedDeclaration,
    Offer,
    OfferKind,
    PickupSite,
    Product,
)

# Neighbourhood centroid for the synthetic dataset (a residential grid, no real address).
CENTER_LAT = 38.6558
CENTER_LON = -90.3050


def _d(days: int) -> date:
    return date.today() + timedelta(days=days)


# --------------------------------------------------------------------------- products

PRODUCTS = [
    Product("prod_rice_jasmine", "Jasmine rice", "pantry", "lb", "rice"),
    Product("prod_rice_generic", "Long-grain white rice", "pantry", "lb", "rice"),
    Product("prod_paper_towels", "Paper towels", "household", "roll", "paper_towels"),
    Product("prod_detergent", "Laundry detergent", "household", "load", "detergent"),
    Product("prod_coffee", "Whole bean coffee", "pantry", "oz", "coffee"),
    Product("prod_dog_food", "Dry dog food", "pet", "lb", "dog_food"),
    Product("prod_canned_tomato", "Canned diced tomatoes", "pantry", "count", "canned_tomato"),
    Product("prod_dish_soap", "Dish soap", "household", "oz", "dish_soap"),
]

# --------------------------------------------------------------------------- offers
# Retail = what one household pays buying alone. Bulk = the supplier tier that only
# opens up once aggregate demand clears `min_units`.

OFFERS = [
    # Showcase product. Retail 135c/lb; bulk 25 lb bags at 69c/lb, 150 lb minimum.
    # The minimum sits just under the inner ring's aggregate demand, which is what
    # makes a single withdrawal genuinely break the pool rather than merely dent it.
    Offer("off_rice_retail", "Neighborhood Grocer", "prod_rice_jasmine", OfferKind.RETAIL, 135, 1, 1, _d(60)),
    Offer("off_rice_bulk", "Riverbend Wholesale", "prod_rice_jasmine", OfferKind.BULK, 69, 25, 150, _d(30)),
    # A second, worse bulk tier — gives the agent a genuine comparison to make.
    Offer("off_rice_bulk_small", "Riverbend Wholesale", "prod_rice_jasmine", OfferKind.BULK, 104, 25, 50, _d(30)),

    Offer("off_towels_retail", "Neighborhood Grocer", "prod_paper_towels", OfferKind.RETAIL, 210, 1, 1, _d(60)),
    Offer("off_towels_bulk", "Riverbend Wholesale", "prod_paper_towels", OfferKind.BULK, 138, 24, 48, _d(25)),

    # Detergent: the bulk tier barely beats retail. Correct outcome is "no pool".
    Offer("off_detergent_retail", "Neighborhood Grocer", "prod_detergent", OfferKind.RETAIL, 32, 1, 1, _d(60)),
    Offer("off_detergent_bulk", "Riverbend Wholesale", "prod_detergent", OfferKind.BULK, 30, 96, 192, _d(30)),

    Offer("off_coffee_retail", "Neighborhood Grocer", "prod_coffee", OfferKind.RETAIL, 89, 1, 1, _d(60)),
    Offer("off_coffee_bulk", "Cascade Roasters", "prod_coffee", OfferKind.BULK, 54, 80, 160, _d(20)),

    Offer("off_dogfood_retail", "Neighborhood Grocer", "prod_dog_food", OfferKind.RETAIL, 178, 1, 1, _d(60)),
    Offer("off_dogfood_bulk", "Riverbend Wholesale", "prod_dog_food", OfferKind.BULK, 112, 40, 80, _d(35)),

    Offer("off_tomato_retail", "Neighborhood Grocer", "prod_canned_tomato", OfferKind.RETAIL, 189, 1, 1, _d(60)),
    Offer("off_tomato_bulk", "Riverbend Wholesale", "prod_canned_tomato", OfferKind.BULK, 118, 24, 72, _d(40)),
]

# --------------------------------------------------------------------------- sites
# Public community locations are preferred; the one residence is opt-in and is used to
# demonstrate that offering a private home is a consequential, approval-gated action.

SITES = [
    PickupSite("site_maple_library", "Maplewood Branch Library", CENTER_LAT + 0.0035, CENTER_LON + 0.0021, True, "library"),
    PickupSite("site_commons", "Delmar Commons Community Center", CENTER_LAT - 0.0060, CENTER_LON + 0.0074, True, "community_center"),
    PickupSite("site_rec", "Skinker Recreation Center", CENTER_LAT + 0.0102, CENTER_LON - 0.0085, True, "community_center"),
    PickupSite("site_elem", "Fairfax Elementary", CENTER_LAT - 0.0128, CENTER_LON - 0.0043, True, "school"),
    PickupSite("site_host_okafor", "Host: Okafor household", CENTER_LAT + 0.0018, CENTER_LON + 0.0009, False, "residence"),
]


# --------------------------------------------------------------------------- households
# (id, name, dlat, dlon, host_willing, autonomy mode, min savings %, max spend $, max travel min, substitutes ok)
_HOUSEHOLDS: list[tuple] = [
    # --- Inner ring: close to Maplewood Branch Library. The rice pool forms here.
    ("hh_okafor",    "Okafor household",    0.0018,  0.0009, True,  AutonomyMode.SMART_JOIN, 25, 3000, 10, False),
    ("hh_bergstrom", "Bergstrom household", 0.0041, -0.0012, False, AutonomyMode.SMART_JOIN, 30, 2500,  8, False),
    ("hh_navarro",   "Navarro household",  -0.0022,  0.0033, False, AutonomyMode.ASK_ME,     20, 4000, 15, True),
    ("hh_thibault",  "Thibault household",  0.0056,  0.0040, False, AutonomyMode.SMART_JOIN, 20, 3500, 12, True),
    ("hh_rasmussen", "Rasmussen household",-0.0037, -0.0028, False, AutonomyMode.SMART_JOIN, 35, 2000,  9, False),
    ("hh_delacroix", "Delacroix household", 0.0009,  0.0052, False, AutonomyMode.ASK_ME,     20, 5000, 20, True),
    ("hh_marchetti", "Marchetti household",-0.0051,  0.0016, True,  AutonomyMode.SMART_JOIN, 25, 3000, 12, False),
    ("hh_villanueva","Villanueva household",0.0028, -0.0044, False, AutonomyMode.SMART_JOIN, 22, 2800, 11, True),

    # --- Middle ring: outside the tight formation radius, inside the recovery radius.
    #     This is where dropout recovery finds a replacement.
    ("hh_sandoval",  "Sandoval household",  0.0210,  0.0165, False, AutonomyMode.SMART_JOIN, 20, 4000, 18, True),
    ("hh_kowalski",  "Kowalski household", -0.0245,  0.0128, False, AutonomyMode.ASK_ME,     25, 3500, 20, False),
    ("hh_amadi",     "Amadi household",     0.0198, -0.0223, False, AutonomyMode.SMART_JOIN, 20, 4500, 22, True),
    ("hh_lindqvist", "Lindqvist household",-0.0176, -0.0195, False, AutonomyMode.SMART_JOIN, 28, 3000, 16, False),

    # --- Outer ring: other products, neighbourhood texture, and impact metrics.
    ("hh_petrov",    "Petrov household",    0.0301,  0.0088, False, AutonomyMode.SMART_JOIN, 20, 4000, 20, True),
    ("hh_castellanos","Castellanos household",-0.0288, 0.0245, False, AutonomyMode.ASK_ME,   20, 6000, 25, True),
    ("hh_whitfield", "Whitfield household",  0.0142,  0.0298, True,  AutonomyMode.SMART_JOIN, 25, 3500, 15, False),
    ("hh_ferraro",   "Ferraro household",   -0.0119,  0.0271, False, AutonomyMode.SMART_JOIN, 30, 2500, 14, False),
    ("hh_odonnell",  "O'Donnell household",  0.0256, -0.0142, False, AutonomyMode.ASK_ME,     20, 4000, 18, True),
    ("hh_bhatt",     "Bhatt household",     -0.0221, -0.0266, False, AutonomyMode.SMART_JOIN, 25, 3200, 17, True),
    ("hh_lindgren",  "Lindgren household",   0.0088,  0.0331, False, AutonomyMode.SMART_JOIN, 20, 3800, 19, False),
    ("hh_moreau",    "Moreau household",    -0.0064,  0.0312, False, AutonomyMode.ASK_ME,     22, 4200, 21, True),
    ("hh_espinoza",  "Espinoza household",   0.0175,  0.0043, False, AutonomyMode.SMART_JOIN, 20, 3000, 16, True),
    ("hh_novak",     "Novak household",     -0.0203,  0.0061, False, AutonomyMode.SMART_JOIN, 26, 2700, 13, False),
    ("hh_achterberg","Achterberg household", 0.0132, -0.0311, False, AutonomyMode.ASK_ME,     20, 5000, 24, True),
    ("hh_quintero",  "Quintero household",  -0.0155,  0.0189, True,  AutonomyMode.SMART_JOIN, 24, 3300, 15, False),
    ("hh_soderberg", "Soderberg household",  0.0067, -0.0258, False, AutonomyMode.SMART_JOIN, 20, 3600, 18, True),
]


def _neighborhood_for(dlat: float, dlon: float) -> str:
    if abs(dlat) < 0.008 and abs(dlon) < 0.008:
        return "Maplewood Core"
    if dlat >= 0:
        return "North Delmar"
    return "South Fairfax"


def build_households() -> list[Household]:
    out: list[Household] = []
    for hid, name, dlat, dlon, host, mode, min_pct, max_spend, max_travel, subs in _HOUSEHOLDS:
        out.append(
            Household(
                id=hid,
                display_name=name,
                neighborhood=_neighborhood_for(dlat, dlon),
                lat=CENTER_LAT + dlat,
                lon=CENTER_LON + dlon,
                is_host_willing=host,
                autonomy=AutonomyPolicy(
                    mode=mode,
                    min_savings_pct=min_pct,
                    max_total_cost_cents=max_spend,
                    max_travel_minutes=max_travel,
                    allow_substitutes=subs,
                    public_pickup_only=not host,
                ),
                synthetic=True,
            )
        )
    return out


# (need id, household, product, qty, cadence days, needed in N days, min savings %, max spend $, subs ok)
_NEEDS: list[tuple] = [
    # --- Rice: the showcase. Inner ring, 125 lb aggregate against a 120 lb minimum.
    ("need_rice_okafor",     "hh_okafor",     "prod_rice_jasmine", 15, 42, 21, 25, 3000, False),
    ("need_rice_bergstrom",  "hh_bergstrom",  "prod_rice_jasmine", 20, 56, 24, 30, 2500, False),
    ("need_rice_navarro",    "hh_navarro",    "prod_rice_jasmine", 10, 30, 18, 20, 4000, True),
    ("need_rice_thibault",   "hh_thibault",   "prod_rice_jasmine", 25, 60, 26, 20, 3500, True),
    ("need_rice_rasmussen",  "hh_rasmussen",  "prod_rice_jasmine", 15, 45, 22, 35, 2000, False),
    ("need_rice_delacroix",  "hh_delacroix",  "prod_rice_jasmine", 12, 35, 19, 20, 5000, True),
    ("need_rice_marchetti",  "hh_marchetti",  "prod_rice_jasmine", 18, 50, 25, 25, 3000, False),
    ("need_rice_villanueva", "hh_villanueva", "prod_rice_jasmine", 10, 40, 20, 22, 2800, True),
    # --- Rice, middle ring: latent demand available for dropout recovery.
    ("need_rice_sandoval",   "hh_sandoval",   "prod_rice_jasmine", 25, 45, 23, 20, 4000, True),
    ("need_rice_kowalski",   "hh_kowalski",   "prod_rice_jasmine", 20, 50, 27, 25, 3500, False),
    ("need_rice_amadi",      "hh_amadi",      "prod_rice_generic", 30, 40, 22, 20, 4500, True),
    ("need_rice_lindqvist",  "hh_lindqvist",  "prod_rice_jasmine", 15, 42, 24, 28, 3000, False),

    # --- Paper towels: a second real opportunity, forms on its own.
    ("need_towels_okafor",   "hh_okafor",     "prod_paper_towels", 12, 30, 14, 20, 3000, False),
    ("need_towels_petrov",   "hh_petrov",     "prod_paper_towels", 12, 35, 16, 20, 4000, True),
    ("need_towels_whitfield","hh_whitfield",  "prod_paper_towels",  8, 28, 15, 25, 3500, False),
    ("need_towels_ferraro",  "hh_ferraro",    "prod_paper_towels", 10, 30, 17, 30, 2500, False),
    ("need_towels_espinoza", "hh_espinoza",   "prod_paper_towels", 12, 32, 15, 20, 3000, True),

    # --- Detergent: real demand, but the bulk tier barely beats retail.
    #     Correct behaviour is to terminate without bothering anyone.
    ("need_deter_novak",     "hh_novak",      "prod_detergent",    96, 90, 30, 26, 2700, False),
    ("need_deter_moreau",    "hh_moreau",     "prod_detergent",    96, 90, 32, 22, 4200, True),
    ("need_deter_bhatt",     "hh_bhatt",      "prod_detergent",    96, 80, 28, 25, 3200, True),

    # --- Coffee.
    ("need_coffee_lindgren", "hh_lindgren",   "prod_coffee",       80, 30, 12, 20, 3800, False),
    ("need_coffee_quintero", "hh_quintero",   "prod_coffee",       80, 28, 13, 24, 3300, False),
    ("need_coffee_soderberg","hh_soderberg",  "prod_coffee",       48, 35, 14, 20, 3600, True),

    # --- Dog food.
    ("need_dog_castellanos", "hh_castellanos","prod_dog_food",     40, 45, 20, 20, 6000, True),
    ("need_dog_odonnell",    "hh_odonnell",   "prod_dog_food",     40, 50, 22, 20, 4000, True),
    ("need_dog_achterberg",  "hh_achterberg", "prod_dog_food",     20, 40, 19, 20, 5000, True),

    # --- Canned tomatoes.
    ("need_tom_navarro",     "hh_navarro",    "prod_canned_tomato",24, 60, 25, 20, 4000, True),
    ("need_tom_marchetti",   "hh_marchetti",  "prod_canned_tomato",24, 60, 26, 25, 3000, False),
    ("need_tom_petrov",      "hh_petrov",     "prod_canned_tomato",24, 55, 24, 20, 4000, True),
]


def build_needs() -> list[NeedDeclaration]:
    return [
        NeedDeclaration(
            id=nid,
            household_id=hh,
            product_id=prod,
            quantity=qty,
            cadence_days=cadence,
            needed_by=_d(days),
            min_savings_pct=min_pct,
            max_spend_cents=max_spend,
            accept_substitutes=subs,
            active=True,
        )
        for nid, hh, prod, qty, cadence, days, min_pct, max_spend, subs in _NEEDS
    ]


def seed(repo: Repository, workspace: str) -> dict[str, int]:
    """Populate a workspace with the deterministic demo dataset.

    Idempotent by construction: every entity has a fixed id, so re-seeding overwrites
    rather than duplicating.
    """
    repo.reset(workspace)
    for p in PRODUCTS:
        repo.put_product(workspace, p)
    for o in OFFERS:
        repo.put_offer(workspace, o)
    for s in SITES:
        repo.put_site(workspace, s)
    households = build_households()
    for h in households:
        repo.put_household(workspace, h)
    needs = build_needs()
    for n in needs:
        repo.put_need(workspace, n)
    return {
        "products": len(PRODUCTS),
        "offers": len(OFFERS),
        "sites": len(SITES),
        "households": len(households),
        "needs": len(needs),
    }
