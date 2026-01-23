# Memory Palace 🏛️

A RAG-based personal knowledge management system that ingests conversation transcripts, stores them with rich metadata in a vector database, and enables sophisticated semantic queries over time-based personal memory data.

## Features

- **Vector Storage & Retrieval**: ChromaDB for local vector storage with sentence-transformers embeddings
- **Rich Metadata**: Automatic extraction of entities, topics, sentiment, and participants
- **Intelligent Chunking**: Semantic text chunking with configurable overlap
- **Multiple Input Formats**: Plain text, JSON transcripts, Markdown, Fireflies.ai format
- **Natural Language Queries**: Ask questions in plain English with temporal filtering
- **LLM-Powered Analysis**: Query planning and result synthesis using Claude
- **Timeline Reconstruction**: Chronological views of related memories
- **REST API**: Full HTTP API for programmatic access
- **CLI Interface**: Rich command-line interface for all operations
- **MCP Server**: Model Context Protocol server for Claude Desktop and LibreChat

## Quick Start

### Installation

```bash
# Clone the repository
cd memory_palace

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model for NER
python -m spacy download en_core_web_sm
```

### Configuration

1. Copy the settings template:
```bash
cp config/settings.yaml config/settings.local.yaml
```

2. Edit `config/settings.local.yaml` and add your API keys:
```yaml
anthropic:
  api_key: "your-anthropic-api-key"  # For LLM features

fireflies:
  api_key: "your-fireflies-api-key"  # For Fireflies.ai sync
```

Or set environment variables:
```bash
export ANTHROPIC_API_KEY="your-key-here"
export FIREFLIES_API_KEY="your-key-here"
```

### Basic Usage

```bash
# Add a quick note
python main.py add "Had a great brainstorming session about AI applications"

# Ingest files
python main.py ingest ./transcripts/

# Query your memories
python main.py query "What did I discuss about AI last month?"

# Generate a timeline
python main.py timeline "project updates"

# Start the API server
python main.py serve

# Interactive mode
python main.py interactive
```

## CLI Commands

### Ingestion

```bash
# Ingest a single file
python main.py ingest meeting.txt

# Ingest a directory
python main.py ingest ./transcripts/ --recursive

# Ingest with custom tags
python main.py ingest notes.md -t work -t important

# Ingest specific file types
python main.py ingest ./docs/ --pattern "*.md" --pattern "*.txt"

# Add a quick note
python main.py add "Meeting notes: discussed Q4 goals" -t meeting -p "Alice" -p "Bob"
```

### Querying

```bash
# Basic query
python main.py query "What are my thoughts on machine learning?"

# Query with more results
python main.py query "project discussions" -k 20

# Export results to markdown
python main.py query "AI safety" --export markdown -o results.md

# Export to JSON
python main.py query "meetings with John" --export json -o results.json

# Query without synthesis (faster)
python main.py query "budget planning" --no-synthesize
```

### Timeline

```bash
# Generate timeline for a topic
python main.py timeline "product development"

# Limit timeline entries
python main.py timeline "AI research" -k 100
```

### Fireflies.ai Sync

```bash
# Sync recent transcripts
python main.py fireflies

# Sync all transcripts
python main.py fireflies --all

# Sync transcripts from last 30 days
python main.py fireflies --since-days 30
```

### System Management

```bash
# View statistics
python main.py stats

# Start API server
python main.py serve --host 0.0.0.0 --port 8080

# Watch folder for auto-ingestion
python main.py watch -d ./incoming/ --interval 60

# Clear all data (use with caution!)
python main.py clear

# Interactive query mode
python main.py interactive
```

## MCP Server

Memory Palace can run as an MCP (Model Context Protocol) server, allowing Claude Desktop, LibreChat, and other MCP-compatible clients to use it as a tool.

### Running the MCP Server

```bash
# Run with stdio transport (for Claude Desktop)
python -m memory_palace.mcp.server

# Or use the script
python scripts/run_stdio.py

# Run with HTTP transport
python scripts/run_http.py --host 0.0.0.0 --port 9000
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "python",
      "args": ["-m", "memory_palace.mcp.server"],
      "cwd": "/path/to/memory_palace"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_memories` | Semantic search with filters |
| `search_by_entity` | Find memories about a person/org/concept |
| `search_by_date_range` | Find memories in a time period |
| `timeline_query` | Chronological view of a topic |
| `get_topic_evolution` | How thinking evolved over time |
| `save_memory` | Store a new memory |
| `save_conversation_summary` | Store conversation summary |
| `list_entities` | List known entities |
| `get_entity_profile` | Detailed entity information |
| `update_memory` | Update existing memory |
| `delete_memory` | Remove a memory |
| `get_memory_stats` | Database statistics |
| `list_topics` | List all topics |
| `list_recent` | Recent memories |

## API Endpoints

Start the server with `python main.py serve`, then access:

- **API Docs**: http://localhost:8000/docs
- **Health Check**: GET /health
- **Statistics**: GET /stats

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest` | POST | Ingest a document |
| `/query` | POST | Query memories |
| `/timeline` | POST | Generate timeline |
| `/batch-ingest` | POST | Batch import from directory |
| `/export` | POST | Export query results |
| `/fireflies/sync` | POST | Sync Fireflies transcripts |
| `/memories` | DELETE | Delete memories |
| `/search` | GET | Simple search (`?q=query`) |

### Example API Requests

```bash
# Ingest a document
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"content": "Meeting notes from today...", "participants": ["Alice", "Bob"]}'

# Query memories
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What did I discuss about AI?", "top_k": 10}'

# Simple search
curl "http://localhost:8000/search?q=machine+learning&top_k=5"
```

## Configuration Reference

### settings.yaml Structure

```yaml
# API Keys
anthropic:
  api_key: ""
  model: "claude-sonnet-4-20250514"

fireflies:
  api_key: ""
  sync_interval_minutes: 60

# Embedding Model
embeddings:
  model_name: "all-MiniLM-L6-v2"
  device: "cpu"  # or "cuda" for GPU

# Vector Database
vector_db:
  persist_directory: "./data/chroma_db"
  collection_name: "memory_palace"
  distance_metric: "cosine"

# Chunking
chunking:
  target_tokens: 500
  overlap_tokens: 50
  strategy: "semantic"  # or "fixed", "paragraph"

# Metadata Extraction
metadata:
  ner:
    enabled: true
    model: "en_core_web_sm"
  sentiment:
    enabled: true
    method: "vader"
  topics:
    enabled: true
    max_topics: 5

# Query Engine
query:
  default_top_k: 10
  synthesis_enabled: true
  cache_enabled: true

# API Server
api:
  host: "127.0.0.1"
  port: 8000
  docs_enabled: true
```

## Supported Query Types

Memory Palace supports natural language queries with automatic temporal parsing:

### Temporal Queries
- "What did I discuss about X **last week**?"
- "Show me conversations **between 2024-2026**"
- "Notes from **last 3 months**"
- "What happened **yesterday**?"
- "Discussions **in January 2024**"

### Topic/Entity Queries
- "All conversations about machine learning"
- "What did I say about mushroom cultivation?"
- "Timeline of my thoughts on AI safety"

### Participant Queries
- "All meetings with John"
- "What did Alice and I discuss?"
- "Conversations involving the marketing team"

### Compound Queries
- "AI discussions with John last month"
- "Project planning meetings in Q4 2024"

## Programmatic Usage

```python
from memory_palace.main import query, ingest, ingest_file, get_query_engine

# Simple query
response = query("What are my notes about Python?")
print(response.synthesis)

# Query with options
response = query("AI safety", top_k=20, synthesize=True)
for result in response.results:
    print(f"{result.metadata.timestamp}: {result.text[:100]}...")

# Ingest text
result = ingest("Important meeting notes...",
                participants=["Alice", "Bob"],
                custom_tags=["meeting"])

# Ingest file
result = ingest_file("./transcript.txt")

# Use query engine directly
engine = get_query_engine()
results = engine.search("machine learning",
                        start_date=datetime(2024, 1, 1),
                        participants=["John"])
```

## Data Directory Structure

```
data/
├── chroma_db/        # Vector database storage
├── raw/              # Unprocessed transcripts (watch folder)
├── processed/        # Archived processed files
├── exports/          # Exported query results
└── cache/            # Query cache
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_chunker.py -v

# Run with coverage
pytest tests/ --cov=.
```

### Project Structure

```
memory_palace/
├── config/
│   ├── settings.yaml      # Configuration template
│   └── schema.py          # Pydantic data models
├── core/                  # Async modules (MCP server path)
│   ├── vector_db.py       # Async ChromaDB wrapper
│   ├── query_engine.py    # Async query interface
│   ├── metadata_db.py     # SQLite metadata storage
│   ├── metadata_extractor.py  # Re-exports from ingestion
│   └── models.py          # Core data models
├── ingestion/
│   ├── chunker.py         # Text chunking
│   ├── metadata_extractor.py  # NER, sentiment, topics (canonical)
│   ├── transcript_parser.py   # Format parsing
│   └── batch_importer.py  # Batch processing
├── storage/               # Sync modules (CLI/API path)
│   ├── vector_db.py       # Sync ChromaDB wrapper
│   ├── embedding_service.py   # Embeddings
│   └── deduplication.py   # Duplicate detection
├── query/                 # Sync query modules (CLI/API path)
│   ├── query_engine.py    # Sync query interface
│   ├── temporal_filter.py # Date parsing
│   ├── agentic_planner.py # LLM query planning
│   └── result_synthesizer.py  # Result synthesis
├── mcp/                   # Model Context Protocol server
│   ├── server.py          # MCP server implementation
│   ├── schemas.py         # MCP request/response schemas
│   ├── tools/             # MCP tool implementations
│   │   ├── search.py      # Search tools
│   │   ├── save.py        # Memory save tools
│   │   ├── manage.py      # Update/delete tools
│   │   ├── entities.py    # Entity tools
│   │   ├── timeline.py    # Timeline tools
│   │   └── browse.py      # Browsing tools
│   └── transports/        # MCP transport implementations
│       ├── stdio_transport.py  # Standard I/O
│       └── http_transport.py   # HTTP transport
├── api/
│   ├── rest_api.py        # FastAPI endpoints
│   ├── fireflies_sync.py  # Fireflies integration
│   └── schemas.py         # API schemas
├── cli/
│   └── commands.py        # CLI interface
├── tests/
│   └── test_*.py          # Unit tests
├── main.py                # Entry point
└── requirements.txt       # Dependencies
```

### Architecture Note: Async vs Sync Paths

The codebase supports two runtime environments with different I/O models:

1. **Async Path (MCP Server)** - `core/` modules
   - Used by the MCP server for Claude Desktop, LibreChat, etc.
   - Fully asynchronous for non-blocking I/O
   - Uses `core.vector_db.VectorDB` and `core.query_engine.QueryEngine`

2. **Sync Path (CLI/API)** - `storage/` and `query/` modules
   - Used by the CLI, REST API, and batch processing
   - Synchronous for simpler integration with existing tools
   - Uses `storage.vector_db.VectorDB` and `query.query_engine.QueryEngine`

Both paths share:
- The same ChromaDB database storage
- The same metadata extraction (`ingestion.metadata_extractor`)
- The same configuration and data models

## Manual Setup Steps

### 1. Install spaCy Model
```bash
python -m spacy download en_core_web_sm
```

### 2. Create Configuration
```bash
cp config/settings.yaml config/settings.local.yaml
# Edit config/settings.local.yaml with your API keys
```

### 3. Initialize Database
The database is created automatically on first run. To start fresh:
```bash
python main.py clear  # Requires confirmation
```

### 4. GPU Support (Optional)
For faster embeddings with CUDA:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```
Then set `embeddings.device: "cuda"` in settings.

## Extending the System

### Adding New Data Sources

1. Create a parser in `ingestion/` for your format
2. Register the format in `DocumentFormat` enum
3. Add handler in `TranscriptParser._format_handlers`

### Adding New Query Types

1. Add methods to `QueryEngine` in `query/query_engine.py`
2. Add API endpoints in `api/rest_api.py`
3. Add CLI commands in `cli/commands.py`

### Custom Metadata Extraction

Extend `MetadataExtractor` in `ingestion/metadata_extractor.py` to extract additional metadata types.

## Troubleshooting

### Common Issues

**"spaCy model not found"**
```bash
python -m spacy download en_core_web_sm
```

**"Anthropic API key not configured"**
- Set `ANTHROPIC_API_KEY` environment variable, or
- Add to `config/settings.local.yaml`

**Slow embedding generation**
- Reduce batch size in settings
- Use GPU if available (`device: "cuda"`)
- Consider smaller embedding model

**Out of memory**
- Reduce `chunking.target_tokens`
- Process files in smaller batches
- Increase system swap space

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

---

**Memory Palace** - Your personal AI-powered knowledge management system. 🧠✨
