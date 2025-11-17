# Test Fixtures

This directory contains test data files used for integration testing.

## export_sample.zip

A lightweight subset of the full Apple Health export designed for faster integration testing.

**Size**: ~94 MB (vs. ~192 MB for full export)
**Contains**:

- Main `apple_health_export/export.xml` with all workout metadata
- 10 selected GPX route files covering various dates and distances

**Routes Included**:

- `route_2019-08-21_4.20pm.gpx` (295 KB) - Historical data
- `route_2020-10-25_1.45pm.gpx` (1714 KB) - Very long route
- `route_2022-09-18_5.44pm.gpx` (3090 KB) - Long route
- `route_2024-03-18_7.04pm.gpx` (555 KB)
- `route_2024-08-08_8.56pm.gpx` (958 KB)
- `route_2024-09-22_6.44pm.gpx` (21 KB) - Short route
- `route_2024-11-26_6.25pm.gpx` (18 KB) - Short route

## Current Test Status

- **44 tests** across 9 test classes
- **64% code coverage** of main tool
- **Test categories**:
  - Unit tests (distance calculations, timestamps, formatting)
  - Integration tests (export processing, date filtering)
  - Edge cases (empty data, invalid input)

## Test Execution Times

- **Quick tests**: ~0.4 seconds (unit + mock tests)
- **Integration tests**: Variable based on test data size
- Uses `export_sample.zip` for faster execution vs full export

## Running Tests

```powershell
# Run all tests
python -m pytest tests/ -v

# Generate coverage report
python -m pytest tests/ -v --cov=tools --cov-report=html

# Run specific test file
python -m pytest tests/test_apple_health_segments.py -v

# Run tests with pattern matching
python -m pytest tests/ -k "test_format" -v
```

## Creating/Updating the Sample

If you need to regenerate `export_sample.zip` with different routes:

```powershell
# Navigate to the tests/fixtures directory
cd tests\fixtures

# Run the script with your full export
python create_test_subset.py --source "path\to\your\export.zip" --out "export_sample.zip" --max-routes 10
```

The `create_test_subset.py` script is located in `tests/fixtures/` and extracts selected route files from your full export to create a new sample zip. Edit the script to select different routes or adjust the count as needed.
