"""
HTTP/SSE transport for Memory Palace MCP server.

This transport supports:
- REST API for Open WebUI functions/pipelines
- SSE transport for LibreChat (alternative to stdio)
- Standard HTTP endpoints for any web client
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..server import server, initialize
from ...config import get_settings

logger = logging.getLogger(__name__)


# ============ REQUEST MODELS ============

class ToolRequest(BaseModel):
    """Request model for tool execution."""
    arguments: dict[str, Any] = {}


class MCPMessage(BaseModel):
    """MCP JSON-RPC message model."""
    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = {}
    id: Any = None


# ============ APP CREATION ============

def create_http_app() -> FastAPI:
    """
    Create the FastAPI application for HTTP transport.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Memory Palace MCP Server",
        description=(
            "HTTP API for Memory Palace - Personal AI Memory System. "
            "Compatible with Open WebUI, LibreChat (SSE mode), and other HTTP clients."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.http.cors_origins + ["*"],  # Add wildcard for dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ============ LIFECYCLE EVENTS ============

    @app.on_event("startup")
    async def startup():
        """Initialize the MCP server on startup."""
        await initialize()
        logger.info(f"Memory Palace HTTP server started on {settings.http.host}:{settings.http.port}")

    # ============ HEALTH & INFO ============

    @app.get("/")
    async def root():
        """Root endpoint with server info."""
        return {
            "name": "Memory Palace MCP Server",
            "version": "1.0.0",
            "description": "Personal AI Memory System",
            "endpoints": {
                "health": "/api/health",
                "tools": "/api/tools",
                "docs": "/docs",
                "mcp_sse": "/mcp/sse",
                "mcp_message": "/mcp/message",
            }
        }

    @app.get("/api/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "server": "memory-palace",
        }

    # ============ REST API (for Open WebUI) ============

    @app.get("/api/tools")
    async def list_tools():
        """
        List all available tools with their schemas.

        This endpoint is useful for:
        - Open WebUI to discover available functions
        - Any client that wants to know available operations
        """
        tools = await server.list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                }
                for t in tools
            ]
        }

    @app.post("/api/tools/{tool_name}")
    async def call_tool(tool_name: str, request: ToolRequest):
        """
        Execute a specific tool by name.

        This endpoint allows direct tool execution for REST clients.
        The arguments should match the tool's input schema.
        """
        try:
            results = await server.call_tool(tool_name, request.arguments)

            # MCP returns list of content blocks, extract the text
            if results and len(results) > 0:
                content = results[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"result": content.text}
                return {"result": str(content)}

            return {"result": None}

        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # ============ RESOURCES API ============

    @app.get("/api/resources")
    async def list_resources():
        """List available resources."""
        resources = await server.list_resources()
        return {
            "resources": [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mimeType,
                }
                for r in resources
            ]
        }

    @app.get("/api/resources/{resource_uri:path}")
    async def read_resource(resource_uri: str):
        """Read a specific resource."""
        try:
            # Reconstruct the full URI
            if not resource_uri.startswith("memory://"):
                resource_uri = f"memory://{resource_uri}"

            content = await server.read_resource(resource_uri)
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"content": content}
        except Exception as e:
            logger.error(f"Resource read error: {e}", exc_info=True)
            raise HTTPException(status_code=404, detail=str(e))

    # ============ SSE TRANSPORT (for LibreChat HTTP mode) ============

    @app.get("/mcp/sse")
    async def mcp_sse(request: Request):
        """
        Server-Sent Events transport for MCP protocol.

        LibreChat can connect here instead of using stdio.
        This maintains a persistent connection for real-time updates.
        """
        async def event_generator():
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "server": "memory-palace",
                    "version": "1.0.0",
                    "tools": len(await server.list_tools()),
                })
            }

            # Keep connection alive with periodic pings
            while True:
                if await request.is_disconnected():
                    logger.info("SSE client disconnected")
                    break

                yield {"event": "ping", "data": ""}
                await asyncio.sleep(30)

        return EventSourceResponse(event_generator())

    @app.post("/mcp/message")
    async def mcp_message(message: MCPMessage):
        """
        Handle MCP JSON-RPC messages via HTTP POST.

        This implements the MCP protocol over HTTP for clients
        that prefer HTTP over stdio or SSE.
        """
        try:
            result = await _handle_mcp_method(message.method, message.params)
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "result": result,
            }
        except Exception as e:
            logger.error(f"MCP message error: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "error": {
                    "code": -32000,
                    "message": str(e),
                }
            }

    async def _handle_mcp_method(method: str, params: dict[str, Any]) -> Any:
        """Handle individual MCP methods."""
        if method == "tools/list":
            tools = await server.list_tools()
            return {"tools": [t.model_dump() for t in tools]}

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            results = await server.call_tool(tool_name, arguments)

            if results and len(results) > 0:
                content = results[0]
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"result": content.text}

            return {"result": None}

        elif method == "resources/list":
            resources = await server.list_resources()
            return {"resources": [r.model_dump() for r in resources]}

        elif method == "resources/read":
            uri = params.get("uri")
            content = await server.read_resource(uri)
            return {"content": content}

        elif method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "memory-palace",
                    "version": "1.0.0",
                },
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
            }

        else:
            raise ValueError(f"Unknown method: {method}")

    return app


# ============ SERVER RUNNER ============

async def run_http_server(host: str = None, port: int = None) -> None:
    """
    Run the HTTP server.

    Args:
        host: Host to bind to (default from config)
        port: Port to bind to (default from config)
    """
    import uvicorn

    settings = get_settings()
    host = host or settings.http.host
    port = port or settings.http.port

    app = create_http_app()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Entry point for HTTP server."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings = get_settings()

    logger.info(f"Starting Memory Palace HTTP server on {settings.http.host}:{settings.http.port}")

    uvicorn.run(
        "memory_palace.mcp.transports.http_transport:create_http_app",
        host=settings.http.host,
        port=settings.http.port,
        reload=False,
        factory=True,
    )


if __name__ == "__main__":
    main()
