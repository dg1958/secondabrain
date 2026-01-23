"""Search tools for Memory Palace MCP server."""

import logging
from datetime import datetime, date
from typing import Optional

from memory_palace.core.query_engine import QueryEngine
from memory_palace.mcp.schemas import (
    MemorySearchParams,
    EntitySearchParams,
    DateRangeSearchParams,
    SearchResponse,
    MemoryResult,
)

logger = logging.getLogger(__name__)


async def search_memories(
    engine: QueryEngine,
    params: MemorySearchParams
) -> dict:
    """
    Search memories using semantic search with optional filters.

    This is the primary search tool. It performs semantic similarity search
    on memory content and can filter by date range, topics, entities, and
    memory types.

    Args:
        engine: QueryEngine instance
        params: Search parameters

    Returns:
        Search response with matching memories
    """
    try:
        # Build filters
        filters = {}

        if params.date_from:
            filters['date_from'] = datetime.combine(params.date_from, datetime.min.time())
        if params.date_to:
            filters['date_to'] = datetime.combine(params.date_to, datetime.max.time())
        if params.topics:
            filters['topics'] = params.topics
        if params.entities:
            filters['entities'] = params.entities
        if params.memory_types:
            filters['memory_types'] = params.memory_types

        # Execute search
        results = await engine.search(
            query=params.query,
            limit=params.limit,
            filters=filters if filters else None,
            min_relevance=params.min_relevance
        )

        # Convert to response format
        memory_results = []
        for result in results:
            memory_results.append(MemoryResult(
                id=result.memory.id,
                content=result.memory.content,
                memory_type=result.memory.memory_type,
                timestamp=result.memory.timestamp,
                topics=result.memory.topics,
                entities=result.memory.entities,
                importance=result.memory.importance,
                relevance_score=result.relevance_score,
                source_conversation_id=result.memory.conversation_id
            ))

        return SearchResponse(
            memories=memory_results,
            total_found=len(memory_results),
            query=params.query,
            filters_applied={
                'date_from': str(params.date_from) if params.date_from else None,
                'date_to': str(params.date_to) if params.date_to else None,
                'topics': params.topics,
                'entities': params.entities,
                'memory_types': params.memory_types,
                'min_relevance': params.min_relevance
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Search failed: {str(e)}",
            "memories": [],
            "total_found": 0
        }


async def search_by_entity(
    engine: QueryEngine,
    params: EntitySearchParams
) -> dict:
    """
    Find memories mentioning a specific entity.

    Use this when you want to find all memories related to a particular
    person, organization, location, project, or concept.

    Args:
        engine: QueryEngine instance
        params: Entity search parameters

    Returns:
        Search response with memories mentioning the entity
    """
    try:
        # Convert dates
        date_from = None
        date_to = None
        if params.date_from:
            date_from = datetime.combine(params.date_from, datetime.min.time())
        if params.date_to:
            date_to = datetime.combine(params.date_to, datetime.max.time())

        # Execute search
        results = await engine.search_by_entity(
            entity_name=params.entity_name,
            entity_type=params.entity_type,
            limit=params.limit,
            date_from=date_from,
            date_to=date_to
        )

        # Convert to response format
        memory_results = []
        for result in results:
            memory_results.append(MemoryResult(
                id=result.memory.id,
                content=result.memory.content,
                memory_type=result.memory.memory_type,
                timestamp=result.memory.timestamp,
                topics=result.memory.topics,
                entities=result.memory.entities,
                importance=result.memory.importance,
                relevance_score=result.relevance_score,
                source_conversation_id=result.memory.conversation_id
            ))

        return SearchResponse(
            memories=memory_results,
            total_found=len(memory_results),
            query=f"entity:{params.entity_name}",
            filters_applied={
                'entity_name': params.entity_name,
                'entity_type': params.entity_type,
                'date_from': str(params.date_from) if params.date_from else None,
                'date_to': str(params.date_to) if params.date_to else None,
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"Entity search error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Entity search failed: {str(e)}",
            "memories": [],
            "total_found": 0
        }


async def search_by_date_range(
    engine: QueryEngine,
    params: DateRangeSearchParams
) -> dict:
    """
    Find memories within a specific date range.

    Use this when you want to see what was recorded during a particular
    time period, such as "last week" or "in January 2024".

    Args:
        engine: QueryEngine instance
        params: Date range search parameters

    Returns:
        Search response with memories in the date range
    """
    try:
        # Convert dates
        date_from = datetime.combine(params.date_from, datetime.min.time())
        date_to = datetime.combine(params.date_to, datetime.max.time())

        # Execute search
        memories = await engine.search_by_date_range(
            date_from=date_from,
            date_to=date_to,
            topics=params.topics,
            memory_types=params.memory_types,
            limit=params.limit
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
                relevance_score=1.0,  # Date range searches don't have relevance
                source_conversation_id=memory.conversation_id
            ))

        return SearchResponse(
            memories=memory_results,
            total_found=len(memory_results),
            query=f"date:{params.date_from} to {params.date_to}",
            filters_applied={
                'date_from': str(params.date_from),
                'date_to': str(params.date_to),
                'topics': params.topics,
                'memory_types': params.memory_types,
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"Date range search error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Date range search failed: {str(e)}",
            "memories": [],
            "total_found": 0
        }
