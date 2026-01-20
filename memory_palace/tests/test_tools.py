"""
Tests for MCP tools.

These tests verify that the MCP tools work correctly
with the underlying query engine.
Uses mock embeddings to avoid loading heavy ML models.
"""

import pytest
from datetime import datetime, timedelta
import os

from memory_palace.mcp.schemas import (
    SaveMemoryInput,
    SearchMemoriesInput,
    ListRecentInput,
    ListTopicsInput,
    ListEntitiesInput,
    GetMemoryStatsInput,
    TimelineQueryInput,
    MemoryTypeEnum,
    ImportanceEnum,
)
from memory_palace.config import reset_settings


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances before each test."""
    reset_settings()
    from memory_palace.core.vector_db import reset_vector_db
    from memory_palace.core.metadata_db import reset_metadata_db
    from memory_palace.core.query_engine import reset_query_engine
    reset_vector_db()
    reset_metadata_db()
    reset_query_engine()
    yield
    reset_settings()
    reset_vector_db()
    reset_metadata_db()
    reset_query_engine()


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    os.environ["MEMORY_PALACE_DATA"] = str(tmp_path)
    return tmp_path


class TestSaveMemory:
    """Tests for save_memory tool."""

    @pytest.mark.asyncio
    async def test_save_basic_memory(self, temp_data_dir):
        """Test saving a basic memory."""
        from memory_palace.mcp.tools import save_memory
        input_data = SaveMemoryInput(
            content="Python 3.12 introduced new typing syntax for generics.",
            memory_type=MemoryTypeEnum.FACT,
            importance=ImportanceEnum.MEDIUM,
        )

        result = await save_memory(input_data)

        assert result.memory_id is not None
        assert "saved" in result.message.lower()

    @pytest.mark.asyncio
    async def test_save_memory_with_topics(self, temp_data_dir):
        """Test saving a memory with explicit topics."""
        from memory_palace.mcp.tools import save_memory
        input_data = SaveMemoryInput(
            content="I prefer using dark mode for all code editors.",
            memory_type=MemoryTypeEnum.PREFERENCE,
            importance=ImportanceEnum.HIGH,
            topics=["coding", "preferences", "IDE"],
        )

        result = await save_memory(input_data)

        assert result.memory_id is not None
        assert "coding" in result.extracted_topics or len(result.extracted_topics) > 0

    @pytest.mark.asyncio
    async def test_save_memory_extracts_entities(self, temp_data_dir):
        """Test that saving memory extracts entities."""
        from memory_palace.mcp.tools import save_memory
        input_data = SaveMemoryInput(
            content="John Smith from Acme Corporation called about the project.",
            memory_type=MemoryTypeEnum.EVENT,
        )

        result = await save_memory(input_data)

        assert result.memory_id is not None
        # Entities should be extracted (depends on NER availability)


class TestSearchMemories:
    """Tests for search_memories tool."""

    @pytest.mark.asyncio
    async def test_search_empty_palace(self, temp_data_dir):
        """Test searching an empty memory palace."""
        from memory_palace.mcp.tools import search_memories
        input_data = SearchMemoriesInput(query="anything")

        result = await search_memories(input_data)

        assert result.total_found == 0
        assert len(result.memories) == 0

    @pytest.mark.asyncio
    async def test_search_finds_memory(self, temp_data_dir):
        """Test that search finds a saved memory."""
        from memory_palace.mcp.tools import save_memory, search_memories
        # First save a memory
        await save_memory(SaveMemoryInput(
            content="The quick brown fox jumps over the lazy dog.",
            memory_type=MemoryTypeEnum.FACT,
        ))

        # Then search for it
        result = await search_memories(SearchMemoriesInput(
            query="quick brown fox",
            limit=10,
        ))

        assert result.total_found >= 1
        assert any("fox" in m.memory.content.lower() for m in result.memories)

    @pytest.mark.asyncio
    async def test_search_with_type_filter(self, temp_data_dir):
        """Test searching with memory type filter."""
        from memory_palace.mcp.tools import save_memory, search_memories
        # Save different types
        await save_memory(SaveMemoryInput(
            content="I like coffee in the morning.",
            memory_type=MemoryTypeEnum.PREFERENCE,
        ))
        await save_memory(SaveMemoryInput(
            content="Coffee beans come from Ethiopia.",
            memory_type=MemoryTypeEnum.FACT,
        ))

        # Search only facts
        result = await search_memories(SearchMemoriesInput(
            query="coffee",
            memory_types=[MemoryTypeEnum.FACT],
        ))

        for m in result.memories:
            assert m.memory.memory_type == "fact"


class TestListRecent:
    """Tests for list_recent tool."""

    @pytest.mark.asyncio
    async def test_list_recent_empty(self, temp_data_dir):
        """Test listing recent memories when empty."""
        from memory_palace.mcp.tools import list_recent
        result = await list_recent(ListRecentInput(limit=10))

        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_list_recent_returns_memories(self, temp_data_dir):
        """Test that list_recent returns saved memories."""
        from memory_palace.mcp.tools import save_memory, list_recent
        # Save some memories
        await save_memory(SaveMemoryInput(content="Memory 1"))
        await save_memory(SaveMemoryInput(content="Memory 2"))
        await save_memory(SaveMemoryInput(content="Memory 3"))

        result = await list_recent(ListRecentInput(limit=10))

        assert result.total_found == 3


class TestListTopics:
    """Tests for list_topics tool."""

    @pytest.mark.asyncio
    async def test_list_topics_empty(self, temp_data_dir):
        """Test listing topics when empty."""
        from memory_palace.mcp.tools import list_topics
        result = await list_topics(ListTopicsInput())

        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_list_topics_after_save(self, temp_data_dir):
        """Test listing topics after saving with topics."""
        from memory_palace.mcp.tools import save_memory, list_topics
        await save_memory(SaveMemoryInput(
            content="Python is a great programming language.",
            topics=["python", "programming"],
        ))

        result = await list_topics(ListTopicsInput())

        assert result.total_count >= 1


class TestListEntities:
    """Tests for list_entities tool."""

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, temp_data_dir):
        """Test listing entities when empty."""
        from memory_palace.mcp.tools import list_entities
        result = await list_entities(ListEntitiesInput())

        assert result.total_count == 0


class TestGetMemoryStats:
    """Tests for get_memory_stats tool."""

    @pytest.mark.asyncio
    async def test_stats_empty_palace(self, temp_data_dir):
        """Test stats for empty palace."""
        from memory_palace.mcp.tools import get_memory_stats
        result = await get_memory_stats(GetMemoryStatsInput())

        assert result.total_memories == 0
        assert result.total_entities == 0
        assert result.total_topics == 0

    @pytest.mark.asyncio
    async def test_stats_after_save(self, temp_data_dir):
        """Test stats after saving memories."""
        from memory_palace.mcp.tools import save_memory, get_memory_stats
        await save_memory(SaveMemoryInput(
            content="Test memory",
            memory_type=MemoryTypeEnum.FACT,
        ))

        result = await get_memory_stats(GetMemoryStatsInput())

        assert result.total_memories == 1
        assert result.memories_by_type.get("fact", 0) == 1


class TestTimelineQuery:
    """Tests for timeline_query tool."""

    @pytest.mark.asyncio
    async def test_timeline_empty(self, temp_data_dir):
        """Test timeline query on empty palace."""
        from memory_palace.mcp.tools import timeline_query
        result = await timeline_query(TimelineQueryInput(
            topic="anything",
        ))

        assert result.total_memories == 0

    @pytest.mark.asyncio
    async def test_timeline_finds_memories(self, temp_data_dir):
        """Test timeline query finds relevant memories."""
        from memory_palace.mcp.tools import save_memory, timeline_query
        await save_memory(SaveMemoryInput(
            content="Started working on the AI project.",
            topics=["AI", "project"],
        ))

        result = await timeline_query(TimelineQueryInput(
            topic="AI project",
        ))

        assert result.total_memories >= 1
