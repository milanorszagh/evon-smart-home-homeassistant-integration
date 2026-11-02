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

# Both values end up in the command line that runs on the HA host (as root on
# HAOS), so only plain numbers are accepted. The text filter is applied locally
# below and never reaches the remote shell.
if ! [[ "$LINES" =~ ^[0-9]+$ ]] || ! [[ "$JOURNAL_LINES" =~ ^[0-9]+$ ]]; then
    echo "Error: lines and HA_LOG_JOURNAL_LINES must be positive integers" >&2
    exit 1
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# SSH key: HA_SSH_KEY from .env (a leading ~ is expanded), default ~/.ssh/claude_code
SSH_KEY="${HA_SSH_KEY:-${HOME}/.ssh/claude_code}"
SSH_KEY="${SSH_KEY/#\~/${HOME}}"
ssh_cmd() {
    ssh -o ConnectTimeout=5 -i "${SSH_KEY}" "${HA_USER}@${HA_HOST}" "$@"
}

echo -e "${GREEN}Fetching Evon-related logs from Home Assistant...${NC}"
echo ""

# On HA OS, logs are accessed via 'ha core logs' command.
# The remote command contains only validated numbers; colour codes are stripped
# and evon lines selected there to keep the transfer small.
REMOTE_CMD="ha core logs -n ${JOURNAL_LINES} 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -i evon"

set -o pipefail
if [[ -n "$FILTER" ]]; then
    echo -e "${YELLOW}Filter: evon AND ${FILTER}${NC}"
    echo ""
    # Matched locally (basic regex, as before), so quotes or ; in the filter
    # are just characters to search for.
    ssh_cmd "$REMOTE_CMD" | grep -i -- "$FILTER" | tail -n "$LINES" || \
    echo "No matching log entries found."
else
    ssh_cmd "$REMOTE_CMD" | tail -n "$LINES" || \
    echo "No evon-related log entries found."
fi
