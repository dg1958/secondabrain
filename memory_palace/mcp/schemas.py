"""
Pydantic schemas for MCP tool inputs and outputs.

These schemas define the structure of requests and responses
for all MCP tools exposed by Memory Palace.
"""

from datetime import datetime
from typing import Optional, Any
from enum import Enum

from pydantic import BaseModel, Field


# ============ ENUMS ============

class MemoryTypeEnum(str, Enum):
    """Memory types for API."""
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    EVENT = "event"
    INSIGHT = "insight"
    CONVERSATION_SUMMARY = "conversation_summary"
    NOTE = "note"


class ImportanceEnum(str, Enum):
    """Importance levels for API."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SortOrder(str, Enum):
    """Sort order options."""
    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    IMPORTANCE = "importance"


# ============ SEARCH SCHEMAS ============

class SearchMemoriesInput(BaseModel):
    """Input for search_memories tool."""
    query: str = Field(
        description="Natural language search query"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    memory_types: Optional[list[MemoryTypeEnum]] = Field(
        default=None,
        description="Filter by memory types (e.g., ['fact', 'preference'])"
    )
    min_importance: Optional[ImportanceEnum] = Field(
        default=None,
        description="Minimum importance level"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date filter (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date filter (YYYY-MM-DD)"
    )
    topics: Optional[list[str]] = Field(
        default=None,
        description="Filter by topics"
    )
    entities: Optional[list[str]] = Field(
        default=None,
        description="Filter by entity names"
    )
    sort_by: SortOrder = Field(
        default=SortOrder.RELEVANCE,
        description="How to sort results"
    )


class SearchByEntityInput(BaseModel):
    """Input for search_by_entity tool."""
    entity_name: str = Field(
        description="Name of the entity to search for"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results"
    )
    include_related: bool = Field(
        default=True,
        description="Include memories mentioning related entities"
    )


class SearchByDateRangeInput(BaseModel):
    """Input for search_by_date_range tool."""
    date_from: str = Field(
        description="Start date (YYYY-MM-DD)"
    )
    date_to: str = Field(
        description="End date (YYYY-MM-DD)"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results"
    )
    memory_types: Optional[list[MemoryTypeEnum]] = Field(
        default=None,
        description="Filter by memory types"
    )


# ============ TIMELINE SCHEMAS ============

class TimelineQueryInput(BaseModel):
    """Input for timeline_query tool."""
    topic: str = Field(
        description="Topic to trace through time"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD), defaults to earliest memory"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD), defaults to now"
    )
    granularity: str = Field(
        default="month",
        description="Time grouping: day, week, month, quarter, year"
    )
    include_summaries: bool = Field(
        default=True,
        description="Generate summaries for each period"
    )


class TopicEvolutionInput(BaseModel):
    """Input for get_topic_evolution tool."""
    topic: str = Field(
        description="Topic to analyze"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD)"
    )


# ============ SAVE SCHEMAS ============

class SaveMemoryInput(BaseModel):
    """Input for save_memory tool."""
    content: str = Field(
        description="The information to remember"
    )
    memory_type: MemoryTypeEnum = Field(
        default=MemoryTypeEnum.FACT,
        description="Type of memory"
    )
    importance: ImportanceEnum = Field(
        default=ImportanceEnum.MEDIUM,
        description="Importance level"
    )
    topics: Optional[list[str]] = Field(
        default=None,
        description="Topics/tags (auto-extracted if not provided)"
    )
    entities: Optional[list[str]] = Field(
        default=None,
        description="Entity names (auto-extracted if not provided)"
    )
    occurred_at: Optional[str] = Field(
        default=None,
        description="When the event/fact occurred (YYYY-MM-DD or ISO datetime)"
    )
    source: Optional[str] = Field(
        default=None,
        description="Source of this memory (e.g., 'conversation', 'manual')"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )


class SaveConversationSummaryInput(BaseModel):
    """Input for save_conversation_summary tool."""
    summary: str = Field(
        description="Summary of the conversation"
    )
    key_points: Optional[list[str]] = Field(
        default=None,
        description="Key points from the conversation"
    )
    decisions_made: Optional[list[str]] = Field(
        default=None,
        description="Decisions made during the conversation"
    )
    action_items: Optional[list[str]] = Field(
        default=None,
        description="Action items identified"
    )
    topics_discussed: Optional[list[str]] = Field(
        default=None,
        description="Main topics discussed"
    )
    participants: Optional[list[str]] = Field(
        default=None,
        description="Participants in the conversation"
    )
    conversation_date: Optional[str] = Field(
        default=None,
        description="Date of the conversation (YYYY-MM-DD)"
    )
    importance: ImportanceEnum = Field(
        default=ImportanceEnum.MEDIUM,
        description="Importance level"
    )


class BulkImportInput(BaseModel):
    """Input for bulk_import tool."""
    memories: list[SaveMemoryInput] = Field(
        description="List of memories to import"
    )
    source: str = Field(
        default="bulk_import",
        description="Source identifier for all imported memories"
    )


# ============ ENTITY SCHEMAS ============

class ListEntitiesInput(BaseModel):
    """Input for list_entities tool."""
    entity_type: Optional[str] = Field(
        default=None,
        description="Filter by entity type (PERSON, ORG, etc.)"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of entities to return"
    )
    sort_by: str = Field(
        default="memory_count",
        description="Sort by: memory_count, name, last_seen"
    )


class GetEntityProfileInput(BaseModel):
    """Input for get_entity_profile tool."""
    entity_name: str = Field(
        description="Name of the entity"
    )
    include_memories: bool = Field(
        default=True,
        description="Include recent memories mentioning this entity"
    )
    memory_limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum memories to include"
    )


# ============ MANAGEMENT SCHEMAS ============

class UpdateMemoryInput(BaseModel):
    """Input for update_memory tool."""
    memory_id: str = Field(
        description="ID of the memory to update"
    )
    content: Optional[str] = Field(
        default=None,
        description="New content (if updating)"
    )
    memory_type: Optional[MemoryTypeEnum] = Field(
        default=None,
        description="New memory type"
    )
    importance: Optional[ImportanceEnum] = Field(
        default=None,
        description="New importance level"
    )
    topics: Optional[list[str]] = Field(
        default=None,
        description="New topics (replaces existing)"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata to merge"
    )


class DeleteMemoryInput(BaseModel):
    """Input for delete_memory tool."""
    memory_id: str = Field(
        description="ID of the memory to delete"
    )
    confirm: bool = Field(
        default=False,
        description="Confirm deletion (must be true to delete)"
    )


class GetMemoryStatsInput(BaseModel):
    """Input for get_memory_stats tool."""
    include_top_topics: bool = Field(
        default=True,
        description="Include list of top topics"
    )
    include_top_entities: bool = Field(
        default=True,
        description="Include list of top entities"
    )
    top_limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of top items to include"
    )


# ============ BROWSE SCHEMAS ============

class ListTopicsInput(BaseModel):
    """Input for list_topics tool."""
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of topics to return"
    )
    sort_by: str = Field(
        default="memory_count",
        description="Sort by: memory_count, name, recent"
    )
    min_count: int = Field(
        default=1,
        ge=1,
        description="Minimum memory count for inclusion"
    )


class ListRecentInput(BaseModel):
    """Input for list_recent tool."""
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of recent memories to return"
    )
    memory_types: Optional[list[MemoryTypeEnum]] = Field(
        default=None,
        description="Filter by memory types"
    )
    days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Only include memories from last N days"
    )


# ============ OUTPUT SCHEMAS ============

class MemoryOutput(BaseModel):
    """Memory in output format."""
    id: str
    content: str
    memory_type: str
    importance: str
    created_at: str
    occurred_at: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None
    source: Optional[str] = None
    summary: Optional[str] = None


class SearchResultOutput(BaseModel):
    """Search result output."""
    memory: MemoryOutput
    relevance_score: float
    match_reasons: list[str] = Field(default_factory=list)


class SearchMemoriesOutput(BaseModel):
    """Output for search_memories tool."""
    memories: list[SearchResultOutput]
    total_found: int
    query: str


class TimelineEntryOutput(BaseModel):
    """Timeline entry output."""
    period_label: str
    start_date: str
    end_date: str
    memory_count: int
    memories: list[MemoryOutput] = Field(default_factory=list)
    summary: Optional[str] = None
    key_events: list[str] = Field(default_factory=list)


class TimelineOutput(BaseModel):
    """Output for timeline_query tool."""
    topic: str
    date_range: tuple[str, str]
    entries: list[TimelineEntryOutput]
    total_memories: int


class TopicEvolutionOutput(BaseModel):
    """Output for get_topic_evolution tool."""
    topic: str
    evolution_summary: str
    phases: list[dict[str, Any]]
    sentiment_trend: Optional[list[dict[str, Any]]] = None


class EntityOutput(BaseModel):
    """Entity in output format."""
    id: str
    name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    memory_count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class EntityListOutput(BaseModel):
    """Output for list_entities tool."""
    entities: list[EntityOutput]
    total_count: int


class EntityProfileOutput(BaseModel):
    """Output for get_entity_profile tool."""
    entity: EntityOutput
    recent_memories: list[MemoryOutput] = Field(default_factory=list)
    related_entities: list[EntityOutput] = Field(default_factory=list)
    associated_topics: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class SaveMemoryOutput(BaseModel):
    """Output for save_memory tool."""
    memory_id: str
    extracted_entities: list[str] = Field(default_factory=list)
    extracted_topics: list[str] = Field(default_factory=list)
    message: str = "Memory saved successfully"


class BulkImportOutput(BaseModel):
    """Output for bulk_import tool."""
    imported_count: int
    failed_count: int
    memory_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MemoryStatsOutput(BaseModel):
    """Output for get_memory_stats tool."""
    total_memories: int
    memories_by_type: dict[str, int]
    memories_by_importance: dict[str, int]
    total_entities: int
    entities_by_type: dict[str, int]
    total_topics: int
    top_topics: list[dict[str, Any]] = Field(default_factory=list)
    top_entities: list[dict[str, Any]] = Field(default_factory=list)
    date_range: Optional[tuple[str, str]] = None
    last_updated: Optional[str] = None


class TopicListOutput(BaseModel):
    """Output for list_topics tool."""
    topics: list[dict[str, Any]]
    total_count: int


class DeleteMemoryOutput(BaseModel):
    """Output for delete_memory tool."""
    success: bool
    message: str
    memory_id: str
