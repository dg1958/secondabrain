"""
Save tools for Memory Palace MCP server.

Provides memory storage and bulk import capabilities.
"""

import logging
from datetime import datetime
from typing import Optional

from ..schemas import (
    SaveMemoryInput,
    SaveMemoryOutput,
    SaveConversationSummaryInput,
    BulkImportInput,
    BulkImportOutput,
)
from ...core.query_engine import get_query_engine

logger = logging.getLogger(__name__)


async def save_memory(input_data: SaveMemoryInput) -> SaveMemoryOutput:
    """
    Save a new memory to the palace.

    Automatically extracts entities and topics from the content if not
    provided explicitly. Use this to remember facts, preferences, decisions,
    events, or insights.

    Args:
        input_data: Memory content and metadata

    Returns:
        Confirmation with extracted metadata
    """
    engine = get_query_engine()

    # Parse occurred_at if provided
    occurred_at = None
    if input_data.occurred_at:
        try:
            occurred_at = datetime.fromisoformat(input_data.occurred_at)
        except ValueError:
            # Try parsing date only
            occurred_at = datetime.strptime(input_data.occurred_at, "%Y-%m-%d")

    memory, extracted_entities, extracted_topics = await engine.save_memory(
        content=input_data.content,
        memory_type=input_data.memory_type.value,
        importance=input_data.importance.value,
        topics=input_data.topics,
        entities=input_data.entities,
        occurred_at=occurred_at,
        source=input_data.source,
        metadata=input_data.metadata,
    )

    return SaveMemoryOutput(
        memory_id=memory.id,
        extracted_entities=extracted_entities,
        extracted_topics=extracted_topics,
        message=f"Memory saved successfully with ID {memory.id}",
    )


async def save_conversation_summary(input_data: SaveConversationSummaryInput) -> SaveMemoryOutput:
    """
    Save a summary of a conversation for future reference.

    This is specifically designed for storing conversation summaries with
    structured information about what was discussed, decisions made, and
    action items identified.

    Args:
        input_data: Conversation summary and structured data

    Returns:
        Confirmation with extracted metadata
    """
    engine = get_query_engine()

    # Build structured content
    content_parts = [input_data.summary]

    if input_data.key_points:
        content_parts.append("\n\nKey Points:")
        for point in input_data.key_points:
            content_parts.append(f"- {point}")

    if input_data.decisions_made:
        content_parts.append("\n\nDecisions Made:")
        for decision in input_data.decisions_made:
            content_parts.append(f"- {decision}")

    if input_data.action_items:
        content_parts.append("\n\nAction Items:")
        for item in input_data.action_items:
            content_parts.append(f"- {item}")

    content = "\n".join(content_parts)

    # Parse conversation date
    occurred_at = None
    if input_data.conversation_date:
        try:
            occurred_at = datetime.fromisoformat(input_data.conversation_date)
        except ValueError:
            occurred_at = datetime.strptime(input_data.conversation_date, "%Y-%m-%d")

    # Build metadata
    metadata = {}
    if input_data.key_points:
        metadata["key_points"] = input_data.key_points
    if input_data.decisions_made:
        metadata["decisions_made"] = input_data.decisions_made
    if input_data.action_items:
        metadata["action_items"] = input_data.action_items
    if input_data.participants:
        metadata["participants"] = input_data.participants

    memory, extracted_entities, extracted_topics = await engine.save_memory(
        content=content,
        memory_type="conversation_summary",
        importance=input_data.importance.value,
        topics=input_data.topics_discussed,
        entities=input_data.participants,
        occurred_at=occurred_at,
        source="conversation",
        metadata=metadata,
    )

    return SaveMemoryOutput(
        memory_id=memory.id,
        extracted_entities=extracted_entities,
        extracted_topics=extracted_topics,
        message=f"Conversation summary saved with ID {memory.id}",
    )


async def bulk_import(input_data: BulkImportInput) -> BulkImportOutput:
    """
    Import multiple memories at once.

    Useful for importing transcripts, notes, or other bulk data.
    Each memory is processed individually with automatic metadata extraction.

    Args:
        input_data: List of memories to import

    Returns:
        Import results with success/failure counts
    """
    engine = get_query_engine()

    imported_count = 0
    failed_count = 0
    memory_ids = []
    errors = []

    for i, memory_input in enumerate(input_data.memories):
        try:
            # Parse occurred_at if provided
            occurred_at = None
            if memory_input.occurred_at:
                try:
                    occurred_at = datetime.fromisoformat(memory_input.occurred_at)
                except ValueError:
                    occurred_at = datetime.strptime(memory_input.occurred_at, "%Y-%m-%d")

            memory, _, _ = await engine.save_memory(
                content=memory_input.content,
                memory_type=memory_input.memory_type.value,
                importance=memory_input.importance.value,
                topics=memory_input.topics,
                entities=memory_input.entities,
                occurred_at=occurred_at,
                source=input_data.source,
                metadata=memory_input.metadata,
            )

            memory_ids.append(memory.id)
            imported_count += 1

        except Exception as e:
            logger.error(f"Failed to import memory {i}: {e}")
            failed_count += 1
            errors.append(f"Memory {i}: {str(e)}")

    return BulkImportOutput(
        imported_count=imported_count,
        failed_count=failed_count,
        memory_ids=memory_ids,
        errors=errors,
    )
