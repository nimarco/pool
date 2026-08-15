from __future__ import annotations

from datetime import date, timedelta

from pool.domain.matching import find_candidates, haversine_km, products_compatible

from .conftest import make_household, make_need


class TestProductCompatibility:
    def test_exact_match_always_compatible(self, rice):
        assert products_compatible(rice, rice, accept_substitutes=False) == (True, True)

    def test_substitute_requires_explicit_opt_in(self, rice, rice_generic):
        assert products_compatible(rice, rice_generic, accept_substitutes=False) == (False, False)
        assert products_compatible(rice, rice_generic, accept_substitutes=True) == (True, False)

    def test_different_group_never_compatible(self, rice, towels):
        assert products_compatible(rice, towels, accept_substitutes=True) == (False, False)


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_km(38.65, -90.30, 38.65, -90.30) == 0

    def test_known_separation(self):
        # ~0.01 degrees of latitude is ~1.11 km.
        d = haversine_km(38.65, -90.30, 38.66, -90.30)
        assert 1.0 < d < 1.2


def _fixture_world(rice, rice_generic, towels):
    products = {p.id: p for p in (rice, rice_generic, towels)}
    return products


class TestFindCandidates:
    def _run(self, rice, rice_generic, towels, needs, households, **kw):
        params = dict(
            target_product=rice,
            needs=needs,
            households={h.id: h for h in households},
            products=_fixture_world(rice, rice_generic, towels),
            pickup_lat=38.65,
            pickup_lon=-90.30,
            pickup_by=date.today() + timedelta(days=10),
        )
        params.update(kw)
        return find_candidates(**params)

    def test_finds_exact_matches(self, rice, rice_generic, towels):
        hs = [make_household("h1"), make_household("h2")]
        needs = [make_need("n1", "h1", "p_rice", 10), make_need("n2", "h2", "p_rice", 20)]
        r = self._run(rice, rice_generic, towels, needs, hs)
        assert len(r.candidates) == 2
        assert r.total_units == 30
        assert all(c.is_exact_product for c in r.candidates)

    def test_substitute_included_only_when_accepted(self, rice, rice_generic, towels):
        hs = [make_household("h1"), make_household("h2")]
        needs = [
            make_need("n1", "h1", "p_rice_generic", 10, accept_substitutes=True),
            make_need("n2", "h2", "p_rice_generic", 10, accept_substitutes=False),
        ]
        r = self._run(rice, rice_generic, towels, needs, hs)
        assert [c.need.id for c in r.candidates] == ["n1"]
        assert not r.candidates[0].is_exact_product
        assert any(x.reason == "product_incompatible" for x in r.rejections)

    def test_incompatible_product_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1")]
        needs = [make_need("n1", "h1", "p_towels", 10, accept_substitutes=True)]
        r = self._run(rice, rice_generic, towels, needs, hs)
        assert r.candidates == []

    def test_need_required_before_pickup_is_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1")]
        needs = [make_need("n1", "h1", "p_rice", 10, days_out=3)]  # pickup is day 10
        r = self._run(rice, rice_generic, towels, needs, hs)
        assert r.candidates == []
        assert r.rejections[0].reason == "needed_before_pickup"

    def test_need_far_beyond_horizon_is_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1")]
        needs = [make_need("n1", "h1", "p_rice", 10, days_out=200)]
        r = self._run(rice, rice_generic, towels, needs, hs, horizon_days=45)
        assert r.rejections[0].reason == "outside_horizon"

    def test_outside_radius_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1", lat=39.50)]  # ~95 km away
        needs = [make_need("n1", "h1", "p_rice", 10)]
        r = self._run(rice, rice_generic, towels, needs, hs, max_radius_km=8.0)
        assert r.candidates == []
        assert r.rejections[0].reason == "outside_radius"

    def test_inactive_need_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1")]
        needs = [make_need("n1", "h1", "p_rice", 10, active=False)]
        r = self._run(rice, rice_generic, towels, needs, hs)
        assert r.rejections[0].reason == "need_inactive"

    def test_excluded_households_rejected(self, rice, rice_generic, towels):
        hs = [make_household("h1")]
        needs = [make_need("n1", "h1", "p_rice", 10)]
        r = self._run(rice, rice_generic, towels, needs, hs,
                      exclude_household_ids=frozenset({"h1"}))
        assert r.rejections[0].reason == "already_in_pool"

    def test_ordering_is_nearest_first_and_stable(self, rice, rice_generic, towels):
        hs = [
            make_household("far", lat=38.67),
            make_household("near", lat=38.6505),
            make_household("mid", lat=38.66),
        ]
        needs = [make_need(f"n_{h.id}", h.id, "p_rice", 10) for h in hs]
        r = self._run(rice, rice_generic, towels, needs, hs, max_radius_km=8.0)
        assert [c.household.id for c in r.candidates] == ["near", "mid", "far"]
        again = self._run(rice, rice_generic, towels, needs, hs, max_radius_km=8.0)
        assert [c.household.id for c in again.candidates] == [
            c.household.id for c in r.candidates
        ]
