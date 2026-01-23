"""Core data models for Memory Palace."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class MemoryType(str, Enum):
    """Types of memories that can be stored."""
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    EVENT = "event"
    INSIGHT = "insight"
    CORRECTION = "correction"
    CONVERSATION = "conversation"
    SUMMARY = "summary"


class EntityType(str, Enum):
    """Types of entities that can be extracted."""
    PERSON = "PERSON"
    ORG = "ORG"
    LOCATION = "LOCATION"
    PROJECT = "PROJECT"
    CONCEPT = "CONCEPT"
    DATE = "DATE"
    MONEY = "MONEY"
    PRODUCT = "PRODUCT"
    EVENT = "EVENT"
    ANY = "ANY"


class ImportanceLevel(str, Enum):
    """Importance levels for memories."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def generate_id() -> str:
    """Generate a unique ID for memories and entities."""
    return str(uuid.uuid4())


class Memory(BaseModel):
    """A single memory unit in the palace."""
    id: str = Field(default_factory=generate_id)
    content: str
    memory_type: MemoryType = MemoryType.FACT
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    topics: list[str] = Field(default_factory=list)
    entities: dict[str, list[str]] = Field(default_factory=dict)
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    source_context: Optional[str] = None
    conversation_id: Optional[str] = None
    sentiment: float = 0.0  # -1 to 1
    embedding: Optional[list[float]] = None

    class Config:
        use_enum_values = True


class Entity(BaseModel):
    """An entity tracked in the memory palace."""
    id: str = Field(default_factory=generate_id)
    name: str
    entity_type: EntityType
    mention_count: int = 1
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    related_topics: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class Topic(BaseModel):
    """A topic/tag in the memory palace."""
    name: str
    count: int = 1
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    """A conversation session in the memory palace."""
    id: str = Field(default_factory=generate_id)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    message_count: int = 0
    topics: list[str] = Field(default_factory=list)


class MemorySearchResult(BaseModel):
    """A memory search result with relevance score."""
    memory: Memory
    relevance_score: float = 0.0


class TimelineEntry(BaseModel):
    """A time-grouped entry in a timeline query."""
    period_start: datetime
    period_end: datetime
    period_label: str
    memories: list[Memory] = Field(default_factory=list)
    summary: Optional[str] = None
    memory_count: int = 0


class EntityProfile(BaseModel):
    """Comprehensive profile of an entity."""
    name: str
    entity_type: str
    mention_count: int
    first_seen: datetime
    last_seen: datetime
    related_topics: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    recent_memories: list[Memory] = Field(default_factory=list)


class PalaceStats(BaseModel):
    """Statistics about the memory palace."""
    total_memories: int = 0
    total_entities: int = 0
    total_topics: int = 0
    total_conversations: int = 0
    memories_by_type: dict[str, int] = Field(default_factory=dict)
    memories_by_importance: dict[str, int] = Field(default_factory=dict)
    oldest_memory: Optional[datetime] = None
    newest_memory: Optional[datetime] = None
    top_topics: list[tuple[str, int]] = Field(default_factory=list)
    top_entities: list[tuple[str, str, int]] = Field(default_factory=list)
