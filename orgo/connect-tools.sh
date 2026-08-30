#!/usr/bin/env bash
# Connect Calendar/inbox apps through Composio and proposals through PandaDoc.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"
mkdir -p "$HERMES_HOME"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

secret() { local value; read -r -s -p "$1: " value; printf '\n' >&2; printf '%s' "$value"; }
upsert() {
  local key=$1 value=$2 temp
  temp="$(mktemp "$HERMES_HOME/.env.tmp.XXXXXX")"
  awk -v key="$key" 'index($0, key "=") != 1 { print }' "$ENV_FILE" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$ENV_FILE"
}

echo "Connect business tools"
echo "  1. Calendar, Gmail, Outlook, Drive, CRM, and apps through Composio"
echo "  2. PandaDoc proposals"
echo "  3. Show current connections"
read -r -p "Choose 1, 2, or 3: " choice
case "$choice" in
  1)
    echo "Open https://app.composio.dev and copy a consumer key beginning ck_."
    value="$(secret "Paste the ck_ consumer key")"
    [[ "$value" == ck_* ]] || { echo "The consumer key must begin with ck_." >&2; exit 1; }
    upsert COMPOSIO_API_KEY "$value"
    unset value
    hermes config set mcp_servers.composio.url https://connect.composio.dev/mcp >/dev/null
    hermes config set mcp_servers.composio.headers.x-consumer-api-key '${COMPOSIO_API_KEY}' >/dev/null
    hermes config set mcp_servers.composio.trust untrusted >/dev/null
    hermes config set mcp_servers.composio.timeout 180 >/dev/null
    hermes config set mcp_servers.composio.enabled true >/dev/null
    echo "Composio is ready. Connect only the intended accounts in its dashboard."
    echo "First test: Read my next three calendar events. Do not change anything."
    ;;
  2)
    echo "  1. Global PandaDoc"
    echo "  2. European PandaDoc"
    read -r -p "Choose 1 or 2: " region
    case "$region" in
      1) url=https://mcp.pandadoc.com/v1/mcp ;;
      2) url=https://mcp.pandadoc.eu/v1/mcp ;;
      *) echo "Choose 1 or 2." >&2; exit 1 ;;
    esac
    hermes config set mcp_servers.pandadoc.url "$url" >/dev/null
    hermes config set mcp_servers.pandadoc.auth oauth >/dev/null
    hermes config set mcp_servers.pandadoc.trust untrusted >/dev/null
    hermes config set mcp_servers.pandadoc.timeout 180 >/dev/null
    hermes config set mcp_servers.pandadoc.enabled true >/dev/null
    hermes mcp login pandadoc
    echo 'First test: Create a private draft proposal titled "Connection Test". Do not send it.'
    ;;
  3) hermes mcp list ;;
  *) echo "Choose 1, 2, or 3." >&2; exit 1 ;;
esac
hermes gateway restart >/dev/null 2>&1 || true
