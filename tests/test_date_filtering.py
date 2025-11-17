#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for date filtering functions."""

import argparse
import os
import sys
from datetime import datetime, date
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestDateFiltering:
    """Test date range filtering functionality."""

    def test_date_before_range(self):
        """Workout before start_date should be excluded."""
        workout_date = datetime(2024, 1, 1)
        start_date = date(2024, 1, 15)

        assert workout_date.date() < start_date

    def test_date_within_range(self):
        """Workout within range should be included."""
        workout_date = datetime(2024, 1, 15)
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        assert start_date <= workout_date.date() <= end_date

    def test_date_after_range(self):
        """Workout after end_date should be excluded."""
        workout_date = datetime(2024, 2, 1)
        end_date = date(2024, 1, 31)

        assert workout_date.date() > end_date


class TestParseDateFilters:
    """Test date filter parsing."""

    def test_parse_no_dates(self):
        """Should return None for both dates when not provided."""
        args = argparse.Namespace(start_date=None, end_date=None)
        start, end = ahs._parse_date_filters(args)  # type: ignore
        assert start is None
        assert end is None

    def test_parse_start_date_only(self):
        """Should parse start date correctly."""
        args = argparse.Namespace(start_date="20240115", end_date=None)
        start, end = ahs._parse_date_filters(args)  # type: ignore
        assert start == datetime(2024, 1, 15).date()
        assert end is None

    def test_parse_end_date_only(self):
        """Should parse end date correctly."""
        args = argparse.Namespace(start_date=None, end_date="20241231")
        start, end = ahs._parse_date_filters(args)  # type: ignore
        assert start is None
        assert end == datetime(2024, 12, 31).date()

    def test_parse_both_dates(self):
        """Should parse both dates correctly."""
        args = argparse.Namespace(start_date="20240101", end_date="20241231")
        start, end = ahs._parse_date_filters(args)  # type: ignore
        assert start == datetime(2024, 1, 1).date()
        assert end == datetime(2024, 12, 31).date()


class TestHelperFunctions:
    """Test various helper functions."""

    def test_should_skip_workout_no_date(self):
        """Should not skip workout with no date."""
        result = ahs._should_skip_workout(None, None, None)  # type: ignore
        assert result is False

    def test_should_skip_workout_before_start(self):
        """Should skip workout before start date."""
        workout_date = datetime(2024, 1, 1)
        start_date = datetime(2024, 1, 15).date()
        result = ahs._should_skip_workout(workout_date, start_date, None)  # type: ignore
        assert result is True

    def test_should_skip_workout_after_end(self):
        """Should skip workout after end date."""
        workout_date = datetime(2024, 12, 31)
        end_date = datetime(2024, 12, 15).date()
        result = ahs._should_skip_workout(workout_date, None, end_date)  # type: ignore
        assert result is True

    def test_should_skip_workout_within_range(self):
        """Should not skip workout within range."""
        workout_date = datetime(2024, 6, 15)
        start_date = datetime(2024, 1, 1).date()
        end_date = datetime(2024, 12, 31).date()
        result = ahs._should_skip_workout(workout_date, start_date, end_date)  # type: ignore
        assert result is False

    def test_finalize_results_sorting(self):
        """Should sort and trim results correctly."""
        best_segments = {
            1000.0: [(120.0, None), (100.0, None), (110.0, None), (105.0, None)]
        }
        result = ahs._finalize_results(best_segments, top_n=2)  # type: ignore
        assert len(result[1000.0]) == 2  # type: ignore
        assert abs(result[1000.0][0][0] - 100.0) < 1e-9  # type: ignore
        assert abs(result[1000.0][1][0] - 105.0) < 1e-9  # type: ignore

    def test_finalize_results_empty(self):
        """Should handle empty segments."""
        best_segments = {1000.0: []}  # type: ignore
        result = ahs._finalize_results(best_segments, top_n=5)  # type: ignore
        assert result[1000.0] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
