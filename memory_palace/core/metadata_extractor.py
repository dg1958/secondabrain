"""Metadata extraction for Memory Palace using spaCy NER and topic extraction."""

import logging
import re
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# Mapping from spaCy entity types to our types
SPACY_TO_ENTITY_TYPE = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "LOCATION",  # Geo-political entity
    "LOC": "LOCATION",
    "FAC": "LOCATION",  # Facilities
    "PRODUCT": "PRODUCT",
    "EVENT": "EVENT",
    "WORK_OF_ART": "CONCEPT",
    "LAW": "CONCEPT",
    "LANGUAGE": "CONCEPT",
    "DATE": "DATE",
    "TIME": "DATE",
    "MONEY": "MONEY",
    "QUANTITY": "CONCEPT",
    "ORDINAL": "CONCEPT",
    "CARDINAL": "CONCEPT",
    "PERCENT": "CONCEPT",
    "NORP": "ORG",  # Nationalities, religious groups, etc.
}

# Common stopwords for topic extraction
STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
    'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
    'his', 'our', 'their', 'what', 'which', 'who', 'whom', 'where',
    'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'not', 'only', 'own', 'same',
    'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
    'then', 'once', 'if', 'about', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'between', 'under', 'again', 'further',
    'while', 'because', 'until', 'against', 'being', 'having', 'doing',
    'get', 'got', 'getting', 'make', 'made', 'making', 'say', 'said',
    'saying', 'go', 'went', 'going', 'come', 'came', 'coming', 'take',
    'took', 'taking', 'see', 'saw', 'seeing', 'know', 'knew', 'knowing',
    'think', 'thought', 'thinking', 'want', 'wanted', 'wanting', 'use',
    'used', 'using', 'find', 'found', 'finding', 'give', 'gave', 'giving',
    'tell', 'told', 'telling', 'ask', 'asked', 'asking', 'seem', 'seemed',
    'seeming', 'feel', 'felt', 'feeling', 'try', 'tried', 'trying',
    'leave', 'left', 'leaving', 'call', 'called', 'calling', 'keep',
    'kept', 'keeping', 'let', 'put', 'putting', 'begin', 'began',
    'beginning', 'show', 'showed', 'showing', 'hear', 'heard', 'hearing',
    'play', 'played', 'playing', 'run', 'ran', 'running', 'move', 'moved',
    'moving', 'live', 'lived', 'living', 'believe', 'believed', 'believing',
    'bring', 'brought', 'bringing', 'happen', 'happened', 'happening',
    'write', 'wrote', 'writing', 'provide', 'provided', 'providing',
    'sit', 'sat', 'sitting', 'stand', 'stood', 'standing', 'lose', 'lost',
    'losing', 'pay', 'paid', 'paying', 'meet', 'met', 'meeting', 'include',
    'included', 'including', 'continue', 'continued', 'continuing',
    'set', 'setting', 'learn', 'learned', 'learning', 'change', 'changed',
    'changing', 'lead', 'led', 'leading', 'understand', 'understood',
    'watch', 'watched', 'watching', 'follow', 'followed', 'following',
    'stop', 'stopped', 'stopping', 'create', 'created', 'creating',
    'speak', 'spoke', 'speaking', 'read', 'reading', 'allow', 'allowed',
    'allowing', 'add', 'added', 'adding', 'spend', 'spent', 'spending',
    'grow', 'grew', 'growing', 'open', 'opened', 'opening', 'walk',
    'walked', 'walking', 'win', 'won', 'winning', 'offer', 'offered',
    'offering', 'remember', 'remembered', 'remembering', 'love', 'loved',
    'loving', 'consider', 'considered', 'considering', 'appear', 'appeared',
    'appearing', 'buy', 'bought', 'buying', 'wait', 'waited', 'waiting',
    'serve', 'served', 'serving', 'die', 'died', 'dying', 'send', 'sent',
    'sending', 'expect', 'expected', 'expecting', 'build', 'built',
    'building', 'stay', 'stayed', 'staying', 'fall', 'fell', 'falling',
    'cut', 'cutting', 'reach', 'reached', 'reaching', 'kill', 'killed',
    'killing', 'remain', 'remained', 'remaining', 'something', 'anything',
    'nothing', 'everything', 'someone', 'anyone', 'everyone', 'nobody',
    'one', 'two', 'first', 'second', 'new', 'old', 'good', 'great',
    'little', 'much', 'many', 'long', 'right', 'still', 'well', 'even',
    'back', 'any', 'way', 'time', 'year', 'day', 'thing', 'man', 'world',
    'life', 'hand', 'part', 'child', 'eye', 'woman', 'place', 'work',
    'week', 'case', 'point', 'government', 'company', 'number', 'group',
    'problem', 'fact', "don't", "doesn't", "didn't", "won't", "wouldn't",
    "couldn't", "shouldn't", "can't", "haven't", "hasn't", "hadn't",
    "isn't", "aren't", "wasn't", "weren't", "i'm", "you're", "he's",
    "she's", "it's", "we're", "they're", "i've", "you've", "we've",
    "they've", "i'd", "you'd", "he'd", "she'd", "we'd", "they'd",
    "i'll", "you'll", "he'll", "she'll", "we'll", "they'll", "let's",
    "that's", "who's", "what's", "here's", "there's", "where's",
    "when's", "why's", "how's",
}


class MetadataExtractor:
    """
    Extract metadata (entities, topics, sentiment) from text.

    Uses spaCy for Named Entity Recognition and simple noun phrase
    extraction for topics.
    """

    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        max_topics: int = 5,
        min_topic_length: int = 3
    ):
        """
        Initialize the metadata extractor.

        Args:
            spacy_model: Name of the spaCy model to load
            max_topics: Maximum number of topics to extract
            min_topic_length: Minimum character length for topics
        """
        self.spacy_model_name = spacy_model
        self.max_topics = max_topics
        self.min_topic_length = min_topic_length
        self._nlp = None
        self._spacy_available = True

    def _load_spacy(self):
        """Load spaCy model lazily."""
        if self._nlp is not None:
            return

        try:
            import spacy
            self._nlp = spacy.load(self.spacy_model_name)
            logger.info(f"Loaded spaCy model: {self.spacy_model_name}")
        except ImportError:
            logger.warning("spaCy not installed. NER will be disabled.")
            self._spacy_available = False
        except OSError:
            logger.warning(
                f"spaCy model '{self.spacy_model_name}' not found. "
                f"Run: python -m spacy download {self.spacy_model_name}"
            )
            self._spacy_available = False

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """
        Extract named entities from text.

        Args:
            text: Input text

        Returns:
            Dictionary mapping entity types to lists of entity names
            e.g., {"PERSON": ["John Smith"], "ORG": ["Acme Corp"]}
        """
        self._load_spacy()

        if not self._spacy_available or self._nlp is None:
            return {}

        entities: dict[str, list[str]] = {}

        try:
            doc = self._nlp(text)

            for ent in doc.ents:
                # Map spaCy type to our type
                entity_type = SPACY_TO_ENTITY_TYPE.get(ent.label_, "CONCEPT")

                # Clean entity text
                entity_text = ent.text.strip()
                if not entity_text or len(entity_text) < 2:
                    continue

                # Skip purely numeric entities except for specific types
                if entity_text.isdigit() and entity_type not in ["MONEY", "DATE"]:
                    continue

                if entity_type not in entities:
                    entities[entity_type] = []

                # Avoid duplicates
                if entity_text not in entities[entity_type]:
                    entities[entity_type].append(entity_text)

        except Exception as e:
            logger.error(f"Entity extraction error: {e}")

        return entities

    def extract_topics(self, text: str, max_topics: Optional[int] = None) -> list[str]:
        """
        Extract topics/keywords from text.

        Uses noun phrase extraction with frequency analysis.

        Args:
            text: Input text
            max_topics: Override default max topics

        Returns:
            List of topic strings
        """
        max_topics = max_topics or self.max_topics

        # Try spaCy-based extraction first
        self._load_spacy()

        if self._spacy_available and self._nlp is not None:
            return self._extract_topics_spacy(text, max_topics)
        else:
            return self._extract_topics_simple(text, max_topics)

    def _extract_topics_spacy(self, text: str, max_topics: int) -> list[str]:
        """Extract topics using spaCy noun chunks."""
        topics = []
        seen = set()

        try:
            doc = self._nlp(text)

            # Extract noun chunks
            noun_chunks = []
            for chunk in doc.noun_chunks:
                # Clean and filter
                chunk_text = chunk.text.lower().strip()

                # Remove leading determiners/pronouns
                chunk_text = re.sub(r'^(the|a|an|this|that|these|those|my|your|his|her|our|their)\s+', '', chunk_text)

                if (
                    len(chunk_text) >= self.min_topic_length
                    and chunk_text not in STOPWORDS
                    and not chunk_text.isdigit()
                    and chunk_text not in seen
                ):
                    noun_chunks.append(chunk_text)
                    seen.add(chunk_text)

            # Also include important single nouns (nouns with high relevance)
            for token in doc:
                if (
                    token.pos_ in ('NOUN', 'PROPN')
                    and len(token.text) >= self.min_topic_length
                    and token.text.lower() not in STOPWORDS
                    and token.text.lower() not in seen
                    and not token.text.isdigit()
                ):
                    noun_chunks.append(token.text.lower())
                    seen.add(token.text.lower())

            # Count and rank
            counter = Counter(noun_chunks)
            topics = [topic for topic, _ in counter.most_common(max_topics)]

        except Exception as e:
            logger.error(f"spaCy topic extraction error: {e}")
            return self._extract_topics_simple(text, max_topics)

        return topics

    def _extract_topics_simple(self, text: str, max_topics: int) -> list[str]:
        """Extract topics using simple word frequency."""
        # Tokenize
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        # Filter stopwords and short words
        words = [
            w for w in words
            if len(w) >= self.min_topic_length
            and w not in STOPWORDS
        ]

        # Count and return top topics
        counter = Counter(words)
        return [topic for topic, _ in counter.most_common(max_topics)]

    def extract_sentiment(self, text: str) -> float:
        """
        Extract sentiment from text.

        Args:
            text: Input text

        Returns:
            Sentiment score from -1 (negative) to 1 (positive)

        Note:
            Currently returns 0.0 as a stub implementation.
            TODO: IMPLEMENT SENTIMENT ANALYSIS
            Future: Use transformers sentiment model or TextBlob.
        """
        # TODO: IMPLEMENT SENTIMENT ANALYSIS
        # Options:
        # 1. Use transformers: from transformers import pipeline
        #    sentiment_pipeline = pipeline("sentiment-analysis")
        # 2. Use TextBlob: from textblob import TextBlob
        #    return TextBlob(text).sentiment.polarity
        # 3. Use VADER: from nltk.sentiment import SentimentIntensityAnalyzer

        # For now, return neutral
        return 0.0

    def extract_all(self, text: str) -> dict:
        """
        Extract all metadata from text.

        Args:
            text: Input text

        Returns:
            Dictionary with entities, topics, and sentiment
        """
        return {
            "entities": self.extract_entities(text),
            "topics": self.extract_topics(text),
            "sentiment": self.extract_sentiment(text),
        }


# Singleton instance for reuse
_extractor: Optional[MetadataExtractor] = None


def get_extractor(
    spacy_model: str = "en_core_web_sm",
    max_topics: int = 5,
    min_topic_length: int = 3
) -> MetadataExtractor:
    """
    Get or create the metadata extractor singleton.

    Args:
        spacy_model: spaCy model name
        max_topics: Maximum topics to extract
        min_topic_length: Minimum topic character length

    Returns:
        MetadataExtractor instance
    """
    global _extractor

    if _extractor is None:
        _extractor = MetadataExtractor(
            spacy_model=spacy_model,
            max_topics=max_topics,
            min_topic_length=min_topic_length
        )

    return _extractor
