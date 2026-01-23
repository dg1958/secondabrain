"""Tests for metadata database."""

import asyncio
import tempfile
import os
from datetime import datetime

import pytest

from memory_palace.core.metadata_db import MetadataDB


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
async def metadata_db(temp_db_path):
    """Create a metadata database instance for testing."""
    db = MetadataDB(temp_db_path)
    await db.initialize()
    yield db
    await db.close()


class TestMetadataDB:
    """Test cases for MetadataDB."""

    @pytest.mark.asyncio
    async def test_initialize(self, temp_db_path):
        """Test database initialization."""
        db = MetadataDB(temp_db_path)
        await db.initialize()
        assert db._connection is not None
        await db.close()

    @pytest.mark.asyncio
    async def test_add_memory_meta(self, metadata_db):
        """Test adding memory metadata."""
        await metadata_db.add_memory_meta(
            id="test-1",
            content="Test memory content",
            memory_type="fact",
            timestamp=datetime.utcnow(),
            importance="high",
            topics=["testing", "python"],
            entities={"CONCEPT": ["Python"]},
        )

        # Verify it was added
        result = await metadata_db.get_memory_meta("test-1")
        assert result is not None
        assert result["memory_type"] == "fact"
        assert result["importance"] == "high"
        assert "testing" in result["topics"]

    @pytest.mark.asyncio
    async def test_upsert_entity(self, metadata_db):
        """Test entity creation and update."""
        timestamp = datetime.utcnow()

        # Create entity
        await metadata_db.upsert_entity(
            name="John Smith",
            entity_type="PERSON",
            timestamp=timestamp,
            related_topics=["project"]
        )

        # Verify creation
        entity = await metadata_db.get_entity("John Smith", "PERSON")
        assert entity is not None
        assert entity["mention_count"] == 1

        # Update (mention again)
        await metadata_db.upsert_entity(
            name="John Smith",
            entity_type="PERSON",
            timestamp=timestamp,
            related_topics=["meeting"]
        )

        # Verify update
        entity = await metadata_db.get_entity("John Smith", "PERSON")
        assert entity["mention_count"] == 2
        assert "project" in entity["related_topics"]
        assert "meeting" in entity["related_topics"]

    @pytest.mark.asyncio
    async def test_upsert_topic(self, metadata_db):
        """Test topic creation and update."""
        timestamp = datetime.utcnow()

        # Create topic
        await metadata_db.upsert_topic("python", timestamp)

        # Verify creation
        topics = await metadata_db.get_topics(limit=10)
        python_topic = next((t for t in topics if t["name"] == "python"), None)
        assert python_topic is not None
        assert python_topic["count"] == 1

        # Update (mention again)
        await metadata_db.upsert_topic("python", timestamp)

        # Verify update
        topics = await metadata_db.get_topics(limit=10)
        python_topic = next((t for t in topics if t["name"] == "python"), None)
        assert python_topic["count"] == 2

    @pytest.mark.asyncio
    async def test_get_entities_by_type(self, metadata_db):
        """Test filtering entities by type."""
        timestamp = datetime.utcnow()

        await metadata_db.upsert_entity("John", "PERSON", timestamp)
        await metadata_db.upsert_entity("Acme Corp", "ORG", timestamp)
        await metadata_db.upsert_entity("Jane", "PERSON", timestamp)

        # Get only PERSON entities
        people = await metadata_db.get_entities(entity_type="PERSON")
        assert len(people) == 2
        assert all(e["entity_type"] == "PERSON" for e in people)

    @pytest.mark.asyncio
    async def test_get_memories_by_date_range(self, metadata_db):
        """Test date range filtering."""
        # Add memories with different timestamps
        await metadata_db.add_memory_meta(
            id="old",
            content="Old memory",
            memory_type="fact",
            timestamp=datetime(2024, 1, 1),
            importance="medium",
            topics=[],
            entities={}
        )
        await metadata_db.add_memory_meta(
            id="recent",
            content="Recent memory",
            memory_type="fact",
            timestamp=datetime(2024, 6, 15),
            importance="medium",
            topics=[],
            entities={}
        )

        # Query for June memories only
        results = await metadata_db.get_memories_by_date_range(
            date_from=datetime(2024, 6, 1),
            date_to=datetime(2024, 6, 30)
        )

        assert len(results) == 1
        assert results[0]["id"] == "recent"

    @pytest.mark.asyncio
    async def test_get_stats(self, metadata_db):
        """Test statistics retrieval."""
        timestamp = datetime.utcnow()

        # Add some data
        await metadata_db.add_memory_meta(
            id="test-1",
            content="Memory 1",
            memory_type="fact",
            timestamp=timestamp,
            importance="high",
            topics=["testing"],
            entities={}
        )
        await metadata_db.upsert_entity("Test Entity", "CONCEPT", timestamp)
        await metadata_db.upsert_topic("testing", timestamp)

        # Get stats
        stats = await metadata_db.get_stats()

        assert stats["total_memories"] >= 1
        assert stats["total_entities"] >= 1
        assert stats["total_topics"] >= 1

    @pytest.mark.asyncio
    async def test_search_entities(self, metadata_db):
        """Test entity search."""
        timestamp = datetime.utcnow()

        await metadata_db.upsert_entity("John Smith", "PERSON", timestamp)
        await metadata_db.upsert_entity("Jane Doe", "PERSON", timestamp)
        await metadata_db.upsert_entity("Smithsonian", "ORG", timestamp)

        # Search for "Smith"
        results = await metadata_db.search_entities("Smith")

        assert len(results) >= 1
        assert any("Smith" in e["name"] for e in results)
