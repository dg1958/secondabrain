"""Stdio transport for Memory Palace MCP server.

This transport is used for Claude Desktop integration.
"""

import asyncio
import logging

from memory_palace.config import load_settings
from memory_palace.mcp.server import create_server

logger = logging.getLogger(__name__)


async def run_stdio() -> None:
    """
    Run the MCP server using stdio transport.

    This is the primary transport for Claude Desktop. Communication
    happens through stdin/stdout using JSON-RPC messages.
    """
    from mcp.server.stdio import stdio_server

    # Load settings
    load_settings()

    logger.info("Starting Memory Palace MCP server (stdio transport)")

    server_instance = create_server()

    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Stdio server running")
            await server_instance.server.run(
                read_stream,
                write_stream,
                server_instance.server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Stdio server error: {e}", exc_info=True)
        raise
    finally:
        await server_instance.cleanup()
        logger.info("Stdio server stopped")


def main():
    """Entry point for stdio server."""
    # Configure logging for stdio (minimal, to stderr)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]  # stderr only
    )

    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
