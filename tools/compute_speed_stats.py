#!/usr/bin/env python3
"""Compute simple statistics from tools/points_2021-12-26.csv

Prints count, min, max, mean, median and percentiles for instantaneous speed (km/h),
and counts of intervals exceeding candidate thresholds.
"""
import csv
import math
from statistics import mean, median

CSV_PATH = 'tools/points_2021-12-26.csv'

def percentile(sorted_list, p):
    if not sorted_list:
        return None
    k = (p / 100.0) * (len(sorted_list) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_list[int(k)]
    d0 = sorted_list[f] * (c - k)
    d1 = sorted_list[c] * (k - f)
    return d0 + d1

def main():
    speeds = []
    durations = []
    rows = []
    with open(CSV_PATH, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            try:
                s = float(r.get('speed_kmh') or 0.0)
                d = float(r.get('duration_s') or 0.0)
            except Exception:
                continue
            speeds.append(s)
            durations.append(d)
            rows.append(r)

    if not speeds:
        print('No speed data found')
        return

    s_sorted = sorted(speeds)
    n = len(s_sorted)
    print(f"Total intervals: {n}")
    print(f"Min speed: {s_sorted[0]:.2f} km/h")
    print(f"Max speed: {s_sorted[-1]:.2f} km/h")
    print(f"Mean speed: {mean(s_sorted):.2f} km/h")
    print(f"Median speed: {median(s_sorted):.2f} km/h")
    for p in (90, 95, 99, 99.9):
        v = percentile(s_sorted, p)
        print(f"P{p}: {v:.2f} km/h")

    thresholds = [20, 25, 30, 35, 40, 50]
    for t in thresholds:
        cnt = sum(1 for x in speeds if x > t)
        pct = cnt / n * 100.0
        print(f"> {t} km/h: {cnt} intervals ({pct:.3f}%)")

    # durations for intervals > 35 km/h
    over35 = [durations[i] for i, x in enumerate(speeds) if x > 35]
    if over35:
        print(f"Intervals >35 km/h: count={len(over35)}, mean duration={mean(over35):.2f}s, max={max(over35):.2f}s")
    else:
        print("No intervals >35 km/h found")

    # show top 10 speeds with timestamp and source
    top = sorted(zip(speeds, rows), key=lambda x: x[0], reverse=True)[:10]
    print('\nTop 10 intervals by instantaneous speed:')
    print('speed_kmh,duration_s,timestamp,source_file')
    for s, r in top:
        print(f"{s:.2f},{r.get('duration_s')},{r.get('timestamp')},{r.get('source_file')}")

if __name__ == '__main__':
    main()
