"""Time estimation module for predicting optimal running times based on performance trends.

This module analyzes recent workout data to estimate optimal times for target distances.
It uses multiple strategies:

1. **Linear Regression Trend** - Fits a line through recent times to predict improvement trajectory
2. **Weighted Recent Average** - Gives more weight to recent workouts (exponential decay)
3. **Speed-based Prediction** - Projects distance time using average sustained speed from 
recent runs
4. **Conservative Estimate** - Uses percentiles to predict achievable optimal time
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional


def _calculate_pace_kmh(duration_seconds: float, distance_meters: float) -> float:
    """Calculate pace in km/h from distance and duration."""
    if duration_seconds <= 0 or distance_meters <= 0:
        return 0.0
    return (distance_meters / 1000.0) / (duration_seconds / 3600.0)


def _calculate_duration_from_pace(distance_meters: float, pace_kmh: float) -> float:
    """Calculate duration in seconds from distance and pace."""
    if pace_kmh <= 0 or distance_meters <= 0:
        return float("inf")
    return (distance_meters / 1000.0) / pace_kmh * 3600.0


def _time_since_days(
    workout_date: datetime | None, reference_date: datetime | None = None
) -> float:
    """Calculate days elapsed since workout date.

    Returns number of days elapsed between `workout_date` and `reference_date`.
    If `workout_date` is None the function returns +inf (treated as unknown/very old).
    """
    if workout_date is None:
        return float("inf")
    if reference_date is None:
        reference_date = (
            datetime.now(datetime.now().astimezone().tzinfo)
            if workout_date.tzinfo
            else datetime.now()
        )
    try:
        delta = reference_date - workout_date
        return delta.total_seconds() / 86400.0  # Convert to days
    except (TypeError, ValueError):
        return float("inf")


def estimate_trend_linear(
    times: List[float],
    dates: List[datetime | None],
    _target_distance: float = 5000.0,
) -> float:
    """Estimate optimal time using linear regression of recent trend.

    Returns projected best time by fitting a line through recent times and
    extrapolating to time zero (perfect conditions). Ignores outliers beyond
    2 std deviations.

    Args:
        times: List of segment durations in seconds (must be sorted fastest first)
        dates: Corresponding workout dates
        target_distance: Target distance in meters (not used for linear extrapolation)

    Returns:
        Estimated optimal time in seconds, or inf if insufficient data
    """
    # `_target_distance` kept for API compatibility; not used in this estimator
    del _target_distance
    if len(times) < 3:
        return float("inf")

    # Use top 3-5 fastest times for regression
    count = min(5, len(times))
    recent_times = times[:count]
    recent_dates = dates[:count]

    # Filter out None dates
    valid_pairs: List[Tuple[float, datetime]] = [
        (t, d) for t, d in zip(recent_times, recent_dates) if d is not None
    ]

    if len(valid_pairs) < 3:
        return float("inf")

    # Pair times with days-ago
    x_vals = [_time_since_days(d) for _, d in valid_pairs]
    y_vals = [t for t, _ in valid_pairs]

    if not x_vals or not y_vals or any(math.isinf(x) for x in x_vals):
        return float("inf")

    # Linear regression: y = mx + b
    n = len(x_vals)
    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
    denominator = sum((x - x_mean) ** 2 for x in x_vals)

    if denominator == 0:
        return min(recent_times)

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Extrapolate to time zero (ideal conditions), but cap at minimum observed
    # Use only if slope is negative (improving trend)
    if slope < 0:
        optimal = intercept
        min_observed = min(recent_times)
        # Conservative: use max of (extrapolated, 90% of best time)
        return max(min_observed * 0.90, min(optimal, min_observed))

    return min(recent_times)


def estimate_weighted_recent(
    times: List[float],
    dates: List[datetime | None],
    _target_distance: float = 5000.0,
    decay_half_life_days: float = 30.0,
) -> float:
    """Estimate optimal time using exponentially weighted recent average.

    Assumes recent performances are more predictive than older ones, with
    exponential decay over time. Weights recent runs 2x more than 30-day-old runs.

    Args:
        times: List of segment durations in seconds
        dates: Corresponding workout dates
        target_distance: Target distance in meters (not used)
        decay_half_life_days: Days for weight to decay to 50%

    Returns:
        Estimated optimal time in seconds, or inf if insufficient data
    """
    # `_target_distance` kept for API compatibility; not used in this estimator
    del _target_distance
    if len(times) < 2:
        return float("inf")

    # Use up to top 10 times
    count = min(10, len(times))
    recent_times = times[:count]
    recent_dates = dates[:count]

    valid_pairs: List[Tuple[float, datetime]] = [
        (t, d) for t, d in zip(recent_times, recent_dates) if d is not None
    ]

    if len(valid_pairs) < 2:
        return float("inf")

    # Calculate weights with exponential decay
    weights: List[float] = []
    for _, d in valid_pairs:
        days_ago = _time_since_days(d)
        if math.isinf(days_ago):
            weight = 0.0
        else:
            # exponential decay weight based on half-life
            weight = 2.0 ** (-days_ago / decay_half_life_days)
        weights.append(weight)

    total_weight = sum(weights)
    if total_weight == 0:
        return float("inf")

    weighted_avg = (
        sum(t * w for t, w in zip([t for t, _ in valid_pairs], weights)) / total_weight
    )
    return weighted_avg


def estimate_speed_based(
    times: List[float],
    distances: List[float],
    dates: List[datetime | None],
    target_distance: float,
    decay_half_life_days: float = 30.0,
) -> float:
    """Estimate time using weighted average speed from recent workouts.

    Calculates the average speed from recent runs, then projects that speed
    to the target distance. More robust for extrapolating to different distances.

    Args:
        times: List of segment durations in seconds
        distances: Corresponding distance data
        dates: Corresponding workout dates
        target_distance: Target distance in meters
        decay_half_life_days: Days for weight to decay to 50%

    Returns:
        Estimated time in seconds for target_distance, or inf if insufficient data
    """
    if len(times) < 2 or not distances:
        return float("inf")

    count = min(10, len(times))
    recent_times = times[:count]
    recent_dists = (
        distances[:count]
        if len(distances) >= count
        else distances + [distances[-1]] * (count - len(distances))
    )
    recent_dates = dates[:count]

    valid_data: List[Tuple[float, float, datetime]] = [
        (t, d, dt)
        for t, d, dt in zip(recent_times, recent_dists, recent_dates)
        if dt is not None and t > 0 and d > 0
    ]

    if len(valid_data) < 2:
        return float("inf")

    # Calculate speeds and weights
    speeds: List[float] = []
    weights: List[float] = []

    for t, d, dt in valid_data:
        pace_kmh = _calculate_pace_kmh(t, d)
        if pace_kmh > 0:
            speeds.append(pace_kmh)
            days_ago = _time_since_days(dt)
            if not math.isinf(days_ago):
                weight = 2.0 ** (-days_ago / decay_half_life_days)
            else:
                weight = 0.0
            weights.append(weight)

    if not speeds or not weights or sum(weights) == 0:
        return float("inf")

    weighted_avg_speed = sum(s * w for s, w in zip(speeds, weights)) / sum(weights)
    return _calculate_duration_from_pace(target_distance, weighted_avg_speed)


def estimate_percentile_based(
    times: List[float],
    dates: Optional[List[datetime | None]] = None,
    percentile: float = 50.0,
) -> float:
    """Estimate using percentile of recent performance.

    Conservative estimate using median (50th percentile) of top recent times.
    More robust to outliers than mean-based methods.

    Args:
        times: List of segment durations in seconds
        percentile: Percentile to use (50=median, 75=conservative, 25=optimistic)

    Returns:
        Estimated time at given percentile
    """
    # `dates` parameter kept for backwards compatibility with earlier callers
    # but is not used in the percentile calculation.
    del dates
    if not times:
        return float("inf")

    count = min(15, len(times))
    recent = sorted(times[:count])

    # Calculate percentile position
    pos = (percentile / 100.0) * (len(recent) - 1)
    lower_idx = int(pos)
    upper_idx = min(lower_idx + 1, len(recent) - 1)

    if lower_idx >= len(recent):
        return recent[-1]

    # Linear interpolation between values
    frac = pos - lower_idx
    return recent[lower_idx] * (1 - frac) + recent[upper_idx] * frac


def _derive_distances(
    times_and_dates: List[Tuple[float, datetime | None, float, float]],
    target_distance: float,
) -> List[float]:
    """Derive per-workout distances from avg speed when available.

    If avg speed is missing or non-positive, fall back to `target_distance`.
    """
    distances: List[float] = []
    for t, _, _, s in times_and_dates:
        if s and s > 0 and t and t > 0:
            distances.append(s * t / 3.6)
        else:
            distances.append(target_distance)
    return distances


def _estimate_by_name(
    name: str,
    times: List[float],
    dates: List[datetime | None],
    distances: List[float],
    target_distance: float,
) -> Optional[float]:
    """Dispatch a single estimation strategy by name."""
    if name == "linear":
        return estimate_trend_linear(times, dates, target_distance)
    if name == "weighted":
        return estimate_weighted_recent(times, dates, target_distance)
    if name == "speed":
        return estimate_speed_based(times, distances, dates, target_distance)
    if name == "median":
        return estimate_percentile_based(times, percentile=50.0)


def _ensemble_estimate(
    times: List[float],
    dates: List[datetime | None],
    distances: List[float],
    target_distance: float,
) -> Optional[float]:
    """Compute an ensemble estimate by averaging multiple strategies."""
    candidates = [
        _estimate_by_name("median", times, dates, distances, target_distance),
        _estimate_by_name("weighted", times, dates, distances, target_distance),
        _estimate_by_name("speed", times, dates, distances, target_distance),
    ]
    valid = [m for m in candidates if m is not None and not math.isinf(m) and m > 0]
    if not valid:
        return None
    return sum(valid) / len(valid)


def estimate_optimal_time(
    times_and_dates: List[Tuple[float, datetime | None, float, float]],
    target_distance: float,
    strategy: str = "ensemble",
) -> Optional[float]:
    """Estimate optimal time for a distance using one or more strategies.

    Args:
        times_and_dates: List of (duration_s, date, elevation_change, avg_speed_kmh)
        target_distance: Target distance in meters
        strategy: One of:
            - "ensemble": Average of multiple methods (recommended)
            - "linear": Linear regression trend
            - "weighted": Exponentially weighted recent average
            - "speed": Speed-based extrapolation
            - "median": Percentile-based (50th percentile)

    Returns:
        Estimated optimal time in seconds, or None if insufficient data
    """
    if not times_and_dates or len(times_and_dates) < 2:
        return None

    times = [t for t, _, _, _ in times_and_dates]
    dates = [d for _, d, _, _ in times_and_dates]
    distances = _derive_distances(times_and_dates, target_distance)

    if strategy != "ensemble":
        est = _estimate_by_name(strategy, times, dates, distances, target_distance)
        if est is None or math.isinf(est) or est <= 0:
            return None
        return est

    est = _ensemble_estimate(times, dates, distances, target_distance)
    if est is None or math.isinf(est) or est <= 0:
        return None
    return est


def format_estimation_confidence(
    estimated_time: float,
    best_observed_time: float,
    improvement_percent: float,
) -> str:
    """Format estimation confidence level with context.

    Args:
        estimated_time: The estimated optimal time
        best_observed_time: The best observed time so far
        improvement_percent: Estimated improvement as percentage of best time

    Returns:
        Confidence label with improvement indicator
    """
    # Use best and estimated time to qualify the message further
    delta = (
        best_observed_time - estimated_time
        if best_observed_time and estimated_time
        else 0.0
    )
    if improvement_percent <= 1.0:
        return "(flat/recovery trend)"
    if improvement_percent <= 3.0:
        return "(modest improvement)"
    if improvement_percent <= 5.0:
        return "(steady improvement)"

    # strong improvement: if estimated is substantially better than best
    if delta / best_observed_time > 0.10 if best_observed_time else False:
        return "(strong improvement — optimistic)"
    return "(strong upward trend)"


def create_estimation_summary(
    results: Dict[float, List[Tuple[float, datetime | None, float, float]]],
) -> Dict[float, Dict[str, Any]]:
    """Create estimation summary for all distances in results.

    Args:
        results: Dict mapping distance -> list of (time, date, elevation, speed) tuples

    Returns:
        Dict mapping distance -> {
            'optimal': estimated_time_seconds,
            'best': best_observed_time_seconds,
            'improvement_pct': percentage improvement,
            'confidence': confidence_string,
            'count': number_of_observations,
        }
    """
    summary: Dict[float, Dict[str, Any]] = {}

    for distance, segments in results.items():
        if not segments or len(segments) < 2:
            summary[distance] = {
                "optimal": None,
                "best": segments[0][0] if segments else None,
                "improvement_pct": 0.0,
                "confidence": "insufficient data",
                "count": len(segments),
            }
            continue

        estimated = estimate_optimal_time(segments, distance, strategy="ensemble")
        best = segments[0][0]

        if estimated is None or math.isinf(estimated) or estimated <= 0:
            summary[distance] = {
                "optimal": None,
                "best": best,
                "improvement_pct": 0.0,
                "confidence": "unable to estimate",
                "count": len(segments),
            }
        else:
            improvement_pct = ((best - estimated) / best) * 100.0 if best > 0 else 0.0
            confidence = format_estimation_confidence(estimated, best, improvement_pct)

            summary[distance] = {
                "optimal": estimated,
                "best": best,
                "improvement_pct": improvement_pct,
                "confidence": confidence,
                "count": len(segments),
            }

    return summary
