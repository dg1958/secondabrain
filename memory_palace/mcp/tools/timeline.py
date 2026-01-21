"""
Timeline tools for Memory Palace MCP server.

Provides chronological reconstruction and topic evolution analysis.
"""

import logging
from datetime import datetime
from typing import Optional

from ..schemas import (
    TimelineQueryInput,
    TimelineOutput,
    TimelineEntryOutput,
    MemoryOutput,
    TopicEvolutionInput,
    TopicEvolutionOutput,
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


async def timeline_query(input_data: TimelineQueryInput) -> TimelineOutput:
    """
    Reconstruct a chronological timeline for a topic.

    Groups memories about a topic into time periods, helping understand
    how discussions or events unfolded over time.

    Args:
        input_data: Timeline parameters including topic and date range

    Returns:
        Timeline with grouped entries and summaries
    """
    engine = get_query_engine()

    # Parse dates
    date_from = None
    date_to = None
    if input_data.date_from:
        date_from = datetime.fromisoformat(input_data.date_from)
    if input_data.date_to:
        date_to = datetime.fromisoformat(input_data.date_to)

    entries = await engine.timeline_query(
        topic=input_data.topic,
        date_from=date_from,
        date_to=date_to,
        granularity=input_data.granularity,
        include_summaries=input_data.include_summaries,
    )

    # Convert to output format
    output_entries = []
    total_memories = 0

    for entry in entries:
        memory_outputs = [_memory_to_output(m) for m in entry.memories[:5]]  # Limit per entry
        total_memories += len(entry.memories)

        output_entries.append(TimelineEntryOutput(
            period_label=entry.period_label,
            start_date=entry.start_date.isoformat(),
            end_date=entry.end_date.isoformat(),
            memory_count=len(entry.memories),
            memories=memory_outputs,
            summary=entry.summary,
            key_events=entry.key_events,
        ))

    # Determine actual date range
    if output_entries:
        actual_start = output_entries[0].start_date
        actual_end = output_entries[-1].end_date
    else:
        actual_start = input_data.date_from or datetime.utcnow().isoformat()
        actual_end = input_data.date_to or datetime.utcnow().isoformat()

    return TimelineOutput(
        topic=input_data.topic,
        date_range=(actual_start, actual_end),
        entries=output_entries,
        total_memories=total_memories,
    )


async def get_topic_evolution(input_data: TopicEvolutionInput) -> TopicEvolutionOutput:
    """
    Analyze how thinking or discussion on a topic evolved over time.

    Shows phases of development, sentiment trends, and how perspectives
    may have changed.

    Args:
        input_data: Topic and optional date range

    Returns:
        Evolution analysis with phases and trends
    """
    engine = get_query_engine()

    # Parse dates
    date_from = None
    date_to = None
    if input_data.date_from:
        date_from = datetime.fromisoformat(input_data.date_from)
    if input_data.date_to:
        date_to = datetime.fromisoformat(input_data.date_to)

    evolution = await engine.get_topic_evolution(
        topic=input_data.topic,
        date_from=date_from,
        date_to=date_to,
    )

    return TopicEvolutionOutput(
        topic=evolution["topic"],
        evolution_summary=evolution["evolution_summary"],
        phases=evolution["phases"],
        sentiment_trend=evolution.get("sentiment_trend"),
    )
