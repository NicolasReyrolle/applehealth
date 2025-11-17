"""Segment analysis functions for finding fastest running segments."""
from __future__ import annotations

import math
from datetime import datetime
from typing import List, Tuple, Any, Dict


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon points."""
    earth_radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_intervals(
    points: List[Tuple[float, float, datetime]],
    max_speed_kmh: float,
    penalty_seconds: float,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Compute cumulative distances and adjusted time deltas."""
    n = len(points)
    cum = [0.0] * n
    time_deltas = [0.0] * n
    dist_between = [0.0] * n
    adj_time_deltas = [0.0] * n

    for i in range(1, n):
        lat1, lon1, _ = points[i - 1]
        lat2, lon2, _ = points[i]
        d = haversine_meters(lat1, lon1, lat2, lon2)
        cum[i] = cum[i - 1] + d

        t1 = points[i - 1][2]
        t2 = points[i][2]
        dt = max(0.0, (t2 - t1).total_seconds())
        time_deltas[i] = dt
        dist_between[i] = d

        if dt <= 0 and d > 0:
            inst_speed_kmh = float("inf")
        else:
            inst_speed_kmh = (d / dt) * 3.6 if dt > 0 else 0.0

        if math.isinf(inst_speed_kmh):
            adj = dt
        else:
            adj = dt + (penalty_seconds if inst_speed_kmh > max_speed_kmh else 0.0)
        adj_time_deltas[i] = adj

    return cum, time_deltas, dist_between, adj_time_deltas


def _collect_debug_penalties(
    i: int,
    j: int,
    adj_time_deltas: List[float],
    time_deltas: List[float],
    dist_between: List[float],
) -> List[Tuple[int, int, float, float, float]]:
    """Collect penalized intervals for debugging."""
    penalized_in_segment: List[Tuple[int, int, float, float, float]] = []
    for k in range(i + 1, j + 1):
        if adj_time_deltas[k] > time_deltas[k]:
            inst_speed_kmh = (
                (dist_between[k] / time_deltas[k]) * 3.6
                if time_deltas[k] > 0
                else float("inf")
            )
            penalized_in_segment.append(
                (k - 1, k, time_deltas[k], inst_speed_kmh, dist_between[k])
            )
    return penalized_in_segment


def _find_best_segment(
    n: int,
    distances: Dict[str, List[float]],
    target_m: float,
    points: List[Tuple[float, float, datetime]],
    intervals: Dict[str, List[float]],
    debug_info: dict[str, Any] | None,
) -> Tuple[
    Tuple[float, datetime | None, datetime | None],
    int,
    int,
    List[Tuple[int, int, List[Tuple[int, int, float, float, float]]]],
]:
    """Find best segment using sliding window."""
    best = (float("inf"), None, None)
    best_i = best_j = -1
    penalized_intervals: List[
        Tuple[int, int, List[Tuple[int, int, float, float, float]]]
    ] = []

    j = 0
    for i in range(n):
        j = max(j, i + 1)
        while j < n and (distances["cum"][j] - distances["cum"][i]) < target_m:
            j += 1
        if j >= n:
            break

        duration = distances["cum_adj_time"][j] - distances["cum_adj_time"][i]
        if debug_info is not None:
            penalties = _collect_debug_penalties(
                i, j, intervals["adj_time"], intervals["time"], intervals["dist"]
            )
            if penalties:
                penalized_intervals.append((i, j, penalties))

        if duration >= 0 and duration < best[0]:
            best = (duration, points[i][2], points[j][2])
            best_i = i
            best_j = j

    return best, best_i, best_j, penalized_intervals


def _update_debug_info(
    debug_info: dict[str, Any],
    best_i: int,
    best_j: int,
    cum: List[float],
    n: int,
    penalized_intervals: List[Tuple[int, int, List[Tuple[int, int, float, float, float]]]],
) -> None:
    """Update debug info with segment details."""
    if best_i < 0 or best_j < 0:
        return
    debug_info.update(
        {
            "best_i": best_i,
            "best_j": best_j,
            "start_cum_dist": cum[best_i],
            "end_cum_dist": cum[best_j],
            "segment_dist": cum[best_j] - cum[best_i],
            "num_points": n,
            "total_dist": cum[-1] if n > 0 else 0,
            "penalized_intervals": penalized_intervals,
        }
    )


def best_segment_for_dist(
    points: List[Tuple[float, float, datetime]],
    target_m: float,
    max_speed_kmh: float = 35.39,
    penalty_seconds: float = 3.0,
    debug_info: dict[str, Any] | None = None,
) -> Tuple[float, datetime | None, datetime | None]:
    """Return (best_adjusted_duration_seconds, start_time, end_time).

    For the given target distance in meters.
    """
    if not points:
        return (float("inf"), None, None)

    n = len(points)
    cum, time_deltas, dist_between, adj_time_deltas = _compute_intervals(
        points, max_speed_kmh, penalty_seconds
    )

    cum_adj_time = [0.0] * n
    for i in range(1, n):
        cum_adj_time[i] = cum_adj_time[i - 1] + adj_time_deltas[i]

    distances = {"cum": cum, "cum_adj_time": cum_adj_time}
    intervals = {"adj_time": adj_time_deltas, "time": time_deltas, "dist": dist_between}

    best, best_i, best_j, penalized_intervals = _find_best_segment(
        n, distances, target_m, points, intervals, debug_info
    )

    if debug_info is not None:
        _update_debug_info(debug_info, best_i, best_j, cum, n, penalized_intervals)

    return best


def collect_penalty_messages(
    penalized_intervals_data: List[
        Tuple[int, int, List[Tuple[int, int, float, float, float]]]
    ],
    points: List[Tuple[float, float, datetime]],
    penalty_messages: Dict[str, str],
) -> None:
    """Collect penalty messages from penalized intervals data."""
    for _, _, penalized_list in penalized_intervals_data:
        for from_idx, to_idx, interval_dur, inst_speed_kmh, _ in penalized_list:
            ts: datetime | None = None
            try:
                ts = points[from_idx][2]
            except IndexError:
                ts = None
            ts_formatted = (
                ts.strftime("%d/%m/%Y %H:%M:%S") if ts is not None else "unknown"
            )
            key = ts_formatted
            msg = (
                f"{ts_formatted} | interval {from_idx}->{to_idx} | "
                f"{interval_dur:.2f}s | {inst_speed_kmh:.1f} km/h"
            )
            if key not in penalty_messages:
                penalty_messages[key] = msg
