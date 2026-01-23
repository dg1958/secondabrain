#!/usr/bin/env python
"""
Entry point for HTTP MCP server.

This script starts the Memory Palace MCP server using HTTP/SSE transport,
which can be used with Open WebUI, LibreChat, and other web clients.

Usage:
    python -m memory_palace.scripts.run_http

    # Or with custom host/port:
    MEMORY_PALACE_HTTP_HOST=0.0.0.0 MEMORY_PALACE_HTTP_PORT=8080 python -m memory_palace.scripts.run_http

Endpoints:
    GET  /health              - Health check
    GET  /tools               - List available tools
    GET  /tools/{name}        - Get tool info
    POST /tools/{name}        - Call a tool
    GET  /sse/tools/{name}    - Call tool with SSE streaming
    POST /tools/batch         - Batch tool calls
    POST /mcp                 - MCP JSON-RPC endpoint
"""

import logging
import os


def main():
    """Main entry point."""
    import uvicorn
    from memory_palace.config import load_settings
    from memory_palace.mcp.transports.http_transport import create_app

    settings = load_settings()

    # Allow environment variable overrides
    host = os.environ.get("MEMORY_PALACE_HTTP_HOST", settings.server.http.host)
    port = int(os.environ.get("MEMORY_PALACE_HTTP_PORT", settings.server.http.port))

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=settings.logging.format
    )

    print(f"Starting Memory Palace HTTP server on {host}:{port}")
    print(f"API docs available at http://{host}:{port}/docs")

    app = create_app()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
