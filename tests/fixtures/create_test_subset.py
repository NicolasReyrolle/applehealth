#!/usr/bin/env python3
"""CLI to create a filtered subset of an Apple Health export.zip for tests.

Usage:
  python create_test_subset.py --source /path/to/export.zip 
    --out ./export_sample.zip --max-routes 50

The script writes a new ZIP containing:
 - the filtered `export.xml` (only Workout and WorkoutRoute elements related to included routes)
 - the selected route files (GPX/XML)

This file is intentionally located in `tests/fixtures` to be available for CI and local dev.
"""

import argparse
import zipfile
import os
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime
from typing import List, Tuple


def parse_dt(s: str) -> datetime | None:
    """Parse datetime string with fallback formats."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
        except (ValueError, TypeError):
            return None


def overlap(
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


def _find_export_xml(all_files: List[str]) -> str:
    """Find export XML file in archive."""
    export_xml_name = next(
        (n for n in all_files if "export" in n.lower() and n.lower().endswith(".xml")),
        None,
    )
    if not export_xml_name:
        raise RuntimeError("Could not find export.xml in the archive")
    return export_xml_name


def _is_route_file(filename: str) -> bool:
    """Check if file is a route file."""
    return filename.lower().endswith((".gpx", ".xml"))


def _is_basename_in_export(basename: str, export_text: str) -> bool:
    """Check if basename appears in export text."""
    return (
        basename in export_text
        or ("/" + basename) in export_text
        or ("workout-routes/" + basename) in export_text
    )


def _find_referenced_routes(
    candidates: List[str], export_text: str, max_routes: int
) -> List[str]:
    """Find routes referenced in export XML."""
    resolved: List[str] = []
    for fpath in candidates:
        basename = os.path.basename(fpath)
        if basename and _is_basename_in_export(basename, export_text):
            resolved.append(fpath)
            if len(resolved) >= max_routes:
                break
    return resolved


def _get_fallback_routes(
    all_files: List[str], candidates: List[str], max_routes: int
) -> List[str]:
    """Get fallback route files when no referenced routes found."""
    route_files = [
        f
        for f in all_files
        if ("workout-routes" in f.lower() or "route" in f.lower()) and _is_route_file(f)
    ]
    return (route_files or candidates)[:max_routes]


def _select_routes(
    all_files: List[str], export_text: str, max_routes: int
) -> List[str]:
    """Select route files based on export XML content."""
    candidates = [f for f in all_files if _is_route_file(f)]
    resolved = _find_referenced_routes(candidates, export_text, max_routes)

    if resolved:
        return resolved[:max_routes]

    return _get_fallback_routes(all_files, candidates, max_routes)


def _parse_workout_element(
    elem: ET.Element,
) -> Tuple[bytes, datetime | None, datetime | None] | None:
    """Parse workout element and return data tuple."""
    wtype = elem.get("workoutActivityType")
    if wtype != "HKWorkoutActivityTypeRunning":
        return None

    s = elem.get("startDate") or elem.get("creationDate") or elem.get("start")
    e = elem.get("endDate") or elem.get("end")
    sdt = parse_dt(s) if s else None
    edt = parse_dt(e) if e else None
    return (ET.tostring(elem, encoding="utf-8"), sdt, edt)


def _extract_file_paths(elem: ET.Element) -> List[str]:
    """Extract file paths from route element."""
    paths: List[str] = []
    for fr in elem.iter():
        if fr.tag.split("}")[-1] == "FileReference":
            path: str | None = fr.get("path") or fr.text
            if path:
                paths.append(path)
    return paths


def _is_path_selected(
    path: str, selected_set: set[str], selected_basenames: set[str]
) -> bool:
    """Check if a path matches selected routes."""
    p_norm = path.lstrip("/")
    return (
        path in selected_set
        or p_norm in selected_set
        or ("apple_health_export/" + p_norm) in selected_set
        or os.path.basename(p_norm) in selected_basenames
    )


def _check_route_match(paths: List[str], selected_routes: List[str]) -> bool:
    """Check if any path in the route matches selected routes."""
    selected_set = set(selected_routes)
    selected_basenames = {os.path.basename(r) for r in selected_routes}

    for p in paths:
        if _is_path_selected(p, selected_set, selected_basenames):
            return True
    return False


def _parse_route_element(
    elem: ET.Element, selected_routes: List[str]
) -> Tuple[bytes, List[str], datetime | None, datetime | None] | None:
    """Parse route element and return data tuple if matched."""
    rstart = elem.get("startDate") or elem.get("creationDate") or None
    rend = elem.get("endDate") or None
    rstart_dt = parse_dt(rstart) if rstart else None
    rend_dt = parse_dt(rend) if rend else None

    paths = _extract_file_paths(elem)

    if _check_route_match(paths, selected_routes):
        return (ET.tostring(elem, encoding="utf-8"), paths, rstart_dt, rend_dt)

    return None


def _parse_export_xml(
    export_xml_data: bytes, selected_routes: List[str]
) -> Tuple[
    List[Tuple[bytes, datetime | None, datetime | None]],
    List[Tuple[bytes, List[str], datetime | None, datetime | None]],
]:
    """Parse export XML and extract workouts and routes."""
    workouts: List[Tuple[bytes, datetime | None, datetime | None]] = []
    workout_routes: List[Tuple[bytes, List[str], datetime | None, datetime | None]] = []

    it = ET.iterparse(BytesIO(export_xml_data), events=("end",))
    for _, elem in it:
        tag = elem.tag.split("}")[-1]
        if tag == "Workout":
            workout_data = _parse_workout_element(elem)
            if workout_data:
                workouts.append(workout_data)
        elif tag == "WorkoutRoute":
            route_data = _parse_route_element(elem, selected_routes)
            if route_data:
                workout_routes.append(route_data)
        elem.clear()

    return workouts, workout_routes


def _filter_overlapping_workouts(
    workouts: List[Tuple[bytes, datetime | None, datetime | None]],
    workout_routes: List[Tuple[bytes, List[str], datetime | None, datetime | None]],
) -> List[bytes]:
    """Filter workouts that overlap with selected routes."""
    selected_workouts_bytes: List[bytes] = []
    for w_bytes, w_s, w_e in workouts:
        for _, _, r_s, r_e in workout_routes:
            if overlap(w_s, w_e, r_s, r_e):
                selected_workouts_bytes.append(w_bytes)
                break
    return selected_workouts_bytes


def _build_filtered_xml(
    selected_workouts_bytes: List[bytes],
    workout_routes: List[Tuple[bytes, List[str], datetime | None, datetime | None]],
) -> bytes:
    """Build filtered export XML from selected elements."""
    new_root = ET.Element("Export")

    for wb in selected_workouts_bytes:
        try:
            el = ET.fromstring(wb)
            new_root.append(el)
        except ET.ParseError:
            continue

    for rb, _, _, _ in workout_routes:
        try:
            el = ET.fromstring(rb)
            new_root.append(el)
        except ET.ParseError:
            continue

    return ET.tostring(new_root, encoding="utf-8", xml_declaration=True)


def create_subset(export_path: str, output_path: str, max_routes: int = 50) -> str:
    """Create a filtered subset of an Apple Health export for testing."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if not os.path.exists(export_path):
        raise FileNotFoundError(export_path)

    with zipfile.ZipFile(export_path, "r") as z_in:
        all_files = z_in.namelist()
        export_xml_name = _find_export_xml(all_files)
        export_xml_data = z_in.read(export_xml_name)

        export_text = ""
        try:
            export_text = export_xml_data.decode("utf-8", errors="ignore")
        except (UnicodeDecodeError, AttributeError):
            export_text = ""

        selected_routes = _select_routes(all_files, export_text, max_routes)
        workouts, workout_routes = _parse_export_xml(export_xml_data, selected_routes)
        selected_workouts_bytes = _filter_overlapping_workouts(workouts, workout_routes)
        new_export_bytes = _build_filtered_xml(selected_workouts_bytes, workout_routes)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z_out:
            z_out.writestr(export_xml_name, new_export_bytes)
            for route in selected_routes:
                try:
                    data = z_in.read(route)
                    z_out.writestr(route, data)
                except (KeyError, zipfile.BadZipFile):
                    continue

    return output_path


def main():
    """Main entry point."""
    p = argparse.ArgumentParser(
        description="Create filtered Apple Health export subset for tests"
    )
    p.add_argument("--source", "-s", required=True, help="Path to full export.zip")
    p.add_argument(
        "--out", "-o", required=True, help="Output path for filtered subset zip"
    )
    p.add_argument(
        "--max-routes",
        type=int,
        default=50,
        help="Maximum number of route files to include",
    )
    args = p.parse_args()

    out = create_subset(args.source, args.out, max_routes=args.max_routes)
    print(f"Wrote subset: {out}")


if __name__ == "__main__":
    main()
