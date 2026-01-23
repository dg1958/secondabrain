"""HTTP/SSE transport for Memory Palace MCP server.

This transport provides a REST API and SSE endpoints for web clients
like Open WebUI, LibreChat, and custom integrations.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from memory_palace.config import load_settings, get_settings
from memory_palace.mcp.server import create_server, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

# Global server instance
_server_instance = None


class ToolCallRequest(BaseModel):
    """Request body for tool calls."""
    arguments: dict = {}


class ToolInfo(BaseModel):
    """Information about a tool."""
    name: str
    description: str
    inputSchema: dict


def json_serializer(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle."""
    global _server_instance

    # Startup
    logger.info("Starting Memory Palace HTTP server")
    _server_instance = create_server()
    await _server_instance.initialize()
    logger.info("Memory Palace HTTP server ready")

    yield

    # Shutdown
    if _server_instance:
        await _server_instance.cleanup()
    logger.info("Memory Palace HTTP server stopped")


def create_app() -> FastAPI:
    """
    Create FastAPI application for HTTP/SSE transport.

    Returns:
        FastAPI application instance
    """
    settings = load_settings()

    app = FastAPI(
        title="Memory Palace MCP Server",
        description="HTTP/SSE transport for Memory Palace MCP server",
        version="0.1.0",
        lifespan=lifespan
    )

    # Add CORS middleware
    cors_origins = settings.server.http.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "memory-palace"}

    # List tools endpoint
    @app.get("/tools", response_model=list[ToolInfo])
    async def list_tools():
        """List all available tools."""
        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.inputSchema
            )
            for tool in TOOL_DEFINITIONS
        ]

    # Get specific tool info
    @app.get("/tools/{tool_name}", response_model=ToolInfo)
    async def get_tool(tool_name: str):
        """Get information about a specific tool."""
        for tool in TOOL_DEFINITIONS:
            if tool.name == tool_name:
                return ToolInfo(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.inputSchema
                )
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Call tool endpoint
    @app.post("/tools/{tool_name}")
    async def call_tool(tool_name: str, request: ToolCallRequest):
        """
        Call a specific tool.

        This endpoint executes an MCP tool and returns the result.
        """
        global _server_instance

        if not _server_instance:
            raise HTTPException(status_code=503, detail="Server not initialized")

        # Check if tool exists
        tool_exists = any(tool.name == tool_name for tool in TOOL_DEFINITIONS)
        if not tool_exists:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        try:
            result = await _server_instance._execute_tool(tool_name, request.arguments)
            return JSONResponse(
                content=json.loads(json.dumps(result, default=json_serializer))
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # SSE endpoint for streaming responses
    @app.get("/sse/tools/{tool_name}")
    async def call_tool_sse(tool_name: str, request: Request):
        """
        Call a tool with Server-Sent Events for streaming.

        Arguments should be passed as query parameters.
        """
        global _server_instance

        if not _server_instance:
            raise HTTPException(status_code=503, detail="Server not initialized")

        # Check if tool exists
        tool_exists = any(tool.name == tool_name for tool in TOOL_DEFINITIONS)
        if not tool_exists:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        # Get arguments from query params
        arguments = dict(request.query_params)

        async def generate():
            try:
                # Send start event
                yield f"event: start\ndata: {json.dumps({'tool': tool_name})}\n\n"

                # Execute tool
                result = await _server_instance._execute_tool(tool_name, arguments)

                # Send result
                yield f"event: result\ndata: {json.dumps(result, default=json_serializer)}\n\n"

                # Send done event
                yield f"event: done\ndata: {json.dumps({'success': True})}\n\n"

            except Exception as e:
                logger.error(f"SSE tool execution error: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    # Batch tool calls
    @app.post("/tools/batch")
    async def batch_call_tools(requests: list[dict]):
        """
        Call multiple tools in a batch.

        Each request should have:
        - tool: Tool name
        - arguments: Tool arguments
        """
        global _server_instance

        if not _server_instance:
            raise HTTPException(status_code=503, detail="Server not initialized")

        results = []
        for req in requests:
            tool_name = req.get("tool")
            arguments = req.get("arguments", {})

            if not tool_name:
                results.append({"error": True, "message": "Missing tool name"})
                continue

            try:
                result = await _server_instance._execute_tool(tool_name, arguments)
                results.append(result)
            except Exception as e:
                results.append({"error": True, "message": str(e)})

        return JSONResponse(
            content=json.loads(json.dumps(results, default=json_serializer))
        )

    # MCP-compatible endpoint (for clients that expect MCP over HTTP)
    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        """
        MCP-compatible JSON-RPC endpoint.

        Accepts JSON-RPC 2.0 requests for MCP operations.
        """
        global _server_instance

        if not _server_instance:
            raise HTTPException(status_code=503, detail="Server not initialized")

        body = await request.json()

        method = body.get("method")
        params = body.get("params", {})
        req_id = body.get("id")

        try:
            if method == "tools/list":
                result = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in TOOL_DEFINITIONS
                ]
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await _server_instance._execute_tool(tool_name, arguments)
            elif method == "resources/list":
                result = [
                    {
                        "uri": "memory-palace://stats",
                        "name": "Memory Palace Statistics",
                        "mimeType": "application/json"
                    }
                ]
            elif method == "resources/read":
                from memory_palace.mcp.tools import get_memory_stats
                uri = params.get("uri")
                if uri == "memory-palace://stats":
                    result = await get_memory_stats(_server_instance.query_engine)
                else:
                    raise ValueError(f"Unknown resource: {uri}")
            else:
                raise ValueError(f"Unknown method: {method}")

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": json.loads(json.dumps(result, default=json_serializer))
            })

        except Exception as e:
            logger.error(f"MCP endpoint error: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }
            )

    return app


def main():
    """Entry point for HTTP server."""
    import uvicorn

    settings = load_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=settings.logging.format
    )

    app = create_app()

    uvicorn.run(
        app,
        host=settings.server.http.host,
        port=settings.server.http.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
