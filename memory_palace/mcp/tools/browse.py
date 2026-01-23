"""Browse tools for Memory Palace MCP server."""

import logging
from datetime import datetime
from typing import Optional

from memory_palace.core.query_engine import QueryEngine
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.mcp.schemas import (
    TopicListParams,
    RecentMemoriesParams,
    TopicListResponse,
    TopicListItem,
    SearchResponse,
    MemoryResult,
)

logger = logging.getLogger(__name__)


async def list_topics(
    metadata_db: MetadataDB,
    params: TopicListParams
) -> dict:
    """
    List all topics/tags in the memory palace.

    Returns topics that have been extracted from or assigned to memories.
    Useful for seeing what subjects you've recorded information about.

    Topics can be sorted by:
    - count: Most frequently used topics first
    - name: Alphabetically
    - recent: Most recently used topics first

    Args:
        metadata_db: Metadata database instance
        params: List parameters

    Returns:
        List of topics with counts
    """
    try:
        # Get topics from metadata DB
        topics = await metadata_db.get_topics(
            limit=params.limit,
            sort_by=params.sort_by,
            min_count=params.min_count
        )

        # Get total count
        total_count = await metadata_db.get_topic_count()

        # Convert to response format
        topic_items = []
        for topic in topics:
            last_seen = topic.get('last_seen')
            if isinstance(last_seen, str):
                from dateutil.parser import parse
                try:
                    last_seen = parse(last_seen)
                except:
                    last_seen = datetime.utcnow()

            topic_items.append(TopicListItem(
                name=topic['name'],
                count=topic.get('count', 1),
                last_seen=last_seen if isinstance(last_seen, datetime) else datetime.utcnow()
            ))

        return TopicListResponse(
            topics=topic_items,
            total_count=total_count
        ).model_dump()

    except Exception as e:
        logger.error(f"List topics error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to list topics: {str(e)}",
            "topics": [],
            "total_count": 0
        }


async def list_recent(
    engine: QueryEngine,
    params: RecentMemoriesParams
) -> dict:
    """
    List the most recent memories.

    Returns memories in reverse chronological order (newest first).
    Useful for seeing what was recently recorded.

    Args:
        engine: QueryEngine instance
        params: List parameters

    Returns:
        List of recent memories
    """
    try:
        # Get recent memories
        memories = await engine.get_recent_memories(
            limit=params.limit,
            memory_types=params.memory_types,
            include_conversations=params.include_conversations
        )

        # Convert to response format
        memory_results = []
        for memory in memories:
            memory_results.append(MemoryResult(
                id=memory.id,
                content=memory.content,
                memory_type=memory.memory_type,
                timestamp=memory.timestamp,
                topics=memory.topics,
                entities=memory.entities,
                importance=memory.importance,
                relevance_score=1.0,
                source_conversation_id=memory.conversation_id
            ))

        return SearchResponse(
            memories=memory_results,
            total_found=len(memory_results),
            query="recent",
            filters_applied={
                'limit': params.limit,
                'memory_types': params.memory_types,
                'include_conversations': params.include_conversations
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"List recent error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to list recent memories: {str(e)}",
            "memories": [],
            "total_found": 0
        }
