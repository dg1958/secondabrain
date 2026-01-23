"""Entity tools for Memory Palace MCP server."""

import logging
from datetime import datetime
from typing import Optional

from memory_palace.core.query_engine import QueryEngine
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.mcp.schemas import (
    EntityListParams,
    EntityProfileParams,
    EntityListResponse,
    EntityListItem,
    EntityProfileResponse,
    MemoryResult,
)

logger = logging.getLogger(__name__)


async def list_entities(
    metadata_db: MetadataDB,
    params: EntityListParams
) -> dict:
    """
    List all known entities in the memory palace.

    Returns entities (people, organizations, locations, projects, concepts)
    that have been mentioned in memories. Useful for seeing what/who you've
    talked about most.

    Entity types:
    - PERSON: People's names
    - ORG: Organizations, companies
    - LOCATION: Places, addresses
    - PROJECT: Projects you've worked on
    - CONCEPT: Abstract concepts, technologies

    Args:
        metadata_db: Metadata database instance
        params: List parameters

    Returns:
        List of entities with mention counts
    """
    try:
        # Get entities from metadata DB
        entities = await metadata_db.get_entities(
            entity_type=params.entity_type,
            limit=params.limit,
            sort_by=params.sort_by
        )

        # Get total count
        total_count = await metadata_db.get_entity_count(params.entity_type)

        # Convert to response format
        entity_items = []
        for entity in entities:
            last_seen = entity.get('last_seen')
            if isinstance(last_seen, str):
                from dateutil.parser import parse
                try:
                    last_seen = parse(last_seen)
                except:
                    last_seen = datetime.utcnow()

            entity_items.append(EntityListItem(
                name=entity['name'],
                entity_type=entity['entity_type'],
                mention_count=entity.get('mention_count', 1),
                last_seen=last_seen if isinstance(last_seen, datetime) else datetime.utcnow()
            ))

        return EntityListResponse(
            entities=entity_items,
            total_count=total_count
        ).model_dump()

    except Exception as e:
        logger.error(f"List entities error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to list entities: {str(e)}",
            "entities": [],
            "total_count": 0
        }


async def get_entity_profile(
    engine: QueryEngine,
    params: EntityProfileParams
) -> dict:
    """
    Get comprehensive profile of a specific entity.

    Returns detailed information about an entity including when it was
    first/last mentioned, related topics, key facts, and recent memories.

    Use this to get a complete picture of everything you know about
    a person, organization, or concept.

    Args:
        engine: QueryEngine instance
        params: Profile parameters

    Returns:
        Comprehensive entity profile
    """
    try:
        # Get entity profile
        profile = await engine.get_entity_profile(
            entity_name=params.entity_name,
            entity_type=params.entity_type,
            include_memories=params.include_memories,
            memory_limit=params.memory_limit
        )

        if not profile:
            return {
                "error": True,
                "message": f"Entity '{params.entity_name}' not found",
                "name": params.entity_name,
                "entity_type": params.entity_type or "unknown"
            }

        # Convert memories to response format
        memory_results = []
        for memory in profile.recent_memories:
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

        return EntityProfileResponse(
            name=profile.name,
            entity_type=profile.entity_type,
            mention_count=profile.mention_count,
            first_seen=profile.first_seen,
            last_seen=profile.last_seen,
            related_topics=profile.related_topics,
            related_entities=profile.related_entities,
            key_facts=profile.key_facts,
            recent_memories=memory_results
        ).model_dump()

    except Exception as e:
        logger.error(f"Get entity profile error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to get entity profile: {str(e)}",
            "name": params.entity_name,
            "entity_type": params.entity_type or "unknown"
        }
