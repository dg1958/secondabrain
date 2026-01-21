"""
FastAPI Middleware for Prometheus Metrics.

This module provides middleware for automatic request instrumentation
and a metrics endpoint for Prometheus scraping.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .metrics import (
    get_metrics_manager,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_ACTIVE_CONNECTIONS,
    HTTP_REQUEST_SIZE_BYTES,
    HTTP_RESPONSE_SIZE_BYTES,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically tracks HTTP request metrics.

    Tracks:
    - Request count by method, endpoint, and status code
    - Request duration
    - Request/response sizes
    - Active connections
    """

    def __init__(
        self,
        app: ASGIApp,
        app_name: str = "memory_palace",
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.app_name = app_name
        self.exclude_paths = exclude_paths or ["/metrics", "/health", "/"]
        self.metrics = get_metrics_manager()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics for excluded paths
        path = request.url.path
        if path in self.exclude_paths:
            return await call_next(request)

        # Normalize endpoint path (remove IDs, etc.)
        endpoint = self._normalize_path(path)
        method = request.method

        # Track active connections
        HTTP_ACTIVE_CONNECTIONS.inc()

        # Get request size
        request_size = 0
        if hasattr(request, "_body"):
            request_size = len(request._body)
        elif "content-length" in request.headers:
            try:
                request_size = int(request.headers["content-length"])
            except (ValueError, TypeError):
                pass

        # Time the request
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Get response size
            response_size = 0
            if hasattr(response, "body"):
                response_size = len(response.body)
            elif hasattr(response, "headers") and "content-length" in response.headers:
                try:
                    response_size = int(response.headers["content-length"])
                except (ValueError, TypeError):
                    pass

            # Record metrics
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

            # Decrement active connections
            HTTP_ACTIVE_CONNECTIONS.dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path by replacing dynamic segments with placeholders.

        /memories/abc123 -> /memories/{id}
        /entities/John%20Smith -> /entities/{name}
        """
        parts = path.strip("/").split("/")
        normalized_parts = []

        for i, part in enumerate(parts):
            # Check if this looks like an ID (UUID, alphanumeric, etc.)
            if self._is_id_segment(part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/" + "/".join(normalized_parts)

    def _is_id_segment(self, segment: str) -> bool:
        """Check if a path segment looks like an ID."""
        # UUID pattern
        if len(segment) == 36 and segment.count("-") == 4:
            return True

        # Hex-only strings (common IDs)
        if len(segment) >= 8 and all(c in "0123456789abcdef" for c in segment.lower()):
            return True

        # Pure numeric
        if segment.isdigit() and len(segment) >= 4:
            return True

        return False


def setup_metrics_endpoint(app: FastAPI, path: str = "/metrics"):
    """
    Add a /metrics endpoint to a FastAPI app for Prometheus scraping.

    Usage:
        app = FastAPI()
        setup_metrics_endpoint(app)
    """
    metrics = get_metrics_manager()

    @app.get(path, include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus metrics endpoint."""
        return Response(
            content=metrics.get_metrics(),
            media_type=metrics.content_type,
        )


def setup_prometheus_middleware(
    app: FastAPI,
    app_name: str = "memory_palace",
    metrics_path: str = "/metrics",
    exclude_paths: list[str] | None = None,
):
    """
    Set up Prometheus metrics middleware and endpoint for a FastAPI app.

    This is a convenience function that adds both the middleware and
    the metrics endpoint.

    Args:
        app: FastAPI application
        app_name: Application name for metrics labels
        metrics_path: Path for the metrics endpoint
        exclude_paths: Paths to exclude from request metrics

    Usage:
        app = FastAPI()
        setup_prometheus_middleware(app)
    """
    # Default excludes
    if exclude_paths is None:
        exclude_paths = [metrics_path, "/health", "/", "/docs", "/redoc", "/openapi.json"]

    # Add middleware
    app.add_middleware(
        PrometheusMiddleware,
        app_name=app_name,
        exclude_paths=exclude_paths,
    )

    # Add metrics endpoint
    setup_metrics_endpoint(app, metrics_path)


class TimedRoute(APIRoute):
    """
    Custom APIRoute that tracks request timing.

    Alternative to middleware for more granular control.

    Usage:
        app = FastAPI()
        app.router.route_class = TimedRoute
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        metrics = get_metrics_manager()

        async def custom_route_handler(request: Request) -> Response:
            start_time = time.time()
            HTTP_ACTIVE_CONNECTIONS.inc()

            try:
                response = await original_route_handler(request)
                status_code = response.status_code
            except Exception as e:
                status_code = 500
                raise
            finally:
                duration = time.time() - start_time
                HTTP_ACTIVE_CONNECTIONS.dec()

                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=str(status_code),
                ).inc()

                HTTP_REQUEST_DURATION_SECONDS.labels(
                    method=request.method,
                    endpoint=request.url.path,
                ).observe(duration)

            return response

        return custom_route_handler
