"""
Configuration management for Memory Palace.

Loads settings from YAML config file and environment variables.
"""

import os
import logging
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StorageSettings(BaseModel):
    """Storage path settings."""
    data_dir: str = "./data"
    vector_db_path: str = "${data_dir}/chromadb"
    metadata_db_path: str = "${data_dir}/metadata.db"


class VectorDBSettings(BaseModel):
    """Vector database settings."""
    collection_name: str = "memory_palace"
    embedding_model: str = "all-MiniLM-L6-v2"
    distance_metric: str = "cosine"


class SearchSettings(BaseModel):
    """Search configuration."""
    default_limit: int = 10
    max_limit: int = 100
    min_relevance_score: float = 0.0
    hybrid_search: bool = True
    semantic_weight: float = 0.7


class ExtractionSettings(BaseModel):
    """Metadata extraction settings."""
    spacy_model: str = "en_core_web_sm"
    entity_types: list[str] = Field(default_factory=lambda: [
        "PERSON", "ORG", "GPE", "LOCATION", "PRODUCT",
        "EVENT", "WORK_OF_ART", "LAW", "DATE"
    ])
    enable_sentiment: bool = True
    enable_topics: bool = True
    max_topics: int = 5


class MemorySettings(BaseModel):
    """Memory storage settings."""
    default_importance: str = "medium"
    types: list[str] = Field(default_factory=lambda: [
        "fact", "preference", "decision", "event",
        "insight", "conversation_summary", "note"
    ])
    auto_summarize: bool = True
    summarize_threshold: int = 1000


class HTTPSettings(BaseModel):
    """HTTP server settings."""
    host: str = "127.0.0.1"
    port: int = 8765
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000"
    ])


class LoggingSettings(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


class Settings(BaseModel):
    """Main settings container."""
    storage: StorageSettings = Field(default_factory=StorageSettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    http: HTTPSettings = Field(default_factory=HTTPSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def resolve_paths(self) -> "Settings":
        """Resolve path variables like ${data_dir}."""
        data_dir = os.environ.get("MEMORY_PALACE_DATA", self.storage.data_dir)
        data_dir = os.path.abspath(data_dir)

        self.storage.data_dir = data_dir
        self.storage.vector_db_path = self.storage.vector_db_path.replace(
            "${data_dir}", data_dir
        )
        self.storage.metadata_db_path = self.storage.metadata_db_path.replace(
            "${data_dir}", data_dir
        )

        return self

    def ensure_directories(self) -> None:
        """Create data directories if they don't exist."""
        Path(self.storage.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.storage.vector_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.storage.metadata_db_path).parent.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[str] = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = os.environ.get("MEMORY_PALACE_CONFIG")

    if config_path is None:
        # Look for default config
        default_paths = [
            Path(__file__).parent / "default_settings.yaml",
            Path.cwd() / "config" / "settings.yaml",
            Path.cwd() / "settings.yaml",
        ]
        for path in default_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path and Path(config_path).exists():
        logger.info(f"Loading config from {config_path}")
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}

    logger.info("Using default configuration")
    return {}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    config_data = load_config()
    settings = Settings(**config_data)
    settings = settings.resolve_paths()
    settings.ensure_directories()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper()),
        format=settings.logging.format
    )
    if settings.logging.file:
        handler = logging.FileHandler(settings.logging.file)
        handler.setFormatter(logging.Formatter(settings.logging.format))
        logging.getLogger().addHandler(handler)

    return settings


def reset_settings() -> None:
    """Clear cached settings (useful for testing)."""
    get_settings.cache_clear()
