# Memory Palace Monitoring Stack

Comprehensive monitoring solution for Memory Palace using Prometheus, Grafana, and AlertManager.

## Overview

This monitoring stack provides:

- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **AlertManager**: Alert routing and notifications
- **Exporters**: MongoDB, Redis, Node, and Container metrics

## Quick Start

```bash
# Start the full stack with monitoring
docker compose up -d

# Access services
# - Grafana:      http://localhost:3000 (admin/admin)
# - Prometheus:   http://localhost:9090
# - AlertManager: http://localhost:9093
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Memory Palace                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  REST API   │  │ MCP Server  │  │   LibreChat │              │
│  │  :8000      │  │  :8765      │  │   :3080     │              │
│  │  /metrics   │  │  /metrics   │  │             │              │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │
│         │                │                                        │
│         └────────┬───────┘                                        │
│                  ▼                                                │
│         ┌─────────────────┐                                       │
│         │   Prometheus    │◄────────────────────────────────────┐│
│         │   :9090         │                                      ││
│         └────────┬────────┘                                      ││
│                  │                                                ││
│      ┌──────────┼──────────┐                                     ││
│      ▼          ▼          ▼                                     ││
│ ┌─────────┐ ┌─────────┐ ┌─────────────┐  ┌───────────────────┐  ││
│ │ Grafana │ │  Alert  │ │   MongoDB   │  │   Redis Exporter  │  ││
│ │ :3000   │ │ Manager │ │  Exporter   │  │   :9121           │──┘│
│ │         │ │ :9093   │ │  :9216      │──┘  └───────────────────┘  │
│ └─────────┘ └─────────┘ └─────────────┘                           │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐                         │
│  │  Node Exporter  │  │    cAdvisor     │                         │
│  │  :9100          │  │    :8080        │                         │
│  └─────────────────┘  └─────────────────┘                         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Metrics Available

### Memory Palace Application Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `memory_palace_http_requests_total` | Counter | Total HTTP requests |
| `memory_palace_http_request_duration_seconds` | Histogram | Request latency |
| `memory_palace_mcp_tool_calls_total` | Counter | MCP tool calls |
| `memory_palace_mcp_tool_duration_seconds` | Histogram | Tool execution time |
| `memory_palace_queries_total` | Counter | Query operations |
| `memory_palace_query_duration_seconds` | Histogram | Query latency |
| `memory_palace_documents_ingested_total` | Counter | Documents ingested |
| `memory_palace_embeddings_generated_total` | Counter | Embeddings created |
| `memory_palace_db_total_chunks` | Gauge | Chunks in vector DB |
| `memory_palace_db_total_documents` | Gauge | Documents stored |
| `memory_palace_component_health` | Gauge | Component health (1=healthy) |
| `memory_palace_errors_total` | Counter | Errors by component |
| `memory_palace_llm_tokens_used_total` | Counter | LLM token usage |

### Infrastructure Metrics

- **MongoDB**: Connections, operations, replication status
- **Redis**: Memory usage, commands, connections
- **Node**: CPU, memory, disk, network
- **Containers**: CPU, memory per container (via cAdvisor)

## Grafana Dashboards

### Memory Palace Overview

Pre-configured dashboard with:

1. **Service Health** - API, MCP, Vector DB, Embedding status
2. **API Performance** - Request rates, latency percentiles, error rates
3. **MCP Server** - Tool calls, latency by tool
4. **Query Engine** - Query types, latency, cache hit rate
5. **Ingestion** - Documents processed, chunks created, duplicates
6. **LLM Usage** - Token consumption, API latency

Access at: `http://localhost:3000/d/memory-palace-overview`

## Alerting

### Configured Alerts

| Alert | Severity | Condition |
|-------|----------|-----------|
| `MemoryPalaceAPIDown` | Critical | API unreachable for 1m |
| `MemoryPalaceMCPDown` | Warning | MCP server down for 2m |
| `VectorDatabaseUnhealthy` | Critical | Vector DB unhealthy for 1m |
| `HighAPILatency` | Warning | p95 latency > 2s for 5m |
| `HighHTTPErrorRate` | Critical | 5xx errors > 5% for 5m |
| `HighQueryLatency` | Warning | p95 query time > 5s for 5m |
| `HighTokenUsage` | Info | > 100k tokens/hour |

### Configuring Notifications

Edit `monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical-receiver'
    # Slack
    slack_configs:
      - channel: '#alerts'
        api_url: 'https://hooks.slack.com/...'

    # Email
    email_configs:
      - to: 'oncall@example.com'

    # PagerDuty
    pagerduty_configs:
      - service_key: 'YOUR_KEY'
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=secure_password
GRAFANA_PORT=3000

# Prometheus
PROMETHEUS_PORT=9090

# AlertManager
ALERTMANAGER_PORT=9093

# Enable metrics in Memory Palace
METRICS_ENABLED=true
```

### Prometheus Targets

Edit `monitoring/prometheus/prometheus.yml` to add/remove scrape targets:

```yaml
scrape_configs:
  - job_name: 'memory-palace-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
```

### Alert Rules

Add custom rules in `monitoring/prometheus/rules/`:

```yaml
groups:
  - name: custom_alerts
    rules:
      - alert: MyCustomAlert
        expr: my_metric > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Custom alert triggered"
```

## Directory Structure

```
monitoring/
├── prometheus/
│   ├── prometheus.yml          # Prometheus configuration
│   └── rules/
│       └── memory_palace_alerts.yml  # Alert rules
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml # Auto-configure Prometheus
│   │   └── dashboards/
│   │       └── dashboards.yml  # Dashboard provisioning
│   └── dashboards/
│       └── memory-palace-overview.json  # Main dashboard
├── alertmanager/
│   └── alertmanager.yml        # Alert routing config
└── README.md                   # This file
```

## Integrating Metrics in Code

### Using the Metrics Module

```python
from monitoring.metrics import get_metrics_manager

metrics = get_metrics_manager()

# Record a query
metrics.record_query(
    query_type="search",
    status="success",
    duration=0.5,
    results_count=10
)

# Track ingestion
metrics.record_ingestion(
    source_type="api",
    status="success",
    duration=1.2,
    chunks_created=5
)

# Track LLM usage
metrics.record_llm_call(
    provider="anthropic",
    model="claude-3-sonnet",
    status="success",
    duration=2.5,
    input_tokens=500,
    output_tokens=200
)
```

### Using Decorators

```python
from monitoring.metrics import track_operation_time

@track_operation_time("query", "semantic_search")
async def search_memories(query: str):
    # This function's execution time is automatically tracked
    ...
```

### FastAPI Middleware

```python
from monitoring.middleware import setup_prometheus_middleware

app = FastAPI()
setup_prometheus_middleware(app)  # Adds /metrics endpoint
```

## Troubleshooting

### Prometheus Not Scraping

1. Check target status: `http://localhost:9090/targets`
2. Verify network connectivity: `docker exec prometheus wget -qO- http://api:8000/metrics`
3. Check service logs: `docker logs prometheus`

### Grafana Dashboard Empty

1. Verify datasource: Settings > Data Sources > Prometheus > Test
2. Check time range: Dashboard may need longer time window
3. Verify metrics exist: Query `{job="memory-palace-api"}` in Prometheus

### Alerts Not Firing

1. Check rule status: `http://localhost:9090/alerts`
2. Verify AlertManager: `http://localhost:9093/#/alerts`
3. Check AlertManager logs: `docker logs alertmanager`

## Performance Tuning

### Prometheus Retention

Adjust in `docker-compose.yml`:

```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=90d'  # Keep 90 days
    - '--storage.tsdb.retention.size=10GB' # Max 10GB
```

### Scrape Intervals

For high-traffic services, reduce intervals:

```yaml
scrape_configs:
  - job_name: 'memory-palace-api'
    scrape_interval: 5s  # More frequent
```

## Security Considerations

1. **Change default credentials** for Grafana
2. **Restrict network access** to monitoring ports in production
3. **Enable HTTPS** for Grafana with reverse proxy
4. **Use authentication** for Prometheus (e.g., basic auth with nginx)

## Maintenance

### Backup Grafana

```bash
# Backup dashboards and config
docker exec grafana tar -czf - /var/lib/grafana > grafana-backup.tar.gz
```

### Update Components

```bash
# Pull latest images
docker compose pull prometheus grafana alertmanager

# Restart with new images
docker compose up -d prometheus grafana alertmanager
```
