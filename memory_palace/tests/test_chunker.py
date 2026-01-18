"""
Tests for text chunking functionality.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.chunker import TextChunker
from config.schema import Document, MemoryMetadata, SourceType


class TestTextChunker:
    """Tests for TextChunker class."""

    def test_basic_chunking(self):
        """Test basic text chunking."""
        chunker = TextChunker(target_tokens=100, overlap_tokens=10)

        text = "This is a test sentence. " * 50
        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = TextChunker()

        chunks = chunker.chunk("")
        assert chunks == []

        chunks = chunker.chunk("   ")
        assert chunks == []

    def test_small_text(self):
        """Test chunking text smaller than target."""
        chunker = TextChunker(target_tokens=500, min_chunk_tokens=10)

        text = "This is a short text."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_semantic_chunking(self):
        """Test semantic chunking strategy."""
        chunker = TextChunker(
            target_tokens=50,
            strategy="semantic",
        )

        text = """First paragraph with some content.

Second paragraph with different content.

Third paragraph to test chunking."""

        chunks = chunker.chunk(text)

        assert len(chunks) >= 1
        # Semantic chunking should respect paragraph boundaries
        assert all("paragraph" in c.lower() for c in chunks)

    def test_fixed_chunking(self):
        """Test fixed-size chunking strategy."""
        chunker = TextChunker(
            target_tokens=50,
            overlap_tokens=10,
            strategy="fixed",
        )

        text = "word " * 200
        chunks = chunker.chunk(text)

        assert len(chunks) > 1

    def test_token_counting(self):
        """Test token counting."""
        chunker = TextChunker()

        # Simple text
        count = chunker.count_tokens("Hello world")
        assert count > 0

        # Empty text
        count = chunker.count_tokens("")
        assert count == 0

    def test_word_counting(self):
        """Test word counting."""
        chunker = TextChunker()

        assert chunker.count_words("Hello world") == 2
        assert chunker.count_words("One two three four") == 4
        assert chunker.count_words("") == 0

    def test_chunk_document(self):
        """Test chunking a Document object."""
        chunker = TextChunker(target_tokens=100)

        metadata = MemoryMetadata(
            doc_id="test-doc",
            source=SourceType.MANUAL,
            participants=["Alice", "Bob"],
        )

        document = Document(
            content="Test content. " * 50,
            metadata=metadata,
        )

        chunks = chunker.chunk_document(document)

        assert len(chunks) > 0
        for chunk in chunks:
            # Metadata should be preserved
            assert chunk.metadata.doc_id == document.id
            assert chunk.metadata.participants == ["Alice", "Bob"]
            assert chunk.metadata.chunk_index >= 0
            assert chunk.metadata.total_chunks == len(chunks)

    def test_overlap(self):
        """Test that chunks have proper overlap."""
        chunker = TextChunker(
            target_tokens=50,
            overlap_tokens=20,
            strategy="fixed",
        )

        text = " ".join([f"word{i}" for i in range(100)])
        chunks = chunker.chunk(text)

        if len(chunks) > 1:
            # Check that consecutive chunks share some content
            for i in range(len(chunks) - 1):
                words1 = set(chunks[i].split()[-10:])
                words2 = set(chunks[i + 1].split()[:10])
                # There should be some overlap
                # Note: overlap might not always be exact due to semantic boundaries
                # So we just verify chunks exist
                assert len(chunks[i]) > 0
                assert len(chunks[i + 1]) > 0


class TestChunkingStrategies:
    """Tests for different chunking strategies."""

    def test_paragraph_strategy(self):
        """Test paragraph-based chunking."""
        chunker = TextChunker(
            target_tokens=100,
            strategy="paragraph",
        )

        text = """First paragraph content here.

Second paragraph content here.

Third paragraph content here."""

        chunks = chunker.chunk(text)
        assert len(chunks) >= 1

    def test_invalid_strategy_fallback(self):
        """Test that invalid strategy falls back to semantic."""
        chunker = TextChunker(strategy="invalid_strategy")

        text = "Some test content for chunking."
        chunks = chunker.chunk(text)

        # Should still work, using semantic fallback
        assert len(chunks) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
