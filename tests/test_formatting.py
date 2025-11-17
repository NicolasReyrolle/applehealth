#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for formatting functions."""

import os
import sys
from datetime import datetime
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestFormatDuration:
    """Unit tests for duration formatting."""

    def test_format_duration_zero(self):
        """Zero seconds should format as 00:00:00."""
        assert ahs.format_duration(0.0) == "00:00:00"  # type: ignore

    def test_format_duration_seconds_only(self):
        """45 seconds should format as 00:00:45."""
        assert ahs.format_duration(45.0) == "00:00:45"  # type: ignore

    def test_format_duration_minutes(self):
        """125 seconds (2:05) should format as 00:02:05."""
        assert ahs.format_duration(125.0) == "00:02:05"  # type: ignore

    def test_format_duration_hours(self):
        """3665 seconds (1:01:05) should format as 01:01:05."""
        assert ahs.format_duration(3665.0) == "01:01:05"  # type: ignore

    def test_format_duration_rounding(self):
        """45.6 seconds should round to 46."""
        result = ahs.format_duration(45.6)  # type: ignore
        assert result == "00:00:46"

    def test_format_duration_infinity(self):
        """Infinity should return '-'."""
        assert ahs.format_duration(float("inf")) == "-"  # type: ignore

    def test_format_duration_none(self):
        """None should return '-'."""
        assert ahs.format_duration(None) == "-"  # type: ignore


class TestFormatDistance:
    """Unit tests for distance formatting."""

    def test_format_distance_meters(self):
        """Distances < 1000m should format in meters."""
        assert ahs.format_distance(400.0) == "400 m"  # type: ignore
        assert ahs.format_distance(800.0) == "800 m"  # type: ignore

    def test_format_distance_kilometers(self):
        """Round kilometers should format without decimals."""
        assert ahs.format_distance(1000.0) == "1 km"  # type: ignore
        assert ahs.format_distance(5000.0) == "5 km"  # type: ignore
        assert ahs.format_distance(10000.0) == "10 km"  # type: ignore

    def test_format_distance_decimal_kilometers(self):
        """Non-round kilometers should show minimal decimals."""
        result = ahs.format_distance(1500.0)  # type: ignore
        assert "1.5" in result or "1.50" in result
        assert "km" in result

    def test_format_distance_half_marathon(self):
        """21097.5 meters should format as 'Half Marathon'."""
        assert ahs.format_distance(21097.5) == "Half Marathon"  # type: ignore

    def test_format_distance_marathon(self):
        """42195 meters should format as 'Marathon'."""
        assert ahs.format_distance(42195.0) == "Marathon"  # type: ignore

    def test_format_distance_none(self):
        """None should return empty string."""
        assert ahs.format_distance(None) == ""  # type: ignore


class TestFormatPenaltyLines:
    """Test penalty message formatting."""

    def test_format_empty_penalties(self):
        """Empty penalties should return empty list."""
        result = ahs._format_penalty_lines({})  # type: ignore
        assert result == []

    def test_format_single_penalty(self):
        """Single penalty should be formatted correctly."""
        penalties = {"key1": "Warning: Speed exceeded"}
        result = ahs._format_penalty_lines(penalties)  # type: ignore
        assert len(result) == 4  # type: ignore
        assert result[0] == ""
        assert result[1] == "=== PENALTY WARNINGS ==="
        assert result[2] == "Warning: Speed exceeded"
        assert result[3] == ""

    def test_format_multiple_penalties_sorted(self):
        """Multiple penalties should be sorted by key."""
        penalties = {"z_key": "Warning Z", "a_key": "Warning A"}
        result = ahs._format_penalty_lines(penalties)  # type: ignore
        assert "Warning A" in result[2]
        assert "Warning Z" in result[3]


class TestFormatResultsLines:
    """Test results formatting."""

    def test_format_empty_results(self):
        """Empty results should return empty list."""
        result = ahs._format_results_lines({})  # type: ignore
        assert result == []

    def test_format_results_no_segments(self):
        """Distance with no segments should show message."""
        results = {1000.0: []}  # type: ignore
        result = ahs._format_results_lines(results)  # type: ignore
        assert any("1 km" in line for line in result)  # type: ignore
        assert any("No segments found" in line for line in result)  # type: ignore

    def test_format_results_with_segments(self):
        """Results with segments should format correctly."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        results = {400.0: [(100.5, dt), (105.2, dt)]}
        result = ahs._format_results_lines(results)  # type: ignore
        assert any("400 m" in line for line in result)  # type: ignore
        assert any("15/01/2024" in line for line in result)  # type: ignore
        assert any("00:01:40" in line or "00:01:41" in line for line in result)  # type: ignore

    def test_format_results_with_none_date(self):
        """Results with None date should show 'unknown'."""
        results = {1000.0: [(120.0, None)]}
        result = ahs._format_results_lines(results)  # type: ignore
        assert any("unknown" in line for line in result)  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
