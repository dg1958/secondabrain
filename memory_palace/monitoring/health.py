"""
Health Check Module for Memory Palace.

Provides comprehensive health checks for all system components
with Prometheus-compatible metrics.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .metrics import get_metrics_manager, COMPONENT_HEALTH


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    version: str
    uptime_seconds: float
    components: list[ComponentHealth]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    "details": c.details,
                    "last_check": c.last_check.isoformat(),
                }
                for c in self.components
            ],
        }


class HealthChecker:
    """
    Comprehensive health checker for Memory Palace.

    Checks all system components and reports their health status
    to Prometheus metrics.
    """

    def __init__(self, version: str = "1.0.0"):
        self.version = version
        self._start_time = time.time()
        self._checks: dict[str, Callable] = {}
        self._metrics = get_metrics_manager()

        # Register default health checks
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks for all components."""
        self.register_check("vector_db", self._check_vector_db)
        self.register_check("embedding_service", self._check_embedding_service)
        self.register_check("metadata_db", self._check_metadata_db)
        self.register_check("llm_service", self._check_llm_service)

    def register_check(self, name: str, check_fn: Callable):
        """Register a health check function."""
        self._checks[name] = check_fn

    async def check_health(self) -> SystemHealth:
        """
        Perform all health checks and return system health status.

        Returns:
            SystemHealth object with overall status and component details
        """
        component_results = []

        # Run all checks concurrently
        check_tasks = []
        for name, check_fn in self._checks.items():
            check_tasks.append(self._run_check(name, check_fn))

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                component_results.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                ))
            else:
                component_results.append(result)

        # Update Prometheus metrics
        for component in component_results:
            healthy = component.status == HealthStatus.HEALTHY
            COMPONENT_HEALTH.labels(component=component.name).set(1 if healthy else 0)

        # Determine overall status
        overall_status = self._determine_overall_status(component_results)

        return SystemHealth(
            status=overall_status,
            version=self.version,
            uptime_seconds=time.time() - self._start_time,
            components=component_results,
        )

    async def _run_check(self, name: str, check_fn: Callable) -> ComponentHealth:
        """Run a single health check with timing."""
        start_time = time.time()

        try:
            # Handle both sync and async check functions
            if asyncio.iscoroutinefunction(check_fn):
                result = await asyncio.wait_for(check_fn(), timeout=10.0)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, check_fn
                )

            latency_ms = (time.time() - start_time) * 1000

            if isinstance(result, ComponentHealth):
                result.latency_ms = latency_ms
                result.last_check = datetime.utcnow()
                return result

            # If check returns a boolean
            if isinstance(result, bool):
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    message="" if result else "Check failed",
                    latency_ms=latency_ms,
                )

            # If check returns a dict
            if isinstance(result, dict):
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=result.get("message", ""),
                    latency_ms=latency_ms,
                    details=result,
                )

            return ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
            )

        except asyncio.TimeoutError:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="Health check timed out",
                latency_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    def _determine_overall_status(
        self, components: list[ComponentHealth]
    ) -> HealthStatus:
        """Determine overall system status based on component health."""
        if not components:
            return HealthStatus.UNKNOWN

        # Critical components that must be healthy
        critical_components = {"vector_db", "embedding_service"}

        unhealthy_count = 0
        critical_unhealthy = False

        for component in components:
            if component.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
                if component.name in critical_components:
                    critical_unhealthy = True

        if critical_unhealthy:
            return HealthStatus.UNHEALTHY

        if unhealthy_count > 0:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    # ========================================================================
    # Default Health Check Implementations
    # ========================================================================

    async def _check_vector_db(self) -> ComponentHealth:
        """Check vector database (ChromaDB) health."""
        try:
            from ..storage.vector_db import get_vector_db

            db = get_vector_db()

            if not db.is_available:
                return ComponentHealth(
                    name="vector_db",
                    status=HealthStatus.UNHEALTHY,
                    message="Vector database not available",
                )

            # Get stats as a health indicator
            stats = db.get_stats()

            return ComponentHealth(
                name="vector_db",
                status=HealthStatus.HEALTHY,
                message=f"ChromaDB operational with {stats.get('total_chunks', 0)} chunks",
                details={
                    "total_chunks": stats.get("total_chunks", 0),
                    "total_documents": stats.get("total_documents", 0),
                    "collection": stats.get("collection_name", "unknown"),
                },
            )

        except ImportError:
            return ComponentHealth(
                name="vector_db",
                status=HealthStatus.UNKNOWN,
                message="Vector DB module not available",
            )

        except Exception as e:
            return ComponentHealth(
                name="vector_db",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
            )

    async def _check_embedding_service(self) -> ComponentHealth:
        """Check embedding service health."""
        try:
            from ..storage.embedding_service import get_embedding_service

            service = get_embedding_service()

            if not service.is_available:
                return ComponentHealth(
                    name="embedding_service",
                    status=HealthStatus.UNHEALTHY,
                    message="Embedding service not available",
                )

            return ComponentHealth(
                name="embedding_service",
                status=HealthStatus.HEALTHY,
                message=f"Using model: {service.model_name}",
                details={
                    "model": service.model_name,
                    "dimension": service.embedding_dimension,
                },
            )

        except ImportError:
            return ComponentHealth(
                name="embedding_service",
                status=HealthStatus.UNKNOWN,
                message="Embedding service module not available",
            )

        except Exception as e:
            return ComponentHealth(
                name="embedding_service",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
            )

    async def _check_metadata_db(self) -> ComponentHealth:
        """Check metadata database (SQLite) health."""
        try:
            from ..core.metadata_store import get_metadata_store

            store = get_metadata_store()

            # Try a simple operation
            stats = await store.get_stats()

            return ComponentHealth(
                name="metadata_db",
                status=HealthStatus.HEALTHY,
                message="SQLite metadata store operational",
                details={
                    "total_memories": stats.get("total_memories", 0),
                    "total_entities": stats.get("total_entities", 0),
                    "total_topics": stats.get("total_topics", 0),
                },
            )

        except ImportError:
            return ComponentHealth(
                name="metadata_db",
                status=HealthStatus.UNKNOWN,
                message="Metadata store module not available",
            )

        except Exception as e:
            return ComponentHealth(
                name="metadata_db",
                status=HealthStatus.DEGRADED,
                message=f"Warning: {str(e)}",
            )

    async def _check_llm_service(self) -> ComponentHealth:
        """Check LLM service (Anthropic) availability."""
        try:
            from ..config import get_settings

            settings = get_settings()

            if not settings.anthropic_api_key:
                return ComponentHealth(
                    name="llm_service",
                    status=HealthStatus.DEGRADED,
                    message="Anthropic API key not configured",
                    details={"configured": False},
                )

            # Just check if key is present - don't make an actual API call
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.HEALTHY,
                message="Anthropic API key configured",
                details={"configured": True},
            )

        except ImportError:
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.UNKNOWN,
                message="Config module not available",
            )

        except Exception as e:
            return ComponentHealth(
                name="llm_service",
                status=HealthStatus.DEGRADED,
                message=f"Warning: {str(e)}",
            )


# Singleton instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker(version: str = "1.0.0") -> HealthChecker:
    """Get the global HealthChecker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(version=version)
    return _health_checker
