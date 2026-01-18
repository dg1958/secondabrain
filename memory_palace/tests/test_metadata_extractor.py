"""
Tests for metadata extraction functionality.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.metadata_extractor import MetadataExtractor, extract_metadata
from config.schema import MemoryMetadata, SentimentLabel


class TestMetadataExtractor:
    """Tests for MetadataExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a metadata extractor."""
        return MetadataExtractor(
            enable_ner=True,
            enable_sentiment=True,
            enable_topics=True,
        )

    def test_extract_participants_from_transcript(self, extractor):
        """Test extracting participants from transcript format."""
        text = """Alice: Hello, how are you?

Bob: I'm doing well, thanks!

Alice: Great to hear."""

        participants = extractor.extract_participants(text)

        assert "Alice" in participants
        assert "Bob" in participants

    def test_extract_topics(self, extractor):
        """Test topic extraction."""
        text = """We discussed machine learning applications in healthcare.
The neural network model showed promising results for diagnosis.
Deep learning techniques improved accuracy significantly."""

        topics = extractor.extract_topics(text, max_topics=5)

        assert len(topics) <= 5
        # Should extract relevant keywords
        assert any("learning" in t.lower() or "machine" in t.lower() for t in topics)

    def test_extract_sentiment_positive(self, extractor):
        """Test sentiment analysis for positive text."""
        text = "This is amazing! I love the results. Great work everyone!"

        score, label = extractor.extract_sentiment(text)

        assert score > 0
        assert label in [SentimentLabel.POSITIVE, SentimentLabel.VERY_POSITIVE]

    def test_extract_sentiment_negative(self, extractor):
        """Test sentiment analysis for negative text."""
        text = "This is terrible. I hate the results. Complete failure."

        score, label = extractor.extract_sentiment(text)

        assert score < 0
        assert label in [SentimentLabel.NEGATIVE, SentimentLabel.VERY_NEGATIVE]

    def test_extract_sentiment_neutral(self, extractor):
        """Test sentiment analysis for neutral text."""
        text = "The meeting was held on Tuesday. We discussed the project timeline."

        score, label = extractor.extract_sentiment(text)

        # Should be relatively neutral
        assert -0.3 <= score <= 0.3

    def test_extract_entities(self, extractor):
        """Test named entity extraction."""
        if not extractor.is_ner_available:
            pytest.skip("spaCy model not available")

        text = "John Smith works at Google in New York. He met with Sarah on Monday."

        entities = extractor.extract_entities(text)

        # Should extract some entities
        assert isinstance(entities, dict)
        # Exact entities depend on spaCy model, but should have some

    def test_extract_all(self, extractor):
        """Test extracting all metadata at once."""
        text = """Alice: I think the project is going really well!

Bob: Agreed, the machine learning model is performing great.

Alice: Let's schedule a meeting with the team at Google next week."""

        metadata = extractor.extract_all(text)

        assert "participants" in metadata
        assert "topics" in metadata
        assert "sentiment" in metadata

    def test_enrich_metadata(self, extractor):
        """Test enriching existing metadata."""
        text = "Great progress on the AI project today!"

        existing = MemoryMetadata(
            doc_id="test",
            participants=["Alice"],
            topics=["planning"],
        )

        enriched = extractor.enrich_metadata(text, existing)

        # Should preserve existing participants
        assert "Alice" in enriched.participants
        # Should add sentiment
        assert enriched.sentiment is not None

    def test_topic_extraction_min_length(self, extractor):
        """Test that short words are filtered from topics."""
        text = "AI ML NLP are important. Machine learning is great."

        topics = extractor.extract_topics(text, min_length=3)

        # Two-letter words should be filtered
        assert "AI" not in topics
        assert "ML" not in topics

    def test_empty_text(self, extractor):
        """Test handling empty text."""
        metadata = extractor.extract_all("")

        assert "participants" in metadata
        assert metadata["participants"] == []


class TestConvenienceFunction:
    """Tests for the extract_metadata function."""

    def test_basic_extraction(self):
        """Test the convenience function."""
        text = "John discussed the project with Sarah."

        result = extract_metadata(text)

        assert isinstance(result, dict)
        assert "participants" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
