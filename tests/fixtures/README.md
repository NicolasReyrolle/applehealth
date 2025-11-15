# Test Fixtures

This directory contains test data files used for integration testing.

## export_sample.zip

A lightweight subset of the full Apple Health export designed for faster integration testing.

**Size**: ~94 MB (vs. ~192 MB for full export)
**Contains**: 
- Main `apple_health_export/export.xml` with all workout metadata
- 10 selected GPX route files covering various dates and distances

**Routes Included**:
- `route_2022-09-18_5.44pm.gpx` (3090 KB) - Long route
- `route_2024-08-08_8.56pm.gpx` (958 KB)
- `route_2025-02-20_8.00pm.gpx` (328 KB)
- `route_2024-11-26_6.25pm.gpx` (18 KB) - Short route
- `route_2025-02-11_6.47pm.gpx` (183 KB)
- `route_2025-02-20_8.53pm.gpx` (75 KB)
- `route_2020-10-25_1.45pm.gpx` (1714 KB) - Very long route
- `route_2024-03-18_7.04pm.gpx` (555 KB)
- `route_2024-09-22_6.44pm.gpx` (21 KB) - Short route
- `route_2019-08-21_4.20pm.gpx` (295 KB)

## Test Execution Times

- **All unit tests**: ~0.3 seconds (31 tests)
- **Mock integration tests**: ~0.1 seconds (5 tests)
- **Real export integration tests**: ~18-20 minutes (10 tests)
  - Uses `export_sample.zip` for ~55x faster execution vs full export
  - Each test processes the sample to validate real-world scenarios

## Running Tests

```bash
# Run only quick tests (skip real export integration)
pytest tests/test_apple_health_segments.py -k "not TestRealExportIntegration" -v

# Run only real export integration tests with sample
pytest tests/test_apple_health_segments.py::TestRealExportIntegration -v

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=tools --cov-report=html
```

## Creating/Updating the Sample

If you need to regenerate `export_sample.zip` with different routes:

```bash
python create_test_subset.py
```

This script extracts the first 10 route files from your full export and creates a new sample zip. Edit the script to select different routes or adjust the count.
