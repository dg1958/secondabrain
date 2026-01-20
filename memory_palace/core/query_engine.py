"""
Unified query engine for Memory Palace.

Combines vector search and metadata filtering for comprehensive
memory retrieval.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Any
from collections import defaultdict

from ..config import get_settings
from .models import (
    Memory, Entity, SearchResult, TimelineEntry,
    EntityProfile, MemoryStats, Importance
)
from .vector_db import get_vector_db, VectorDB
from .metadata_db import get_metadata_db, MetadataDB
from .metadata_extractor import get_extractor, MetadataExtractor

logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Unified query interface for the Memory Palace.

    Coordinates between vector DB and metadata DB to provide
    comprehensive search capabilities.
    """

    def __init__(
        self,
        vector_db: Optional[VectorDB] = None,
        metadata_db: Optional[MetadataDB] = None,
        extractor: Optional[MetadataExtractor] = None,
    ):
        """
        Initialize the query engine.

        Args:
            vector_db: Vector database instance (uses global if not provided)
            metadata_db: Metadata database instance (uses global if not provided)
            extractor: Metadata extractor instance (uses global if not provided)
        """
        self._vector_db = vector_db
        self._metadata_db = metadata_db
        self._extractor = extractor
        self._settings = get_settings()

    @property
    def vector_db(self) -> VectorDB:
        """Get vector database instance."""
        if self._vector_db is None:
            self._vector_db = get_vector_db()
        return self._vector_db

    @property
    def metadata_db(self) -> MetadataDB:
        """Get metadata database instance."""
        if self._metadata_db is None:
            self._metadata_db = get_metadata_db()
        return self._metadata_db

    @property
    def extractor(self) -> MetadataExtractor:
        """Get metadata extractor instance."""
        if self._extractor is None:
            self._extractor = get_extractor()
        return self._extractor

    # ============ SAVE OPERATIONS ============

    async def save_memory(
        self,
        content: str,
        memory_type: str = "fact",
        importance: str = "medium",
        topics: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        occurred_at: Optional[datetime] = None,
        source: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Memory, list[str], list[str]]:
        """
        Save a new memory with automatic metadata extraction.

        Args:
            content: Memory content
            memory_type: Type of memory
            importance: Importance level
            topics: Topics (auto-extracted if not provided)
            entities: Entity names (auto-extracted if not provided)
            occurred_at: When the event occurred
            source: Source identifier
            metadata: Additional metadata

        Returns:
            Tuple of (memory, extracted_entities, extracted_topics)
        """
        # Extract metadata if not provided
        extracted = await self.extractor.extract_all(content)

        extracted_entity_names = []
        extracted_topic_names = []

        # Handle entities
        entity_ids = []
        if entities is not None:
            # Use provided entities
            for name in entities:
                entity = await self._get_or_create_entity(name)
                entity_ids.append(entity.id)
                extracted_entity_names.append(entity.name)
        else:
            # Use extracted entities
            for entity in extracted["entities"]:
                existing = await self.metadata_db.find_entity_by_name(entity.name)
                if existing:
                    entity_ids.append(existing.id)
                    await self.metadata_db.update_entity_seen(existing.id)
                else:
                    await self.metadata_db.save_entity(entity)
                    entity_ids.append(entity.id)
                extracted_entity_names.append(entity.name)

        # Handle topics
        if topics is not None:
            memory_topics = topics
        else:
            memory_topics = extracted["topics"]
        extracted_topic_names = memory_topics

        # Create memory object
        memory = Memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            topics=memory_topics,
            entities=entity_ids,
            occurred_at=occurred_at,
            source=source or "manual",
            sentiment_score=extracted["sentiment"],
            metadata=metadata or {},
        )

        # Save to both databases
        await self.vector_db.add_memory(memory)
        await self.metadata_db.save_memory(memory)

        logger.info(f"Saved memory {memory.id}")
        return memory, extracted_entity_names, extracted_topic_names

    async def _get_or_create_entity(self, name: str) -> Entity:
        """Get an existing entity or create a new one."""
        existing = await self.metadata_db.find_entity_by_name(name)
        if existing:
            await self.metadata_db.update_entity_seen(existing.id)
            return existing

        # Create new entity (will be typed as CONCEPT by default)
        entity = Entity(
            name=name,
            entity_type="CONCEPT",
        )
        await self.metadata_db.save_entity(entity)
        return entity

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        memory_type: Optional[str] = None,
        importance: Optional[str] = None,
        topics: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[Memory]:
        """
        Update an existing memory.

        Args:
            memory_id: ID of the memory to update
            content: New content (if updating)
            memory_type: New memory type
            importance: New importance level
            topics: New topics (replaces existing)
            metadata: Additional metadata to merge

        Returns:
            Updated memory or None if not found
        """
        memory = await self.metadata_db.get_memory(memory_id)
        if not memory:
            return None

        if content is not None:
            memory.content = content
            # Re-extract entities/topics for new content
            extracted = await self.extractor.extract_all(content)
            if topics is None:
                memory.topics = extracted["topics"]
            memory.sentiment_score = extracted["sentiment"]

        if memory_type is not None:
            memory.memory_type = memory_type

        if importance is not None:
            memory.importance = importance

        if topics is not None:
            memory.topics = topics

        if metadata is not None:
            memory.metadata.update(metadata)

        memory.updated_at = datetime.utcnow()

        # Update both databases
        await self.vector_db.update_memory(memory)
        await self.metadata_db.update_memory(memory)

        return memory

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory from both databases.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if deleted successfully
        """
        vector_deleted = await self.vector_db.delete_memory(memory_id)
        metadata_deleted = await self.metadata_db.delete_memory(memory_id)

        return vector_deleted and metadata_deleted

    # ============ SEARCH OPERATIONS ============

    async def search(
        self,
        query: str,
        limit: int = 10,
        memory_types: Optional[list[str]] = None,
        min_importance: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        topics: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        sort_by: str = "relevance",
    ) -> list[SearchResult]:
        """
        Semantic search with metadata filtering.

        Args:
            query: Search query
            limit: Maximum results
            memory_types: Filter by memory types
            min_importance: Minimum importance level
            date_from: Start date filter
            date_to: End date filter
            topics: Filter by topics
            entities: Filter by entity names
            sort_by: Sort order (relevance, date_desc, date_asc, importance)

        Returns:
            List of search results with relevance scores
        """
        settings = self._settings.search

        # Build ChromaDB where clause for filtering
        where = {}

        if memory_types:
            where["memory_type"] = {"$in": memory_types}

        if min_importance:
            importance_order = ["low", "medium", "high", "critical"]
            min_idx = importance_order.index(min_importance)
            valid_importance = importance_order[min_idx:]
            where["importance"] = {"$in": valid_importance}

        if date_from:
            where["created_at"] = {"$gte": date_from.isoformat()}

        if date_to:
            if "created_at" in where:
                where["created_at"]["$lte"] = date_to.isoformat()
            else:
                where["created_at"] = {"$lte": date_to.isoformat()}

        # Perform vector search
        vector_results = await self.vector_db.search(
            query=query,
            limit=limit * 2,  # Get extra for post-filtering
            where=where if where else None,
        )

        if not vector_results:
            return []

        # Get full memory objects
        memory_ids = [r["id"] for r in vector_results]
        memories = await self.metadata_db.get_memories_by_ids(memory_ids)

        # Create lookup for relevance scores
        score_map = {r["id"]: r["similarity"] for r in vector_results}

        # Build results with filtering
        results = []
        for memory in memories:
            # Apply topic filter
            if topics:
                if not any(t in memory.topics for t in topics):
                    continue

            # Apply entity filter (by name matching)
            if entities:
                # Get entity IDs from names
                entity_ids_to_match = []
                for name in entities:
                    entity = await self.metadata_db.find_entity_by_name(name)
                    if entity:
                        entity_ids_to_match.append(entity.id)

                if not any(eid in memory.entities for eid in entity_ids_to_match):
                    continue

            relevance = score_map.get(memory.id, 0.5)
            match_reasons = self._get_match_reasons(query, memory)

            results.append(SearchResult(
                memory=memory,
                relevance_score=relevance,
                match_reasons=match_reasons,
            ))

        # Sort results
        if sort_by == "relevance":
            results.sort(key=lambda r: r.relevance_score, reverse=True)
        elif sort_by == "date_desc":
            results.sort(key=lambda r: r.memory.created_at, reverse=True)
        elif sort_by == "date_asc":
            results.sort(key=lambda r: r.memory.created_at)
        elif sort_by == "importance":
            importance_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            results.sort(
                key=lambda r: importance_order.get(r.memory.importance, 2),
                reverse=True
            )

        return results[:limit]

    def _get_match_reasons(self, query: str, memory: Memory) -> list[str]:
        """Determine why a memory matched a query."""
        reasons = []
        query_lower = query.lower()
        content_lower = memory.content.lower()

        # Check for direct term matches
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        common_words = query_words & content_words
        if common_words:
            reasons.append(f"Content matches: {', '.join(list(common_words)[:3])}")

        # Check topic matches
        for topic in memory.topics:
            if topic.lower() in query_lower or query_lower in topic.lower():
                reasons.append(f"Topic match: {topic}")
                break

        if not reasons:
            reasons.append("Semantic similarity")

        return reasons

    async def search_by_entity(
        self,
        entity_name: str,
        limit: int = 20,
        include_related: bool = True,
    ) -> list[SearchResult]:
        """
        Search for memories mentioning a specific entity.

        Args:
            entity_name: Name of the entity
            limit: Maximum results
            include_related: Include memories mentioning related entities

        Returns:
            List of search results
        """
        entity = await self.metadata_db.find_entity_by_name(entity_name)
        if not entity:
            # Try semantic search as fallback
            return await self.search(entity_name, limit=limit)

        # Get memories directly mentioning this entity
        memories = await self.metadata_db.get_entity_memories(entity.id, limit=limit)

        results = []
        for memory in memories:
            results.append(SearchResult(
                memory=memory,
                relevance_score=1.0,
                match_reasons=[f"Mentions entity: {entity.name}"],
            ))

        # Sort by date
        results.sort(key=lambda r: r.memory.created_at, reverse=True)

        return results

    async def search_by_date_range(
        self,
        date_from: datetime,
        date_to: datetime,
        memory_types: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[Memory]:
        """
        Get all memories within a date range.

        Args:
            date_from: Start date
            date_to: End date
            memory_types: Filter by memory types
            limit: Maximum results

        Returns:
            List of memories
        """
        return await self.metadata_db.get_memories_by_date_range(
            date_from=date_from,
            date_to=date_to,
            memory_types=memory_types,
            limit=limit,
        )

    # ============ TIMELINE OPERATIONS ============

    async def timeline_query(
        self,
        topic: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        granularity: str = "month",
        include_summaries: bool = True,
    ) -> list[TimelineEntry]:
        """
        Reconstruct a chronological timeline for a topic.

        Args:
            topic: Topic to trace
            date_from: Start date (defaults to earliest memory)
            date_to: End date (defaults to now)
            granularity: Time grouping (day, week, month, quarter, year)
            include_summaries: Generate summaries for each period

        Returns:
            List of timeline entries
        """
        # Default date range
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=365)

        # Search for relevant memories
        results = await self.search(
            query=topic,
            limit=100,
            date_from=date_from,
            date_to=date_to,
            sort_by="date_asc",
        )

        if not results:
            return []

        # Group memories by time period
        grouped = self._group_by_period([r.memory for r in results], granularity)

        # Build timeline entries
        entries = []
        for period_label, memories in grouped.items():
            if not memories:
                continue

            start = min(m.created_at for m in memories)
            end = max(m.created_at for m in memories)

            # Extract key events
            key_events = []
            for m in sorted(memories, key=lambda x: Importance.to_score(x.importance), reverse=True)[:3]:
                key_events.append(m.content[:100] + "..." if len(m.content) > 100 else m.content)

            # Generate summary (simple concatenation for now)
            summary = None
            if include_summaries and memories:
                summary = f"{len(memories)} memories about {topic}. "
                if key_events:
                    summary += f"Key: {key_events[0]}"

            entries.append(TimelineEntry(
                period_label=period_label,
                start_date=start,
                end_date=end,
                memories=memories,
                summary=summary,
                key_events=key_events,
            ))

        return entries

    def _group_by_period(
        self,
        memories: list[Memory],
        granularity: str
    ) -> dict[str, list[Memory]]:
        """Group memories by time period."""
        grouped = defaultdict(list)

        for memory in memories:
            dt = memory.occurred_at or memory.created_at

            if granularity == "day":
                label = dt.strftime("%Y-%m-%d")
            elif granularity == "week":
                # Start of week
                week_start = dt - timedelta(days=dt.weekday())
                label = f"Week of {week_start.strftime('%Y-%m-%d')}"
            elif granularity == "month":
                label = dt.strftime("%B %Y")
            elif granularity == "quarter":
                quarter = (dt.month - 1) // 3 + 1
                label = f"Q{quarter} {dt.year}"
            elif granularity == "year":
                label = str(dt.year)
            else:
                label = dt.strftime("%B %Y")

            grouped[label].append(memory)

        return dict(grouped)

    async def get_topic_evolution(
        self,
        topic: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Analyze how thinking on a topic evolved over time.

        Args:
            topic: Topic to analyze
            date_from: Start date
            date_to: End date

        Returns:
            Evolution analysis with phases and sentiment trends
        """
        timeline = await self.timeline_query(
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            granularity="month",
            include_summaries=True,
        )

        if not timeline:
            return {
                "topic": topic,
                "evolution_summary": f"No memories found about {topic}.",
                "phases": [],
                "sentiment_trend": None,
            }

        # Analyze phases
        phases = []
        for entry in timeline:
            avg_sentiment = None
            sentiments = [m.sentiment_score for m in entry.memories if m.sentiment_score is not None]
            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)

            phases.append({
                "period": entry.period_label,
                "memory_count": len(entry.memories),
                "avg_sentiment": avg_sentiment,
                "key_themes": entry.key_events[:2],
            })

        # Generate evolution summary
        total_memories = sum(len(e.memories) for e in timeline)
        evolution_summary = (
            f"Found {total_memories} memories about {topic} across {len(timeline)} periods. "
        )

        if len(phases) >= 2:
            first_phase = phases[0]
            last_phase = phases[-1]
            if first_phase.get("avg_sentiment") and last_phase.get("avg_sentiment"):
                sentiment_change = last_phase["avg_sentiment"] - first_phase["avg_sentiment"]
                if sentiment_change > 0.2:
                    evolution_summary += "Sentiment has become more positive over time."
                elif sentiment_change < -0.2:
                    evolution_summary += "Sentiment has become more negative over time."
                else:
                    evolution_summary += "Sentiment has remained relatively stable."

        # Sentiment trend
        sentiment_trend = []
        for phase in phases:
            if phase.get("avg_sentiment") is not None:
                sentiment_trend.append({
                    "period": phase["period"],
                    "sentiment": phase["avg_sentiment"],
                })

        return {
            "topic": topic,
            "evolution_summary": evolution_summary,
            "phases": phases,
            "sentiment_trend": sentiment_trend if sentiment_trend else None,
        }

    # ============ ENTITY OPERATIONS ============

    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "memory_count",
    ) -> list[Entity]:
        """List all known entities."""
        return await self.metadata_db.list_entities(
            entity_type=entity_type,
            limit=limit,
            sort_by=sort_by,
        )

    async def get_entity_profile(
        self,
        entity_name: str,
        include_memories: bool = True,
        memory_limit: int = 10,
    ) -> Optional[EntityProfile]:
        """
        Get comprehensive information about an entity.

        Args:
            entity_name: Name of the entity
            include_memories: Include recent memories
            memory_limit: Maximum memories to include

        Returns:
            Entity profile or None if not found
        """
        entity = await self.metadata_db.find_entity_by_name(entity_name)
        if not entity:
            return None

        # Get recent memories
        recent_memories = []
        if include_memories:
            recent_memories = await self.metadata_db.get_entity_memories(
                entity.id,
                limit=memory_limit,
            )

        # Get associated topics from memories
        associated_topics = set()
        for memory in recent_memories:
            associated_topics.update(memory.topics)

        # Find related entities (co-occurring in memories)
        related_entity_ids = set()
        for memory in recent_memories:
            for eid in memory.entities:
                if eid != entity.id:
                    related_entity_ids.add(eid)

        related_entities = []
        for eid in list(related_entity_ids)[:5]:
            rel_entity = await self.metadata_db.get_entity(eid)
            if rel_entity:
                related_entities.append(rel_entity)

        # Count total memories
        all_entity_memories = await self.metadata_db.get_entity_memories(entity.id, limit=1000)
        memory_count = len(all_entity_memories)

        return EntityProfile(
            entity=entity,
            recent_memories=recent_memories,
            memory_count=memory_count,
            related_entities=related_entities,
            associated_topics=list(associated_topics),
            first_mentioned=entity.first_seen,
            last_mentioned=entity.last_seen,
        )

    # ============ BROWSE OPERATIONS ============

    async def list_topics(
        self,
        limit: int = 50,
        sort_by: str = "memory_count",
        min_count: int = 1,
    ) -> list[dict[str, Any]]:
        """List all topics with memory counts."""
        return await self.metadata_db.list_topics(
            limit=limit,
            sort_by=sort_by,
            min_count=min_count,
        )

    async def list_recent(
        self,
        limit: int = 20,
        memory_types: Optional[list[str]] = None,
        days: Optional[int] = None,
    ) -> list[Memory]:
        """
        Get recent memories.

        Args:
            limit: Maximum memories to return
            memory_types: Filter by memory types
            days: Only include memories from last N days

        Returns:
            List of recent memories
        """
        date_from = None
        if days:
            date_from = datetime.utcnow() - timedelta(days=days)

        return await self.metadata_db.search_memories(
            memory_types=memory_types,
            date_from=date_from,
            limit=limit,
        )

    # ============ STATISTICS ============

    async def get_stats(
        self,
        include_top_topics: bool = True,
        include_top_entities: bool = True,
        top_limit: int = 10,
    ) -> MemoryStats:
        """
        Get comprehensive statistics about the memory palace.

        Args:
            include_top_topics: Include top topics
            include_top_entities: Include top entities
            top_limit: Number of top items to include

        Returns:
            Statistics object
        """
        db_stats = await self.metadata_db.get_stats()

        top_topics = []
        if include_top_topics:
            topics = await self.list_topics(limit=top_limit)
            top_topics = [(t["name"], t["memory_count"]) for t in topics]

        date_range = None
        if db_stats.get("date_range"):
            start, end = db_stats["date_range"]
            if start and end:
                date_range = (datetime.fromisoformat(start), datetime.fromisoformat(end))

        last_updated = None
        if db_stats.get("last_updated"):
            last_updated = datetime.fromisoformat(db_stats["last_updated"])

        return MemoryStats(
            total_memories=db_stats.get("total_memories", 0),
            memories_by_type=db_stats.get("memories_by_type", {}),
            memories_by_importance=db_stats.get("memories_by_importance", {}),
            total_entities=db_stats.get("total_entities", 0),
            entities_by_type=db_stats.get("entities_by_type", {}),
            total_topics=db_stats.get("total_topics", 0),
            top_topics=top_topics,
            date_range=date_range,
            last_updated=last_updated,
        )


# Global instance
_query_engine: Optional[QueryEngine] = None


def get_query_engine() -> QueryEngine:
    """Get the global QueryEngine instance."""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine


def reset_query_engine() -> None:
    """Reset the global QueryEngine instance (for testing)."""
    global _query_engine
    _query_engine = None
