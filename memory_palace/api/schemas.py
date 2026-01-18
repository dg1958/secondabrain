"""
API request and response schemas for Memory Palace.

This module defines Pydantic models for API validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request schema for document ingestion."""

    content: str = Field(
        description="Text content to ingest"
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp for the content"
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="Participants in the conversation"
    )
    topics: Optional[List[str]] = Field(
        default=None,
        description="Topics/tags for the content"
    )
    custom_tags: Optional[List[str]] = Field(
        default=None,
        description="Custom tags"
    )
    source: Optional[str] = Field(
        default="api",
        description="Source identifier"
    )
    extract_metadata: bool = Field(
        default=True,
        description="Whether to extract NER/sentiment/topics"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Meeting transcript about Q4 planning...",
                "timestamp": "2024-01-15T10:00:00",
                "participants": ["Alice", "Bob"],
                "topics": ["planning", "Q4"],
                "source": "api",
            }
        }


class IngestResponse(BaseModel):
    """Response schema for document ingestion."""

    success: bool = Field(
        description="Whether ingestion succeeded"
    )
    doc_id: str = Field(
        description="Document ID"
    )
    chunks_created: int = Field(
        description="Number of chunks created"
    )
    message: str = Field(
        description="Status message"
    )
    processing_time_ms: float = Field(
        description="Processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "doc_id": "abc123",
                "chunks_created": 5,
                "message": "Document ingested successfully",
                "processing_time_ms": 150.5,
            }
        }


class QueryRequest(BaseModel):
    """Request schema for memory queries."""

    query: str = Field(
        description="Natural language query"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return"
    )
    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter results after this date"
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter results before this date"
    )
    participants: Optional[List[str]] = Field(
        default=None,
        description="Filter by participants"
    )
    topics: Optional[List[str]] = Field(
        default=None,
        description="Filter by topics"
    )
    custom_tags: Optional[List[str]] = Field(
        default=None,
        description="Filter by custom tags"
    )
    synthesize: bool = Field(
        default=True,
        description="Generate synthesis of results"
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM for query interpretation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What did I discuss about AI safety last month?",
                "top_k": 10,
                "synthesize": True,
            }
        }


class QueryResultSchema(BaseModel):
    """Schema for a single query result."""

    chunk_id: str = Field(
        description="Chunk identifier"
    )
    text: str = Field(
        description="Chunk text content"
    )
    score: float = Field(
        description="Relevance score"
    )
    timestamp: datetime = Field(
        description="Memory timestamp"
    )
    participants: List[str] = Field(
        default_factory=list,
        description="Participants"
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Topics"
    )
    source: str = Field(
        description="Source type"
    )


class QueryResponseSchema(BaseModel):
    """Response schema for memory queries."""

    query: str = Field(
        description="Original query"
    )
    total_results: int = Field(
        description="Total number of results"
    )
    results: List[QueryResultSchema] = Field(
        description="Query results"
    )
    synthesis: Optional[str] = Field(
        default=None,
        description="LLM-generated synthesis"
    )
    processing_time_ms: float = Field(
        description="Processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "AI safety discussions",
                "total_results": 5,
                "results": [],
                "synthesis": "Based on your conversations...",
                "processing_time_ms": 250.0,
            }
        }


class TimelineRequest(BaseModel):
    """Request schema for timeline generation."""

    query: str = Field(
        description="Topic/subject for timeline"
    )
    top_k: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum results"
    )
    start_date: Optional[datetime] = Field(
        default=None,
        description="Timeline start date"
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Timeline end date"
    )


class TimelineEntry(BaseModel):
    """Schema for a timeline entry."""

    timestamp: datetime = Field(
        description="Entry timestamp"
    )
    preview: str = Field(
        description="Content preview"
    )
    participants: List[str] = Field(
        description="Participants"
    )
    topics: List[str] = Field(
        description="Topics"
    )


class TimelineResponse(BaseModel):
    """Response schema for timeline requests."""

    query: str = Field(
        description="Original query"
    )
    total_entries: int = Field(
        description="Total timeline entries"
    )
    date_range: str = Field(
        description="Date range covered"
    )
    entries: List[TimelineEntry] = Field(
        description="Timeline entries"
    )


class BatchIngestRequest(BaseModel):
    """Request schema for batch ingestion."""

    directory: str = Field(
        description="Directory path to import from"
    )
    patterns: Optional[List[str]] = Field(
        default=None,
        description="File patterns to match"
    )
    recursive: bool = Field(
        default=True,
        description="Search subdirectories"
    )
    custom_tags: Optional[List[str]] = Field(
        default=None,
        description="Tags to apply to all files"
    )


class BatchIngestResponse(BaseModel):
    """Response schema for batch ingestion."""

    total_files: int = Field(
        description="Total files processed"
    )
    successful: int = Field(
        description="Successfully imported"
    )
    failed: int = Field(
        description="Failed imports"
    )
    duplicates: int = Field(
        description="Duplicate files skipped"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Error messages"
    )


class StatsResponse(BaseModel):
    """Response schema for database statistics."""

    total_chunks: int = Field(
        description="Total chunks stored"
    )
    total_documents: int = Field(
        description="Total unique documents"
    )
    collection_name: str = Field(
        description="Database collection name"
    )
    embedding_model: str = Field(
        description="Embedding model in use"
    )
    llm_available: bool = Field(
        description="Whether LLM features are available"
    )


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field(
        description="Service status"
    )
    version: str = Field(
        description="API version"
    )
    database_available: bool = Field(
        description="Database status"
    )
    embedding_available: bool = Field(
        description="Embedding service status"
    )
    llm_available: bool = Field(
        description="LLM service status"
    )


class ExportRequest(BaseModel):
    """Request schema for exporting query results."""

    query: str = Field(
        description="Query to export"
    )
    format: str = Field(
        default="markdown",
        description="Export format: markdown or json"
    )
    top_k: int = Field(
        default=50,
        description="Maximum results"
    )
    include_synthesis: bool = Field(
        default=True,
        description="Include LLM synthesis"
    )


class ExportResponse(BaseModel):
    """Response schema for exports."""

    format: str = Field(
        description="Export format"
    )
    content: str = Field(
        description="Exported content"
    )
    filename: str = Field(
        description="Suggested filename"
    )


class FirefliesSyncRequest(BaseModel):
    """Request schema for Fireflies sync."""

    sync_all: bool = Field(
        default=False,
        description="Sync all transcripts (not just new)"
    )
    since_date: Optional[datetime] = Field(
        default=None,
        description="Only sync transcripts after this date"
    )


class FirefliesSyncResponse(BaseModel):
    """Response schema for Fireflies sync."""

    success: bool = Field(
        description="Whether sync succeeded"
    )
    transcripts_synced: int = Field(
        description="Number of transcripts synced"
    )
    message: str = Field(
        description="Status message"
    )


class DeleteRequest(BaseModel):
    """Request schema for deletion."""

    doc_id: Optional[str] = Field(
        default=None,
        description="Document ID to delete"
    )
    chunk_ids: Optional[List[str]] = Field(
        default=None,
        description="Chunk IDs to delete"
    )


class DeleteResponse(BaseModel):
    """Response schema for deletion."""

    success: bool = Field(
        description="Whether deletion succeeded"
    )
    chunks_deleted: int = Field(
        description="Number of chunks deleted"
    )
    message: str = Field(
        description="Status message"
    )
