"""
Tests for data schemas and models.
"""

import pytest
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.schema import (
    MemoryMetadata,
    Document,
    MemoryChunk,
    QueryFilter,
    QueryResult,
    QueryResponse,
    SourceType,
    DocumentFormat,
    SentimentLabel,
)


class TestMemoryMetadata:
    """Tests for MemoryMetadata model."""

    def test_default_values(self):
        """Test default values are set correctly."""
        metadata = MemoryMetadata(doc_id="test-123")

        assert metadata.doc_id == "test-123"
        assert metadata.chunk_id is not None
        assert metadata.source == SourceType.MANUAL
        assert metadata.participants == []
        assert metadata.topics == []
        assert metadata.custom_tags == []
        assert metadata.language == "en"

    def test_full_metadata(self):
        """Test creating metadata with all fields."""
        metadata = MemoryMetadata(
            doc_id="doc-123",
            chunk_id="chunk-456",
            timestamp=datetime(2024, 1, 15, 10, 0),
            source=SourceType.FIREFLIES,
            participants=["Alice", "Bob"],
            topics=["AI", "planning"],
            entities={"PERSON": ["Alice"], "ORG": ["Acme Corp"]},
            sentiment=0.5,
            sentiment_label=SentimentLabel.POSITIVE,
            custom_tags=["important"],
            conversation_id="conv-789",
            platform="zoom",
            word_count=100,
            token_count=120,
        )

        assert metadata.source == SourceType.FIREFLIES
        assert len(metadata.participants) == 2
        assert metadata.sentiment == 0.5
        assert metadata.entities["PERSON"] == ["Alice"]

    def test_to_chroma_metadata(self):
        """Test conversion to ChromaDB format."""
        metadata = MemoryMetadata(
            doc_id="test",
            participants=["Alice", "Bob"],
            topics=["AI", "ML"],
            sentiment=0.5,
        )

        chroma_meta = metadata.to_chroma_metadata()

        assert chroma_meta["doc_id"] == "test"
        assert chroma_meta["participants"] == "Alice,Bob"
        assert chroma_meta["topics"] == "AI,ML"
        assert chroma_meta["sentiment"] == 0.5
        assert isinstance(chroma_meta["timestamp"], str)

    def test_from_chroma_metadata(self):
        """Test reconstruction from ChromaDB format."""
        chroma_meta = {
            "doc_id": "test",
            "chunk_id": "chunk-1",
            "chunk_index": 0,
            "total_chunks": 1,
            "timestamp": "2024-01-15T10:00:00",
            "source": "manual",
            "source_file": "",
            "participants": "Alice,Bob",
            "topics": "AI,ML",
            "entities_json": "{'PERSON': ['Alice']}",
            "sentiment": 0.5,
            "sentiment_label": "positive",
            "custom_tags": "important,urgent",
            "conversation_id": "",
            "platform": "",
            "language": "en",
            "word_count": 100,
            "token_count": 120,
        }

        metadata = MemoryMetadata.from_chroma_metadata(chroma_meta)

        assert metadata.doc_id == "test"
        assert metadata.participants == ["Alice", "Bob"]
        assert metadata.topics == ["AI", "ML"]
        assert metadata.sentiment == 0.5
        assert metadata.custom_tags == ["important", "urgent"]


class TestDocument:
    """Tests for Document model."""

    def test_create_document(self):
        """Test creating a document."""
        doc = Document(
            content="Test content",
            format=DocumentFormat.PLAIN_TEXT,
        )

        assert doc.content == "Test content"
        assert doc.format == DocumentFormat.PLAIN_TEXT
        assert doc.id is not None

    def test_document_with_metadata(self):
        """Test creating document with metadata."""
        metadata = MemoryMetadata(
            doc_id="doc-1",
            participants=["Alice"],
        )

        doc = Document(
            content="Meeting notes",
            format=DocumentFormat.MARKDOWN,
            metadata=metadata,
        )

        assert doc.metadata.participants == ["Alice"]


class TestMemoryChunk:
    """Tests for MemoryChunk model."""

    def test_create_chunk(self):
        """Test creating a memory chunk."""
        metadata = MemoryMetadata(doc_id="doc-1")

        chunk = MemoryChunk(
            text="Chunk content",
            metadata=metadata,
        )

        assert chunk.text == "Chunk content"
        assert chunk.id is not None
        assert chunk.embedding is None

    def test_chunk_with_embedding(self):
        """Test chunk with embedding."""
        metadata = MemoryMetadata(doc_id="doc-1")

        chunk = MemoryChunk(
            text="Chunk content",
            metadata=metadata,
            embedding=[0.1, 0.2, 0.3],
        )

        assert chunk.embedding == [0.1, 0.2, 0.3]


class TestQueryFilter:
    """Tests for QueryFilter model."""

    def test_empty_filter(self):
        """Test creating empty filter."""
        filter = QueryFilter()

        assert filter.start_date is None
        assert filter.end_date is None
        assert filter.topics is None
        assert filter.participants is None

    def test_full_filter(self):
        """Test creating filter with all fields."""
        filter = QueryFilter(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            topics=["AI", "ML"],
            participants=["Alice"],
            custom_tags=["important"],
            source=SourceType.FIREFLIES,
            min_sentiment=-0.5,
            max_sentiment=0.5,
        )

        assert filter.start_date.year == 2024
        assert "AI" in filter.topics
        assert filter.min_sentiment == -0.5


class TestQueryResult:
    """Tests for QueryResult model."""

    def test_create_result(self):
        """Test creating a query result."""
        metadata = MemoryMetadata(doc_id="doc-1")

        result = QueryResult(
            chunk_id="chunk-1",
            text="Matched content",
            score=0.85,
            metadata=metadata,
        )

        assert result.chunk_id == "chunk-1"
        assert result.score == 0.85
        assert result.highlights is None


class TestQueryResponse:
    """Tests for QueryResponse model."""

    def test_empty_response(self):
        """Test creating empty response."""
        response = QueryResponse(query="Test query")

        assert response.query == "Test query"
        assert response.results == []
        assert response.total_results == 0

    def test_response_with_results(self):
        """Test response with results."""
        metadata = MemoryMetadata(doc_id="doc-1")
        result = QueryResult(
            chunk_id="chunk-1",
            text="Content",
            score=0.9,
            metadata=metadata,
        )

        response = QueryResponse(
            query="Test",
            results=[result],
            total_results=1,
            processing_time_ms=100.5,
            synthesis="Summary of results",
        )

        assert len(response.results) == 1
        assert response.synthesis == "Summary of results"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
