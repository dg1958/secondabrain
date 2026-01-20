#!/usr/bin/env python3
"""
Database setup script for Memory Palace.

This script initializes the databases and verifies the installation.

Usage:
    python -m memory_palace.scripts.setup_db
    python -m memory_palace.scripts.setup_db --verify
    python -m memory_palace.scripts.setup_db --reset
"""

import argparse
import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory_palace.config import get_settings
from memory_palace.core.vector_db import get_vector_db
from memory_palace.core.metadata_db import get_metadata_db

logger = logging.getLogger(__name__)


async def setup_databases():
    """Initialize all databases."""
    settings = get_settings()

    print(f"Setting up Memory Palace databases...")
    print(f"Data directory: {settings.storage.data_dir}")
    print()

    # Initialize vector database
    print("Initializing vector database (ChromaDB)...")
    vector_db = get_vector_db()
    count = await vector_db.get_count()
    print(f"  Path: {settings.storage.vector_db_path}")
    print(f"  Collection: {settings.vector_db.collection_name}")
    print(f"  Current entries: {count}")
    print("  Status: OK")
    print()

    # Initialize metadata database
    print("Initializing metadata database (SQLite)...")
    metadata_db = get_metadata_db()
    await metadata_db._ensure_initialized()
    stats = await metadata_db.get_stats()
    print(f"  Path: {settings.storage.metadata_db_path}")
    print(f"  Total memories: {stats['total_memories']}")
    print(f"  Total entities: {stats['total_entities']}")
    print(f"  Total topics: {stats['total_topics']}")
    print("  Status: OK")
    print()

    print("Database setup complete!")


async def verify_installation():
    """Verify that all components are working."""
    print("Verifying Memory Palace installation...")
    print()

    errors = []

    # Check config
    print("1. Checking configuration...")
    try:
        settings = get_settings()
        print(f"   Data directory: {settings.storage.data_dir}")
        print("   Status: OK")
    except Exception as e:
        print(f"   Status: FAILED - {e}")
        errors.append(f"Config: {e}")
    print()

    # Check vector database
    print("2. Checking vector database...")
    try:
        vector_db = get_vector_db()
        count = await vector_db.get_count()
        print(f"   Entries: {count}")
        print("   Status: OK")
    except Exception as e:
        print(f"   Status: FAILED - {e}")
        errors.append(f"VectorDB: {e}")
    print()

    # Check metadata database
    print("3. Checking metadata database...")
    try:
        metadata_db = get_metadata_db()
        await metadata_db._ensure_initialized()
        print("   Status: OK")
    except Exception as e:
        print(f"   Status: FAILED - {e}")
        errors.append(f"MetadataDB: {e}")
    print()

    # Check spaCy
    print("4. Checking NLP (spaCy)...")
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        doc = nlp("This is a test sentence with John Smith from Acme Corp.")
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        print(f"   Entities found: {entities}")
        print("   Status: OK")
    except Exception as e:
        print(f"   Status: WARNING - {e}")
        print("   Note: NER will use fallback extraction without spaCy")
    print()

    # Check MCP server
    print("5. Checking MCP server...")
    try:
        from memory_palace.mcp.server import server, TOOLS
        print(f"   Tools available: {len(TOOLS)}")
        print("   Status: OK")
    except Exception as e:
        print(f"   Status: FAILED - {e}")
        errors.append(f"MCP Server: {e}")
    print()

    # Summary
    if errors:
        print("=" * 50)
        print("VERIFICATION FAILED")
        print("=" * 50)
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("=" * 50)
        print("VERIFICATION PASSED")
        print("=" * 50)
        print("Memory Palace is ready to use!")
        return True


async def reset_databases():
    """Reset all databases (WARNING: destructive!)."""
    print("WARNING: This will delete all data in Memory Palace!")
    confirm = input("Type 'RESET' to confirm: ")

    if confirm != "RESET":
        print("Reset cancelled.")
        return

    settings = get_settings()

    # Clear vector database
    print("Clearing vector database...")
    vector_db = get_vector_db()
    await vector_db.clear()
    print("  Done.")

    # Remove SQLite database file
    print("Removing metadata database...")
    import os
    if os.path.exists(settings.storage.metadata_db_path):
        os.remove(settings.storage.metadata_db_path)
    print("  Done.")

    print()
    print("Databases reset. Run setup again to reinitialize.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Memory Palace Database Setup"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify installation without making changes"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all databases (WARNING: destructive!)"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,  # Suppress info logs during setup
        format="%(message)s",
    )

    if args.verify:
        success = asyncio.run(verify_installation())
        sys.exit(0 if success else 1)
    elif args.reset:
        asyncio.run(reset_databases())
    else:
        asyncio.run(setup_databases())


if __name__ == "__main__":
    main()
