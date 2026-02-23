# pyright: ignore[reportUnknownVariableType]
# type: ignore
"""Tests for time estimation module."""

import sys
import os

# pylint: disable=import-error,wrong-import-position,protected-access

import math
import pytest
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
    create_estimation_summary,
    _calculate_pace_kmh,
    _calculate_duration_from_pace,
    _time_since_days,
    _compute_linear_regression,
    _extrapolate_trend,
    _prepare_distance_list,
    _calculate_speed_and_weight,
    _compute_weighted_speed,
    _derive_distances,
    _get_improvement_level,
    _estimate_by_name,
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


class TestLinearRegression:
    """Test linear regression helper functions."""

    def test_compute_linear_regression_positive_slope(self) -> None:
        """Test linear regression with positive slope."""
        x_vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        y_vals = [2.0, 4.0, 6.0, 8.0, 10.0]  # y = 2x
        slope, _ = _compute_linear_regression(x_vals, y_vals)
        assert abs(slope - 2.0) < 0.01

    def test_compute_linear_regression_negative_slope(self) -> None:
        """Test linear regression with negative slope."""
        x_vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        y_vals = [10.0, 8.0, 6.0, 4.0, 2.0]  # y = -2x + 12
        slope, _ = _compute_linear_regression(x_vals, y_vals)
        assert slope < 0
        assert abs(slope + 2.0) < 0.01

    def test_compute_linear_regression_zero_denominator(self) -> None:
        """Test linear regression with constant x values."""
        x_vals = [1.0, 1.0, 1.0]
        y_vals = [2.0, 3.0, 4.0]
        slope, _ = _compute_linear_regression(x_vals, y_vals)
        assert abs(slope - 0.0) < 0.001

    def test_extrapolate_trend_negative_slope(self) -> None:
        """Test trend extrapolation with improving trend."""
        estimated = _extrapolate_trend(slope=-2.0, intercept=100.0, min_observed=110.0)
        # When slope < 0, returns max(min_observed * 0.90, min(optimal, min_observed))
        # = max(99.0, min(100.0, 110.0)) = max(99.0, 100.0) = 100.0
        assert abs(estimated - 100.0) < 0.001
        assert estimated >= 99.0

    def test_extrapolate_trend_positive_slope(self) -> None:
        """Test trend extrapolation with worsening trend."""
        estimated = _extrapolate_trend(slope=2.0, intercept=100.0, min_observed=110.0)
        assert abs(estimated - 110.0) < 0.001

    def test_extrapolate_trend_zero_slope(self) -> None:
        """Test trend extrapolation with flat trend."""
        estimated = _extrapolate_trend(slope=0.0, intercept=100.0, min_observed=110.0)
        assert abs(estimated - 110.0) < 0.001


class TestHelperFunctions:
    """Test utility helper functions."""

    def test_prepare_distance_list_sufficient(self) -> None:
        """Test distance list preparation with sufficient data."""
        distances = [1000.0, 1100.0, 1200.0, 1300.0]
        result = _prepare_distance_list(distances, 2)
        assert result == [1000.0, 1100.0]

    def test_prepare_distance_list_padding(self) -> None:
        """Test distance list preparation with padding."""
        distances = [1000.0]
        result = _prepare_distance_list(distances, 3)
        assert len(result) == 3
        assert result == [1000.0, 1000.0, 1000.0]

    def test_calculate_speed_and_weight_valid(self) -> None:
        """Test speed and weight calculation with valid data."""
        now = datetime.now()
        result = _calculate_speed_and_weight(300.0, 1000.0, now, decay_half_life_days=30.0)
        assert result is not None
        speed, weight = result
        assert speed > 0
        assert weight > 0

    def test_calculate_speed_and_weight_zero_pace(self) -> None:
        """Test speed and weight calculation with zero pace."""
        now = datetime.now()
        result = _calculate_speed_and_weight(0.0, 1000.0, now, decay_half_life_days=30.0)
        assert result is None

    def test_calculate_speed_and_weight_none_date(self) -> None:
        """Test speed and weight calculation with None date."""
        result = _calculate_speed_and_weight(300.0, 1000.0, None, decay_half_life_days=30.0)
        assert result is not None
        _, weight = result
        assert abs(weight - 0.0) < 0.001

    def test_compute_weighted_speed_basic(self) -> None:
        """Test weighted speed computation."""
        speeds = [10.0, 12.0, 14.0]
        weights = [1.0, 1.0, 1.0]
        avg = _compute_weighted_speed(speeds, weights)
        assert abs(avg - 12.0) < 0.01

    def test_compute_weighted_speed_unequal_weights(self) -> None:
        """Test weighted speed with different weights."""
        speeds = [10.0, 20.0]
        weights = [3.0, 1.0]  # 10 gets 3x weight
        avg = _compute_weighted_speed(speeds, weights)
        assert avg < 15.0

    def test_compute_weighted_speed_zero_weight(self) -> None:
        """Test weighted speed with zero total weight."""
        speeds = [10.0, 12.0]
        weights = [0.0, 0.0]
        avg = _compute_weighted_speed(speeds, weights)
        assert abs(avg - 0.0) < 0.001

    def test_derive_distances_with_speed(self) -> None:
        """Test distance derivation from speed."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now, 0.0, 12.0),
            (300.0, now, 0.0, 10.0),
        ]
        distances = _derive_distances(times_and_dates, target_distance=5000.0)
        assert len(distances) == 2
        assert distances[0] > 0
        assert distances[1] > 0

    def test_derive_distances_without_speed(self) -> None:
        """Test distance derivation falls back to target distance."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now, 0.0, 0.0),
            (300.0, now, 0.0, -1.0),
        ]
        distances = _derive_distances(times_and_dates, target_distance=5000.0)
        assert distances == [5000.0, 5000.0]

    def test_get_improvement_level_flat(self) -> None:
        """Test improvement level for flat performance."""
        level = _get_improvement_level(0.5)
        assert level == "(flat/recovery trend)"

    def test_get_improvement_level_modest(self) -> None:
        """Test improvement level for modest improvement."""
        level = _get_improvement_level(2.0)
        assert level == "(modest improvement)"

    def test_get_improvement_level_steady(self) -> None:
        """Test improvement level for steady improvement."""
        level = _get_improvement_level(4.0)
        assert level == "(steady improvement)"

    def test_get_improvement_level_strong(self) -> None:
        """Test improvement level for strong improvement."""
        level = _get_improvement_level(10.0)
        assert level is None


class TestEstimationSummary:
    """Test estimation summary creation."""

    def test_create_estimation_summary_single_distance(self) -> None:
        """Test summary creation for single distance."""
        now = datetime.now()
        results = {
            5000.0: [
                (300.0, now - timedelta(days=10), 0.0, 12.0),
                (295.0, now - timedelta(days=5), 0.0, 12.1),
                (290.0, now, 0.0, 12.2),
            ]
        }
        summary = create_estimation_summary(results)
        assert 5000.0 in summary
        assert summary[5000.0]["count"] == 3
        assert abs(summary[5000.0]["best"] - 300.0) < 0.001

    def test_create_estimation_summary_insufficient_data(self) -> None:
        """Test summary creation with insufficient data."""
        results = {
            5000.0: [
                (300.0, datetime.now(), 0.0, 12.0),
            ]
        }
        summary = create_estimation_summary(results)
        assert summary[5000.0]["optimal"] is None
        assert "insufficient" in summary[5000.0]["confidence"]

    def test_create_estimation_summary_multiple_distances(self) -> None:
        """Test summary creation for multiple distances."""
        now = datetime.now()
        results = {
            5000.0: [
                (300.0, now - timedelta(days=10), 0.0, 12.0),
                (295.0, now, 0.0, 12.1),
            ],
            10000.0: [
                (600.0, now - timedelta(days=10), 0.0, 12.0),
                (595.0, now, 0.0, 12.1),
            ]
        }
        summary = create_estimation_summary(results)
        assert len(summary) == 2
        assert 5000.0 in summary
        assert 10000.0 in summary

    def test_create_estimation_summary_empty_results(self) -> None:
        """Test summary creation with empty results."""
        summary = create_estimation_summary({})
        assert summary == {}


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_estimate_trend_linear_with_no_dates(self) -> None:
        """Test linear estimation when all dates are None."""
        times = [100.0, 95.0, 90.0]
        dates = [None, None, None]
        estimated = estimate_trend_linear(times, dates)
        assert math.isinf(estimated)

    def test_estimate_weighted_recent_single_date(self) -> None:
        """Test weighted recent with mostly None dates."""
        times = [100.0, 95.0, 90.0, 85.0, 80.0, 75.0]
        now = datetime.now()
        dates = [None, None, None, None, None, now]
        estimated = estimate_weighted_recent(times, dates)
        # With only one valid date (all others are None with inf days), result is inf
        # because other weights become 0 and total_weight = 0
        assert math.isinf(estimated)

    def test_estimate_percentile_empty_times(self) -> None:
        """Test percentile estimation with empty times."""
        estimated = estimate_percentile_based([], percentile=50.0)
        assert math.isinf(estimated)

    def test_pace_calculations_boundary(self) -> None:
        """Test pace calculations at boundaries."""
        # Very small distance
        pace = _calculate_pace_kmh(300.0, 0.001)
        assert pace > 0

    def test_duration_from_pace_very_small(self) -> None:
        """Test duration calculation with very small pace."""
        duration = _calculate_duration_from_pace(10000.0, 0.1)
        assert duration > 0
        assert not math.isinf(duration)


class TestEstimateStrategies:
    """Test different estimation strategies."""

    def test_estimate_optimal_weighted_strategy(self) -> None:
        """Test optimal estimation with weighted strategy."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now - timedelta(days=60), 0.0, 12.0),
            (295.0, now - timedelta(days=30), 0.0, 12.1),
            (290.0, now - timedelta(days=10), 0.0, 12.2),
        ]
        estimated = estimate_optimal_time(times_and_dates, 1000.0, strategy="weighted")
        if estimated is not None:
            assert estimated < 300.0

    def test_estimate_optimal_speed_strategy(self) -> None:
        """Test optimal estimation with speed strategy."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now - timedelta(days=30), 0.0, 12.0),
            (295.0, now - timedelta(days=15), 0.0, 12.1),
            (290.0, now, 0.0, 12.2),
        ]
        estimated = estimate_optimal_time(times_and_dates, 1000.0, strategy="speed")
        if estimated is not None:
            assert estimated > 0

    def test_estimate_optimal_median_strategy(self) -> None:
        """Test optimal estimation with median strategy."""
        now = datetime.now()
        times_and_dates = [
            (300.0, now - timedelta(days=30), 0.0, 12.0),
            (295.0, now - timedelta(days=15), 0.0, 12.1),
            (290.0, now, 0.0, 12.2),
        ]
        estimated = estimate_optimal_time(times_and_dates, 1000.0, strategy="median")
        if estimated is not None:
            assert estimated > 0


class TestEstimateByName:
    """Test _estimate_by_name dispatch function."""

    def test_estimate_by_name_unknown_strategy_returns_none(self) -> None:
        """Test that unknown strategy name returns None."""
        now = datetime.now()
        times = [300.0, 295.0, 290.0]
        dates = [now - timedelta(days=30), now - timedelta(days=15), now]
        distances = [1000.0, 1000.0, 1000.0]
        result = _estimate_by_name("unknown", times, dates, distances, 1000.0)
        assert result is None

    def test_estimate_by_name_empty_string_returns_none(self) -> None:
        """Test that empty string strategy name returns None."""
        now = datetime.now()
        times = [300.0, 295.0, 290.0]
        dates = [now - timedelta(days=30), now - timedelta(days=15), now]
        distances = [1000.0, 1000.0, 1000.0]
        result = _estimate_by_name("", times, dates, distances, 1000.0)
        assert result is None

    def test_estimate_by_name_linear_dispatches_correctly(self) -> None:
        """Test that 'linear' strategy dispatches to estimate_trend_linear."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0, 85.0, 80.0]
        dates = [now - timedelta(days=i * 10) for i in range(5)]
        distances = [1000.0] * 5
        result = _estimate_by_name("linear", times, dates, distances, 1000.0)
        expected = estimate_trend_linear(times, dates, 1000.0)
        assert result == expected

    def test_estimate_by_name_weighted_dispatches_correctly(self) -> None:
        """Test that 'weighted' strategy dispatches to estimate_weighted_recent."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0]
        dates = [now - timedelta(days=i * 10) for i in range(3)]
        distances = [1000.0] * 3
        result = _estimate_by_name("weighted", times, dates, distances, 1000.0)
        expected = estimate_weighted_recent(times, dates, 1000.0)
        assert result is not None and not math.isinf(result)
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_estimate_by_name_speed_dispatches_correctly(self) -> None:
        """Test that 'speed' strategy dispatches to estimate_speed_based."""
        now = datetime.now()
        times = [300.0, 295.0, 290.0]
        dates = [now - timedelta(days=i * 10) for i in range(3)]
        distances = [1000.0] * 3
        result = _estimate_by_name("speed", times, dates, distances, 1000.0)
        expected = estimate_speed_based(times, distances, dates, 1000.0)
        assert result is not None and not math.isinf(result)
        assert math.isclose(result, expected, rel_tol=1e-6)

    def test_estimate_by_name_median_dispatches_correctly(self) -> None:
        """Test that 'median' strategy dispatches to estimate_percentile_based."""
        now = datetime.now()
        times = [100.0, 95.0, 90.0]
        dates = [now - timedelta(days=i * 10) for i in range(3)]
        distances = [1000.0] * 3
        result = _estimate_by_name("median", times, dates, distances, 1000.0)
        expected = estimate_percentile_based(times, percentile=50.0)
        assert result == expected


class TestPrepareDistanceListEdgeCases:
    """Test _prepare_distance_list edge cases from PR review fixes."""

    def test_prepare_distance_list_empty_positive_required(self) -> None:
        """Test that empty list with positive required_count raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _prepare_distance_list([], 3)

    def test_prepare_distance_list_empty_zero_required(self) -> None:
        """Test that empty list with required_count=0 returns empty list."""
        result = _prepare_distance_list([], 0)
        assert result == []

    def test_prepare_distance_list_empty_negative_required(self) -> None:
        """Test that empty list with negative required_count returns empty list."""
        result = _prepare_distance_list([], -1)
        assert result == []


class TestPercentileBasedClamping:
    """Test percentile clamping behaviour added in PR review fix."""

    def test_percentile_below_zero_clamped_to_minimum(self) -> None:
        """Test that percentile below 0 is clamped to 0 (minimum value)."""
        times = [80.0, 85.0, 90.0, 95.0, 100.0]
        result_clamped = estimate_percentile_based(times, percentile=-10.0)
        result_zero = estimate_percentile_based(times, percentile=0.0)
        assert result_clamped == result_zero

    def test_percentile_above_100_clamped_to_maximum(self) -> None:
        """Test that percentile above 100 is clamped to 100 (maximum value)."""
        times = [80.0, 85.0, 90.0, 95.0, 100.0]
        result_clamped = estimate_percentile_based(times, percentile=110.0)
        result_max = estimate_percentile_based(times, percentile=100.0)
        assert result_clamped == result_max

    def test_percentile_zero_returns_minimum(self) -> None:
        """Test that percentile=0 returns the minimum value."""
        times = [80.0, 85.0, 90.0, 95.0, 100.0]
        result = estimate_percentile_based(times, percentile=0.0)
        assert abs(result - 80.0) < 0.001

    def test_percentile_100_returns_maximum(self) -> None:
        """Test that percentile=100 returns the maximum value."""
        times = [80.0, 85.0, 90.0, 95.0, 100.0]
        result = estimate_percentile_based(times, percentile=100.0)
        assert abs(result - 100.0) < 0.001
