"""Unified query engine for Memory Palace."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.models import (
    Memory,
    MemorySearchResult,
    TimelineEntry,
    EntityProfile,
    PalaceStats,
    MemoryType,
    ImportanceLevel,
)

logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Unified query interface combining vector search with metadata filtering.

    Provides high-level search operations that combine semantic similarity
    from ChromaDB with structured filtering from SQLite.
    """

    def __init__(self, vector_db: VectorDB, metadata_db: MetadataDB):
        """
        Initialize the query engine.

        Args:
            vector_db: Vector database instance
            metadata_db: Metadata database instance
        """
        self.vector_db = vector_db
        self.metadata_db = metadata_db

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[dict] = None,
        min_relevance: float = 0.5
    ) -> list[MemorySearchResult]:
        """
        Search for memories using semantic search with optional filters.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            filters: Optional filters (date_from, date_to, topics, entities, memory_types)
            min_relevance: Minimum similarity score (0-1)

        Returns:
            List of MemorySearchResult objects sorted by relevance
        """
        filters = filters or {}

        # Build vector DB filters for fields it can handle
        vector_filters = {}
        if filters.get('date_from'):
            vector_filters['date_from'] = filters['date_from']
        if filters.get('date_to'):
            vector_filters['date_to'] = filters['date_to']
        if filters.get('memory_types'):
            vector_filters['memory_types'] = filters['memory_types']
        if filters.get('importance'):
            vector_filters['importance'] = filters['importance']

        # Fetch more results than needed for post-filtering
        fetch_limit = limit * 3 if filters.get('topics') or filters.get('entities') else limit

        # Perform vector search
        raw_results = await self.vector_db.search(
            query=query,
            limit=fetch_limit,
            filters=vector_filters,
            min_relevance=min_relevance
        )

        # Post-filter by topics and entities (stored as JSON in metadata)
        results = []
        for raw in raw_results:
            metadata = raw.get('metadata', {})

            # Filter by topics
            if filters.get('topics'):
                memory_topics = metadata.get('topics', [])
                if isinstance(memory_topics, str):
                    import json
                    try:
                        memory_topics = json.loads(memory_topics)
                    except:
                        memory_topics = []
                if not any(t in memory_topics for t in filters['topics']):
                    continue

            # Filter by entities
            if filters.get('entities'):
                memory_entities = metadata.get('entities', {})
                if isinstance(memory_entities, str):
                    import json
                    try:
                        memory_entities = json.loads(memory_entities)
                    except:
                        memory_entities = {}
                # Flatten entity names from all types
                all_entity_names = []
                for names in memory_entities.values():
                    all_entity_names.extend(names)
                if not any(e.lower() in [n.lower() for n in all_entity_names] for e in filters['entities']):
                    continue

            # Parse timestamp
            timestamp = metadata.get('timestamp')
            if isinstance(timestamp, str):
                from dateutil.parser import parse
                try:
                    timestamp = parse(timestamp)
                except:
                    timestamp = datetime.utcnow()

            # Create Memory object
            memory = Memory(
                id=raw['id'],
                content=raw['content'],
                memory_type=metadata.get('memory_type', 'fact'),
                timestamp=timestamp if isinstance(timestamp, datetime) else datetime.utcnow(),
                topics=metadata.get('topics', []) if isinstance(metadata.get('topics'), list) else [],
                entities=metadata.get('entities', {}) if isinstance(metadata.get('entities'), dict) else {},
                importance=metadata.get('importance', 'medium'),
                source_context=metadata.get('source_context'),
                conversation_id=metadata.get('conversation_id'),
                sentiment=metadata.get('sentiment', 0.0),
            )

            results.append(MemorySearchResult(
                memory=memory,
                relevance_score=raw.get('relevance_score', 0.0)
            ))

            if len(results) >= limit:
                break

        return results

    async def search_by_entity(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> list[MemorySearchResult]:
        """
        Find memories mentioning a specific entity.

        Args:
            entity_name: Name of the entity
            entity_type: Optional type filter
            limit: Maximum results
            date_from: Optional start date
            date_to: Optional end date

        Returns:
            List of memories mentioning the entity
        """
        # Use entity name as search query for semantic relevance
        filters = {'entities': [entity_name]}
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to

        # Search using entity name
        results = await self.search(
            query=entity_name,
            limit=limit * 2,  # Get extra for filtering
            filters=filters,
            min_relevance=0.3  # Lower threshold for entity matches
        )

        # Additional filtering by entity type if specified
        if entity_type and entity_type != "ANY":
            filtered = []
            for result in results:
                entities_of_type = result.memory.entities.get(entity_type, [])
                if any(entity_name.lower() in e.lower() for e in entities_of_type):
                    filtered.append(result)
            results = filtered

        return results[:limit]

    async def search_by_date_range(
        self,
        date_from: datetime,
        date_to: datetime,
        topics: Optional[list[str]] = None,
        memory_types: Optional[list[str]] = None,
        limit: int = 50
    ) -> list[Memory]:
        """
        Find memories within a date range.

        Args:
            date_from: Start date
            date_to: End date
            topics: Optional topic filter
            memory_types: Optional memory type filter
            limit: Maximum results

        Returns:
            List of memories in the date range
        """
        # Use metadata DB for date range queries (more efficient)
        meta_results = await self.metadata_db.get_memories_by_date_range(
            date_from=date_from,
            date_to=date_to,
            memory_types=memory_types,
            limit=limit * 2 if topics else limit
        )

        memories = []
        for meta in meta_results:
            # Filter by topics if specified
            if topics:
                memory_topics = meta.get('topics', [])
                if not any(t in memory_topics for t in topics):
                    continue

            # Get full content from vector DB
            full_memory = await self.vector_db.get_by_id(meta['id'])
            if full_memory:
                memory = Memory(
                    id=meta['id'],
                    content=full_memory['content'],
                    memory_type=meta.get('memory_type', 'fact'),
                    timestamp=meta.get('timestamp', datetime.utcnow()),
                    topics=meta.get('topics', []),
                    entities=meta.get('entities', {}),
                    importance=meta.get('importance', 'medium'),
                    conversation_id=meta.get('conversation_id'),
                    sentiment=meta.get('sentiment', 0.0),
                )
                memories.append(memory)

                if len(memories) >= limit:
                    break

        return memories

    async def timeline_query(
        self,
        topic: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        granularity: str = "week",
        max_entries: int = 50
    ) -> list[TimelineEntry]:
        """
        Get chronological timeline of memories for a topic.

        Args:
            topic: Topic to trace through time
            date_from: Optional start date
            date_to: Optional end date
            granularity: Time grouping (day, week, month, year)
            max_entries: Maximum memories to include

        Returns:
            List of TimelineEntry objects grouped by time period
        """
        # Set default date range
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            # Default to 1 year ago
            date_from = date_to - timedelta(days=365)

        # Search for memories related to the topic
        results = await self.search(
            query=topic,
            limit=max_entries,
            filters={
                'date_from': date_from,
                'date_to': date_to,
            },
            min_relevance=0.3
        )

        # Group by time period
        period_groups: dict[str, list[Memory]] = {}

        for result in results:
            period_key, period_start, period_end, period_label = self._get_period_info(
                result.memory.timestamp, granularity
            )

            if period_key not in period_groups:
                period_groups[period_key] = {
                    'start': period_start,
                    'end': period_end,
                    'label': period_label,
                    'memories': []
                }

            period_groups[period_key]['memories'].append(result.memory)

        # Convert to TimelineEntry objects
        entries = []
        for period_key in sorted(period_groups.keys()):
            group = period_groups[period_key]
            entry = TimelineEntry(
                period_start=group['start'],
                period_end=group['end'],
                period_label=group['label'],
                memories=group['memories'],
                memory_count=len(group['memories']),
                # TODO: Add AI-generated summaries
                summary=None
            )
            entries.append(entry)

        return entries

    def _get_period_info(self, dt: datetime, granularity: str) -> tuple:
        """Get period key, start, end, and label for a datetime."""
        if granularity == "day":
            period_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=1)
            period_key = dt.strftime("%Y-%m-%d")
            period_label = dt.strftime("%B %d, %Y")

        elif granularity == "week":
            # Start of week (Monday)
            period_start = dt - timedelta(days=dt.weekday())
            period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=7)
            period_key = period_start.strftime("%Y-W%W")
            period_label = f"Week of {period_start.strftime('%B %d, %Y')}"

        elif granularity == "month":
            period_start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
            period_key = dt.strftime("%Y-%m")
            period_label = dt.strftime("%B %Y")

        elif granularity == "year":
            period_start = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start.replace(year=period_start.year + 1)
            period_key = dt.strftime("%Y")
            period_label = dt.strftime("%Y")

        else:
            # Default to week
            return self._get_period_info(dt, "week")

        return period_key, period_start, period_end, period_label

    async def get_topic_evolution(
        self,
        topic: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        granularity: str = "month"
    ) -> dict:
        """
        Analyze how thinking on a topic evolved over time.

        Args:
            topic: Topic to analyze
            date_from: Start date
            date_to: End date
            granularity: Analysis period (week, month, quarter, year)

        Returns:
            Evolution analysis with trends and key themes per period
        """
        # Get timeline entries
        entries = await self.timeline_query(
            topic=topic,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
            max_entries=100
        )

        evolution = []
        for entry in entries:
            # Extract key themes from memories in this period
            all_topics = []
            sentiments = []
            sample_contents = []

            for memory in entry.memories[:5]:  # Limit samples
                all_topics.extend(memory.topics)
                sentiments.append(memory.sentiment)
                sample_contents.append(memory.content[:100] + "..." if len(memory.content) > 100 else memory.content)

            # Count topic frequency
            from collections import Counter
            topic_counts = Counter(all_topics)
            key_themes = [t for t, _ in topic_counts.most_common(5) if t.lower() != topic.lower()]

            # Average sentiment
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            evolution.append({
                'period_label': entry.period_label,
                'period_start': entry.period_start,
                'period_end': entry.period_end,
                'memory_count': entry.memory_count,
                'key_themes': key_themes,
                'sentiment_trend': avg_sentiment,
                'sample_memories': sample_contents
            })

        # Determine overall trend
        if len(evolution) >= 2:
            first_count = evolution[0]['memory_count']
            last_count = evolution[-1]['memory_count']
            if last_count > first_count * 1.5:
                overall_trend = "increasing interest"
            elif last_count < first_count * 0.5:
                overall_trend = "decreasing interest"
            else:
                overall_trend = "stable interest"
        else:
            overall_trend = "insufficient data"

        return {
            'topic': topic,
            'evolution': evolution,
            'overall_trend': overall_trend
        }

    async def get_entity_profile(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
        include_memories: bool = True,
        memory_limit: int = 10
    ) -> Optional[EntityProfile]:
        """
        Get comprehensive profile of an entity.

        Args:
            entity_name: Entity name
            entity_type: Optional type for disambiguation
            include_memories: Whether to include recent memories
            memory_limit: Max memories to include

        Returns:
            EntityProfile or None if not found
        """
        # Get entity from metadata DB
        entity = await self.metadata_db.get_entity(entity_name, entity_type)

        if not entity:
            # Try searching
            entities = await self.metadata_db.search_entities(entity_name, limit=1)
            if entities:
                entity = entities[0]
            else:
                return None

        # Get related entities (entities that appear in same memories)
        # For now, return empty - would need memory traversal
        related_entities = []

        # Get key facts (memories with "fact" type mentioning this entity)
        key_facts = []
        recent_memories = []

        if include_memories:
            memories = await self.search_by_entity(
                entity_name=entity['name'],
                entity_type=entity.get('entity_type'),
                limit=memory_limit
            )

            for result in memories:
                recent_memories.append(result.memory)
                if result.memory.memory_type == "fact":
                    key_facts.append(result.memory.content[:200])

        return EntityProfile(
            name=entity['name'],
            entity_type=entity['entity_type'],
            mention_count=entity.get('mention_count', 1),
            first_seen=entity.get('first_seen', datetime.utcnow()),
            last_seen=entity.get('last_seen', datetime.utcnow()),
            related_topics=entity.get('related_topics', []),
            related_entities=related_entities,
            key_facts=key_facts[:5],
            recent_memories=recent_memories
        )

    async def get_stats(self) -> PalaceStats:
        """
        Get statistics about the memory palace.

        Returns:
            PalaceStats object with comprehensive statistics
        """
        stats = await self.metadata_db.get_stats()

        # Parse datetime strings
        oldest = stats.get('oldest_memory')
        newest = stats.get('newest_memory')

        if oldest and isinstance(oldest, str):
            from dateutil.parser import parse
            try:
                oldest = parse(oldest)
            except:
                oldest = None

        if newest and isinstance(newest, str):
            from dateutil.parser import parse
            try:
                newest = parse(newest)
            except:
                newest = None

        return PalaceStats(
            total_memories=stats.get('total_memories', 0),
            total_entities=stats.get('total_entities', 0),
            total_topics=stats.get('total_topics', 0),
            total_conversations=stats.get('total_conversations', 0),
            memories_by_type=stats.get('memories_by_type', {}),
            memories_by_importance=stats.get('memories_by_importance', {}),
            oldest_memory=oldest,
            newest_memory=newest,
            top_topics=stats.get('top_topics', []),
            top_entities=stats.get('top_entities', [])
        )

    async def get_recent_memories(
        self,
        limit: int = 20,
        memory_types: Optional[list[str]] = None,
        include_conversations: bool = True
    ) -> list[Memory]:
        """
        Get most recent memories.

        Args:
            limit: Number of memories to return
            memory_types: Optional filter by types
            include_conversations: Include conversation summaries

        Returns:
            List of recent Memory objects
        """
        # Adjust types filter
        types_filter = memory_types
        if types_filter and not include_conversations:
            types_filter = [t for t in types_filter if t not in ['conversation', 'summary']]

        meta_results = await self.metadata_db.get_recent_memories(
            limit=limit,
            memory_types=types_filter
        )

        memories = []
        for meta in meta_results:
            # Get full content
            full = await self.vector_db.get_by_id(meta['id'])
            if full:
                memory = Memory(
                    id=meta['id'],
                    content=full['content'],
                    memory_type=meta.get('memory_type', 'fact'),
                    timestamp=meta.get('timestamp', datetime.utcnow()),
                    topics=meta.get('topics', []),
                    entities=meta.get('entities', {}),
                    importance=meta.get('importance', 'medium'),
                    conversation_id=meta.get('conversation_id'),
                    sentiment=meta.get('sentiment', 0.0),
                )
                memories.append(memory)

        return memories
