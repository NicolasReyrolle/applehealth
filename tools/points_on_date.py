#!/usr/bin/env python3
"""Extract all GPX points from an Apple Health export for a specific date.

Usage: python tools/points_on_date.py --zip /path/to/export.zip --date YYYY-MM-DD

Prints CSV-like lines: timestamp, duration_since_prev_s, distance_m, speed_kmh
"""
import argparse
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timezone
from dateutil import parser as dateparser
import math


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def parse_gpx_points(gpx_bytes):
    # parse GPX and yield (timestamp(datetime), lat(float), lon(float)) for each trkpt
    it = ET.iterparse(BytesIO(gpx_bytes))
    for _, elem in it:
        tag = elem.tag
        if tag.endswith('trkpt'):
            lat = float(elem.attrib.get('lat'))
            lon = float(elem.attrib.get('lon'))
            # find time child
            time_elem = None
            for child in elem:
                if child.tag.endswith('time'):
                    time_elem = child
                    break
            if time_elem is None:
                elem.clear()
                continue
            try:
                ts = dateparser.parse(time_elem.text)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                elem.clear()
                continue
            yield ts, lat, lon
            elem.clear()


def find_gpx_files_for_date(zip_path, target_date):
    # returns list of (name, bytes)
    found = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        for info in z.infolist():
            name = info.filename
            if not name.lower().endswith('.gpx'):
                continue
            data = z.read(name)
            # quick check: if the file contains the target date string, include it
            if target_date.encode('utf-8') in data:
                found.append((name, data))
            else:
                # still attempt parsing to be safe
                if target_date in str(data):
                    found.append((name, data))
    return found


def extract_points_for_date(zip_path, date_str):
    target_date = date_str
    files = find_gpx_files_for_date(zip_path, target_date)
    all_points = []
    for name, data in files:
        for ts, lat, lon in parse_gpx_points(data):
            if ts.date().isoformat() == date_str:
                all_points.append((ts, lat, lon, name))
    # sort by timestamp
    all_points.sort(key=lambda x: x[0])
    return all_points


def format_point_lines(points):
    lines = []
    prev_ts = None
    prev_lat = None
    prev_lon = None
    for ts, lat, lon, fname in points:
        if prev_ts is None:
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
        lines.append((ts.isoformat(), f"{dur:.2f}", f"{dist:.2f}", f"{speed:.2f}", fname))
        prev_ts = ts
        prev_lat = lat
        prev_lon = lon
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', required=True, help='Path to Apple Health export.zip')
    parser.add_argument('--date', required=True, help='Date in YYYY-MM-DD')
    args = parser.parse_args()
    pts = extract_points_for_date(args.zip, args.date)
    if not pts:
        print(f"No GPX points found for {args.date}")
        return
    lines = format_point_lines(pts)
    # print header
    print('timestamp,duration_s,distance_m,speed_kmh,source_file')
    for t, dur, dist, speed, fname in lines:
        print(f"{t},{dur},{dist},{speed},{fname}")


if __name__ == '__main__':
    main()
