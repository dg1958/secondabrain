"""Pydantic schemas for MCP tool inputs and outputs."""

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

from memory_palace.core.models import MemoryType, EntityType, ImportanceLevel


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class MemorySearchParams(BaseModel):
    """Parameters for searching memories."""
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return")
    date_from: Optional[date] = Field(default=None, description="Filter: start date (inclusive)")
    date_to: Optional[date] = Field(default=None, description="Filter: end date (inclusive)")
    topics: Optional[list[str]] = Field(default=None, description="Filter: only memories with these topics")
    entities: Optional[list[str]] = Field(default=None, description="Filter: only memories mentioning these entities")
    memory_types: Optional[list[str]] = Field(default=None, description="Filter: only these memory types (fact, preference, decision, event, insight, correction)")
    min_relevance: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum relevance score (0-1)")


class EntitySearchParams(BaseModel):
    """Parameters for searching by entity."""
    entity_name: str = Field(..., description="Name of the entity to search for")
    entity_type: Optional[str] = Field(default=None, description="Entity type filter (PERSON, ORG, LOCATION, PROJECT, CONCEPT)")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    date_from: Optional[date] = Field(default=None, description="Filter: start date")
    date_to: Optional[date] = Field(default=None, description="Filter: end date")


class DateRangeSearchParams(BaseModel):
    """Parameters for date range search."""
    date_from: date = Field(..., description="Start date (inclusive)")
    date_to: date = Field(..., description="End date (inclusive)")
    topics: Optional[list[str]] = Field(default=None, description="Filter by topics")
    memory_types: Optional[list[str]] = Field(default=None, description="Filter by memory types")
    limit: int = Field(default=50, ge=1, le=100, description="Maximum results")


class TimelineQueryParams(BaseModel):
    """Parameters for timeline queries."""
    topic: str = Field(..., description="Topic to trace through time")
    date_from: Optional[date] = Field(default=None, description="Start date for timeline")
    date_to: Optional[date] = Field(default=None, description="End date for timeline")
    granularity: Literal["day", "week", "month", "year"] = Field(default="week", description="Time grouping granularity")
    include_summaries: bool = Field(default=True, description="Include AI-generated period summaries")
    max_entries: int = Field(default=50, ge=1, le=200, description="Maximum memories to include")


class TopicEvolutionParams(BaseModel):
    """Parameters for topic evolution query."""
    topic: str = Field(..., description="Topic to analyze evolution for")
    date_from: Optional[date] = Field(default=None, description="Start date")
    date_to: Optional[date] = Field(default=None, description="End date")
    granularity: Literal["week", "month", "quarter", "year"] = Field(default="month", description="Analysis granularity")


class MemorySaveParams(BaseModel):
    """Parameters for saving a new memory."""
    content: str = Field(..., min_length=1, description="The memory content to save")
    memory_type: str = Field(default="fact", description="Type of memory: fact, preference, decision, event, insight, correction")
    topics: Optional[list[str]] = Field(default=None, description="Topics/tags (auto-extracted if not provided)")
    importance: str = Field(default="medium", description="Importance level: low, medium, high, critical")
    source_context: Optional[str] = Field(default=None, description="Context about where this memory came from")
    timestamp: Optional[datetime] = Field(default=None, description="When this memory occurred (defaults to now)")


class ConversationSummaryParams(BaseModel):
    """Parameters for saving a conversation summary."""
    summary: str = Field(..., min_length=1, description="Summary of the conversation")
    topics: Optional[list[str]] = Field(default=None, description="Main topics discussed")
    key_points: Optional[list[str]] = Field(default=None, description="Key points from the conversation")
    started_at: Optional[datetime] = Field(default=None, description="When conversation started")
    ended_at: Optional[datetime] = Field(default=None, description="When conversation ended")


class EntityListParams(BaseModel):
    """Parameters for listing entities."""
    entity_type: Optional[str] = Field(default=None, description="Filter by entity type")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum entities to return")
    sort_by: Literal["count", "name", "recent"] = Field(default="count", description="Sort order")


class EntityProfileParams(BaseModel):
    """Parameters for getting entity profile."""
    entity_name: str = Field(..., description="Name of the entity")
    entity_type: Optional[str] = Field(default=None, description="Entity type (helps with disambiguation)")
    include_memories: bool = Field(default=True, description="Include recent memories about this entity")
    memory_limit: int = Field(default=10, ge=1, le=50, description="Maximum memories to include")


class MemoryUpdateParams(BaseModel):
    """Parameters for updating a memory."""
    memory_id: str = Field(..., description="ID of the memory to update")
    content: Optional[str] = Field(default=None, description="New content (if updating)")
    topics: Optional[list[str]] = Field(default=None, description="New topics (if updating)")
    importance: Optional[str] = Field(default=None, description="New importance level")
    memory_type: Optional[str] = Field(default=None, description="New memory type")


class MemoryDeleteParams(BaseModel):
    """Parameters for deleting a memory."""
    memory_id: str = Field(..., description="ID of the memory to delete")
    confirm: bool = Field(default=False, description="Confirm deletion (must be true)")


class TopicListParams(BaseModel):
    """Parameters for listing topics."""
    limit: int = Field(default=50, ge=1, le=200, description="Maximum topics to return")
    sort_by: Literal["count", "name", "recent"] = Field(default="count", description="Sort order")
    min_count: int = Field(default=1, ge=1, description="Minimum memory count to include topic")


class RecentMemoriesParams(BaseModel):
    """Parameters for listing recent memories."""
    limit: int = Field(default=20, ge=1, le=100, description="Number of recent memories")
    memory_types: Optional[list[str]] = Field(default=None, description="Filter by memory types")
    include_conversations: bool = Field(default=True, description="Include conversation summaries")


# ============================================================================
# OUTPUT SCHEMAS
# ============================================================================

class MemoryResult(BaseModel):
    """A single memory result."""
    id: str
    content: str
    memory_type: str
    timestamp: datetime
    topics: list[str]
    entities: dict[str, list[str]]
    importance: str
    relevance_score: float = 0.0
    source_conversation_id: Optional[str] = None


class SearchResponse(BaseModel):
    """Response from search operations."""
    memories: list[MemoryResult]
    total_found: int
    query: str
    filters_applied: dict


class TimelineEntryResult(BaseModel):
    """A single timeline entry."""
    period_start: datetime
    period_end: datetime
    period_label: str
    memories: list[MemoryResult]
    summary: Optional[str] = None
    memory_count: int


class TimelineResponse(BaseModel):
    """Response from timeline query."""
    topic: str
    entries: list[TimelineEntryResult]
    total_memories: int
    date_range: dict


class TopicEvolutionEntry(BaseModel):
    """A single entry in topic evolution."""
    period_label: str
    period_start: datetime
    period_end: datetime
    memory_count: int
    key_themes: list[str]
    sentiment_trend: Optional[float] = None
    sample_memories: list[str]


class TopicEvolutionResponse(BaseModel):
    """Response from topic evolution query."""
    topic: str
    evolution: list[TopicEvolutionEntry]
    overall_trend: str


class SaveResponse(BaseModel):
    """Response from save operations."""
    success: bool
    memory_id: str
    extracted_topics: list[str]
    extracted_entities: dict[str, list[str]]
    message: str


class EntityListItem(BaseModel):
    """An entity in list results."""
    name: str
    entity_type: str
    mention_count: int
    last_seen: datetime


class EntityListResponse(BaseModel):
    """Response from entity list."""
    entities: list[EntityListItem]
    total_count: int


class EntityProfileResponse(BaseModel):
    """Response from entity profile query."""
    name: str
    entity_type: str
    mention_count: int
    first_seen: datetime
    last_seen: datetime
    related_topics: list[str]
    related_entities: list[str]
    key_facts: list[str]
    recent_memories: list[MemoryResult]


class UpdateResponse(BaseModel):
    """Response from update operations."""
    success: bool
    memory_id: str
    message: str


class DeleteResponse(BaseModel):
    """Response from delete operations."""
    success: bool
    memory_id: str
    message: str


class TopicListItem(BaseModel):
    """A topic in list results."""
    name: str
    count: int
    last_seen: datetime


class TopicListResponse(BaseModel):
    """Response from topic list."""
    topics: list[TopicListItem]
    total_count: int


class StatsResponse(BaseModel):
    """Response from stats query."""
    total_memories: int
    total_entities: int
    total_topics: int
    total_conversations: int
    memories_by_type: dict[str, int]
    memories_by_importance: dict[str, int]
    oldest_memory: Optional[datetime]
    newest_memory: Optional[datetime]
    top_topics: list[dict]
    top_entities: list[dict]


class ErrorResponse(BaseModel):
    """Error response."""
    error: bool = True
    message: str
    details: Optional[str] = None
