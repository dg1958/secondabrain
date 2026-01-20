"""
Entity tools for Memory Palace MCP server.

Provides entity listing and profile retrieval.
"""

import logging
from typing import Optional

from ..schemas import (
    ListEntitiesInput,
    EntityListOutput,
    EntityOutput,
    GetEntityProfileInput,
    EntityProfileOutput,
    MemoryOutput,
)
from ...core.query_engine import get_query_engine

logger = logging.getLogger(__name__)


def _entity_to_output(entity) -> EntityOutput:
    """Convert Entity model to output schema."""
    return EntityOutput(
        id=entity.id,
        name=entity.name,
        entity_type=entity.entity_type,
        aliases=entity.aliases,
        description=entity.description,
        memory_count=entity.memory_count,
        first_seen=entity.first_seen.isoformat() if entity.first_seen else None,
        last_seen=entity.last_seen.isoformat() if entity.last_seen else None,
    )


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


async def list_entities(input_data: ListEntitiesInput) -> EntityListOutput:
    """
    List all known entities in the memory palace.

    Returns people, organizations, projects, and other named entities
    that have been mentioned in memories.

    Args:
        input_data: Filter and sort parameters

    Returns:
        List of entities with memory counts
    """
    engine = get_query_engine()

    entities = await engine.list_entities(
        entity_type=input_data.entity_type,
        limit=input_data.limit,
        sort_by=input_data.sort_by,
    )

    output_entities = [_entity_to_output(e) for e in entities]

    return EntityListOutput(
        entities=output_entities,
        total_count=len(output_entities),
    )


async def get_entity_profile(input_data: GetEntityProfileInput) -> Optional[EntityProfileOutput]:
    """
    Get comprehensive information about a specific entity.

    Returns all known information including recent memories,
    related entities, and associated topics.

    Args:
        input_data: Entity name and options

    Returns:
        Entity profile or None if not found
    """
    engine = get_query_engine()

    profile = await engine.get_entity_profile(
        entity_name=input_data.entity_name,
        include_memories=input_data.include_memories,
        memory_limit=input_data.memory_limit,
    )

    if not profile:
        return None

    return EntityProfileOutput(
        entity=_entity_to_output(profile.entity),
        recent_memories=[_memory_to_output(m) for m in profile.recent_memories],
        related_entities=[_entity_to_output(e) for e in profile.related_entities],
        associated_topics=profile.associated_topics,
        summary=profile.summary,
    )
