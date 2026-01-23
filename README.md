# Memory Palace - MCP Server for Personal RAG System

Memory Palace is an MCP (Model Context Protocol) server that provides a personal memory system for AI assistants. It enables Claude Desktop, LibreChat, Open WebUI, and other MCP-compatible clients to store, search, and recall personal information, preferences, decisions, and insights.

## Features

- **Semantic Search**: Find memories using natural language queries with vector similarity search
- **Entity Tracking**: Automatically extract and track people, organizations, locations, projects, and concepts
- **Topic Management**: Organize memories by topics with automatic extraction
- **Timeline Queries**: Trace how topics evolved over time
- **Dual Transport**: Support for both stdio (Claude Desktop) and HTTP/SSE (web clients)
- **Local Storage**: All data stored locally using ChromaDB and SQLite

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd secondabrain

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Download spaCy model for entity extraction
python -m spacy download en_core_web_sm

# Initialize databases
python -m memory_palace.scripts.setup_db
```

### Claude Desktop Setup

1. Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "python",
      "args": ["-m", "memory_palace.scripts.run_stdio"],
      "env": {
        "MEMORY_PALACE_PATH": "/path/to/your/memory_palace/data"
      }
    }
  }
}
```

2. Restart Claude Desktop
3. The memory palace tools will be available in your conversations

### HTTP Server (for Open WebUI, LibreChat)

```bash
# Start the HTTP server
python -m memory_palace.scripts.run_http

# Server runs on http://127.0.0.1:8765 by default
# API docs available at http://127.0.0.1:8765/docs
```

## Available Tools

### Search Tools

| Tool | Description |
|------|-------------|
| `search_memories` | Semantic search with filters for date, topics, entities, types |
| `search_by_entity` | Find all memories mentioning a specific person, org, or concept |
| `search_by_date_range` | Find memories from a specific time period |

### Timeline Tools

| Tool | Description |
|------|-------------|
| `timeline_query` | Get chronological timeline of memories for a topic |
| `get_topic_evolution` | Analyze how thinking on a topic changed over time |

### Save Tools

| Tool | Description |
|------|-------------|
| `save_memory` | Store a new memory with automatic entity/topic extraction |
| `save_conversation_summary` | Store a summary of a conversation |

### Entity Tools

| Tool | Description |
|------|-------------|
| `list_entities` | List all known entities (people, orgs, locations, etc.) |
| `get_entity_profile` | Get comprehensive profile of an entity |

### Management Tools

| Tool | Description |
|------|-------------|
| `update_memory` | Modify an existing memory |
| `delete_memory` | Remove a memory (requires confirmation) |
| `get_memory_stats` | Get statistics about the memory palace |

### Browse Tools

| Tool | Description |
|------|-------------|
| `list_topics` | List all topics with counts |
| `list_recent` | List most recent memories |

## Example Usage

### Saving Memories

```
User: Remember that John Smith's birthday is March 15th
Claude: [Uses save_memory tool]
"I've saved that John Smith's birthday is March 15th."

User: I decided to use PostgreSQL for the new project
Claude: [Uses save_memory with type "decision"]
"I've recorded your decision to use PostgreSQL."
```

### Searching Memories

```
User: What do I know about the ML project?
Claude: [Uses search_memories with query "ML project"]
"Based on your memory palace, here's what I found about the ML project..."

User: What did John Smith say about the budget?
Claude: [Uses search_by_entity for "John Smith"]
"I found these memories mentioning John Smith..."
```

### Timeline Queries

```
User: Show me how my thoughts on Python evolved over the last year
Claude: [Uses get_topic_evolution with topic "Python"]
"Here's how your thinking about Python has evolved..."
```

## Configuration

### Default Settings

Configuration is loaded from `~/.memory_palace/settings.yaml` or via environment variables:

```yaml
storage:
  chroma_path: "./data/chroma_db"
  sqlite_path: "./data/metadata.db"

embeddings:
  model: "all-MiniLM-L6-v2"

extraction:
  spacy_model: "en_core_web_sm"
  max_topics_per_memory: 5

server:
  http:
    host: "127.0.0.1"
    port: 8765

search:
  default_limit: 10
  max_limit: 100
  default_min_relevance: 0.5
```

### Environment Variables

- `MEMORY_PALACE_PATH`: Base path for data storage
- `MEMORY_PALACE_CONFIG`: Path to configuration file
- `MEMORY_PALACE_HTTP_HOST`: HTTP server host
- `MEMORY_PALACE_HTTP_PORT`: HTTP server port

## Memory Types

- **fact**: Factual information (default)
- **preference**: Personal preferences or opinions
- **decision**: Decisions made
- **event**: Things that happened
- **insight**: Realizations or learnings
- **correction**: Corrections to previous information
- **conversation**: Conversation summaries

## Entity Types

- **PERSON**: People's names
- **ORG**: Organizations, companies
- **LOCATION**: Places, addresses
- **PROJECT**: Projects
- **CONCEPT**: Technologies, ideas, abstract concepts

## API Reference (HTTP Server)

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/tools` | List all available tools |
| GET | `/tools/{name}` | Get tool information |
| POST | `/tools/{name}` | Call a tool |
| GET | `/sse/tools/{name}` | Call tool with SSE streaming |
| POST | `/tools/batch` | Batch tool calls |
| POST | `/mcp` | MCP JSON-RPC endpoint |

### Example API Call

```bash
curl -X POST "http://localhost:8765/tools/search_memories" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"query": "Python programming", "limit": 5}}'
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=memory_palace
```

### Project Structure

```
memory_palace/
├── mcp/
│   ├── server.py              # Main MCP server
│   ├── schemas.py             # Pydantic schemas
│   ├── tools/                 # Tool implementations
│   │   ├── search.py
│   │   ├── timeline.py
│   │   ├── save.py
│   │   ├── entities.py
│   │   ├── manage.py
│   │   └── browse.py
│   └── transports/
│       ├── stdio_transport.py # Claude Desktop
│       └── http_transport.py  # Web clients
├── core/
│   ├── vector_db.py           # ChromaDB wrapper
│   ├── metadata_db.py         # SQLite metadata
│   ├── query_engine.py        # Unified search
│   ├── metadata_extractor.py  # NER & topic extraction
│   └── models.py              # Data models
├── config/
│   ├── settings.py            # Configuration loader
│   └── default_settings.yaml
├── scripts/
│   ├── run_stdio.py           # Claude Desktop entry
│   ├── run_http.py            # HTTP server entry
│   └── setup_db.py            # Database setup
└── tests/
```

## Troubleshooting

### spaCy Model Not Found

```bash
python -m spacy download en_core_web_sm
```

### ChromaDB Issues

Ensure you have enough disk space and that the data directory is writable.

### Claude Desktop Not Connecting

1. Check the configuration file path is correct
2. Verify Python is in your PATH
3. Check Claude Desktop logs for errors

## Future Enhancements

- [ ] Advanced topic extraction using KeyBERT/LLM
- [ ] Sentiment analysis for memories
- [ ] Memory deduplication
- [ ] Periodic automatic summaries
- [ ] Embedding cache for faster queries
- [ ] Conversation threading

## License

MIT License

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.
