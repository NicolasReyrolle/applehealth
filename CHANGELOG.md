# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Tagging Strategy

This project uses **Semantic Versioning** (MAJOR.MINOR.PATCH):

- **MAJOR** version (x.0.0): Incompatible API changes or breaking CLI changes
- **MINOR** version (0.x.0): New features in a backwards-compatible manner
- **PATCH** version (0.0.x): Backwards-compatible bug fixes

### Release Process

1. Update CHANGELOG.md:
   - Move items from `[Unreleased]` to a new version section
   - Add release date in format `## [X.Y.Z] - YYYY-MM-DD`
   - Update comparison links at bottom of file

2. Create and push a version tag:
   ```bash
   git tag -a vX.Y.Z -m "Release version X.Y.Z"
   git push origin vX.Y.Z
   ```

3. GitHub Actions will automatically:
   - Run tests and quality checks
   - Create a GitHub Release with changelog notes
   - Build and publish artifacts (if configured)

### Tag Format

- Tags follow the format `vX.Y.Z` (e.g., `v1.0.0`, `v1.2.3`)
- Pre-releases use suffix: `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N`, `vX.Y.Z-rc.N`
- Development builds: `vX.Y.Z-dev.N`

## [Unreleased]

### Added
- Initial release of Apple Health Segments tool
- Core CLI tool (`apple_health_segments.py`) for finding fastest running segments from Apple Health exports
- Penalty-based GPS error handling system
  - Configurable speed threshold (`--max-speed`, default 20 km/h)
  - Configurable penalty duration (`--speed-penalty`, default 3 seconds)
  - Instead of dropping bad GPS data, penalize suspect segments in ranking
- Date range filtering with `--start-date` and `--end-date` options
- Verbose penalty reporting with `--verbose` flag
- File output options:
  - `--output-file` / `-o` for results
  - `--penalty-file` for GPS anomaly warnings
- Support for multiple distance targets (default: 400m, 800m, 1km, 5km, 10km, 15km, 20km, half marathon, marathon)
- Memory-efficient streaming architecture for large exports
- Progress bar with `--progress` / `--no-progress` toggle
- Utility tools:
  - `points_on_date.py` - Extract GPS points from specific date to CSV
  - `compute_speed_stats.py` - Analyze speed distribution for parameter tuning
  - `export_processor.py` - Export processing library
  - `segment_analysis.py` - Segment analysis core library

### Features
- Two-pointer sliding window algorithm for segment detection
- Haversine formula for distance calculations (±0.1% precision)
- Support for Apple Health Route XML and GPX file formats
- Namespace-agnostic XML/GPX parsing
- Timezone-aware timestamp handling
- Streams exports without loading entire dataset into RAM

### Testing
- Comprehensive test suite with 13 test modules
- 1,564+ lines of test code covering:
  - CLI argument parsing
  - Date filtering functionality
  - Distance calculations and precision
  - Error handling and edge cases
  - Export processing with real-world data
  - File I/O operations
  - Output formatting
  - Integration tests with sample data
  - Segment analysis algorithms
  - Timestamp parsing variations
- Test fixtures including real export samples
- CI/CD integration:
  - GitHub Actions workflows for automated testing
  - CodeQL security analysis
  - Dependency review automation
  - Dependabot configuration

### Documentation
- Comprehensive README.md with quick start guide
- Detailed tools/README.md with CLI reference and algorithm explanation
- Test documentation in tests/README.md
- Fixture documentation in tests/fixtures/README.md
- GitHub Copilot instructions for development
- Codacy configuration for code quality monitoring

### Development
- Python 3.x compatible
- Dependencies: `python-dateutil`, `tqdm`, `pytest`, `pytest-cov`
- Codacy quality monitoring
- Code coverage tracking with codecov

[Unreleased]: https://github.com/NicolasReyrolle/applehealth/compare/main...HEAD
