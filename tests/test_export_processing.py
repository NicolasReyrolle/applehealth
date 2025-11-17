#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for export processing functions."""

import os
import sys
import zipfile
from datetime import datetime
from io import BytesIO
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


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
        return gpx.encode("utf-8")

    @pytest.fixture
    def mock_export_zip(self, mock_gpx_content, tmp_path):  # type: ignore
        """Create a mock export.zip file."""
        zip_path = tmp_path / "export.zip"  # type: ignore

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

        with zipfile.ZipFile(zip_path, "w") as zf:  # type: ignore
            zf.writestr("export.xml", export_xml.encode("utf-8"))  # type: ignore
            zf.writestr(
                "apple_health_export/workout-routes/test_route.gpx", mock_gpx_content  # type: ignore
            )  # type: ignore

        return str(zip_path)  # type: ignore

    def test_process_export_finds_segments(self, mock_export_zip):  # type: ignore
        """Should find segments in a mock export."""
        results, _ = ahs.process_export(  # type: ignore
            mock_export_zip,
            distances_m=[10.0, 100.0],
            top_n=1,
            config={"progress": False},
        )

        assert isinstance(results, dict)
        assert 10.0 in results or 100.0 in results

    def test_process_export_with_date_filter(self, mock_export_zip):  # type: ignore
        """Should respect date filters."""
        # Filter to exclude the test date
        results, _ = ahs.process_export(  # type: ignore
            mock_export_zip,
            distances_m=[10.0],
            config={"start_date": datetime(2024, 1, 16).date(), "progress": False},
        )

        # Should have no results since test date is 2024-01-15
        assert results.get(10.0, []) == []  # type: ignore

    def test_process_export_within_date_range(self, mock_export_zip):  # type: ignore
        """Should include results within date range."""
        results, _ = ahs.process_export(  # type: ignore
            mock_export_zip,
            distances_m=[10.0],
            top_n=1,
            config={
                "start_date": datetime(2024, 1, 1).date(),
                "end_date": datetime(2024, 1, 31).date(),
                "progress": False,
            },
        )

        assert 10.0 in results

    def test_process_export_returns_penalty_messages(self, mock_export_zip):  # type: ignore
        """Should collect penalty messages when verbose."""
        _, penalties = ahs.process_export(  # type: ignore
            mock_export_zip,
            distances_m=[10.0],
            config={"verbose": True, "progress": False, "max_speed_kmh": 10.0},
        )

        assert isinstance(penalties, dict)

    def test_process_export_returns_tuple(self, mock_export_zip):  # type: ignore
        """process_export should return (results, penalties) tuple."""
        result = ahs.process_export(  # type: ignore
            mock_export_zip, distances_m=[10.0], config={"progress": False}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2  # type: ignore
        assert isinstance(result[0], dict)
        assert isinstance(result[1], dict)

    def test_process_export_with_none_config(self, mock_export_zip):  # type: ignore
        """Should handle None config by using defaults."""
        results, penalties = ahs.process_export(  # type: ignore
            mock_export_zip, distances_m=[10.0], top_n=1, config=None
        )
        assert isinstance(results, dict)
        assert isinstance(penalties, dict)

    def test_process_export_empty_distances(self, mock_export_zip):  # type: ignore
        """Should handle empty distances list."""
        results, penalties = ahs.process_export(  # type: ignore
            mock_export_zip, distances_m=[], config={"progress": False}
        )
        assert results == {}
        assert isinstance(penalties, dict)


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

        bio = BytesIO(gpx_content.encode("utf-8"))
        points = list(ahs.stream_points_from_route(bio))  # type: ignore

        assert len(points) == 2  # type: ignore
        lat1, lon1, ts1 = points[0]  # type: ignore
        assert abs(lat1 - 0.0) < 1e-6  # type: ignore
        assert abs(lon1 - 0.0) < 1e-6  # type: ignore
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

        bio = BytesIO(gpx_content.encode("utf-8"))
        points = list(ahs.stream_points_from_route(bio))  # type: ignore

        assert len(points) == 0  # type: ignore

    def test_stream_invalid_xml(self):
        """Should handle invalid XML gracefully."""
        invalid_content = b"This is not valid XML at all"

        bio = BytesIO(invalid_content)
        points = list(ahs.stream_points_from_route(bio))  # type: ignore

        # Should return empty list instead of crashing
        assert isinstance(points, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
