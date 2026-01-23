#!/usr/bin/env python
"""
Initialize Memory Palace databases.

This script creates the required database files and structures for the
Memory Palace MCP server. Run this before first use.

Usage:
    python -m memory_palace.scripts.setup_db

    # Or with custom data path:
    MEMORY_PALACE_PATH=/path/to/data python -m memory_palace.scripts.setup_db
"""

import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def setup():
    """Initialize databases."""
    from memory_palace.config import load_settings
    from memory_palace.core.vector_db import VectorDB
    from memory_palace.core.metadata_db import MetadataDB

    settings = load_settings()

    print("Memory Palace Database Setup")
    print("=" * 40)
    print(f"ChromaDB path: {settings.storage.chroma_path}")
    print(f"SQLite path: {settings.storage.sqlite_path}")
    print(f"Embedding model: {settings.embeddings.model}")
    print("=" * 40)
    print()

    # Create data directory if needed
    chroma_path = Path(settings.storage.chroma_path)
    sqlite_path = Path(settings.storage.sqlite_path)

    chroma_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize vector DB
    print("Initializing vector database...")
    try:
        vector_db = VectorDB(
            persist_path=settings.storage.chroma_path,
            embedding_model=settings.embeddings.model
        )
        await vector_db.initialize()
        count = await vector_db.count()
        print(f"  Vector database initialized ({count} existing memories)")
    except Exception as e:
        print(f"  ERROR: Failed to initialize vector database: {e}")
        sys.exit(1)

    # Initialize metadata DB
    print("Initializing metadata database...")
    try:
        metadata_db = MetadataDB(settings.storage.sqlite_path)
        await metadata_db.initialize()
        stats = await metadata_db.get_stats()
        print(f"  Metadata database initialized")
        print(f"  - {stats.get('total_memories', 0)} memories")
        print(f"  - {stats.get('total_entities', 0)} entities")
        print(f"  - {stats.get('total_topics', 0)} topics")
        await metadata_db.close()
    except Exception as e:
        print(f"  ERROR: Failed to initialize metadata database: {e}")
        sys.exit(1)

    # Try loading spaCy model
    print("Checking spaCy model...")
    try:
        import spacy
        nlp = spacy.load(settings.extraction.spacy_model)
        print(f"  spaCy model '{settings.extraction.spacy_model}' loaded successfully")
    except ImportError:
        print("  WARNING: spaCy not installed. NER will be disabled.")
        print("  Install with: pip install spacy")
    except OSError:
        print(f"  WARNING: spaCy model '{settings.extraction.spacy_model}' not found.")
        print(f"  Install with: python -m spacy download {settings.extraction.spacy_model}")

    print()
    print("Setup complete!")
    print()
    print("Next steps:")
    print("1. For Claude Desktop: Add the server to your claude_desktop_config.json")
    print("2. For HTTP server: Run 'python -m memory_palace.scripts.run_http'")
    print("3. Start saving memories!")


def main():
    """Main entry point."""
    asyncio.run(setup())


if __name__ == "__main__":
    main()
