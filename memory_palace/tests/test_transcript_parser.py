"""
Tests for transcript parsing functionality.
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.transcript_parser import TranscriptParser, parse_transcript
from config.schema import DocumentFormat, SourceType


class TestTranscriptParser:
    """Tests for TranscriptParser class."""

    @pytest.fixture
    def parser(self):
        """Create a transcript parser."""
        return TranscriptParser()

    def test_parse_plain_text(self, parser):
        """Test parsing plain text."""
        content = """This is a simple transcript.

Speaker 1: Hello everyone.
Speaker 2: Hi there!"""

        doc = parser.parse(content, DocumentFormat.PLAIN_TEXT)

        assert doc.content == content.strip()
        assert doc.format == DocumentFormat.PLAIN_TEXT
        assert doc.metadata.source == SourceType.IMPORT

    def test_parse_markdown(self, parser):
        """Test parsing markdown content."""
        content = """---
title: Meeting Notes
date: 2024-01-15
participants:
  - Alice
  - Bob
tags:
  - meeting
  - planning
---

# Meeting Notes

We discussed the project timeline."""

        doc = parser.parse(content, DocumentFormat.MARKDOWN)

        assert "Meeting Notes" in doc.content
        assert doc.format == DocumentFormat.MARKDOWN
        assert "Alice" in doc.metadata.participants
        assert "Bob" in doc.metadata.participants
        assert "meeting" in doc.metadata.custom_tags

    def test_parse_json_transcript(self, parser):
        """Test parsing JSON transcript format."""
        data = {
            "id": "transcript-123",
            "timestamp": "2024-01-15T10:00:00",
            "participants": ["Alice", "Bob"],
            "transcript": "Alice: Hello\nBob: Hi there!",
        }
        content = json.dumps(data)

        doc = parser.parse(content, DocumentFormat.JSON_TRANSCRIPT)

        assert "Hello" in doc.content
        assert doc.format == DocumentFormat.JSON_TRANSCRIPT
        assert "Alice" in doc.metadata.participants
        assert "Bob" in doc.metadata.participants

    def test_parse_json_with_messages(self, parser):
        """Test parsing JSON with messages array."""
        data = {
            "messages": [
                {"speaker": "Alice", "text": "Hello everyone!"},
                {"speaker": "Bob", "text": "Hi Alice!"},
                {"speaker": "Alice", "text": "Let's begin."},
            ]
        }
        content = json.dumps(data)

        doc = parser.parse(content, DocumentFormat.JSON_TRANSCRIPT)

        assert "Hello everyone!" in doc.content
        assert "Hi Alice!" in doc.content

    def test_detect_format_txt(self, parser):
        """Test format detection for .txt files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Plain text content")
            temp_path = f.name

        try:
            format = parser.detect_format(temp_path)
            assert format == DocumentFormat.PLAIN_TEXT
        finally:
            Path(temp_path).unlink()

    def test_detect_format_md(self, parser):
        """Test format detection for .md files."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Markdown content")
            temp_path = f.name

        try:
            format = parser.detect_format(temp_path)
            assert format == DocumentFormat.MARKDOWN
        finally:
            Path(temp_path).unlink()

    def test_detect_format_json(self, parser):
        """Test format detection for .json files."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"transcript": "content"}, f)
            temp_path = f.name

        try:
            format = parser.detect_format(temp_path)
            assert format == DocumentFormat.JSON_TRANSCRIPT
        finally:
            Path(temp_path).unlink()

    def test_parse_file(self, parser):
        """Test parsing a file from disk."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("Test transcript content\n\nAlice: Hello!")
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            assert "Test transcript content" in doc.content
            assert doc.metadata.source_file is not None
        finally:
            Path(temp_path).unlink()

    def test_extract_speakers(self, parser):
        """Test extracting speakers from transcript."""
        content = """John: Hello everyone.
Sarah: Hi John, how are you?
John: I'm doing well.
Michael: Good morning!"""

        speakers = parser._extract_speakers(content)

        assert "John" in speakers
        assert "Sarah" in speakers
        assert "Michael" in speakers

    def test_extract_date_from_filename(self, parser):
        """Test extracting date from filename."""
        # YYYY-MM-DD format
        date = parser._extract_date_from_filename("meeting_2024-01-15_notes.txt")
        assert date is not None
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 15

        # YYYYMMDD format
        date = parser._extract_date_from_filename("transcript_20240215.json")
        assert date is not None
        assert date.year == 2024
        assert date.month == 2
        assert date.day == 15

    def test_parse_fireflies_json(self, parser):
        """Test parsing Fireflies.ai JSON format."""
        data = {
            "id": "fireflies-123",
            "title": "Team Meeting",
            "date": "2024-01-15T10:00:00Z",
            "participants": [{"name": "Alice"}, {"name": "Bob"}],
            "sentences": [
                {"speaker_name": "Alice", "text": "Welcome everyone."},
                {"speaker_name": "Bob", "text": "Thanks for having us."},
            ],
            "summary": {"overview": "Discussion about Q1 goals."},
        }
        content = json.dumps(data)

        doc = parser.parse(content, DocumentFormat.FIREFLIES_JSON)

        assert doc.format == DocumentFormat.FIREFLIES_JSON
        assert "Welcome everyone" in doc.content
        assert doc.metadata.source == SourceType.FIREFLIES

    def test_invalid_json_fallback(self, parser):
        """Test that invalid JSON falls back to plain text."""
        content = "This is not valid JSON { broken"

        doc = parser.parse(content, DocumentFormat.JSON_TRANSCRIPT)

        # Should fall back to plain text
        assert doc.content == content.strip()


class TestConvenienceFunction:
    """Tests for the parse_transcript function."""

    def test_basic_parsing(self):
        """Test the convenience function."""
        content = "Simple transcript text."

        doc = parse_transcript(content)

        assert doc.content == content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
