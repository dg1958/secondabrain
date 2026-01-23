"""Timeline tools for Memory Palace MCP server."""

import logging
from datetime import datetime
from typing import Optional

from memory_palace.core.query_engine import QueryEngine
from memory_palace.mcp.schemas import (
    TimelineQueryParams,
    TopicEvolutionParams,
    TimelineResponse,
    TimelineEntryResult,
    TopicEvolutionResponse,
    TopicEvolutionEntry,
    MemoryResult,
)

logger = logging.getLogger(__name__)


async def timeline_query(
    engine: QueryEngine,
    params: TimelineQueryParams
) -> dict:
    """
    Get chronological timeline of memories for a topic.

    Use this to see how a topic developed over time. Results are grouped
    by time period (day, week, month, or year) and sorted chronologically.

    Example: "Show me the timeline of my machine learning project"
    This would return memories about machine learning grouped by week.

    Args:
        engine: QueryEngine instance
        params: Timeline query parameters

    Returns:
        Timeline response with grouped memories
    """
    try:
        # Convert dates
        date_from = None
        date_to = None
        if params.date_from:
            date_from = datetime.combine(params.date_from, datetime.min.time())
        if params.date_to:
            date_to = datetime.combine(params.date_to, datetime.max.time())

        # Execute timeline query
        entries = await engine.timeline_query(
            topic=params.topic,
            date_from=date_from,
            date_to=date_to,
            granularity=params.granularity,
            max_entries=params.max_entries
        )

        # Convert to response format
        entry_results = []
        total_memories = 0

        for entry in entries:
            memory_results = []
            for memory in entry.memories:
                memory_results.append(MemoryResult(
                    id=memory.id,
                    content=memory.content,
                    memory_type=memory.memory_type,
                    timestamp=memory.timestamp,
                    topics=memory.topics,
                    entities=memory.entities,
                    importance=memory.importance,
                    relevance_score=0.0,
                    source_conversation_id=memory.conversation_id
                ))

            entry_results.append(TimelineEntryResult(
                period_start=entry.period_start,
                period_end=entry.period_end,
                period_label=entry.period_label,
                memories=memory_results,
                summary=entry.summary,
                memory_count=entry.memory_count
            ))

            total_memories += entry.memory_count

        # Build date range for response
        date_range = {
            'from': str(date_from.date()) if date_from else None,
            'to': str(date_to.date()) if date_to else None,
            'granularity': params.granularity
        }

        return TimelineResponse(
            topic=params.topic,
            entries=entry_results,
            total_memories=total_memories,
            date_range=date_range
        ).model_dump()

    except Exception as e:
        logger.error(f"Timeline query error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Timeline query failed: {str(e)}",
            "topic": params.topic,
            "entries": [],
            "total_memories": 0
        }


async def get_topic_evolution(
    engine: QueryEngine,
    params: TopicEvolutionParams
) -> dict:
    """
    Analyze how thinking on a topic evolved over time.

    Use this to understand how your perspective, knowledge, or focus
    on a topic has changed. It shows key themes and trends for each
    time period.

    Example: "How has my understanding of Python evolved?"
    This would show key themes per month and whether interest increased.

    Args:
        engine: QueryEngine instance
        params: Topic evolution parameters

    Returns:
        Evolution analysis with trends and themes
    """
    try:
        # Convert dates
        date_from = None
        date_to = None
        if params.date_from:
            date_from = datetime.combine(params.date_from, datetime.min.time())
        if params.date_to:
            date_to = datetime.combine(params.date_to, datetime.max.time())

        # Execute evolution query
        result = await engine.get_topic_evolution(
            topic=params.topic,
            date_from=date_from,
            date_to=date_to,
            granularity=params.granularity
        )

        # Convert to response format
        evolution_entries = []
        for entry in result.get('evolution', []):
            evolution_entries.append(TopicEvolutionEntry(
                period_label=entry['period_label'],
                period_start=entry['period_start'],
                period_end=entry['period_end'],
                memory_count=entry['memory_count'],
                key_themes=entry['key_themes'],
                sentiment_trend=entry.get('sentiment_trend'),
                sample_memories=entry.get('sample_memories', [])
            ))

        return TopicEvolutionResponse(
            topic=params.topic,
            evolution=evolution_entries,
            overall_trend=result.get('overall_trend', 'unknown')
        ).model_dump()

    except Exception as e:
        logger.error(f"Topic evolution error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Topic evolution analysis failed: {str(e)}",
            "topic": params.topic,
            "evolution": [],
            "overall_trend": "error"
        }
