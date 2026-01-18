"""
Transcript parser for various input formats.

This module provides:
- Plain text parsing
- JSON transcript parsing
- Markdown parsing
- Fireflies.ai transcript format parsing
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from config.schema import (
    Document,
    DocumentFormat,
    FirefliesTranscript,
    MemoryMetadata,
    SourceType,
)


class TranscriptParser:
    """
    Parser for various transcript and document formats.

    Supports:
    - Plain text files (.txt)
    - JSON transcripts (generic and Fireflies format)
    - Markdown files (.md)
    """

    def __init__(self):
        """Initialize the transcript parser."""
        self._format_handlers = {
            DocumentFormat.PLAIN_TEXT: self._parse_plain_text,
            DocumentFormat.JSON_TRANSCRIPT: self._parse_json_transcript,
            DocumentFormat.MARKDOWN: self._parse_markdown,
            DocumentFormat.FIREFLIES_JSON: self._parse_fireflies_json,
        }

    def detect_format(self, file_path: Union[str, Path]) -> DocumentFormat:
        """
        Detect the format of a file based on extension and content.

        Args:
            file_path: Path to the file

        Returns:
            Detected DocumentFormat
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == ".md":
            return DocumentFormat.MARKDOWN
        elif extension == ".json":
            # Try to detect JSON type
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check for Fireflies format
                if self._is_fireflies_format(data):
                    return DocumentFormat.FIREFLIES_JSON

                return DocumentFormat.JSON_TRANSCRIPT
            except (json.JSONDecodeError, IOError):
                return DocumentFormat.PLAIN_TEXT
        else:
            return DocumentFormat.PLAIN_TEXT

    def _is_fireflies_format(self, data: Any) -> bool:
        """Check if JSON data matches Fireflies format."""
        if isinstance(data, dict):
            # Fireflies typically has these fields
            fireflies_fields = {"id", "title", "transcript", "participants"}
            return bool(fireflies_fields & set(data.keys()))
        return False

    def parse(
        self,
        content: str,
        format: DocumentFormat,
        source_file: Optional[str] = None,
        **kwargs,
    ) -> Document:
        """
        Parse content into a Document.

        Args:
            content: Raw content to parse
            format: Format of the content
            source_file: Original filename
            **kwargs: Additional metadata fields

        Returns:
            Parsed Document object
        """
        handler = self._format_handlers.get(format)
        if handler is None:
            logger.warning(f"Unknown format {format}, treating as plain text")
            handler = self._parse_plain_text

        return handler(content, source_file=source_file, **kwargs)

    def parse_file(
        self,
        file_path: Union[str, Path],
        format: Optional[DocumentFormat] = None,
        **kwargs,
    ) -> Document:
        """
        Parse a file into a Document.

        Args:
            file_path: Path to the file
            format: Optional format override
            **kwargs: Additional metadata fields

        Returns:
            Parsed Document object
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect format if not specified
        if format is None:
            format = self.detect_format(path)

        # Read file content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()

        return self.parse(
            content,
            format=format,
            source_file=str(path.name),
            **kwargs,
        )

    def _parse_plain_text(
        self,
        content: str,
        source_file: Optional[str] = None,
        **kwargs,
    ) -> Document:
        """
        Parse plain text content.

        Args:
            content: Plain text content
            source_file: Source filename
            **kwargs: Additional metadata

        Returns:
            Document object
        """
        # Try to extract a timestamp from the filename
        timestamp = kwargs.pop("timestamp", None)
        if timestamp is None and source_file:
            timestamp = self._extract_date_from_filename(source_file)
        if timestamp is None:
            timestamp = datetime.now()

        # Create metadata
        metadata = MemoryMetadata(
            doc_id=kwargs.get("doc_id", ""),
            timestamp=timestamp,
            source=kwargs.get("source", SourceType.IMPORT),
            source_file=source_file,
            participants=kwargs.get("participants", []),
            custom_tags=kwargs.get("custom_tags", []),
        )

        # Extract participants from content
        participants = self._extract_speakers(content)
        if participants:
            metadata.participants = list(set(metadata.participants + participants))

        doc = Document(
            content=content.strip(),
            format=DocumentFormat.PLAIN_TEXT,
            metadata=metadata,
        )
        doc.metadata.doc_id = doc.id

        return doc

    def _parse_markdown(
        self,
        content: str,
        source_file: Optional[str] = None,
        **kwargs,
    ) -> Document:
        """
        Parse markdown content.

        Extracts metadata from YAML frontmatter if present.

        Args:
            content: Markdown content
            source_file: Source filename
            **kwargs: Additional metadata

        Returns:
            Document object
        """
        # Check for YAML frontmatter
        frontmatter = {}
        body = content

        frontmatter_match = re.match(
            r"^---\s*\n(.*?)\n---\s*\n(.*)$",
            content,
            re.DOTALL,
        )

        if frontmatter_match:
            try:
                import yaml
                frontmatter = yaml.safe_load(frontmatter_match.group(1)) or {}
                body = frontmatter_match.group(2)
            except Exception as e:
                logger.warning(f"Failed to parse YAML frontmatter: {e}")

        # Extract metadata from frontmatter
        timestamp = kwargs.pop("timestamp", None)
        if timestamp is None:
            timestamp = frontmatter.get("date") or frontmatter.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = None
        if timestamp is None and source_file:
            timestamp = self._extract_date_from_filename(source_file)
        if timestamp is None:
            timestamp = datetime.now()

        # Create metadata
        metadata = MemoryMetadata(
            doc_id=kwargs.get("doc_id", ""),
            timestamp=timestamp,
            source=kwargs.get("source", SourceType.IMPORT),
            source_file=source_file,
            participants=frontmatter.get("participants", kwargs.get("participants", [])),
            topics=frontmatter.get("topics", kwargs.get("topics", [])),
            custom_tags=frontmatter.get("tags", kwargs.get("custom_tags", [])),
        )

        doc = Document(
            content=body.strip(),
            format=DocumentFormat.MARKDOWN,
            metadata=metadata,
        )
        doc.metadata.doc_id = doc.id

        return doc

    def _parse_json_transcript(
        self,
        content: str,
        source_file: Optional[str] = None,
        **kwargs,
    ) -> Document:
        """
        Parse generic JSON transcript format.

        Expected format:
        {
            "id": "optional_id",
            "title": "Optional title",
            "timestamp": "2024-01-15T10:00:00",
            "participants": ["Alice", "Bob"],
            "transcript": "Full transcript text",
            // or
            "messages": [
                {"speaker": "Alice", "text": "Hello", "timestamp": "..."},
                ...
            ]
        }

        Args:
            content: JSON content string
            source_file: Source filename
            **kwargs: Additional metadata

        Returns:
            Document object
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            # Fall back to plain text
            return self._parse_plain_text(content, source_file, **kwargs)

        # Extract transcript text
        if isinstance(data, dict):
            if "transcript" in data:
                text = data["transcript"]
            elif "text" in data:
                text = data["text"]
            elif "content" in data:
                text = data["content"]
            elif "messages" in data:
                # Combine messages into transcript
                messages = data["messages"]
                text = self._format_messages(messages)
            else:
                text = json.dumps(data, indent=2)
        elif isinstance(data, list):
            # Assume list of messages
            text = self._format_messages(data)
        else:
            text = str(data)

        # Extract metadata
        timestamp = kwargs.pop("timestamp", None)
        if timestamp is None and isinstance(data, dict):
            ts_str = data.get("timestamp") or data.get("date") or data.get("created_at")
            if ts_str:
                try:
                    timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

        if timestamp is None:
            timestamp = datetime.now()

        participants = kwargs.get("participants", [])
        if isinstance(data, dict) and "participants" in data:
            participants = data["participants"]

        metadata = MemoryMetadata(
            doc_id=data.get("id", "") if isinstance(data, dict) else "",
            timestamp=timestamp,
            source=kwargs.get("source", SourceType.IMPORT),
            source_file=source_file,
            participants=participants,
            conversation_id=data.get("conversation_id") if isinstance(data, dict) else None,
            platform=data.get("platform") if isinstance(data, dict) else None,
        )

        doc = Document(
            content=text.strip(),
            format=DocumentFormat.JSON_TRANSCRIPT,
            metadata=metadata,
        )
        if not doc.metadata.doc_id:
            doc.metadata.doc_id = doc.id

        return doc

    def _parse_fireflies_json(
        self,
        content: str,
        source_file: Optional[str] = None,
        **kwargs,
    ) -> Document:
        """
        Parse Fireflies.ai JSON transcript format.

        Args:
            content: Fireflies JSON content
            source_file: Source filename
            **kwargs: Additional metadata

        Returns:
            Document object
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Fireflies JSON: {e}")
            return self._parse_plain_text(content, source_file, **kwargs)

        # Parse Fireflies transcript
        fireflies = self._parse_fireflies_data(data)

        metadata = MemoryMetadata(
            doc_id=fireflies.id,
            timestamp=fireflies.date,
            source=SourceType.FIREFLIES,
            source_file=source_file,
            participants=fireflies.participants,
            topics=fireflies.keywords or [],
            conversation_id=fireflies.id,
            platform="fireflies",
        )

        # Build full text
        text = fireflies.transcript_text
        if fireflies.summary:
            text = f"Summary: {fireflies.summary}\n\n{text}"

        doc = Document(
            content=text.strip(),
            format=DocumentFormat.FIREFLIES_JSON,
            metadata=metadata,
        )

        return doc

    def _parse_fireflies_data(self, data: Dict[str, Any]) -> FirefliesTranscript:
        """
        Parse Fireflies data dictionary into structured format.

        Args:
            data: Fireflies JSON data

        Returns:
            FirefliesTranscript object
        """
        # Extract timestamp
        date_str = data.get("date") or data.get("dateString") or data.get("created_at")
        if date_str:
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                date = datetime.now()
        else:
            date = datetime.now()

        # Extract transcript text
        transcript_text = data.get("transcript", "")
        if not transcript_text and "sentences" in data:
            # Build from sentences
            sentences = data["sentences"]
            transcript_text = self._format_fireflies_sentences(sentences)

        # Extract participants
        participants = data.get("participants", [])
        if isinstance(participants, list) and participants:
            if isinstance(participants[0], dict):
                participants = [p.get("name", str(p)) for p in participants]

        return FirefliesTranscript(
            id=data.get("id", str(hash(transcript_text))[:16]),
            title=data.get("title", "Untitled Meeting"),
            date=date,
            duration_minutes=data.get("duration", 0),
            participants=participants,
            transcript_text=transcript_text,
            summary=data.get("summary"),
            action_items=data.get("action_items"),
            keywords=data.get("keywords"),
            meeting_url=data.get("meeting_url"),
        )

    def _format_messages(self, messages: List[Dict]) -> str:
        """
        Format a list of messages into transcript text.

        Args:
            messages: List of message dictionaries

        Returns:
            Formatted transcript text
        """
        lines = []
        for msg in messages:
            speaker = msg.get("speaker") or msg.get("from") or msg.get("name") or "Unknown"
            text = msg.get("text") or msg.get("content") or msg.get("message") or ""
            if text:
                lines.append(f"{speaker}: {text}")

        return "\n\n".join(lines)

    def _format_fireflies_sentences(self, sentences: List[Dict]) -> str:
        """
        Format Fireflies sentences into transcript text.

        Args:
            sentences: List of Fireflies sentence objects

        Returns:
            Formatted transcript text
        """
        lines = []
        current_speaker = None

        for sentence in sentences:
            speaker = sentence.get("speaker_name") or sentence.get("speaker")
            text = sentence.get("text", "")

            if speaker and speaker != current_speaker:
                if lines:
                    lines.append("")  # Add blank line for speaker change
                current_speaker = speaker

            if text:
                if speaker:
                    lines.append(f"{speaker}: {text}")
                else:
                    lines.append(text)

        return "\n".join(lines)

    def _extract_speakers(self, text: str) -> List[str]:
        """
        Extract speaker names from transcript text.

        Args:
            text: Transcript text

        Returns:
            List of speaker names
        """
        speakers = set()

        # Pattern: "Name:" at line start
        pattern = r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*:"
        matches = re.findall(pattern, text, re.MULTILINE)
        speakers.update(matches)

        return sorted(list(speakers))

    def _extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Try to extract a date from a filename.

        Args:
            filename: Filename to parse

        Returns:
            Extracted datetime or None
        """
        # Common date patterns in filenames
        patterns = [
            r"(\d{4})-(\d{2})-(\d{2})",  # YYYY-MM-DD
            r"(\d{4})(\d{2})(\d{2})",     # YYYYMMDD
            r"(\d{2})-(\d{2})-(\d{4})",   # DD-MM-YYYY
            r"(\d{2})(\d{2})(\d{4})",     # DDMMYYYY
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                groups = match.groups()
                try:
                    if len(groups[0]) == 4:  # Year first
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    else:  # Day first
                        return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
                except ValueError:
                    continue

        return None


# Convenience functions
_parser: Optional[TranscriptParser] = None


def get_parser() -> TranscriptParser:
    """Get the global transcript parser instance."""
    global _parser
    if _parser is None:
        _parser = TranscriptParser()
    return _parser


def parse_transcript(
    content: str,
    format: DocumentFormat = DocumentFormat.PLAIN_TEXT,
    **kwargs,
) -> Document:
    """
    Convenience function to parse transcript content.

    Args:
        content: Raw content
        format: Document format
        **kwargs: Additional metadata

    Returns:
        Parsed Document
    """
    return get_parser().parse(content, format, **kwargs)


def parse_file(file_path: Union[str, Path], **kwargs) -> Document:
    """
    Convenience function to parse a file.

    Args:
        file_path: Path to file
        **kwargs: Additional metadata

    Returns:
        Parsed Document
    """
    return get_parser().parse_file(file_path, **kwargs)
