from __future__ import annotations

from datetime import date, timedelta

import pytest

from pool.adapters.repository import InMemoryRepository
from pool.adapters.routing import CachingRouting, DeterministicRouting
from pool.data.seed import seed
from pool.domain.models import (
    AutonomyMode,
    AutonomyPolicy,
    Household,
    NeedDeclaration,
    Offer,
    OfferKind,
    PickupSite,
    Product,
)

WS = "test"


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def routing() -> CachingRouting:
    return CachingRouting(DeterministicRouting(max_cells=100))


@pytest.fixture
def seeded(repo: InMemoryRepository) -> InMemoryRepository:
    seed(repo, WS)
    return repo


@pytest.fixture
def rice() -> Product:
    return Product("p_rice", "Rice", "pantry", "lb", "rice")


@pytest.fixture
def rice_generic() -> Product:
    return Product("p_rice_generic", "Generic rice", "pantry", "lb", "rice")


@pytest.fixture
def towels() -> Product:
    return Product("p_towels", "Paper towels", "household", "roll", "towels")


@pytest.fixture
def retail_offer() -> Offer:
    return Offer("o_retail", "Grocer", "p_rice", OfferKind.RETAIL, 100, 1, 1, None)


@pytest.fixture
def bulk_offer() -> Offer:
    """60c/unit in 25-unit cases, 100-unit supplier minimum."""
    return Offer("o_bulk", "Wholesale", "p_rice", OfferKind.BULK, 60, 25, 100, None)


def make_household(
    hid: str,
    *,
    lat: float = 38.65,
    lon: float = -90.30,
    mode: AutonomyMode = AutonomyMode.SMART_JOIN,
    min_savings_pct: int = 20,
    max_spend: int = 10_000,
    max_travel: int = 30,
    allow_substitutes: bool = False,
    public_only: bool = False,
    host: bool = False,
) -> Household:
    return Household(
        id=hid,
        display_name=f"{hid} household",
        neighborhood="Test",
        lat=lat,
        lon=lon,
        is_host_willing=host,
        autonomy=AutonomyPolicy(
            mode=mode,
            min_savings_pct=min_savings_pct,
            max_total_cost_cents=max_spend,
            max_travel_minutes=max_travel,
            allow_substitutes=allow_substitutes,
            public_pickup_only=public_only,
        ),
    )


def make_need(
    nid: str,
    household_id: str,
    product_id: str,
    quantity: int,
    *,
    days_out: int = 20,
    min_savings_pct: int = 20,
    max_spend: int = 10_000,
    accept_substitutes: bool = False,
    active: bool = True,
) -> NeedDeclaration:
    return NeedDeclaration(
        id=nid,
        household_id=household_id,
        product_id=product_id,
        quantity=quantity,
        cadence_days=30,
        needed_by=date.today() + timedelta(days=days_out),
        min_savings_pct=min_savings_pct,
        max_spend_cents=max_spend,
        accept_substitutes=accept_substitutes,
        active=active,
    )


@pytest.fixture
def public_site() -> PickupSite:
    return PickupSite("s_lib", "Library", 38.65, -90.30, True, "library")


@pytest.fixture
def private_site() -> PickupSite:
    return PickupSite("s_home", "A residence", 38.65, -90.30, False, "residence")
