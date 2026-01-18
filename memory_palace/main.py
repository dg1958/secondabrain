#!/usr/bin/env python3
"""
Memory Palace - Personal AI Knowledge Management System

This is the main entry point for the Memory Palace application.
It provides access to the CLI, API server, and core functionality.

Usage:
    # Run CLI commands
    python main.py query "What did I discuss about AI?"
    python main.py ingest ./transcripts/
    python main.py serve

    # Or install and use directly
    pip install -e .
    memory-palace query "Your query here"
"""

import sys
from pathlib import Path

# Ensure the package root is in the path
package_root = Path(__file__).parent
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from loguru import logger

# Configure logging
from config import settings

log_level = settings.get("logging", "level", default="INFO")
log_file = settings.get("logging", "file", default=None)

# Remove default handler and add custom one
logger.remove()
logger.add(
    sys.stderr,
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

if log_file:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_file,
        level=log_level,
        rotation=settings.get("logging", "rotation", default="10 MB"),
        retention=settings.get("logging", "retention", default="1 week"),
    )


def initialize():
    """
    Initialize the Memory Palace system.

    Creates necessary directories and validates configuration.
    """
    from config import settings

    # Create data directories
    data_dirs = [
        settings.get("paths", "data_dir", default="./data"),
        settings.get("paths", "raw_dir", default="./data/raw"),
        settings.get("paths", "processed_dir", default="./data/processed"),
        settings.get("paths", "db_dir", default="./data/chroma_db"),
        settings.get("paths", "export_dir", default="./data/exports"),
        settings.get("paths", "cache_dir", default="./data/cache"),
    ]

    for dir_path in data_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    logger.info("Memory Palace initialized")


def main():
    """Main entry point."""
    # Initialize system
    initialize()

    # Import and run CLI
    from cli.commands import cli
    cli()


# Expose key classes for programmatic use
def get_query_engine():
    """Get the query engine for programmatic access."""
    from query.query_engine import get_query_engine as _get_engine
    return _get_engine(settings.anthropic_api_key)


def get_importer():
    """Get the batch importer for programmatic access."""
    from ingestion.batch_importer import get_batch_importer
    return get_batch_importer()


def query(query_text: str, top_k: int = 10, synthesize: bool = True):
    """
    Query memories.

    Args:
        query_text: Natural language query
        top_k: Number of results
        synthesize: Generate AI synthesis

    Returns:
        QueryResponse object
    """
    engine = get_query_engine()
    return engine.query(query_text, top_k=top_k, synthesize_results=synthesize)


def ingest(text: str, **metadata):
    """
    Ingest text into the memory system.

    Args:
        text: Text content to ingest
        **metadata: Additional metadata (timestamp, participants, tags)

    Returns:
        IngestionResult object
    """
    importer = get_importer()
    return importer.import_text(text, **metadata)


def ingest_file(file_path: str, **kwargs):
    """
    Ingest a file into the memory system.

    Args:
        file_path: Path to file
        **kwargs: Additional options

    Returns:
        IngestionResult object
    """
    importer = get_importer()
    return importer.import_file(file_path, **kwargs)


if __name__ == "__main__":
    main()
