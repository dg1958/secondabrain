"""
Search tools for Memory Palace MCP server.

Provides semantic and metadata-based search capabilities.
"""

import logging
from datetime import datetime
from typing import Optional

from ..schemas import (
    SearchMemoriesInput,
    SearchMemoriesOutput,
    SearchResultOutput,
    MemoryOutput,
    SearchByEntityInput,
    SearchByDateRangeInput,
)
from ...core.query_engine import get_query_engine

logger = logging.getLogger(__name__)


def _memory_to_output(memory) -> MemoryOutput:
    """Convert Memory model to output schema."""
    return MemoryOutput(
        id=memory.id,
        content=memory.content,
        memory_type=memory.memory_type,
        importance=memory.importance,
        created_at=memory.created_at.isoformat(),
        occurred_at=memory.occurred_at.isoformat() if memory.occurred_at else None,
        topics=memory.topics,
        entities=memory.entities,
        sentiment_score=memory.sentiment_score,
        source=memory.source,
        summary=memory.summary,
    )


async def search_memories(input_data: SearchMemoriesInput) -> SearchMemoriesOutput:
    """
    Search the memory palace using semantic search with optional filters.

    This is the primary search tool. It uses embeddings for semantic matching
    and supports filtering by type, importance, date range, topics, and entities.

    Args:
        input_data: Search parameters including query, filters, and limits

    Returns:
        Search results with relevance scores
    """
    engine = get_query_engine()

    # Parse date filters
    date_from = None
    date_to = None
    if input_data.date_from:
        date_from = datetime.fromisoformat(input_data.date_from)
    if input_data.date_to:
        date_to = datetime.fromisoformat(input_data.date_to)

    # Convert memory types
    memory_types = None
    if input_data.memory_types:
        memory_types = [t.value for t in input_data.memory_types]

    # Perform search
    results = await engine.search(
        query=input_data.query,
        limit=input_data.limit,
        memory_types=memory_types,
        min_importance=input_data.min_importance.value if input_data.min_importance else None,
        date_from=date_from,
        date_to=date_to,
        topics=input_data.topics,
        entities=input_data.entities,
        sort_by=input_data.sort_by.value,
    )

    # Convert to output format
    output_results = []
    for result in results:
        output_results.append(SearchResultOutput(
            memory=_memory_to_output(result.memory),
            relevance_score=result.relevance_score,
            match_reasons=result.match_reasons,
        ))

    return SearchMemoriesOutput(
        memories=output_results,
        total_found=len(output_results),
        query=input_data.query,
    )


async def search_by_entity(input_data: SearchByEntityInput) -> SearchMemoriesOutput:
    """
    Find all memories mentioning a specific entity (person, organization, etc.).

    This is useful when you want to know everything about a particular
    person, organization, project, or other named entity.

    Args:
        input_data: Entity search parameters

    Returns:
        Memories mentioning the entity
    """
    engine = get_query_engine()

    results = await engine.search_by_entity(
        entity_name=input_data.entity_name,
        limit=input_data.limit,
        include_related=input_data.include_related,
    )

    output_results = []
    for result in results:
        output_results.append(SearchResultOutput(
            memory=_memory_to_output(result.memory),
            relevance_score=result.relevance_score,
            match_reasons=result.match_reasons,
        ))

    return SearchMemoriesOutput(
        memories=output_results,
        total_found=len(output_results),
        query=f"entity:{input_data.entity_name}",
    )


async def search_by_date_range(input_data: SearchByDateRangeInput) -> SearchMemoriesOutput:
    """
    Get all memories within a specific date range.

    Useful for finding what was discussed during a particular time period.

    Args:
        input_data: Date range parameters

    Returns:
        Memories within the date range
    """
    engine = get_query_engine()

    date_from = datetime.fromisoformat(input_data.date_from)
    date_to = datetime.fromisoformat(input_data.date_to)

    memory_types = None
    if input_data.memory_types:
        memory_types = [t.value for t in input_data.memory_types]

    memories = await engine.search_by_date_range(
        date_from=date_from,
        date_to=date_to,
        memory_types=memory_types,
        limit=input_data.limit,
    )

    output_results = []
    for memory in memories:
        output_results.append(SearchResultOutput(
            memory=_memory_to_output(memory),
            relevance_score=1.0,  # Date range doesn't have relevance
            match_reasons=[f"Within date range: {input_data.date_from} to {input_data.date_to}"],
        ))

    return SearchMemoriesOutput(
        memories=output_results,
        total_found=len(output_results),
        query=f"date:{input_data.date_from}..{input_data.date_to}",
    )
