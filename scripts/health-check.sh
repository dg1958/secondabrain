#!/bin/bash
# =============================================================================
# LibreChat Health Check Script
# =============================================================================
# Checks the health of all services and MCP connectivity.
#
# Usage:
#   ./scripts/health-check.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "============================================================================="
echo "  LibreChat Health Check"
echo "============================================================================="
echo -e "${NC}"

# -----------------------------------------------------------------------------
# Check Docker Services
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Checking Docker services...${NC}"

cd "$PROJECT_DIR"

services=("librechat-api" "librechat-mongodb" "librechat-redis" "librechat-rag-api")
all_healthy=true

for service in "${services[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        status=$(docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null || echo "unknown")
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$service" 2>/dev/null || echo "unknown")

        if [ "$status" = "running" ]; then
            if [ "$health" = "healthy" ] || [ "$health" = "no healthcheck" ]; then
                echo -e "  ${GREEN}✓${NC} $service: running ($health)"
            else
                echo -e "  ${YELLOW}!${NC} $service: running ($health)"
                all_healthy=false
            fi
        else
            echo -e "  ${RED}✗${NC} $service: $status"
            all_healthy=false
        fi
    else
        echo -e "  ${RED}✗${NC} $service: not running"
        all_healthy=false
    fi
done

# -----------------------------------------------------------------------------
# Check API Health Endpoint
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking API health endpoint...${NC}"

API_URL="http://localhost:3080"

if curl -s -f "$API_URL/api/health" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} API responding at $API_URL"
else
    echo -e "  ${RED}✗${NC} API not responding at $API_URL"
    all_healthy=false
fi

# -----------------------------------------------------------------------------
# Check MongoDB Connection
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking MongoDB connection...${NC}"

if docker exec librechat-mongodb mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} MongoDB accepting connections"
else
    echo -e "  ${RED}✗${NC} MongoDB not responding"
    all_healthy=false
fi

# -----------------------------------------------------------------------------
# Check Redis Connection
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking Redis connection...${NC}"

if docker exec librechat-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo -e "  ${GREEN}✓${NC} Redis accepting connections"
else
    echo -e "  ${RED}✗${NC} Redis not responding"
    all_healthy=false
fi

# -----------------------------------------------------------------------------
# Check MCP Server (if running via Docker)
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking MCP configuration...${NC}"

if [ -f "$PROJECT_DIR/librechat.yaml" ]; then
    if grep -q "memory-palace:" "$PROJECT_DIR/librechat.yaml"; then
        echo -e "  ${GREEN}✓${NC} Memory Palace MCP configured in librechat.yaml"
    else
        echo -e "  ${YELLOW}!${NC} Memory Palace MCP not found in librechat.yaml"
    fi
else
    echo -e "  ${RED}✗${NC} librechat.yaml not found"
    all_healthy=false
fi

# -----------------------------------------------------------------------------
# Check Data Directories
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking data directories...${NC}"

data_dirs=("mongodb" "redis" "uploads" "logs" "rag" "memory_palace")

for dir in "${data_dirs[@]}"; do
    if [ -d "$PROJECT_DIR/data/$dir" ]; then
        echo -e "  ${GREEN}✓${NC} data/$dir exists"
    else
        echo -e "  ${YELLOW}!${NC} data/$dir missing"
    fi
done

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}============================================================================="
if [ "$all_healthy" = true ]; then
    echo -e "  ${GREEN}All checks passed!${NC}"
    echo -e "  LibreChat is ready at: ${YELLOW}http://localhost:3080${NC}"
else
    echo -e "  ${YELLOW}Some checks failed. Review the output above.${NC}"
fi
echo "============================================================================="
echo -e "${NC}"
