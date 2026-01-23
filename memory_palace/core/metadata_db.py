"""SQLite metadata database for Memory Palace."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class MetadataDB:
    """
    SQLite database for metadata, entities, and topics.

    Provides fast filtering and aggregation that complements
    the vector database's semantic search.
    """

    SCHEMA = """
    -- Entities table
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        mention_count INTEGER DEFAULT 1,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP,
        related_topics TEXT,
        UNIQUE(name, entity_type)
    );

    -- Topics table
    CREATE TABLE IF NOT EXISTS topics (
        name TEXT PRIMARY KEY,
        count INTEGER DEFAULT 1,
        first_seen TIMESTAMP,
        last_seen TIMESTAMP
    );

    -- Memory metadata cache
    CREATE TABLE IF NOT EXISTS memories_meta (
        id TEXT PRIMARY KEY,
        content_preview TEXT,
        memory_type TEXT,
        timestamp TIMESTAMP,
        importance TEXT,
        topics TEXT,
        entities TEXT,
        conversation_id TEXT,
        sentiment REAL DEFAULT 0.0
    );

    -- Conversations table
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        started_at TIMESTAMP,
        ended_at TIMESTAMP,
        summary TEXT,
        message_count INTEGER DEFAULT 0,
        topics TEXT
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories_meta(timestamp);
    CREATE INDEX IF NOT EXISTS idx_memories_type ON memories_meta(memory_type);
    CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories_meta(importance);
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
    CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
    """

    def __init__(self, db_path: str):
        """
        Initialize the metadata database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database and create tables."""
        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row

        # Create tables
        await self._connection.executescript(self.SCHEMA)
        await self._connection.commit()

        logger.info(f"Metadata DB initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def _ensure_connected(self) -> None:
        """Ensure database is connected."""
        if self._connection is None:
            raise RuntimeError("MetadataDB not initialized. Call initialize() first.")

    # =========================================================================
    # Memory Metadata Operations
    # =========================================================================

    async def add_memory_meta(
        self,
        id: str,
        content: str,
        memory_type: str,
        timestamp: datetime,
        importance: str,
        topics: list[str],
        entities: dict[str, list[str]],
        conversation_id: Optional[str] = None,
        sentiment: float = 0.0
    ) -> None:
        """Add memory metadata to the cache."""
        self._ensure_connected()

        content_preview = content[:200] if len(content) > 200 else content

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO memories_meta
            (id, content_preview, memory_type, timestamp, importance, topics, entities, conversation_id, sentiment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                content_preview,
                memory_type,
                timestamp.isoformat(),
                importance,
                json.dumps(topics),
                json.dumps(entities),
                conversation_id,
                sentiment
            )
        )
        await self._connection.commit()

        # Update topic counts
        for topic in topics:
            await self.upsert_topic(topic, timestamp)

        # Update entity counts
        for entity_type, names in entities.items():
            for name in names:
                await self.upsert_entity(name, entity_type, timestamp, topics)

    async def get_memory_meta(self, id: str) -> Optional[dict]:
        """Get memory metadata by ID."""
        self._ensure_connected()

        async with self._connection.execute(
            "SELECT * FROM memories_meta WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    async def update_memory_meta(
        self,
        id: str,
        **updates
    ) -> bool:
        """Update memory metadata."""
        self._ensure_connected()

        if not updates:
            return False

        # Build update query
        set_clauses = []
        values = []

        for key, value in updates.items():
            if value is not None:
                set_clauses.append(f"{key} = ?")
                if isinstance(value, (list, dict)):
                    values.append(json.dumps(value))
                elif isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)

        if not set_clauses:
            return False

        values.append(id)
        query = f"UPDATE memories_meta SET {', '.join(set_clauses)} WHERE id = ?"

        await self._connection.execute(query, values)
        await self._connection.commit()
        return True

    async def delete_memory_meta(self, id: str) -> bool:
        """Delete memory metadata."""
        self._ensure_connected()

        await self._connection.execute(
            "DELETE FROM memories_meta WHERE id = ?", (id,)
        )
        await self._connection.commit()
        return True

    async def get_memories_by_date_range(
        self,
        date_from: datetime,
        date_to: datetime,
        memory_types: Optional[list[str]] = None,
        limit: int = 100
    ) -> list[dict]:
        """Get memories within a date range."""
        self._ensure_connected()

        query = """
            SELECT * FROM memories_meta
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [date_from.isoformat(), date_to.isoformat()]

        if memory_types:
            placeholders = ','.join('?' * len(memory_types))
            query += f" AND memory_type IN ({placeholders})"
            params.extend(memory_types)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    async def get_recent_memories(
        self,
        limit: int = 20,
        memory_types: Optional[list[str]] = None
    ) -> list[dict]:
        """Get most recent memories."""
        self._ensure_connected()

        query = "SELECT * FROM memories_meta"
        params = []

        if memory_types:
            placeholders = ','.join('?' * len(memory_types))
            query += f" WHERE memory_type IN ({placeholders})"
            params.extend(memory_types)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    # =========================================================================
    # Entity Operations
    # =========================================================================

    async def upsert_entity(
        self,
        name: str,
        entity_type: str,
        timestamp: datetime,
        related_topics: Optional[list[str]] = None
    ) -> None:
        """Insert or update an entity."""
        self._ensure_connected()

        import uuid

        # Check if entity exists
        async with self._connection.execute(
            "SELECT id, mention_count, related_topics FROM entities WHERE name = ? AND entity_type = ?",
            (name, entity_type)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            # Update existing entity
            current_topics = json.loads(existing['related_topics'] or '[]')
            if related_topics:
                current_topics = list(set(current_topics + related_topics))

            await self._connection.execute(
                """
                UPDATE entities
                SET mention_count = mention_count + 1,
                    last_seen = ?,
                    related_topics = ?
                WHERE id = ?
                """,
                (timestamp.isoformat(), json.dumps(current_topics), existing['id'])
            )
        else:
            # Insert new entity
            await self._connection.execute(
                """
                INSERT INTO entities (id, name, entity_type, mention_count, first_seen, last_seen, related_topics)
                VALUES (?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    name,
                    entity_type,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    json.dumps(related_topics or [])
                )
            )

        await self._connection.commit()

    async def get_entity(self, name: str, entity_type: Optional[str] = None) -> Optional[dict]:
        """Get an entity by name and optionally type."""
        self._ensure_connected()

        if entity_type:
            query = "SELECT * FROM entities WHERE name = ? AND entity_type = ?"
            params = (name, entity_type)
        else:
            query = "SELECT * FROM entities WHERE name = ? ORDER BY mention_count DESC LIMIT 1"
            params = (name,)

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    async def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "count"
    ) -> list[dict]:
        """Get entities with optional filtering."""
        self._ensure_connected()

        query = "SELECT * FROM entities"
        params = []

        if entity_type and entity_type != "ANY":
            query += " WHERE entity_type = ?"
            params.append(entity_type)

        if sort_by == "count":
            query += " ORDER BY mention_count DESC"
        elif sort_by == "name":
            query += " ORDER BY name ASC"
        elif sort_by == "recent":
            query += " ORDER BY last_seen DESC"

        query += " LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    async def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        """Search entities by name."""
        self._ensure_connected()

        async with self._connection.execute(
            "SELECT * FROM entities WHERE name LIKE ? ORDER BY mention_count DESC LIMIT ?",
            (f"%{query}%", limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    async def get_entity_count(self, entity_type: Optional[str] = None) -> int:
        """Get total entity count."""
        self._ensure_connected()

        if entity_type and entity_type != "ANY":
            query = "SELECT COUNT(*) FROM entities WHERE entity_type = ?"
            params = (entity_type,)
        else:
            query = "SELECT COUNT(*) FROM entities"
            params = ()

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # Topic Operations
    # =========================================================================

    async def upsert_topic(self, name: str, timestamp: datetime) -> None:
        """Insert or update a topic."""
        self._ensure_connected()

        # Check if topic exists
        async with self._connection.execute(
            "SELECT name FROM topics WHERE name = ?", (name,)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await self._connection.execute(
                "UPDATE topics SET count = count + 1, last_seen = ? WHERE name = ?",
                (timestamp.isoformat(), name)
            )
        else:
            await self._connection.execute(
                "INSERT INTO topics (name, count, first_seen, last_seen) VALUES (?, 1, ?, ?)",
                (name, timestamp.isoformat(), timestamp.isoformat())
            )

        await self._connection.commit()

    async def get_topics(
        self,
        limit: int = 50,
        sort_by: str = "count",
        min_count: int = 1
    ) -> list[dict]:
        """Get topics with optional filtering."""
        self._ensure_connected()

        query = "SELECT * FROM topics WHERE count >= ?"
        params = [min_count]

        if sort_by == "count":
            query += " ORDER BY count DESC"
        elif sort_by == "name":
            query += " ORDER BY name ASC"
        elif sort_by == "recent":
            query += " ORDER BY last_seen DESC"

        query += " LIMIT ?"
        params.append(limit)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    async def get_topic_count(self) -> int:
        """Get total topic count."""
        self._ensure_connected()

        async with self._connection.execute("SELECT COUNT(*) FROM topics") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # Conversation Operations
    # =========================================================================

    async def add_conversation(
        self,
        id: str,
        started_at: datetime,
        ended_at: Optional[datetime] = None,
        summary: Optional[str] = None,
        message_count: int = 0,
        topics: Optional[list[str]] = None
    ) -> None:
        """Add a conversation record."""
        self._ensure_connected()

        await self._connection.execute(
            """
            INSERT OR REPLACE INTO conversations
            (id, started_at, ended_at, summary, message_count, topics)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                started_at.isoformat(),
                ended_at.isoformat() if ended_at else None,
                summary,
                message_count,
                json.dumps(topics or [])
            )
        )
        await self._connection.commit()

    async def get_conversation(self, id: str) -> Optional[dict]:
        """Get a conversation by ID."""
        self._ensure_connected()

        async with self._connection.execute(
            "SELECT * FROM conversations WHERE id = ?", (id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    async def get_conversation_count(self) -> int:
        """Get total conversation count."""
        self._ensure_connected()

        async with self._connection.execute("SELECT COUNT(*) FROM conversations") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> dict:
        """Get database statistics."""
        self._ensure_connected()

        stats = {}

        # Memory counts
        async with self._connection.execute("SELECT COUNT(*) FROM memories_meta") as cursor:
            stats['total_memories'] = (await cursor.fetchone())[0]

        # Memory counts by type
        async with self._connection.execute(
            "SELECT memory_type, COUNT(*) FROM memories_meta GROUP BY memory_type"
        ) as cursor:
            stats['memories_by_type'] = {row[0]: row[1] for row in await cursor.fetchall()}

        # Memory counts by importance
        async with self._connection.execute(
            "SELECT importance, COUNT(*) FROM memories_meta GROUP BY importance"
        ) as cursor:
            stats['memories_by_importance'] = {row[0]: row[1] for row in await cursor.fetchall()}

        # Date range
        async with self._connection.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM memories_meta"
        ) as cursor:
            row = await cursor.fetchone()
            stats['oldest_memory'] = row[0]
            stats['newest_memory'] = row[1]

        # Entity and topic counts
        stats['total_entities'] = await self.get_entity_count()
        stats['total_topics'] = await self.get_topic_count()
        stats['total_conversations'] = await self.get_conversation_count()

        # Top topics
        top_topics = await self.get_topics(limit=10, sort_by="count")
        stats['top_topics'] = [(t['name'], t['count']) for t in top_topics]

        # Top entities
        top_entities = await self.get_entities(limit=10, sort_by="count")
        stats['top_entities'] = [(e['name'], e['entity_type'], e['mention_count']) for e in top_entities]

        return stats

    # =========================================================================
    # Utilities
    # =========================================================================

    def _row_to_dict(self, row: aiosqlite.Row) -> dict:
        """Convert a database row to a dictionary."""
        d = dict(row)

        # Parse JSON fields
        for field in ['topics', 'entities', 'related_topics']:
            if field in d and d[field]:
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    pass

        # Parse datetime fields
        for field in ['timestamp', 'first_seen', 'last_seen', 'started_at', 'ended_at']:
            if field in d and d[field] and isinstance(d[field], str):
                try:
                    from dateutil.parser import parse
                    d[field] = parse(d[field])
                except (ValueError, ImportError):
                    pass

        return d

    async def reset(self) -> None:
        """Reset the database (delete all data)."""
        self._ensure_connected()

        await self._connection.execute("DELETE FROM memories_meta")
        await self._connection.execute("DELETE FROM entities")
        await self._connection.execute("DELETE FROM topics")
        await self._connection.execute("DELETE FROM conversations")
        await self._connection.commit()

        logger.warning("Metadata DB reset - all data deleted")
