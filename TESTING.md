# Testing Guide

Comprehensive unit and integration tests for the Apple Health segments tool.

## Setup

Install test dependencies:

```powershell
python -m pip install -r .\tools\requirements.txt
```

This installs:
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting

## Running Tests

### Run all tests
```powershell
python -m pytest tests/ -v
```

### Run specific test file
```powershell
python -m pytest tests/test_apple_health_segments.py -v
```

### Run specific test class
```powershell
python -m pytest tests/test_apple_health_segments.py::TestHaversineMeters -v
```

### Run specific test
```powershell
python -m pytest tests/test_apple_health_segments.py::TestHaversineMeters::test_haversine_zero_distance -v
```

## Coverage Reports

Generate coverage report in terminal:
```powershell
python -m pytest tests/ -v --cov=tools --cov-report=term-missing
```

Generate HTML coverage report:
```powershell
python -m pytest tests/ -v --cov=tools --cov-report=html
```

Then open `htmlcov/index.html` in a browser to see detailed coverage.

## Test Structure

### Unit Tests (25 tests)

#### `TestHaversineMeters` (5 tests)
- `test_haversine_zero_distance` - Same coordinates = ~0m
- `test_haversine_one_degree_latitude` - 1° latitude ≈ 111km
- `test_haversine_one_degree_longitude_at_equator` - 1° longitude ≈ 111km
- `test_haversine_known_distance` - Real-world distance validation
- `test_haversine_symmetry` - Distance A→B = B→A

#### `TestParseTimestamp` (5 tests)
- `test_parse_iso_format` - ISO 8601 timestamps
- `test_parse_apple_format` - Apple's format
- `test_parse_various_formats` - Mixed format tolerance
- `test_parse_empty_string_raises` - Error handling
- `test_parse_none_raises` - Null handling

#### `TestFormatDuration` (7 tests)
- `test_format_duration_zero` - 0s → "00:00:00"
- `test_format_duration_seconds_only` - 45s → "00:00:45"
- `test_format_duration_minutes` - 125s → "00:02:05"
- `test_format_duration_hours` - 3665s → "01:01:05"
- `test_format_duration_rounding` - Rounding behavior
- `test_format_duration_infinity` - ∞ → "-"
- `test_format_duration_none` - None → "-"

#### `TestFormatDistance` (6 tests)
- `test_format_distance_meters` - <1000m format
- `test_format_distance_kilometers` - Round km format
- `test_format_distance_decimal_kilometers` - Decimal km format
- `test_format_distance_half_marathon` - 21097.5m label
- `test_format_distance_marathon` - 42195m label
- `test_format_distance_none` - None handling

#### `TestStreamPointsFromRoute` (3 tests)
- `test_stream_gpx_points` - Extract GPX points
- `test_stream_empty_route` - Handle empty routes
- `test_stream_invalid_xml` - Handle invalid XML

#### `TestDateFiltering` (3 tests)
- `test_date_before_range` - Exclude pre-range
- `test_date_within_range` - Include in-range
- `test_date_after_range` - Exclude post-range

### Integration Tests (4 tests)

#### `TestBestSegmentForDist` (6 tests)
- `test_segment_with_enough_points` - Basic segment finding
- `test_segment_ordering` - Chronological order
- `test_segment_unrealistic_distance` - Unrealistic distance handling
- `test_segment_empty_points` - Empty points handling
- `test_segment_penalty_applied` - Penalty mechanism
- `test_segment_debug_info` - Debug information

#### `TestIntegrationWithMockExport` (4 tests)
- `test_process_export_finds_segments` - Mock export processing
- `test_process_export_with_date_filter` - Date filtering
- `test_process_export_within_date_range` - Date range inclusion
- `test_process_export_returns_penalty_messages` - Penalty collection
- `test_process_export_returns_tuple` - Return value structure

### Edge Cases (5 tests)

#### `TestEdgeCases` (5 tests)
- `test_zero_distance_target` - Handle 0m gracefully
- `test_negative_distance_target` - Handle negative distances
- `test_single_point` - Single point handling
- `test_two_identical_points` - Duplicate points handling

## Test Fixtures

### `simple_points`
Creates 100 points in a straight line at equator, 10 seconds apart.

### `mock_gpx_content`
Minimal valid GPX file with 5 track points.

### `mock_export_zip`
Complete mock Apple Health export.zip with:
- `export.xml` with one running workout
- One GPX file with 5 track points

## Key Testing Areas

### 1. Distance Calculations
- Haversine formula accuracy with known distances
- Edge cases (poles, dateline)
- Symmetry properties

### 2. Data Parsing
- Timestamp parsing in multiple formats
- GPX/XML point extraction
- Error handling for malformed data

### 3. Segment Finding
- Two-pointer sliding window algorithm correctness
- Penalty mechanism application
- Empty/edge case handling

### 4. Date Filtering
- Inclusive range boundaries
- Before/after comparisons
- Null/None handling

### 5. Output Formatting
- Duration formatting with rounding
- Distance labels (meters, km, special names)
- Infinity/None special cases

### 6. Integration
- Mock export processing
- Full workflow validation
- Penalty collection and reporting

## Expected Results

All tests should pass:
```
=================== 43 passed in 0.42s ===================
```

Coverage should be >85%:
```
apple_health_segments.py    87%     (25 lines missing in complex paths)
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'pytest'`
Install test dependencies:
```powershell
python -m pip install pytest pytest-cov
```

### `ImportError: cannot import name 'apple_health_segments'`
Ensure the tools directory is in Python path. The test file handles this automatically.

### Test fails with permission error
Ensure temp directory has write permissions (used for mock zip files).

### Individual test failure
Run with more verbose output:
```powershell
python -m pytest tests/test_apple_health_segments.py::TestName::test_name -vv -s
```

## Adding New Tests

When adding new functionality:

1. Create test method in appropriate class
2. Use descriptive name: `test_<feature>_<scenario>`
3. Add docstring explaining what's tested
4. Use fixtures for reusable test data
5. Run tests to ensure they pass: `pytest -v`
6. Check coverage: `pytest --cov=tools --cov-report=term-missing`

Example:

```python
class TestNewFeature:
    """Tests for new_feature()."""

    def test_new_feature_happy_path(self):
        """Should work correctly with valid input."""
        result = ahs.new_feature(valid_input)
        assert result == expected_output

    def test_new_feature_edge_case(self):
        """Should handle edge case gracefully."""
        result = ahs.new_feature(edge_input)
        assert isinstance(result, ExpectedType)
```

## Continuous Integration

Tests can be run in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run tests
  run: |
    python -m pip install -r tools/requirements.txt
    python -m pytest tests/ -v --cov=tools
```

## Test Coverage Goals

- **Unit tests**: >90% for utility functions
- **Integration tests**: >80% for main workflows
- **Overall**: >85% code coverage
