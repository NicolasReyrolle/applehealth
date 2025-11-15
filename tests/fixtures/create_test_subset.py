#!/usr/bin/env python3
"""CLI to create a filtered subset of an Apple Health export.zip for tests.

Usage:
  python create_test_subset.py --source /path/to/export.zip --out ./export_sample.zip --max-routes 50

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


def parse_dt(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        try:
            return datetime.strptime(s, '%Y-%m-%d %H:%M:%S %z')
        except Exception:
            return None


def overlap(a_s, a_e, b_s, b_e):
    if a_s is None or a_e is None or b_s is None or b_e is None:
        return False
    latest_start = a_s if a_s > b_s else b_s
    earliest_end = a_e if a_e < b_e else b_e
    return latest_start <= earliest_end


def create_subset(export_path, output_path, max_routes=50):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if not os.path.exists(export_path):
        raise FileNotFoundError(export_path)

    with zipfile.ZipFile(export_path, 'r') as z_in:
        all_files = z_in.namelist()

        # locate export xml
        export_xml_name = next((n for n in all_files if 'export' in n.lower() and n.lower().endswith('.xml')), None)
        if not export_xml_name:
            raise RuntimeError('Could not find export.xml in the archive')

        export_xml_data = z_in.read(export_xml_name)

        # Heuristic: prefer route files whose basenames appear in the export.xml
        export_text = ''
        try:
            export_text = export_xml_data.decode('utf-8', errors='ignore')
        except Exception:
            export_text = ''

        candidates = [f for f in all_files if f.lower().endswith(('.gpx', '.xml'))]
        resolved = []
        for fpath in candidates:
            b = os.path.basename(fpath)
            if not b:
                continue
            # check various ways the basename might appear in the export XML
            if (b in export_text) or (('/' + b) in export_text) or (('workout-routes/' + b) in export_text):
                resolved.append(fpath)
            if len(resolved) >= max_routes:
                break

        if resolved:
            selected_routes = resolved[:max_routes]
        else:
            # fallback: choose any route-like files
            route_files = [f for f in all_files if ('workout-routes' in f.lower() or 'route' in f.lower()) and f.lower().endswith(('.gpx', '.xml'))]
            if not route_files:
                route_files = candidates
            selected_routes = route_files[:max_routes]

        selected_set = set(selected_routes)

        workouts = []
        workout_routes = []

        # parse iteratively and collect only the elements we may need
        it = ET.iterparse(BytesIO(export_xml_data), events=('end',))
        for _, elem in it:
            tag = elem.tag.split('}')[-1]
            if tag == 'Workout':
                wtype = elem.get('workoutActivityType')
                if wtype == 'HKWorkoutActivityTypeRunning':
                    s = elem.get('startDate') or elem.get('creationDate') or elem.get('start')
                    e = elem.get('endDate') or elem.get('end')
                    sdt = parse_dt(s) if s else None
                    edt = parse_dt(e) if e else None
                    workouts.append((ET.tostring(elem, encoding='utf-8'), sdt, edt))
                elem.clear()
            elif tag == 'WorkoutRoute':
                paths = []
                rstart = elem.get('startDate') or elem.get('creationDate') or None
                rend = elem.get('endDate') or None
                rstart_dt = parse_dt(rstart) if rstart else None
                rend_dt = parse_dt(rend) if rend else None
                for fr in elem.iter():
                    if fr.tag.split('}')[-1] == 'FileReference':
                        path = fr.get('path') or fr.text
                        if path:
                            paths.append(path)
                matched = False
                # also match by basename to be resilient to path differences
                selected_basenames = {os.path.basename(r) for r in selected_routes}
                for p in paths:
                    p_norm = p.lstrip('/') if isinstance(p, str) else p
                    if (p in selected_set
                        or p_norm in selected_set
                        or ('apple_health_export/' + p_norm) in selected_set
                        or os.path.basename(p_norm) in selected_basenames):
                        matched = True
                        break
                if matched:
                    workout_routes.append((ET.tostring(elem, encoding='utf-8'), paths, rstart_dt, rend_dt))
                elem.clear()
            else:
                elem.clear()

        # choose workouts that overlap the selected routes
        selected_workouts_bytes = []
        for w_bytes, w_s, w_e in workouts:
            keep = False
            for _, _, r_s, r_e in workout_routes:
                if overlap(w_s, w_e, r_s, r_e):
                    keep = True
                    break
            if keep:
                selected_workouts_bytes.append(w_bytes)

        # build filtered export.xml root
        new_root = ET.Element('Export')
        for wb in selected_workouts_bytes:
            try:
                el = ET.fromstring(wb)
                new_root.append(el)
            except Exception:
                continue
        for rb, paths, r_s, r_e in workout_routes:
            try:
                el = ET.fromstring(rb)
                new_root.append(el)
            except Exception:
                continue

        new_export_bytes = ET.tostring(new_root, encoding='utf-8', xml_declaration=True)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z_out:
            z_out.writestr(export_xml_name, new_export_bytes)
            for route in selected_routes:
                try:
                    data = z_in.read(route)
                    z_out.writestr(route, data)
                except Exception:
                    continue

    return output_path


def main():
    p = argparse.ArgumentParser(description='Create filtered Apple Health export subset for tests')
    p.add_argument('--source', '-s', required=True, help='Path to full export.zip')
    p.add_argument('--out', '-o', required=True, help='Output path for filtered subset zip')
    p.add_argument('--max-routes', type=int, default=50, help='Maximum number of route files to include')
    args = p.parse_args()

    out = create_subset(args.source, args.out, max_routes=args.max_routes)
    print(f'Wrote subset: {out}')


if __name__ == '__main__':
    main()
