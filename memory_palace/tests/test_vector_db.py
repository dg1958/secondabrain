"""Tests for vector database."""

import asyncio
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from memory_palace.core.vector_db import VectorDB


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
async def vector_db(temp_dir):
    """Create a vector database instance for testing."""
    db = VectorDB(persist_path=temp_dir)
    await db.initialize()
    yield db


class TestVectorDB:
    """Test cases for VectorDB."""

    @pytest.mark.asyncio
    async def test_initialize(self, temp_dir):
        """Test database initialization."""
        db = VectorDB(persist_path=temp_dir)
        await db.initialize()
        assert db._collection is not None

    @pytest.mark.asyncio
    async def test_add_memory(self, vector_db):
        """Test adding a memory."""
        await vector_db.add_memory(
            id="test-1",
            content="This is a test memory about Python programming.",
            metadata={
                "memory_type": "fact",
                "timestamp": datetime.utcnow().isoformat(),
                "topics": ["python", "programming"],
            }
        )

        # Verify it was added
        result = await vector_db.get_by_id("test-1")
        assert result is not None
        assert result["content"] == "This is a test memory about Python programming."

    @pytest.mark.asyncio
    async def test_search(self, vector_db):
        """Test searching memories."""
        # Add some test memories
        await vector_db.add_memory(
            id="test-1",
            content="Python is a programming language.",
            metadata={"memory_type": "fact", "timestamp": datetime.utcnow().isoformat()}
        )
        await vector_db.add_memory(
            id="test-2",
            content="JavaScript is used for web development.",
            metadata={"memory_type": "fact", "timestamp": datetime.utcnow().isoformat()}
        )
        await vector_db.add_memory(
            id="test-3",
            content="Machine learning uses Python extensively.",
            metadata={"memory_type": "fact", "timestamp": datetime.utcnow().isoformat()}
        )

        # Search for Python-related memories
        results = await vector_db.search("Python programming", limit=2)

        assert len(results) <= 2
        # The most relevant results should mention Python
        if results:
            assert any("Python" in r["content"] for r in results)

    @pytest.mark.asyncio
    async def test_update(self, vector_db):
        """Test updating a memory."""
        # Add a memory
        await vector_db.add_memory(
            id="test-1",
            content="Original content",
            metadata={"memory_type": "fact"}
        )

        # Update it
        await vector_db.update(
            id="test-1",
            content="Updated content",
            metadata={"memory_type": "insight"}
        )

        # Verify update
        result = await vector_db.get_by_id("test-1")
        assert result["content"] == "Updated content"

    @pytest.mark.asyncio
    async def test_delete(self, vector_db):
        """Test deleting a memory."""
        # Add a memory
        await vector_db.add_memory(
            id="test-1",
            content="Memory to delete",
            metadata={}
        )

        # Delete it
        await vector_db.delete("test-1")

        # Verify deletion
        result = await vector_db.get_by_id("test-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_count(self, vector_db):
        """Test counting memories."""
        initial_count = await vector_db.count()

        # Add memories
        await vector_db.add_memory(id="test-1", content="Memory 1", metadata={})
        await vector_db.add_memory(id="test-2", content="Memory 2", metadata={})

        new_count = await vector_db.count()
        assert new_count == initial_count + 2

    @pytest.mark.asyncio
    async def test_get_all_ids(self, vector_db):
        """Test getting all IDs."""
        await vector_db.add_memory(id="id-1", content="Memory 1", metadata={})
        await vector_db.add_memory(id="id-2", content="Memory 2", metadata={})

        ids = await vector_db.get_all_ids()
        assert "id-1" in ids
        assert "id-2" in ids
