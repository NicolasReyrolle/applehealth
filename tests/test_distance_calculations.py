#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for distance calculation functions."""

import os
import sys
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools'))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import segment_analysis as sa  # noqa: E402 # type: ignore

sa = cast(Any, sa)


class TestHaversineMeters:
    """Unit tests for haversine distance calculation."""

    def test_haversine_zero_distance(self):
        """Same coordinates should return ~0 meters."""
        result = sa.haversine_meters(0.0, 0.0, 0.0, 0.0)  # type: ignore
        assert abs(result) < 1e-6, "Same coordinates should be ~0 meters apart"  # type: ignore

    def test_haversine_one_degree_latitude(self):
        """One degree latitude is approximately 111 km."""
        result = sa.haversine_meters(0.0, 0.0, 1.0, 0.0)  # type: ignore
        assert 110000 < result < 112000, "One degree latitude should be ~111 km"

    def test_haversine_one_degree_longitude_at_equator(self):
        """One degree longitude at equator is approximately 111 km."""
        result = sa.haversine_meters(0.0, 0.0, 0.0, 1.0)  # type: ignore
        assert 110000 < result < 112000, "One degree longitude at equator should be ~111 km"

    def test_haversine_known_distance(self):
        """Test with known real-world coordinates (Luxembourg)."""
        # Gare Centrale Luxembourg to City Center (~2.5 km)
        lat1, lon1 = 49.6116, 6.1319
        lat2, lon2 = 49.6163, 6.1408
        result = sa.haversine_meters(lat1, lon1, lat2, lon2)  # type: ignore
        # Should be roughly 1 km (rough estimate)
        assert 500 < result < 2000, f"Distance should be ~1km, got {result}m"

    def test_haversine_symmetry(self):
        """Distance from A to B should equal distance from B to A."""
        lat1, lon1, lat2, lon2 = 40.7128, -74.0060, 34.0522, -118.2437
        d1 = sa.haversine_meters(lat1, lon1, lat2, lon2)  # type: ignore
        d2 = sa.haversine_meters(lat2, lon2, lat1, lon1)  # type: ignore
        assert abs(d1 - d2) < 1e-6, "Haversine distance should be symmetric"  # type: ignore


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
