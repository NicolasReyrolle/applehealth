#!/usr/bin/env python3
# pylint: disable=import-error,wrong-import-position,protected-access
"""Tests for CLI argument parsing."""

import argparse
import os
import sys
from typing import cast, Any

import pytest

# Add tools directory to path
tools_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools'))
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

import apple_health_segments as ahs  # noqa: E402 # type: ignore

ahs = cast(Any, ahs)


class TestCLIArgumentParsing:
    """Test CLI argument parsing functions."""

    def test_add_basic_args(self):
        """Should add basic arguments to parser."""
        parser = argparse.ArgumentParser()
        ahs._add_basic_args(parser)  # type: ignore
        args = parser.parse_args(["--zip", "test.zip"])
        assert args.zip == "test.zip"
        assert args.top == 5
        assert args.debug is False

    def test_add_speed_args(self):
        """Should add speed arguments to parser."""
        parser = argparse.ArgumentParser()
        ahs._add_speed_args(parser)  # type: ignore
        args = parser.parse_args(["--max-speed", "15.0", "--verbose"])
        assert abs(args.max_speed - 15.0) < 1e-9
        assert args.verbose is True

    def test_add_filter_args(self):
        """Should add filter arguments to parser."""
        parser = argparse.ArgumentParser()
        ahs._add_filter_args(parser)  # type: ignore
        args = parser.parse_args(["--no-progress", "--start-date", "20240101"])
        assert args.progress is False
        assert args.start_date == "20240101"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
