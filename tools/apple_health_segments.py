#!/usr/bin/env python3
"""
CLI to find top fastest segments for running workouts inside an Apple Health export.zip.

Usage examples (PowerShell):
  pwsh> python .\tools\apple_health_segments.py \
      --zip "C:\\Users\\NicolasReyrolle\\OneDrive - EDDA Luxembourg S.A\\Perso\\export.zip" \
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
from collections import defaultdict
from datetime import datetime
from dateutil import parser as dateutil_parser
from typing import Iterable, List, Tuple
import heapq
import zipfile
try:
    from tqdm import tqdm
except Exception:
    tqdm = None

DATE_FMT = '%d/%m/%Y'


def haversine_meters(lat1, lon1, lat2, lon2):
    # Returns distance in meters between two lat/lon points
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_timestamp(s: str) -> datetime:
    # Use dateutil for robust parsing of many timestamp formats
    if not s:
        raise ValueError("Empty timestamp")
    return dateutil_parser.parse(s)


def stream_points_from_route(f) -> Iterable[Tuple[float, float, datetime]]:
    """Yield (lat, lon, timestamp) tuples from a route file-like object.

    Supports Apple Health `Route` XML with `Location` tags or GPX `trkpt` entries.
    Uses iterparse and clears elements to keep memory low.
    """
    # read entire file into memory for robust parsing (route files are small)
    data = f.read()
    try:
        bio = __import__('io').BytesIO(data)
        text_start = data[:4096].decode('utf-8', errors='ignore').lstrip()
    except Exception:
        return

    if text_start.startswith("<?xml") or text_start.startswith("<"):
        # Use iterparse on BytesIO
        it = ET.iterparse(bio, events=("end",))
        for event, elem in it:
            tag = elem.tag.split('}')[-1]
            if tag in ("Location", "location"):
                lat = elem.get("latitude") or elem.get("lat")
                lon = elem.get("longitude") or elem.get("lon")
                ts = elem.get("timestamp") or elem.get("time") or elem.get("timestamp")
                if lat and lon and ts:
                    try:
                        yield float(lat), float(lon), parse_timestamp(ts)
                    except Exception:
                        pass
                elem.clear()
            elif tag in ("trkpt", "trkPoint"):
                lat = elem.get("lat")
                lon = elem.get("lon")
                # try to find a child <time> in a namespace-agnostic way
                ts_text = None
                for child in elem:
                    if child.tag.split('}')[-1] == 'time' and child.text:
                        ts_text = child.text
                        break
                if lat and lon and ts_text:
                    try:
                        yield float(lat), float(lon), parse_timestamp(ts_text)
                    except Exception:
                        pass
                elem.clear()
    else:
        # Unknown format: try line-based search for numeric lat/lon/time
        for line in f:
            try:
                s = line.decode() if isinstance(line, (bytes, bytearray)) else line
            except Exception:
                continue
            if "latitude" in s and "longitude" in s:
                # naive parse
                try:
                    parts = s.replace('"', "").replace("'", "").split()
                    lat = next((p.split('=')[1] for p in parts if p.startswith("latitude")), None)
                    lon = next((p.split('=')[1] for p in parts if p.startswith("longitude")), None)
                    ts = next((p.split('=')[1] for p in parts if p.startswith("timestamp")), None)
                    if lat and lon and ts:
                        yield float(lat), float(lon), parse_timestamp(ts)
                except Exception:
                    continue


def best_segment_for_dist(points: List[Tuple[float, float, datetime]], target_m: float, max_speed_kmh: float = 35.39, penalty_seconds: float = 3.0, debug_info: dict | None = None) -> Tuple[float, datetime, datetime]:
    """Return (best_adjusted_duration_seconds, start_time, end_time) for the given target distance in meters.
    Points is a list of (lat, lon, datetime) sorted by time.
    Uses two-pointer sliding window. Instead of dropping segments whose instantaneous
    intervals exceed `max_speed_kmh`, we add `penalty_seconds` to any interval where
    the instantaneous speed > max_speed_kmh. The adjusted duration is used for ranking.
    """
    if not points:
        return (float('inf'), None, None)
    n = len(points)
    # Precompute cumulative distances between points and per-interval times/distances
    cum = [0.0] * n
    # time_deltas[i] is seconds between point i-1 and i (for i>=1)
    time_deltas = [0.0] * n
    dist_between = [0.0] * n
    adj_time_deltas = [0.0] * n
    for i in range(1, n):
        lat1, lon1, _ = points[i - 1]
        lat2, lon2, _ = points[i]
        d = haversine_meters(lat1, lon1, lat2, lon2)
        cum[i] = cum[i - 1] + d
        # compute time delta
        t1 = points[i - 1][2]
        t2 = points[i][2]
        dt = (t2 - t1).total_seconds()
        if dt < 0:
            dt = 0.0
        time_deltas[i] = dt
        dist_between[i] = d
        # instantaneous speed (km/h) for this interval
        # Skip intervals with infinite speed (zero duration, nonzero distance)
        if dt <= 0 and d > 0:
            inst_speed_kmh = float('inf')
        else:
            inst_speed_kmh = (d / dt) * 3.6 if dt > 0 else 0.0
        # Skip penalty assignment for infinite speed; treat as normal duration
        if math.isinf(inst_speed_kmh):
            adj = dt
        else:
            adj = dt + (penalty_seconds if inst_speed_kmh > max_speed_kmh else 0.0)
        adj_time_deltas[i] = adj

    best = (float('inf'), None, None)
    best_i = -1
    best_j = -1
    penalized_intervals = []  # list of (i_from, i_to, interval_seconds, speed_kmh, distance)
    # cumulative adjusted time for fast sum queries
    cum_adj_time = [0.0] * n
    for i in range(1, n):
        cum_adj_time[i] = cum_adj_time[i - 1] + adj_time_deltas[i]
    j = 0
    for i in range(n):
        # ensure j starts ahead of i
        if j <= i:
            j = i + 1
        # advance j until distance between i and j >= target
        while j < n and (cum[j] - cum[i]) < target_m:
            j += 1
        if j >= n:
            break
        start_time = points[i][2]
        end_time = points[j][2]
        # Adjusted duration: sum of adjusted per-interval times from i+1..j
        # which equals cum_adj_time[j] - cum_adj_time[i]
        duration = cum_adj_time[j] - cum_adj_time[i]
        # For debugging, collect any penalized intervals inside [i+1..j]
        if debug_info is not None:
            # find penalized intervals indices where adj_time_deltas[k] > time_deltas[k]
            penalized_in_segment = []
            for k in range(i + 1, j + 1):
                if adj_time_deltas[k] > time_deltas[k]:
                    inst_speed_kmh = (dist_between[k] / time_deltas[k]) * 3.6 if time_deltas[k] > 0 else float('inf')
                    penalized_in_segment.append((k - 1, k, time_deltas[k], inst_speed_kmh, dist_between[k]))
            if penalized_in_segment:
                penalized_intervals.append((i, j, penalized_in_segment))
        if duration >= 0 and duration < best[0]:
            best = (duration, start_time, end_time)
            best_i = i
            best_j = j
    
    # Store debug info if requested
    if debug_info is not None and best_i >= 0 and best_j >= 0:
        debug_info['best_i'] = best_i
        debug_info['best_j'] = best_j
        debug_info['start_cum_dist'] = cum[best_i]
        debug_info['end_cum_dist'] = cum[best_j]
        debug_info['segment_dist'] = cum[best_j] - cum[best_i]
        debug_info['num_points'] = n
        debug_info['total_dist'] = cum[-1] if n > 0 else 0
        debug_info['penalized_intervals'] = penalized_intervals
    
    return best


def process_export(zip_path: str, distances_m: Iterable[float], top_n: int = 5, debug: bool = False, progress: bool = False, max_speed_kmh: float = 35.39, penalty_seconds: float = 3.0, verbose: bool = False, start_date=None, end_date=None, penalty_file: str | None = None):
    distances_m = list(distances_m)
    # best_segments[d] -> list of tuples (duration_seconds, date)
    best_segments = {d: [] for d in distances_m}
    # Collect penalty messages: dict of (date_str, ts_str) -> message to deduplicate
    penalty_messages = {}

    with zipfile.ZipFile(zip_path, 'r') as z:
        # Try to locate the export XML inside the archive (Apple exports sometimes use export_cda.xml)
        names = z.namelist()
        export_xml_name = None
        for n in names:
            ln = n.lower()
            if ln.endswith('export.xml') or ln.endswith('export_cda.xml') or '/export.xml' in ln:
                export_xml_name = n
                break
        if not export_xml_name:
            # fallback: try any xml at root containing 'export'
            for n in names:
                if n.lower().endswith('.xml') and 'export' in n.lower():
                    export_xml_name = n
                    break
        if not export_xml_name:
            raise FileNotFoundError('Could not find export XML inside the zip')
        # First pass: collect running workouts into a list (id -> {'start','end'})
        running_workouts = {}
        running_workouts_list = []
        with z.open(export_xml_name) as ef:
            it = ET.iterparse(ef, events=("end",))
            idx = 0
            for _, elem in it:
                tag = elem.tag.split('}')[-1]
                if tag == 'Workout':
                    wtype = elem.get('workoutActivityType')
                    start = elem.get('startDate') or elem.get('creationDate') or elem.get('start')
                    end = elem.get('endDate') or elem.get('end')
                    if wtype == 'HKWorkoutActivityTypeRunning':
                        wid = f"wk_{idx}"
                        idx += 1
                        try:
                            sdt = parse_timestamp(start) if start else None
                        except Exception:
                            sdt = None
                        try:
                            edt = parse_timestamp(end) if end else None
                        except Exception:
                            edt = None
                        running_workouts_list.append((wid, sdt, edt))
                        running_workouts[wid] = {'start': sdt, 'end': edt}
                elem.clear()

        # Collect all WorkoutRoute entries (with start/end and file refs).
        # We'll match routes to workouts by time-overlap.
        from collections import defaultdict

        workout_to_files = defaultdict(set)
        routes = []  # list of (route_start, route_end, [paths])
        with z.open(export_xml_name) as ef:
            it = ET.iterparse(ef, events=("end",))
            for _, elem in it:
                tag = elem.tag.split('}')[-1]
                if tag == 'WorkoutRoute':
                    rstart = elem.get('startDate') or elem.get('creationDate') or None
                    rend = elem.get('endDate') or None
                    try:
                        rstart_dt = parse_timestamp(rstart) if rstart else None
                    except Exception:
                        rstart_dt = None
                    try:
                        rend_dt = parse_timestamp(rend) if rend else None
                    except Exception:
                        rend_dt = None
                    paths = []
                    # namespace-agnostic findall for FileReference
                    for fr in elem.iter():
                        if fr.tag.split('}')[-1] == 'FileReference':
                            path = fr.get('path') or fr.text
                            if path:
                                paths.append(path)
                    if paths:
                        routes.append((rstart_dt, rend_dt, paths))
                elem.clear()

        # Match route time windows to running workouts by overlap
        def overlap(a_s, a_e, b_s, b_e):
            if a_s is None or a_e is None or b_s is None or b_e is None:
                return False
            latest_start = a_s if a_s > b_s else b_s
            earliest_end = a_e if a_e < b_e else b_e
            return latest_start <= earliest_end

        # For each route, attach its files to workouts that overlap in time
        for rstart, rend, paths in routes:
            for wid, w in running_workouts.items():
                if overlap(rstart, rend, w.get('start'), w.get('end')):
                    for p in paths:
                        workout_to_files[wid].add(p)

        # If we found no routes via XML parsing above, fallback to a text-based scan
        # which is more forgiving about namespaces and structure.
        if not routes:
            try:
                data = z.read(export_xml_name).decode('utf-8', errors='ignore')
                import re
                pattern = re.compile(r"<WorkoutRoute([^>]*)>(.*?)</WorkoutRoute>", re.DOTALL)
                for m in pattern.finditer(data):
                    opening = m.group(1)
                    body = m.group(2)
                    # find start and end attributes
                    def find_attr(s, name):
                        p = re.search(rf'{name}="([^"]+)"', s)
                        return p.group(1) if p else None
                    rstart = find_attr(opening, 'startDate') or find_attr(opening, 'creationDate')
                    rend = find_attr(opening, 'endDate')
                    try:
                        rstart_dt = parse_timestamp(rstart) if rstart else None
                    except Exception:
                        rstart_dt = None
                    try:
                        rend_dt = parse_timestamp(rend) if rend else None
                    except Exception:
                        rend_dt = None
                    # find all FileReference path occurrences in body
                    paths = re.findall(r'<FileReference[^>]*path="([^"]+)"', body)
                    if paths:
                        routes.append((rstart_dt, rend_dt, paths))
                # re-run matching
                for rstart, rend, paths in routes:
                    for wid, w in running_workouts.items():
                        if overlap(rstart, rend, w.get('start'), w.get('end')):
                            for p in paths:
                                workout_to_files[wid].add(p)
            except Exception:
                pass

        def resolve_zip_path(zf: zipfile.ZipFile, ref_path: str):
            # Try several variants of the FileReference path to match entries inside the ZIP.
            if not ref_path:
                return None
            candidates = []
            # raw as-is
            candidates.append(ref_path)
            # strip leading slash
            if ref_path.startswith('/'):
                candidates.append(ref_path.lstrip('/'))
            else:
                candidates.append('/' + ref_path)
            # try under apple_health_export/ prefix
            if not ref_path.startswith('apple_health_export'):
                p = ref_path.lstrip('/')
                candidates.append('apple_health_export/' + p)
                candidates.append('apple_health_export' + ref_path)

            for c in candidates:
                if c in zf.namelist():
                    return c
            return None

        # Diagnostic summary: counts (only if debug requested)
        if debug:
            print(f"DEBUG: running_workouts={len(running_workouts)}, routes_with_paths={len(routes)}")
            print(f"DEBUG: matched workout->files entries={len(workout_to_files)}")
            # show a small sample
            sample_count = 0
            for k, v in list(workout_to_files.items())[:5]:
                print(f"DEBUG: workout {k} -> {list(v)[:3]}")
                sample_count += 1
                if sample_count >= 5:
                    break

        # Process each workout once, consolidating points across all referenced route files
        iterable = workout_to_files.items()
        if progress and tqdm is not None:
            iterable = tqdm(list(iterable), desc="Workouts")
        elif progress and tqdm is None:
            if debug:
                print("DEBUG: tqdm not installed, progress disabled")

        for workout_ref, refs in iterable:
            workout_date = None
            wd = running_workouts.get(workout_ref)
            if isinstance(wd, dict):
                workout_date = wd.get('start')
            else:
                workout_date = wd
            points = []
            for ref in refs:
                try:
                    z_path = resolve_zip_path(z, ref)
                    if not z_path:
                        # try without leading slash
                        z_path = resolve_zip_path(z, ref.lstrip('/') if ref else ref)
                    if not z_path:
                        # referenced file not found in zip, skip
                        # keep going to next referenced file
                        # print a small debug hint
                        # (avoid noisy output; only print when running interactively)
                        # fallback to next
                        continue
                    with z.open(z_path) as rf:
                        for lat, lon, ts in stream_points_from_route(rf):
                            points.append((lat, lon, ts))
                except KeyError:
                    # referenced file not found in zip, skip
                    continue
                except Exception:
                    # ignore parsing errors per-file to be robust
                    continue

            if not points:
                continue
            # sort by timestamp and compute segments once per workout
            points.sort(key=lambda x: x[2])
            # Filter by date range if specified
            if start_date and workout_date and workout_date.date() < start_date:
                continue
            if end_date and workout_date and workout_date.date() > end_date:
                continue
            for d in distances_m:
                debug_info = {} if debug or verbose else None
                duration, s, _ = best_segment_for_dist(points, d, max_speed_kmh, penalty_seconds, debug_info)
                if duration != float('inf') and s:
                    best_segments[d].append((duration, workout_date))
                    # Log details if this is the target date and distance
                    if debug and workout_date and s and math.isclose(d, 400.0):
                        if workout_date.strftime(DATE_FMT) == '26/12/2021':
                            print(f"DEBUG [26/12/2021, 400m]: duration={duration:.2f}s, dist_covered={debug_info.get('segment_dist', 'N/A'):.1f}m, pts={debug_info.get('num_points', 'N/A')}, total={debug_info.get('total_dist', 'N/A'):.0f}m")
                # Collect penalty messages if verbose (deduplicating by timestamp)
                if verbose and debug_info and debug_info.get('penalized_intervals'):
                    # debug_info['penalized_intervals'] is a list of (seg_i, seg_j, penalized_in_segment)
                    for seg_i, seg_j, penalized_list in debug_info['penalized_intervals']:
                        for from_idx, to_idx, interval_dur, inst_speed_kmh, interval_dist in penalized_list:
                            # from_idx is index of the earlier point in the pair
                            ts = None
                            try:
                                ts = points[from_idx][2]
                            except Exception:
                                ts = None
                            if ts is not None:
                                # Format as DD/MM/YYYY HH:MM:SS
                                ts_formatted = ts.strftime('%d/%m/%Y %H:%M:%S')
                            else:
                                ts_formatted = 'unknown'
                            # Use timestamp as unique key to avoid duplicate messages for same data point
                            key = ts_formatted
                            msg = f"{ts_formatted} | interval {from_idx}->{to_idx} | {interval_dur:.2f}s | {inst_speed_kmh:.1f} km/h"
                            if key not in penalty_messages:
                                penalty_messages[key] = msg

    # Reduce to top-N fastest per distance
    results = {}
    for d, segs in best_segments.items():
        segs.sort(key=lambda x: x[0])
        results[d] = segs[:top_n]
    
    # Return both results and penalty messages
    return results, penalty_messages


def format_duration(s: float) -> str:
    if s is None or s == float('inf'):
        return "-"
    total = int(round(s))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_distance(d: float) -> str:
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
    except Exception:
        pass
    # Use km for round kilometers
    if d >= 1000:
        km = d / 1000.0
        if abs(km - round(km)) < 1e-6:
            return f"{int(round(km))} km"
        # show up to 2 decimals, trim trailing zeros
        s = f"{km:.2f}".rstrip('0').rstrip('.')
        return f"{s} km"
    # default to meters
    return f"{int(round(d))} m"


def main():
    parser = argparse.ArgumentParser(description="Find top fastest running segments in an Apple Health export.zip")
    parser.add_argument('--zip', required=True, help='Path to export.zip')
    parser.add_argument('--top', type=int, default=5, help='Number of top segments per distance')
    parser.add_argument('--distances', nargs='+', type=float,
                        default=[400.0, 800.0, 1000.0, 5000.0, 10000.0, 15000.0, 20000.0, 21097.5, 42195.0],
                        help='Distances in meters to search (e.g. 400 1000 5000)')
    parser.add_argument('--output-file', '-o', help='Write output to this text file')
    parser.add_argument('--penalty-file', help='Write penalty messages to this text file (also prints to screen)')
    parser.add_argument('--debug', action='store_true', help='Show debug messages')
    parser.add_argument('--max-speed', type=float, default=20.0, help='Maximum instantaneous speed in km/h to consider valid (filters GPS errors; default: 20.0 km/h)')
    parser.add_argument('--verbose', action='store_true', help='Show warnings for segments exceeding max-speed limit')
    parser.add_argument('--speed-penalty', '--penalty-seconds', dest='speed_penalty', type=float, default=3.0, help='Seconds to add to any interval exceeding --max-speed')
    # progress is enabled by default; use --no-progress to disable
    parser.add_argument('--progress', dest='progress', action='store_true', help='Show a progress bar during processing (default: enabled)')
    parser.add_argument('--no-progress', dest='progress', action='store_false', help='Disable the progress bar')
    parser.add_argument('--start-date', help='Start date filter (YYYYMMDD format, inclusive)')
    parser.add_argument('--end-date', help='End date filter (YYYYMMDD format, inclusive)')
    parser.set_defaults(progress=True)
    args = parser.parse_args()

    # Parse and validate date filters
    start_date = None
    end_date = None
    try:
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y%m%d').date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y%m%d').date()
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
        penalty_file=args.penalty_file,
    )

    # Print results
    out_lines = []
    
    # Add penalty messages to output if any
    penalty_lines = []
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
        for idx, (duration, date) in enumerate(rows, start=1):
            if date:
                try:
                    date_str = date.strftime('%d/%m/%Y')
                except Exception:
                    # fallback to isoformat
                    date_str = date.isoformat()
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
            with open(args.penalty_file, 'w', encoding='utf-8') as fh:
                for line in penalty_lines:
                    fh.write(line + '\n')
        except Exception as e:
            print(f"Error writing penalty file: {e}")

    # optionally write main results to file
    if args.output_file:
        try:
            with open(args.output_file, 'w', encoding='utf-8') as fh:
                for line in out_lines:
                    fh.write(line + '\n')
        except Exception as e:
            print(f"Error writing output file: {e}")


if __name__ == '__main__':
    main()
