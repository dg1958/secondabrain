"""
API module for Memory Palace.

This module provides:
- FastAPI REST endpoints
- Fireflies.ai integration
- Request/response schemas
"""

from .rest_api import create_app, app
from .fireflies_sync import FirefliesSync
from .schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponseSchema,
    HealthResponse,
)

__all__ = [
    "create_app",
    "app",
    "FirefliesSync",
    "IngestRequest",
    "IngestResponse",
    "QueryRequest",
    "QueryResponseSchema",
    "HealthResponse",
]
