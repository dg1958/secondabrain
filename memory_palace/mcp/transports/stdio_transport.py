"""
Stdio transport for Memory Palace MCP server.

This transport is used by Claude Desktop, LibreChat (default mode),
Cursor, Windsurf, and other MCP-compatible editors.
"""

import asyncio
import logging
import sys

from mcp.server.stdio import stdio_server

from ..server import server, initialize

logger = logging.getLogger(__name__)


async def run_stdio_server() -> None:
    """
    Run the MCP server using stdio transport.

    This is the primary transport for desktop MCP clients.
    Communication happens over stdin/stdout using JSON-RPC.
    """
    # Initialize the server
    await initialize()

    logger.info("Starting Memory Palace MCP server (stdio transport)")

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Entry point for stdio server."""
    # Configure logging to stderr (stdout is used for MCP protocol)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
