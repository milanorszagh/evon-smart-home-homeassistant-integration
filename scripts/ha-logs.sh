#!/bin/bash
# Fetch Home Assistant logs related to Evon integration
# Usage: ./scripts/ha-logs.sh [lines] [filter]
#   lines  - Number of lines to fetch (default: 100)
#   filter - Additional grep filter (optional)
#
# Examples:
#   ./scripts/ha-logs.sh           # Last 100 evon-related lines
#   ./scripts/ha-logs.sh 50        # Last 50 evon-related lines
#   ./scripts/ha-logs.sh 100 error # Last 100 evon lines containing "error"

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
if [[ -z "$HA_HOST" ]] || [[ -z "$HA_USER" ]]; then
    echo "Error: HA_HOST and HA_USER must be set in .env"
    exit 1
fi

# Configuration
LINES="${1:-100}"
FILTER="${2:-}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ssh_cmd() {
    ssh -o ConnectTimeout=5 "${HA_USER}@${HA_HOST}" "$@"
}

echo -e "${GREEN}Fetching Evon-related logs from Home Assistant...${NC}"
echo ""

# On HA OS, logs are accessed via 'ha core logs' command
# Filter for evon-related entries
if [[ -n "$FILTER" ]]; then
    echo -e "${YELLOW}Filter: evon AND ${FILTER}${NC}"
    echo ""
    ssh_cmd "ha core logs 2>/dev/null | grep -i evon | grep -i '${FILTER}' | tail -${LINES}" || \
    echo "No matching log entries found."
else
    ssh_cmd "ha core logs 2>/dev/null | grep -i evon | tail -${LINES}" || \
    echo "No evon-related log entries found."
fi
