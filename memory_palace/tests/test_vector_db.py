"""
Tests for vector database.

These tests verify ChromaDB integration works correctly.
Uses a mock embedding function to avoid loading heavy ML models.
"""

import pytest
from datetime import datetime
import os

from memory_palace.core.models import Memory, MemoryType, Importance
from memory_palace.config import reset_settings


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances before each test."""
    reset_settings()
    from memory_palace.core.vector_db import reset_vector_db
    reset_vector_db()
    yield
    reset_settings()
    reset_vector_db()


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory."""
    os.environ["MEMORY_PALACE_DATA"] = str(tmp_path)
    return tmp_path


@pytest.fixture
def vector_db(temp_data_dir):
    """Get a fresh vector DB instance."""
    from memory_palace.core.vector_db import VectorDB
    return VectorDB()


class TestVectorDB:
    """Tests for VectorDB class."""

    @pytest.mark.asyncio
    async def test_add_memory(self, vector_db):
        """Test adding a memory to vector DB."""
        memory = Memory(
            content="Test memory content",
            memory_type=MemoryType.FACT,
            importance=Importance.MEDIUM,
        )

        memory_id = await vector_db.add_memory(memory)

        assert memory_id == memory.id
        count = await vector_db.get_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_search_memory(self, vector_db):
        """Test searching for a memory."""
        memory = Memory(
            content="Python is a programming language",
            memory_type=MemoryType.FACT,
        )
        await vector_db.add_memory(memory)

        results = await vector_db.search("programming language", limit=10)

        assert len(results) >= 1
        assert results[0]["id"] == memory.id

    @pytest.mark.asyncio
    async def test_search_with_filter(self, vector_db):
        """Test searching with metadata filter."""
        memory1 = Memory(
            content="This is a fact",
            memory_type=MemoryType.FACT,
        )
        memory2 = Memory(
            content="This is a preference",
            memory_type=MemoryType.PREFERENCE,
        )
        await vector_db.add_memory(memory1)
        await vector_db.add_memory(memory2)

        results = await vector_db.search(
            "content",
            where={"memory_type": "fact"},
        )

        assert len(results) == 1
        assert results[0]["id"] == memory1.id

    @pytest.mark.asyncio
    async def test_delete_memory(self, vector_db):
        """Test deleting a memory."""
        memory = Memory(content="To be deleted")
        await vector_db.add_memory(memory)

        assert await vector_db.get_count() == 1

        success = await vector_db.delete_memory(memory.id)

        assert success
        assert await vector_db.get_count() == 0

    @pytest.mark.asyncio
    async def test_update_memory(self, vector_db):
        """Test updating a memory."""
        memory = Memory(content="Original content")
        await vector_db.add_memory(memory)

        memory.content = "Updated content"
        await vector_db.update_memory(memory)

        results = await vector_db.search("Updated content")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_by_ids(self, vector_db):
        """Test getting memories by IDs."""
        memory1 = Memory(content="Memory 1")
        memory2 = Memory(content="Memory 2")
        await vector_db.add_memory(memory1)
        await vector_db.add_memory(memory2)

        results = await vector_db.get_by_ids([memory1.id, memory2.id])

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_clear(self, vector_db):
        """Test clearing the database."""
        await vector_db.add_memory(Memory(content="Test 1"))
        await vector_db.add_memory(Memory(content="Test 2"))

        assert await vector_db.get_count() == 2

        await vector_db.clear()

        assert await vector_db.get_count() == 0
