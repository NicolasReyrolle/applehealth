# Apple Health Segments

Find your fastest running segments for any distance from your Apple Health export.

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/b02a0df8d6ce4926bcd13468bdb8484d)](https://app.codacy.com/gh/NicolasReyrolle/applehealth/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![codecov](https://codecov.io/gh/NicolasReyrolle/applehealth/graph/badge.svg?token=xlwtapQwu8)](https://codecov.io/gh/NicolasReyrolle/applehealth)

## Quick Start

```powershell
# Install dependencies
python -m pip install -r tools/requirements.txt

# Find fastest segments
python tools/apple_health_segments.py --zip "path\to\export.zip" --top 5
```

## Documentation

### User Guide
- **[tools/README.md](tools/README.md)** - Complete CLI documentation
  - Installation & setup
  - Command-line options
  - Algorithm explanation
  - GPS error handling
  - Examples and troubleshooting

### Testing
- **[TESTING.md](TESTING.md)** - How to run tests
  - Test commands
  - Coverage reports
  - Test structure overview

- **[TEST_SUMMARY.md](TEST_SUMMARY.md)** - Implementation details
  - 44 tests covering all major functionality
  - 64% code coverage of main tool
  - Test design and organization

## Features

✅ **Penalty-based outlier handling** - Instead of dropping bad GPS data, demote suspect segments

✅ **Date range filtering** - Analyze specific time periods (e.g., 2024 only)

✅ **Verbose penalty reporting** - See which data points triggered speed anomalies

✅ **File output** - Save results and penalties to text files

✅ **Memory efficient** - Streams large exports without loading into RAM

✅ **Format support** - Apple Health Route XML and GPX files

## Example Usage

### Find your fastest 5km times in 2024
```powershell
python tools/apple_health_segments.py `
  --zip "path\to\export.zip" `
  --distances 5000 `
  --top 5 `
  --start-date 20240101 `
  --end-date 20241231
```

### Analyze GPS issues on a specific date
```powershell
python tools/apple_health_segments.py `
  --zip "path\to\export.zip" `
  --distances 400 1000 `
  --verbose `
  --penalty-file gps_issues.txt `
  --start-date 20240101 `
  --end-date 20240101
```

### See all command options
```powershell
python tools/apple_health_segments.py --help
```

## Project Structure

```
applehealth/
├── tools/
│   ├── apple_health_segments.py    # Main CLI tool (439 lines)
│   ├── points_on_date.py           # Extract points utility
│   ├── compute_speed_stats.py      # Speed analysis utility
│   ├── requirements.txt            # Dependencies
│   └── README.md                   # User documentation
├── tests/
│   └── test_apple_health_segments.py  # 44 comprehensive tests
├── TESTING.md                      # Testing guide
├── TEST_SUMMARY.md                 # Test implementation details
└── README.md                       # This file
```

## Testing

Run all tests:
```powershell
python -m pytest tests/ -v
```

Generate coverage report:
```powershell
python -m pytest tests/ -v --cov=tools --cov-report=html
```

### Test Summary
- **44 tests** passing
- **64% code coverage** of main tool
- **9 test classes** covering:
  - Unit tests (distance, timestamps, formatting)
  - Integration tests (export processing, date filtering)
  - Edge cases (empty data, invalid input)

## Core Algorithm

The tool uses a **two-pointer sliding window** to find the fastest segments:

1. For each target distance (e.g., 400m)
2. Find consecutive GPS points covering that distance
3. Calculate adjusted duration accounting for GPS errors
4. Rank by adjusted duration (fastest first)
5. Return top N results

### GPS Error Handling

GPS receivers sometimes produce erratic readings (especially in urban areas). Instead of discarding these segments:

- Flag suspect intervals (speed > 20 km/h by default)
- Add penalty seconds to their duration
- Keep them in results but rank them lower
- Show warnings with `--verbose` flag

**Example:**
- Clean segment: 400m in 100s → Rank: 100s ⭐
- Segment with spike: 400m in 103s adjusted → Rank: 103s (slower)
- Normal segment: 400m in 96s → Rank: 96s (fastest) 🏃

## Performance

- **Memory**: Streams exports without loading into RAM
- **Speed**: ~0.5s for small exports, scales linearly
- **Accuracy**: Haversine formula with ±0.1% precision

## Command Reference

See [tools/README.md](tools/README.md) for complete documentation.

Key parameters:
- `--zip PATH` - Export file (required)
- `--top N` - Number of results per distance (default: 5)
- `--distances D1 D2 ...` - Target distances in meters
- `--max-speed KM/H` - Speed threshold for penalties (default: 20.0)
- `--verbose` - Show GPS anomaly warnings
- `--start-date YYYYMMDD` - Filter by date range
- `--end-date YYYYMMDD`

## Troubleshooting

**No segments found?**
- Check export.zip contains running workouts with routes
- Verify distances are in meters (1000 = 1km)
- Check date filters if using --start-date/--end-date

**Unrealistic speeds?**
- Lower `--max-speed` (e.g., 15 km/h)
- Use `--verbose` to see flagged intervals
- Increase `--speed-penalty` to demote these segments further

**Performance issues?**
- Use `--no-progress` to skip progress bar
- Filter by date range to reduce workouts processed
- Ensure export.zip is on local fast storage (SSD)

## Dependencies

- `python-dateutil` - Flexible timestamp parsing
- `tqdm` - Progress bars
- `pytest` - Testing (optional, for running tests)
- `pytest-cov` - Coverage reporting (optional)

## License

For personal use. See repository for details.

## Support

- Check [tools/README.md](tools/README.md) for usage details
- See [TESTING.md](TESTING.md) for running tests
- Review [TEST_SUMMARY.md](TEST_SUMMARY.md) for test coverage info

