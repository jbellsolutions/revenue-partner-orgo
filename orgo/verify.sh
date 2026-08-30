#!/usr/bin/env bash
set -euo pipefail

ALLOW_UNCONNECTED=false
[ "${1:-}" = "--allow-unconnected" ] && ALLOW_UNCONNECTED=true
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
EXPECTED_COMMIT="5fc308a70719a83cccdbba4c0e39c23f5a8239d5"

python3 -m json.tool "$REPO_DIR/orgo/deployment.json" >/dev/null
bash -n "$REPO_DIR/orgo/setup.sh" "$REPO_DIR/orgo/connect-channels.sh" \
  "$REPO_DIR/orgo/connect-tools.sh" "$REPO_DIR/orgo/connect-a2a.sh"
python3 -m py_compile "$REPO_DIR/orgo/sync_seed.py"
[ -f "$HERMES_HOME/SOUL.md" ]
[ -f "$HERMES_HOME/skills/go-to-market/revenue-partner/SKILL.md" ]
installed="$(git -C /usr/local/lib/hermes-agent rev-parse HEAD 2>/dev/null || true)"
[ "$installed" = "$EXPECTED_COMMIT" ] || {
  echo "Hermes is not at the reviewed commit." >&2
  exit 1
}
hermes config get gateway.platforms.a2a.enabled 2>/dev/null | grep -qi true
hermes config get platform_toolsets.cli 2>/dev/null | grep -q a2a
if [ "$ALLOW_UNCONNECTED" = false ]; then
  hermes doctor
  hermes gateway status
fi
echo "Revenue Partner Orgo verification passed."
