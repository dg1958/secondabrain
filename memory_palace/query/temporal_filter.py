"""
Temporal filtering for Memory Palace queries.

This module provides:
- Natural language date parsing
- Relative time expressions ("last week", "past 3 months")
- Date range handling
- ISO date parsing
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from loguru import logger


class TemporalFilter:
    """
    Service for parsing and handling temporal expressions in queries.

    Supports:
    - Relative expressions: "last week", "past 3 months", "yesterday"
    - Absolute dates: "2024-01-15", "January 15, 2024"
    - Ranges: "between 2024-2026", "from Jan to March 2024"
    - Named periods: "this year", "last quarter"
    """

    # Patterns for relative time expressions
    RELATIVE_PATTERNS = [
        # "last N days/weeks/months/years"
        (r"last\s+(\d+)\s+(day|week|month|year)s?", "_parse_last_n"),
        # "past N days/weeks/months/years"
        (r"past\s+(\d+)\s+(day|week|month|year)s?", "_parse_last_n"),
        # "N days/weeks/months/years ago"
        (r"(\d+)\s+(day|week|month|year)s?\s+ago", "_parse_n_ago"),
        # "last week/month/year"
        (r"last\s+(week|month|year)", "_parse_last_period"),
        # "this week/month/year"
        (r"this\s+(week|month|year)", "_parse_this_period"),
        # "yesterday"
        (r"\byesterday\b", "_parse_yesterday"),
        # "today"
        (r"\btoday\b", "_parse_today"),
        # "last quarter"
        (r"last\s+quarter", "_parse_last_quarter"),
        # "this quarter"
        (r"this\s+quarter", "_parse_this_quarter"),
    ]

    # Patterns for absolute ranges
    RANGE_PATTERNS = [
        # "between YYYY and YYYY" or "between YYYY-YYYY"
        (r"between\s+(\d{4})\s*(?:and|-)\s*(\d{4})", "_parse_year_range"),
        # "from DATE to DATE"
        (r"from\s+(.+?)\s+to\s+(.+?)(?:\s|$)", "_parse_date_range"),
        # "in YYYY"
        (r"\bin\s+(\d{4})\b", "_parse_single_year"),
        # "in Month YYYY"
        (r"\bin\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", "_parse_month_year"),
    ]

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Initialize the temporal filter.

        Args:
            reference_date: Reference date for relative expressions (default: now)
        """
        self.reference_date = reference_date or datetime.now()

    def parse(self, expression: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse a temporal expression into a date range.

        Args:
            expression: Natural language temporal expression

        Returns:
            Tuple of (start_date, end_date). Either may be None for open-ended ranges.
        """
        expression = expression.lower().strip()

        # Try relative patterns first
        for pattern, handler_name in self.RELATIVE_PATTERNS:
            match = re.search(pattern, expression, re.IGNORECASE)
            if match:
                handler = getattr(self, handler_name)
                result = handler(match)
                if result:
                    return result

        # Try range patterns
        for pattern, handler_name in self.RANGE_PATTERNS:
            match = re.search(pattern, expression, re.IGNORECASE)
            if match:
                handler = getattr(self, handler_name)
                result = handler(match)
                if result:
                    return result

        # Try to parse as a single date
        try:
            parsed_date = date_parser.parse(expression, fuzzy=True)
            # Return the whole day
            start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
            return start, end
        except (ValueError, TypeError):
            pass

        logger.debug(f"Could not parse temporal expression: {expression}")
        return None, None

    def _parse_last_n(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'last N units' or 'past N units'."""
        n = int(match.group(1))
        unit = match.group(2).lower()

        end = self.reference_date

        if unit == "day":
            start = end - timedelta(days=n)
        elif unit == "week":
            start = end - timedelta(weeks=n)
        elif unit == "month":
            start = end - relativedelta(months=n)
        elif unit == "year":
            start = end - relativedelta(years=n)
        else:
            return None, None

        return start, end

    def _parse_n_ago(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'N units ago' as a point in time."""
        n = int(match.group(1))
        unit = match.group(2).lower()

        if unit == "day":
            target = self.reference_date - timedelta(days=n)
        elif unit == "week":
            target = self.reference_date - timedelta(weeks=n)
        elif unit == "month":
            target = self.reference_date - relativedelta(months=n)
        elif unit == "year":
            target = self.reference_date - relativedelta(years=n)
        else:
            return None, None

        # Return the whole day
        start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return start, end

    def _parse_last_period(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'last week/month/year'."""
        period = match.group(1).lower()

        if period == "week":
            # Get the previous week (Monday to Sunday)
            today = self.reference_date.date()
            days_since_monday = today.weekday()
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            start = datetime.combine(last_monday, datetime.min.time())
            end = datetime.combine(last_sunday, datetime.max.time())

        elif period == "month":
            # Get the previous month
            first_of_this_month = self.reference_date.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            start = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = datetime.combine(last_of_prev_month.date(), datetime.max.time())

        elif period == "year":
            # Get the previous year
            prev_year = self.reference_date.year - 1
            start = datetime(prev_year, 1, 1)
            end = datetime(prev_year, 12, 31, 23, 59, 59, 999999)

        else:
            return None, None

        return start, end

    def _parse_this_period(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'this week/month/year'."""
        period = match.group(1).lower()

        if period == "week":
            # Get current week (Monday to now)
            today = self.reference_date.date()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            start = datetime.combine(monday, datetime.min.time())
            end = self.reference_date

        elif period == "month":
            # Get current month
            start = self.reference_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = self.reference_date

        elif period == "year":
            # Get current year
            start = datetime(self.reference_date.year, 1, 1)
            end = self.reference_date

        else:
            return None, None

        return start, end

    def _parse_yesterday(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'yesterday'."""
        yesterday = self.reference_date.date() - timedelta(days=1)
        start = datetime.combine(yesterday, datetime.min.time())
        end = datetime.combine(yesterday, datetime.max.time())
        return start, end

    def _parse_today(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'today'."""
        today = self.reference_date.date()
        start = datetime.combine(today, datetime.min.time())
        end = self.reference_date
        return start, end

    def _parse_last_quarter(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'last quarter'."""
        current_quarter = (self.reference_date.month - 1) // 3
        if current_quarter == 0:
            # Q4 of previous year
            start = datetime(self.reference_date.year - 1, 10, 1)
            end = datetime(self.reference_date.year - 1, 12, 31, 23, 59, 59, 999999)
        else:
            # Previous quarter this year
            quarter_start_month = (current_quarter - 1) * 3 + 1
            start = datetime(self.reference_date.year, quarter_start_month, 1)
            # End of quarter
            end_month = quarter_start_month + 2
            if end_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif end_month in [4, 6, 9, 11]:
                end_day = 30
            else:
                end_day = 28  # Simplified for Feb
            end = datetime(self.reference_date.year, end_month, end_day, 23, 59, 59, 999999)

        return start, end

    def _parse_this_quarter(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'this quarter'."""
        current_quarter = (self.reference_date.month - 1) // 3
        quarter_start_month = current_quarter * 3 + 1
        start = datetime(self.reference_date.year, quarter_start_month, 1)
        end = self.reference_date
        return start, end

    def _parse_year_range(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'between YYYY and YYYY'."""
        start_year = int(match.group(1))
        end_year = int(match.group(2))
        start = datetime(start_year, 1, 1)
        end = datetime(end_year, 12, 31, 23, 59, 59, 999999)
        return start, end

    def _parse_date_range(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'from DATE to DATE'."""
        try:
            start_str = match.group(1).strip()
            end_str = match.group(2).strip()

            start = date_parser.parse(start_str, fuzzy=True)
            end = date_parser.parse(end_str, fuzzy=True)

            # Ensure end is at end of day
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)

            return start, end
        except (ValueError, TypeError):
            return None, None

    def _parse_single_year(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'in YYYY'."""
        year = int(match.group(1))
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31, 23, 59, 59, 999999)
        return start, end

    def _parse_month_year(self, match: re.Match) -> Tuple[datetime, datetime]:
        """Parse 'in Month YYYY'."""
        month_name = match.group(1).lower()
        year = int(match.group(2))

        months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }

        month = months.get(month_name)
        if month is None:
            return None, None

        start = datetime(year, month, 1)
        # Get last day of month
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(microseconds=1)

        return start, end

    def extract_temporal_from_query(
        self,
        query: str,
    ) -> Tuple[str, Optional[datetime], Optional[datetime]]:
        """
        Extract temporal expression from a query and return cleaned query.

        Args:
            query: Full query string

        Returns:
            Tuple of (cleaned_query, start_date, end_date)
        """
        start_date = None
        end_date = None
        cleaned_query = query

        # Try all patterns
        all_patterns = self.RELATIVE_PATTERNS + self.RANGE_PATTERNS

        for pattern, handler_name in all_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                handler = getattr(self, handler_name)
                result = handler(match)
                if result and result[0] is not None:
                    start_date, end_date = result
                    # Remove the temporal expression from query
                    cleaned_query = re.sub(pattern, "", cleaned_query, flags=re.IGNORECASE)
                    break

        # Clean up the query
        cleaned_query = " ".join(cleaned_query.split())

        return cleaned_query, start_date, end_date

    def format_range(
        self,
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> str:
        """
        Format a date range for display.

        Args:
            start: Start date
            end: End date

        Returns:
            Human-readable date range string
        """
        if start is None and end is None:
            return "all time"

        if start is None:
            return f"before {end.strftime('%B %d, %Y')}"

        if end is None:
            return f"after {start.strftime('%B %d, %Y')}"

        # Same day
        if start.date() == end.date():
            return start.strftime("%B %d, %Y")

        # Same month
        if start.year == end.year and start.month == end.month:
            return f"{start.strftime('%B %d')} - {end.strftime('%d, %Y')}"

        # Same year
        if start.year == end.year:
            return f"{start.strftime('%B %d')} - {end.strftime('%B %d, %Y')}"

        # Different years
        return f"{start.strftime('%B %d, %Y')} - {end.strftime('%B %d, %Y')}"


def parse_temporal_expression(
    expression: str,
    reference_date: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Convenience function to parse a temporal expression.

    Args:
        expression: Temporal expression string
        reference_date: Reference date for relative expressions

    Returns:
        Tuple of (start_date, end_date)
    """
    filter = TemporalFilter(reference_date)
    return filter.parse(expression)
