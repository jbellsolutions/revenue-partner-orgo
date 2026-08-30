#!/usr/bin/env bash
# Guided Slack and Telegram connection for host-native Hermes on Orgo.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"
mkdir -p "$HERMES_HOME"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

secret() { local value; read -r -s -p "$1: " value; printf '\n' >&2; printf '%s' "$value"; }
fail() { printf 'Connection stopped: %s\n' "$*" >&2; exit 1; }
upsert() {
  local key=$1 value=$2 temp
  [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || fail "invalid setting name"
  [[ "$value" != *$'\n'* ]] || fail "a private value cannot contain a new line"
  temp="$(mktemp "$HERMES_HOME/.env.tmp.XXXXXX")"
  awk -v key="$key" 'index($0, key "=") != 1 { print }' "$ENV_FILE" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$ENV_FILE"
}

echo "Connect Revenue Partner"
echo "Choose one channel now. You can run this helper again to add the other."
echo "  1. Slack"
echo "  2. Telegram"
read -r -p "Choose 1 or 2: " choice
case "$choice" in
  1)
    echo "Create the app from slack-manifest.json in this repository."
    echo "Install it to the intended Slack workspace, then create an app-level"
    echo "token with connections:write. Private values are hidden while entered."
    bot="$(secret "Paste the xoxb- Bot Token")"
    app="$(secret "Paste the xapp- App Token")"
    [[ "$bot" == xoxb-* ]] || fail "the Bot Token must start with xoxb-"
    [[ "$app" == xapp-* ]] || fail "the App Token must start with xapp-"
    read -r -p "Paste the owner's Slack Member ID: " allowed
    [[ "$allowed" =~ ^[UW][A-Z0-9]+(,[UW][A-Z0-9]+)*$ ]] || fail "that Member ID is not valid"
    upsert SLACK_BOT_TOKEN "$bot"
    upsert SLACK_APP_TOKEN "$app"
    upsert SLACK_ALLOWED_USERS "$allowed"
    unset bot app
    hermes config set gateway.platforms.slack.enabled true >/dev/null
    ;;
  2)
    echo "Create the bot in Telegram with @BotFather, then copy its token."
    token="$(secret "Paste the Telegram bot token")"
    [[ "$token" == *:* ]] || fail "that does not look like a Telegram bot token"
    upsert TELEGRAM_BOT_TOKEN "$token"
    unset token
    hermes config set gateway.platforms.telegram.enabled true >/dev/null
    ;;
  *) fail "choose 1 or 2" ;;
esac

hermes gateway install >/dev/null
hermes gateway restart >/dev/null 2>&1 || hermes gateway start >/dev/null
echo "The channel is connected. Send hello, then verify the reply."
