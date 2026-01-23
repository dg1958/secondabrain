"""Management tools for Memory Palace MCP server."""

import logging
from datetime import datetime
from typing import Optional

from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.query_engine import QueryEngine
from memory_palace.core.metadata_extractor import get_extractor
from memory_palace.mcp.schemas import (
    MemoryUpdateParams,
    MemoryDeleteParams,
    UpdateResponse,
    DeleteResponse,
    StatsResponse,
)

logger = logging.getLogger(__name__)


async def update_memory(
    vector_db: VectorDB,
    metadata_db: MetadataDB,
    params: MemoryUpdateParams
) -> dict:
    """
    Update an existing memory.

    Use this to correct or enhance a previously stored memory.
    You can update the content, topics, importance, or type.

    Only provide the fields you want to change - other fields
    will remain unchanged.

    Args:
        vector_db: Vector database instance
        metadata_db: Metadata database instance
        params: Update parameters

    Returns:
        Update response indicating success
    """
    try:
        # Check if memory exists
        existing = await vector_db.get_by_id(params.memory_id)
        if not existing:
            return UpdateResponse(
                success=False,
                memory_id=params.memory_id,
                message=f"Memory {params.memory_id} not found"
            ).model_dump()

        # Build updates
        vector_updates = {}
        meta_updates = {}

        # Handle content update
        if params.content is not None:
            vector_updates['content'] = params.content
            meta_updates['content_preview'] = params.content[:200]

            # Re-extract metadata from new content
            extractor = get_extractor()
            extracted = extractor.extract_all(params.content)

            # Update topics if not explicitly provided
            if params.topics is None:
                params.topics = extracted.get('topics', [])

            # Always update entities from new content
            meta_updates['entities'] = extracted.get('entities', {})

        # Handle other updates
        if params.topics is not None:
            meta_updates['topics'] = params.topics
            vector_updates['metadata'] = vector_updates.get('metadata', {})
            vector_updates.setdefault('metadata', {})['topics'] = params.topics

        if params.importance is not None:
            meta_updates['importance'] = params.importance
            vector_updates.setdefault('metadata', {})['importance'] = params.importance

        if params.memory_type is not None:
            meta_updates['memory_type'] = params.memory_type
            vector_updates.setdefault('metadata', {})['memory_type'] = params.memory_type

        # Apply vector DB updates
        if vector_updates:
            content = vector_updates.get('content')
            metadata = vector_updates.get('metadata')

            # Get existing metadata and merge
            if metadata:
                existing_meta = existing.get('metadata', {})
                existing_meta.update(metadata)
                metadata = existing_meta

            await vector_db.update(
                id=params.memory_id,
                content=content,
                metadata=metadata
            )

        # Apply metadata DB updates
        if meta_updates:
            await metadata_db.update_memory_meta(
                id=params.memory_id,
                **meta_updates
            )

        logger.info(f"Updated memory {params.memory_id}")

        return UpdateResponse(
            success=True,
            memory_id=params.memory_id,
            message=f"Memory {params.memory_id} updated successfully"
        ).model_dump()

    except Exception as e:
        logger.error(f"Update memory error: {e}", exc_info=True)
        return {
            "error": True,
            "success": False,
            "memory_id": params.memory_id,
            "message": f"Failed to update memory: {str(e)}"
        }


async def delete_memory(
    vector_db: VectorDB,
    metadata_db: MetadataDB,
    params: MemoryDeleteParams
) -> dict:
    """
    Delete a memory from the palace.

    This permanently removes a memory. Use with caution.
    You must set confirm=true to actually delete.

    Args:
        vector_db: Vector database instance
        metadata_db: Metadata database instance
        params: Delete parameters

    Returns:
        Delete response indicating success
    """
    try:
        # Require confirmation
        if not params.confirm:
            return DeleteResponse(
                success=False,
                memory_id=params.memory_id,
                message="Deletion not confirmed. Set confirm=true to delete."
            ).model_dump()

        # Check if memory exists
        existing = await vector_db.get_by_id(params.memory_id)
        if not existing:
            return DeleteResponse(
                success=False,
                memory_id=params.memory_id,
                message=f"Memory {params.memory_id} not found"
            ).model_dump()

        # Delete from vector DB
        await vector_db.delete(params.memory_id)

        # Delete from metadata DB
        await metadata_db.delete_memory_meta(params.memory_id)

        logger.info(f"Deleted memory {params.memory_id}")

        return DeleteResponse(
            success=True,
            memory_id=params.memory_id,
            message=f"Memory {params.memory_id} deleted successfully"
        ).model_dump()

    except Exception as e:
        logger.error(f"Delete memory error: {e}", exc_info=True)
        return {
            "error": True,
            "success": False,
            "memory_id": params.memory_id,
            "message": f"Failed to delete memory: {str(e)}"
        }


async def get_memory_stats(
    engine: QueryEngine
) -> dict:
    """
    Get statistics about the memory palace.

    Returns counts, distributions, and top items for:
    - Total memories, entities, topics, conversations
    - Memories by type and importance
    - Date range of memories
    - Most mentioned topics and entities

    Use this to understand the overall state of your memory palace.

    Args:
        engine: QueryEngine instance

    Returns:
        Palace statistics
    """
    try:
        stats = await engine.get_stats()

        # Format top topics
        top_topics = []
        for item in stats.top_topics:
            if isinstance(item, tuple):
                top_topics.append({'name': item[0], 'count': item[1]})
            else:
                top_topics.append(item)

        # Format top entities
        top_entities = []
        for item in stats.top_entities:
            if isinstance(item, tuple):
                top_entities.append({
                    'name': item[0],
                    'type': item[1],
                    'count': item[2]
                })
            else:
                top_entities.append(item)

        return StatsResponse(
            total_memories=stats.total_memories,
            total_entities=stats.total_entities,
            total_topics=stats.total_topics,
            total_conversations=stats.total_conversations,
            memories_by_type=stats.memories_by_type,
            memories_by_importance=stats.memories_by_importance,
            oldest_memory=stats.oldest_memory,
            newest_memory=stats.newest_memory,
            top_topics=top_topics,
            top_entities=top_entities
        ).model_dump()

    except Exception as e:
        logger.error(f"Get stats error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to get statistics: {str(e)}",
            "total_memories": 0,
            "total_entities": 0,
            "total_topics": 0
        }
