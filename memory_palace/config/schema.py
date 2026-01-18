"""
Data models and schemas for the Memory Palace system.

This module defines Pydantic models for:
- Memory metadata
- Document representations
- Query structures
- Configuration objects
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid


class SourceType(str, Enum):
    """Supported data source types."""
    FIREFLIES = "fireflies"
    MANUAL = "manual"
    IMPORT = "import"
    API = "api"
    WATCH_FOLDER = "watch_folder"


class DocumentFormat(str, Enum):
    """Supported input document formats."""
    PLAIN_TEXT = "plain_text"
    JSON_TRANSCRIPT = "json_transcript"
    MARKDOWN = "markdown"
    FIREFLIES_JSON = "fireflies_json"


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class EntityType(str, Enum):
    """Named entity types recognized by the system."""
    PERSON = "PERSON"
    ORG = "ORG"
    GPE = "GPE"  # Geopolitical entity (countries, cities, states)
    LOC = "LOC"  # Non-GPE locations
    DATE = "DATE"
    TIME = "TIME"
    MONEY = "MONEY"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    WORK_OF_ART = "WORK_OF_ART"
    LAW = "LAW"
    LANGUAGE = "LANGUAGE"


class MemoryMetadata(BaseModel):
    """
    Metadata associated with a memory chunk.

    This is the core metadata schema that accompanies every stored memory
    fragment in the vector database.
    """
    doc_id: str = Field(
        description="Unique identifier for the source document"
    )
    chunk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this specific chunk"
    )
    chunk_index: int = Field(
        default=0,
        description="Position of this chunk within the source document"
    )
    total_chunks: int = Field(
        default=1,
        description="Total number of chunks from the source document"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this memory was created/recorded"
    )
    source: SourceType = Field(
        default=SourceType.MANUAL,
        description="Origin of this memory"
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Original filename if imported from file"
    )
    participants: List[str] = Field(
        default_factory=list,
        description="People involved in this conversation/memory"
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Auto-extracted or manually assigned topics"
    )
    entities: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Named entities grouped by type"
    )
    sentiment: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Sentiment score from -1 (negative) to 1 (positive)"
    )
    sentiment_label: Optional[SentimentLabel] = Field(
        default=None,
        description="Categorical sentiment label"
    )
    custom_tags: List[str] = Field(
        default_factory=list,
        description="User-defined tags for organization"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID linking related conversation chunks"
    )
    platform: Optional[str] = Field(
        default=None,
        description="Platform where conversation occurred (e.g., 'zoom', 'teams')"
    )
    language: str = Field(
        default="en",
        description="Language code of the content"
    )
    word_count: int = Field(
        default=0,
        description="Number of words in this chunk"
    )
    token_count: int = Field(
        default=0,
        description="Estimated token count for this chunk"
    )

    def to_chroma_metadata(self) -> Dict[str, Any]:
        """
        Convert to ChromaDB-compatible metadata format.

        ChromaDB has restrictions on metadata types, so we need to
        serialize complex types to strings.
        """
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "source_file": self.source_file or "",
            "participants": ",".join(self.participants),
            "topics": ",".join(self.topics),
            "entities_json": str(self.entities),
            "sentiment": self.sentiment if self.sentiment is not None else 0.0,
            "sentiment_label": self.sentiment_label.value if self.sentiment_label else "",
            "custom_tags": ",".join(self.custom_tags),
            "conversation_id": self.conversation_id or "",
            "platform": self.platform or "",
            "language": self.language,
            "word_count": self.word_count,
            "token_count": self.token_count,
        }

    @classmethod
    def from_chroma_metadata(cls, metadata: Dict[str, Any]) -> "MemoryMetadata":
        """Reconstruct MemoryMetadata from ChromaDB metadata format."""
        import ast

        # Parse entities from string representation
        entities_str = metadata.get("entities_json", "{}")
        try:
            entities = ast.literal_eval(entities_str) if entities_str else {}
        except (ValueError, SyntaxError):
            entities = {}

        # Parse sentiment label
        sentiment_label_str = metadata.get("sentiment_label", "")
        sentiment_label = None
        if sentiment_label_str:
            try:
                sentiment_label = SentimentLabel(sentiment_label_str)
            except ValueError:
                pass

        return cls(
            doc_id=metadata.get("doc_id", ""),
            chunk_id=metadata.get("chunk_id", ""),
            chunk_index=metadata.get("chunk_index", 0),
            total_chunks=metadata.get("total_chunks", 1),
            timestamp=datetime.fromisoformat(metadata.get("timestamp", datetime.now().isoformat())),
            source=SourceType(metadata.get("source", "manual")),
            source_file=metadata.get("source_file") or None,
            participants=metadata.get("participants", "").split(",") if metadata.get("participants") else [],
            topics=metadata.get("topics", "").split(",") if metadata.get("topics") else [],
            entities=entities,
            sentiment=metadata.get("sentiment") if metadata.get("sentiment") != 0.0 else None,
            sentiment_label=sentiment_label,
            custom_tags=metadata.get("custom_tags", "").split(",") if metadata.get("custom_tags") else [],
            conversation_id=metadata.get("conversation_id") or None,
            platform=metadata.get("platform") or None,
            language=metadata.get("language", "en"),
            word_count=metadata.get("word_count", 0),
            token_count=metadata.get("token_count", 0),
        )


class Document(BaseModel):
    """
    Represents a document before chunking.

    This is the input format for the ingestion pipeline.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique document identifier"
    )
    content: str = Field(
        description="Raw text content of the document"
    )
    format: DocumentFormat = Field(
        default=DocumentFormat.PLAIN_TEXT,
        description="Format of the input document"
    )
    metadata: MemoryMetadata = Field(
        default_factory=lambda: MemoryMetadata(doc_id=""),
        description="Document-level metadata"
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def set_doc_id(cls, v, info):
        """Ensure metadata has the correct doc_id."""
        if isinstance(v, dict):
            return v
        return v


class MemoryChunk(BaseModel):
    """
    A chunk of memory ready for storage.

    This represents a processed chunk with its embedding-ready text
    and associated metadata.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique chunk identifier"
    )
    text: str = Field(
        description="Chunk text content"
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding of the text"
    )
    metadata: MemoryMetadata = Field(
        description="Chunk metadata"
    )


class QueryFilter(BaseModel):
    """
    Filters for querying the memory database.
    """
    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter memories after this date"
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter memories before this date"
    )
    topics: Optional[List[str]] = Field(
        default=None,
        description="Filter by topics (OR logic)"
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="Filter by participants (OR logic)"
    )
    entities: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Filter by named entities"
    )
    custom_tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by custom tags (OR logic)"
    )
    source: Optional[SourceType] = Field(
        default=None,
        description="Filter by source type"
    )
    min_sentiment: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Minimum sentiment score"
    )
    max_sentiment: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Maximum sentiment score"
    )


class QueryResult(BaseModel):
    """
    A single result from a memory query.
    """
    chunk_id: str = Field(
        description="ID of the matched chunk"
    )
    text: str = Field(
        description="Text content of the chunk"
    )
    score: float = Field(
        description="Similarity/relevance score"
    )
    metadata: MemoryMetadata = Field(
        description="Chunk metadata"
    )
    highlights: Optional[List[str]] = Field(
        default=None,
        description="Highlighted matching sections"
    )


class QueryResponse(BaseModel):
    """
    Complete response from a memory query.
    """
    query: str = Field(
        description="Original query text"
    )
    results: List[QueryResult] = Field(
        default_factory=list,
        description="Matched memory chunks"
    )
    total_results: int = Field(
        default=0,
        description="Total number of results"
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="Query processing time in milliseconds"
    )
    filters_applied: Optional[QueryFilter] = Field(
        default=None,
        description="Filters that were applied"
    )
    synthesis: Optional[str] = Field(
        default=None,
        description="LLM-generated synthesis of results"
    )


class FirefliesTranscript(BaseModel):
    """
    Schema for Fireflies.ai transcript data.
    """
    id: str = Field(
        description="Fireflies transcript ID"
    )
    title: str = Field(
        description="Meeting title"
    )
    date: datetime = Field(
        description="Meeting date/time"
    )
    duration_minutes: int = Field(
        default=0,
        description="Meeting duration in minutes"
    )
    participants: List[str] = Field(
        default_factory=list,
        description="Meeting participants"
    )
    transcript_text: str = Field(
        description="Full transcript text"
    )
    summary: Optional[str] = Field(
        default=None,
        description="AI-generated summary"
    )
    action_items: Optional[List[str]] = Field(
        default=None,
        description="Extracted action items"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Extracted keywords"
    )
    meeting_url: Optional[str] = Field(
        default=None,
        description="Original meeting URL"
    )


class IngestionResult(BaseModel):
    """
    Result of a document ingestion operation.
    """
    doc_id: str = Field(
        description="Document ID"
    )
    success: bool = Field(
        description="Whether ingestion succeeded"
    )
    chunks_created: int = Field(
        default=0,
        description="Number of chunks created"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    duplicate: bool = Field(
        default=False,
        description="Whether document was a duplicate"
    )
    processing_time_ms: float = Field(
        default=0.0,
        description="Processing time in milliseconds"
    )
