# Test Structure

The test suite has been split into focused modules for better maintainability:

## Test Modules

- **`test_distance_calculations.py`** - Haversine distance calculation tests
- **`test_timestamp_parsing.py`** - Timestamp parsing and format handling tests
- **`test_formatting.py`** - Duration, distance, and output formatting tests
- **`test_segment_analysis.py`** - Core segment finding algorithm tests
- **`test_export_processing.py`** - Export file processing and GPX parsing tests
- **`test_date_filtering.py`** - Date range filtering and helper function tests
- **`test_file_operations.py`** - File I/O operation tests
- **`test_cli_parsing.py`** - Command-line argument parsing tests
- **`test_integration.py`** - Integration tests with real export data

## Running Tests

Run all tests:

```powershell
python -m pytest tests/ -v
```

Run specific test module:

```powershell
python -m pytest tests/test_formatting.py -v
```

Generate coverage report:

```powershell
python -m pytest tests/ -v --cov=tools --cov-report=html
```

## Test Organization

Each module focuses on a specific functional area, making it easier to:

- Locate relevant tests when debugging
- Add new tests in the appropriate module
- Maintain and update tests independently
- Run focused test suites during development

The original `test_apple_health_segments.py` now serves as a test runner that imports all modules.
