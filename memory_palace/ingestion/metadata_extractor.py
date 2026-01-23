"""
Metadata extraction service for Memory Palace.

This module provides:
- Named Entity Recognition (NER) using spaCy
- Sentiment analysis
- Topic/keyword extraction
- Automatic metadata enrichment
"""

import re
from collections import Counter
from importlib import import_module, util
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

try:
    import spacy
    from spacy.language import Language
except ImportError:
    spacy = None
    Language = None
    logger.warning("spaCy not installed. NER features disabled.")

from config.schema import MemoryMetadata, SentimentLabel


class MetadataExtractor:
    """
    Service for extracting rich metadata from text.

    Capabilities:
    - Named Entity Recognition (people, organizations, locations, etc.)
    - Sentiment analysis (positive/negative/neutral)
    - Topic/keyword extraction
    - Date/time extraction
    """

    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        enable_ner: bool = True,
        enable_sentiment: bool = True,
        enable_topics: bool = True,
    ):
        """
        Initialize the metadata extractor.

        Args:
            spacy_model: Name of the spaCy model to use
            enable_ner: Enable named entity recognition
            enable_sentiment: Enable sentiment analysis
            enable_topics: Enable topic extraction
        """
        self.enable_ner = enable_ner
        self.enable_sentiment = enable_sentiment
        self.enable_topics = enable_topics

        self._nlp: Optional["Language"] = None
        self._spacy_model = spacy_model

        if enable_ner and spacy is not None:
            self._load_spacy_model()

        # Stopwords for topic extraction
        self._stopwords: Set[str] = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "dare", "ought", "used", "it", "its", "this", "that", "these", "those",
            "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
            "my", "your", "his", "our", "their", "what", "which", "who", "whom",
            "when", "where", "why", "how", "all", "each", "every", "both", "few",
            "more", "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "also", "now",
            "here", "there", "then", "once", "again", "always", "never", "ever",
            "still", "already", "even", "well", "back", "much", "many", "any",
            "about", "after", "before", "between", "through", "during", "into",
            "over", "under", "above", "below", "up", "down", "out", "off", "away",
            "around", "among", "along", "across", "behind", "beside", "besides",
            "beyond", "within", "without", "upon", "toward", "towards", "against",
            "until", "unless", "while", "although", "though", "because", "since",
            "if", "whether", "either", "neither", "else", "otherwise", "however",
            "therefore", "thus", "hence", "moreover", "furthermore", "nevertheless",
            "nonetheless", "instead", "meanwhile", "anyway", "besides", "indeed",
            "certainly", "perhaps", "maybe", "probably", "possibly", "actually",
            "really", "basically", "essentially", "generally", "usually", "often",
            "sometimes", "rarely", "simply", "merely", "quite", "rather", "fairly",
            "pretty", "almost", "nearly", "hardly", "barely", "exactly", "entirely",
            "completely", "absolutely", "definitely", "certainly", "surely",
            "yeah", "yes", "no", "ok", "okay", "like", "know", "think", "going",
            "get", "got", "go", "come", "came", "make", "made", "take", "took",
            "see", "saw", "say", "said", "tell", "told", "ask", "asked", "want",
            "wanted", "give", "gave", "put", "let", "keep", "kept", "seem", "seemed",
        }

    def _load_spacy_model(self) -> None:
        """Load the spaCy language model."""
        if spacy is None:
            logger.warning("spaCy not installed. Install with: pip install spacy")
            return

        try:
            self._nlp = spacy.load(self._spacy_model)
            logger.info(f"Loaded spaCy model: {self._spacy_model}")
        except OSError:
            logger.warning(
                f"spaCy model '{self._spacy_model}' not found. "
                f"Install with: python -m spacy download {self._spacy_model}"
            )
            self._nlp = None

    @property
    def is_ner_available(self) -> bool:
        """Check if NER is available."""
        return self._nlp is not None

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary mapping entity types to lists of entities
        """
        if not self.enable_ner or not self.is_ner_available:
            return {}

        try:
            doc = self._nlp(text)

            entities: Dict[str, Set[str]] = {}
            for ent in doc.ents:
                ent_type = ent.label_
                ent_text = ent.text.strip()

                # Filter out very short or numeric-only entities
                if len(ent_text) < 2:
                    continue

                if ent_type not in entities:
                    entities[ent_type] = set()
                entities[ent_type].add(ent_text)

            # Convert sets to sorted lists
            return {k: sorted(list(v)) for k, v in entities.items()}

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {}

    def extract_sentiment(self, text: str) -> Tuple[float, SentimentLabel]:
        """
        Analyze sentiment of text.

        Uses VADER sentiment analysis for social media-friendly analysis.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (sentiment_score, sentiment_label)
        """
        if not self.enable_sentiment:
            return 0.0, SentimentLabel.NEUTRAL

        compound = None
        vader_spec = util.find_spec("vaderSentiment")
        if vader_spec is not None:
            vader_module = import_module("vaderSentiment.vaderSentiment")
            analyzer = vader_module.SentimentIntensityAnalyzer()
            scores = analyzer.polarity_scores(text)
            compound = scores["compound"]

        if compound is None:
            textblob_spec = util.find_spec("textblob")
            if textblob_spec is not None:
                textblob_module = import_module("textblob")
                blob = textblob_module.TextBlob(text)
                compound = blob.sentiment.polarity

        if compound is None:
            compound = self._lexicon_sentiment(text)

        # Map score to label
        if compound <= -0.6:
            label = SentimentLabel.VERY_NEGATIVE
        elif compound <= -0.2:
            label = SentimentLabel.NEGATIVE
        elif compound < 0.2:
            label = SentimentLabel.NEUTRAL
        elif compound < 0.6:
            label = SentimentLabel.POSITIVE
        else:
            label = SentimentLabel.VERY_POSITIVE

        return compound, label

    def _lexicon_sentiment(self, text: str) -> float:
        """Simple lexicon-based sentiment fallback."""
        positive_words = {
            "amazing", "awesome", "best", "brilliant", "excellent", "fantastic",
            "good", "great", "happy", "love", "outstanding", "positive", "success",
            "wonderful",
        }
        negative_words = {
            "angry", "awful", "bad", "disappointing", "disaster", "failure",
            "horrible", "hate", "negative", "poor", "problem", "sad", "terrible",
            "worst",
        }
        tokens = re.findall(r"[a-zA-Z']+", text.lower())
        if not tokens:
            return 0.0

        positives = sum(1 for token in tokens if token in positive_words)
        negatives = sum(1 for token in tokens if token in negative_words)
        if positives == 0 and negatives == 0:
            logger.warning(
                "No sentiment analyzer available. "
                "Install vaderSentiment or textblob."
            )
            return 0.0

        return (positives - negatives) / max(positives + negatives, 1)

    def extract_topics(
        self,
        text: str,
        max_topics: int = 5,
        min_length: int = 3,
    ) -> List[str]:
        """
        Extract key topics/keywords from text.

        Uses a combination of noun phrases and frequency analysis.

        Args:
            text: Text to analyze
            max_topics: Maximum number of topics to return
            min_length: Minimum keyword length

        Returns:
            List of topic keywords
        """
        if not self.enable_topics:
            return []

        topics: List[str] = []

        # Extract noun phrases if spaCy is available
        if self.is_ner_available:
            try:
                doc = self._nlp(text)

                # Get noun phrases
                noun_phrases = []
                for chunk in doc.noun_chunks:
                    # Clean the phrase
                    phrase = chunk.text.lower().strip()
                    # Remove leading articles/determiners
                    phrase = re.sub(r"^(the|a|an|this|that|these|those)\s+", "", phrase)
                    if len(phrase) >= min_length and phrase not in self._stopwords:
                        noun_phrases.append(phrase)

                # Count phrase frequencies
                phrase_counts = Counter(noun_phrases)
                topics.extend([p for p, _ in phrase_counts.most_common(max_topics)])

            except Exception as e:
                logger.warning(f"Noun phrase extraction failed: {e}")

        # Fall back to / supplement with keyword frequency
        if len(topics) < max_topics:
            keywords = self._extract_keywords(text, min_length)
            for keyword in keywords:
                if keyword not in topics:
                    topics.append(keyword)
                if len(topics) >= max_topics:
                    break

        return topics[:max_topics]

    def _extract_keywords(
        self,
        text: str,
        min_length: int = 3,
    ) -> List[str]:
        """
        Extract keywords using frequency analysis.

        Args:
            text: Text to analyze
            min_length: Minimum keyword length

        Returns:
            List of keywords sorted by frequency
        """
        # Tokenize and clean
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

        # Filter
        filtered = [
            w for w in words
            if len(w) >= min_length and w not in self._stopwords
        ]

        # Count and sort
        word_counts = Counter(filtered)
        return [word for word, _ in word_counts.most_common(20)]

    def extract_participants(self, text: str) -> List[str]:
        """
        Extract participant names from conversation text.

        Looks for patterns like "Speaker Name:" or "[Name]" commonly
        used in transcripts.

        Args:
            text: Text to analyze

        Returns:
            List of participant names
        """
        participants: Set[str] = set()

        # Pattern: "Name:" at start of line (common transcript format)
        speaker_pattern = r"^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*:"
        matches = re.findall(speaker_pattern, text, re.MULTILINE)
        participants.update(matches)

        # Pattern: "[Name]" format
        bracket_pattern = r"\[([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\]"
        matches = re.findall(bracket_pattern, text)
        participants.update(matches)

        # Also use NER for PERSON entities
        if self.is_ner_available:
            entities = self.extract_entities(text)
            if "PERSON" in entities:
                participants.update(entities["PERSON"])

        return sorted(list(participants))

    def extract_all(
        self,
        text: str,
        existing_metadata: Optional[MemoryMetadata] = None,
    ) -> Dict[str, Any]:
        """
        Extract all metadata from text.

        Args:
            text: Text to analyze
            existing_metadata: Existing metadata to merge with

        Returns:
            Dictionary of extracted metadata
        """
        results = {}

        # Extract entities
        if self.enable_ner:
            results["entities"] = self.extract_entities(text)

        # Extract sentiment
        if self.enable_sentiment:
            sentiment_score, sentiment_label = self.extract_sentiment(text)
            results["sentiment"] = sentiment_score
            results["sentiment_label"] = sentiment_label

        # Extract topics
        if self.enable_topics:
            results["topics"] = self.extract_topics(text)

        # Extract participants
        results["participants"] = self.extract_participants(text)

        # Merge with existing metadata if provided
        if existing_metadata:
            # Merge participants
            all_participants = set(existing_metadata.participants)
            all_participants.update(results.get("participants", []))
            results["participants"] = sorted(list(all_participants))

            # Merge topics
            all_topics = set(existing_metadata.topics)
            all_topics.update(results.get("topics", []))
            results["topics"] = list(all_topics)[:10]  # Limit to 10

            # Merge entities
            all_entities = existing_metadata.entities.copy()
            for ent_type, ent_list in results.get("entities", {}).items():
                if ent_type in all_entities:
                    all_entities[ent_type] = list(
                        set(all_entities[ent_type]) | set(ent_list)
                    )
                else:
                    all_entities[ent_type] = ent_list
            results["entities"] = all_entities

        return results

    def enrich_metadata(
        self,
        text: str,
        metadata: MemoryMetadata,
    ) -> MemoryMetadata:
        """
        Enrich existing metadata with extracted information.

        Args:
            text: Text to analyze
            metadata: Existing metadata to enrich

        Returns:
            Enriched MemoryMetadata object
        """
        extracted = self.extract_all(text, metadata)

        # Update metadata fields
        if "entities" in extracted:
            metadata.entities = extracted["entities"]

        if "sentiment" in extracted:
            metadata.sentiment = extracted["sentiment"]
            metadata.sentiment_label = extracted["sentiment_label"]

        if "topics" in extracted:
            # Merge with existing topics
            all_topics = set(metadata.topics)
            all_topics.update(extracted["topics"])
            metadata.topics = list(all_topics)[:10]

        if "participants" in extracted:
            # Merge with existing participants
            all_participants = set(metadata.participants)
            all_participants.update(extracted["participants"])
            metadata.participants = sorted(list(all_participants))

        return metadata


# Global extractor instance
_extractor: Optional[MetadataExtractor] = None


def get_metadata_extractor(
    spacy_model: str = "en_core_web_sm",
    enable_ner: bool = True,
    enable_sentiment: bool = True,
    enable_topics: bool = True,
) -> MetadataExtractor:
    """
    Get the global metadata extractor instance.

    Args:
        spacy_model: spaCy model name
        enable_ner: Enable NER
        enable_sentiment: Enable sentiment
        enable_topics: Enable topics

    Returns:
        MetadataExtractor instance
    """
    global _extractor
    if _extractor is None:
        _extractor = MetadataExtractor(
            spacy_model=spacy_model,
            enable_ner=enable_ner,
            enable_sentiment=enable_sentiment,
            enable_topics=enable_topics,
        )
    return _extractor


def extract_metadata(
    text: str,
    existing_metadata: Optional[MemoryMetadata] = None,
) -> Dict[str, Any]:
    """
    Convenience function to extract metadata from text.

    Args:
        text: Text to analyze
        existing_metadata: Existing metadata to merge

    Returns:
        Dictionary of extracted metadata
    """
    extractor = get_metadata_extractor()
    return extractor.extract_all(text, existing_metadata)
