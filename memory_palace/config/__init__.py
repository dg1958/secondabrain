"""
Configuration module for Memory Palace.

This module handles loading and accessing configuration settings
from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from loguru import logger


class Settings:
    """
    Configuration manager for Memory Palace.

    Loads settings from YAML files with support for:
    - Default settings (settings.yaml)
    - Local overrides (settings.local.yaml)
    - Environment variable substitution
    """

    _instance: Optional["Settings"] = None
    _config: Dict[str, Any] = {}

    def __new__(cls) -> "Settings":
        """Singleton pattern to ensure one config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from YAML files."""
        config_dir = Path(__file__).parent
        default_config_path = config_dir / "settings.yaml"
        local_config_path = config_dir / "settings.local.yaml"

        # Load default config
        if default_config_path.exists():
            with open(default_config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded default config from {default_config_path}")
        else:
            logger.warning(f"Default config not found at {default_config_path}")
            self._config = {}

        # Load local overrides if present
        if local_config_path.exists():
            with open(local_config_path, "r") as f:
                local_config = yaml.safe_load(f) or {}
            self._merge_config(self._config, local_config)
            logger.debug(f"Loaded local config overrides from {local_config_path}")

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _merge_config(self, base: Dict, override: Dict) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides for sensitive values."""
        env_mappings = {
            "ANTHROPIC_API_KEY": ("anthropic", "api_key"),
            "FIREFLIES_API_KEY": ("fireflies", "api_key"),
            "MEMORY_PALACE_API_KEY": ("api", "api_key"),
        }

        for env_var, config_path in env_mappings.items():
            env_value = os.environ.get(env_var)
            if env_value:
                self._set_nested(config_path, env_value)
                logger.debug(f"Applied environment override for {env_var}")

    def _set_nested(self, path: tuple, value: Any) -> None:
        """Set a nested config value."""
        current = self._config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a config value by dot-notation path.

        Example:
            settings.get("anthropic", "api_key")
            settings.get("embeddings", "model_name", default="all-MiniLM-L6-v2")
        """
        current = self._config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access to top-level config sections."""
        return self._config.get(key, {})

    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_config()
        logger.info("Configuration reloaded")

    @property
    def anthropic_api_key(self) -> str:
        """Get Anthropic API key."""
        return self.get("anthropic", "api_key", default="")

    @property
    def fireflies_api_key(self) -> str:
        """Get Fireflies API key."""
        return self.get("fireflies", "api_key", default="")

    @property
    def embedding_model(self) -> str:
        """Get embedding model name."""
        return self.get("embeddings", "model_name", default="all-MiniLM-L6-v2")

    @property
    def chroma_persist_dir(self) -> str:
        """Get ChromaDB persistence directory."""
        return self.get("vector_db", "persist_directory", default="./data/chroma_db")

    @property
    def collection_name(self) -> str:
        """Get ChromaDB collection name."""
        return self.get("vector_db", "collection_name", default="memory_palace")


# Global settings instance
settings = Settings()

# Re-export schema classes
from .schema import (
    Document,
    DocumentFormat,
    EntityType,
    FirefliesTranscript,
    IngestionResult,
    MemoryChunk,
    MemoryMetadata,
    QueryFilter,
    QueryResponse,
    QueryResult,
    SentimentLabel,
    SourceType,
)

__all__ = [
    "settings",
    "Settings",
    "Document",
    "DocumentFormat",
    "EntityType",
    "FirefliesTranscript",
    "IngestionResult",
    "MemoryChunk",
    "MemoryMetadata",
    "QueryFilter",
    "QueryResponse",
    "QueryResult",
    "SentimentLabel",
    "SourceType",
]
