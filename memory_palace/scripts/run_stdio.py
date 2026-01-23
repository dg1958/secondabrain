#!/usr/bin/env python
"""
Entry point for Claude Desktop MCP server.

This script starts the Memory Palace MCP server using stdio transport,
which is the required transport for Claude Desktop integration.

Usage:
    python -m memory_palace.scripts.run_stdio

Claude Desktop Configuration:
    Add to claude_desktop_config.json:
    {
        "mcpServers": {
            "memory-palace": {
                "command": "python",
                "args": ["-m", "memory_palace.scripts.run_stdio"],
                "env": {
                    "MEMORY_PALACE_PATH": "/path/to/data"
                }
            }
        }
    }
"""

import asyncio
import logging
import sys

# Configure logging to stderr (not stdout, which is used for MCP communication)
logging.basicConfig(
    level=logging.WARNING,  # Only warnings and errors
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)


def main():
    """Main entry point."""
    from memory_palace.mcp.transports.stdio_transport import run_stdio
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
