#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Test edge cases in export processing."""

import os
import sys
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import export_processor as ep  # noqa: E402 # type: ignore

ep = cast(Any, ep)


class TestExportProcessorEdgeCases:
    """Test edge cases in export processor."""

    def test_parse_timestamp_with_timezone(self):
        """Should handle timestamps with timezone info."""
        result = ep.parse_timestamp("2024-01-15T10:00:00+01:00")  # type: ignore
        assert result.year == 2024  # type: ignore

    def test_get_location_attrs_missing_elevation(self):
        """Should handle missing elevation attribute."""

        class MockElement:  # pylint: disable=missing-class-docstring,too-few-public-methods
            def get(self, attr: str):  # type: ignore # pylint: disable=missing-function-docstring
                if attr in ["latitude", "lat"]:
                    return "0.0"
                elif attr in ["longitude", "lon"]:
                    return "0.0"
                elif attr in ["timestamp", "time"]:
                    return "2024-01-15T10:00:00Z"
                return None

        lat, lon, ele, ts = ep._get_location_attrs(MockElement())  # type: ignore
        assert lat == "0.0"  # type: ignore
        assert lon == "0.0"  # type: ignore
        assert ele is None  # type: ignore
        assert ts == "2024-01-15T10:00:00Z"  # type: ignore

    def test_create_gps_point_missing_elevation(self):
        """Should handle missing elevation in GPS point creation."""
        result = ep._create_gps_point("0.0", "0.0", None, "2024-01-15T10:00:00Z")  # type: ignore
        assert result is not None  # type: ignore
        lat, lon, ele, _ = result  # type: ignore
        assert abs(lat - 0.0) < 1e-6  # type: ignore
        assert abs(lon - 0.0) < 1e-6  # type: ignore
        assert abs(ele - 0.0) < 1e-6  # Should default to 0.0  # type: ignore

    def test_decode_line_with_bytes(self):
        """Should decode bytes to string."""
        result = ep._decode_line(b"test line")  # type: ignore
        assert result == "test line"  # type: ignore

    def test_decode_line_with_string(self):
        """Should handle string input."""
        result = ep._decode_line("test line")  # type: ignore
        assert result == "test line"  # type: ignore

    def test_decode_line_with_unicode_error(self):
        """Should handle unicode decode errors."""
        # Create invalid UTF-8 bytes
        invalid_bytes = b"\xff\xfe"
        result = ep._decode_line(invalid_bytes)  # type: ignore
        assert result is None  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
