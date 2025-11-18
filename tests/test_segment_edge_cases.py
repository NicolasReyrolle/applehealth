#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Test edge cases in segment analysis."""

import os
import sys
from datetime import datetime
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import segment_analysis as sa  # noqa: E402 # type: ignore

sa = cast(Any, sa)


class TestSegmentAnalysisEdgeCases:
    """Test edge cases in segment analysis."""

    def test_distance_3d_meters_zero_elevation_change(self):
        """Should calculate distance with zero elevation change."""
        result = sa.distance_3d_meters(0.0, 0.0, 10.0, 0.001, 0.0, 10.0)  # type: ignore
        # Should be approximately equal to haversine distance
        haversine_result = sa.haversine_meters(0.0, 0.0, 0.001, 0.0)  # type: ignore
        assert abs(result - haversine_result) < 1e-6  # type: ignore

    def test_distance_3d_meters_with_elevation(self):
        """Should calculate 3D distance with elevation change."""
        # Same horizontal position, different elevation
        result = sa.distance_3d_meters(0.0, 0.0, 0.0, 0.0, 0.0, 100.0)  # type: ignore
        assert (
            abs(result - 100.0) < 1e-6  # type: ignore
        )  # Should be exactly the elevation difference

    def test_collect_penalty_messages_empty_data(self):
        """Should handle empty penalty data."""
        points = [(0.0, 0.0, 0.0, datetime(2024, 1, 1, 10, 0, 0))]
        penalty_messages = {}

        sa.collect_penalty_messages([], points, penalty_messages)  # type: ignore

        assert len(penalty_messages) == 0  # type: ignore

    def test_collect_penalty_messages_with_data(self):
        """Should collect penalty messages from data."""
        points = [
            (0.0, 0.0, 0.0, datetime(2024, 1, 1, 10, 0, 0)),
            (0.001, 0.0, 0.0, datetime(2024, 1, 1, 10, 0, 10)),
        ]
        penalty_messages = {}

        # Mock penalty data: (segment_start, segment_end, [(from_idx, to_idx,
        # duration, speed, distance)])
        penalty_data = [(0, 1, [(0, 1, 5.0, 25.0, 100.0)])]

        sa.collect_penalty_messages(penalty_data, points, penalty_messages)  # type: ignore

        assert len(penalty_messages) > 0  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
