#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for timestamp parsing functions."""

import os
import sys
from datetime import datetime
from typing import Any, cast

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # type: ignore # noqa: E402

ahs = cast(Any, ahs)


class TestParseTimestamp:
    """Unit tests for timestamp parsing."""

    def test_parse_iso_format(self):
        """Should parse ISO 8601 format."""
        result = ahs.parse_timestamp("2024-01-15T10:30:45Z")  # type: ignore
        assert result.year == 2024  # type: ignore
        assert result.month == 1  # type: ignore
        assert result.day == 15  # type: ignore
        assert result.hour == 10  # type: ignore
        assert result.minute == 30  # type: ignore

    def test_parse_apple_format(self):
        """Should parse Apple's timestamp format."""
        result = ahs.parse_timestamp("2024-01-15 10:30:45 +0000")  # type: ignore
        assert result.year == 2024  # type: ignore
        assert result.month == 1  # type: ignore
        assert result.day == 15  # type: ignore

    def test_parse_various_formats(self):
        """Should handle various timestamp formats gracefully."""
        formats = [
            "2024-01-15T10:30:45Z",
            "2024-01-15 10:30:45 UTC",
            "01/15/2024 10:30:45",
            "2024-01-15T10:30:45+00:00",
        ]
        for fmt in formats:
            result = ahs.parse_timestamp(fmt)  # type: ignore
            assert isinstance(result, datetime), f"Failed to parse: {fmt}"

    def test_parse_empty_string_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            ahs.parse_timestamp("")  # type: ignore

    def test_parse_none_raises(self):
        """None should raise an error."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            ahs.parse_timestamp(None)  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
