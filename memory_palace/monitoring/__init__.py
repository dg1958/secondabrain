"""
Memory Palace Monitoring Module.

This module provides comprehensive Prometheus metrics instrumentation
for all components of the Memory Palace system.
"""

from .metrics import (
    # Core metrics
    MetricsManager,
    get_metrics_manager,

    # Decorators
    track_request_time,
    track_operation_time,

    # Counters
    increment_request_counter,
    increment_error_counter,
    increment_memory_counter,

    # Gauges
    set_active_connections,
    set_database_size,
    set_embedding_queue_size,

    # Histograms
    observe_query_latency,
    observe_embedding_latency,
    observe_ingestion_time,
)

__all__ = [
    "MetricsManager",
    "get_metrics_manager",
    "track_request_time",
    "track_operation_time",
    "increment_request_counter",
    "increment_error_counter",
    "increment_memory_counter",
    "set_active_connections",
    "set_database_size",
    "set_embedding_queue_size",
    "observe_query_latency",
    "observe_embedding_latency",
    "observe_ingestion_time",
]
