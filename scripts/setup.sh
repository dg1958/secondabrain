#!/bin/bash
# =============================================================================
# LibreChat + Memory Palace Setup Script
# =============================================================================
# This script initializes the environment for running LibreChat with
# Memory Palace MCP integration.
#
# Usage:
#   ./scripts/setup.sh [--dev]
#
# Options:
#   --dev    Setup for development mode (additional tooling)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
DEV_MODE=false
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dev) DEV_MODE=true ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

echo -e "${BLUE}"
echo "============================================================================="
echo "  LibreChat + Memory Palace Setup"
echo "============================================================================="
echo -e "${NC}"

# -----------------------------------------------------------------------------
# Check Prerequisites
# -----------------------------------------------------------------------------
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker installed"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker Compose installed"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon is not running.${NC}"
    echo "Please start Docker and try again."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker daemon running"

# -----------------------------------------------------------------------------
# Create Data Directories
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Creating data directories...${NC}"

mkdir -p "$PROJECT_DIR/data/mongodb"
mkdir -p "$PROJECT_DIR/data/redis"
mkdir -p "$PROJECT_DIR/data/uploads"
mkdir -p "$PROJECT_DIR/data/logs"
mkdir -p "$PROJECT_DIR/data/rag"
mkdir -p "$PROJECT_DIR/data/memory_palace"

echo -e "  ${GREEN}✓${NC} Data directories created"

# -----------------------------------------------------------------------------
# Setup Environment File
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Setting up environment file...${NC}"

if [ -f "$PROJECT_DIR/.env" ]; then
    echo -e "  ${YELLOW}!${NC} .env file already exists"
    read -p "  Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "  ${GREEN}✓${NC} Keeping existing .env file"
    else
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "  ${GREEN}✓${NC} .env file created from example"
    fi
else
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo -e "  ${GREEN}✓${NC} .env file created from example"
fi

# -----------------------------------------------------------------------------
# Generate Security Keys
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Generating security keys...${NC}"

generate_key() {
    local length=$1
    openssl rand -hex "$length" 2>/dev/null || head -c "$length" /dev/urandom | xxd -p | tr -d '\n'
}

# Check if keys need to be generated
if grep -q "^CREDS_KEY=$" "$PROJECT_DIR/.env" 2>/dev/null; then
    CREDS_KEY=$(generate_key 32)
    sed -i "s/^CREDS_KEY=$/CREDS_KEY=$CREDS_KEY/" "$PROJECT_DIR/.env"
    echo -e "  ${GREEN}✓${NC} Generated CREDS_KEY"
fi

if grep -q "^CREDS_IV=$" "$PROJECT_DIR/.env" 2>/dev/null; then
    CREDS_IV=$(generate_key 16)
    sed -i "s/^CREDS_IV=$/CREDS_IV=$CREDS_IV/" "$PROJECT_DIR/.env"
    echo -e "  ${GREEN}✓${NC} Generated CREDS_IV"
fi

if grep -q "^JWT_SECRET=$" "$PROJECT_DIR/.env" 2>/dev/null; then
    JWT_SECRET=$(generate_key 32)
    sed -i "s/^JWT_SECRET=$/JWT_SECRET=$JWT_SECRET/" "$PROJECT_DIR/.env"
    echo -e "  ${GREEN}✓${NC} Generated JWT_SECRET"
fi

if grep -q "^JWT_REFRESH_SECRET=$" "$PROJECT_DIR/.env" 2>/dev/null; then
    JWT_REFRESH_SECRET=$(generate_key 32)
    sed -i "s/^JWT_REFRESH_SECRET=$/JWT_REFRESH_SECRET=$JWT_REFRESH_SECRET/" "$PROJECT_DIR/.env"
    echo -e "  ${GREEN}✓${NC} Generated JWT_REFRESH_SECRET"
fi

# -----------------------------------------------------------------------------
# Validate Configuration
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Validating configuration...${NC}"

# Source .env file
set -a
source "$PROJECT_DIR/.env"
set +a

# Check required variables
MISSING_VARS=()

if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" ]; then
    MISSING_VARS+=("ANTHROPIC_API_KEY")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "  ${YELLOW}!${NC} Missing required configuration:"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "      - $var"
    done
    echo -e "\n  Please edit .env and add the missing values."
else
    echo -e "  ${GREEN}✓${NC} Configuration validated"
fi

# -----------------------------------------------------------------------------
# Check Memory Palace Path
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}Checking Memory Palace configuration...${NC}"

MEMORY_PALACE_PATH=${MEMORY_PALACE_PATH:-./memory_palace}

if [ -d "$MEMORY_PALACE_PATH" ]; then
    echo -e "  ${GREEN}✓${NC} Memory Palace found at: $MEMORY_PALACE_PATH"
else
    echo -e "  ${YELLOW}!${NC} Memory Palace not found at: $MEMORY_PALACE_PATH"
    echo -e "      Please update MEMORY_PALACE_PATH in .env"
    echo -e "      Or place your memory palace in: $PROJECT_DIR/memory_palace"
fi

# -----------------------------------------------------------------------------
# Development Mode Setup
# -----------------------------------------------------------------------------
if [ "$DEV_MODE" = true ]; then
    echo -e "\n${YELLOW}Setting up development environment...${NC}"

    # Check Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        echo -e "  ${GREEN}✓${NC} Node.js installed: $NODE_VERSION"
    else
        echo -e "  ${YELLOW}!${NC} Node.js not found (optional for development)"
    fi

    # Create VS Code settings
    mkdir -p "$PROJECT_DIR/.vscode"
    cat > "$PROJECT_DIR/.vscode/settings.json" << 'EOF'
{
    "yaml.schemas": {
        "https://raw.githubusercontent.com/danny-avila/LibreChat/main/config/librechat.schema.json": "librechat.yaml"
    },
    "files.associations": {
        "*.yaml": "yaml",
        "*.yml": "yaml"
    }
}
EOF
    echo -e "  ${GREEN}✓${NC} VS Code settings created"
fi

# -----------------------------------------------------------------------------
# Final Instructions
# -----------------------------------------------------------------------------
echo -e "\n${BLUE}============================================================================="
echo "  Setup Complete!"
echo "=============================================================================${NC}"

echo -e "\n${GREEN}Next steps:${NC}"
echo ""
echo "  1. Edit .env and add your ANTHROPIC_API_KEY:"
echo -e "     ${YELLOW}nano .env${NC}"
echo ""
echo "  2. (Optional) Update MEMORY_PALACE_PATH in .env"
echo ""
echo "  3. Start the services:"
echo -e "     ${YELLOW}docker compose up -d${NC}"
echo ""
echo "  4. Open LibreChat in your browser:"
echo -e "     ${YELLOW}http://localhost:3080${NC}"
echo ""
echo "  5. Create an account and start chatting!"
echo ""

echo -e "${BLUE}Useful commands:${NC}"
echo "  docker compose logs -f api     # View API logs"
echo "  docker compose ps              # Check service status"
echo "  docker compose down            # Stop all services"
echo "  docker compose restart api     # Restart API only"
echo ""

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Remember to configure:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
fi
