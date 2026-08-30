#!/usr/bin/env bash
# Install the public Revenue Partner profile on an Orgo Linux computer.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_TAG="v2026.8.27"
HERMES_COMMIT="5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
HERMES_REPO="/usr/local/lib/hermes-agent"

say() { printf '\n%s\n' "$*"; }
fail() { printf '\nSetup stopped: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || fail "this installer belongs on the Orgo Linux computer"
if [ "$(id -u)" -eq 0 ]; then
  ELEVATE=()
else
  command -v sudo >/dev/null 2>&1 || fail "this account needs administrator access"
  ELEVATE=(sudo)
fi

say "Revenue Partner for Orgo"
echo "This installs the agent profile and tools. Private account connections stay"
echo "on this computer and are never written into the GitHub repository."

say "1 of 5 — Checking the computer"
if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  "${ELEVATE[@]}" apt-get update -qq
  "${ELEVATE[@]}" apt-get install -y -qq ca-certificates curl git python3
fi

installed_commit=""
if [ -d "$HERMES_REPO/.git" ]; then
  installed_commit="$(git -C "$HERMES_REPO" rev-parse HEAD 2>/dev/null || true)"
fi
if [ "$installed_commit" != "$HERMES_COMMIT" ]; then
  say "2 of 5 — Installing the reviewed Hermes release"
  installer="$(mktemp)"
  curl -fsSL "https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_TAG/scripts/install.sh" -o "$installer"
  bash "$installer" --skip-setup --branch "$HERMES_TAG" --commit "$HERMES_COMMIT" --force-commit
  rm -f "$installer"
else
  say "2 of 5 — The reviewed Hermes release is already installed"
fi
command -v hermes >/dev/null 2>&1 || fail "Hermes did not install correctly"

say "3 of 5 — Installing the Revenue Partner profile and skills"
python3 "$REPO_DIR/orgo/sync_seed.py" "$REPO_DIR" "$HERMES_HOME"
chmod 700 "$HERMES_HOME"
chmod 600 "$HERMES_HOME/SOUL.md" 2>/dev/null || true

say "4 of 5 — Enabling the complete operator toolset and safe A2A foundation"
for setting in \
  'toolsets=["hermes-cli","a2a"]' \
  'platform_toolsets.cli=["hermes-cli","a2a"]' \
  'platform_toolsets.slack=["hermes-slack","a2a"]' \
  'platform_toolsets.telegram=["hermes-telegram","a2a"]' \
  'gateway.platforms.a2a.enabled=true' \
  'gateway.platforms.a2a.extra.port=9900' \
  'skills.creation_nudge_interval=15' \
  'skills.write_approval=true' \
  'skills.guard_agent_created=true' \
  'approvals.mode=manual' \
  'approvals.mcp_reload_confirm=true' \
  'privacy.redact_pii=true' \
  'security.redact_secrets=true' \
  'compression.tail_mode=lean'; do
  key=${setting%%=*}
  value=${setting#*=}
  hermes config set "$key" "$value" >/dev/null
done

mkdir -p "$HOME/Desktop"
install -m 0755 "$REPO_DIR/orgo/RevenuePartner.desktop" "$HOME/Desktop/RevenuePartner.desktop"
install -m 0755 "$REPO_DIR/orgo/RevenuePartnerSetup.desktop" "$HOME/Desktop/RevenuePartnerSetup.desktop"

say "5 of 5 — Verifying the installation"
"$REPO_DIR/orgo/verify.sh" --allow-unconnected

cat <<'TEXT'

Revenue Partner is installed on this Orgo computer.

Next:
  ./orgo/connect-channels.sh   Connect Slack and/or Telegram
  ./orgo/connect-tools.sh      Connect Calendar, inboxes, files, and proposals
  ./orgo/connect-a2a.sh        Securely connect the second agent

The same choices are available from the desktop icons.
TEXT
