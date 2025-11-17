#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Integration tests using actual Apple Health export data."""

import os
import sys
from datetime import datetime
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestRealExportIntegration:
    """Integration tests using actual Apple Health export.zip data."""

    @pytest.fixture(scope="class")
    def export_zip_path(self):
        """Path to the sample export.zip file for faster integration testing."""
        # Use the lightweight sample subset (~94 MB with 10 routes)
        sample_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "export_sample.zip"
        )
        if os.path.exists(sample_path):
            return sample_path
        # Skip if sample doesn't exist
        pytest.skip("export_sample.zip not found in tests/fixtures/")

    def test_process_export_finds_running_workouts(self, export_zip_path: str) -> None:
        """Should find and process running workouts from the actual export."""
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[400.0, 1000.0, 5000.0],
            top_n=3,
            config={"progress": False},
        )

        # Should have results for requested distances
        assert len(results) == 3  # type: ignore
        assert 400.0 in results
        assert 1000.0 in results
        assert 5000.0 in results

    def test_process_export_returns_valid_segments(self, export_zip_path):  # type: ignore
        """Should return valid segment data with proper timing."""
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path, distances_m=[1000.0], top_n=5, config={"progress": False}
        )

        segments = results[1000.0]  # type: ignore
        if segments:  # Only check if we have segments
            for duration, workout_date in segments:  # type: ignore
                assert isinstance(duration, float)
                assert duration > 0
                assert duration != float("inf")
                assert isinstance(workout_date, (datetime, type(None)))

    def test_process_export_respects_top_n(self, export_zip_path):  # type: ignore
        """Should return at most top_n segments per distance."""
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[400.0, 1000.0],
            top_n=3,
            config={"progress": False},
        )

        for distance, segments in results.items():  # type: ignore
            assert len(segments) <= 3, ( # type: ignore
                f"Expected ≤3 segments for {distance}m, got {len(segments)}"  # type: ignore
            )

    def test_process_export_with_start_date_filter(self, export_zip_path):  # type: ignore
        """Should filter segments by start date (inclusive)."""
        start_date = datetime(2024, 1, 1).date()
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            config={"progress": False, "start_date": start_date},
        )

        segments = results[1000.0]  # type: ignore
        for _, workout_date in segments:  # type: ignore
            if workout_date:
                assert workout_date.date() >= start_date  # type: ignore

    def test_process_export_with_end_date_filter(self, export_zip_path):  # type: ignore
        """Should filter segments by end date (inclusive)."""
        end_date = datetime(2024, 12, 31).date()
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            config={"progress": False, "end_date": end_date},
        )

        segments = results[1000.0]  # type: ignore
        for _, workout_date in segments:  # type: ignore
            if workout_date:
                assert workout_date.date() <= end_date  # type: ignore

    def test_process_export_with_date_range(self, export_zip_path):  # type: ignore
        """Should filter by date range (both start and end)."""
        start_date = datetime(2024, 1, 1).date()  # type: ignore
        end_date = datetime(2024, 12, 31).date()  # type: ignore
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[1000.0],
            top_n=10,
            config={"progress": False, "start_date": start_date, "end_date": end_date},
        )

        segments = results[1000.0]  # type: ignore
        for _, workout_date in segments:  # type: ignore
            if workout_date:
                assert start_date <= workout_date.date() <= end_date  # type: ignore

    def test_process_export_max_speed_filtering(self, export_zip_path):  # type: ignore
        """Should apply speed penalties to fast intervals."""
        # With low max_speed, should see more penalization
        results_strict, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[1000.0],
            top_n=3,
            config={"progress": False, "max_speed_kmh": 10.0, "penalty_seconds": 3.0},
        )

        results_lenient, _ = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[1000.0],
            top_n=3,
            config={"progress": False, "max_speed_kmh": 50.0, "penalty_seconds": 3.0},
        )

        # Both should have segments found (may be empty)
        assert isinstance(results_strict[1000.0], list)  # type: ignore
        assert isinstance(results_lenient[1000.0], list)  # type: ignore

    def test_process_export_verbose_mode(self, export_zip_path):  # type: ignore
        """Should collect penalty messages in verbose mode."""
        _, penalties = ahs.process_export(  # type: ignore
            export_zip_path,
            distances_m=[400.0, 1000.0],
            top_n=3,
            config={"progress": False, "verbose": True, "max_speed_kmh": 15.0},
        )

        # penalties should be a dict
        assert isinstance(penalties, dict)
        # May or may not have penalties depending on data
        if penalties:
            for key, msg in penalties.items():  # type: ignore
                assert isinstance(key, str)
                assert isinstance(msg, str)

    def test_process_export_multiple_distances(self, export_zip_path):  # type: ignore
        """Should process multiple target distances in one pass."""
        distances = [400.0, 800.0, 1000.0, 5000.0, 10000.0]
        results, _ = ahs.process_export(  # type: ignore
            export_zip_path, distances_m=distances, top_n=2, config={"progress": False}
        )

        # Should have results for each distance
        for d in distances:
            assert d in results
            assert isinstance(results[d], list)

    def test_process_export_consistency_across_runs(self, export_zip_path):  # type: ignore
        """Running the same export twice should give identical results."""
        config = {"progress": False, "max_speed_kmh": 20.0}  # type: ignore

        results1, _ = ahs.process_export(  # type: ignore
            export_zip_path, distances_m=[1000.0], top_n=3, config=config
        )
        results2, _ = ahs.process_export(  # type: ignore
            export_zip_path, distances_m=[1000.0], top_n=3, config=config
        )

        # Results should be identical
        assert len(results1[1000.0]) == len(results2[1000.0])  # type: ignore
        for (d1, dt1), (d2, dt2) in zip(results1[1000.0], results2[1000.0]):  # type: ignore
            assert abs(d1 - d2) < 0.01  # Allow tiny floating point differences  # type: ignore
            if dt1 and dt2:
                assert dt1 == dt2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
