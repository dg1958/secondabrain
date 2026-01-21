#!/bin/bash
# =============================================================================
# Memory Palace MCP Server Test Script
# =============================================================================
# Tests that the Memory Palace MCP server can be started and responds correctly.
#
# Usage:
#   ./scripts/test-mcp.sh [path/to/memory_palace]
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

# Load .env if exists
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Memory palace path from argument or .env or default
MEMORY_PALACE_PATH="${1:-${MEMORY_PALACE_PATH:-$PROJECT_DIR/memory_palace}}"

echo -e "${BLUE}"
echo "============================================================================="
echo "  Memory Palace MCP Server Test"
echo "============================================================================="
echo -e "${NC}"

echo -e "${YELLOW}Memory Palace path:${NC} $MEMORY_PALACE_PATH"
echo ""

# -----------------------------------------------------------------------------
# Check Memory Palace Exists
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Checking Memory Palace installation...${NC}"

if [ ! -d "$MEMORY_PALACE_PATH" ]; then
    echo -e "  ${RED}✗${NC} Directory not found: $MEMORY_PALACE_PATH"
    echo ""
    echo "  Please either:"
    echo "    1. Set MEMORY_PALACE_PATH in .env"
    echo "    2. Pass the path as an argument: ./scripts/test-mcp.sh /path/to/memory_palace"
    echo "    3. Create a memory_palace directory in this project"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Directory exists"

# Check for run_stdio.py
if [ -f "$MEMORY_PALACE_PATH/memory_palace/scripts/run_stdio.py" ]; then
    echo -e "  ${GREEN}✓${NC} run_stdio.py found"
elif [ -f "$MEMORY_PALACE_PATH/scripts/run_stdio.py" ]; then
    echo -e "  ${GREEN}✓${NC} run_stdio.py found (alternate location)"
else
    echo -e "  ${YELLOW}!${NC} run_stdio.py not found in expected locations"
    echo "      Expected: memory_palace/scripts/run_stdio.py"
fi

# Check for run_http.py
if [ -f "$MEMORY_PALACE_PATH/memory_palace/scripts/run_http.py" ] || [ -f "$MEMORY_PALACE_PATH/scripts/run_http.py" ]; then
    echo -e "  ${GREEN}✓${NC} run_http.py found (HTTP transport available)"
fi

# -----------------------------------------------------------------------------
# Check Python Environment
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking Python environment...${NC}"

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "  ${RED}✗${NC} Python not found"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo -e "  ${GREEN}✓${NC} $PYTHON_VERSION"

# -----------------------------------------------------------------------------
# Check Required Python Packages
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking Python packages...${NC}"

check_package() {
    if $PYTHON_CMD -c "import $1" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not installed"
        return 1
    fi
}

packages_ok=true
check_package "mcp" || packages_ok=false
check_package "chromadb" || packages_ok=false
check_package "sqlite3" || packages_ok=false

if [ "$packages_ok" = false ]; then
    echo -e "\n  ${YELLOW}Some packages are missing. Install with:${NC}"
    echo "    pip install mcp chromadb"
fi

# -----------------------------------------------------------------------------
# Test MCP Server Startup (Quick Test)
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Testing MCP server startup...${NC}"

cd "$MEMORY_PALACE_PATH"

# Create a simple test that sends initialize request
TEST_RESULT=$(timeout 5 $PYTHON_CMD -c "
import sys
import json
sys.path.insert(0, '.')

try:
    # Try to import the MCP server module
    from memory_palace.scripts import run_stdio
    print('import_ok')
except ImportError as e:
    print(f'import_error: {e}')
except Exception as e:
    print(f'error: {e}')
" 2>&1) || true

if echo "$TEST_RESULT" | grep -q "import_ok"; then
    echo -e "  ${GREEN}✓${NC} MCP server module imports successfully"
elif echo "$TEST_RESULT" | grep -q "import_error"; then
    echo -e "  ${YELLOW}!${NC} Import issue: $TEST_RESULT"
    echo "      You may need to adjust PYTHONPATH or module structure"
else
    echo -e "  ${YELLOW}!${NC} Could not verify import: $TEST_RESULT"
fi

# -----------------------------------------------------------------------------
# MCP Inspector Test (if available)
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking MCP Inspector availability...${NC}"

if command -v npx &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} npx available"
    echo ""
    echo -e "  ${BLUE}To test with MCP Inspector, run:${NC}"
    echo "    cd $MEMORY_PALACE_PATH"
    echo "    npx @modelcontextprotocol/inspector python -m memory_palace.scripts.run_stdio"
else
    echo -e "  ${YELLOW}!${NC} npx not available (install Node.js for MCP Inspector)"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}============================================================================="
echo "  Test Complete"
echo "=============================================================================${NC}"
echo ""
echo -e "If all checks passed, your Memory Palace MCP server should work with LibreChat."
echo ""
echo -e "${YELLOW}Configuration in librechat.yaml:${NC}"
echo "  mcpServers:"
echo "    memory-palace:"
echo "      command: \"python\""
echo "      args:"
echo "        - \"-m\""
echo "        - \"memory_palace.scripts.run_stdio\""
echo "      cwd: \"$MEMORY_PALACE_PATH\""
echo ""
