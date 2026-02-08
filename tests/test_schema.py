"""Tests for pymessage.schema module."""

import pandas as pd
import pytest

from pymessage.schema import convert_apple_timestamp, parse_reaction_type


class TestConvertAppleTimestamp:
    """Tests for convert_apple_timestamp function."""

    def test_none_input(self):
        """Test that None input returns None."""
        assert convert_apple_timestamp(None) is None

    def test_zero_input(self):
        """Test that zero input returns None."""
        assert convert_apple_timestamp(0) is None

    def test_seconds_format(self):
        """Test conversion of seconds-based timestamps (older iOS)."""
        # 629990400 seconds since 2001-01-01 = 2020-12-18
        result = convert_apple_timestamp(629990400)
        assert isinstance(result, pd.Timestamp)
        assert result.year == 2020
        assert result.month == 12
        assert result.day == 18

    def test_nanoseconds_format(self):
        """Test conversion of nanoseconds-based timestamps (modern iOS)."""
        # 629990400000000000 nanoseconds since 2001-01-01 = 2020-12-18
        result = convert_apple_timestamp(629990400000000000)
        assert isinstance(result, pd.Timestamp)
        assert result.year == 2020
        assert result.month == 12
        assert result.day == 18

    def test_epoch_start(self):
        """Test that timestamp 1 gives date just after 2001-01-01."""
        result = convert_apple_timestamp(1)
        assert result.year == 2001
        assert result.month == 1

    def test_timezone_is_utc(self):
        """Test that returned timestamps are in UTC."""
        result = convert_apple_timestamp(629990400)
        assert result.tz is not None
        assert str(result.tz) == "UTC"


class TestParseReactionType:
    """Tests for parse_reaction_type function."""

    def test_none_input(self):
        """Test that None input returns (None, None)."""
        assert parse_reaction_type(None) == (None, None)

    def test_zero_input(self):
        """Test that zero input returns (None, None)."""
        assert parse_reaction_type(0) == (None, None)

    def test_loved_add(self):
        """Test parsing 'loved' reaction addition."""
        reaction_type, action = parse_reaction_type(2000)
        assert reaction_type == "loved"
        assert action == "add"

    def test_liked_add(self):
        """Test parsing 'liked' reaction addition."""
        reaction_type, action = parse_reaction_type(2001)
        assert reaction_type == "liked"
        assert action == "add"

    def test_disliked_add(self):
        """Test parsing 'disliked' reaction addition."""
        reaction_type, action = parse_reaction_type(2002)
        assert reaction_type == "disliked"
        assert action == "add"

    def test_laughed_add(self):
        """Test parsing 'laughed' reaction addition."""
        reaction_type, action = parse_reaction_type(2003)
        assert reaction_type == "laughed"
        assert action == "add"

    def test_emphasized_add(self):
        """Test parsing 'emphasized' reaction addition."""
        reaction_type, action = parse_reaction_type(2004)
        assert reaction_type == "emphasized"
        assert action == "add"

    def test_questioned_add(self):
        """Test parsing 'questioned' reaction addition."""
        reaction_type, action = parse_reaction_type(2005)
        assert reaction_type == "questioned"
        assert action == "add"

    def test_loved_remove(self):
        """Test parsing 'loved' reaction removal."""
        reaction_type, action = parse_reaction_type(3000)
        assert reaction_type == "loved"
        assert action == "remove"

    def test_liked_remove(self):
        """Test parsing 'liked' reaction removal."""
        reaction_type, action = parse_reaction_type(3001)
        assert reaction_type == "liked"
        assert action == "remove"

    def test_disliked_remove(self):
        """Test parsing 'disliked' reaction removal."""
        reaction_type, action = parse_reaction_type(3002)
        assert reaction_type == "disliked"
        assert action == "remove"

    def test_non_reaction_type(self):
        """Test that non-reaction type codes return (None, None)."""
        assert parse_reaction_type(1) == (None, None)
        assert parse_reaction_type(1000) == (None, None)
        assert parse_reaction_type(4000) == (None, None)
