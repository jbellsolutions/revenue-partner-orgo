#!/usr/bin/env bash
set -euo pipefail

ALLOW_UNCONNECTED=false
[ "${1:-}" = "--allow-unconnected" ] && ALLOW_UNCONNECTED=true
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
EXPECTED_COMMIT="939e45c91d751fadd94dcd1b873ac3cb44846213"

python3 -m json.tool "$REPO_DIR/orgo/deployment.json" >/dev/null
bash -n "$REPO_DIR/orgo/setup.sh" "$REPO_DIR/orgo/connect-channels.sh" \
  "$REPO_DIR/orgo/connect-tools.sh" "$REPO_DIR/orgo/connect-a2a.sh"
python3 -m py_compile "$REPO_DIR/orgo/sync_seed.py" "$REPO_DIR/orgo/identity.py"
[ -f "$HERMES_HOME/SOUL.md" ]
[ -f "$HERMES_HOME/skills/go-to-market/revenue-partner/SKILL.md" ]
HERMES_SOURCE_DIR="${HERMES_SOURCE_DIR:-/usr/local/lib/hermes-agent}"
[ -d "$HERMES_SOURCE_DIR/.git" ] || HERMES_SOURCE_DIR="$HERMES_HOME/hermes-agent"
installed="$(git -C "$HERMES_SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)"
[ "$installed" = "$EXPECTED_COMMIT" ] || {
  echo "Hermes is not at the reviewed commit." >&2
  exit 1
}
hermes config get gateway.platforms.a2a.enabled 2>/dev/null | grep -qi true
hermes config get platform_toolsets.cli 2>/dev/null | grep -q a2a
IDENTITY_ARGS=()
[ "$ALLOW_UNCONNECTED" = false ] || IDENTITY_ARGS=(--local-only)
# Use Hermes's dotenv parser when checking the actual Slack token, without
# importing the agent or executing its gateway. Local checks need only stdlib.
IDENTITY_PYTHON=python3
if [ -x /usr/local/lib/hermes-agent/venv/bin/python3 ]; then
  IDENTITY_PYTHON=/usr/local/lib/hermes-agent/venv/bin/python3
fi
"$IDENTITY_PYTHON" "$REPO_DIR/orgo/identity.py" verify --hermes-home "$HERMES_HOME" "${IDENTITY_ARGS[@]}"
if [ "$ALLOW_UNCONNECTED" = false ]; then
  hermes doctor
  hermes gateway status
fi
AGENT_DISPLAY_NAME="$(python3 "$REPO_DIR/orgo/identity.py" name --hermes-home "$HERMES_HOME")"
printf '%s Orgo verification passed.\n' "$AGENT_DISPLAY_NAME"
