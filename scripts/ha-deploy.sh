#!/bin/bash
# Deploy Evon integration to Home Assistant
# Usage: ./scripts/ha-deploy.sh [restart]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load configuration from .env
ENV_FILE="$PROJECT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: .env file not found!"
    echo "Copy .env.example to .env and configure your Home Assistant connection."
    exit 1
fi

source "$ENV_FILE"

# Validate required variables
if [[ -z "$HA_HOST" ]]; then
    echo "Error: HA_HOST not set in .env"
    exit 1
fi
if [[ -z "$HA_USER" ]]; then
    echo "Error: HA_USER not set in .env"
    exit 1
fi

# Configuration
HA_CONFIG="/config"
LOCAL_COMPONENT="$PROJECT_DIR/custom_components/evon"
REMOTE_COMPONENT="$HA_CONFIG/custom_components/evon"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ssh_cmd() {
    ssh -o ConnectTimeout=5 "${HA_USER}@${HA_HOST}" "$@"
}

echo -e "${GREEN}Deploying Evon integration to Home Assistant...${NC}"
echo "  Host: ${HA_HOST}"
echo "  User: ${HA_USER}"
echo ""

# Check SSH connection
if ! ssh_cmd "echo 'SSH OK'" 2>/dev/null; then
    echo -e "${RED}Error: Cannot connect to Home Assistant via SSH${NC}"
    echo "Make sure:"
    echo "  1. SSH add-on is running on HA"
    echo "  2. Your SSH key is in the add-on's authorized_keys"
    echo "  3. HA_HOST in .env is correct"
    exit 1
fi

# Create custom_components directory if needed
ssh_cmd "mkdir -p ${HA_CONFIG}/custom_components" 2>/dev/null

# Remove old version
echo "  Removing old version..."
ssh_cmd "rm -rf ${REMOTE_COMPONENT}" 2>/dev/null || true

# Copy new version
echo "  Copying new version..."
scp -r -o ConnectTimeout=5 "$LOCAL_COMPONENT" "${HA_USER}@${HA_HOST}:${HA_CONFIG}/custom_components/"

echo -e "${GREEN}Deployed successfully!${NC}"

# Optionally restart HA
if [[ "${1:-}" == "restart" ]]; then
    echo ""
    echo -e "${YELLOW}Restarting Home Assistant...${NC}"
    ssh_cmd "ha core restart" 2>/dev/null || \
    echo -e "${YELLOW}Could not auto-restart. Please restart HA manually.${NC}"
else
    echo ""
    echo "To apply changes:"
    echo "  - Restart HA: ./scripts/ha-deploy.sh restart"
    echo "  - Or reload the integration from HA UI"
fi
