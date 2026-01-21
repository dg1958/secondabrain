#!/usr/bin/env python3
"""
Entry point for Memory Palace MCP server (HTTP transport).

This entry point is for Open WebUI and LibreChat (SSE mode).

Usage:
    python -m memory_palace.scripts.run_http
    python -m memory_palace.scripts.run_http --host 0.0.0.0 --port 8765

Configuration:
    Set MEMORY_PALACE_DATA environment variable to specify data directory.
    Set MEMORY_PALACE_CONFIG environment variable to specify config file.
"""

import argparse
import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory_palace.mcp.transports.http_transport import run_http_server
from memory_palace.config import get_settings


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Memory Palace MCP Server (HTTP transport)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (default: from config or 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from config or 8765)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Log level (DEBUG, INFO, WARNING, ERROR)"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = args.log_level or os.environ.get("MEMORY_PALACE_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)

    settings = get_settings()
    host = args.host or settings.http.host
    port = args.port or settings.http.port

    logger.info(f"Starting Memory Palace HTTP server on {host}:{port}")

    try:
        asyncio.run(run_http_server(host=host, port=port))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
