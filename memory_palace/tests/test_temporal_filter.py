"""
Tests for temporal filtering functionality.
"""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from query.temporal_filter import TemporalFilter, parse_temporal_expression


class TestTemporalFilter:
    """Tests for TemporalFilter class."""

    @pytest.fixture
    def filter(self):
        """Create a temporal filter with fixed reference date."""
        # Use a fixed date for reproducible tests
        reference = datetime(2024, 6, 15, 12, 0, 0)
        return TemporalFilter(reference_date=reference)

    def test_last_n_days(self, filter):
        """Test 'last N days' parsing."""
        start, end = filter.parse("last 7 days")

        assert start is not None
        assert end is not None
        assert end >= start
        assert (end - start).days == 7

    def test_last_n_weeks(self, filter):
        """Test 'last N weeks' parsing."""
        start, end = filter.parse("last 2 weeks")

        assert start is not None
        assert end is not None
        assert (end - start).days == 14

    def test_last_n_months(self, filter):
        """Test 'last N months' parsing."""
        start, end = filter.parse("last 3 months")

        assert start is not None
        assert end is not None
        # Approximately 3 months
        assert (end - start).days >= 85

    def test_last_week(self, filter):
        """Test 'last week' parsing."""
        start, end = filter.parse("last week")

        assert start is not None
        assert end is not None
        # Should be 7 days
        assert (end - start).days == 6

    def test_last_month(self, filter):
        """Test 'last month' parsing."""
        start, end = filter.parse("last month")

        assert start is not None
        assert end is not None
        # Should be a full month
        assert start.month == 5  # May (previous month from June)

    def test_last_year(self, filter):
        """Test 'last year' parsing."""
        start, end = filter.parse("last year")

        assert start is not None
        assert end is not None
        assert start.year == 2023
        assert end.year == 2023

    def test_this_week(self, filter):
        """Test 'this week' parsing."""
        start, end = filter.parse("this week")

        assert start is not None
        assert end is not None

    def test_this_month(self, filter):
        """Test 'this month' parsing."""
        start, end = filter.parse("this month")

        assert start is not None
        assert end is not None
        assert start.month == 6
        assert start.day == 1

    def test_this_year(self, filter):
        """Test 'this year' parsing."""
        start, end = filter.parse("this year")

        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1

    def test_yesterday(self, filter):
        """Test 'yesterday' parsing."""
        start, end = filter.parse("yesterday")

        assert start is not None
        assert end is not None
        assert start.day == 14
        assert end.day == 14

    def test_today(self, filter):
        """Test 'today' parsing."""
        start, end = filter.parse("today")

        assert start is not None
        assert end is not None
        assert start.day == 15

    def test_year_range(self, filter):
        """Test 'between YYYY and YYYY' parsing."""
        start, end = filter.parse("between 2022 and 2024")

        assert start is not None
        assert end is not None
        assert start.year == 2022
        assert end.year == 2024

    def test_year_range_hyphen(self, filter):
        """Test 'between YYYY-YYYY' parsing."""
        start, end = filter.parse("between 2020-2023")

        assert start is not None
        assert end is not None
        assert start.year == 2020
        assert end.year == 2023

    def test_single_year(self, filter):
        """Test 'in YYYY' parsing."""
        start, end = filter.parse("in 2023")

        assert start is not None
        assert end is not None
        assert start.year == 2023
        assert start.month == 1
        assert end.year == 2023
        assert end.month == 12

    def test_month_year(self, filter):
        """Test 'in Month YYYY' parsing."""
        start, end = filter.parse("in January 2024")

        assert start is not None
        assert end is not None
        assert start.year == 2024
        assert start.month == 1
        assert end.month == 1

    def test_n_days_ago(self, filter):
        """Test 'N days ago' parsing."""
        start, end = filter.parse("5 days ago")

        assert start is not None
        assert end is not None
        assert start.day == 10

    def test_extract_temporal_from_query(self, filter):
        """Test extracting temporal expression from a query."""
        query = "What did I discuss about AI last week?"
        cleaned, start, end = filter.extract_temporal_from_query(query)

        assert "last week" not in cleaned.lower()
        assert start is not None
        assert end is not None

    def test_no_temporal_expression(self, filter):
        """Test query with no temporal expression."""
        query = "What are my notes about machine learning?"
        cleaned, start, end = filter.extract_temporal_from_query(query)

        assert cleaned.strip() == query
        assert start is None
        assert end is None

    def test_format_range(self, filter):
        """Test date range formatting."""
        # Same day
        start = datetime(2024, 1, 15)
        end = datetime(2024, 1, 15, 23, 59)
        result = filter.format_range(start, end)
        assert "January 15, 2024" in result

        # No dates
        result = filter.format_range(None, None)
        assert result == "all time"


class TestConvenienceFunction:
    """Tests for the parse_temporal_expression function."""

    def test_basic_parsing(self):
        """Test the convenience function."""
        start, end = parse_temporal_expression("last 30 days")

        assert start is not None
        assert end is not None

    def test_with_custom_reference(self):
        """Test with custom reference date."""
        reference = datetime(2024, 1, 1)
        start, end = parse_temporal_expression("last week", reference_date=reference)

        assert start is not None
        # Should be relative to January 1, 2024
        assert start.year == 2023


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
