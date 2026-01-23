"""MCP Tool implementations for Memory Palace."""

from memory_palace.mcp.tools.search import (
    search_memories,
    search_by_entity,
    search_by_date_range,
)
from memory_palace.mcp.tools.timeline import (
    timeline_query,
    get_topic_evolution,
)
from memory_palace.mcp.tools.save import (
    save_memory,
    save_conversation_summary,
)
from memory_palace.mcp.tools.entities import (
    list_entities,
    get_entity_profile,
)
from memory_palace.mcp.tools.manage import (
    update_memory,
    delete_memory,
    get_memory_stats,
)
from memory_palace.mcp.tools.browse import (
    list_topics,
    list_recent,
)

__all__ = [
    # Search tools
    "search_memories",
    "search_by_entity",
    "search_by_date_range",
    # Timeline tools
    "timeline_query",
    "get_topic_evolution",
    # Save tools
    "save_memory",
    "save_conversation_summary",
    # Entity tools
    "list_entities",
    "get_entity_profile",
    # Management tools
    "update_memory",
    "delete_memory",
    "get_memory_stats",
    # Browse tools
    "list_topics",
    "list_recent",
]
