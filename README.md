# Second Brain: Memory Palace + LibreChat Integration

A personal AI assistant system with persistent memory. Combines Memory Palace (an MCP server for semantic memory storage and retrieval) with LibreChat (a ChatGPT-style web interface) for a complete, self-hosted AI experience.

## Overview

This project provides:
- **Memory Palace MCP Server** - Personal RAG system with semantic search, entity tracking, and timeline queries
- **LibreChat Web UI** - ChatGPT-level UX with conversation history and multi-model support
- **Local Storage** - All data stored locally using ChromaDB and SQLite

Everything runs locally via Docker, giving you a private, powerful AI assistant with long-term memory.

## Features

### Memory Palace
- **Semantic Search**: Find memories using natural language queries with vector similarity search
- **Entity Tracking**: Automatically extract and track people, organizations, locations, projects, and concepts
- **Topic Management**: Organize memories by topics with automatic extraction
- **Timeline Queries**: Trace how topics evolved over time
- **Dual Transport**: Support for both stdio (Claude Desktop) and HTTP/SSE (web clients)

### LibreChat Integration
- ChatGPT-level UX with conversation history
- Claude 4 family models (Sonnet, Opus, Haiku)
- Multi-user support with authentication
- File uploads and document processing
- Dark/light theme support

## Quick Start

### Option 1: Memory Palace Standalone (for Claude Desktop)

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

#### Claude Desktop Setup

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

### Option 2: Full Stack with LibreChat (Docker)

#### Prerequisites
- Docker and Docker Compose
- Anthropic API key ([get one here](https://console.anthropic.com/))

#### Setup

```bash
# Clone and setup
git clone <repository-url>
cd secondabrain
./scripts/setup.sh

# Edit .env with your settings
# Required: Add your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Launch
docker compose up -d

# Access at http://localhost:3080
```

### HTTP Server (for Open WebUI, custom clients)

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

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Yes (Docker) |
| `MEMORY_PALACE_PATH` | Base path for data storage | Yes |
| `MEMORY_PALACE_CONFIG` | Path to configuration file | No |
| `MEMORY_PALACE_HTTP_HOST` | HTTP server host | No |
| `MEMORY_PALACE_HTTP_PORT` | HTTP server port | No |

### LibreChat Configuration (librechat.yaml)

For Docker deployments, the main configuration file controls:
- MCP server connections
- Model availability and settings
- UI features and appearance
- Rate limiting and security

See [librechat.yaml](./librechat.yaml) for full documentation.

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

## Project Structure

```
secondabrain/
├── docker-compose.yml          # Docker configuration for full stack
├── librechat.yaml              # LibreChat + MCP configuration
├── pyproject.toml              # Python package configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── memory_palace/
│   ├── mcp/
│   │   ├── server.py           # Main MCP server
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── tools/              # Tool implementations
│   │   │   ├── search.py
│   │   │   ├── timeline.py
│   │   │   ├── save.py
│   │   │   ├── entities.py
│   │   │   ├── manage.py
│   │   │   └── browse.py
│   │   └── transports/
│   │       ├── stdio_transport.py  # Claude Desktop
│   │       └── http_transport.py   # Web clients
│   ├── core/
│   │   ├── vector_db.py        # ChromaDB wrapper
│   │   ├── metadata_db.py      # SQLite metadata
│   │   ├── query_engine.py     # Unified search
│   │   ├── metadata_extractor.py # NER & topic extraction
│   │   └── models.py           # Data models
│   ├── api/                    # REST API (standalone)
│   ├── cli/                    # Command-line interface
│   ├── ingestion/              # Document processing
│   ├── query/                  # Query engine components
│   ├── storage/                # Storage backends
│   ├── config/
│   │   ├── settings.py         # Configuration loader
│   │   ├── schema.py           # Data schemas
│   │   └── settings.yaml       # Default settings
│   └── tests/                  # Test suite
└── scripts/
    ├── setup.sh                # Initial setup
    ├── health-check.sh         # Service health verification
    └── test-mcp.sh             # MCP server testing
```

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

## Commands

### Service Management (Docker)

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f api

# Restart a specific service
docker compose restart api

# Check service status
docker compose ps
```

### Health & Testing

```bash
# Run health check
./scripts/health-check.sh

# Test MCP server connectivity
./scripts/test-mcp.sh

# Test with MCP Inspector
npx @modelcontextprotocol/inspector python -m memory_palace.scripts.run_stdio
```

### Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=memory_palace
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

### LibreChat Won't Start

1. Check logs: `docker compose logs api`
2. Verify environment: Ensure `.env` has all required variables
3. Check ports: Make sure 3080 isn't in use

### MCP Server Not Connecting

1. Test standalone:
   ```bash
   cd /path/to/memory_palace
   python -m memory_palace.scripts.run_stdio
   ```

2. Check Docker logs for MCP errors:
   ```bash
   docker compose logs api | grep -i mcp
   ```

3. Verify paths in `librechat.yaml` match your Docker volumes

### Memory Not Persisting

1. Check data directory permissions
2. Verify volume mounts in `docker-compose.yml`
3. Ensure ChromaDB/SQLite paths are correct

### API Key Issues

1. Verify your Anthropic API key at https://console.anthropic.com/
2. Check the key is correctly set in `.env`
3. Ensure no extra spaces or quotes around the key

## Security Notes

- The `.env` file contains secrets - never commit it
- Default setup is for local/single-user use
- For production, enable proper authentication
- Consider network isolation for sensitive data

## Future Enhancements

- [ ] Advanced topic extraction using KeyBERT/LLM
- [ ] Sentiment analysis for memories
- [ ] Memory deduplication
- [ ] Periodic automatic summaries
- [ ] Embedding cache for faster queries
- [ ] Conversation threading

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [LibreChat](https://github.com/danny-avila/LibreChat) - The web UI framework
- [Anthropic](https://anthropic.com/) - Claude AI models
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
