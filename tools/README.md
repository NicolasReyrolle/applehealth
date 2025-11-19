# Apple Health Segments CLI

Find your fastest running segments for any distance from an Apple Health export.

## Overview

This tool scans your Apple Health `export.zip` and identifies the top-N fastest segments for target distances (default: 400m, 800m, 1km, 5km, 10km, 15km, 20km, Half Marathon, Marathon).

**Key Features:**

- ✅ Penalty-based outlier handling (instead of dropping bad GPS data)
- ✅ Date range filtering (analyze specific time periods)
- ✅ Verbose penalty reporting (see which data points were flagged)
- ✅ File output (save results and penalty warnings to text files)
- ✅ Memory-efficient streaming (processes large exports without loading into RAM)
- ✅ GPS format support: Apple Health XML Routes and GPX files
- ✅ **Performance trend estimation** (predict optimal times based on recent workouts)

## Installation

```powershell
# Create and activate a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r .\tools\requirements.txt
```

## Quick Start

```powershell
# Find top 5 fastest segments for all default distances
python .\tools\apple_health_segments.py --zip "path\to\export.zip"

# Find top 3 fastest 400m and 1km segments
python .\tools\apple_health_segments.py --zip "path\to\export.zip" --top 3 --distances 400 1000

# Show penalty warnings and save to file
python .\tools\apple_health_segments.py --zip "path\to\export.zip" --verbose --penalty-file penalties.txt

# Filter results to a specific date range
python .\tools\apple_health_segments.py --zip "path\to\export.zip" --start-date 20240101 --end-date 20241231
```

## Command-Line Options

```bash
--zip PATH                      Path to export.zip (required)
--top N                         Number of top segments per distance (default: 5)
--distances D1 D2 ...          Target distances in meters
                                (default: 400 800 1000 5000 10000 15000 20000 21097.5 42195)
--max-speed KMH                 Speed threshold in km/h (default: 20.0)
                                Intervals exceeding this are penalized, not filtered
--speed-penalty SECONDS         Penalty duration in seconds (default: 3.0)
                                Added to any interval exceeding --max-speed
--verbose                       Show all penalty warnings for GPS anomalies
--penalty-file PATH             Write penalty warnings to file (requires --verbose)
--output-file PATH, -o PATH     Write results to text file (in addition to stdout)
--start-date YYYYMMDD          Start of date range (inclusive)
--end-date YYYYMMDD            End of date range (inclusive)
--progress / --no-progress      Show/hide progress bar (default: enabled)
--show-estimation /             Show/hide estimated optimal time based on recent
--no-estimation                 performance trends (default: enabled)
--debug                         Show debug information
```

## How It Works

### Segment Detection Algorithm

The tool uses a **two-pointer sliding window** algorithm:

1. **For each distance target** (e.g., 400m), scan all GPX points in all workouts
2. **Find the consecutive points** that cover ~400m in the shortest time
3. **Calculate "adjusted duration"** which accounts for GPS errors:

   - Normal intervals: use actual time delta
   - High-speed intervals (> --max-speed): add penalty seconds
   - Infinite-speed intervals (zero duration, nonzero distance): skip penalty

4. **Rank segments** by adjusted duration (fastest first)
5. **Return top N** results

### GPS Error Handling (Penalty System)

GPS receivers can produce occasional erratic readings, especially in urban canyons or tunnels.
Without correction, these create unrealistic speeds (e.g., 100+ km/h on a run).

**Old approach (hard filtering):** Drop any segment with an anomalous interval → Lost valid segments.

**New approach (penalty-based):** Keep the segment but add penalty seconds to demote it in ranking:

- Interval speed > 20 km/h? → Add 3 seconds to its duration
- This keeps outliers in the results but ranks them lower
- You can see exactly which data points were flagged with `--verbose`

**Example:**

- Segment with all normal points: 400m in 100s → Rank: 100s
- Segment with one 40 km/h spike (penalty +3s): 400m in 103s adjusted → Rank: 103s (lower rank)
- Segment with all 15 km/h points: 400m in 96s → Rank: 96s (fastest)

### Parameter Tuning

#### --max-speed (default: 20.0 km/h)

- Your average running speed: probably 8-12 km/h
- Outliers are typically 2-5x faster
- Default of 20 km/h catches ~1% of intervals (reasonable for urban running with traffic signals)

#### --speed-penalty (default: 3.0 seconds)

- How much to demote a segment with anomalies
- 3 seconds ≈ 0.5m at race pace (minimal impact on ranking)
- Increase if you want to ignore segments with any GPS errors

## Performance Trend Estimation

The tool can predict your **optimal achievable time** for each distance based on recent workout performance. This uses an ensemble of estimation methods to give you a realistic target based on your actual running patterns.

### Estimation Strategy

The estimation analyzes your fastest recent times and extrapolates using three strategies:

1. **Percentile-based** (50th percentile) - Uses your median recent performance
2. **Weighted recent average** - Emphasizes more recent workouts (exponential decay over 30 days)
3. **Speed-based projection** - Extrapolates your average recent pace to the target distance

The final estimate is the **average of these three methods**, giving a balanced prediction that accounts for:

- Recent training progress and trends
- Variable performance across different conditions
- Realistic expectations vs. one-off great days

### Example Output

```text
Distance: 5 km
  Estimated optimal:  00:25:15  (steady improvement)
    1. 08/08/2024  00:25:30
    2. 24/04/2025  00:25:45
    3. 30/03/2025  00:26:02
```

The "Estimated optimal" line shows:

- **Time**: Predicted best time you could achieve based on recent form
- **Confidence**: How strong the trend is
  - "flat/recovery trend" - No improvement visible (relax, it's normal)
  - "modest improvement" - Slight positive trend
  - "steady improvement" - Consistent gains (training is working!)
  - "strong upward trend" - Major improvements (excellent progress)

### Disabling Estimation

If you prefer to see just the actual segments without predictions:

```powershell
python .\tools\apple_health_segments.py --zip "export.zip" --no-estimation
```

### Quality of Estimation

The estimation is most accurate when you have:

- **At least 5-10 recent runs** of the same distance
- **Consistent training** (not long breaks)
- **Recent data** (within 1-3 months)
- **Minimal GPS errors** (results already filtered by the penalty system)

With fewer runs or inconsistent data, the tool may show "unable to estimate" – that's normal and doesn't affect the actual segment rankings.

## Output Format

### Results

```text
Distance: 400 m
   1. 08/08/2024  00:01:51
   2. 24/04/2025  00:01:52
   3. 30/03/2025  00:01:56
```

Shows: rank, date (DD/MM/YYYY), and segment duration (HH:MM:SS).

### Penalty Warnings (with --verbose)

```text
=== PENALTY WARNINGS ===
01/01/2024 14:27:58 | interval 0->1 | 1.00s | 81.6 km/h
04/02/2024 14:18:33 | interval 2->3 | 1.00s | 102.3 km/h
```

Shows: timestamp (DD/MM/YYYY HH:MM:SS), interval indices, duration, and instantaneous speed.
Entries are sorted chronologically and deduplicated by data point.

## Files

- **apple_health_segments.py** – Main CLI tool
- **points_on_date.py** – Utility to extract all GPS points from a specific date (CSV format)
- **compute_speed_stats.py** – Utility to analyze speed distribution for parameter tuning
- **requirements.txt** – Python dependencies
- **README.md** – This file

## Examples

### Find your fastest 5km times in 2024

```powershell
python .\tools\apple_health_segments.py `
  --zip "path\to\export.zip" `
  --distances 5000 `
  --top 5 `
  --start-date 20240101 `
  --end-date 20241231
```

### Analyze a specific date with GPS details

```powershell
python .\tools\apple_health_segments.py `
  --zip "path\to\export.zip" `
  --distances 400 1000 `
  --verbose `
  --penalty-file gps_issues_20240101.txt `
  --start-date 20240101 `
  --end-date 20240101
```

### Extract all points from a specific date

```powershell
python .\tools\points_on_date.py `
  --zip "path\to\export.zip" `
  --date 2024-01-01
```

Output: CSV with timestamp, duration since previous point, distance, and speed for each GPS point.

## Technical Details

### Supported Formats

- **Apple Health Route XML** with `<Location>` tags (latitude, longitude, timestamp attributes)
- **GPX 1.0/1.1** with `<trkpt>` entries and `<time>` child elements
- Namespace-agnostic parsing (handles variants from different export tools)

### Streaming Architecture

- Reads `export.xml` once to enumerate workouts and route files
- Processes each route file individually, then discards (memory-efficient)
- Suitable for multi-GB exports

### Date Handling

- Inclusive on both ends: `--start-date 20240101 --end-date 20240131` = January 2024 only
- Uses workout start date for filtering
- Timestamps parsed via `python-dateutil` (supports ISO 8601, Apple formats, etc.)

### Time Zone Handling

- Respects timezone info in GPX/XML timestamps
- Comparisons are timezone-aware
- Output times are in the original timezone

## Troubleshooting

**No segments found?**

- Check that your export.zip contains running workouts with route files
- Verify distances are in meters (e.g., 1000 for 1km, not 1)
- Check date range filters if using --start-date/--end-date

**Unrealistic speeds in penalties?**

- Lower --max-speed to be more strict (e.g., 15 km/h)
- Increase --speed-penalty to rank these segments lower
- Use --verbose to see all flagged intervals

**Performance issues with large exports?**

- Use --no-progress to disable progress bar (slight speedup)
- Filter by date range (--start-date, --end-date) to reduce workouts processed
- Ensure export.zip is on local SSD, not network drive
