"""
Core data models for Memory Palace.

These models define the structure of memories, entities, topics,
and other data stored in the system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class MemoryType(str, Enum):
    """Types of memories that can be stored."""
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    EVENT = "event"
    INSIGHT = "insight"
    CONVERSATION_SUMMARY = "conversation_summary"
    NOTE = "note"


class Importance(str, Enum):
    """Importance levels for memories."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def to_score(cls, importance: "Importance") -> float:
        """Convert importance to numeric score."""
        scores = {
            cls.LOW: 0.25,
            cls.MEDIUM: 0.5,
            cls.HIGH: 0.75,
            cls.CRITICAL: 1.0
        }
        return scores.get(importance, 0.5)


class EntityType(str, Enum):
    """Types of entities that can be extracted."""
    PERSON = "PERSON"
    ORG = "ORG"
    GPE = "GPE"  # Geopolitical entity
    LOCATION = "LOCATION"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    WORK_OF_ART = "WORK_OF_ART"
    LAW = "LAW"
    DATE = "DATE"
    CONCEPT = "CONCEPT"  # Custom type for abstract concepts
    PROJECT = "PROJECT"  # Custom type for projects


class Entity(BaseModel):
    """An entity (person, organization, etc.) mentioned in memories."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    memory_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Topic(BaseModel):
    """A topic or tag associated with memories."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    memory_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Memory(BaseModel):
    """A single memory stored in the palace."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    memory_type: MemoryType = MemoryType.FACT
    importance: Importance = Importance.MEDIUM

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # When the event/fact occurred (may differ from creation time)
    occurred_at: Optional[datetime] = None

    # Extracted metadata
    entities: list[str] = Field(default_factory=list)  # Entity IDs
    topics: list[str] = Field(default_factory=list)  # Topic names
    sentiment_score: Optional[float] = None  # -1.0 to 1.0

    # Source information
    source: Optional[str] = None  # e.g., "conversation", "manual", "import"
    source_id: Optional[str] = None  # e.g., conversation ID
    summary: Optional[str] = None  # Auto-generated summary for long content

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_search_text(self) -> str:
        """Generate searchable text representation."""
        parts = [self.content]
        if self.summary:
            parts.append(self.summary)
        if self.topics:
            parts.append(" ".join(self.topics))
        return " ".join(parts)


class SearchResult(BaseModel):
    """A search result with relevance information."""
    memory: Memory
    relevance_score: float = Field(ge=0.0, le=1.0)
    # Why this result matched
    match_reasons: list[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    """An entry in a timeline reconstruction."""
    period_label: str  # e.g., "January 2024", "Q1 2024"
    start_date: datetime
    end_date: datetime
    memories: list[Memory] = Field(default_factory=list)
    summary: Optional[str] = None
    key_events: list[str] = Field(default_factory=list)


class EntityProfile(BaseModel):
    """Comprehensive information about an entity."""
    entity: Entity
    # Related memories
    recent_memories: list[Memory] = Field(default_factory=list)
    memory_count: int = 0
    # Related entities
    related_entities: list[Entity] = Field(default_factory=list)
    # Topics associated with this entity
    associated_topics: list[str] = Field(default_factory=list)
    # Timeline of interactions
    first_mentioned: Optional[datetime] = None
    last_mentioned: Optional[datetime] = None
    # Summary of relationship/importance
    summary: Optional[str] = None


class MemoryStats(BaseModel):
    """Statistics about the memory palace."""
    total_memories: int = 0
    memories_by_type: dict[str, int] = Field(default_factory=dict)
    memories_by_importance: dict[str, int] = Field(default_factory=dict)
    total_entities: int = 0
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    total_topics: int = 0
    top_topics: list[tuple[str, int]] = Field(default_factory=list)
    date_range: Optional[tuple[datetime, datetime]] = None
    last_updated: Optional[datetime] = None
