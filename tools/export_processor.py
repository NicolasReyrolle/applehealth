"""Export processor for Apple Health data."""
from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple, Dict, BinaryIO, Iterable, Any
from dateutil import parser as dateutil_parser

try:
    from defusedxml.ElementTree import iterparse
except ImportError:
    from xml.etree.ElementTree import iterparse


def parse_timestamp(s: str) -> datetime:
    """Parse timestamp string using dateutil for robust format handling."""
    if not s:
        raise ValueError("Empty timestamp")
    return dateutil_parser.parse(s)


def _get_location_attrs(elem: Any) -> Tuple[str | None, str | None, str | None]:
    """Extract lat, lon, and timestamp attributes from element."""
    lat = elem.get("latitude") or elem.get("lat")
    lon = elem.get("longitude") or elem.get("lon")
    ts = elem.get("timestamp") or elem.get("time")
    return lat, lon, ts


def _parse_location_element(elem: Any) -> Tuple[float, float, datetime] | None:
    """Parse Location element and return (lat, lon, timestamp) or None."""
    lat, lon, ts = _get_location_attrs(elem)
    if lat and lon and ts:
        try:
            return float(lat), float(lon), parse_timestamp(ts)
        except (ValueError, TypeError):
            pass
    return None


def _parse_trkpt_with_time(
    elem: Any, current_time: str | None
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
    it = iterparse(bio, events=("end",))
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


def _decode_line(line: bytes | bytearray | str) -> str | None:
    """Decode line to string, return None on error."""
    try:
        return line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
    except (UnicodeDecodeError, AttributeError):
        return None


def _extract_gps_from_line(s: str) -> Tuple[str | None, str | None, str | None]:
    """Extract lat, lon, timestamp from line string."""
    parts = s.replace('"', "").replace("'", "").split()
    lat = next((p.split("=")[1] for p in parts if p.startswith("latitude")), None)
    lon = next((p.split("=")[1] for p in parts if p.startswith("longitude")), None)
    ts = next((p.split("=")[1] for p in parts if p.startswith("timestamp")), None)
    return lat, lon, ts


def _create_gps_point(
    lat: str | None, lon: str | None, ts: str | None
) -> Tuple[float, float, datetime] | None:
    """Create GPS point from string values, return None on error."""
    if not (lat and lon and ts):
        return None
    try:
        return float(lat), float(lon), parse_timestamp(ts)
    except (ValueError, TypeError, IndexError):
        return None


def _parse_line_data(f: BinaryIO) -> Iterable[Tuple[float, float, datetime]]:
    """Parse line-based data and yield GPS points."""
    for line in f:
        s = _decode_line(line)
        if not s or "latitude" not in s or "longitude" not in s:
            continue
        lat, lon, ts = _extract_gps_from_line(s)
        point = _create_gps_point(lat, lon, ts)
        if point:
            yield point


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


class ExportReader:
    """Reads and parses Apple Health export files."""

    def __init__(self, zip_path: str):
        self.zip_path = zip_path
        self.zipfile = zipfile.ZipFile(zip_path, "r")

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.zipfile.close()

    def find_export_xml(self) -> str:
        """Locate export XML file in archive."""
        names = self.zipfile.namelist()
        for n in names:
            ln = n.lower()
            if ln.endswith("export.xml") or ln.endswith("export_cda.xml") or "/export.xml" in ln:
                return n
        for n in names:
            if n.lower().endswith(".xml") and "export" in n.lower():
                return n
        raise FileNotFoundError("Could not find export XML inside the zip")

    def _parse_workout_times(self, elem: Any) -> Tuple[datetime | None, datetime | None]:
        """Extract start and end times from workout element."""
        start = elem.get("startDate") or elem.get("creationDate") or elem.get("start")
        end = elem.get("endDate") or elem.get("end")
        try:
            sdt = parse_timestamp(start) if start else None
        except (ValueError, TypeError):
            sdt = None
        try:
            edt = parse_timestamp(end) if end else None
        except (ValueError, TypeError):
            edt = None
        return sdt, edt

    def collect_running_workouts(self, xml_name: str) -> Dict[str, Dict[str, datetime | None]]:
        """Parse running workouts from export XML."""
        workouts: Dict[str, Dict[str, datetime | None]] = {}
        with self.zipfile.open(xml_name) as ef:
            it = iterparse(ef, events=("end",))
            idx = 0
            for _, elem in it:
                if elem.tag.split("}")[-1] == "Workout":
                    if elem.get("workoutActivityType") == "HKWorkoutActivityTypeRunning":
                        sdt, edt = self._parse_workout_times(elem)
                        workouts[f"wk_{idx}"] = {"start": sdt, "end": edt}
                        idx += 1
                elem.clear()
        return workouts

    def _parse_route_times(self, elem: Any) -> Tuple[datetime | None, datetime | None]:
        """Extract start and end times from route element."""
        rstart = elem.get("startDate") or elem.get("creationDate") or None
        rend = elem.get("endDate") or None
        try:
            rstart_dt = parse_timestamp(rstart) if rstart else None
        except (ValueError, TypeError):
            rstart_dt = None
        try:
            rend_dt = parse_timestamp(rend) if rend else None
        except (ValueError, TypeError):
            rend_dt = None
        return rstart_dt, rend_dt

    def _extract_file_paths(self, elem: Any) -> List[str]:
        """Extract file paths from route element."""
        paths: List[str] = []
        for fr in elem.iter():
            if fr.tag.split("}")[-1] == "FileReference":
                path = fr.get("path") or fr.text
                if path:
                    paths.append(path)
        return paths

    def collect_routes(
        self, xml_name: str
    ) -> List[Tuple[datetime | None, datetime | None, List[str]]]:
        """Parse workout routes from export XML."""
        routes: List[Tuple[datetime | None, datetime | None, List[str]]] = []
        with self.zipfile.open(xml_name) as ef:
            it = iterparse(ef, events=("end",))
            for _, elem in it:
                if elem.tag.split("}")[-1] == "WorkoutRoute":
                    rstart_dt, rend_dt = self._parse_route_times(elem)
                    paths = self._extract_file_paths(elem)
                    if paths:
                        routes.append((rstart_dt, rend_dt, paths))
                elem.clear()
        return routes

    def _parse_route_from_text(
        self, opening: str, body: str
    ) -> Tuple[datetime | None, datetime | None, List[str]] | None:
        """Parse a single route from text match."""
        def find_attr(s: str, name: str) -> str | None:
            p = re.search(rf'{name}="([^"]+)"', s)
            return p.group(1) if p else None

        rstart = find_attr(opening, "startDate") or find_attr(opening, "creationDate")
        rend = find_attr(opening, "endDate")
        try:
            rstart_dt = parse_timestamp(rstart) if rstart else None
        except (ValueError, TypeError):
            rstart_dt = None
        try:
            rend_dt = parse_timestamp(rend) if rend else None
        except (ValueError, TypeError):
            rend_dt = None
        paths = re.findall(r'<FileReference[^>]*path="([^"]+)"', body)
        if paths:
            return (rstart_dt, rend_dt, paths)
        return None

    def collect_routes_fallback(
        self, xml_name: str
    ) -> List[Tuple[datetime | None, datetime | None, List[str]]]:
        """Fallback text-based route parsing."""
        routes: List[Tuple[datetime | None, datetime | None, List[str]]] = []
        try:
            data = self.zipfile.read(xml_name).decode("utf-8", errors="ignore")
            pattern = re.compile(
                r"<WorkoutRoute([^>]*)>(.*?)</WorkoutRoute>", re.DOTALL
            )
            for m in pattern.finditer(data):
                route = self._parse_route_from_text(m.group(1), m.group(2))
                if route:
                    routes.append(route)
        except (UnicodeDecodeError, AttributeError):
            pass
        return routes

    def resolve_zip_path(self, ref_path: str) -> str | None:
        """Try several path variants to match FileReference inside ZIP."""
        if not ref_path:
            return None
        candidates: List[str] = [
            ref_path,
            ref_path.lstrip("/"),
            "/" + ref_path if not ref_path.startswith("/") else ref_path,
        ]
        if not ref_path.startswith("apple_health_export"):
            p = ref_path.lstrip("/")
            candidates.extend([
                "apple_health_export/" + p,
                "apple_health_export" + ref_path,
            ])
        for c in candidates:
            if c in self.zipfile.namelist():
                return c
        return None


def _time_ranges_overlap(
    a_s: datetime | None,
    a_e: datetime | None,
    b_s: datetime | None,
    b_e: datetime | None,
) -> bool:
    """Check if two time ranges overlap."""
    if a_s is None or a_e is None or b_s is None or b_e is None:
        return False
    latest_start = a_s if a_s > b_s else b_s
    earliest_end = a_e if a_e < b_e else b_e
    return latest_start <= earliest_end


def _add_route_to_matching_workouts(
    rstart: datetime | None,
    rend: datetime | None,
    paths: List[str],
    workouts: Dict[str, Dict[str, datetime | None]],
    workout_to_files: defaultdict[str, set[str]],
) -> None:
    """Add route paths to all workouts that overlap in time."""
    for wid, w in workouts.items():
        if _time_ranges_overlap(rstart, rend, w.get("start"), w.get("end")):
            for p in paths:
                workout_to_files[wid].add(p)


def match_routes_to_workouts(
    routes: List[Tuple[datetime | None, datetime | None, List[str]]],
    workouts: Dict[str, Dict[str, datetime | None]],
) -> defaultdict[str, set[str]]:
    """Match route files to workouts by time overlap."""
    workout_to_files: defaultdict[str, set[str]] = defaultdict(set)
    for rstart, rend, paths in routes:
        _add_route_to_matching_workouts(
            rstart, rend, paths, workouts, workout_to_files
        )
    return workout_to_files
