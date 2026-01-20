"""
MCP Server for Memory Palace.

This module implements the Model Context Protocol server that exposes
memory palace functionality to MCP-compatible clients like Claude Desktop,
LibreChat, Open WebUI, and Cursor.
"""

import json
import logging
from typing import Any, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceTemplate,
)

from .schemas import (
    # Search
    SearchMemoriesInput,
    SearchByEntityInput,
    SearchByDateRangeInput,
    # Timeline
    TimelineQueryInput,
    TopicEvolutionInput,
    # Save
    SaveMemoryInput,
    SaveConversationSummaryInput,
    BulkImportInput,
    # Entities
    ListEntitiesInput,
    GetEntityProfileInput,
    # Management
    UpdateMemoryInput,
    DeleteMemoryInput,
    GetMemoryStatsInput,
    # Browse
    ListTopicsInput,
    ListRecentInput,
)
from .tools import (
    search_memories,
    search_by_entity,
    search_by_date_range,
    timeline_query,
    get_topic_evolution,
    save_memory,
    save_conversation_summary,
    bulk_import,
    list_entities,
    get_entity_profile,
    update_memory,
    delete_memory,
    get_memory_stats,
    list_topics,
    list_recent,
)

logger = logging.getLogger(__name__)

# Create the MCP server instance
server = Server("memory-palace")

# ============ TOOL DEFINITIONS ============
# These are the tools exposed to MCP clients

TOOLS = [
    # Search Tools
    Tool(
        name="search_memories",
        description="""Search the memory palace using semantic search with optional filters.

This is the primary search tool for finding relevant memories. It uses AI embeddings
for semantic matching (not just keyword matching), so it understands meaning and context.

Use this when:
- Looking for information about a topic
- Finding relevant past discussions
- Searching for specific types of memories (facts, decisions, preferences)

The search supports filtering by:
- Memory type (fact, preference, decision, event, insight)
- Importance level (low, medium, high, critical)
- Date range
- Topics
- Entities (people, organizations, etc.)

Examples:
- "What have we discussed about Python async patterns?"
- "Find all decisions made about the database architecture"
- "Search for preferences related to code style"
""",
        inputSchema=SearchMemoriesInput.model_json_schema(),
    ),
    Tool(
        name="search_by_entity",
        description="""Find all memories mentioning a specific entity (person, organization, project, etc.).

Use this when you want to know everything stored about a particular:
- Person (colleague, friend, contact)
- Organization (company, team, group)
- Project or product
- Location
- Concept or topic

This returns memories ordered by relevance and recency.

Examples:
- "Show me everything about John Smith"
- "What do we know about Acme Corporation?"
- "Find all mentions of the Memory Palace project"
""",
        inputSchema=SearchByEntityInput.model_json_schema(),
    ),
    Tool(
        name="search_by_date_range",
        description="""Get all memories within a specific date range.

Use this when you want to:
- Find what was discussed during a particular period
- Review memories from a specific week/month/year
- Look up events that happened in a time window

Dates should be in YYYY-MM-DD format.

Examples:
- "What was discussed between 2024-01-01 and 2024-03-31?"
- "Show memories from the week of 2024-06-15"
""",
        inputSchema=SearchByDateRangeInput.model_json_schema(),
    ),

    # Timeline Tools
    Tool(
        name="timeline_query",
        description="""Reconstruct a chronological timeline for a topic.

This tool helps understand how discussions or events about a topic
unfolded over time. It groups memories into time periods (day, week,
month, quarter, year) and provides summaries.

Use this when:
- You want to see the history of a topic
- Understanding how a project evolved
- Tracing the development of an idea
- Reviewing past discussions chronologically

Examples:
- "Show me a timeline of the database migration project"
- "How did our AI safety discussions evolve over the past year?"
""",
        inputSchema=TimelineQueryInput.model_json_schema(),
    ),
    Tool(
        name="get_topic_evolution",
        description="""Analyze how thinking on a topic evolved over time.

This provides a higher-level analysis than timeline_query, showing:
- Different phases of development
- How sentiment changed over time
- Key themes in each phase

Use this for understanding shifts in perspective or approach.

Examples:
- "How has my thinking about remote work evolved?"
- "Analyze the evolution of our API design approach"
""",
        inputSchema=TopicEvolutionInput.model_json_schema(),
    ),

    # Save Tools
    Tool(
        name="save_memory",
        description="""Save a new memory to the palace.

Use this to remember:
- Facts: Objective information ("Python 3.12 adds new typing features")
- Preferences: Personal choices ("I prefer dark mode for coding")
- Decisions: Choices made ("We decided to use PostgreSQL for the project")
- Events: Things that happened ("Met with Sarah to discuss the roadmap")
- Insights: Realizations or conclusions ("The bottleneck is in the database layer")

The system automatically extracts:
- Entities (people, organizations, etc.)
- Topics
- Sentiment

You can also manually specify topics and importance.

Examples:
- Save a fact: "Python 3.12 introduced new typing syntax for generics"
- Save a preference: "I prefer 4-space indentation over tabs"
- Save a decision: "Team decided to migrate to AWS Lambda for serverless functions"
""",
        inputSchema=SaveMemoryInput.model_json_schema(),
    ),
    Tool(
        name="save_conversation_summary",
        description="""Save a summary of a conversation.

This is specifically designed for storing structured conversation summaries
with key points, decisions made, and action items.

Use at the end of important conversations to capture:
- Main summary
- Key points discussed
- Decisions that were made
- Action items identified
- Topics discussed
- Participants

This helps maintain continuity across conversations.

Example:
Save a summary with:
- summary: "Discussed the Q2 roadmap and prioritized mobile features"
- key_points: ["Mobile app launch is top priority", "Need to hire 2 more developers"]
- decisions_made: ["Will use React Native for mobile", "Launch target is June 1st"]
- action_items: ["Create job postings for mobile devs", "Set up React Native project"]
""",
        inputSchema=SaveConversationSummaryInput.model_json_schema(),
    ),
    Tool(
        name="bulk_import",
        description="""Import multiple memories at once.

Use this for:
- Importing transcripts
- Bulk adding notes
- Migrating from other systems

Each memory is processed individually with automatic metadata extraction.

Example:
Import a list of facts from a document or transcript.
""",
        inputSchema=BulkImportInput.model_json_schema(),
    ),

    # Entity Tools
    Tool(
        name="list_entities",
        description="""List all known entities in the memory palace.

Shows all the people, organizations, projects, and other named entities
that have been mentioned in memories, along with how many times each
appears.

Use this to:
- See who/what is in the memory palace
- Find the correct name for an entity
- Discover frequently mentioned entities

Can filter by entity type (PERSON, ORG, PROJECT, etc.)
""",
        inputSchema=ListEntitiesInput.model_json_schema(),
    ),
    Tool(
        name="get_entity_profile",
        description="""Get comprehensive information about a specific entity.

Returns everything known about an entity:
- Basic information (name, type, aliases)
- Recent memories mentioning them
- Related entities (co-occurring)
- Associated topics
- Timeline of mentions

Use this to build a complete picture of a person, organization, or project.

Example:
- "Tell me everything we know about John Smith"
- "What's the full profile for Acme Corporation?"
""",
        inputSchema=GetEntityProfileInput.model_json_schema(),
    ),

    # Management Tools
    Tool(
        name="update_memory",
        description="""Update an existing memory.

Use this to:
- Correct information
- Change importance level
- Add or modify topics
- Update the content

You need the memory ID (from search results) to update.
""",
        inputSchema=UpdateMemoryInput.model_json_schema(),
    ),
    Tool(
        name="delete_memory",
        description="""Delete a memory from the palace.

Use this to remove incorrect, outdated, or unwanted memories.
Requires confirmation (confirm=true) to prevent accidents.

The memory is permanently removed from both the vector database
and metadata storage.
""",
        inputSchema=DeleteMemoryInput.model_json_schema(),
    ),
    Tool(
        name="get_memory_stats",
        description="""Get statistics about the memory palace.

Returns:
- Total number of memories
- Breakdown by type and importance
- Number of entities
- Number of topics
- Top topics and entities
- Date range of memories

Use this to understand what's in the palace at a glance.
""",
        inputSchema=GetMemoryStatsInput.model_json_schema(),
    ),

    # Browse Tools
    Tool(
        name="list_topics",
        description="""List all topics in the memory palace.

Returns topics sorted by frequency (most common first) or alphabetically,
with memory counts for each.

Use this to:
- Discover what subjects are covered
- Find topics to search for
- Understand the breadth of stored knowledge
""",
        inputSchema=ListTopicsInput.model_json_schema(),
    ),
    Tool(
        name="list_recent",
        description="""Get the most recent memories.

Use this to:
- See what was recently added
- Review recent discussions
- Catch up on recent activity

Can filter by memory type and time window (last N days).
""",
        inputSchema=ListRecentInput.model_json_schema(),
    ),
]


# ============ SERVER HANDLERS ============

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle tool execution requests."""
    logger.info(f"Tool call: {name}")
    logger.debug(f"Arguments: {arguments}")

    try:
        result = await _execute_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str, indent=2))]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        error_result = {"error": str(e), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result))]


async def _execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Execute a tool by name with arguments."""

    # Search tools
    if name == "search_memories":
        input_data = SearchMemoriesInput(**arguments)
        result = await search_memories(input_data)
        return result.model_dump()

    elif name == "search_by_entity":
        input_data = SearchByEntityInput(**arguments)
        result = await search_by_entity(input_data)
        return result.model_dump()

    elif name == "search_by_date_range":
        input_data = SearchByDateRangeInput(**arguments)
        result = await search_by_date_range(input_data)
        return result.model_dump()

    # Timeline tools
    elif name == "timeline_query":
        input_data = TimelineQueryInput(**arguments)
        result = await timeline_query(input_data)
        return result.model_dump()

    elif name == "get_topic_evolution":
        input_data = TopicEvolutionInput(**arguments)
        result = await get_topic_evolution(input_data)
        return result.model_dump()

    # Save tools
    elif name == "save_memory":
        input_data = SaveMemoryInput(**arguments)
        result = await save_memory(input_data)
        return result.model_dump()

    elif name == "save_conversation_summary":
        input_data = SaveConversationSummaryInput(**arguments)
        result = await save_conversation_summary(input_data)
        return result.model_dump()

    elif name == "bulk_import":
        input_data = BulkImportInput(**arguments)
        result = await bulk_import(input_data)
        return result.model_dump()

    # Entity tools
    elif name == "list_entities":
        input_data = ListEntitiesInput(**arguments)
        result = await list_entities(input_data)
        return result.model_dump()

    elif name == "get_entity_profile":
        input_data = GetEntityProfileInput(**arguments)
        result = await get_entity_profile(input_data)
        if result:
            return result.model_dump()
        return {"error": "Entity not found"}

    # Management tools
    elif name == "update_memory":
        input_data = UpdateMemoryInput(**arguments)
        result = await update_memory(input_data)
        if result:
            return result.model_dump()
        return {"error": "Memory not found"}

    elif name == "delete_memory":
        input_data = DeleteMemoryInput(**arguments)
        result = await delete_memory(input_data)
        return result.model_dump()

    elif name == "get_memory_stats":
        input_data = GetMemoryStatsInput(**arguments)
        result = await get_memory_stats(input_data)
        return result.model_dump()

    # Browse tools
    elif name == "list_topics":
        input_data = ListTopicsInput(**arguments)
        result = await list_topics(input_data)
        return result.model_dump()

    elif name == "list_recent":
        input_data = ListRecentInput(**arguments)
        result = await list_recent(input_data)
        return result.model_dump()

    else:
        raise ValueError(f"Unknown tool: {name}")


# ============ RESOURCES ============

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="memory://stats",
            name="Memory Palace Statistics",
            description="Overview statistics of the memory palace",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://topics",
            name="Topic List",
            description="List of all topics in the palace",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://entities",
            name="Entity List",
            description="List of all entities in the palace",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a resource by URI."""
    if uri == "memory://stats":
        input_data = GetMemoryStatsInput()
        result = await get_memory_stats(input_data)
        return json.dumps(result.model_dump(), default=str, indent=2)

    elif uri == "memory://topics":
        input_data = ListTopicsInput(limit=100)
        result = await list_topics(input_data)
        return json.dumps(result.model_dump(), default=str, indent=2)

    elif uri == "memory://entities":
        input_data = ListEntitiesInput(limit=100)
        result = await list_entities(input_data)
        return json.dumps(result.model_dump(), default=str, indent=2)

    else:
        raise ValueError(f"Unknown resource: {uri}")


@server.list_resource_templates()
async def handle_list_resource_templates() -> list[ResourceTemplate]:
    """List available resource templates."""
    return [
        ResourceTemplate(
            uriTemplate="memory://entity/{name}",
            name="Entity Profile",
            description="Profile for a specific entity",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="memory://search/{query}",
            name="Search Results",
            description="Search results for a query",
            mimeType="application/json",
        ),
    ]


# ============ INITIALIZATION ============

async def initialize() -> None:
    """Initialize the server and its dependencies."""
    from ..config import get_settings

    settings = get_settings()
    logger.info("Memory Palace MCP server initialized")
    logger.info(f"Data directory: {settings.storage.data_dir}")


def create_server() -> Server:
    """Factory function to create the server instance."""
    return server
