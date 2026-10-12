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
# `ha core logs` only returns its last 100 journal lines unless told otherwise.
# With debug logging enabled that is a few seconds of history, so ask for the
# whole journal of the current boot before filtering for evon.
JOURNAL_LINES="${HA_LOG_JOURNAL_LINES:-300000}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SSH_KEY="${HOME}/.ssh/claude_code"
ssh_cmd() {
    ssh -o ConnectTimeout=5 -i "${SSH_KEY}" "${HA_USER}@${HA_HOST}" "$@"
}

echo -e "${GREEN}Fetching Evon-related logs from Home Assistant...${NC}"
echo ""

# On HA OS, logs are accessed via 'ha core logs' command
# Filter for evon-related entries
if [[ -n "$FILTER" ]]; then
    echo -e "${YELLOW}Filter: evon AND ${FILTER}${NC}"
    echo ""
    ssh_cmd "ha core logs -n ${JOURNAL_LINES} 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -i evon | grep -i '${FILTER}' | tail -${LINES}" || \
    echo "No matching log entries found."
else
    ssh_cmd "ha core logs -n ${JOURNAL_LINES} 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -i evon | tail -${LINES}" || \
    echo "No evon-related log entries found."
fi
