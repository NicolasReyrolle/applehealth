#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Additional tests to improve coverage."""

import os
import sys
from datetime import datetime
from typing import cast, Any, List

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestFormatPace:
    """Test pace formatting function."""

    def test_format_pace_zero_speed(self):
        """Zero speed should return dash."""
        assert ahs.format_pace(0.0) == "-"  # type: ignore

    def test_format_pace_negative_speed(self):
        """Negative speed should return dash."""
        assert ahs.format_pace(-5.0) == "-"  # type: ignore

    def test_format_pace_normal_speed(self):
        """Normal speed should format correctly."""
        # 12 km/h = 5:00/km
        result = ahs.format_pace(12.0)  # type: ignore
        assert result == "5:00/km"  # type: ignore

    def test_format_pace_fast_speed(self):
        """Fast speed should format correctly."""
        # 20 km/h = 3:00/km
        result = ahs.format_pace(20.0)  # type: ignore
        assert result == "3:00/km"  # type: ignore


class TestFormatDateString:
    """Test date string formatting helper."""

    def test_format_date_string_none(self):
        """None date should return unknown."""
        result = ahs._format_date_string(None)  # type: ignore
        assert result == "unknown"  # type: ignore

    def test_format_date_string_valid(self):
        """Valid date should format correctly."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = ahs._format_date_string(dt)  # type: ignore
        assert result == "15/01/2024"  # type: ignore


class TestFormatSegmentLine:
    """Test segment line formatting helper."""

    def test_format_segment_line_with_elevation(self):
        """Should format line with elevation change."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = ahs._format_segment_line(1, 120.0, dt, 15.0, 12.0)  # type: ignore
        assert "15/01/2024" in result  # type: ignore
        assert "00:02:00" in result  # type: ignore
        assert "+15m" in result  # type: ignore
        assert "5:00/km" in result  # type: ignore

    def test_format_segment_line_zero_elevation(self):
        """Should format line with zero elevation."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = ahs._format_segment_line(1, 120.0, dt, 0.0, 12.0)  # type: ignore
        assert "0m" in result  # type: ignore

    def test_format_segment_line_none_date(self):
        """Should handle None date."""
        result = ahs._format_segment_line(1, 120.0, None, 0.0, 12.0)  # type: ignore
        assert "unknown" in result  # type: ignore


class TestMainFunction:
    """Test main function error handling."""

    def test_main_invalid_date_format(self, monkeypatch: Any):  # type: ignore
        """Should handle invalid date format gracefully."""
        # Mock sys.argv to simulate invalid date
        monkeypatch.setattr(
            "sys.argv", ["script", "--zip", "test.zip", "--start-date", "invalid"]
        )  # type: ignore

        # Capture print output
        captured_output: List[str] = []

        def mock_print(*args: Any, **kwargs: Any) -> None:  # type: ignore # pylint: disable=unused-argument
            captured_output.append(" ".join(str(arg) for arg in args))  # type: ignore

        monkeypatch.setattr("builtins.print", mock_print)  # type: ignore

        # Should not raise exception
        ahs.main()  # type: ignore

        # Should print error message
        assert any("Error parsing date" in output for output in captured_output)  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
