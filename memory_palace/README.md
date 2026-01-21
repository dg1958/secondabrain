# Memory Palace MCP Server

Personal AI memory system accessible via Model Context Protocol (MCP).

Memory Palace stores and retrieves personal knowledge, facts, preferences, decisions, and conversation histories. It works seamlessly with Claude Desktop, LibreChat, Open WebUI, Cursor, and other MCP-compatible clients.

## Features

- **Semantic Search**: Find memories by meaning, not just keywords
- **Timeline Reconstruction**: Trace how your thinking on any topic evolved
- **Entity Tracking**: Automatically extract and track people, organizations, projects
- **Topic Organization**: Auto-categorize memories by topic
- **Multi-Client Support**: Works with Claude Desktop, LibreChat, Open WebUI, Cursor
- **Triple Transport**: stdio (primary), HTTP REST, and SSE transports
- **Local Storage**: ChromaDB + SQLite, no cloud dependencies

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/example/memory-palace.git
cd memory-palace

# Install dependencies
pip install -r requirements.txt

# Optional: Install spaCy model for enhanced entity extraction
python -m spacy download en_core_web_sm

# Initialize databases
python -m memory_palace.scripts.setup_db

# Verify installation
python -m memory_palace.scripts.setup_db --verify
```

### Claude Desktop Configuration

Add to your Claude Desktop config file:

**Location:**
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "python",
      "args": ["-m", "memory_palace.scripts.run_stdio"],
      "cwd": "/path/to/memory_palace",
      "env": {
        "MEMORY_PALACE_DATA": "/path/to/memory_palace/data"
      }
    }
  }
}
```

### LibreChat Configuration

Add to your `librechat.yaml`:

```yaml
mcpServers:
  memory-palace:
    command: "python"
    args:
      - "-m"
      - "memory_palace.scripts.run_stdio"
    cwd: "/path/to/memory_palace"
    env:
      MEMORY_PALACE_DATA: "/path/to/memory_palace/data"
    timeout: 30000
```

### Open WebUI

1. Start the HTTP server:
   ```bash
   python -m memory_palace.scripts.run_http
   ```

2. Install the function from `examples/open_webui_function.py` in Open WebUI

### Cursor / Windsurf

Same as Claude Desktop - uses standard MCP stdio transport.

## Available Tools

| Tool | Description |
|------|-------------|
| `search_memories` | Semantic search with filters for type, importance, date, topics, entities |
| `search_by_entity` | Find all memories mentioning a specific person, org, or concept |
| `search_by_date_range` | Get memories from a specific time period |
| `timeline_query` | Chronological reconstruction of a topic over time |
| `get_topic_evolution` | Analyze how your thinking on a topic changed |
| `save_memory` | Store new information with auto-extraction of entities and topics |
| `save_conversation_summary` | Store a conversation summary with key points and decisions |
| `bulk_import` | Import multiple memories at once |
| `list_entities` | Browse all known entities (people, orgs, etc.) |
| `get_entity_profile` | Get comprehensive info about an entity |
| `update_memory` | Modify an existing memory |
| `delete_memory` | Remove a memory |
| `get_memory_stats` | Get statistics about your memory palace |
| `list_topics` | Browse all topics with memory counts |
| `list_recent` | Get recent memories |

## Example Queries

Once connected, you can ask:

- "What have we discussed about project management?"
- "Remember that I prefer morning meetings"
- "Show me everything about John Smith"
- "Timeline of my thoughts on AI safety"
- "What decisions did we make last month?"
- "List all people we've discussed"

## Configuration

Environment variables:
- `MEMORY_PALACE_DATA`: Data directory path
- `MEMORY_PALACE_CONFIG`: Path to custom settings YAML

See `config/default_settings.yaml` for all options.

## Architecture

```
memory_palace/
├── mcp/                    # MCP server implementation
│   ├── server.py           # Main server with tool definitions
│   ├── schemas.py          # Pydantic models for API
│   ├── tools/              # Tool implementations
│   │   ├── search.py       # Search tools
│   │   ├── timeline.py     # Timeline tools
│   │   ├── save.py         # Save tools
│   │   ├── entities.py     # Entity tools
│   │   ├── manage.py       # Management tools
│   │   └── browse.py       # Browse tools
│   └── transports/         # Transport implementations
│       ├── stdio_transport.py   # For Claude Desktop, LibreChat, Cursor
│       └── http_transport.py    # For Open WebUI, web clients
├── core/                   # Core functionality
│   ├── vector_db.py        # ChromaDB wrapper
│   ├── metadata_db.py      # SQLite for metadata
│   ├── query_engine.py     # Unified query interface
│   ├── metadata_extractor.py # NER and topic extraction
│   └── models.py           # Data models
├── config/                 # Configuration
│   ├── settings.py         # Config loader
│   └── default_settings.yaml
├── scripts/                # Entry points
│   ├── run_stdio.py        # stdio transport entry
│   ├── run_http.py         # HTTP server entry
│   └── setup_db.py         # Database setup
└── examples/               # Client configurations
```

## Storage

- **Vector Storage**: ChromaDB for semantic embeddings
- **Metadata Storage**: SQLite for structured data, relationships, and indices
- **Default Location**: `./data/` (configurable)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black memory_palace/
ruff check memory_palace/

# Type check
mypy memory_palace/
```

## License

MIT License
