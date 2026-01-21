# Second Brain: LibreChat + Memory Palace

A ChatGPT-style web interface powered by Claude, with persistent memory capabilities through a local MCP (Model Context Protocol) server.

## Overview

This project sets up [LibreChat](https://github.com/danny-avila/LibreChat) as a polished web frontend that connects to:
- **Anthropic API** (Claude Sonnet 4, Opus 4, Haiku 4)
- **Memory Palace MCP Server** for persistent, searchable memory
- **Local RAG** for document processing and vector search

Everything runs locally via Docker, giving you a private, powerful AI assistant with long-term memory.

## Features

- ChatGPT-level UX with conversation history
- Claude 4 family models (Sonnet, Opus, Haiku)
- Persistent memory via Memory Palace MCP
- Semantic search across all conversations
- Timeline queries for chronological recall
- Entity tracking and relationship mapping
- Multi-user support with authentication
- File uploads and document processing
- Dark/light theme support

## Prerequisites

- Docker and Docker Compose
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Memory Palace MCP server (your existing installation)
- (Optional) Node.js 18+ for development

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/secondabrain.git
cd secondabrain
./scripts/setup.sh
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Required: Add your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Required: Point to your Memory Palace installation
MEMORY_PALACE_PATH=/path/to/your/memory_palace
```

### 3. Launch

```bash
docker compose up -d
```

### 4. Access

Open http://localhost:3080 in your browser, create an account, and start chatting!

## Configuration

### Environment Variables (.env)

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Yes |
| `MEMORY_PALACE_PATH` | Path to Memory Palace MCP server | Yes |
| `MEMORY_PALACE_DATA` | Data directory for memories | No (default: `./data/memory_palace`) |
| `PORT` | Web UI port | No (default: `3080`) |
| `CREDS_KEY` | Encryption key (auto-generated) | Yes |
| `CREDS_IV` | Encryption IV (auto-generated) | Yes |
| `JWT_SECRET` | JWT secret (auto-generated) | Yes |

### LibreChat Configuration (librechat.yaml)

The main configuration file controls:
- MCP server connections
- Model availability and settings
- UI features and appearance
- Rate limiting and security

See [librechat.yaml](./librechat.yaml) for full documentation.

### MCP Server Configuration

Memory Palace is configured as an MCP server using stdio transport:

```yaml
mcpServers:
  memory-palace:
    command: "python"
    args:
      - "-m"
      - "memory_palace.scripts.run_stdio"
    cwd: "/app/memory_palace"
    env:
      MEMORY_PALACE_DATA: "/app/memory_palace_data"
    timeout: 30000
```

## Memory Palace Tools

Once connected, Claude has access to these memory tools:

| Tool | Description |
|------|-------------|
| `search_memories` | Semantic search across all stored memories |
| `save_memory` | Store new information for later recall |
| `timeline_query` | Retrieve memories chronologically |
| `list_entities` | Show known people, projects, concepts |
| `get_entity_profile` | Detailed view of a specific entity |
| `topic_evolution` | Track how a topic has developed over time |

### Example Interactions

```
You: "Search my memories for our discussions about the trading project"
Claude: [Uses search_memories] Found 5 relevant memories about your trading project...

You: "Remember that I prefer TypeScript over JavaScript for new projects"
Claude: [Uses save_memory] I've saved that preference to your memory palace.

You: "Show me a timeline of our architecture decisions this month"
Claude: [Uses timeline_query] Here are your architecture decisions chronologically...
```

## Project Structure

```
secondabrain/
├── docker-compose.yml      # Main Docker configuration
├── librechat.yaml          # LibreChat + MCP configuration
├── .env.example            # Environment template
├── .env                    # Your configuration (gitignored)
├── config/                 # Additional config files
├── scripts/
│   ├── setup.sh           # Initial setup script
│   ├── health-check.sh    # Service health verification
│   └── test-mcp.sh        # MCP server testing
├── data/                   # Persistent data (gitignored)
│   ├── mongodb/           # Conversation database
│   ├── redis/             # Cache
│   ├── memory_palace/     # Memory Palace data
│   ├── rag/               # Vector embeddings
│   ├── uploads/           # User uploads
│   └── logs/              # Application logs
└── docs/                   # Additional documentation
```

## Commands

### Service Management

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

### Database Management

```bash
# Backup MongoDB
docker exec librechat-mongodb mongodump --out /data/backup

# Backup Memory Palace data
cp -r data/memory_palace data/memory_palace_backup
```

## Troubleshooting

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
