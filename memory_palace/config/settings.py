"""Configuration loader for Memory Palace."""

import os
import logging
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StorageSettings(BaseModel):
    """Storage configuration."""
    chroma_path: str = "./data/chroma_db"
    sqlite_path: str = "./data/metadata.db"


class EmbeddingsSettings(BaseModel):
    """Embeddings configuration."""
    model: str = "all-MiniLM-L6-v2"


class ExtractionSettings(BaseModel):
    """Metadata extraction configuration."""
    spacy_model: str = "en_core_web_sm"
    max_topics_per_memory: int = 5
    min_topic_length: int = 3


class StdioServerSettings(BaseModel):
    """Stdio server configuration."""
    enabled: bool = True


class HttpServerSettings(BaseModel):
    """HTTP server configuration."""
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:*", "http://127.0.0.1:*"])


class ServerSettings(BaseModel):
    """Server configuration."""
    stdio: StdioServerSettings = Field(default_factory=StdioServerSettings)
    http: HttpServerSettings = Field(default_factory=HttpServerSettings)


class SearchSettings(BaseModel):
    """Search configuration."""
    default_limit: int = 10
    max_limit: int = 100
    default_min_relevance: float = 0.5


class LoggingSettings(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Settings(BaseModel):
    """Complete settings model."""
    storage: StorageSettings = Field(default_factory=StorageSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


# Global settings instance
_settings: Optional[Settings] = None


def _find_config_file() -> Optional[Path]:
    """Find configuration file in standard locations."""
    # Check environment variable first
    env_config = os.environ.get("MEMORY_PALACE_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            return path
        logger.warning(f"Config file from MEMORY_PALACE_CONFIG not found: {env_config}")

    # Check data directory
    data_path = os.environ.get("MEMORY_PALACE_PATH", "./data")
    data_config = Path(data_path) / "settings.yaml"
    if data_config.exists():
        return data_config

    # Check current directory
    local_config = Path("settings.yaml")
    if local_config.exists():
        return local_config

    return None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _get_default_config() -> dict[str, Any]:
    """Load default configuration from package."""
    default_path = Path(__file__).parent / "default_settings.yaml"
    if default_path.exists():
        return _load_yaml_config(default_path)
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_path: Optional[str] = None) -> Settings:
    """
    Load settings from configuration files.

    Priority (highest to lowest):
    1. Explicitly provided config_path
    2. MEMORY_PALACE_CONFIG environment variable
    3. {MEMORY_PALACE_PATH}/settings.yaml
    4. ./settings.yaml
    5. Default settings

    Args:
        config_path: Optional path to configuration file

    Returns:
        Settings instance
    """
    global _settings

    # Start with defaults
    config = _get_default_config()

    # Find and load user config
    if config_path:
        user_config_path = Path(config_path)
    else:
        user_config_path = _find_config_file()

    if user_config_path and user_config_path.exists():
        logger.info(f"Loading configuration from: {user_config_path}")
        user_config = _load_yaml_config(user_config_path)
        config = _deep_merge(config, user_config)

    # Resolve relative paths based on MEMORY_PALACE_PATH
    base_path = Path(os.environ.get("MEMORY_PALACE_PATH", "."))

    if not Path(config.get("storage", {}).get("chroma_path", "")).is_absolute():
        config.setdefault("storage", {})["chroma_path"] = str(
            base_path / config.get("storage", {}).get("chroma_path", "data/chroma_db")
        )

    if not Path(config.get("storage", {}).get("sqlite_path", "")).is_absolute():
        config.setdefault("storage", {})["sqlite_path"] = str(
            base_path / config.get("storage", {}).get("sqlite_path", "data/metadata.db")
        )

    _settings = Settings(**config)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, _settings.logging.level),
        format=_settings.logging.format
    )

    return _settings


def get_settings() -> Settings:
    """
    Get the current settings instance.

    Returns:
        Settings instance (loads defaults if not already loaded)
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
