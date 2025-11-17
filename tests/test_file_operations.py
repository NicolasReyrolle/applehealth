#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for file operations."""

import os
import sys
from typing import Any, cast

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestWriteOutputFile:
    """Test file writing functionality."""

    def test_write_output_file_success(self, tmp_path):  # type: ignore
        """Should write lines to file successfully."""
        filepath = tmp_path / "output.txt"  # type: ignore
        lines = ["Line 1", "Line 2", "Line 3"]
        ahs._write_output_file(str(filepath), lines)  # type: ignore

        content = filepath.read_text(encoding="utf-8")  # type: ignore
        assert "Line 1\n" in content
        assert "Line 2\n" in content
        assert "Line 3\n" in content

    def test_write_output_file_invalid_path(self, capsys):  # type: ignore
        """Should handle invalid path gracefully."""
        ahs._write_output_file("/invalid/path/file.txt", ["test"])  # type: ignore
        captured = capsys.readouterr()  # type: ignore
        assert "Error writing file" in captured.out  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
