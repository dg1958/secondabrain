"""
Prometheus Metrics for Memory Palace.

This module defines all metrics used throughout the Memory Palace system,
providing comprehensive observability for:
- API requests and responses
- MCP tool calls
- Database operations
- Embedding generation
- Query processing
- Ingestion pipeline
"""

import functools
import time
from contextlib import contextmanager
from typing import Callable, Optional, Any

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    multiprocess,
    REGISTRY,
)

# ============================================================================
# METRICS REGISTRY
# ============================================================================

# Use the default registry for single-process mode
# For multiprocess mode (gunicorn), use multiprocess.MultiProcessCollector
registry = REGISTRY


# ============================================================================
# APPLICATION INFO
# ============================================================================

APP_INFO = Info(
    "memory_palace",
    "Memory Palace application information",
    registry=registry,
)
APP_INFO.info({
    "version": "1.0.0",
    "component": "memory_palace",
})


# ============================================================================
# REQUEST METRICS (REST API)
# ============================================================================

# Total HTTP requests
HTTP_REQUESTS_TOTAL = Counter(
    "memory_palace_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

# HTTP request duration
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "memory_palace_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    registry=registry,
)

# Active HTTP connections
HTTP_ACTIVE_CONNECTIONS = Gauge(
    "memory_palace_http_active_connections",
    "Number of active HTTP connections",
    registry=registry,
)

# HTTP request size
HTTP_REQUEST_SIZE_BYTES = Histogram(
    "memory_palace_http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
    registry=registry,
)

# HTTP response size
HTTP_RESPONSE_SIZE_BYTES = Histogram(
    "memory_palace_http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
    registry=registry,
)


# ============================================================================
# MCP SERVER METRICS
# ============================================================================

# Total MCP tool calls
MCP_TOOL_CALLS_TOTAL = Counter(
    "memory_palace_mcp_tool_calls_total",
    "Total number of MCP tool calls",
    ["tool_name", "status"],
    registry=registry,
)

# MCP tool call duration
MCP_TOOL_DURATION_SECONDS = Histogram(
    "memory_palace_mcp_tool_duration_seconds",
    "MCP tool execution latency in seconds",
    ["tool_name"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

# Active MCP connections
MCP_ACTIVE_CONNECTIONS = Gauge(
    "memory_palace_mcp_active_connections",
    "Number of active MCP connections",
    ["transport"],
    registry=registry,
)

# MCP resource reads
MCP_RESOURCE_READS_TOTAL = Counter(
    "memory_palace_mcp_resource_reads_total",
    "Total number of MCP resource reads",
    ["resource_uri"],
    registry=registry,
)


# ============================================================================
# QUERY ENGINE METRICS
# ============================================================================

# Total queries
QUERIES_TOTAL = Counter(
    "memory_palace_queries_total",
    "Total number of queries executed",
    ["query_type", "status"],
    registry=registry,
)

# Query duration
QUERY_DURATION_SECONDS = Histogram(
    "memory_palace_query_duration_seconds",
    "Query execution latency in seconds",
    ["query_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

# Query results count
QUERY_RESULTS_COUNT = Histogram(
    "memory_palace_query_results_count",
    "Number of results returned per query",
    ["query_type"],
    buckets=(0, 1, 5, 10, 25, 50, 100, 250, 500, 1000),
    registry=registry,
)

# Query cache hits/misses
QUERY_CACHE_HITS = Counter(
    "memory_palace_query_cache_hits_total",
    "Total number of query cache hits",
    registry=registry,
)

QUERY_CACHE_MISSES = Counter(
    "memory_palace_query_cache_misses_total",
    "Total number of query cache misses",
    registry=registry,
)


# ============================================================================
# STORAGE METRICS (Vector DB)
# ============================================================================

# Database operations
DB_OPERATIONS_TOTAL = Counter(
    "memory_palace_db_operations_total",
    "Total number of database operations",
    ["operation", "status"],
    registry=registry,
)

# Database operation duration
DB_OPERATION_DURATION_SECONDS = Histogram(
    "memory_palace_db_operation_duration_seconds",
    "Database operation latency in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry,
)

# Database size metrics
DB_TOTAL_CHUNKS = Gauge(
    "memory_palace_db_total_chunks",
    "Total number of chunks in the vector database",
    registry=registry,
)

DB_TOTAL_DOCUMENTS = Gauge(
    "memory_palace_db_total_documents",
    "Total number of documents in the database",
    registry=registry,
)

DB_COLLECTION_SIZE_BYTES = Gauge(
    "memory_palace_db_collection_size_bytes",
    "Size of the vector collection in bytes",
    registry=registry,
)


# ============================================================================
# EMBEDDING METRICS
# ============================================================================

# Embeddings generated
EMBEDDINGS_GENERATED_TOTAL = Counter(
    "memory_palace_embeddings_generated_total",
    "Total number of embeddings generated",
    ["model"],
    registry=registry,
)

# Embedding generation duration
EMBEDDING_DURATION_SECONDS = Histogram(
    "memory_palace_embedding_duration_seconds",
    "Embedding generation latency in seconds",
    ["model"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

# Embedding batch size
EMBEDDING_BATCH_SIZE = Histogram(
    "memory_palace_embedding_batch_size",
    "Number of texts per embedding batch",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500),
    registry=registry,
)

# Embedding queue size (for async processing)
EMBEDDING_QUEUE_SIZE = Gauge(
    "memory_palace_embedding_queue_size",
    "Number of texts waiting for embedding",
    registry=registry,
)


# ============================================================================
# INGESTION METRICS
# ============================================================================

# Documents ingested
DOCUMENTS_INGESTED_TOTAL = Counter(
    "memory_palace_documents_ingested_total",
    "Total number of documents ingested",
    ["source_type", "status"],
    registry=registry,
)

# Chunks created
CHUNKS_CREATED_TOTAL = Counter(
    "memory_palace_chunks_created_total",
    "Total number of chunks created during ingestion",
    ["source_type"],
    registry=registry,
)

# Ingestion duration
INGESTION_DURATION_SECONDS = Histogram(
    "memory_palace_ingestion_duration_seconds",
    "Document ingestion latency in seconds",
    ["source_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=registry,
)

# Duplicates detected
DUPLICATES_DETECTED_TOTAL = Counter(
    "memory_palace_duplicates_detected_total",
    "Total number of duplicate documents detected",
    registry=registry,
)

# Document size
DOCUMENT_SIZE_BYTES = Histogram(
    "memory_palace_document_size_bytes",
    "Size of ingested documents in bytes",
    ["source_type"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
    registry=registry,
)


# ============================================================================
# MEMORY METRICS
# ============================================================================

# Memories by type
MEMORIES_BY_TYPE = Gauge(
    "memory_palace_memories_by_type",
    "Number of memories by type",
    ["memory_type"],
    registry=registry,
)

# Memories by importance
MEMORIES_BY_IMPORTANCE = Gauge(
    "memory_palace_memories_by_importance",
    "Number of memories by importance level",
    ["importance"],
    registry=registry,
)

# Total entities
ENTITIES_TOTAL = Gauge(
    "memory_palace_entities_total",
    "Total number of unique entities",
    ["entity_type"],
    registry=registry,
)

# Total topics
TOPICS_TOTAL = Gauge(
    "memory_palace_topics_total",
    "Total number of unique topics",
    registry=registry,
)


# ============================================================================
# LLM METRICS
# ============================================================================

# LLM API calls
LLM_API_CALLS_TOTAL = Counter(
    "memory_palace_llm_api_calls_total",
    "Total number of LLM API calls",
    ["provider", "model", "status"],
    registry=registry,
)

# LLM API latency
LLM_API_DURATION_SECONDS = Histogram(
    "memory_palace_llm_api_duration_seconds",
    "LLM API call latency in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0),
    registry=registry,
)

# LLM tokens used
LLM_TOKENS_USED_TOTAL = Counter(
    "memory_palace_llm_tokens_used_total",
    "Total number of tokens used",
    ["provider", "model", "token_type"],
    registry=registry,
)


# ============================================================================
# SYSTEM METRICS
# ============================================================================

# Process uptime
PROCESS_START_TIME = Gauge(
    "memory_palace_process_start_time_seconds",
    "Unix timestamp when the process started",
    registry=registry,
)

# Component health
COMPONENT_HEALTH = Gauge(
    "memory_palace_component_health",
    "Health status of components (1=healthy, 0=unhealthy)",
    ["component"],
    registry=registry,
)


# ============================================================================
# ERROR METRICS
# ============================================================================

# Total errors
ERRORS_TOTAL = Counter(
    "memory_palace_errors_total",
    "Total number of errors",
    ["component", "error_type"],
    registry=registry,
)


# ============================================================================
# METRICS MANAGER
# ============================================================================

class MetricsManager:
    """
    Centralized manager for all Memory Palace metrics.

    Provides convenient methods for recording metrics and
    handles initialization and cleanup.
    """

    _instance: Optional["MetricsManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "MetricsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._start_time = time.time()
            PROCESS_START_TIME.set(self._start_time)
            MetricsManager._initialized = True

    @property
    def registry(self) -> CollectorRegistry:
        """Get the metrics registry."""
        return registry

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output."""
        return generate_latest(registry)

    @property
    def content_type(self) -> str:
        """Get the Prometheus content type."""
        return CONTENT_TYPE_LATEST

    # HTTP metrics
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0,
    ):
        """Record an HTTP request."""
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)
        if request_size > 0:
            HTTP_REQUEST_SIZE_BYTES.labels(
                method=method,
                endpoint=endpoint,
            ).observe(request_size)
        if response_size > 0:
            HTTP_RESPONSE_SIZE_BYTES.labels(
                method=method,
                endpoint=endpoint,
            ).observe(response_size)

    # MCP metrics
    def record_mcp_tool_call(
        self,
        tool_name: str,
        status: str,
        duration: float,
    ):
        """Record an MCP tool call."""
        MCP_TOOL_CALLS_TOTAL.labels(
            tool_name=tool_name,
            status=status,
        ).inc()
        MCP_TOOL_DURATION_SECONDS.labels(
            tool_name=tool_name,
        ).observe(duration)

    def set_mcp_connections(self, transport: str, count: int):
        """Set the number of active MCP connections."""
        MCP_ACTIVE_CONNECTIONS.labels(transport=transport).set(count)

    # Query metrics
    def record_query(
        self,
        query_type: str,
        status: str,
        duration: float,
        results_count: int = 0,
    ):
        """Record a query execution."""
        QUERIES_TOTAL.labels(
            query_type=query_type,
            status=status,
        ).inc()
        QUERY_DURATION_SECONDS.labels(
            query_type=query_type,
        ).observe(duration)
        QUERY_RESULTS_COUNT.labels(
            query_type=query_type,
        ).observe(results_count)

    def record_cache_hit(self):
        """Record a query cache hit."""
        QUERY_CACHE_HITS.inc()

    def record_cache_miss(self):
        """Record a query cache miss."""
        QUERY_CACHE_MISSES.inc()

    # Database metrics
    def record_db_operation(
        self,
        operation: str,
        status: str,
        duration: float,
    ):
        """Record a database operation."""
        DB_OPERATIONS_TOTAL.labels(
            operation=operation,
            status=status,
        ).inc()
        DB_OPERATION_DURATION_SECONDS.labels(
            operation=operation,
        ).observe(duration)

    def update_db_stats(
        self,
        total_chunks: int,
        total_documents: int,
        collection_size_bytes: int = 0,
    ):
        """Update database size metrics."""
        DB_TOTAL_CHUNKS.set(total_chunks)
        DB_TOTAL_DOCUMENTS.set(total_documents)
        if collection_size_bytes > 0:
            DB_COLLECTION_SIZE_BYTES.set(collection_size_bytes)

    # Embedding metrics
    def record_embedding(
        self,
        model: str,
        duration: float,
        batch_size: int = 1,
    ):
        """Record embedding generation."""
        EMBEDDINGS_GENERATED_TOTAL.labels(model=model).inc(batch_size)
        EMBEDDING_DURATION_SECONDS.labels(model=model).observe(duration)
        EMBEDDING_BATCH_SIZE.observe(batch_size)

    def set_embedding_queue_size(self, size: int):
        """Set the embedding queue size."""
        EMBEDDING_QUEUE_SIZE.set(size)

    # Ingestion metrics
    def record_ingestion(
        self,
        source_type: str,
        status: str,
        duration: float,
        chunks_created: int = 0,
        document_size_bytes: int = 0,
    ):
        """Record a document ingestion."""
        DOCUMENTS_INGESTED_TOTAL.labels(
            source_type=source_type,
            status=status,
        ).inc()
        INGESTION_DURATION_SECONDS.labels(
            source_type=source_type,
        ).observe(duration)
        if chunks_created > 0:
            CHUNKS_CREATED_TOTAL.labels(
                source_type=source_type,
            ).inc(chunks_created)
        if document_size_bytes > 0:
            DOCUMENT_SIZE_BYTES.labels(
                source_type=source_type,
            ).observe(document_size_bytes)

    def record_duplicate(self):
        """Record a duplicate detection."""
        DUPLICATES_DETECTED_TOTAL.inc()

    # Memory metrics
    def update_memory_stats(
        self,
        memories_by_type: dict[str, int],
        memories_by_importance: dict[str, int],
        entities_by_type: dict[str, int],
        topics_count: int,
    ):
        """Update memory statistics."""
        for memory_type, count in memories_by_type.items():
            MEMORIES_BY_TYPE.labels(memory_type=memory_type).set(count)
        for importance, count in memories_by_importance.items():
            MEMORIES_BY_IMPORTANCE.labels(importance=importance).set(count)
        for entity_type, count in entities_by_type.items():
            ENTITIES_TOTAL.labels(entity_type=entity_type).set(count)
        TOPICS_TOTAL.set(topics_count)

    # LLM metrics
    def record_llm_call(
        self,
        provider: str,
        model: str,
        status: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Record an LLM API call."""
        LLM_API_CALLS_TOTAL.labels(
            provider=provider,
            model=model,
            status=status,
        ).inc()
        LLM_API_DURATION_SECONDS.labels(
            provider=provider,
            model=model,
        ).observe(duration)
        if input_tokens > 0:
            LLM_TOKENS_USED_TOTAL.labels(
                provider=provider,
                model=model,
                token_type="input",
            ).inc(input_tokens)
        if output_tokens > 0:
            LLM_TOKENS_USED_TOTAL.labels(
                provider=provider,
                model=model,
                token_type="output",
            ).inc(output_tokens)

    # Health metrics
    def set_component_health(self, component: str, healthy: bool):
        """Set the health status of a component."""
        COMPONENT_HEALTH.labels(component=component).set(1 if healthy else 0)

    # Error metrics
    def record_error(self, component: str, error_type: str):
        """Record an error."""
        ERRORS_TOTAL.labels(
            component=component,
            error_type=error_type,
        ).inc()


# Singleton instance
_metrics_manager: Optional[MetricsManager] = None


def get_metrics_manager() -> MetricsManager:
    """Get the global MetricsManager instance."""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager()
    return _metrics_manager


# ============================================================================
# DECORATORS AND CONTEXT MANAGERS
# ============================================================================

def track_request_time(method: str, endpoint: str):
    """
    Decorator to track HTTP request time.

    Usage:
        @track_request_time("POST", "/query")
        async def query_memories(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = get_metrics_manager()
            HTTP_ACTIVE_CONNECTIONS.inc()
            start_time = time.time()
            status_code = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                HTTP_ACTIVE_CONNECTIONS.dec()
                metrics.record_http_request(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration,
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = get_metrics_manager()
            HTTP_ACTIVE_CONNECTIONS.inc()
            start_time = time.time()
            status_code = 200
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                HTTP_ACTIVE_CONNECTIONS.dec()
                metrics.record_http_request(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration,
                )

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_operation_time(operation_type: str, operation_name: str):
    """
    Decorator to track operation time for any component.

    Usage:
        @track_operation_time("db", "search")
        async def search(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics = get_metrics_manager()
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                if operation_type == "db":
                    metrics.record_db_operation(operation_name, status, duration)
                elif operation_type == "query":
                    metrics.record_query(operation_name, status, duration)
                elif operation_type == "mcp":
                    metrics.record_mcp_tool_call(operation_name, status, duration)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics = get_metrics_manager()
            start_time = time.time()
            status = "success"
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time
                if operation_type == "db":
                    metrics.record_db_operation(operation_name, status, duration)
                elif operation_type == "query":
                    metrics.record_query(operation_name, status, duration)
                elif operation_type == "mcp":
                    metrics.record_mcp_tool_call(operation_name, status, duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def track_time(metric_callback: Callable[[float], None]):
    """
    Context manager to track execution time.

    Usage:
        with track_time(lambda d: metrics.record_embedding("model", d)):
            # do work
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metric_callback(duration)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def increment_request_counter(method: str, endpoint: str, status_code: int):
    """Increment the HTTP request counter."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()


def increment_error_counter(component: str, error_type: str):
    """Increment the error counter."""
    ERRORS_TOTAL.labels(
        component=component,
        error_type=error_type,
    ).inc()


def increment_memory_counter(source_type: str, status: str):
    """Increment the documents ingested counter."""
    DOCUMENTS_INGESTED_TOTAL.labels(
        source_type=source_type,
        status=status,
    ).inc()


def set_active_connections(count: int):
    """Set the number of active HTTP connections."""
    HTTP_ACTIVE_CONNECTIONS.set(count)


def set_database_size(chunks: int, documents: int):
    """Set database size metrics."""
    DB_TOTAL_CHUNKS.set(chunks)
    DB_TOTAL_DOCUMENTS.set(documents)


def set_embedding_queue_size(size: int):
    """Set the embedding queue size."""
    EMBEDDING_QUEUE_SIZE.set(size)


def observe_query_latency(query_type: str, duration: float):
    """Observe a query latency."""
    QUERY_DURATION_SECONDS.labels(query_type=query_type).observe(duration)


def observe_embedding_latency(model: str, duration: float):
    """Observe embedding generation latency."""
    EMBEDDING_DURATION_SECONDS.labels(model=model).observe(duration)


def observe_ingestion_time(source_type: str, duration: float):
    """Observe document ingestion time."""
    INGESTION_DURATION_SECONDS.labels(source_type=source_type).observe(duration)
