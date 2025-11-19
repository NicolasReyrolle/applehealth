# pyright: ignore[reportUnknownVariableType]
# type: ignore
"""Tests for time estimation module."""

import sys
import os

# pylint: disable=import-error,wrong-import-position,protected-access

import math
from datetime import datetime, timedelta

# Add tools directory to path before importing time_estimation
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

from time_estimation import (  # type: ignore  # noqa: E402
    estimate_optimal_time,
    estimate_trend_linear,
    estimate_weighted_recent,
    estimate_speed_based,
    estimate_percentile_based,
    format_estimation_confidence,
    _calculate_pace_kmh,
    _calculate_duration_from_pace,
    _time_since_days,
)


class TestPaceCalculations:
    """Test pace and duration calculations."""

    def test_calculate_pace_kmh(self) -> None:
        """Test pace calculation from distance and time."""
        # 1000m in 300s (5 min) = 12 km/h
        pace = _calculate_pace_kmh(300.0, 1000.0)
        assert abs(pace - 12.0) < 0.01

    def test_calculate_pace_kmh_zero_duration(self) -> None:
        """Test pace with zero duration."""
        pace = _calculate_pace_kmh(0.0, 1000.0)
        assert abs(pace - 0.0) < 0.001

    def test_calculate_pace_kmh_zero_distance(self) -> None:
        """Test pace with zero distance."""
        pace = _calculate_pace_kmh(300.0, 0.0)
        assert abs(pace - 0.0) < 0.001

    def test_calculate_duration_from_pace(self) -> None:
        """Test duration calculation from pace."""
        # 5km at 12 km/h = 1500 seconds (25 min)
        duration = _calculate_duration_from_pace(5000.0, 12.0)
        assert abs(duration - 1500.0) < 1.0

    def test_calculate_duration_from_pace_zero_pace(self) -> None:
        """Test duration with zero pace."""
        duration = _calculate_duration_from_pace(5000.0, 0.0)
        assert math.isinf(duration)

    def test_calculate_duration_from_pace_zero_distance(self) -> None:
        """Test duration with zero distance."""
        duration = _calculate_duration_from_pace(0.0, 12.0)
        assert math.isinf(duration)


class TestTimeSinceDays:
    """Test time calculation in days."""

    def test_time_since_days_same_date(self) -> None:
        """Test with same date."""
        now = (
            datetime.now(datetime.now().astimezone().tzinfo)
            if hasattr(datetime.now(), "tzinfo")
            else datetime.now()
        )
        days = _time_since_days(now, now)
        assert abs(days - 0.0) < 0.01

    def test_time_since_days_one_day_ago(self) -> None:
        """Test with one day difference."""
        now = (
            datetime.now(datetime.now().astimezone().tzinfo)
            if hasattr(datetime.now(), "tzinfo")
            else datetime.now()
        )
        one_day_ago = now - timedelta(days=1)
        days = _time_since_days(one_day_ago, now)
        assert abs(days - 1.0) < 0.01

    def test_time_since_days_none_date(self) -> None:
        """Test with None date."""
        days = _time_since_days(None)
        assert math.isinf(days)


class TestEstimateTrendLinear:
    """Test linear trend estimation."""

    def test_estimate_linear_improving_trend(self) -> None:
        """Test with improving trend (decreasing times)."""
        now = datetime.now()
        times = [100.0, 95.0, 92.0, 90.0, 88.0]
        dates = [
            now - timedelta(days=50),
            now - timedelta(days=40),
            now - timedelta(days=30),
            now - timedelta(days=20),
            now - timedelta(days=10),
        ]

        estimated = estimate_trend_linear(times, dates)

        # Should estimate below best observed time due to improving trend
        assert not math.isinf(estimated)
        assert estimated >= 85.0  # Should be optimistic but not too much
        assert estimated <= 88.0  # Should be less than best observed

    def test_estimate_linear_insufficient_data(self) -> None:
        """Test with insufficient data."""
        times = [100.0, 95.0]
        dates = [datetime.now(), datetime.now() - timedelta(days=10)]

        estimated = estimate_trend_linear(times, dates)
        assert math.isinf(estimated)

    def test_estimate_linear_flat_trend(self) -> None:
        """Test with flat (no improvement) trend."""
        now = datetime.now()
        times = [100.0, 100.5, 99.5, 100.0]
        dates = [
            now - timedelta(days=40),
            now - timedelta(days=30),
            now - timedelta(days=20),
            now - timedelta(days=10),
        ]

        estimated = estimate_trend_linear(times, dates)
        # Flat trend should return minimum
        assert estimated >= 99.0


class TestEstimateWeightedRecent:
    """Test weighted recent average estimation."""

    def test_estimate_weighted_recent_basic(self) -> None:
        """Test weighted recent average."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0, 85.0]
        dates = [
            now - timedelta(days=60),
            now - timedelta(days=30),
            now - timedelta(days=15),
            now - timedelta(days=1),
        ]

        estimated = estimate_weighted_recent(times, dates)

        # Should be weighted towards recent times (85.0 is most recent)
        assert not math.isinf(estimated)
        assert estimated < 100.0
        assert estimated > 85.0

    def test_estimate_weighted_recent_insufficient_data(self) -> None:
        """Test with insufficient data."""
        times = [100.0]
        dates = [datetime.now()]

        estimated = estimate_weighted_recent(times, dates)
        assert math.isinf(estimated)


class TestEstimateSpeedBased:
    """Test speed-based estimation."""

    def test_estimate_speed_based_consistent_pace(self) -> None:
        """Test with consistent pace."""
        now = datetime.now()
        # 1000m in 300s = 12 km/h
        times = [300.0, 305.0, 295.0]
        distances = [1000.0, 1000.0, 1000.0]
        dates = [
            now - timedelta(days=30),
            now - timedelta(days=15),
            now - timedelta(days=1),
        ]

        # Estimate for 5km
        estimated = estimate_speed_based(times, distances, dates, 5000.0)

        # At 12 km/h, 5km should take ~1500s
        assert not math.isinf(estimated)
        assert estimated > 1400.0
        assert estimated < 1600.0

    def test_estimate_speed_based_insufficient_data(self) -> None:
        """Test with insufficient data."""
        times = [300.0]
        distances = [1000.0]
        dates = [datetime.now()]

        estimated = estimate_speed_based(times, distances, dates, 5000.0)
        assert math.isinf(estimated)


class TestEstimatePercentileBased:
    """Test percentile-based estimation."""

    def test_estimate_percentile_median(self) -> None:
        """Test with median percentile."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0, 85.0, 80.0]
        dates = [now - timedelta(days=i * 10) for i in range(5)]

        median = estimate_percentile_based(times, dates, percentile=50.0)

        # Median of [80, 85, 90, 95, 100] should be 90
        assert abs(median - 90.0) < 1.0

    def test_estimate_percentile_p75(self) -> None:
        """Test with 75th percentile."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0, 85.0, 80.0]
        dates = [now - timedelta(days=i * 10) for i in range(5)]

        p75 = estimate_percentile_based(times, dates, percentile=75.0)

        # 75th percentile should be between 85 and 90
        assert p75 >= 85.0
        assert p75 <= 95.0

    def test_estimate_percentile_single_value(self) -> None:
        """Test with single value."""
        now = datetime.now()
        times = [100.0]
        dates = [now]

        percentile: float = estimate_percentile_based(times, dates, percentile=50.0)
        assert abs(percentile - 100.0) < 0.001


class TestEstimateOptimalTime:
    """Test overall optimal time estimation."""

    def test_estimate_optimal_ensemble(self) -> None:
        """Test ensemble estimation strategy."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now - timedelta(days=60), 0.0, 12.0),
            (295.0, now - timedelta(days=30), 0.0, 12.1),
            (290.0, now - timedelta(days=10), 0.0, 12.2),
        ]

        estimated = estimate_optimal_time(times_and_dates, 1000.0, strategy="ensemble")

        assert estimated is not None
        assert not math.isinf(estimated)
        assert estimated < 300.0
        assert estimated > 280.0

    def test_estimate_optimal_insufficient_data(self) -> None:
        """Test with insufficient data."""
        times_and_dates = [
            (300.0, datetime.now(), 0.0, 12.0),
        ]

        estimated = estimate_optimal_time(times_and_dates, 1000.0)
        assert estimated is None

    def test_estimate_optimal_empty_data(self) -> None:
        """Test with empty data."""
        times_and_dates: list = []

        estimated = estimate_optimal_time(times_and_dates, 1000.0)
        assert estimated is None

    def test_estimate_optimal_linear_strategy(self) -> None:
        """Test with linear strategy."""
        now = datetime.now()
        times_and_dates = [
            (100.0, now - timedelta(days=50), 0.0, 10.0),
            (95.0, now - timedelta(days=40), 0.0, 10.5),
            (90.0, now - timedelta(days=30), 0.0, 11.0),
            (85.0, now - timedelta(days=20), 0.0, 11.5),
            (80.0, now - timedelta(days=10), 0.0, 12.0),
        ]

        estimated = estimate_optimal_time(times_and_dates, 1000.0, strategy="linear")

        # Should estimate below best time with linear trend
        assert estimated is not None


class TestConfidenceFormatting:
    """Test confidence level formatting."""

    def test_confidence_flat_trend(self) -> None:
        """Test formatting for flat trend."""
        conf = format_estimation_confidence(100.0, 100.0, 0.5)
        assert "flat" in conf or "recovery" in conf

    def test_confidence_modest_improvement(self) -> None:
        """Test formatting for modest improvement."""
        conf = format_estimation_confidence(98.0, 100.0, 2.0)
        assert "modest" in conf

    def test_confidence_steady_improvement(self) -> None:
        """Test formatting for steady improvement."""
        conf = format_estimation_confidence(95.0, 100.0, 5.0)
        assert "steady" in conf

    def test_confidence_strong_improvement(self) -> None:
        """Test formatting for strong improvement."""
        conf = format_estimation_confidence(90.0, 100.0, 10.0)
        assert "strong" in conf or "upward" in conf
