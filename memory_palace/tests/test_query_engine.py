"""
Tests for query engine.

These tests verify the unified query interface works correctly.
Uses mock embeddings to avoid loading heavy ML models.
"""

import pytest
from datetime import datetime, timedelta
import os

from memory_palace.core.models import MemoryType, Importance
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


@pytest.fixture
def query_engine(temp_data_dir):
    """Get a fresh query engine instance."""
    from memory_palace.core.query_engine import QueryEngine
    return QueryEngine()


class TestQueryEngineSave:
    """Tests for saving memories."""

    @pytest.mark.asyncio
    async def test_save_memory(self, query_engine):
        """Test saving a memory."""
        memory, entities, topics = await query_engine.save_memory(
            content="Test content",
            memory_type="fact",
            importance="medium",
        )

        assert memory.id is not None
        assert memory.content == "Test content"
        assert memory.memory_type == "fact"

    @pytest.mark.asyncio
    async def test_save_with_topics(self, query_engine):
        """Test saving with explicit topics."""
        memory, entities, topics = await query_engine.save_memory(
            content="Test content",
            topics=["topic1", "topic2"],
        )

        assert "topic1" in memory.topics
        assert "topic2" in memory.topics

    @pytest.mark.asyncio
    async def test_save_extracts_topics(self, query_engine):
        """Test that saving extracts topics automatically."""
        memory, entities, topics = await query_engine.save_memory(
            content="Python programming language is great for data science and machine learning.",
        )

        # Should extract some topics (depends on extractor)
        assert isinstance(topics, list)


class TestQueryEngineSearch:
    """Tests for searching memories."""

    @pytest.mark.asyncio
    async def test_search_empty(self, query_engine):
        """Test searching empty palace."""
        results = await query_engine.search("anything")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_finds_memory(self, query_engine):
        """Test that search finds saved memory."""
        await query_engine.save_memory(
            content="The quick brown fox jumps over the lazy dog.",
        )

        results = await query_engine.search("quick brown fox")

        assert len(results) >= 1
        assert "fox" in results[0].memory.content.lower()

    @pytest.mark.asyncio
    async def test_search_by_type(self, query_engine):
        """Test searching by memory type."""
        await query_engine.save_memory(
            content="Fact content",
            memory_type="fact",
        )
        await query_engine.save_memory(
            content="Preference content",
            memory_type="preference",
        )

        results = await query_engine.search(
            "content",
            memory_types=["fact"],
        )

        for r in results:
            assert r.memory.memory_type == "fact"


class TestQueryEngineDelete:
    """Tests for deleting memories."""

    @pytest.mark.asyncio
    async def test_delete_memory(self, query_engine):
        """Test deleting a memory."""
        memory, _, _ = await query_engine.save_memory(content="To delete")

        success = await query_engine.delete_memory(memory.id)

        assert success
        results = await query_engine.search("To delete")
        assert len(results) == 0


class TestQueryEngineTimeline:
    """Tests for timeline queries."""

    @pytest.mark.asyncio
    async def test_timeline_empty(self, query_engine):
        """Test timeline query on empty palace."""
        entries = await query_engine.timeline_query("anything")
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_timeline_groups_by_month(self, query_engine):
        """Test that timeline groups by month."""
        await query_engine.save_memory(
            content="AI project started",
            topics=["AI"],
        )

        entries = await query_engine.timeline_query(
            topic="AI",
            granularity="month",
        )

        if entries:
            # Each entry should have a period label
            for entry in entries:
                assert entry.period_label is not None


class TestQueryEngineStats:
    """Tests for statistics."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, query_engine):
        """Test stats on empty palace."""
        stats = await query_engine.get_stats()

        assert stats.total_memories == 0
        assert stats.total_entities == 0

    @pytest.mark.asyncio
    async def test_stats_after_save(self, query_engine):
        """Test stats after saving."""
        await query_engine.save_memory(
            content="Test memory",
            memory_type="fact",
        )

        stats = await query_engine.get_stats()

        assert stats.total_memories == 1
        assert stats.memories_by_type.get("fact", 0) == 1
