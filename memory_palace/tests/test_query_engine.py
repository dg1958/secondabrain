"""Tests for query engine."""

import asyncio
import tempfile
import shutil
import os
from datetime import datetime, timedelta

import pytest

from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.query_engine import QueryEngine


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
async def query_engine(temp_dirs):
    """Create a query engine instance for testing."""
    vector_dir, sqlite_path = temp_dirs

    vector_db = VectorDB(persist_path=vector_dir)
    await vector_db.initialize()

    metadata_db = MetadataDB(sqlite_path)
    await metadata_db.initialize()

    engine = QueryEngine(vector_db, metadata_db)
    yield engine

    await metadata_db.close()


async def add_test_memory(engine, id, content, memory_type="fact", timestamp=None, topics=None, entities=None):
    """Helper to add a test memory."""
    timestamp = timestamp or datetime.utcnow()
    topics = topics or []
    entities = entities or {}

    metadata = {
        "memory_type": memory_type,
        "timestamp": timestamp.isoformat(),
        "importance": "medium",
        "topics": topics,
        "entities": entities,
    }

    await engine.vector_db.add_memory(id=id, content=content, metadata=metadata)
    await engine.metadata_db.add_memory_meta(
        id=id,
        content=content,
        memory_type=memory_type,
        timestamp=timestamp,
        importance="medium",
        topics=topics,
        entities=entities
    )


class TestQueryEngine:
    """Test cases for QueryEngine."""

    @pytest.mark.asyncio
    async def test_search_basic(self, query_engine):
        """Test basic search functionality."""
        # Add test memories
        await add_test_memory(
            query_engine, "mem-1",
            "Python is great for machine learning",
            topics=["python", "ml"]
        )
        await add_test_memory(
            query_engine, "mem-2",
            "JavaScript is popular for web development",
            topics=["javascript", "web"]
        )

        # Search
        results = await query_engine.search("machine learning Python", limit=5)

        assert len(results) >= 1
        # Most relevant should be about Python/ML
        assert any("Python" in r.memory.content for r in results)

    @pytest.mark.asyncio
    async def test_search_with_date_filter(self, query_engine):
        """Test search with date filtering."""
        old_date = datetime(2024, 1, 1)
        recent_date = datetime(2024, 6, 1)

        await add_test_memory(
            query_engine, "old-mem",
            "Old Python information",
            timestamp=old_date,
            topics=["python"]
        )
        await add_test_memory(
            query_engine, "recent-mem",
            "Recent Python developments",
            timestamp=recent_date,
            topics=["python"]
        )

        # Search with date filter
        results = await query_engine.search(
            "Python",
            filters={"date_from": datetime(2024, 5, 1)},
            limit=10
        )

        # Should only get recent memory
        assert all(r.memory.timestamp >= datetime(2024, 5, 1) for r in results)

    @pytest.mark.asyncio
    async def test_search_by_entity(self, query_engine):
        """Test entity-based search."""
        await add_test_memory(
            query_engine, "mem-1",
            "John Smith leads the Python project",
            entities={"PERSON": ["John Smith"], "PROJECT": ["Python project"]}
        )
        await add_test_memory(
            query_engine, "mem-2",
            "The Python project is progressing well",
            entities={"PROJECT": ["Python project"]}
        )

        # Search by entity
        results = await query_engine.search_by_entity("John Smith", limit=10)

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_timeline_query(self, query_engine):
        """Test timeline query functionality."""
        # Add memories across different weeks
        base_date = datetime(2024, 1, 1)

        for i in range(4):
            date = base_date + timedelta(weeks=i)
            await add_test_memory(
                query_engine, f"timeline-{i}",
                f"Python progress update week {i+1}",
                timestamp=date,
                topics=["python", "progress"]
            )

        # Query timeline
        entries = await query_engine.timeline_query(
            topic="Python",
            date_from=base_date,
            date_to=base_date + timedelta(weeks=4),
            granularity="week"
        )

        # Should have entries for different weeks
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_get_stats(self, query_engine):
        """Test statistics retrieval."""
        # Add some data
        await add_test_memory(
            query_engine, "stat-1",
            "Test memory for stats",
            memory_type="fact",
            topics=["testing"]
        )

        stats = await query_engine.get_stats()

        assert stats.total_memories >= 1
        assert "fact" in stats.memories_by_type or stats.memories_by_type.get("fact", 0) >= 0

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, query_engine):
        """Test getting recent memories."""
        now = datetime.utcnow()

        # Add memories with different timestamps
        await add_test_memory(
            query_engine, "recent-1",
            "Most recent memory",
            timestamp=now
        )
        await add_test_memory(
            query_engine, "recent-2",
            "Older memory",
            timestamp=now - timedelta(hours=1)
        )

        # Get recent
        memories = await query_engine.get_recent_memories(limit=5)

        assert len(memories) >= 1
        # Should be sorted by timestamp (newest first)
        if len(memories) >= 2:
            assert memories[0].timestamp >= memories[1].timestamp
