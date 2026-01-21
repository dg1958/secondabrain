"""
SQLite metadata database for Memory Palace.

Stores memory metadata, entities, topics, and relationships
that complement the vector database.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import aiosqlite

from ..config import get_settings
from .models import Memory, Entity, Topic, EntityType, MemoryType, Importance

logger = logging.getLogger(__name__)


class MetadataDB:
    """
    SQLite database for memory metadata and entity tracking.

    Complements ChromaDB by storing structured metadata that
    doesn't fit well in vector storage.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metadata database.

        Args:
            db_path: Path to SQLite database file
        """
        settings = get_settings()
        self.db_path = db_path or settings.storage.metadata_db_path

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Initialize database schema if needed."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Memories table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    occurred_at TEXT,
                    sentiment_score REAL,
                    source TEXT,
                    source_id TEXT,
                    summary TEXT,
                    metadata TEXT
                )
            """)

            # Entities table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    aliases TEXT,
                    description TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    metadata TEXT,
                    UNIQUE(name, entity_type)
                )
            """)

            # Topics table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Memory-Entity relationship table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_entities (
                    memory_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    PRIMARY KEY (memory_id, entity_id),
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
            """)

            # Memory-Topic relationship table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory_topics (
                    memory_id TEXT NOT NULL,
                    topic_name TEXT NOT NULL,
                    PRIMARY KEY (memory_id, topic_name),
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)

            # Create indices for common queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_type
                ON memories(memory_type)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_importance
                ON memories(importance)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_created
                ON memories(created_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_occurred
                ON memories(occurred_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_type
                ON entities(entity_type)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_name
                ON entities(name)
            """)

            await db.commit()

        self._initialized = True
        logger.info(f"Metadata database initialized at {self.db_path}")

    # ============ MEMORY OPERATIONS ============

    async def save_memory(self, memory: Memory) -> str:
        """
        Save a memory to the database.

        Args:
            memory: The memory to save

        Returns:
            The memory ID
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO memories
                (id, content, memory_type, importance, created_at, updated_at,
                 occurred_at, sentiment_score, source, source_id, summary, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.content,
                memory.memory_type,
                memory.importance,
                memory.created_at.isoformat(),
                memory.updated_at.isoformat(),
                memory.occurred_at.isoformat() if memory.occurred_at else None,
                memory.sentiment_score,
                memory.source,
                memory.source_id,
                memory.summary,
                json.dumps(memory.metadata) if memory.metadata else None,
            ))

            # Save topic relationships
            if memory.topics:
                for topic_name in memory.topics:
                    await self._ensure_topic_exists(db, topic_name)
                    await db.execute("""
                        INSERT OR IGNORE INTO memory_topics (memory_id, topic_name)
                        VALUES (?, ?)
                    """, (memory.id, topic_name))

            # Save entity relationships
            if memory.entities:
                for entity_id in memory.entities:
                    await db.execute("""
                        INSERT OR IGNORE INTO memory_entities (memory_id, entity_id)
                        VALUES (?, ?)
                    """, (memory.id, entity_id))

            await db.commit()

        logger.debug(f"Saved memory {memory.id} to metadata DB")
        return memory.id

    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                memory = self._row_to_memory(dict(row))

            # Get topics
            async with db.execute(
                "SELECT topic_name FROM memory_topics WHERE memory_id = ?",
                (memory_id,)
            ) as cursor:
                topics = [row[0] async for row in cursor]
                memory.topics = topics

            # Get entity IDs
            async with db.execute(
                "SELECT entity_id FROM memory_entities WHERE memory_id = ?",
                (memory_id,)
            ) as cursor:
                entities = [row[0] async for row in cursor]
                memory.entities = entities

        return memory

    async def update_memory(self, memory: Memory) -> None:
        """Update an existing memory."""
        memory.updated_at = datetime.utcnow()
        await self.save_memory(memory)

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            # Delete relationships first (CASCADE should handle this but be explicit)
            await db.execute(
                "DELETE FROM memory_topics WHERE memory_id = ?", (memory_id,)
            )
            await db.execute(
                "DELETE FROM memory_entities WHERE memory_id = ?", (memory_id,)
            )
            # Delete memory
            cursor = await db.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_memories_by_ids(self, memory_ids: list[str]) -> list[Memory]:
        """Get multiple memories by their IDs."""
        await self._ensure_initialized()

        if not memory_ids:
            return []

        memories = []
        for memory_id in memory_ids:
            memory = await self.get_memory(memory_id)
            if memory:
                memories.append(memory)

        return memories

    async def search_memories(
        self,
        memory_types: Optional[list[str]] = None,
        min_importance: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        topics: Optional[list[str]] = None,
        entity_ids: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        """
        Search memories with metadata filters.

        Returns memories matching the criteria, sorted by date descending.
        """
        await self._ensure_initialized()

        conditions = []
        params = []

        if memory_types:
            placeholders = ",".join("?" * len(memory_types))
            conditions.append(f"m.memory_type IN ({placeholders})")
            params.extend(memory_types)

        if min_importance:
            importance_order = ["low", "medium", "high", "critical"]
            min_idx = importance_order.index(min_importance)
            valid_importance = importance_order[min_idx:]
            placeholders = ",".join("?" * len(valid_importance))
            conditions.append(f"m.importance IN ({placeholders})")
            params.extend(valid_importance)

        if date_from:
            conditions.append("m.created_at >= ?")
            params.append(date_from.isoformat())

        if date_to:
            conditions.append("m.created_at <= ?")
            params.append(date_to.isoformat())

        joins = []
        if topics:
            joins.append("JOIN memory_topics mt ON m.id = mt.memory_id")
            placeholders = ",".join("?" * len(topics))
            conditions.append(f"mt.topic_name IN ({placeholders})")
            params.extend(topics)

        if entity_ids:
            joins.append("JOIN memory_entities me ON m.id = me.memory_id")
            placeholders = ",".join("?" * len(entity_ids))
            conditions.append(f"me.entity_id IN ({placeholders})")
            params.extend(entity_ids)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        join_clause = " ".join(joins)

        query = f"""
            SELECT DISTINCT m.* FROM memories m
            {join_clause}
            WHERE {where_clause}
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        memories = []
        for row in rows:
            memory = self._row_to_memory(dict(row))
            # We'd need to fetch topics/entities separately for full data
            memories.append(memory)

        return memories

    async def get_memories_by_date_range(
        self,
        date_from: datetime,
        date_to: datetime,
        memory_types: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[Memory]:
        """Get memories within a date range."""
        return await self.search_memories(
            date_from=date_from,
            date_to=date_to,
            memory_types=memory_types,
            limit=limit,
        )

    async def get_recent_memories(
        self,
        limit: int = 20,
        memory_types: Optional[list[str]] = None,
    ) -> list[Memory]:
        """Get most recent memories."""
        return await self.search_memories(
            memory_types=memory_types,
            limit=limit,
        )

    # ============ ENTITY OPERATIONS ============

    async def save_entity(self, entity: Entity) -> str:
        """Save or update an entity."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO entities
                (id, name, entity_type, aliases, description, first_seen, last_seen, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.id,
                entity.name,
                entity.entity_type,
                json.dumps(entity.aliases) if entity.aliases else None,
                entity.description,
                entity.first_seen.isoformat(),
                entity.last_seen.isoformat(),
                json.dumps(entity.metadata) if entity.metadata else None,
            ))
            await db.commit()

        return entity.id

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_entity(dict(row))

    async def get_entity_by_name(
        self,
        name: str,
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """Get an entity by name (and optionally type)."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if entity_type:
                query = "SELECT * FROM entities WHERE name = ? AND entity_type = ?"
                params = (name, entity_type)
            else:
                query = "SELECT * FROM entities WHERE name = ?"
                params = (name,)

            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return self._row_to_entity(dict(row))

    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """Find an entity by name (case-insensitive, checks aliases)."""
        await self._ensure_initialized()

        name_lower = name.lower()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # First try exact name match
            async with db.execute(
                "SELECT * FROM entities WHERE LOWER(name) = ?", (name_lower,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_entity(dict(row))

            # Then search aliases
            async with db.execute("SELECT * FROM entities WHERE aliases IS NOT NULL") as cursor:
                async for row in cursor:
                    entity = self._row_to_entity(dict(row))
                    if any(alias.lower() == name_lower for alias in entity.aliases):
                        return entity

        return None

    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "memory_count",
    ) -> list[Entity]:
        """List entities with optional filtering."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if entity_type:
                query = """
                    SELECT e.*, COUNT(me.memory_id) as memory_count
                    FROM entities e
                    LEFT JOIN memory_entities me ON e.id = me.entity_id
                    WHERE e.entity_type = ?
                    GROUP BY e.id
                """
                params = [entity_type]
            else:
                query = """
                    SELECT e.*, COUNT(me.memory_id) as memory_count
                    FROM entities e
                    LEFT JOIN memory_entities me ON e.id = me.entity_id
                    GROUP BY e.id
                """
                params = []

            # Add sorting
            if sort_by == "memory_count":
                query += " ORDER BY memory_count DESC"
            elif sort_by == "name":
                query += " ORDER BY e.name ASC"
            elif sort_by == "last_seen":
                query += " ORDER BY e.last_seen DESC"

            query += " LIMIT ?"
            params.append(limit)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        entities = []
        for row in rows:
            row_dict = dict(row)
            memory_count = row_dict.pop("memory_count", 0)
            entity = self._row_to_entity(row_dict)
            entity.memory_count = memory_count
            entities.append(entity)

        return entities

    async def get_entity_memories(
        self,
        entity_id: str,
        limit: int = 20
    ) -> list[Memory]:
        """Get memories mentioning an entity."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT m.* FROM memories m
                JOIN memory_entities me ON m.id = me.memory_id
                WHERE me.entity_id = ?
                ORDER BY m.created_at DESC
                LIMIT ?
            """

            async with db.execute(query, (entity_id, limit)) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_memory(dict(row)) for row in rows]

    async def update_entity_seen(self, entity_id: str) -> None:
        """Update entity's last_seen timestamp."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE entities SET last_seen = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), entity_id)
            )
            await db.commit()

    # ============ TOPIC OPERATIONS ============

    async def _ensure_topic_exists(
        self,
        db: aiosqlite.Connection,
        topic_name: str
    ) -> None:
        """Ensure a topic exists in the database."""
        now = datetime.utcnow().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO topics (id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (topic_name, topic_name, now, now))

    async def list_topics(
        self,
        limit: int = 50,
        sort_by: str = "memory_count",
        min_count: int = 1,
    ) -> list[dict[str, Any]]:
        """List topics with memory counts."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT t.name, t.description, COUNT(mt.memory_id) as memory_count
                FROM topics t
                LEFT JOIN memory_topics mt ON t.name = mt.topic_name
                GROUP BY t.name
                HAVING COUNT(mt.memory_id) >= ?
            """

            if sort_by == "memory_count":
                query += " ORDER BY memory_count DESC"
            elif sort_by == "name":
                query += " ORDER BY t.name ASC"
            elif sort_by == "recent":
                query += " ORDER BY t.updated_at DESC"

            query += " LIMIT ?"

            async with db.execute(query, (min_count, limit)) as cursor:
                rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_memories_by_topic(
        self,
        topic_name: str,
        limit: int = 50
    ) -> list[Memory]:
        """Get memories with a specific topic."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT m.* FROM memories m
                JOIN memory_topics mt ON m.id = mt.memory_id
                WHERE mt.topic_name = ?
                ORDER BY m.created_at DESC
                LIMIT ?
            """

            async with db.execute(query, (topic_name, limit)) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_memory(dict(row)) for row in rows]

    # ============ STATISTICS ============

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            # Total memories
            async with db.execute("SELECT COUNT(*) FROM memories") as cursor:
                total_memories = (await cursor.fetchone())[0]

            # Memories by type
            async with db.execute("""
                SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type
            """) as cursor:
                memories_by_type = {row[0]: row[1] async for row in cursor}

            # Memories by importance
            async with db.execute("""
                SELECT importance, COUNT(*) FROM memories GROUP BY importance
            """) as cursor:
                memories_by_importance = {row[0]: row[1] async for row in cursor}

            # Total entities
            async with db.execute("SELECT COUNT(*) FROM entities") as cursor:
                total_entities = (await cursor.fetchone())[0]

            # Entities by type
            async with db.execute("""
                SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type
            """) as cursor:
                entities_by_type = {row[0]: row[1] async for row in cursor}

            # Total topics
            async with db.execute("""
                SELECT COUNT(DISTINCT topic_name) FROM memory_topics
            """) as cursor:
                total_topics = (await cursor.fetchone())[0]

            # Date range
            async with db.execute("""
                SELECT MIN(created_at), MAX(created_at) FROM memories
            """) as cursor:
                row = await cursor.fetchone()
                date_range = (row[0], row[1]) if row[0] else None

            # Last updated
            async with db.execute("""
                SELECT MAX(updated_at) FROM memories
            """) as cursor:
                last_updated = (await cursor.fetchone())[0]

        return {
            "total_memories": total_memories,
            "memories_by_type": memories_by_type,
            "memories_by_importance": memories_by_importance,
            "total_entities": total_entities,
            "entities_by_type": entities_by_type,
            "total_topics": total_topics,
            "date_range": date_range,
            "last_updated": last_updated,
        }

    # ============ HELPERS ============

    def _row_to_memory(self, row: dict[str, Any]) -> Memory:
        """Convert database row to Memory object."""
        return Memory(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            importance=Importance(row["importance"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]) if row.get("occurred_at") else None,
            sentiment_score=row.get("sentiment_score"),
            source=row.get("source"),
            source_id=row.get("source_id"),
            summary=row.get("summary"),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
        )

    def _row_to_entity(self, row: dict[str, Any]) -> Entity:
        """Convert database row to Entity object."""
        return Entity(
            id=row["id"],
            name=row["name"],
            entity_type=EntityType(row["entity_type"]),
            aliases=json.loads(row["aliases"]) if row.get("aliases") else [],
            description=row.get("description"),
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            metadata=json.loads(row["metadata"]) if row.get("metadata") else {},
        )


# Global instance
_metadata_db: Optional[MetadataDB] = None


def get_metadata_db() -> MetadataDB:
    """Get the global MetadataDB instance."""
    global _metadata_db
    if _metadata_db is None:
        _metadata_db = MetadataDB()
    return _metadata_db


def reset_metadata_db() -> None:
    """Reset the global MetadataDB instance (for testing)."""
    global _metadata_db
    _metadata_db = None
