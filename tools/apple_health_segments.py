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
from typing import Iterable, List, Tuple, Any, Dict

from export_processor import (
    ExportReader,
    match_routes_to_workouts,
    stream_points_from_route,
)
from segment_analysis import best_segment_for_dist, collect_penalty_messages

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

DATE_FMT = "%d/%m/%Y"


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
    config: Dict[str, Any],
) -> None:
    """Process a single distance for the workout."""
    max_speed_kmh = config.get("max_speed_kmh", 20.0)
    penalty_seconds = config.get("penalty_seconds", 3.0)
    debug = config.get("debug", False)
    verbose = config.get("verbose", False)

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
        collect_penalty_messages(penalized_intervals_data, points, penalty_messages)


def _should_skip_workout(
    workout_date: datetime | None, start_date: date | None, end_date: date | None
) -> bool:
    """Check if workout should be skipped based on date filters."""
    if not workout_date:
        return False
    if start_date and workout_date.date() < start_date:
        return True
    if end_date and workout_date.date() > end_date:
        return True
    return False


def _process_workout(
    reader: ExportReader,
    workout_ref: str,
    refs: set[str],
    running_workouts: Dict[str, Dict[str, datetime | None]],
    distances_m: List[float],
    results: Dict[float, List[Tuple[float, datetime | None]]],
    penalty_messages: Dict[str, str],
    config: Dict[str, Any],
) -> None:
    """Process a single workout and update results."""
    wd = running_workouts.get(workout_ref)
    workout_date = wd.get("start") if isinstance(wd, dict) else wd

    if _should_skip_workout(
        workout_date, config.get("start_date"), config.get("end_date")
    ):
        return

    points = _load_workout_points(reader, refs)
    if not points:
        return

    points.sort(key=lambda x: x[2])  # type: ignore

    for d in distances_m:
        _process_distance(d, points, workout_date, results, penalty_messages, config)


def _print_debug_info(
    debug: bool,
    running_workouts: Dict[str, Dict[str, datetime | None]],
    routes: List[Tuple[datetime | None, datetime | None, List[str]]],
    workout_to_files: Dict[str, set[str]],
) -> None:
    """Print debug information."""
    if not debug:
        return
    print(
        f"DEBUG: running_workouts={len(running_workouts)}, "
        f"routes_with_paths={len(routes)}"
    )
    print(f"DEBUG: matched workout->files entries={len(workout_to_files)}")
    for k, v in list(workout_to_files.items())[:5]:
        print(f"DEBUG: workout {k} -> {list(v)[:3]}")


def _get_progress_iterable(iterable: Any, progress: bool, debug: bool) -> Any:
    """Wrap iterable with progress bar if available."""
    if progress and tqdm is not None:
        return tqdm(list(iterable), desc="Workouts")
    if progress and tqdm is None and debug:
        print("DEBUG: tqdm not installed, progress disabled")
    return iterable


def _finalize_results(
    best_segments: Dict[float, List[Tuple[float, datetime | None]]], top_n: int
) -> Dict[float, List[Tuple[float, datetime | None]]]:
    """Sort and trim results to top N."""
    results: Dict[float, List[Tuple[float, datetime | None]]] = {}
    for d, segs in best_segments.items():
        segs.sort(key=lambda x: x[0])  # type: ignore
        results[d] = segs[:top_n]
    return results


def _load_export_data(
    reader: ExportReader,
) -> Tuple[
    Dict[str, Dict[str, datetime | None]],
    List[Tuple[datetime | None, datetime | None, List[str]]],
    Dict[str, set[str]],
]:
    """Load workouts, routes, and match them."""
    export_xml_name = reader.find_export_xml()
    running_workouts = reader.collect_running_workouts(export_xml_name)
    routes = reader.collect_routes(export_xml_name)
    if not routes:
        routes = reader.collect_routes_fallback(export_xml_name)
    workout_to_files = match_routes_to_workouts(routes, running_workouts)
    return running_workouts, routes, workout_to_files


def _process_all_workouts(
    reader: ExportReader,
    workout_to_files: Dict[str, set[str]],
    running_workouts: Dict[str, Dict[str, datetime | None]],
    distances_m: List[float],
    best_segments: Dict[float, List[Tuple[float, datetime | None]]],
    penalty_messages: Dict[str, str],
    config: Dict[str, Any],
) -> None:
    """Process all workouts with progress tracking."""
    iterable = _get_progress_iterable(
        workout_to_files.items(),
        config.get("progress", False),
        config.get("debug", False),
    )
    for workout_ref, refs in iterable:
        _process_workout(
            reader,
            workout_ref,
            refs,
            running_workouts,
            distances_m,
            best_segments,
            penalty_messages,
            config,
        )


def process_export(
    zip_path: str,
    distances_m: Iterable[float],
    top_n: int = 5,
    config: Dict[str, Any] | None = None,
) -> Tuple[Dict[float, List[Tuple[float, datetime | None]]], Dict[str, str]]:
    """Process Apple Health export to find fastest running segments.

    Returns tuple of (results_dict, penalty_messages_dict).
    """
    if config is None:
        config = {}

    distances_m = list(distances_m)
    best_segments: Dict[float, List[Tuple[float, datetime | None]]] = {
        d: [] for d in distances_m
    }
    penalty_messages: Dict[str, str] = {}

    with ExportReader(zip_path) as reader:
        running_workouts, routes, workout_to_files = _load_export_data(reader)
        _print_debug_info(
            config.get("debug", False), running_workouts, routes, workout_to_files
        )
        _process_all_workouts(
            reader,
            workout_to_files,
            running_workouts,
            distances_m,
            best_segments,
            penalty_messages,
            config,
        )

    return _finalize_results(best_segments, top_n), penalty_messages


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


def _add_basic_args(parser: argparse.ArgumentParser) -> None:
    """Add basic CLI arguments."""
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


def _add_speed_args(parser: argparse.ArgumentParser) -> None:
    """Add speed and penalty related arguments."""
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


def _add_filter_args(parser: argparse.ArgumentParser) -> None:
    """Add progress and date filter arguments."""
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


def _add_cli_arguments(parser: argparse.ArgumentParser) -> None:
    """Add all CLI arguments to parser."""
    _add_basic_args(parser)
    _add_speed_args(parser)
    _add_filter_args(parser)


def _parse_cli_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Find top fastest running segments in an Apple Health export.zip"
    )
    _add_cli_arguments(parser)
    return parser.parse_args()


def _parse_date_filters(args: argparse.Namespace) -> Tuple[date | None, date | None]:
    """Parse and validate date filter arguments."""
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y%m%d").date()
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y%m%d").date()
    return start_date, end_date


def _format_penalty_lines(penalty_messages: Dict[str, str]) -> List[str]:
    """Format penalty messages for output."""
    if not penalty_messages:
        return []
    lines = ["", "=== PENALTY WARNINGS ==="]
    for key in sorted(penalty_messages.keys()):
        lines.append(penalty_messages[key])
    lines.append("")
    return lines


def _format_results_lines(
    results: Dict[float, List[Tuple[float, datetime | None]]],
) -> List[str]:
    """Format results for output."""
    lines: List[str] = []
    for d in sorted(results.keys()):
        lines.append(f"\nDistance: {format_distance(d)}")
        rows = results[d]
        if not rows:
            lines.append("  No segments found")
            continue
        for idx, (duration, workout_dt) in enumerate(rows, start=1):
            if workout_dt:
                try:
                    date_str = workout_dt.strftime("%d/%m/%Y")
                except (AttributeError, ValueError):
                    date_str = workout_dt.isoformat()
            else:
                date_str = "unknown"
            lines.append(f"  {idx:2d}. {date_str}  {format_duration(duration)}")
    return lines


def _write_output_file(filepath: str, lines: List[str]) -> None:
    """Write lines to output file."""
    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line + "\n")
    except OSError as e:
        print(f"Error writing file: {e}")


def main():
    """Main entry point for CLI."""
    args = _parse_cli_args()

    try:
        start_date, end_date = _parse_date_filters(args)
    except ValueError as e:
        print(f"Error parsing date: {e}. Use YYYYMMDD format.")
        return

    config: Dict[str, Any] = {
        "debug": args.debug,
        "progress": args.progress,
        "max_speed_kmh": args.max_speed,
        "penalty_seconds": args.speed_penalty,
        "verbose": args.verbose,
        "start_date": start_date,
        "end_date": end_date,
    }
    results, penalty_messages = process_export(
        args.zip, args.distances, top_n=args.top, config=config
    )

    penalty_lines = _format_penalty_lines(penalty_messages)
    out_lines = _format_results_lines(results)

    for line in penalty_lines:
        print(line)
    for line in out_lines:
        print(line)

    if args.penalty_file and penalty_messages:
        _write_output_file(args.penalty_file, penalty_lines)
    if args.output_file:
        _write_output_file(args.output_file, out_lines)


if __name__ == "__main__":
    main()
