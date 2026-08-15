"""Routing adapters.

One interface, two implementations:

* ``DeterministicRouting`` — a pure function of coordinates. Free, offline, stable,
  and therefore what every test and local demo run uses (AGENTS.md §3.6).
* ``AmazonLocationRouting`` — the real Amazon Location Service Routes API.

Both are bounded: a route matrix is ``origins x destinations`` cells, which multiplies
fast and is billed per cell, so the cap is enforced *before* any call goes out
(AGENTS.md §3.4). Results are cached per instance so repeated agent tool calls in one
run cannot re-bill the same lookup.

The AWS adapter uses ``geo-routes`` (the standalone Routes API) rather than the older
``location`` service deliberately: geo-routes needs no provisioned route-calculator
resource, so there is one less billable, forgettable thing to create and destroy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain.matching import haversine_km

logger = logging.getLogger(__name__)

# Urban surface streets: straight-line distance under-states real driving distance.
ROAD_WINDING_FACTOR = 1.32
ASSUMED_SPEED_KMH = 32.0


class RoutingError(RuntimeError):
    """Routing could not be computed. Never swallowed into a fabricated number."""


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float


@dataclass(frozen=True)
class TravelLeg:
    distance_km: float
    duration_minutes: int
    provider: str

    def to_dict(self) -> dict:
        return {
            "distance_km": round(self.distance_km, 2),
            "duration_minutes": self.duration_minutes,
            "provider": self.provider,
        }


@runtime_checkable
class RoutingService(Protocol):
    name: str

    def travel_matrix(
        self, origins: list[Coordinate], destinations: list[Coordinate]
    ) -> list[list[TravelLeg]]:
        """Return a matrix[origin][destination] of travel legs."""
        ...


def _check_matrix_size(origins: int, destinations: int, max_cells: int) -> None:
    cells = origins * destinations
    if cells == 0:
        raise RoutingError("route matrix requires at least one origin and destination")
    if cells > max_cells:
        raise RoutingError(
            f"route matrix of {origins}x{destinations}={cells} cells exceeds the "
            f"configured cap of {max_cells} (MAX_ROUTE_MATRIX_CELLS)"
        )


class DeterministicRouting:
    """Offline routing derived from great-circle distance.

    Deliberately simple and honest: it is a *model* of travel time, not a claim about
    real roads. Anything user-visible that came from here is labelled with
    ``provider="deterministic"`` so the demo can distinguish simulated from real.
    """

    name = "deterministic"

    def __init__(self, max_cells: int = 100) -> None:
        self.max_cells = max_cells
        self.call_count = 0

    def travel_matrix(
        self, origins: list[Coordinate], destinations: list[Coordinate]
    ) -> list[list[TravelLeg]]:
        _check_matrix_size(len(origins), len(destinations), self.max_cells)
        self.call_count += 1
        matrix: list[list[TravelLeg]] = []
        for o in origins:
            row: list[TravelLeg] = []
            for d in destinations:
                straight = haversine_km(o.lat, o.lon, d.lat, d.lon)
                road_km = straight * ROAD_WINDING_FACTOR
                minutes = int(round(road_km / ASSUMED_SPEED_KMH * 60))
                # A trip is never zero minutes; parking and walking exist.
                row.append(TravelLeg(road_km, max(1, minutes), self.name))
            matrix.append(row)
        return matrix


class AmazonLocationRouting:
    """Amazon Location Service Routes (``geo-routes``) CalculateRouteMatrix.

    Never falls back to a made-up number: if the call fails, it raises. A hallucinated
    route is exactly the failure mode Pool's architecture exists to prevent, so the
    caller decides whether to degrade to the deterministic adapter and, crucially, to
    *say so* in the result (AGENTS.md §5).
    """

    name = "aws_location"

    def __init__(self, region_name: str, max_cells: int = 100, client=None) -> None:
        self.region_name = region_name
        self.max_cells = max_cells
        self._client = client
        self.call_count = 0
        self.cells_billed = 0

    def _get_client(self):
        if self._client is None:
            import boto3  # imported lazily so tests never need boto3 configured

            self._client = boto3.client("geo-routes", region_name=self.region_name)
        return self._client

    def travel_matrix(
        self, origins: list[Coordinate], destinations: list[Coordinate]
    ) -> list[list[TravelLeg]]:
        _check_matrix_size(len(origins), len(destinations), self.max_cells)
        client = self._get_client()
        try:
            response = client.calculate_route_matrix(
                Origins=[{"Position": [o.lon, o.lat]} for o in origins],
                Destinations=[{"Position": [d.lon, d.lat]} for d in destinations],
                RoutingBoundary={"Unbounded": True},
                TravelMode="Car",
            )
        except Exception as exc:  # noqa: BLE001 - surfaced, never silently absorbed
            raise RoutingError(f"Amazon Location route matrix failed: {exc}") from exc

        self.call_count += 1
        self.cells_billed += len(origins) * len(destinations)
        return self.parse_matrix(response)

    def parse_matrix(self, response: dict) -> list[list[TravelLeg]]:
        """Parse a CalculateRouteMatrix response.

        Split out from the call so it can be tested against a recorded response shape
        without any network access or credentials.
        """
        raw = response.get("RouteMatrix")
        if raw is None:
            raise RoutingError("route matrix response missing RouteMatrix")
        matrix: list[list[TravelLeg]] = []
        for row in raw:
            legs: list[TravelLeg] = []
            for cell in row:
                if cell.get("Error"):
                    raise RoutingError(f"route matrix cell error: {cell['Error']}")
                # Distance is metres, Duration is seconds (verified against the
                # geo-routes service model).
                distance_km = float(cell["Distance"]) / 1000.0
                minutes = int(round(float(cell["Duration"]) / 60.0))
                legs.append(TravelLeg(distance_km, max(1, minutes), self.name))
            matrix.append(legs)
        return matrix


class CachingRouting:
    """Memoises legs by coordinate pair so one agent run cannot re-bill a lookup."""

    def __init__(self, inner: RoutingService) -> None:
        self.inner = inner
        self.name = inner.name
        self._cache: dict[tuple, TravelLeg] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    @staticmethod
    def _key(o: Coordinate, d: Coordinate) -> tuple:
        return (round(o.lat, 5), round(o.lon, 5), round(d.lat, 5), round(d.lon, 5))

    def travel_matrix(
        self, origins: list[Coordinate], destinations: list[Coordinate]
    ) -> list[list[TravelLeg]]:
        missing_o: list[Coordinate] = []
        missing_d: list[Coordinate] = []
        for o in origins:
            for d in destinations:
                if self._key(o, d) not in self._cache:
                    if o not in missing_o:
                        missing_o.append(o)
                    if d not in missing_d:
                        missing_d.append(d)

        if missing_o and missing_d:
            fetched = self.inner.travel_matrix(missing_o, missing_d)
            for i, o in enumerate(missing_o):
                for j, d in enumerate(missing_d):
                    self._cache[self._key(o, d)] = fetched[i][j]

        result: list[list[TravelLeg]] = []
        for o in origins:
            row: list[TravelLeg] = []
            for d in destinations:
                leg = self._cache.get(self._key(o, d))
                if leg is None:
                    self.cache_misses += 1
                    leg = self.inner.travel_matrix([o], [d])[0][0]
                    self._cache[self._key(o, d)] = leg
                else:
                    self.cache_hits += 1
                row.append(leg)
            result.append(row)
        return result


def build_routing(provider: str, region_name: str, max_cells: int) -> RoutingService:
    """Factory. Unknown providers fail loudly rather than silently degrading."""
    if provider == "deterministic":
        return CachingRouting(DeterministicRouting(max_cells=max_cells))
    if provider == "aws_location":
        return CachingRouting(AmazonLocationRouting(region_name=region_name, max_cells=max_cells))
    raise ValueError(f"unknown routing provider: {provider!r}")
