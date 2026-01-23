"""
Main query engine for Memory Palace.

This module provides:
- Unified query interface
- Natural language query processing
- Hybrid search (vector + metadata)
- Result caching
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from config.schema import (
    QueryFilter,
    QueryResponse,
    QueryResult,
    SourceType,
)
from query.agentic_planner import AgenticPlanner, get_agentic_planner
from query.result_synthesizer import ResultSynthesizer, get_result_synthesizer
from query.temporal_filter import TemporalFilter
from storage.embedding_service import EmbeddingService, get_embedding_service
from storage.vector_db import VectorDB, get_vector_db


class QueryEngine:
    """
    Main query interface for Memory Palace.

    Provides:
    - Natural language query processing
    - Semantic similarity search
    - Temporal and metadata filtering
    - LLM-powered query interpretation
    - Result synthesis and summarization
    """

    def __init__(
        self,
        vector_db: Optional[VectorDB] = None,
        embedding_service: Optional[EmbeddingService] = None,
        planner: Optional[AgenticPlanner] = None,
        synthesizer: Optional[ResultSynthesizer] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        """
        Initialize the query engine.

        Args:
            vector_db: Vector database for search
            embedding_service: Service for generating query embeddings
            planner: LLM query planner
            synthesizer: Result synthesizer
            anthropic_api_key: API key for LLM features
        """
        self._vector_db = vector_db
        self._embedding_service = embedding_service
        self._planner = planner
        self._synthesizer = synthesizer
        self._api_key = anthropic_api_key
        self._temporal_filter = TemporalFilter()

        # Simple query cache
        self._cache: Dict[str, QueryResponse] = {}
        self._cache_ttl = 3600  # 1 hour

    @property
    def vector_db(self) -> VectorDB:
        """Get the vector database."""
        if self._vector_db is None:
            self._vector_db = get_vector_db()
        return self._vector_db

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get the embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def planner(self) -> AgenticPlanner:
        """Get the query planner."""
        if self._planner is None:
            self._planner = get_agentic_planner(self._api_key)
        return self._planner

    @property
    def synthesizer(self) -> ResultSynthesizer:
        """Get the result synthesizer."""
        if self._synthesizer is None:
            self._synthesizer = get_result_synthesizer(self._api_key)
        return self._synthesizer

    def query(
        self,
        query_text: str,
        top_k: int = 10,
        filters: Optional[QueryFilter] = None,
        use_llm_interpretation: bool = True,
        synthesize_results: bool = True,
        use_cache: bool = True,
    ) -> QueryResponse:
        """
        Execute a natural language query.

        Args:
            query_text: Natural language query
            top_k: Number of results to return
            filters: Optional explicit filters
            use_llm_interpretation: Use LLM to interpret query
            synthesize_results: Generate synthesis of results
            use_cache: Use cached results if available

        Returns:
            QueryResponse with results and optional synthesis
        """
        start_time = time.time()

        # Check cache
        cache_key = f"{query_text}:{top_k}:{filters}"
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug(f"Returning cached results for query: {query_text[:50]}")
            return cached

        # Process the query
        search_text = query_text
        query_filters = filters or QueryFilter()

        # Extract temporal expressions
        cleaned_query, start_date, end_date = self._temporal_filter.extract_temporal_from_query(
            query_text
        )

        if start_date or end_date:
            search_text = cleaned_query
            if start_date:
                query_filters.start_date = start_date
            if end_date:
                query_filters.end_date = end_date

        # Use LLM to interpret query if enabled and available
        if use_llm_interpretation and self.planner.is_available:
            try:
                interpretation = self.planner.interpret_query(search_text)

                # Apply interpreted filters
                if interpretation.get("search_text"):
                    search_text = interpretation["search_text"]

                if interpretation.get("participants"):
                    query_filters.participants = interpretation["participants"]

                if interpretation.get("topics"):
                    query_filters.topics = interpretation["topics"]

            except Exception as e:
                logger.warning(f"LLM interpretation failed: {e}")

        # Generate query embedding
        query_embedding = self.embedding_service.embed_query(search_text)

        # Execute search
        results = self.vector_db.query(
            query_embedding=query_embedding.tolist(),
            filters=query_filters,
            top_k=top_k,
        )

        # Build response
        response = QueryResponse(
            query=query_text,
            results=results,
            total_results=len(results),
            processing_time_ms=(time.time() - start_time) * 1000,
            filters_applied=query_filters,
        )

        # Generate synthesis if requested
        if synthesize_results and results and self.synthesizer.is_available:
            try:
                response.synthesis = self.synthesizer.synthesize(query_text, results)
            except Exception as e:
                logger.warning(f"Result synthesis failed: {e}")

        # Cache result
        if use_cache:
            self._cache[cache_key] = response

        logger.info(
            f"Query completed: {len(results)} results in "
            f"{response.processing_time_ms:.0f}ms"
        )

        return response

    def search(
        self,
        search_text: str,
        top_k: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        participants: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        custom_tags: Optional[List[str]] = None,
        source: Optional[SourceType] = None,
    ) -> List[QueryResult]:
        """
        Execute a direct search with explicit parameters.

        Args:
            search_text: Text to search for
            top_k: Number of results
            start_date: Filter start date
            end_date: Filter end date
            participants: Filter by participants
            topics: Filter by topics
            custom_tags: Filter by tags
            source: Filter by source type

        Returns:
            List of QueryResult objects
        """
        # Build filters
        filters = QueryFilter(
            start_date=start_date,
            end_date=end_date,
            participants=participants,
            topics=topics,
            custom_tags=custom_tags,
            source=source,
        )

        # Generate embedding
        query_embedding = self.embedding_service.embed_query(search_text)

        # Execute search
        return self.vector_db.query(
            query_embedding=query_embedding.tolist(),
            filters=filters,
            top_k=top_k,
        )

    def search_by_participant(
        self,
        participant: str,
        top_k: int = 20,
    ) -> List[QueryResult]:
        """
        Find all memories involving a specific participant.

        Args:
            participant: Participant name to search for
            top_k: Maximum results

        Returns:
            List of QueryResult objects
        """
        filters = QueryFilter(participants=[participant])

        return self.vector_db.query(
            filters=filters,
            top_k=top_k,
        )

    def search_by_topic(
        self,
        topic: str,
        top_k: int = 20,
    ) -> List[QueryResult]:
        """
        Find all memories about a specific topic.

        Args:
            topic: Topic to search for
            top_k: Maximum results

        Returns:
            List of QueryResult objects
        """
        # Combine semantic search with topic filter
        query_embedding = self.embedding_service.embed_query(topic)
        filters = QueryFilter(topics=[topic])

        return self.vector_db.query(
            query_embedding=query_embedding.tolist(),
            filters=filters,
            top_k=top_k,
        )

    def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        search_text: Optional[str] = None,
        top_k: int = 50,
    ) -> List[QueryResult]:
        """
        Find memories within a date range.

        Args:
            start_date: Range start
            end_date: Range end
            search_text: Optional search text
            top_k: Maximum results

        Returns:
            List of QueryResult objects
        """
        filters = QueryFilter(
            start_date=start_date,
            end_date=end_date,
        )

        if search_text:
            query_embedding = self.embedding_service.embed_query(search_text)
            return self.vector_db.query(
                query_embedding=query_embedding.tolist(),
                filters=filters,
                top_k=top_k,
            )
        else:
            return self.vector_db.query(
                filters=filters,
                top_k=top_k,
            )

    def get_timeline(
        self,
        query_text: str,
        top_k: int = 50,
    ) -> List[QueryResult]:
        """
        Get a chronological timeline of memories related to a query.

        Args:
            query_text: Topic/subject for timeline
            top_k: Maximum results

        Returns:
            List of QueryResult objects sorted chronologically
        """
        # Search for relevant memories
        results = self.search(query_text, top_k=top_k)

        # Sort by timestamp
        results.sort(key=lambda r: r.metadata.timestamp)

        return results

    def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> List[QueryResult]:
        """
        Pure semantic similarity search without filters.

        Args:
            query_text: Search text
            top_k: Number of results

        Returns:
            List of QueryResult objects
        """
        query_embedding = self.embedding_service.embed_query(query_text)

        return self.vector_db.query(
            query_embedding=query_embedding.tolist(),
            top_k=top_k,
        )

    def multi_query_search(
        self,
        queries: List[str],
        top_k_per_query: int = 5,
        deduplicate: bool = True,
    ) -> List[QueryResult]:
        """
        Execute multiple queries and combine results.

        Args:
            queries: List of query strings
            top_k_per_query: Results per query
            deduplicate: Remove duplicate results

        Returns:
            Combined list of QueryResult objects
        """
        all_results: Dict[str, QueryResult] = {}

        for query in queries:
            results = self.semantic_search(query, top_k=top_k_per_query)

            for result in results:
                # Deduplicate by chunk_id
                if deduplicate and result.chunk_id in all_results:
                    # Keep higher scoring result
                    if result.score > all_results[result.chunk_id].score:
                        all_results[result.chunk_id] = result
                else:
                    all_results[result.chunk_id] = result

        # Sort by score
        combined = list(all_results.values())
        combined.sort(key=lambda r: r.score, reverse=True)

        return combined

    def agentic_query(
        self,
        query_text: str,
        max_steps: int = 5,
        synthesize: bool = True,
    ) -> QueryResponse:
        """
        Execute an agentic multi-step query.

        Uses LLM to plan and execute a complex query in steps.

        Args:
            query_text: Complex natural language query
            max_steps: Maximum planning steps
            synthesize: Whether to synthesize final results

        Returns:
            QueryResponse with combined results
        """
        start_time = time.time()

        if not self.planner.is_available:
            # Fall back to simple query
            return self.query(query_text, synthesize_results=synthesize)

        # Generate query plan
        plan = self.planner.plan_query(query_text)

        # Execute each step
        all_results: List[QueryResult] = []

        for i, step in enumerate(plan.steps[:max_steps]):
            search_query = step.get("search_query", query_text)
            step_filters = step.get("filters", {})

            # Build filter from step
            filters = QueryFilter()
            if "topics" in step_filters:
                filters.topics = step_filters["topics"]
            if "participants" in step_filters:
                filters.participants = step_filters["participants"]
            if "date_range" in step_filters:
                dr = step_filters["date_range"]
                if dr.get("start"):
                    filters.start_date = datetime.fromisoformat(dr["start"])
                if dr.get("end"):
                    filters.end_date = datetime.fromisoformat(dr["end"])

            # Execute step
            step_results = self.search(
                search_query,
                top_k=10,
                start_date=filters.start_date,
                end_date=filters.end_date,
                participants=filters.participants,
                topics=filters.topics,
            )

            # Store results
            plan.set_result(i, step_results)
            all_results.extend(step_results)

        # Deduplicate
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result.chunk_id not in seen_ids:
                seen_ids.add(result.chunk_id)
                unique_results.append(result)

        # Sort by relevance
        unique_results.sort(key=lambda r: r.score, reverse=True)

        # Build response
        response = QueryResponse(
            query=query_text,
            results=unique_results,
            total_results=len(unique_results),
            processing_time_ms=(time.time() - start_time) * 1000,
        )

        # Synthesize if requested
        if synthesize and unique_results:
            try:
                response.synthesis = self.synthesizer.synthesize(
                    query_text,
                    unique_results[:20],
                )
            except Exception as e:
                logger.warning(f"Synthesis failed: {e}")

        return response

    def clear_cache(self) -> None:
        """Clear the query cache."""
        self._cache.clear()
        logger.debug("Query cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get query engine statistics.

        Returns:
            Dictionary with engine statistics
        """
        return {
            "vector_db": self.vector_db.get_stats(),
            "cache_size": len(self._cache),
            "llm_available": self.planner.is_available,
            "synthesis_available": self.synthesizer.is_available,
        }


# Global query engine instance
_engine: Optional[QueryEngine] = None


def get_query_engine(
    anthropic_api_key: Optional[str] = None,
) -> QueryEngine:
    """
    Get the global query engine instance.

    Args:
        anthropic_api_key: API key for LLM features

    Returns:
        QueryEngine instance
    """
    global _engine
    if _engine is None:
        _engine = QueryEngine(anthropic_api_key=anthropic_api_key)
    return _engine


def query_memories(
    query_text: str,
    top_k: int = 10,
    synthesize: bool = True,
    api_key: Optional[str] = None,
) -> QueryResponse:
    """
    Convenience function to query memories.

    Args:
        query_text: Natural language query
        top_k: Number of results
        synthesize: Generate synthesis
        api_key: Optional API key

    Returns:
        QueryResponse
    """
    engine = get_query_engine(api_key)
    return engine.query(query_text, top_k=top_k, synthesize_results=synthesize)
