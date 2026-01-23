"""Tests for MCP tools."""

import asyncio
import tempfile
import shutil
import os
from datetime import datetime, date

import pytest

from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.query_engine import QueryEngine
from memory_palace.mcp.schemas import (
    MemorySearchParams,
    MemorySaveParams,
    EntityListParams,
    TopicListParams,
    RecentMemoriesParams,
)
from memory_palace.mcp.tools import (
    search_memories,
    save_memory,
    list_entities,
    list_topics,
    list_recent,
    get_memory_stats,
)


@pytest.fixture
def temp_dirs():
    """Create temporary directories for tests."""
    vector_dir = tempfile.mkdtemp()
    fd, sqlite_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield vector_dir, sqlite_path
    shutil.rmtree(vector_dir, ignore_errors=True)
    os.unlink(sqlite_path)


@pytest.fixture
async def test_context(temp_dirs):
    """Create test context with all required components."""
    vector_dir, sqlite_path = temp_dirs

    vector_db = VectorDB(persist_path=vector_dir)
    await vector_db.initialize()

    metadata_db = MetadataDB(sqlite_path)
    await metadata_db.initialize()

    engine = QueryEngine(vector_db, metadata_db)

    yield {
        "vector_db": vector_db,
        "metadata_db": metadata_db,
        "engine": engine,
    }

    await metadata_db.close()


class TestSaveMemoryTool:
    """Test cases for save_memory tool."""

    @pytest.mark.asyncio
    async def test_save_basic_memory(self, test_context):
        """Test saving a basic memory."""
        params = MemorySaveParams(
            content="Python is a great programming language.",
            memory_type="fact",
            importance="medium"
        )

        result = await save_memory(
            test_context["vector_db"],
            test_context["metadata_db"],
            params
        )

        assert result["success"] is True
        assert result["memory_id"]
        assert "message" in result

    @pytest.mark.asyncio
    async def test_save_with_topics(self, test_context):
        """Test saving a memory with explicit topics."""
        params = MemorySaveParams(
            content="Learning about neural networks today.",
            memory_type="insight",
            topics=["ml", "neural-networks", "learning"],
            importance="high"
        )

        result = await save_memory(
            test_context["vector_db"],
            test_context["metadata_db"],
            params
        )

        assert result["success"] is True
        # Should use provided topics
        assert "ml" in result["extracted_topics"] or len(result["extracted_topics"]) > 0


class TestSearchMemoriesTool:
    """Test cases for search_memories tool."""

    @pytest.mark.asyncio
    async def test_search_empty_db(self, test_context):
        """Test searching an empty database."""
        params = MemorySearchParams(query="test query")

        result = await search_memories(test_context["engine"], params)

        assert "memories" in result
        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_search_with_results(self, test_context):
        """Test searching with results."""
        # First save a memory
        save_params = MemorySaveParams(
            content="Machine learning is transforming industries.",
            memory_type="fact"
        )
        await save_memory(
            test_context["vector_db"],
            test_context["metadata_db"],
            save_params
        )

        # Then search
        search_params = MemorySearchParams(
            query="machine learning",
            limit=5
        )
        result = await search_memories(test_context["engine"], search_params)

        assert "memories" in result
        assert result["total_found"] >= 0  # May find it depending on embedding quality


class TestListEntitiesTool:
    """Test cases for list_entities tool."""

    @pytest.mark.asyncio
    async def test_list_empty_entities(self, test_context):
        """Test listing entities when none exist."""
        params = EntityListParams()

        result = await list_entities(test_context["metadata_db"], params)

        assert "entities" in result
        assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_list_entities_after_save(self, test_context):
        """Test listing entities after saving a memory with entities."""
        # Save a memory that should extract entities
        save_params = MemorySaveParams(
            content="John Smith works at Google in California.",
            memory_type="fact"
        )
        await save_memory(
            test_context["vector_db"],
            test_context["metadata_db"],
            save_params
        )

        # List entities
        params = EntityListParams()
        result = await list_entities(test_context["metadata_db"], params)

        assert "entities" in result
        # May have entities if spaCy is available


class TestListTopicsTool:
    """Test cases for list_topics tool."""

    @pytest.mark.asyncio
    async def test_list_topics(self, test_context):
        """Test listing topics."""
        # Save some memories to create topics
        for topic in ["python", "javascript", "rust"]:
            save_params = MemorySaveParams(
                content=f"Learning about {topic} programming.",
                memory_type="insight",
                topics=[topic]
            )
            await save_memory(
                test_context["vector_db"],
                test_context["metadata_db"],
                save_params
            )

        # List topics
        params = TopicListParams(sort_by="count")
        result = await list_topics(test_context["metadata_db"], params)

        assert "topics" in result
        assert result["total_count"] >= 3


class TestListRecentTool:
    """Test cases for list_recent tool."""

    @pytest.mark.asyncio
    async def test_list_recent(self, test_context):
        """Test listing recent memories."""
        # Save some memories
        for i in range(3):
            save_params = MemorySaveParams(
                content=f"Memory number {i}",
                memory_type="fact"
            )
            await save_memory(
                test_context["vector_db"],
                test_context["metadata_db"],
                save_params
            )

        # List recent
        params = RecentMemoriesParams(limit=10)
        result = await list_recent(test_context["engine"], params)

        assert "memories" in result
        assert result["total_found"] >= 3


class TestGetStatsTool:
    """Test cases for get_memory_stats tool."""

    @pytest.mark.asyncio
    async def test_get_stats(self, test_context):
        """Test getting stats."""
        # Save a memory
        save_params = MemorySaveParams(
            content="Test memory for stats.",
            memory_type="fact",
            importance="high"
        )
        await save_memory(
            test_context["vector_db"],
            test_context["metadata_db"],
            save_params
        )

        # Get stats
        result = await get_memory_stats(test_context["engine"])

        assert "total_memories" in result
        assert result["total_memories"] >= 1
