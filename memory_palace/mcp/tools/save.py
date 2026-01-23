"""Save tools for Memory Palace MCP server."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.metadata_extractor import get_extractor
from memory_palace.core.models import MemoryType, ImportanceLevel
from memory_palace.mcp.schemas import (
    MemorySaveParams,
    ConversationSummaryParams,
    SaveResponse,
)

logger = logging.getLogger(__name__)


async def save_memory(
    vector_db: VectorDB,
    metadata_db: MetadataDB,
    params: MemorySaveParams
) -> dict:
    """
    Save a new memory to the palace.

    This tool stores a new memory with automatic extraction of entities
    and topics if not provided. Use this to record facts, preferences,
    decisions, events, insights, or corrections.

    Memory types:
    - fact: A piece of factual information
    - preference: A personal preference or like/dislike
    - decision: A decision that was made
    - event: Something that happened
    - insight: An insight or realization
    - correction: A correction to previous information

    Args:
        vector_db: Vector database instance
        metadata_db: Metadata database instance
        params: Memory save parameters

    Returns:
        Save response with extracted metadata
    """
    try:
        # Generate ID
        memory_id = str(uuid.uuid4())

        # Get timestamp
        timestamp = params.timestamp or datetime.utcnow()

        # Extract metadata if not provided
        extractor = get_extractor()
        extracted = extractor.extract_all(params.content)

        # Use provided values or extracted ones
        topics = params.topics if params.topics else extracted.get('topics', [])
        entities = extracted.get('entities', {})
        sentiment = extracted.get('sentiment', 0.0)

        # Validate memory type
        try:
            memory_type = MemoryType(params.memory_type)
        except ValueError:
            memory_type = MemoryType.FACT

        # Validate importance
        try:
            importance = ImportanceLevel(params.importance)
        except ValueError:
            importance = ImportanceLevel.MEDIUM

        # Prepare metadata
        metadata = {
            'memory_type': memory_type.value,
            'timestamp': timestamp.isoformat(),
            'importance': importance.value,
            'topics': topics,
            'entities': entities,
            'sentiment': sentiment,
            'source_context': params.source_context,
        }

        # Save to vector DB
        await vector_db.add_memory(
            id=memory_id,
            content=params.content,
            metadata=metadata
        )

        # Save to metadata DB
        await metadata_db.add_memory_meta(
            id=memory_id,
            content=params.content,
            memory_type=memory_type.value,
            timestamp=timestamp,
            importance=importance.value,
            topics=topics,
            entities=entities,
            sentiment=sentiment
        )

        logger.info(f"Saved memory {memory_id}")

        return SaveResponse(
            success=True,
            memory_id=memory_id,
            extracted_topics=topics,
            extracted_entities=entities,
            message=f"Memory saved successfully with ID {memory_id}"
        ).model_dump()

    except Exception as e:
        logger.error(f"Save memory error: {e}", exc_info=True)
        return {
            "error": True,
            "success": False,
            "message": f"Failed to save memory: {str(e)}",
            "memory_id": "",
            "extracted_topics": [],
            "extracted_entities": {}
        }


async def save_conversation_summary(
    vector_db: VectorDB,
    metadata_db: MetadataDB,
    params: ConversationSummaryParams
) -> dict:
    """
    Save a conversation summary to the palace.

    Use this to store summaries of conversations for future reference.
    The summary will be searchable and linked to a conversation record.

    Args:
        vector_db: Vector database instance
        metadata_db: Metadata database instance
        params: Conversation summary parameters

    Returns:
        Save response with conversation ID
    """
    try:
        # Generate IDs
        memory_id = str(uuid.uuid4())
        conversation_id = str(uuid.uuid4())

        # Get timestamps
        started_at = params.started_at or datetime.utcnow()
        ended_at = params.ended_at or datetime.utcnow()

        # Extract metadata
        extractor = get_extractor()
        extracted = extractor.extract_all(params.summary)

        # Combine topics
        topics = params.topics if params.topics else extracted.get('topics', [])
        entities = extracted.get('entities', {})

        # Build full content
        content_parts = [params.summary]
        if params.key_points:
            content_parts.append("\nKey points:")
            for point in params.key_points:
                content_parts.append(f"- {point}")
        full_content = "\n".join(content_parts)

        # Prepare metadata
        metadata = {
            'memory_type': 'conversation',
            'timestamp': ended_at.isoformat(),
            'importance': 'medium',
            'topics': topics,
            'entities': entities,
            'conversation_id': conversation_id,
            'started_at': started_at.isoformat(),
            'ended_at': ended_at.isoformat(),
        }

        # Save memory to vector DB
        await vector_db.add_memory(
            id=memory_id,
            content=full_content,
            metadata=metadata
        )

        # Save memory metadata
        await metadata_db.add_memory_meta(
            id=memory_id,
            content=full_content,
            memory_type='conversation',
            timestamp=ended_at,
            importance='medium',
            topics=topics,
            entities=entities,
            conversation_id=conversation_id
        )

        # Save conversation record
        await metadata_db.add_conversation(
            id=conversation_id,
            started_at=started_at,
            ended_at=ended_at,
            summary=params.summary,
            message_count=len(params.key_points) if params.key_points else 0,
            topics=topics
        )

        logger.info(f"Saved conversation summary {conversation_id}")

        return SaveResponse(
            success=True,
            memory_id=memory_id,
            extracted_topics=topics,
            extracted_entities=entities,
            message=f"Conversation summary saved with ID {conversation_id}"
        ).model_dump()

    except Exception as e:
        logger.error(f"Save conversation summary error: {e}", exc_info=True)
        return {
            "error": True,
            "success": False,
            "message": f"Failed to save conversation summary: {str(e)}",
            "memory_id": "",
            "extracted_topics": [],
            "extracted_entities": {}
        }
