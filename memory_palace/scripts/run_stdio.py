#!/usr/bin/env python3
"""
Entry point for Memory Palace MCP server (stdio transport).

This is the main entry point for Claude Desktop, LibreChat, Cursor,
and other MCP-compatible clients using stdio transport.

Usage:
    python -m memory_palace.scripts.run_stdio

Configuration:
    Set MEMORY_PALACE_DATA environment variable to specify data directory.
    Set MEMORY_PALACE_CONFIG environment variable to specify config file.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory_palace.mcp.transports.stdio_transport import run_stdio_server


def main():
    """Main entry point."""
    # Configure logging to stderr (stdout is used for MCP protocol)
    log_level = os.environ.get("MEMORY_PALACE_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Memory Palace MCP server (stdio transport)")

    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
