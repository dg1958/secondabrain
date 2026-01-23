"""MCP Server module for Memory Palace.

This module provides Model Context Protocol (MCP) server functionality
for Claude Desktop, LibreChat, and other MCP-compatible clients.

Note: Due to package naming conflict with the external 'mcp' package,
imports are not performed at package level. Import directly from submodules:

    from memory_palace.mcp.server import create_server, run_stdio_server
    from memory_palace.mcp.tools import search_memories, save_memory
"""

# Lazy imports to avoid circular import with external 'mcp' package
__all__ = ["create_server", "run_stdio_server"]


def __getattr__(name):
    """Lazy import to avoid circular import with external mcp package."""
    if name in ("create_server", "run_stdio_server"):
        from memory_palace.mcp.server import create_server, run_stdio_server
        return {"create_server": create_server, "run_stdio_server": run_stdio_server}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
