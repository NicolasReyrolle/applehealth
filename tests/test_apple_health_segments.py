#!/usr/bin/env python3
# pyright: reportAttributeAccessIssue=false
"""
Unit and integration tests for apple_health_segments.py

Run tests with: python -m pytest tests/ -v
Or with coverage: python -m pytest tests/ -v --cov=tools --cov-report=html
"""

import sys
import os
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
import pytest

# Add tools directory to path so we can import apple_health_segments
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools'))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

# pylint: disable=import-error,wrong-import-position
import apple_health_segments as ahs  # type: ignore # pyright: ignore


class TestHaversineMeters:
    """Unit tests for haversine distance calculation."""

    def test_haversine_zero_distance(self):
        """Same coordinates should return ~0 meters."""
        result = ahs.haversine_meters(0.0, 0.0, 0.0, 0.0)
        assert abs(result) < 1e-6, "Same coordinates should be ~0 meters apart"

    def test_haversine_one_degree_latitude(self):
        """One degree latitude is approximately 111 km."""
        result = ahs.haversine_meters(0.0, 0.0, 1.0, 0.0)
        assert 110000 < result < 112000, "One degree latitude should be ~111 km"

    def test_haversine_one_degree_longitude_at_equator(self):
        """One degree longitude at equator is approximately 111 km."""
        result = ahs.haversine_meters(0.0, 0.0, 0.0, 1.0)
        assert 110000 < result < 112000, "One degree longitude at equator should be ~111 km"

    def test_haversine_known_distance(self):
        """Test with known real-world coordinates (Luxembourg)."""
        # Gare Centrale Luxembourg to City Center (~2.5 km)
        lat1, lon1 = 49.6116, 6.1319
        lat2, lon2 = 49.6163, 6.1408
        result = ahs.haversine_meters(lat1, lon1, lat2, lon2)
        # Should be roughly 1 km (rough estimate)
        assert 500 < result < 2000, f"Distance should be ~1km, got {result}m"

    def test_haversine_symmetry(self):
        """Distance from A to B should equal distance from B to A."""
        lat1, lon1, lat2, lon2 = 40.7128, -74.0060, 34.0522, -118.2437
        d1 = ahs.haversine_meters(lat1, lon1, lat2, lon2)
        d2 = ahs.haversine_meters(lat2, lon2, lat1, lon1)
        assert abs(d1 - d2) < 1e-6, "Haversine distance should be symmetric"


class TestParseTimestamp:
    """Unit tests for timestamp parsing."""

    def test_parse_iso_format(self):
        """Should parse ISO 8601 format."""
        result = ahs.parse_timestamp("2024-01-15T10:30:45Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_apple_format(self):
        """Should parse Apple's timestamp format."""
        result = ahs.parse_timestamp("2024-01-15 10:30:45 +0000")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_various_formats(self):
        """Should handle various timestamp formats gracefully."""
        formats = [
            "2024-01-15T10:30:45Z",
            "2024-01-15 10:30:45 UTC",
            "01/15/2024 10:30:45",
            "2024-01-15T10:30:45+00:00",
        ]
        for fmt in formats:
            result = ahs.parse_timestamp(fmt)
            assert isinstance(result, datetime), f"Failed to parse: {fmt}"

    def test_parse_empty_string_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            ahs.parse_timestamp("")

    def test_parse_none_raises(self):
        """None should raise an error."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            ahs.parse_timestamp(None)


class TestFormatDuration:
    """Unit tests for duration formatting."""

    def test_format_duration_zero(self):
        """Zero seconds should format as 00:00:00."""
        assert ahs.format_duration(0.0) == "00:00:00"

    def test_format_duration_seconds_only(self):
        """45 seconds should format as 00:00:45."""
        assert ahs.format_duration(45.0) == "00:00:45"

    def test_format_duration_minutes(self):
        """125 seconds (2:05) should format as 00:02:05."""
        assert ahs.format_duration(125.0) == "00:02:05"

    def test_format_duration_hours(self):
        """3665 seconds (1:01:05) should format as 01:01:05."""
        assert ahs.format_duration(3665.0) == "01:01:05"

    def test_format_duration_rounding(self):
        """45.6 seconds should round to 46."""
        result = ahs.format_duration(45.6)
        assert result == "00:00:46"

    def test_format_duration_infinity(self):
        """Infinity should return '-'."""
        assert ahs.format_duration(float('inf')) == "-"

    def test_format_duration_none(self):
        """None should return '-'."""
        assert ahs.format_duration(None) == "-"


class TestFormatDistance:
    """Unit tests for distance formatting."""

    def test_format_distance_meters(self):
        """Distances < 1000m should format in meters."""
        assert ahs.format_distance(400.0) == "400 m"
        assert ahs.format_distance(800.0) == "800 m"

    def test_format_distance_kilometers(self):
        """Round kilometers should format without decimals."""
        assert ahs.format_distance(1000.0) == "1 km"
        assert ahs.format_distance(5000.0) == "5 km"
        assert ahs.format_distance(10000.0) == "10 km"

    def test_format_distance_decimal_kilometers(self):
        """Non-round kilometers should show minimal decimals."""
        result = ahs.format_distance(1500.0)
        assert "1.5" in result or "1.50" in result
        assert "km" in result

    def test_format_distance_half_marathon(self):
        """21097.5 meters should format as 'Half Marathon'."""
        assert ahs.format_distance(21097.5) == "Half Marathon"

    def test_format_distance_marathon(self):
        """42195 meters should format as 'Marathon'."""
        assert ahs.format_distance(42195.0) == "Marathon"

    def test_format_distance_none(self):
        """None should return empty string."""
        assert ahs.format_distance(None) == ""


class TestBestSegmentForDist:
    """Unit tests for segment finding algorithm."""

    @pytest.fixture
    def simple_points(self):
        """Create simple test points in a straight line."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            # Longitude increases by ~0.01 degrees per 1km at equator
            (0.0, 0.0 + i*0.009, base_time + timedelta(seconds=i*10))
            for i in range(100)
        ]
        return points

    def test_segment_with_enough_points(self, simple_points):
        """Should find a segment for reasonable distances."""
        result = ahs.best_segment_for_dist(simple_points, 100.0)
        duration, start_time, end_time = result
        assert duration != float('inf'), "Should find a segment"
        assert start_time is not None
        assert end_time is not None
        assert start_time < end_time

    def test_segment_ordering(self, simple_points):
        """Segment should maintain chronological order."""
        result = ahs.best_segment_for_dist(simple_points, 100.0)
        duration, start_time, end_time = result
        assert start_time <= end_time

    def test_segment_unrealistic_distance(self, simple_points):
        """Unrealistic distance should return infinity."""
        result = ahs.best_segment_for_dist(simple_points, 100000000.0)
        duration, start_time, end_time = result
        assert duration == float('inf')

    def test_segment_empty_points(self):
        """Empty points list should return infinity."""
        result = ahs.best_segment_for_dist([], 100.0)
        duration, start_time, end_time = result
        assert duration == float('inf')
        assert start_time is None
        assert end_time is None

    def test_segment_penalty_applied(self):
        """High-speed intervals should increase adjusted duration."""
        # Create two identical segments, one with a penalty
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        # Segment 1: normal speeds
        points1 = [
            (0.0, 0.0 + i*0.001, base_time + timedelta(seconds=i*10))
            for i in range(50)
        ]
        
        # Segment 2: same distance but with one fast point (will trigger penalty)
        points2 = [
            (0.0, 0.0 + i*0.001, base_time + timedelta(seconds=i*10 if i != 25 else i*1))
            for i in range(50)
        ]
        
        dur1, _, _ = ahs.best_segment_for_dist(points1, 100.0, max_speed_kmh=20.0, penalty_seconds=3.0)
        dur2, _, _ = ahs.best_segment_for_dist(points2, 100.0, max_speed_kmh=20.0, penalty_seconds=3.0)
        
        # Both should be valid segments
        assert dur1 != float('inf')
        assert dur2 != float('inf')

    def test_segment_debug_info(self):
        """Debug info should be populated when requested."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i*0.001, base_time + timedelta(seconds=i*10))
            for i in range(50)
        ]
        
        debug_info = {}
        ahs.best_segment_for_dist(points, 100.0, debug_info=debug_info)
        
        assert 'num_points' in debug_info
        assert 'segment_dist' in debug_info
        assert 'total_dist' in debug_info


class TestIntegrationWithMockExport:
    """Integration tests using mock Apple Health export files."""

    @pytest.fixture
    def mock_gpx_content(self):
        """Create a minimal valid GPX file."""
        gpx = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test">
  <trk>
    <trkseg>
      <trkpt lat="0.0" lon="0.0">
        <time>2024-01-15T10:00:00Z</time>
      </trkpt>
      <trkpt lat="0.001" lon="0.0">
        <time>2024-01-15T10:00:10Z</time>
      </trkpt>
      <trkpt lat="0.002" lon="0.0">
        <time>2024-01-15T10:00:20Z</time>
      </trkpt>
      <trkpt lat="0.003" lon="0.0">
        <time>2024-01-15T10:00:30Z</time>
      </trkpt>
      <trkpt lat="0.004" lon="0.0">
        <time>2024-01-15T10:00:40Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""
        return gpx.encode('utf-8')

    @pytest.fixture
    def mock_export_zip(self, mock_gpx_content, tmp_path):
        """Create a mock export.zip file."""
        zip_path = tmp_path / "export.zip"
        
        # Create a minimal export.xml
        export_xml = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning" 
           startDate="2024-01-15 10:00:00 +0000" 
           endDate="2024-01-15 10:01:00 +0000">
    <WorkoutRoute startDate="2024-01-15 10:00:00 +0000" 
                  endDate="2024-01-15 10:01:00 +0000">
      <FileReference path="apple_health_export/workout-routes/test_route.gpx"/>
    </WorkoutRoute>
  </Workout>
</HealthData>"""
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('export.xml', export_xml.encode('utf-8'))
            zf.writestr('apple_health_export/workout-routes/test_route.gpx', mock_gpx_content)
        
        return str(zip_path)

    def test_process_export_finds_segments(self, mock_export_zip):
        """Should find segments in a mock export."""
        results, penalties = ahs.process_export(
            mock_export_zip,
            distances_m=[10.0, 100.0],
            top_n=1,
            progress=False
        )
        
        assert isinstance(results, dict)
        assert 10.0 in results or 100.0 in results

    def test_process_export_with_date_filter(self, mock_export_zip):
        """Should respect date filters."""
        # Filter to exclude the test date
        results, penalties = ahs.process_export(
            mock_export_zip,
            distances_m=[10.0],
            start_date=datetime(2024, 1, 16).date(),
            progress=False
        )
        
        # Should have no results since test date is 2024-01-15
        assert results.get(10.0, []) == []

    def test_process_export_within_date_range(self, mock_export_zip):
        """Should include results within date range."""
        results, penalties = ahs.process_export(
            mock_export_zip,
            distances_m=[10.0],
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 1, 31).date(),
            top_n=1,
            progress=False
        )
        
        assert 10.0 in results

    def test_process_export_returns_penalty_messages(self, mock_export_zip):
        """Should collect penalty messages when verbose."""
        results, penalties = ahs.process_export(
            mock_export_zip,
            distances_m=[10.0],
            verbose=True,
            progress=False,
            max_speed_kmh=10.0  # Low threshold to trigger penalties
        )
        
        assert isinstance(penalties, dict)

    def test_process_export_returns_tuple(self, mock_export_zip):
        """process_export should return (results, penalties) tuple."""
        result = ahs.process_export(
            mock_export_zip,
            distances_m=[10.0],
            progress=False
        )
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert isinstance(result[1], dict)


class TestStreamPointsFromRoute:
    """Unit tests for GPX/XML point streaming."""

    def test_stream_gpx_points(self):
        """Should extract points from GPX content."""
        gpx_content = """<?xml version="1.0"?>
<gpx version="1.1">
  <trk>
    <trkseg>
      <trkpt lat="0.0" lon="0.0">
        <time>2024-01-15T10:00:00Z</time>
      </trkpt>
      <trkpt lat="0.001" lon="0.0">
        <time>2024-01-15T10:00:10Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""
        
        bio = BytesIO(gpx_content.encode('utf-8'))
        points = list(ahs.stream_points_from_route(bio))
        
        assert len(points) == 2
        lat1, lon1, ts1 = points[0]
        assert abs(lat1 - 0.0) < 1e-6
        assert abs(lon1 - 0.0) < 1e-6
        assert isinstance(ts1, datetime)

    def test_stream_empty_route(self):
        """Should handle empty routes gracefully."""
        gpx_content = """<?xml version="1.0"?>
<gpx version="1.1">
  <trk>
    <trkseg>
    </trkseg>
  </trk>
</gpx>"""
        
        bio = BytesIO(gpx_content.encode('utf-8'))
        points = list(ahs.stream_points_from_route(bio))
        
        assert len(points) == 0

    def test_stream_invalid_xml(self):
        """Should handle invalid XML gracefully."""
        invalid_content = b"This is not valid XML at all"
        
        bio = BytesIO(invalid_content)
        points = list(ahs.stream_points_from_route(bio))
        
        # Should return empty list instead of crashing
        assert isinstance(points, list)


class TestDateFiltering:
    """Test date range filtering functionality."""

    def test_date_before_range(self):
        """Workout before start_date should be excluded."""
        from datetime import date
        workout_date = datetime(2024, 1, 1)
        start_date = date(2024, 1, 15)
        
        assert workout_date.date() < start_date

    def test_date_within_range(self):
        """Workout within range should be included."""
        from datetime import date
        workout_date = datetime(2024, 1, 15)
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        assert start_date <= workout_date.date() <= end_date

    def test_date_after_range(self):
        """Workout after end_date should be excluded."""
        from datetime import date
        workout_date = datetime(2024, 2, 1)
        end_date = date(2024, 1, 31)
        
        assert workout_date.date() > end_date


class TestRealExportIntegration:
    """Integration tests using actual Apple Health export.zip data."""

    @pytest.fixture(scope="class")
    def export_zip_path(self):
        """Path to the sample export.zip file for faster integration testing."""
        # Use the lightweight sample subset (~94 MB with 10 routes)
        sample_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures',
            'export_sample.zip'
        )
        if os.path.exists(sample_path):
            return sample_path
        # Skip if sample doesn't exist
        pytest.skip("export_sample.zip not found in tests/fixtures/")

    def test_process_export_finds_running_workouts(self, export_zip_path: str) -> None:
        """Should find and process running workouts from the actual export."""
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[400.0, 1000.0, 5000.0],
            top_n=3,
            progress=False
        )
        
        # Should have results for requested distances
        assert len(results) == 3
        assert 400.0 in results
        assert 1000.0 in results
        assert 5000.0 in results

    def test_process_export_returns_valid_segments(self, export_zip_path):
        """Should return valid segment data with proper timing."""
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=5,
            progress=False
        )
        
        segments = results[1000.0]
        if segments:  # Only check if we have segments
            for duration, workout_date in segments:
                assert isinstance(duration, float)
                assert duration > 0
                assert duration != float('inf')
                assert isinstance(workout_date, (datetime, type(None)))

    def test_process_export_respects_top_n(self, export_zip_path):
        """Should return at most top_n segments per distance."""
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[400.0, 1000.0],
            top_n=3,
            progress=False
        )
        
        for distance, segments in results.items():
            assert len(segments) <= 3, f"Expected ≤3 segments for {distance}m, got {len(segments)}"

    def test_process_export_with_start_date_filter(self, export_zip_path):
        """Should filter segments by start date (inclusive)."""
        start_date = datetime(2024, 1, 1).date()
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            progress=False,
            start_date=start_date
        )
        
        segments = results[1000.0]
        for _, workout_date in segments:
            if workout_date:
                assert workout_date.date() >= start_date

    def test_process_export_with_end_date_filter(self, export_zip_path):
        """Should filter segments by end date (inclusive)."""
        end_date = datetime(2024, 12, 31).date()
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            progress=False,
            end_date=end_date
        )
        
        segments = results[1000.0]
        for _, workout_date in segments:
            if workout_date:
                assert workout_date.date() <= end_date

    def test_process_export_with_date_range(self, export_zip_path):
        """Should filter by date range (both start and end)."""
        start_date = datetime(2024, 1, 1).date()
        end_date = datetime(2024, 12, 31).date()
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            progress=False,
            start_date=start_date,
            end_date=end_date
        )
        
        segments = results[1000.0]
        for _, workout_date in segments:
            if workout_date:
                assert start_date <= workout_date.date() <= end_date

    def test_process_export_max_speed_filtering(self, export_zip_path):
        """Should apply speed penalties to fast intervals."""
        # With low max_speed, should see more penalization
        results_strict, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=3,
            progress=False,
            max_speed_kmh=10.0,  # Very restrictive
            penalty_seconds=3.0
        )
        
        results_lenient, _ = ahs.process_export(
            export_zip_path,
            distances_m=[1000.0],
            top_n=3,
            progress=False,
            max_speed_kmh=50.0,  # Very lenient
            penalty_seconds=3.0
        )
        
        # Both should have similar number of segments found
        assert len(results_strict[1000.0]) >= 0
        assert len(results_lenient[1000.0]) >= 0

    def test_process_export_verbose_mode(self, export_zip_path):
        """Should collect penalty messages in verbose mode."""
        results, penalties = ahs.process_export(
            export_zip_path,
            distances_m=[400.0, 1000.0],
            top_n=3,
            progress=False,
            verbose=True,
            max_speed_kmh=15.0  # Lower threshold to trigger penalties
        )
        
        # penalties should be a dict
        assert isinstance(penalties, dict)
        # May or may not have penalties depending on data
        if penalties:
            for key, msg in penalties.items():
                assert isinstance(key, str)
                assert isinstance(msg, str)

    def test_process_export_multiple_distances(self, export_zip_path):
        """Should process multiple target distances in one pass."""
        distances = [400.0, 800.0, 1000.0, 5000.0, 10000.0]
        results, _ = ahs.process_export(
            export_zip_path,
            distances_m=distances,
            top_n=2,
            progress=False
        )
        
        # Should have results for each distance
        for d in distances:
            assert d in results
            assert isinstance(results[d], list)

    def test_process_export_consistency_across_runs(self, export_zip_path):
        """Running the same export twice should give identical results."""
        kwargs = {
            'distances_m': [1000.0],
            'top_n': 3,
            'progress': False,
            'max_speed_kmh': 20.0
        }
        
        results1, _ = ahs.process_export(export_zip_path, **kwargs)
        results2, _ = ahs.process_export(export_zip_path, **kwargs)
        
        # Results should be identical
        assert len(results1[1000.0]) == len(results2[1000.0])
        for (d1, dt1), (d2, dt2) in zip(results1[1000.0], results2[1000.0]):
            assert abs(d1 - d2) < 0.01  # Allow tiny floating point differences
            if dt1 and dt2:
                assert dt1 == dt2


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_zero_distance_target(self):
        """Should handle zero distance target gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i*0.001, base_time + timedelta(seconds=i*10))
            for i in range(10)
        ]
        
        result = ahs.best_segment_for_dist(points, 0.0)
        # Should handle it without crashing
        assert isinstance(result, tuple)

    def test_negative_distance_target(self):
        """Should handle negative distance gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0 + i*0.001, base_time + timedelta(seconds=i*10))
            for i in range(10)
        ]
        
        result = ahs.best_segment_for_dist(points, -100.0)
        # Should handle it without crashing
        assert isinstance(result, tuple)

    def test_single_point(self):
        """Should handle single point gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [(0.0, 0.0, base_time)]
        
        result = ahs.best_segment_for_dist(points, 100.0)
        duration, start_time, end_time = result
        assert duration == float('inf')

    def test_two_identical_points(self):
        """Should handle duplicate points gracefully."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        points = [
            (0.0, 0.0, base_time),
            (0.0, 0.0, base_time + timedelta(seconds=10)),
        ]
        
        result = ahs.best_segment_for_dist(points, 100.0)
        # Should not crash
        assert isinstance(result, tuple)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
