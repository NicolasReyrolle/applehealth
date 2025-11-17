#!/usr/bin/env python3
"""Extract all GPX points from an Apple Health export for a specific date.

Usage: python tools/points_on_date.py --zip /path/to/export.zip --date YYYY-MM-DD

Prints CSV-like lines: timestamp, duration_since_prev_s, distance_m, speed_kmh
"""

import argparse
import math
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Tuple

from dateutil import parser as dateparser


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in meters using Haversine formula."""
    earth_radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _extract_coordinates(elem: ET.Element) -> Tuple[float, float] | None:
    """Extract lat/lon coordinates from trkpt element."""
    lat_str = elem.attrib.get("lat")
    lon_str = elem.attrib.get("lon")
    if lat_str is None or lon_str is None:
        return None
    return float(lat_str), float(lon_str)


def _find_time_element(elem: ET.Element) -> ET.Element | None:
    """Find time child element in trkpt."""
    for child in elem:
        if child.tag.endswith("time"):
            return child
    return None


def _parse_timestamp(time_elem: ET.Element) -> datetime | None:
    """Parse timestamp from time element."""
    if time_elem.text is None:
        return None
    try:
        ts = dateparser.parse(time_elem.text)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except (ValueError, TypeError, OverflowError):
        return None


def parse_gpx_points(gpx_bytes: bytes):
    """Parse GPX and yield (timestamp(datetime), lat(float), lon(float)) for each trkpt."""
    it = ET.iterparse(BytesIO(gpx_bytes))
    for _, elem in it:
        if elem.tag.endswith("trkpt"):
            coords = _extract_coordinates(elem)
            if coords is None:
                elem.clear()
                continue

            time_elem = _find_time_element(elem)
            if time_elem is None:
                elem.clear()
                continue

            ts = _parse_timestamp(time_elem)
            if ts is None:
                elem.clear()
                continue

            yield ts, coords[0], coords[1]
        elem.clear()


def find_gpx_files_for_date(zip_path: str, target_date: str) -> List[Tuple[str, bytes]]:
    """Find GPX files in zip that contain the target date."""
    found: List[Tuple[str, bytes]] = []
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            name = info.filename
            if not name.lower().endswith(".gpx"):
                continue
            data = z.read(name)
            # quick check: if the file contains the target date string, include it
            if target_date.encode("utf-8") in data:
                found.append((name, data))
            else:
                # still attempt parsing to be safe
                if target_date in str(data):
                    found.append((name, data))
    return found


def extract_points_for_date(
    zip_path: str, date_str: str
) -> List[Tuple[datetime, float, float, str]]:
    """Extract GPS points from zip file for specific date."""
    target_date: str = date_str
    files = find_gpx_files_for_date(zip_path, target_date)
    all_points: List[Tuple[datetime, float, float, str]] = []
    for name, data in files:
        for ts, lat, lon in parse_gpx_points(data):
            if ts.date().isoformat() == date_str:
                all_points.append((ts, lat, lon, name))
    # sort by timestamp
    all_points.sort(key=lambda x: x[0])
    return all_points


def format_point_lines(
    points: List[Tuple[datetime, float, float, str]],
) -> List[Tuple[str, str, str, str, str]]:
    """Format GPS points into CSV-ready lines with duration and speed calculations."""
    lines: List[Tuple[str, str, str, str, str]] = []
    prev_ts: datetime | None = None
    prev_lat: float | None = None
    prev_lon: float | None = None
    for ts, lat, lon, fname in points:
        if prev_ts is None or prev_lat is None or prev_lon is None:
            dur = 0.0
            dist = 0.0
            speed = 0.0
        else:
            dur = (ts - prev_ts).total_seconds()
            if dur <= 0:
                dur = 0.0
            dist = haversine_m(prev_lat, prev_lon, lat, lon)
            speed = (dist / dur) * 3.6 if dur > 0 else 0.0
        # timestamp in ISO
        lines.append(
            (ts.isoformat(), f"{dur:.2f}", f"{dist:.2f}", f"{speed:.2f}", fname)
        )
        prev_ts = ts
        prev_lat = lat
        prev_lon = lon
    return lines


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, help="Path to Apple Health export.zip")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD")
    args = parser.parse_args()
    pts = extract_points_for_date(args.zip, args.date)
    if not pts:
        print(f"No GPX points found for {args.date}")
        return
    lines = format_point_lines(pts)
    print("timestamp,duration_s,distance_m,speed_kmh,source_file")
    for t, dur, dist, speed, fname in lines:
        print(f"{t},{dur},{dist},{speed},{fname}")


if __name__ == "__main__":
    main()
