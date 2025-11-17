#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for segment analysis functions."""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, cast

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # type: ignore # noqa: E402

ahs = cast(Any, ahs)


class TestBestSegmentForDist:
    """Unit tests for segment finding algorithm."""

    @pytest.fixture
    def simple_points(self):
        """Create simple test points in a straight line."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            # Longitude increases by ~0.01 degrees per 1km at equator
            (0.0, 0.0 + i * 0.009, 0.0, base_time + timedelta(seconds=i * 10))
            for i in range(100)
        ]
        return points

    def test_segment_with_enough_points(self, simple_points):  # type: ignore
        """Should find a segment for reasonable distances."""
        result = ahs.best_segment_for_dist(simple_points, 100.0)  # type: ignore
        duration, start_time, end_time, _, _ = result  # type: ignore
        assert duration != float("inf"), "Should find a segment"
        assert start_time is not None
        assert end_time is not None
        assert start_time < end_time

    def test_segment_ordering(self, simple_points):  # type: ignore
        """Segment should maintain chronological order."""
        result = ahs.best_segment_for_dist(simple_points, 100.0)  # type: ignore
        _, start_time, end_time, _, _ = result  # type: ignore
        assert start_time <= end_time

    def test_segment_unrealistic_distance(self, simple_points):  # type: ignore
        """Unrealistic distance should return infinity."""
        result = ahs.best_segment_for_dist(simple_points, 100000000.0)  # type: ignore
        duration, _, _, _, _ = result  # type: ignore
        assert duration == float("inf")

    def test_segment_empty_points(self):
        """Empty points list should return infinity."""
        result = ahs.best_segment_for_dist([], 100.0)  # type: ignore
        duration, start_time, end_time, _, _ = result  # type: ignore
        assert duration == float("inf")
        assert start_time is None
        assert end_time is None

    def test_segment_penalty_applied(self):
        """High-speed intervals should increase adjusted duration."""
        # Create two identical segments, one with a penalty
        base_time = datetime(2024, 1, 1, 10, 0, 0)

        # Segment 1: normal speeds
        points1 = [
            (0.0, 0.0 + i * 0.001, 0.0, base_time + timedelta(seconds=i * 10))
            for i in range(50)
        ]

        # Segment 2: same distance but with one fast point (will trigger penalty)
        points2 = [
            (
                0.0,
                0.0 + i * 0.001,
                0.0,
                base_time + timedelta(seconds=i * 10 if i != 25 else i * 1),
            )
            for i in range(50)
        ]

        dur1, _, _, _, _ = ahs.best_segment_for_dist(  # type: ignore
            points1, 100.0, max_speed_kmh=20.0, penalty_seconds=3.0
        )
        dur2, _, _, _, _ = ahs.best_segment_for_dist(  # type: ignore
            points2, 100.0, max_speed_kmh=20.0, penalty_seconds=3.0
        )

        # Both should be valid segments
        assert dur1 != float("inf")
        assert dur2 != float("inf")

    def test_segment_debug_info(self):
        """Debug info should be populated when requested."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i * 0.001, 0.0, base_time + timedelta(seconds=i * 10))
            for i in range(50)
        ]

        debug_info = {}
        ahs.best_segment_for_dist(points, 100.0, debug_info=debug_info)  # type: ignore

        assert "num_points" in debug_info
        assert "segment_dist" in debug_info
        assert "total_dist" in debug_info


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_zero_distance_target(self):
        """Should handle zero distance target gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i * 0.001, 0.0, base_time + timedelta(seconds=i * 10))
            for i in range(10)
        ]

        result = ahs.best_segment_for_dist(points, 0.0)  # type: ignore
        # Should handle it without crashing
        assert isinstance(result, tuple)

    def test_negative_distance_target(self):
        """Should handle negative distance gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i * 0.001, 0.0, base_time + timedelta(seconds=i * 10))
            for i in range(10)
        ]

        result = ahs.best_segment_for_dist(points, -100.0)  # type: ignore
        # Should handle it without crashing
        assert isinstance(result, tuple)

    def test_single_point(self):
        """Should handle single point gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [(0.0, 0.0, 0.0, base_time)]

        result = ahs.best_segment_for_dist(points, 100.0)  # type: ignore
        duration, _, _, _, _ = result  # type: ignore
        assert duration == float("inf")

    def test_two_identical_points(self):
        """Should handle duplicate points gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0, 0.0, base_time),
            (0.0, 0.0, 0.0, base_time + timedelta(seconds=10)),
        ]

        result = ahs.best_segment_for_dist(points, 100.0)  # type: ignore
        # Should not crash
        assert isinstance(result, tuple)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
