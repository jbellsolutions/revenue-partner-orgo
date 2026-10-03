#!/usr/bin/env python3
"""Safely bridge allowlisted runtime values into Hermes and optionally exec.

Dotenv content is parsed without expansion or command evaluation. Values are
serialized with POSIX-safe quoting and written atomically with mode 0600.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence, Set
import os
from pathlib import Path
import re
import shlex
import tempfile


MANAGED_KEYS = (
    # Slack authorization. The gateway denies unknown senders unless a
    # platform allowlist reaches it, so these must survive the bridge
    # rebuild or the bot connects and then silently ignores everyone.
    "SLACK_ALLOW_ALL_USERS",
    "SLACK_ALLOWED_USERS",
    "SLACK_ALLOWED_CHANNELS",
    "SLACK_FREE_RESPONSE_CHANNELS",
    # Slack socket-mode transport (bot + app-level token).
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "SLACK_HOME_CHANNEL",
    # Scrape Creators hosted MCP transport (public-data routes; no login).
    "SCRAPECREATORS_API_KEY",
    # Hosted Super Browser transport — the agent attaches by URL rather than
    # vendoring a local copy, so the endpoint and bearer token must survive
    # the bridge rebuild or the MCP server authenticates as anonymous.
    "SUPER_BROWSER_URL",
    "SUPER_BROWSER_TOKEN",
    # browser-box and data-box hosted transports (Super Browser's successors), same reason.
    "BROWSER_BOX_URL",
    "BROWSER_BOX_TOKEN",
    "DATABOX_URL",
    "DATABOX_TOKEN",
    # Non-secret operational defaults.
    "AGENT_BROWSER_EXECUTABLE_PATH",
    "TERMINAL_TIMEOUT",
    "TERMINAL_LIFETIME_SECONDS",
    "BROWSER_SESSION_TIMEOUT",
    "BROWSER_INACTIVITY_TIMEOUT",
    "OBSIDIAN_VAULT_PATH",
    "WIKI_PATH",

    "LATITUDE_SERVICE_NAME",
    "LATITUDE_HERMES_NO_CONTENT",
    "LATITUDE_HERMES_TELEMETRY_ENABLED",

    # Runtime credentials and identifiers.
    "ORGO_API_KEY",
    "REVENUE_PARTNER_REVIEW_ATTESTATIONS",
    "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY",
    "REVENUE_PARTNER_NONCE_LEDGER",
    "ONEPASSWORD_SERVICE_ACCOUNT_TOKEN",
    "OP_SERVICE_ACCOUNT_TOKEN",
    "LATITUDE_API_KEY",
    "LATITUDE_PROJECT_ID",
    "LATITUDE_PROJECT",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "XAI_API_KEY",
    "AI_GATEWAY_API_KEY",
    "MODEL_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USERS",
    "TELEGRAM_HOME_CHANNEL",
    "TELEGRAM_BOT_USERNAME",
)

# The gateway may receive only capabilities executable in this immutable image.
# ORGO_API_KEY, REVENUE_PARTNER_REVIEW_ATTESTATIONS, and REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY are selectable only via
# an explicit operator-authored ``--only`` release command; absent-connector
# credentials are not accepted by either the default or explicit path.
RUNTIME_MANAGED_KEYS = (
    # Slack authorization. The gateway denies unknown senders unless a
    # platform allowlist reaches it, so these must survive the bridge
    # rebuild or the bot connects and then silently ignores everyone.
    "SLACK_ALLOW_ALL_USERS",
    "SLACK_ALLOWED_USERS",
    "SLACK_ALLOWED_CHANNELS",
    "SLACK_FREE_RESPONSE_CHANNELS",
    # Slack socket-mode transport (bot + app-level token).
    "SLACK_BOT_TOKEN",
    "SLACK_APP_TOKEN",
    "SLACK_HOME_CHANNEL",
    # Scrape Creators hosted MCP transport (public-data routes; no login).
    "SCRAPECREATORS_API_KEY",
    # Hosted Super Browser transport — the agent attaches by URL rather than
    # vendoring a local copy, so the endpoint and bearer token must survive
    # the bridge rebuild or the MCP server authenticates as anonymous.
    "SUPER_BROWSER_URL",
    "SUPER_BROWSER_TOKEN",
    # browser-box and data-box hosted transports (Super Browser's successors), same reason.
    "BROWSER_BOX_URL",
    "BROWSER_BOX_TOKEN",
    "DATABOX_URL",
    "DATABOX_TOKEN",
    "AGENT_BROWSER_EXECUTABLE_PATH",
    "TERMINAL_TIMEOUT",
    "TERMINAL_LIFETIME_SECONDS",
    "BROWSER_SESSION_TIMEOUT",
    "BROWSER_INACTIVITY_TIMEOUT",
    "OBSIDIAN_VAULT_PATH",
    "WIKI_PATH",
    "LATITUDE_SERVICE_NAME",
    "LATITUDE_HERMES_NO_CONTENT",
    "LATITUDE_HERMES_TELEMETRY_ENABLED",
    "LATITUDE_API_KEY",
    "LATITUDE_PROJECT_ID",
    "LATITUDE_PROJECT",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "XAI_API_KEY",
    "AI_GATEWAY_API_KEY",
    "MODEL_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_USERS",
    "TELEGRAM_HOME_CHANNEL",
    "TELEGRAM_BOT_USERNAME",
)

# Process context required for a normal child process. All other inherited
# variables are dropped; in particular, credentials and Hermes policy flags
# must arrive through MANAGED_KEYS and the parsed target file.
SAFE_INHERITED_KEYS = (
    "PATH",
    "HOME",
    "HERMES_HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TMPDIR",
    "TERM",
    "COLORTERM",
    "DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "NO_COLOR",
)

_ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _decode_value(raw: str) -> str | None:
    """Parse one dotenv RHS without expansion or command evaluation."""
    try:
        parts = shlex.split(raw, comments=False, posix=True)
    except ValueError:
        return None
    if len(parts) != 1:
        return None
    value = parts[0]
    if any(char in value for char in ("\x00", "\r", "\n")):
        return None
    return value


def read_allowlisted(path: Path, allowed: Set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _ASSIGNMENT.match(line)
        if not match or match.group(1) not in allowed:
            continue
        value = _decode_value(match.group(2))
        if value is not None:
            values[match.group(1)] = value
    return values


def collect_values(
    sources: Sequence[Path],
    environ: Mapping[str, str] | None = None,
    managed_keys: Sequence[str] = RUNTIME_MANAGED_KEYS,
) -> dict[str, str]:
    allowed = set(managed_keys)
    values: dict[str, str] = {}
    for source in sources:
        values.update(read_allowlisted(source, allowed))

    current_env = os.environ if environ is None else environ
    for key in managed_keys:
        value = current_env.get(key)
        if not value or any(char in value for char in ("\x00", "\r", "\n")):
            continue
        values[key] = value
    return values


def update_env(
    target: Path,
    sources: Sequence[Path],
    environ: Mapping[str, str] | None = None,
    managed_keys: Sequence[str] = RUNTIME_MANAGED_KEYS,
) -> int:
    values = collect_values(sources, environ, managed_keys)

    # Rewrite the target as an allowlist-only file. Preserving unmanaged
    # assignments would let the child application reload policy flags or secrets
    # from dotenv even when they were stripped from the inherited environment.
    rendered: list[str] = []
    for key in managed_keys:
        if key in values:
            rendered.append(f"{key}={shlex.quote(values[key])}")
    body = "\n".join(rendered).rstrip("\n") + "\n"

    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        os.chmod(target, 0o600)
    finally:
        temporary_path.unlink(missing_ok=True)
    return len(values)


def child_environment(
    environ: Mapping[str, str],
    managed_values: Mapping[str, str],
) -> dict[str, str]:
    """Build a minimal exec environment from safe context plus managed values."""
    child = {key: environ[key] for key in SAFE_INHERITED_KEYS if key in environ}
    child.update(managed_values)
    return child


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("/root/.hermes/.env"))
    parser.add_argument("--source", action="append", type=Path)
    parser.add_argument("--only", action="append", choices=MANAGED_KEYS)
    parser.add_argument("--exec", dest="exec_command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    sources = args.source or [Path("/root/.env"), args.target]
    managed_keys = tuple(args.only) if args.only else RUNTIME_MANAGED_KEYS
    count = update_env(args.target, sources, managed_keys=managed_keys)
    print(f"bridged {count} allowlisted environment values", flush=True)

    if args.exec_command:
        managed_values = collect_values([args.target], {}, managed_keys)
        child_env = child_environment(os.environ, managed_values)
        os.execvpe(args.exec_command[0], args.exec_command, child_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
