"""
FastAPI REST API for Memory Palace.

This module provides HTTP endpoints for:
- Document ingestion
- Memory queries
- Timeline generation
- Database management
- Fireflies sync
- Prometheus metrics (at /metrics)
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from loguru import logger

from api.schemas import (
    BatchIngestRequest,
    BatchIngestResponse,
    DeleteRequest,
    DeleteResponse,
    ExportRequest,
    ExportResponse,
    FirefliesSyncRequest,
    FirefliesSyncResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponseSchema,
    QueryResultSchema,
    StatsResponse,
    TimelineEntry,
    TimelineRequest,
    TimelineResponse,
)
from api.fireflies_sync import FirefliesSync, get_fireflies_sync
from config import settings
from config.schema import QueryFilter, SourceType
from ingestion.batch_importer import BatchImporter, get_batch_importer
from query.query_engine import QueryEngine, get_query_engine
from query.result_synthesizer import get_result_synthesizer
from query.temporal_filter import TemporalFilter
from storage.vector_db import VectorDB, get_vector_db

# Metrics imports (conditional)
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "false").lower() == "true"

if METRICS_ENABLED:
    try:
        from monitoring.middleware import setup_prometheus_middleware
        from monitoring.health import get_health_checker, HealthStatus
        from monitoring.metrics import get_metrics_manager
    except ImportError:
        METRICS_ENABLED = False
        logger.warning("Monitoring module not available, metrics disabled")

# API version
API_VERSION = "1.0.0"

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Memory Palace API",
        description="Personal AI Memory Management System with Prometheus Metrics",
        version=API_VERSION,
        docs_url="/docs" if settings.get("api", "docs_enabled", default=True) else None,
        redoc_url="/redoc" if settings.get("api", "docs_enabled", default=True) else None,
    )

    # Configure CORS
    cors_origins = settings.get("api", "cors_origins", default=["*"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Prometheus metrics middleware if enabled
    if METRICS_ENABLED:
        setup_prometheus_middleware(
            app,
            app_name="memory_palace",
            metrics_path="/metrics",
        )
        logger.info("Prometheus metrics enabled at /metrics")

    return app


# Create app instance
app = create_app()


async def verify_api_key(api_key: str = Security(api_key_header)) -> Optional[str]:
    """
    Verify API key if authentication is enabled.

    Args:
        api_key: API key from header

    Returns:
        API key if valid

    Raises:
        HTTPException: If API key is invalid
    """
    configured_key = settings.get("api", "api_key", default="")

    # If no key configured, skip authentication
    if not configured_key:
        return None

    if api_key != configured_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    return api_key


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic health info."""
    return await health_check()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns service status and component availability.
    """
    try:
        db = get_vector_db()
        db_available = db.is_available

        from storage.embedding_service import get_embedding_service
        embedding = get_embedding_service()
        embedding_available = embedding.is_available

        engine = get_query_engine(settings.anthropic_api_key)
        llm_available = engine.planner.is_available

        # Update metrics if enabled
        if METRICS_ENABLED:
            metrics = get_metrics_manager()
            metrics.set_component_health("vector_db", db_available)
            metrics.set_component_health("embedding_service", embedding_available)
            metrics.set_component_health("llm_service", llm_available)

        return HealthResponse(
            status="healthy",
            version=API_VERSION,
            database_available=db_available,
            embedding_available=embedding_available,
            llm_available=llm_available,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            version=API_VERSION,
            database_available=False,
            embedding_available=False,
            llm_available=False,
        )


@app.get("/stats", response_model=StatsResponse)
async def get_stats(api_key: str = Security(api_key_header)):
    """
    Get database statistics.

    Returns information about stored memories and system status.
    """
    await verify_api_key(api_key)

    try:
        db = get_vector_db()
        stats = db.get_stats()

        from storage.embedding_service import get_embedding_service
        embedding = get_embedding_service()

        engine = get_query_engine(settings.anthropic_api_key)

        return StatsResponse(
            total_chunks=stats.get("total_chunks", 0),
            total_documents=stats.get("total_documents", 0),
            collection_name=stats.get("collection_name", "unknown"),
            embedding_model=embedding.model_name,
            llm_available=engine.planner.is_available,
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    api_key: str = Security(api_key_header),
):
    """
    Ingest a document into the memory system.

    Processes text content, extracts metadata, generates embeddings,
    and stores in the vector database.
    """
    await verify_api_key(api_key)

    try:
        importer = get_batch_importer()

        result = importer.import_text(
            text=request.content,
            timestamp=request.timestamp,
            source=SourceType.API,
            participants=request.participants,
            custom_tags=request.custom_tags,
            extract_metadata=request.extract_metadata,
        )

        return IngestResponse(
            success=result.success,
            doc_id=result.doc_id,
            chunks_created=result.chunks_created,
            message="Document ingested successfully" if result.success else result.error_message,
            processing_time_ms=result.processing_time_ms,
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponseSchema)
async def query_memories(
    request: QueryRequest,
    api_key: str = Security(api_key_header),
):
    """
    Query the memory database.

    Supports natural language queries with optional filters.
    Returns relevant memories and optional LLM synthesis.
    """
    await verify_api_key(api_key)

    try:
        engine = get_query_engine(settings.anthropic_api_key)

        # Build filters
        filters = QueryFilter(
            start_date=request.start_date,
            end_date=request.end_date,
            participants=request.participants,
            topics=request.topics,
            custom_tags=request.custom_tags,
        )

        # Execute query
        response = engine.query(
            query_text=request.query,
            top_k=request.top_k,
            filters=filters,
            use_llm_interpretation=request.use_llm,
            synthesize_results=request.synthesize,
        )

        # Convert results to schema
        results = [
            QueryResultSchema(
                chunk_id=r.chunk_id,
                text=r.text,
                score=r.score,
                timestamp=r.metadata.timestamp,
                participants=r.metadata.participants,
                topics=r.metadata.topics,
                source=r.metadata.source.value,
            )
            for r in response.results
        ]

        return QueryResponseSchema(
            query=response.query,
            total_results=response.total_results,
            results=results,
            synthesis=response.synthesis,
            processing_time_ms=response.processing_time_ms,
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/timeline", response_model=TimelineResponse)
async def get_timeline(
    request: TimelineRequest,
    api_key: str = Security(api_key_header),
):
    """
    Generate a chronological timeline for a topic.

    Returns memories sorted by date for reconstructing
    the evolution of thoughts on a subject.
    """
    await verify_api_key(api_key)

    try:
        engine = get_query_engine(settings.anthropic_api_key)
        temporal = TemporalFilter()

        # Get timeline results
        results = engine.get_timeline(request.query, top_k=request.top_k)

        # Filter by date range if specified
        if request.start_date or request.end_date:
            results = [
                r for r in results
                if (not request.start_date or r.metadata.timestamp >= request.start_date)
                and (not request.end_date or r.metadata.timestamp <= request.end_date)
            ]

        # Convert to entries
        entries = [
            TimelineEntry(
                timestamp=r.metadata.timestamp,
                preview=r.text[:200] + "..." if len(r.text) > 200 else r.text,
                participants=r.metadata.participants,
                topics=r.metadata.topics,
            )
            for r in results
        ]

        # Determine date range
        if entries:
            start = min(e.timestamp for e in entries)
            end = max(e.timestamp for e in entries)
            date_range = temporal.format_range(start, end)
        else:
            date_range = "No data"

        return TimelineResponse(
            query=request.query,
            total_entries=len(entries),
            date_range=date_range,
            entries=entries,
        )

    except Exception as e:
        logger.error(f"Timeline generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-ingest", response_model=BatchIngestResponse)
async def batch_ingest(
    request: BatchIngestRequest,
    api_key: str = Security(api_key_header),
):
    """
    Batch import documents from a directory.

    Processes all matching files in the specified directory.
    """
    await verify_api_key(api_key)

    try:
        importer = get_batch_importer()

        results = importer.import_directory(
            directory=request.directory,
            patterns=request.patterns,
            recursive=request.recursive,
            custom_tags=request.custom_tags,
        )

        successful = sum(1 for r in results.values() if r.success and not r.duplicate)
        duplicates = sum(1 for r in results.values() if r.duplicate)
        failed = sum(1 for r in results.values() if not r.success)

        errors = [
            f"{path}: {r.error_message}"
            for path, r in results.items()
            if not r.success and r.error_message
        ]

        return BatchIngestResponse(
            total_files=len(results),
            successful=successful,
            failed=failed,
            duplicates=duplicates,
            errors=errors[:10],  # Limit error messages
        )

    except Exception as e:
        logger.error(f"Batch ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export", response_model=ExportResponse)
async def export_results(
    request: ExportRequest,
    api_key: str = Security(api_key_header),
):
    """
    Export query results in various formats.

    Supports Markdown and JSON export formats.
    """
    await verify_api_key(api_key)

    try:
        engine = get_query_engine(settings.anthropic_api_key)
        synthesizer = get_result_synthesizer(settings.anthropic_api_key)

        # Execute query
        response = engine.query(
            query_text=request.query,
            top_k=request.top_k,
            synthesize_results=False,
        )

        # Export in requested format
        if request.format.lower() == "json":
            content = synthesizer.export_json(
                request.query,
                response.results,
                include_synthesis=request.include_synthesis,
            )
            filename = f"memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            content = synthesizer.export_markdown(
                request.query,
                response.results,
                include_synthesis=request.include_synthesis,
            )
            filename = f"memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        return ExportResponse(
            format=request.format,
            content=content,
            filename=filename,
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fireflies/sync", response_model=FirefliesSyncResponse)
async def sync_fireflies(
    request: FirefliesSyncRequest,
    api_key: str = Security(api_key_header),
):
    """
    Sync transcripts from Fireflies.ai.

    Fetches new transcripts and imports them into Memory Palace.
    """
    await verify_api_key(api_key)

    try:
        fireflies = get_fireflies_sync(settings.fireflies_api_key)

        if not fireflies.is_configured:
            return FirefliesSyncResponse(
                success=False,
                transcripts_synced=0,
                message="Fireflies API key not configured",
            )

        result = await fireflies.sync_transcripts(
            sync_all=request.sync_all,
            since_date=request.since_date,
        )

        return FirefliesSyncResponse(
            success=result["success"],
            transcripts_synced=result["transcripts_synced"],
            message=result["message"],
        )

    except Exception as e:
        logger.error(f"Fireflies sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", response_model=DeleteResponse)
async def delete_memories(
    request: DeleteRequest,
    api_key: str = Security(api_key_header),
):
    """
    Delete memories from the database.

    Can delete by document ID or specific chunk IDs.
    """
    await verify_api_key(api_key)

    try:
        db = get_vector_db()
        deleted = 0

        if request.doc_id:
            deleted = db.delete_by_doc_id(request.doc_id)
        elif request.chunk_ids:
            if db.delete(request.chunk_ids):
                deleted = len(request.chunk_ids)

        return DeleteResponse(
            success=deleted > 0,
            chunks_deleted=deleted,
            message=f"Deleted {deleted} chunks",
        )

    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear")
async def clear_database(api_key: str = Security(api_key_header)):
    """
    Clear all data from the database.

    WARNING: This operation is irreversible!
    """
    await verify_api_key(api_key)

    try:
        db = get_vector_db()
        db.clear()

        return {"success": True, "message": "Database cleared"}

    except Exception as e:
        logger.error(f"Clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def simple_search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(default=10, ge=1, le=100),
    api_key: str = Security(api_key_header),
):
    """
    Simple search endpoint for quick queries.

    GET /search?q=your+query&top_k=10
    """
    await verify_api_key(api_key)

    request = QueryRequest(query=q, top_k=top_k, synthesize=False)
    return await query_memories(request, api_key)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
):
    """
    Run the API server.

    Args:
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload for development
    """
    import uvicorn

    uvicorn.run(
        "api.rest_api:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server()
