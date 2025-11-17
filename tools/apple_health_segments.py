#!/usr/bin/env python3
"""
CLI to find top fastest segments for running workouts inside an Apple Health export.zip.

Usage examples (PowerShell):
  pwsh> python .\tools\apple_health_segments.py \
      --zip "export.zip" \
      --top 5

Notes:
- The script streams the `export.xml` file from the zip and processes each referenced
  route file one at a time to avoid loading the entire archive into memory.
- Supported route file formats: Apple Health `Route` XML with `Location` tags, and GPX.
"""

from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Iterable, List, Tuple, BinaryIO, Any, Dict
from dateutil import parser as dateutil_parser

from export_processor import ExportReader, match_routes_to_workouts

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

DATE_FMT = "%d/%m/%Y"


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


def parse_timestamp(s: str) -> datetime:
    """Parse timestamp string using dateutil for robust format handling."""
    if not s:
        raise ValueError("Empty timestamp")
    return dateutil_parser.parse(s)


def _parse_location_element(elem: ET.Element) -> Tuple[float, float, datetime] | None:
    """Parse Location element and return (lat, lon, timestamp) or None."""
    lat = elem.get("latitude") or elem.get("lat")
    lon = elem.get("longitude") or elem.get("lon")
    ts = elem.get("timestamp") or elem.get("time") or elem.get("timestamp")
    if lat and lon and ts:
        try:
            return float(lat), float(lon), parse_timestamp(ts)
        except (ValueError, TypeError):
            pass
    return None


def _parse_trkpt_with_time(
    elem: ET.Element, current_time: str | None
) -> Tuple[float, float, datetime] | None:
    """Parse trkpt element with stored time data."""
    lat = elem.get("lat")
    lon = elem.get("lon")
    if lat and lon and current_time:
        try:
            return float(lat), float(lon), parse_timestamp(current_time)
        except (ValueError, TypeError):
            pass
    return None


def _parse_xml_data(bio: BinaryIO) -> Iterable[Tuple[float, float, datetime]]:
    """Parse XML data and yield GPS points."""
    it = ET.iterparse(bio, events=("end",))
    current_trkpt_data: Dict[str, str] = {}

    for _, elem in it:
        tag = elem.tag.split("}")[-1]
        if tag in ("Location", "location"):
            point = _parse_location_element(elem)
            if point:
                yield point
        elif tag == "time" and elem.text:
            current_trkpt_data["time"] = elem.text
        elif tag in ("trkpt", "trkPoint"):
            point = _parse_trkpt_with_time(elem, current_trkpt_data.get("time"))
            if point:
                yield point
            current_trkpt_data.clear()
        elem.clear()


def _parse_line_data(f: BinaryIO) -> Iterable[Tuple[float, float, datetime]]:
    """Parse line-based data and yield GPS points."""
    for line in f:
        try:
            s = line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
        except (UnicodeDecodeError, AttributeError):
            continue
        if "latitude" in s and "longitude" in s:
            try:
                parts = s.replace('"', "").replace("'", "").split()
                lat = next(
                    (p.split("=")[1] for p in parts if p.startswith("latitude")), None
                )
                lon = next(
                    (p.split("=")[1] for p in parts if p.startswith("longitude")), None
                )
                ts = next(
                    (p.split("=")[1] for p in parts if p.startswith("timestamp")), None
                )
                if lat and lon and ts:
                    yield float(lat), float(lon), parse_timestamp(ts)
            except (ValueError, TypeError, IndexError):
                continue


def stream_points_from_route(f: BinaryIO) -> Iterable[Tuple[float, float, datetime]]:
    """Yield (lat, lon, timestamp) tuples from a route file-like object.

    Supports Apple Health `Route` XML with `Location` tags or GPX `trkpt` entries.
    Uses iterparse and clears elements to keep memory low.
    """
    data = f.read()
    try:
        bio = __import__("io").BytesIO(data)
        text_start = data[:4096].decode("utf-8", errors="ignore").lstrip()
    except (UnicodeDecodeError, AttributeError):
        return

    if text_start.startswith("<?xml") or text_start.startswith("<"):
        yield from _parse_xml_data(bio)
    else:
        yield from _parse_line_data(f)


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
    cum: List[float],
    cum_adj_time: List[float],
    target_m: float,
    points: List[Tuple[float, float, datetime]],
    adj_time_deltas: List[float],
    time_deltas: List[float],
    dist_between: List[float],
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
        while j < n and (cum[j] - cum[i]) < target_m:
            j += 1
        if j >= n:
            break

        duration = cum_adj_time[j] - cum_adj_time[i]
        if debug_info is not None:
            penalties = _collect_debug_penalties(
                i, j, adj_time_deltas, time_deltas, dist_between
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

    best, best_i, best_j, penalized_intervals = _find_best_segment(
        n,
        cum,
        cum_adj_time,
        target_m,
        points,
        adj_time_deltas,
        time_deltas,
        dist_between,
        debug_info,
    )

    if debug_info is not None:
        _update_debug_info(debug_info, best_i, best_j, cum, n, penalized_intervals)

    return best


def _collect_penalty_messages(
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


def _load_workout_points(
    reader: ExportReader, refs: set[str]
) -> List[Tuple[float, float, datetime]]:
    """Load GPS points from workout route files."""
    points: List[Tuple[float, float, datetime]] = []
    for ref in refs:
        try:
            z_path = reader.resolve_zip_path(ref)
            if not z_path:
                z_path = reader.resolve_zip_path(ref.lstrip("/") if ref else ref)
                if not z_path:
                    continue
            with reader.zipfile.open(z_path) as rf:
                for lat, lon, ts in stream_points_from_route(rf):  # type: ignore
                    points.append((lat, lon, ts))
        except (KeyError, ET.ParseError, ValueError, TypeError):
            continue
    return points


def _log_debug_segment(
    debug: bool,
    workout_date: datetime | None,
    d: float,
    duration: float,
    debug_info: Dict[str, Any] | None,
) -> None:
    """Log debug information for specific segment."""
    if not debug or not workout_date or not debug_info:
        return
    if not math.isclose(d, 400.0):
        return
    if workout_date.strftime(DATE_FMT) != "26/12/2021":
        return
    segment_dist = debug_info.get("segment_dist", "N/A")  # type: ignore
    num_points = debug_info.get("num_points", "N/A")  # type: ignore
    total_dist = debug_info.get("total_dist", "N/A")  # type: ignore
    print(
        f"DEBUG [26/12/2021, 400m]: duration={duration:.2f}s, "
        f"dist_covered={segment_dist:.1f}m, pts={num_points}, "
        f"total={total_dist:.0f}m"
    )


def _process_distance(
    d: float,
    points: List[Tuple[float, float, datetime]],
    workout_date: datetime | None,
    best_segments: Dict[float, List[Tuple[float, datetime | None]]],
    penalty_messages: Dict[str, str],
    max_speed_kmh: float,
    penalty_seconds: float,
    debug: bool,
    verbose: bool,
) -> None:
    """Process a single distance for the workout."""
    debug_info: Dict[str, Any] | None = {} if debug or verbose else None
    duration, s, _ = best_segment_for_dist(
        points, d, max_speed_kmh, penalty_seconds, debug_info
    )
    if duration != float("inf") and s:
        best_segments[d].append((duration, workout_date))
        _log_debug_segment(debug, workout_date, d, duration, debug_info)
    if (
        verbose
        and debug_info is not None
        and (penalized_intervals_data := debug_info.get("penalized_intervals"))
    ):  # type: ignore
        _collect_penalty_messages(penalized_intervals_data, points, penalty_messages)


def _process_workout(
    reader: ExportReader,
    workout_ref: str,
    refs: set[str],
    running_workouts: Dict[str, Dict[str, datetime | None]],
    distances_m: List[float],
    best_segments: Dict[float, List[Tuple[float, datetime | None]]],
    penalty_messages: Dict[str, str],
    max_speed_kmh: float,
    penalty_seconds: float,
    debug: bool,
    verbose: bool,
    start_date: date | None,
    end_date: date | None,
) -> None:
    """Process a single workout and update results."""
    wd = running_workouts.get(workout_ref)
    workout_date = wd.get("start") if isinstance(wd, dict) else wd

    if start_date and workout_date and workout_date.date() < start_date:
        return
    if end_date and workout_date and workout_date.date() > end_date:
        return

    points = _load_workout_points(reader, refs)
    if not points:
        return

    points.sort(key=lambda x: x[2])  # type: ignore

    for d in distances_m:
        _process_distance(
            d,
            points,
            workout_date,
            best_segments,
            penalty_messages,
            max_speed_kmh,
            penalty_seconds,
            debug,
            verbose,
        )


def process_export(
    zip_path: str,
    distances_m: Iterable[float],
    top_n: int = 5,
    debug: bool = False,
    progress: bool = False,
    max_speed_kmh: float = 35.39,
    penalty_seconds: float = 3.0,
    verbose: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Tuple[Dict[float, List[Tuple[float, datetime | None]]], Dict[str, str]]:
    """Process Apple Health export to find fastest running segments.

    Returns tuple of (results_dict, penalty_messages_dict).
    """
    distances_m = list(distances_m)
    best_segments: Dict[float, List[Tuple[float, datetime | None]]] = {
        d: [] for d in distances_m
    }
    penalty_messages: Dict[str, str] = {}

    with ExportReader(zip_path) as reader:
        export_xml_name = reader.find_export_xml()
        running_workouts = reader.collect_running_workouts(export_xml_name)
        routes = reader.collect_routes(export_xml_name)

        if not routes:
            routes = reader.collect_routes_fallback(export_xml_name)

        workout_to_files = match_routes_to_workouts(routes, running_workouts)

        if debug:
            print(
                f"DEBUG: running_workouts={len(running_workouts)}, "
                f"routes_with_paths={len(routes)}"
            )
            print(f"DEBUG: matched workout->files entries={len(workout_to_files)}")
            for k, v in list(workout_to_files.items())[:5]:
                print(f"DEBUG: workout {k} -> {list(v)[:3]}")

        iterable = workout_to_files.items()
        if progress and tqdm is not None:
            iterable = tqdm(list(iterable), desc="Workouts")
        elif progress and tqdm is None and debug:
            print("DEBUG: tqdm not installed, progress disabled")

        for workout_ref, refs in iterable:
            _process_workout(
                reader,
                workout_ref,
                refs,
                running_workouts,
                distances_m,
                best_segments,
                penalty_messages,
                max_speed_kmh,
                penalty_seconds,
                debug,
                verbose,
                start_date,
                end_date,
            )

    results: Dict[float, List[Tuple[float, datetime | None]]] = {}
    for d, segs in best_segments.items():
        segs.sort(key=lambda x: x[0])  # type: ignore
        results[d] = segs[:top_n]

    return results, penalty_messages


def format_duration(s: float | None) -> str:
    """Format duration in seconds as HH:MM:SS string."""
    if s is None or s == float("inf"):
        return "-"
    total = int(round(s))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_distance(d: float | None) -> str:
    """Return a human-friendly label for a distance in meters.

    - 1000 -> '1 km', 5000 -> '5 km'
    - 21097.5 -> 'Half Marathon', 42195 -> 'Marathon'
    - <1000 -> '400 m' style
    """
    if d is None:
        return ""
    # Common exact labels
    try:
        if abs(d - 21097.5) < 0.5:
            return "Half Marathon"
        if abs(d - 42195.0) < 0.5:
            return "Marathon"
    except (ArithmeticError, ValueError):
        pass
    # Use km for round kilometers
    if d >= 1000:
        km = d / 1000.0
        if abs(km - round(km)) < 1e-6:
            return f"{int(round(km))} km"
        # show up to 2 decimals, trim trailing zeros
        s = f"{km:.2f}".rstrip("0").rstrip(".")
        return f"{s} km"
    # default to meters
    return f"{int(round(d))} m"


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Find top fastest running segments in an Apple Health export.zip"
    )
    parser.add_argument("--zip", required=True, help="Path to export.zip")
    parser.add_argument(
        "--top", type=int, default=5, help="Number of top segments per distance"
    )
    parser.add_argument(
        "--distances",
        nargs="+",
        type=float,
        default=[
            400.0,
            800.0,
            1000.0,
            5000.0,
            10000.0,
            15000.0,
            20000.0,
            21097.5,
            42195.0,
        ],
        help="Distances in meters to search (e.g. 400 1000 5000)",
    )
    parser.add_argument("--output-file", "-o", help="Write output to this text file")
    parser.add_argument(
        "--penalty-file",
        help="Write penalty messages to this text file (also prints to screen)",
    )
    parser.add_argument("--debug", action="store_true", help="Show debug messages")
    parser.add_argument(
        "--max-speed",
        type=float,
        default=20.0,
        help=(
            "Maximum instantaneous speed in km/h to consider valid "
            "(filters GPS errors; default: 20.0 km/h)"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show warnings for segments exceeding max-speed limit",
    )
    parser.add_argument(
        "--speed-penalty",
        "--penalty-seconds",
        dest="speed_penalty",
        type=float,
        default=3.0,
        help="Seconds to add to any interval exceeding --max-speed",
    )
    # progress is enabled by default; use --no-progress to disable
    parser.add_argument(
        "--progress",
        dest="progress",
        action="store_true",
        help="Show a progress bar during processing (default: enabled)",
    )
    parser.add_argument(
        "--no-progress",
        dest="progress",
        action="store_false",
        help="Disable the progress bar",
    )
    parser.add_argument(
        "--start-date", help="Start date filter (YYYYMMDD format, inclusive)"
    )
    parser.add_argument(
        "--end-date", help="End date filter (YYYYMMDD format, inclusive)"
    )
    parser.set_defaults(progress=True)
    args = parser.parse_args()

    # Parse and validate date filters
    start_date = None
    end_date = None
    try:
        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y%m%d").date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y%m%d").date()
    except ValueError as e:
        print(f"Error parsing date: {e}. Use YYYYMMDD format.")
        return

    results, penalty_messages = process_export(
        args.zip,
        args.distances,
        top_n=args.top,
        debug=args.debug,
        progress=args.progress,
        max_speed_kmh=args.max_speed,
        penalty_seconds=args.speed_penalty,
        verbose=args.verbose,
        start_date=start_date,
        end_date=end_date,
    )

    # Print results
    out_lines: List[str] = []

    # Add penalty messages to output if any
    penalty_lines: List[str] = []
    if penalty_messages:
        penalty_lines.append("")
        penalty_lines.append("=== PENALTY WARNINGS ===")
        # Sort penalty messages by timestamp (key is already in DD/MM/YYYY HH:MM:SS format)
        for key in sorted(penalty_messages.keys()):
            penalty_lines.append(penalty_messages[key])
        penalty_lines.append("")

    for d in sorted(results.keys()):
        out_lines.append(f"\nDistance: {format_distance(d)}")
        rows = results[d]
        if not rows:
            out_lines.append("  No segments found")
            continue
        for idx, (duration, workout_dt) in enumerate(rows, start=1):
            if workout_dt:
                try:
                    date_str = workout_dt.strftime("%d/%m/%Y")
                except (AttributeError, ValueError):
                    date_str = workout_dt.isoformat()
            else:
                date_str = "unknown"
            out_lines.append(f"  {idx:2d}. {date_str}  {format_duration(duration)}")

    # print penalty messages to stdout
    for line in penalty_lines:
        print(line)

    # print results to stdout
    for line in out_lines:
        print(line)

    # optionally write penalty messages to file
    if args.penalty_file and penalty_messages:
        try:
            with open(args.penalty_file, "w", encoding="utf-8") as fh:
                for line in penalty_lines:
                    fh.write(line + "\n")
        except OSError as e:
            print(f"Error writing penalty file: {e}")

    # optionally write main results to file
    if args.output_file:
        try:
            with open(args.output_file, "w", encoding="utf-8") as fh:
                for line in out_lines:
                    fh.write(line + "\n")
        except OSError as e:
            print(f"Error writing output file: {e}")


if __name__ == "__main__":
    main()
