from __future__ import annotations

from datetime import date, timedelta

import pytest

from pool.adapters.payments import LocalSimulatedPaymentProvider
from pool.adapters.purchase import SimulatedPurchaseExecutor
from pool.adapters.repository import InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.adapters.sourcing import SyntheticCatalogProvider
from pool.data.seed import COMMUNITY_ID, seed
from pool.domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    Community,
    CommunityKind,
    CommunityMembership,
    HostProfile,
    Household,
    MembershipStatus,
    MoqKind,
    NeedDeclaration,
    Offer,
    OfferKind,
    OfferSource,
    PickupSite,
    PoolDaySchedule,
    Product,
    SubstitutionPolicy,
    Supplier,
    VerificationMethod,
    iso,
    utcnow,
)
from pool.services.context import PoolContext
from pool.services.demo import onboard_consumer

WS = "test"
COMM = "comm_test"
OTHER_COMM = "comm_other"

# A fixed centre for unit fixtures. Synthetic, like everything else in this repository.
LAT = 38.6488
LON = -90.3108


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def routing() -> CachingRouting:
    return CachingRouting(DeterministicRouting(max_cells=100))


@pytest.fixture
def payments() -> LocalSimulatedPaymentProvider:
    return LocalSimulatedPaymentProvider()


@pytest.fixture
def ctx(repo, routing, payments) -> PoolContext:
    """A service context wired entirely to free, offline, deterministic adapters."""
    return PoolContext(
        repo=repo,
        ws=WS,
        routing=routing,
        payments=payments,
        purchaser=SimulatedPurchaseExecutor(),
        sourcing=SyntheticCatalogProvider(),
        now=utcnow(),
    )


@pytest.fixture
def seeded(repo: InMemoryRepository) -> InMemoryRepository:
    seed(repo, WS)
    return repo


@pytest.fixture
def seeded_ctx(seeded, routing, payments) -> PoolContext:
    """The community exactly as ``seed()`` leaves it.

    Rosa has **not** declared the flagship whey need here — the fixture deliberately does
    not seed it, because the first thing the product asks anyone to do is say what they
    buy, and a demo that opens on a declaration nobody was shown making is the
    pre-populated dashboard this design exists to remove. Use ``declared_ctx`` for the
    canonical scenario.
    """
    return PoolContext(
        repo=seeded,
        ws=WS,
        routing=routing,
        payments=payments,
        purchaser=SimulatedPurchaseExecutor(),
        sourcing=SyntheticCatalogProvider(),
        now=utcnow(),
    )


@pytest.fixture
def declared_ctx(seeded_ctx) -> PoolContext:
    """``seeded_ctx``, plus the one declaration a member makes for herself.

    Made through the real ``declare_need`` service, exactly as the form and the showcase
    do, so every canonical-scenario test starts from the same premise a person would
    create by using the product — rather than from a fixture row that quietly stood in
    for them.
    """
    onboard_consumer(seeded_ctx)
    return seeded_ctx


@pytest.fixture
def demo_community_id() -> str:
    return COMMUNITY_ID


# --------------------------------------------------------------------------- builders


def make_community(cid: str = COMM, **overrides) -> Community:
    defaults = {
        "id": cid,
        "name": f"Community {cid}",
        "kind": CommunityKind.UNIVERSITY,
        "center_lat": LAT,
        "center_lon": LON,
        "radius_km": 3.0,
        "schedule": PoolDaySchedule(),
        "verification_methods": [VerificationMethod.DEMO],
    }
    defaults.update(overrides)
    return Community(**defaults)


def make_member(
    hid: str,
    *,
    dlat: float = 0.0,
    dlon: float = 0.0,
    mode: AutonomyMode = AutonomyMode.SMART_JOIN,
    min_savings_pct: int = 10,
    max_spend: int = 100_000,
    max_travel: int = 60,
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY,
    public_only: bool = False,
    payment_method: str | None = None,
    pickup_weekdays: list[int] | None = None,
) -> Household:
    return Household(
        id=hid,
        display_name=f"{hid} member",
        lat=LAT + dlat,
        lon=LON + dlon,
        neighborhood="Test zone",
        autonomy=AutonomyPolicy(
            mode=mode,
            min_savings_pct=min_savings_pct,
            max_total_cost_cents=max_spend,
            max_travel_minutes=max_travel,
            substitution=substitution,
            public_pickup_only=public_only,
            available_pickup_weekdays=pickup_weekdays or [],
        ),
        contact_email=f"{hid}@example.invalid",
        payment_method_ref=f"pm_sim_{hid}" if payment_method is None else payment_method,
    )


def make_need(
    nid: str,
    household_id: str,
    product_id: str,
    quantity: int,
    *,
    community_id: str = COMM,
    days_out: int = 14,
    flexibility_days: int = 14,
    routine_lead_days: int = 14,
    min_savings_pct: int = 10,
    max_spend: int = 100_000,
    substitution: SubstitutionPolicy = SubstitutionPolicy.EXACT_ONLY,
    approved_product_ids: list[str] | None = None,
    approved_brands: list[str] | None = None,
    max_unit_price_cents: int = 0,
    active: bool = True,
) -> NeedDeclaration:
    due = date.today() + timedelta(days=days_out)
    return NeedDeclaration(
        id=nid,
        household_id=household_id,
        community_id=community_id,
        product_id=product_id,
        quantity=quantity,
        cadence_days=30,
        expected_next_need_date=due,
        earliest_acceptable_purchase_date=due - timedelta(days=flexibility_days),
        latest_acceptable_purchase_date=due,
        routine_lead_days=routine_lead_days,
        min_savings_pct=min_savings_pct,
        max_spend_cents=max_spend,
        substitution=substitution,
        approved_product_ids=approved_product_ids or [],
        approved_brands=approved_brands or [],
        max_unit_price_cents=max_unit_price_cents,
        active=active,
    )


def make_membership(
    household_id: str, community_id: str = COMM, verified: bool = True
) -> CommunityMembership:
    return CommunityMembership(
        community_id=community_id,
        household_id=household_id,
        status=MembershipStatus.VERIFIED if verified else MembershipStatus.PENDING_VERIFICATION,
        verification_method=VerificationMethod.DEMO,
        verified_at=iso(utcnow()) if verified else "",
    )


def make_host_profile(household_id: str, community_id: str = COMM, **overrides) -> HostProfile:
    defaults = {
        "household_id": household_id,
        "community_id": community_id,
        "has_vehicle": True,
        "vehicle_capacity_units": 200,
        "max_orders": 100,
        "max_weight_kg": 500,
        "max_supplier_distance_km": 100.0,
        "minimum_compensation_cents": 0,
        "public_pickup_only": False,
        "standing": True,
    }
    defaults.update(overrides)
    return HostProfile(**defaults)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def protein() -> Product:
    return Product(
        "p_protein", "Protein powder", "nutrition", "tub", "protein",
        brand="Northfield", variant="vanilla", unit_weight_grams=2000,
    )


@pytest.fixture
def protein_chocolate() -> Product:
    return Product(
        "p_protein_choc", "Protein powder, chocolate", "nutrition", "tub", "protein",
        brand="Northfield", variant="chocolate", unit_weight_grams=2000,
    )


@pytest.fixture
def protein_rival() -> Product:
    return Product(
        "p_protein_rival", "Protein powder, other brand", "nutrition", "tub", "protein",
        brand="Peakform", variant="vanilla", unit_weight_grams=2000,
    )


@pytest.fixture
def towels() -> Product:
    return Product(
        "p_towels", "Paper towels", "household", "pack", "towels",
        brand="Mapleline", unit_weight_grams=1000,
    )


@pytest.fixture
def supplier() -> Supplier:
    return Supplier("sup_test", "Test Wholesale", LAT + 0.02, LON - 0.02)


@pytest.fixture
def retail_offer() -> Offer:
    """$10.00 per sealed unit at retail."""
    return Offer(
        "o_retail", "sup_test", "p_protein", OfferKind.RETAIL, 1000, 1,
        MoqKind.UNITS, 1, iso(utcnow()), "", OfferSource.SYNTHETIC,
    )


@pytest.fixture
def bulk_offer() -> Offer:
    """$6.00 per unit in 10-unit cases, 20-unit supplier minimum."""
    return Offer(
        "o_bulk", "sup_test", "p_protein", OfferKind.BULK, 600, 10,
        MoqKind.UNITS, 20, iso(utcnow()), "", OfferSource.SYNTHETIC,
    )


@pytest.fixture
def public_site() -> PickupSite:
    return PickupSite("s_union", "Union", COMM, LAT, LON, True, "campus_common")


@pytest.fixture
def private_site() -> PickupSite:
    return PickupSite("s_room", "A private room", COMM, LAT, LON, False, "residence_hall")
