from __future__ import annotations

import pytest

from pool.adapters.routing import (
    AmazonLocationRouting,
    CachingRouting,
    Coordinate,
    DeterministicRouting,
    RoutingError,
    build_routing,
)

HERE = Coordinate(38.6558, -90.3050)
NEAR = Coordinate(38.6600, -90.3000)
FAR = Coordinate(38.7500, -90.2000)


class TestDeterministicRouting:
    def test_is_deterministic(self):
        r = DeterministicRouting()
        assert r.travel_matrix([HERE], [NEAR]) == r.travel_matrix([HERE], [NEAR])

    def test_farther_takes_longer(self):
        r = DeterministicRouting()
        m = r.travel_matrix([HERE], [NEAR, FAR])
        assert m[0][0].duration_minutes < m[0][1].duration_minutes

    def test_never_reports_a_zero_minute_trip(self):
        r = DeterministicRouting()
        assert r.travel_matrix([HERE], [HERE])[0][0].duration_minutes >= 1

    def test_matrix_shape(self):
        m = DeterministicRouting().travel_matrix([HERE, NEAR], [NEAR, FAR, HERE])
        assert len(m) == 2 and all(len(row) == 3 for row in m)

    def test_labels_its_own_provider(self):
        """User-visible numbers must be attributable to a real or simulated source."""
        assert DeterministicRouting().travel_matrix([HERE], [NEAR])[0][0].provider == "deterministic"


class TestMatrixBounds:
    def test_rejects_a_matrix_over_the_cap(self):
        """A route matrix is billed per cell — the cap is enforced before any call."""
        r = DeterministicRouting(max_cells=10)
        origins = [HERE] * 4
        destinations = [NEAR] * 4  # 16 cells
        with pytest.raises(RoutingError, match="exceeds the configured cap"):
            r.travel_matrix(origins, destinations)

    def test_allows_a_matrix_at_the_cap(self):
        r = DeterministicRouting(max_cells=4)
        assert len(r.travel_matrix([HERE, NEAR], [HERE, NEAR])) == 2

    def test_rejects_empty(self):
        with pytest.raises(RoutingError):
            DeterministicRouting().travel_matrix([], [NEAR])

    def test_cap_applies_to_the_aws_adapter_before_any_call(self):
        class ExplodingClient:
            def calculate_route_matrix(self, **kw):
                raise AssertionError("must not be called once the cap is exceeded")

        aws = AmazonLocationRouting("us-east-1", max_cells=1, client=ExplodingClient())
        with pytest.raises(RoutingError, match="exceeds the configured cap"):
            aws.travel_matrix([HERE, NEAR], [HERE, NEAR])


class FakeGeoRoutes:
    """Records requests and returns a response in the real geo-routes shape."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response
        self._error = error

    def calculate_route_matrix(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


class TestAmazonLocationRouting:
    # Shape verified against the botocore geo-routes service model: Distance is
    # metres, Duration is seconds, RouteMatrix is [origin][destination].
    RESPONSE = {
        "RouteMatrix": [
            [{"Distance": 3200, "Duration": 480}, {"Distance": 12800, "Duration": 1500}],
        ],
        "ErrorCount": 0,
        "PricingBucket": "RouteMatrix",
        "RoutingBoundary": {"Unbounded": True},
    }

    def test_parses_metres_and_seconds_correctly(self):
        aws = AmazonLocationRouting("us-east-1", client=FakeGeoRoutes(self.RESPONSE))
        m = aws.travel_matrix([HERE], [NEAR, FAR])
        assert m[0][0].distance_km == pytest.approx(3.2)
        assert m[0][0].duration_minutes == 8
        assert m[0][1].distance_km == pytest.approx(12.8)
        assert m[0][1].duration_minutes == 25
        assert m[0][0].provider == "aws_location"

    def test_sends_positions_as_lon_lat(self):
        """geo-routes takes [longitude, latitude] — reversing them silently routes
        somewhere in the Indian Ocean."""
        client = FakeGeoRoutes(self.RESPONSE)
        AmazonLocationRouting("us-east-1", client=client).travel_matrix([HERE], [NEAR, FAR])
        sent = client.calls[0]
        assert sent["Origins"] == [{"Position": [HERE.lon, HERE.lat]}]
        assert sent["Destinations"][0] == {"Position": [NEAR.lon, NEAR.lat]}
        assert sent["RoutingBoundary"] == {"Unbounded": True}
        assert sent["TravelMode"] == "Car"

    def test_counts_billable_cells(self):
        aws = AmazonLocationRouting("us-east-1", client=FakeGeoRoutes(self.RESPONSE))
        aws.travel_matrix([HERE], [NEAR, FAR])
        assert aws.cells_billed == 2
        assert aws.call_count == 1

    def test_api_failure_raises_rather_than_inventing_a_route(self):
        """The one behaviour that matters most: never fabricate a distance."""
        aws = AmazonLocationRouting("us-east-1", client=FakeGeoRoutes(error=RuntimeError("boom")))
        with pytest.raises(RoutingError, match="route matrix failed"):
            aws.travel_matrix([HERE], [NEAR])

    def test_cell_level_error_raises(self):
        bad = {"RouteMatrix": [[{"Distance": 0, "Duration": 0, "Error": "NoMatch"}]]}
        aws = AmazonLocationRouting("us-east-1", client=FakeGeoRoutes(bad))
        with pytest.raises(RoutingError, match="cell error"):
            aws.travel_matrix([HERE], [NEAR])

    def test_missing_matrix_raises(self):
        aws = AmazonLocationRouting("us-east-1", client=FakeGeoRoutes({"ErrorCount": 0}))
        with pytest.raises(RoutingError, match="missing RouteMatrix"):
            aws.travel_matrix([HERE], [NEAR])


class CountingRouting:
    name = "counting"

    def __init__(self):
        self.calls = 0

    def travel_matrix(self, origins, destinations):
        self.calls += 1
        return [[__import__("pool.adapters.routing", fromlist=["TravelLeg"]).TravelLeg(1.0, 5, self.name)
                 for _ in destinations] for _ in origins]


class TestCaching:
    def test_repeated_lookups_do_not_re_bill(self):
        inner = CountingRouting()
        cached = CachingRouting(inner)
        cached.travel_matrix([HERE, NEAR], [FAR])
        cached.travel_matrix([HERE, NEAR], [FAR])
        cached.travel_matrix([HERE], [FAR])
        assert inner.calls == 1
        assert cached.cache_hits > 0

    def test_new_coordinates_still_fetch(self):
        inner = CountingRouting()
        cached = CachingRouting(inner)
        cached.travel_matrix([HERE], [FAR])
        cached.travel_matrix([NEAR], [FAR])
        assert inner.calls == 2


class TestFactory:
    def test_builds_known_providers(self):
        assert build_routing("deterministic", "us-east-1", 100).name == "deterministic"
        assert build_routing("aws_location", "us-east-1", 100).name == "aws_location"

    def test_unknown_provider_fails_loudly(self):
        with pytest.raises(ValueError, match="unknown routing provider"):
            build_routing("magic", "us-east-1", 100)
