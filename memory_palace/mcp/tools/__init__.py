"""MCP tool implementations for Memory Palace."""

from .search import (
    search_memories,
    search_by_entity,
    search_by_date_range,
)
from .timeline import (
    timeline_query,
    get_topic_evolution,
)
from .save import (
    save_memory,
    save_conversation_summary,
    bulk_import,
)
from .entities import (
    list_entities,
    get_entity_profile,
)
from .manage import (
    update_memory,
    delete_memory,
    get_memory_stats,
)
from .browse import (
    list_topics,
    list_recent,
)

__all__ = [
    # Search
    "search_memories",
    "search_by_entity",
    "search_by_date_range",
    # Timeline
    "timeline_query",
    "get_topic_evolution",
    # Save
    "save_memory",
    "save_conversation_summary",
    "bulk_import",
    # Entities
    "list_entities",
    "get_entity_profile",
    # Manage
    "update_memory",
    "delete_memory",
    "get_memory_stats",
    # Browse
    "list_topics",
    "list_recent",
]
