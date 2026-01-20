"""
Browse tools for Memory Palace MCP server.

Provides topic listing and recent memory browsing.
"""

import logging
from typing import Optional

from ..schemas import (
    ListTopicsInput,
    TopicListOutput,
    ListRecentInput,
    SearchMemoriesOutput,
    SearchResultOutput,
    MemoryOutput,
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


async def list_topics(input_data: ListTopicsInput) -> TopicListOutput:
    """
    List all topics in the memory palace.

    Returns topics sorted by frequency or name, with memory counts.
    Useful for discovering what subjects are covered in the palace.

    Args:
        input_data: Filter and sort options

    Returns:
        List of topics with counts
    """
    engine = get_query_engine()

    topics = await engine.list_topics(
        limit=input_data.limit,
        sort_by=input_data.sort_by,
        min_count=input_data.min_count,
    )

    return TopicListOutput(
        topics=topics,
        total_count=len(topics),
    )


async def list_recent(input_data: ListRecentInput) -> SearchMemoriesOutput:
    """
    Get the most recent memories.

    Useful for reviewing what was recently added or discussed.
    Can filter by memory type and time window.

    Args:
        input_data: Limit, type filter, and time window

    Returns:
        Recent memories in chronological order
    """
    engine = get_query_engine()

    # Convert memory types
    memory_types = None
    if input_data.memory_types:
        memory_types = [t.value for t in input_data.memory_types]

    memories = await engine.list_recent(
        limit=input_data.limit,
        memory_types=memory_types,
        days=input_data.days,
    )

    output_results = []
    for memory in memories:
        output_results.append(SearchResultOutput(
            memory=_memory_to_output(memory),
            relevance_score=1.0,
            match_reasons=["Recent memory"],
        ))

    return SearchMemoriesOutput(
        memories=output_results,
        total_found=len(output_results),
        query="recent",
    )
