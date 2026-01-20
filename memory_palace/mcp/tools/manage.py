"""
Management tools for Memory Palace MCP server.

Provides memory update, deletion, and statistics.
"""

import logging
from typing import Optional

from ..schemas import (
    UpdateMemoryInput,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    GetMemoryStatsInput,
    MemoryStatsOutput,
    SaveMemoryOutput,
)
from ...core.query_engine import get_query_engine

logger = logging.getLogger(__name__)


async def update_memory(input_data: UpdateMemoryInput) -> Optional[SaveMemoryOutput]:
    """
    Update an existing memory.

    Allows modifying the content, type, importance, or topics of
    an existing memory.

    Args:
        input_data: Memory ID and fields to update

    Returns:
        Updated memory info or None if not found
    """
    engine = get_query_engine()

    memory = await engine.update_memory(
        memory_id=input_data.memory_id,
        content=input_data.content,
        memory_type=input_data.memory_type.value if input_data.memory_type else None,
        importance=input_data.importance.value if input_data.importance else None,
        topics=input_data.topics,
        metadata=input_data.metadata,
    )

    if not memory:
        return None

    return SaveMemoryOutput(
        memory_id=memory.id,
        extracted_entities=[],  # Not re-extracted on update
        extracted_topics=memory.topics,
        message=f"Memory {memory.id} updated successfully",
    )


async def delete_memory(input_data: DeleteMemoryInput) -> DeleteMemoryOutput:
    """
    Delete a memory from the palace.

    Requires confirmation to prevent accidental deletion.
    Permanently removes the memory from both vector and metadata databases.

    Args:
        input_data: Memory ID and confirmation flag

    Returns:
        Deletion result
    """
    if not input_data.confirm:
        return DeleteMemoryOutput(
            success=False,
            message="Deletion not confirmed. Set confirm=true to delete.",
            memory_id=input_data.memory_id,
        )

    engine = get_query_engine()

    success = await engine.delete_memory(input_data.memory_id)

    if success:
        return DeleteMemoryOutput(
            success=True,
            message=f"Memory {input_data.memory_id} deleted successfully",
            memory_id=input_data.memory_id,
        )
    else:
        return DeleteMemoryOutput(
            success=False,
            message=f"Memory {input_data.memory_id} not found or could not be deleted",
            memory_id=input_data.memory_id,
        )


async def get_memory_stats(input_data: GetMemoryStatsInput) -> MemoryStatsOutput:
    """
    Get statistics about the memory palace.

    Returns counts of memories, entities, topics, and other
    aggregate information.

    Args:
        input_data: Options for what to include

    Returns:
        Statistics about the palace
    """
    engine = get_query_engine()

    stats = await engine.get_stats(
        include_top_topics=input_data.include_top_topics,
        include_top_entities=input_data.include_top_entities,
        top_limit=input_data.top_limit,
    )

    # Format date range
    date_range = None
    if stats.date_range:
        date_range = (
            stats.date_range[0].isoformat(),
            stats.date_range[1].isoformat(),
        )

    # Format top topics
    top_topics = [
        {"name": name, "count": count}
        for name, count in stats.top_topics
    ]

    # Format top entities (if available)
    top_entities = []
    if input_data.include_top_entities:
        entities = await engine.list_entities(limit=input_data.top_limit)
        top_entities = [
            {"name": e.name, "type": e.entity_type, "count": e.memory_count}
            for e in entities
        ]

    return MemoryStatsOutput(
        total_memories=stats.total_memories,
        memories_by_type=stats.memories_by_type,
        memories_by_importance=stats.memories_by_importance,
        total_entities=stats.total_entities,
        entities_by_type=stats.entities_by_type,
        total_topics=stats.total_topics,
        top_topics=top_topics,
        top_entities=top_entities,
        date_range=date_range,
        last_updated=stats.last_updated.isoformat() if stats.last_updated else None,
    )
