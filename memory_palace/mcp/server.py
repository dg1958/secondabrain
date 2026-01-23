"""MCP Server for Memory Palace.

This module implements the Model Context Protocol (MCP) server that exposes
memory palace functionality as tools for Claude Desktop, LibreChat, Open WebUI,
and other MCP-compatible clients.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceTemplate,
)

from memory_palace.config import load_settings, get_settings
from memory_palace.core.vector_db import VectorDB
from memory_palace.core.metadata_db import MetadataDB
from memory_palace.core.query_engine import QueryEngine
from memory_palace.mcp.schemas import (
    MemorySearchParams,
    EntitySearchParams,
    DateRangeSearchParams,
    TimelineQueryParams,
    TopicEvolutionParams,
    MemorySaveParams,
    ConversationSummaryParams,
    EntityListParams,
    EntityProfileParams,
    MemoryUpdateParams,
    MemoryDeleteParams,
    TopicListParams,
    RecentMemoriesParams,
)
from memory_palace.mcp.tools import (
    search_memories,
    search_by_entity,
    search_by_date_range,
    timeline_query,
    get_topic_evolution,
    save_memory,
    save_conversation_summary,
    list_entities,
    get_entity_profile,
    update_memory,
    delete_memory,
    get_memory_stats,
    list_topics,
    list_recent,
)

logger = logging.getLogger(__name__)

# Tool definitions with comprehensive descriptions for LLM consumption
TOOL_DEFINITIONS = [
    # Search Tools
    Tool(
        name="search_memories",
        description="""Search the memory palace using natural language.

This is the primary search tool. It performs semantic similarity search on memory content
and can filter by date range, topics, entities, and memory types.

Use this when:
- Looking for specific information that was previously recorded
- Searching for memories about a topic
- Finding information from a particular time period

Examples:
- "What did I decide about the project architecture?"
- "Find memories about Python from last month"
- "Search for anything related to budget discussions"

Parameters:
- query: Natural language search query (required)
- limit: Max results (default 10, max 100)
- date_from/date_to: Filter by date range (YYYY-MM-DD format)
- topics: Filter by specific topics (list)
- entities: Filter by mentioned entities (list)
- memory_types: Filter by type (fact, preference, decision, event, insight, correction)
- min_relevance: Minimum similarity score 0-1 (default 0.5)""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-100)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100
                },
                "date_from": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date filter (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "format": "date",
                    "description": "End date filter (YYYY-MM-DD)"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by these topics"
                },
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by these entities"
                },
                "memory_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["fact", "preference", "decision", "event", "insight", "correction"]},
                    "description": "Filter by memory types"
                },
                "min_relevance": {
                    "type": "number",
                    "description": "Minimum relevance score (0-1)",
                    "default": 0.5,
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="search_by_entity",
        description="""Find memories mentioning a specific person, organization, or concept.

Use this when looking for all information about a particular entity rather than
a general topic. Good for building a picture of what you know about someone/something.

Entity types:
- PERSON: People's names
- ORG: Organizations, companies
- LOCATION: Places
- PROJECT: Projects
- CONCEPT: Technologies, ideas

Examples:
- "Find all memories about John Smith"
- "What do I know about Acme Corporation?"
- "Show memories mentioning the ML project"

Parameters:
- entity_name: Name of the entity to search for (required)
- entity_type: Filter by type (PERSON, ORG, LOCATION, PROJECT, CONCEPT)
- limit: Max results
- date_from/date_to: Date range filter""",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Name of the entity to search for"
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["PERSON", "ORG", "LOCATION", "PROJECT", "CONCEPT", "ANY"],
                    "description": "Type of entity"
                },
                "limit": {
                    "type": "integer",
                    "default": 10
                },
                "date_from": {
                    "type": "string",
                    "format": "date"
                },
                "date_to": {
                    "type": "string",
                    "format": "date"
                }
            },
            "required": ["entity_name"]
        }
    ),
    Tool(
        name="search_by_date_range",
        description="""Find memories from a specific time period.

Use this when you want to see what was recorded during a particular time,
regardless of topic. Good for reviewing a week, month, or specific date range.

Examples:
- "What did I record last week?"
- "Show memories from January 2024"
- "What happened between March 1 and March 15?"

Parameters:
- date_from: Start date (required, YYYY-MM-DD)
- date_to: End date (required, YYYY-MM-DD)
- topics: Optional topic filter
- memory_types: Optional type filter
- limit: Max results (default 50)""",
        inputSchema={
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "format": "date",
                    "description": "End date (YYYY-MM-DD)"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "memory_types": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "limit": {
                    "type": "integer",
                    "default": 50
                }
            },
            "required": ["date_from", "date_to"]
        }
    ),

    # Timeline Tools
    Tool(
        name="timeline_query",
        description="""Get a chronological timeline of memories for a topic.

Shows how a topic developed over time, grouped by day/week/month/year.
Use this to understand the progression of a project, learning journey,
or any topic where temporal context matters.

Examples:
- "Show timeline of my Python learning"
- "Timeline of the product launch project"
- "How did the budget discussions evolve over Q1?"

Parameters:
- topic: Topic to trace through time (required)
- date_from/date_to: Time window
- granularity: Grouping (day, week, month, year) - default week
- include_summaries: Include AI summaries per period
- max_entries: Max memories to include (default 50)""",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to trace through time"
                },
                "date_from": {
                    "type": "string",
                    "format": "date"
                },
                "date_to": {
                    "type": "string",
                    "format": "date"
                },
                "granularity": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year"],
                    "default": "week"
                },
                "include_summaries": {
                    "type": "boolean",
                    "default": True
                },
                "max_entries": {
                    "type": "integer",
                    "default": 50
                }
            },
            "required": ["topic"]
        }
    ),
    Tool(
        name="get_topic_evolution",
        description="""Analyze how your thinking on a topic evolved over time.

Shows key themes, sentiment trends, and sample memories for each period.
Use this to understand how your perspective or knowledge changed.

Examples:
- "How has my understanding of machine learning evolved?"
- "Show evolution of my thoughts on remote work"
- "Track how the project scope changed over time"

Parameters:
- topic: Topic to analyze (required)
- date_from/date_to: Analysis window
- granularity: Analysis period (week, month, quarter, year) - default month""",
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to analyze"
                },
                "date_from": {
                    "type": "string",
                    "format": "date"
                },
                "date_to": {
                    "type": "string",
                    "format": "date"
                },
                "granularity": {
                    "type": "string",
                    "enum": ["week", "month", "quarter", "year"],
                    "default": "month"
                }
            },
            "required": ["topic"]
        }
    ),

    # Save Tools
    Tool(
        name="save_memory",
        description="""Save a new memory to the palace.

Records information with automatic extraction of entities and topics.
Use this to store facts, preferences, decisions, events, insights, or corrections.

Memory types:
- fact: Factual information
- preference: Personal preferences or opinions
- decision: Decisions made
- event: Things that happened
- insight: Realizations or learnings
- correction: Corrections to previous information

Importance levels: low, medium, high, critical

Examples:
- Save a fact: "John's birthday is March 15th" (type: fact)
- Save a preference: "I prefer Python over Java for ML" (type: preference)
- Save a decision: "Decided to use PostgreSQL for the project" (type: decision)

Parameters:
- content: The memory content (required)
- memory_type: Type of memory (default: fact)
- topics: Topics/tags (auto-extracted if not provided)
- importance: Importance level (default: medium)
- source_context: Where this info came from
- timestamp: When this occurred (defaults to now)""",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The memory content to save",
                    "minLength": 1
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["fact", "preference", "decision", "event", "insight", "correction"],
                    "default": "fact"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topics/tags (auto-extracted if not provided)"
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium"
                },
                "source_context": {
                    "type": "string",
                    "description": "Context about where this memory came from"
                },
                "timestamp": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When this occurred (ISO format)"
                }
            },
            "required": ["content"]
        }
    ),
    Tool(
        name="save_conversation_summary",
        description="""Save a summary of a conversation.

Use this to record the key points and outcomes of a conversation
for future reference.

Parameters:
- summary: Summary of the conversation (required)
- topics: Main topics discussed
- key_points: Bullet points of key takeaways
- started_at/ended_at: Conversation time range""",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of the conversation",
                    "minLength": 1
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "started_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "ended_at": {
                    "type": "string",
                    "format": "date-time"
                }
            },
            "required": ["summary"]
        }
    ),

    # Entity Tools
    Tool(
        name="list_entities",
        description="""List all known entities in the memory palace.

Shows people, organizations, locations, projects, and concepts that have
been mentioned in memories. Useful for seeing who/what you've recorded
information about.

Examples:
- "Show all people in my memory palace"
- "List organizations I've mentioned"
- "What entities do I know about?"

Parameters:
- entity_type: Filter by type (PERSON, ORG, LOCATION, PROJECT, CONCEPT)
- limit: Max results (default 50)
- sort_by: Sort order (count, name, recent)""",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["PERSON", "ORG", "LOCATION", "PROJECT", "CONCEPT", "ANY"]
                },
                "limit": {
                    "type": "integer",
                    "default": 50
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["count", "name", "recent"],
                    "default": "count"
                }
            }
        }
    ),
    Tool(
        name="get_entity_profile",
        description="""Get comprehensive profile of a specific entity.

Returns detailed information including when first/last mentioned,
related topics, key facts, and recent memories.

Use this to get a complete picture of everything you know about
a person, organization, or concept.

Examples:
- "Tell me everything about John Smith"
- "Get profile for Acme Corp"
- "What do I know about the ML project?"

Parameters:
- entity_name: Name of the entity (required)
- entity_type: Type for disambiguation
- include_memories: Include recent memories (default true)
- memory_limit: Max memories to include (default 10)""",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "Name of the entity"
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["PERSON", "ORG", "LOCATION", "PROJECT", "CONCEPT"]
                },
                "include_memories": {
                    "type": "boolean",
                    "default": True
                },
                "memory_limit": {
                    "type": "integer",
                    "default": 10
                }
            },
            "required": ["entity_name"]
        }
    ),

    # Management Tools
    Tool(
        name="update_memory",
        description="""Update an existing memory.

Use this to correct or enhance a previously stored memory.
Only provide the fields you want to change.

Parameters:
- memory_id: ID of the memory to update (required)
- content: New content
- topics: New topics
- importance: New importance level
- memory_type: New memory type""",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "ID of the memory to update"
                },
                "content": {
                    "type": "string",
                    "description": "New content"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "importance": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"]
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["fact", "preference", "decision", "event", "insight", "correction"]
                }
            },
            "required": ["memory_id"]
        }
    ),
    Tool(
        name="delete_memory",
        description="""Delete a memory from the palace.

This permanently removes a memory. Use with caution.
You must set confirm=true to actually delete.

Parameters:
- memory_id: ID of the memory to delete (required)
- confirm: Must be true to confirm deletion (required)""",
        inputSchema={
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "ID of the memory to delete"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Confirm deletion (must be true)"
                }
            },
            "required": ["memory_id", "confirm"]
        }
    ),
    Tool(
        name="get_memory_stats",
        description="""Get statistics about the memory palace.

Returns counts, distributions, and top items including:
- Total memories, entities, topics, conversations
- Memories by type and importance
- Date range of memories
- Most mentioned topics and entities

Use this to understand the overall state of your memory palace.""",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),

    # Browse Tools
    Tool(
        name="list_topics",
        description="""List all topics/tags in the memory palace.

Shows topics that have been extracted from or assigned to memories.
Useful for seeing what subjects you've recorded information about.

Parameters:
- limit: Max results (default 50)
- sort_by: Sort order (count, name, recent)
- min_count: Minimum memory count to include (default 1)""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 50
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["count", "name", "recent"],
                    "default": "count"
                },
                "min_count": {
                    "type": "integer",
                    "default": 1
                }
            }
        }
    ),
    Tool(
        name="list_recent",
        description="""List the most recent memories.

Shows memories in reverse chronological order (newest first).
Use this to see what was recently recorded.

Parameters:
- limit: Number of memories (default 20)
- memory_types: Filter by specific types
- include_conversations: Include conversation summaries (default true)""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 20
                },
                "memory_types": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "include_conversations": {
                    "type": "boolean",
                    "default": True
                }
            }
        }
    ),
]


class MemoryPalaceServer:
    """MCP Server for Memory Palace."""

    def __init__(self):
        """Initialize the server."""
        self.server = Server("memory-palace")
        self.vector_db: Optional[VectorDB] = None
        self.metadata_db: Optional[MetadataDB] = None
        self.query_engine: Optional[QueryEngine] = None
        self._initialized = False

        # Register handlers
        self._register_handlers()

    async def initialize(self) -> None:
        """Initialize database connections."""
        if self._initialized:
            return

        settings = get_settings()

        # Initialize vector database
        self.vector_db = VectorDB(
            persist_path=settings.storage.chroma_path,
            embedding_model=settings.embeddings.model
        )
        await self.vector_db.initialize()

        # Initialize metadata database
        self.metadata_db = MetadataDB(settings.storage.sqlite_path)
        await self.metadata_db.initialize()

        # Initialize query engine
        self.query_engine = QueryEngine(self.vector_db, self.metadata_db)

        self._initialized = True
        logger.info("Memory Palace server initialized")

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """Return all available tools."""
            return TOOL_DEFINITIONS

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            # Ensure initialized
            await self.initialize()

            try:
                result = await self._execute_tool(name, arguments)
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str)
                )]
            except Exception as e:
                logger.error(f"Tool execution error: {e}", exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": True,
                        "message": str(e)
                    }, indent=2)
                )]

        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="memory-palace://stats",
                    name="Memory Palace Statistics",
                    description="Current statistics about the memory palace",
                    mimeType="application/json"
                )
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a resource."""
            await self.initialize()

            if uri == "memory-palace://stats":
                stats = await get_memory_stats(self.query_engine)
                return json.dumps(stats, indent=2, default=str)

            raise ValueError(f"Unknown resource: {uri}")

    async def _execute_tool(self, name: str, arguments: dict) -> dict:
        """Execute a tool by name."""
        # Parse date strings to date objects
        arguments = self._parse_dates(arguments)

        if name == "search_memories":
            params = MemorySearchParams(**arguments)
            return await search_memories(self.query_engine, params)

        elif name == "search_by_entity":
            params = EntitySearchParams(**arguments)
            return await search_by_entity(self.query_engine, params)

        elif name == "search_by_date_range":
            params = DateRangeSearchParams(**arguments)
            return await search_by_date_range(self.query_engine, params)

        elif name == "timeline_query":
            params = TimelineQueryParams(**arguments)
            return await timeline_query(self.query_engine, params)

        elif name == "get_topic_evolution":
            params = TopicEvolutionParams(**arguments)
            return await get_topic_evolution(self.query_engine, params)

        elif name == "save_memory":
            params = MemorySaveParams(**arguments)
            return await save_memory(self.vector_db, self.metadata_db, params)

        elif name == "save_conversation_summary":
            params = ConversationSummaryParams(**arguments)
            return await save_conversation_summary(self.vector_db, self.metadata_db, params)

        elif name == "list_entities":
            params = EntityListParams(**arguments)
            return await list_entities(self.metadata_db, params)

        elif name == "get_entity_profile":
            params = EntityProfileParams(**arguments)
            return await get_entity_profile(self.query_engine, params)

        elif name == "update_memory":
            params = MemoryUpdateParams(**arguments)
            return await update_memory(self.vector_db, self.metadata_db, params)

        elif name == "delete_memory":
            params = MemoryDeleteParams(**arguments)
            return await delete_memory(self.vector_db, self.metadata_db, params)

        elif name == "get_memory_stats":
            return await get_memory_stats(self.query_engine)

        elif name == "list_topics":
            params = TopicListParams(**arguments)
            return await list_topics(self.metadata_db, params)

        elif name == "list_recent":
            params = RecentMemoriesParams(**arguments)
            return await list_recent(self.query_engine, params)

        else:
            raise ValueError(f"Unknown tool: {name}")

    def _parse_dates(self, arguments: dict) -> dict:
        """Parse date strings in arguments."""
        from datetime import date, datetime

        result = arguments.copy()

        for key in ['date_from', 'date_to']:
            if key in result and result[key]:
                value = result[key]
                if isinstance(value, str):
                    # Try parsing as date
                    try:
                        result[key] = date.fromisoformat(value)
                    except ValueError:
                        try:
                            # Try parsing as datetime
                            result[key] = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                        except ValueError:
                            pass

        for key in ['timestamp', 'started_at', 'ended_at']:
            if key in result and result[key]:
                value = result[key]
                if isinstance(value, str):
                    try:
                        result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        pass

        return result

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.metadata_db:
            await self.metadata_db.close()
        logger.info("Memory Palace server cleanup complete")


def create_server() -> MemoryPalaceServer:
    """Create a new Memory Palace server instance."""
    return MemoryPalaceServer()


async def run_stdio_server() -> None:
    """Run the MCP server using stdio transport."""
    # Load settings
    load_settings()

    server_instance = create_server()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server_instance.server.run(
                read_stream,
                write_stream,
                server_instance.server.create_initialization_options()
            )
    finally:
        await server_instance.cleanup()


def main():
    """Entry point for stdio server."""
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
