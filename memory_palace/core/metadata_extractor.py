"""
Metadata extraction for Memory Palace.

Extracts entities, topics, and sentiment from memory content
using spaCy NER and keyword extraction.
"""

import logging
import re
from datetime import datetime
from typing import Optional
from collections import Counter

from ..config import get_settings
from .models import Entity, EntityType

logger = logging.getLogger(__name__)

# Try to import spaCy, but provide fallback
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available, NER extraction will be limited")


class MetadataExtractor:
    """
    Extracts metadata from text content.

    Uses spaCy for NER when available, with fallback to simple patterns.
    """

    def __init__(self, spacy_model: Optional[str] = None):
        """
        Initialize the extractor.

        Args:
            spacy_model: spaCy model name (e.g., 'en_core_web_sm')
        """
        settings = get_settings()
        self.spacy_model_name = spacy_model or settings.extraction.spacy_model
        self.entity_types = settings.extraction.entity_types
        self.enable_sentiment = settings.extraction.enable_sentiment
        self.enable_topics = settings.extraction.enable_topics
        self.max_topics = settings.extraction.max_topics

        self._nlp = None
        self._initialized = False

        # Simple topic extraction patterns (fallback)
        self._topic_patterns = [
            r'\b(?:about|regarding|concerning|on the topic of)\s+([a-z\s]+)',
            r'\b(?:discussion of|conversation about)\s+([a-z\s]+)',
        ]

        # Common stopwords for topic extraction
        self._stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'my', 'your', 'his', 'her', 'its', 'our', 'their', 'what', 'which',
            'who', 'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every',
            'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
            'also', 'now', 'here', 'there', 'then', 'once', 'if', 'while',
            'although', 'because', 'until', 'unless', 'since', 'during', 'before',
            'after', 'above', 'below', 'between', 'under', 'again', 'further',
            'having', 'being', 'doing', 'going', 'getting', 'making', 'saying',
            'thinking', 'knowing', 'wanting', 'seeing', 'looking', 'using',
        }

    def _ensure_initialized(self) -> None:
        """Lazy load spaCy model."""
        if self._initialized:
            return

        if SPACY_AVAILABLE:
            try:
                self._nlp = spacy.load(self.spacy_model_name)
                logger.info(f"Loaded spaCy model: {self.spacy_model_name}")
            except OSError:
                logger.warning(
                    f"spaCy model '{self.spacy_model_name}' not found. "
                    f"Run: python -m spacy download {self.spacy_model_name}"
                )
                self._nlp = None

        self._initialized = True

    async def extract_entities(self, text: str) -> list[Entity]:
        """
        Extract named entities from text.

        Args:
            text: Text to analyze

        Returns:
            List of extracted entities
        """
        self._ensure_initialized()

        entities = []

        if self._nlp is not None:
            doc = self._nlp(text)

            # Extract entities using spaCy NER
            seen = set()
            for ent in doc.ents:
                if ent.label_ not in self.entity_types:
                    continue

                # Normalize entity name
                name = ent.text.strip()
                key = (name.lower(), ent.label_)

                if key in seen:
                    continue
                seen.add(key)

                try:
                    entity_type = EntityType(ent.label_)
                except ValueError:
                    # Unknown entity type, skip
                    continue

                entities.append(Entity(
                    name=name,
                    entity_type=entity_type,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                ))
        else:
            # Fallback: extract capitalized phrases that look like names
            entities = self._extract_entities_simple(text)

        return entities

    def _extract_entities_simple(self, text: str) -> list[Entity]:
        """
        Simple entity extraction without spaCy.

        Looks for capitalized words/phrases that may be names.
        """
        entities = []

        # Pattern for potential names (2-3 capitalized words)
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
        matches = re.findall(name_pattern, text)

        seen = set()
        for match in matches:
            # Skip common words that happen to be capitalized
            if match.lower() in self._stopwords:
                continue
            if match.lower() in seen:
                continue
            seen.add(match.lower())

            # Guess entity type based on patterns
            entity_type = EntityType.PERSON
            if any(suffix in match for suffix in ['Inc', 'Corp', 'LLC', 'Ltd', 'Co']):
                entity_type = EntityType.ORG
            elif match in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                continue  # Skip days
            elif match in ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']:
                continue  # Skip months

            entities.append(Entity(
                name=match,
                entity_type=entity_type,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
            ))

        return entities[:10]  # Limit to 10 entities

    async def extract_topics(self, text: str) -> list[str]:
        """
        Extract topics from text.

        Uses noun phrases from spaCy when available, falls back to
        keyword extraction.

        Args:
            text: Text to analyze

        Returns:
            List of topic strings
        """
        if not self.enable_topics:
            return []

        self._ensure_initialized()

        topics = []

        if self._nlp is not None:
            doc = self._nlp(text)

            # Extract noun chunks as potential topics
            noun_chunks = []
            for chunk in doc.noun_chunks:
                # Clean the chunk
                chunk_text = chunk.text.lower().strip()
                # Remove leading articles/determiners
                chunk_text = re.sub(r'^(the|a|an|this|that|these|those|my|your|his|her|its|our|their)\s+', '', chunk_text)

                if len(chunk_text) > 2 and chunk_text not in self._stopwords:
                    noun_chunks.append(chunk_text)

            # Count and rank noun chunks
            chunk_counts = Counter(noun_chunks)
            topics = [chunk for chunk, _ in chunk_counts.most_common(self.max_topics)]

        else:
            # Fallback: simple keyword extraction
            topics = self._extract_topics_simple(text)

        return topics[:self.max_topics]

    def _extract_topics_simple(self, text: str) -> list[str]:
        """
        Simple topic extraction without spaCy.

        Extracts frequent meaningful words.
        """
        # Tokenize and clean
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())

        # Remove stopwords
        words = [w for w in words if w not in self._stopwords]

        # Count frequencies
        word_counts = Counter(words)

        # Get most common as topics
        topics = [word for word, count in word_counts.most_common(self.max_topics * 2)
                  if count >= 2 or len(words) < 50]

        return topics[:self.max_topics]

    async def extract_sentiment(self, text: str) -> Optional[float]:
        """
        Extract sentiment score from text.

        Returns a score from -1.0 (very negative) to 1.0 (very positive).

        Args:
            text: Text to analyze

        Returns:
            Sentiment score or None if analysis fails
        """
        if not self.enable_sentiment:
            return None

        # Simple keyword-based sentiment
        # (A more sophisticated approach would use a trained model)
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
            'happy', 'glad', 'pleased', 'delighted', 'love', 'like', 'enjoy',
            'perfect', 'best', 'beautiful', 'awesome', 'brilliant', 'success',
            'successful', 'positive', 'helpful', 'useful', 'valuable', 'important',
            'interesting', 'exciting', 'impressive', 'outstanding', 'remarkable',
        }

        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'poor', 'worst', 'hate',
            'dislike', 'angry', 'sad', 'upset', 'disappointed', 'frustrated',
            'annoying', 'annoyed', 'difficult', 'problem', 'issue', 'wrong',
            'fail', 'failure', 'failed', 'negative', 'useless', 'waste',
            'boring', 'confusing', 'confused', 'worried', 'concern', 'concerned',
        }

        words = set(re.findall(r'\b[a-z]+\b', text.lower()))

        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)

        total = positive_count + negative_count
        if total == 0:
            return 0.0  # Neutral

        # Calculate score
        score = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, score))

    async def extract_all(self, text: str) -> dict:
        """
        Extract all metadata from text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with entities, topics, and sentiment
        """
        entities = await self.extract_entities(text)
        topics = await self.extract_topics(text)
        sentiment = await self.extract_sentiment(text)

        return {
            "entities": entities,
            "topics": topics,
            "sentiment": sentiment,
        }


# Global instance
_extractor: Optional[MetadataExtractor] = None


def get_extractor() -> MetadataExtractor:
    """Get the global MetadataExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = MetadataExtractor()
    return _extractor


def reset_extractor() -> None:
    """Reset the global MetadataExtractor instance (for testing)."""
    global _extractor
    _extractor = None
