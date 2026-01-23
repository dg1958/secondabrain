"""
Metadata extraction for Memory Palace.

This module re-exports the metadata extraction functionality from the
ingestion module to provide a unified interface. The ingestion module
contains the full implementation with:
- Named Entity Recognition (NER) using spaCy
- Sentiment analysis (VADER, TextBlob, or lexicon fallback)
- Topic/keyword extraction
- Participant extraction from transcripts

This consolidation eliminates code duplication between the async MCP server
path and the sync CLI/API path, while maintaining API compatibility.
"""

# Re-export everything from the ingestion metadata extractor
from memory_palace.ingestion.metadata_extractor import (
    MetadataExtractor,
    get_metadata_extractor,
    extract_metadata,
)

# Alias for backward compatibility with MCP tools
get_extractor = get_metadata_extractor

__all__ = [
    "MetadataExtractor",
    "get_extractor",
    "get_metadata_extractor",
    "extract_metadata",
]
