#!/usr/bin/env python3
# ==========================================================================
# Revenue Partner Agent — template builder / publisher (key-less, self-contained)
# ==========================================================================
# Assembles the orgo.ai/v1 template dict programmatically from the byte-exact
# files in ./files, validates it against the schema, and (optionally) runs the
# proven publish -> build -> stream -> launch REST flow.
#
#   python3 build_template.py                 # assemble + local jsonschema validate + dump resolved.json
#   python3 release_entry.py --remote-validate   # + POST /api/templates/validate
#   python3 release_entry.py --publish       # publish (wrapped envelope)
#   python3 release_entry.py --build         # publish + trigger build + stream events to ready
#   python3 release_entry.py --build --launch WS_ID  # publish, build, then launch a test VM
#   Edit the VERSION constant, rerun the full release ratchet, then use --build.
#
# Revenue Partner release: source-grounded GTM behavior, tenant-neutral runtime,
# approval-constrained production actions, and deterministic browser packaging:
#   • 1Password secret plane (op CLI + narrow six-value allowlist)
#   • 1 configured/enabled MCP server: hosted Super Browser, attached by URL
#   • latitude-telemetry-hermes stdlib-registered plugin + core reasoning_config patch
#   • AgentPhone future-integration source with immutable network hard stops
#   • Curated Revenue Partner skill, SOUL.md persona, and operating defaults
#
# NO SECRETS are baked. The template declares only permitted setup values; the
# on_resume hook bridges any that Orgo injects into /root/.env, 1Password
# resolves the narrow allowlist at every Hermes start. Disabled connector keys
# are neither requested nor mapped. build-recipe.md §4: we do NOT use
# env:{secret}/files:secret:// (they crash the build at compile), so the
# secrets block is declarative only.
import argparse
import base64
import hashlib
import hmac
import json
import io
import os
import re
import secrets
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "files")
NAMESPACE = "default"
NAME = "revenue-partner-agent"
VERSION = "1.0.1"
API_BASE = "https://www.orgo.ai/api"
MAX_PUBLICATION_BODY_BYTES = 1_000_000
MAX_ORGO_RESPONSE_BYTES = 1_048_576
MAX_ORGO_SSE_LINE_BYTES = 65_536
MAX_ORGO_SSE_TOTAL_BYTES = 4_194_304
MAX_ORGO_SSE_EVENTS = 10_000
ORGO_SSE_DEADLINE_SECONDS = 3_600
TEMPLATE_SCHEMA_PATH = os.path.join(HERE, "template-schema.json")
TEMPLATE_SCHEMA_SHA256 = "619fbd1becd060a4c5c0de28c325f8e96b4f6cb456ef6c8f8cacdb0789932dd7"
REVIEW_ATTESTATIONS_ENV = "REVENUE_PARTNER_REVIEW_ATTESTATIONS"
GIT = "/usr/bin/git"
SSH_KEYGEN = "/usr/bin/ssh-keygen"
EXTERNAL_REVIEW_TRUST_ROOT_PATH = "/etc/revenue-partner/reviewers.allowed_signers"
REVIEW_SIGNATURE_NAMESPACE = "revenue-partner-review"
OPERATION_INTENT_DIRECTORY_ENV = "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY"
OPERATION_SIGNATURE_NAMESPACE = "revenue-partner-operation"
OPERATION_INTENT_WAIT_SECONDS = 600
BROKER_FD_ENV = "REVENUE_PARTNER_BROKER_FD"
BROKER_SECRET_ENV = "REVENUE_PARTNER_BROKER_SECRET"
BROKER_KEY_SHA256_ENV = "REVENUE_PARTNER_BROKER_KEY_SHA256"


def _validate_orgo_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.orgo.ai"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/api/")
    ):
        raise ValueError("Orgo request target must use the fixed https://www.orgo.ai/api/ authority")


OBSIDIAN_DEB_URL = ("https://github.com/obsidianmd/obsidian-releases/releases/"
                    "download/v1.12.7/obsidian_1.12.7_amd64.deb")
OBSIDIAN_DEB_SHA = "3644e3ef19bcd23db4d17f7c73311b5245429391a2a48b361da93375f59712b0"
OP_CLI_URL = "https://cache.agilebits.com/dist/1P/op2/pkg/v2.34.1/op_linux_amd64_v2.34.1.zip"
OP_CLI_SHA = "b13ed106335419ea0fb0ebd7ebbb3b48cf26a2f214eb4b2fd8d950548e7980ed"
NODE_URL = "https://nodejs.org/dist/v24.19.0/node-v24.19.0-linux-x64.tar.xz"
NODE_SHA = "14b342e71204f811bde6153be8e04b62aef63c236fef92b55f9c83154b409647"



GIT_SAFE_ARGS = ["-c", "core.fsmonitor=false"]


def _scrubbed_env():
    """Build a from-scratch environment for git/ssh-keygen subprocesses.

    No operator variable survives: gitconfig, fsmonitor hooks, index/object
    redirection, and credential variables cannot reach a child of the
    key-less builder.
    """
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/tmp",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }


def rd(rel):
    repo_path = f"files/{rel}".replace(os.sep, "/")
    return subprocess.check_output([GIT, *GIT_SAFE_ARGS, "show", f":{repo_path}"], cwd=HERE, env=_scrubbed_env()).decode("utf-8")


# --------------------------------------------------------------------------
# files[]  — staged under /opt/revenue-partner/stage (copied into place post-install
# so the Hermes installer can never clobber them) + scripts/icons at final paths
# --------------------------------------------------------------------------
def F(to, body, mode="0644", when="build", owner=None, group=None):
    e = {"to": to, "inline": body, "mode": mode, "when": when}
    if owner:
        e["owner"] = owner
    if group:
        e["group"] = group
    return e


STAGE = "/opt/revenue-partner/stage"


def payload_b64():
    """Pack curated tenant-neutral runtime trees into one deterministic archive.
    ONE deterministic tar.gz (base64) — inlining ~130 files individually blew
    the publish endpoint's body-size limit ("request body too large"). Modes
    are set in-archive (0755 for *.sh + anything under a scripts/ dir); mtime,
    uid and gid are zeroed so identical content publishes byte-identically."""
    import gzip
    import io
    import tarfile
    buf = io.BytesIO()
    entries = []
    runtime_roots = (
        ("build-locks", "build-locks"),
        ("skills/go-to-market/revenue-partner", "hermes/skills/go-to-market/revenue-partner"),
        ("scripts", "hermes/scripts"),
        ("local-packages/latitude-telemetry-hermes",
         "hermes/local-packages/latitude-telemetry-hermes"),
        ("agent-knowledge", "agent-knowledge"),
    )
    pathspecs = [f"files/{rel_root}" for rel_root, _ in runtime_roots]
    tracked = subprocess.check_output([GIT, *GIT_SAFE_ARGS, "ls-files", "-z", "--", *pathspecs], cwd=HERE, env=_scrubbed_env()).split(b"\0")
    for raw_path in sorted(item for item in tracked if item):
        repo_path = raw_path.decode("utf-8")
        for rel_root, prefix in runtime_roots:
            root_prefix = f"files/{rel_root}/"
            if not repo_path.startswith(root_prefix):
                continue
            rel = repo_path[len(root_prefix):]
            name = rel.rsplit("/", 1)[-1]
            data = subprocess.check_output([GIT, *GIT_SAFE_ARGS, "show", f":{repo_path}"], cwd=HERE, env=_scrubbed_env())
            mode = 0o755 if (name.endswith(".sh") or "/scripts/" in f"/{rel}"
                             or rel_root == "scripts") else 0o644
            entries.append((f"{prefix}/{rel}", data, mode))
            break
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for arcname, data, mode in sorted(entries):
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mode = mode
                info.mtime = 0
                info.uid = info.gid = 0
                tar.addfile(info, io.BytesIO(data))
    n = len(entries)
    print(f"payload.tgz: {n} files, {buf.tell()//1024}KB compressed")
    return base64.b64encode(buf.getvalue()).decode("ascii")


files = [
    # --- staged Hermes config / identity / env ---
    F(f"{STAGE}/hermes/config.yaml", rd("config.yaml"), "0600"),
    F(f"{STAGE}/hermes/SOUL.md", rd("SOUL.md"), "0644"),
    F(f"{STAGE}/hermes/env", rd("hermes.env"), "0600"),
    # --- curated runtime trees, one deterministic tarball ---
    F("/opt/revenue-partner/payload.tgz.b64", payload_b64(), "0644"),
    # --- reviewed AgentPhone source; executable entrypoint hard-stopped ---
    F(f"{STAGE}/agentphone-bridge/agentphone_bridge.py",
      rd("agentphone-bridge/agentphone_bridge.py"), "0700"),
    F(f"{STAGE}/agentphone-bridge/env", rd("agentphone-bridge/env"), "0600"),
    F(f"{STAGE}/agentphone-bridge/test_event_ordering.py",
      rd("agentphone-bridge/test_event_ordering.py"), "0644"),
    # --- staged Obsidian vault skeleton + vault registry ---
    F(f"{STAGE}/vault/Welcome.md", rd("vault/Welcome.md"), "0644"),
    F(f"{STAGE}/vault/.obsidian/app.json", rd("vault/.obsidian/app.json"), "0644"),
    F(f"{STAGE}/vault/.obsidian/appearance.json", rd("vault/.obsidian/appearance.json"), "0644"),
    F(f"{STAGE}/vault/.obsidian/core-plugins.json", rd("vault/.obsidian/core-plugins.json"), "0644"),
    F(f"{STAGE}/obsidian.json", rd("obsidian-registry.json"), "0644"),
    # --- executables (installer never touches /usr/local/bin) ---
    F("/usr/local/bin/hermes-gateway-run.sh", rd("gateway-run.sh"), "0755"),
    F("/usr/local/bin/revenue-partner-agentphone-bridge-run.sh", rd("agentphone-bridge-run.sh"), "0755"),
    F("/usr/local/bin/revenue-partner-onboard.sh", rd("onboard.sh"), "0755"),
    F("/usr/local/bin/revenue-partner-op-enable", rd("op-enable.py"), "0755"),
    F("/usr/local/bin/revenue-partner-onboard-launch.sh", rd("onboard-launch.sh"), "0755"),
    F("/usr/local/bin/revenue-partner-telegram-pair.py", rd("telegram-pair.py"), "0755"),
    F("/usr/local/bin/obsidian-launch", rd("obsidian-launch"), "0755"),
    F("/usr/local/bin/revenue-partner-env-bridge", rd("safe-env-bridge.py"), "0755"),
    # --- desktop icons ---
    F("/root/Desktop/Obsidian.desktop", rd("Obsidian.desktop"), "0755"),
    F("/root/Desktop/RevenuePartnerSetup.desktop", rd("RevenuePartnerSetup.desktop"), "0755"),
    F("/root/.hermes/daily-brief.prompt", rd("daily-brief.prompt"), "0644"),
]

# --------------------------------------------------------------------------
# apps[].install — the one build-time script (runs as root, after files staged)
# --------------------------------------------------------------------------
INSTALL = f"""
set -e
export DEBIAN_FRONTEND=noninteractive
export HOME=/root
export HERMES_HOME=/root/.hermes
export PATH=/usr/local/bin:/root/.hermes/bin:/root/.hermes/node/bin:/root/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH

# 0) Extract the deterministic payload before dependency installation so the
#    committed Python lockfiles are available to every install step.
mkdir -p {STAGE}
base64 -d /opt/revenue-partner/payload.tgz.b64 | tar xzf - -C {STAGE}

# 1) Node.js + npm — immutable LTS archive with official SHA-256.
curl -fsSL "{NODE_URL}" -o /tmp/node.tar.xz
echo "{NODE_SHA}  /tmp/node.tar.xz" | sha256sum -c -
tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1
rm -f /tmp/node.tar.xz
node --version
npm --version

# 2) Hermes Agent 0.18.0, uv 0.12.4, and QR support. The full Linux/Python
#    dependency graph is version- and hash-locked in the staged lockfile.
python3 -m venv /usr/local/lib/hermes-agent/venv
VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python
"$VENV_PY" -m pip install --require-hashes -r {STAGE}/build-locks/hermes-runtime.lock
"$VENV_PY" {STAGE}/hermes/scripts/prune_hermes_runtime.py
mkdir -p /root/.hermes/bin
ln -sf /usr/local/lib/hermes-agent/venv/bin/hermes /usr/local/bin/hermes
ln -sf /usr/local/lib/hermes-agent/venv/bin/hermes /root/.hermes/bin/hermes
ln -sf /usr/local/lib/hermes-agent/venv/bin/uv /usr/local/bin/uv
ln -sf /usr/local/lib/hermes-agent/venv/bin/uv /root/.hermes/bin/uv
hermes --version
uv --version

# 3) 1Password CLI — pinned release plus verified archive checksum.
curl -fsSL "{OP_CLI_URL}" -o /tmp/op.zip
echo "{OP_CLI_SHA}  /tmp/op.zip" | sha256sum -c -
python3 -c "import zipfile; zipfile.ZipFile('/tmp/op.zip').extract('op', '/tmp/opx')"
install -m 0755 /tmp/opx/op /usr/bin/op
rm -rf /tmp/op.zip /tmp/opx
op --version

# 4) Obsidian 1.12.7 (pinned) — extract the .deb (GUI deps already present via
#    Chrome); libsecret-1-0 is the only extra and pulls no libssl upgrade.
curl -fsSL "{OBSIDIAN_DEB_URL}" -o /tmp/obsidian.deb
echo "{OBSIDIAN_DEB_SHA}  /tmp/obsidian.deb" | sha256sum -c -
dpkg-deb -x /tmp/obsidian.deb /
ln -sf /opt/Obsidian/obsidian /usr/bin/obsidian
rm -f /tmp/obsidian.deb
apt-get install -y -qq --no-install-recommends libsecret-1-0 >/dev/null 2>&1 || true

# 8) Place staged Hermes config/identity/env/plugins/skills/scripts/packages.
#    The deterministic payload was already extracted before dependency install.
mkdir -p {STAGE}
mkdir -p /root/.hermes/skills /root/.hermes/scripts \\
         /root/.hermes/local-packages /root/.hermes/memories /root/.hermes/state \\
         /root/agent-knowledge /root/.super-browser \\
         /root/.hermes_agentphone_bridge /root/Documents/HermesVault \\
         /root/.config/obsidian /var/log/orgo /var/lib/orgo
cp -f  {STAGE}/hermes/config.yaml /root/.hermes/config.yaml
cp -f  {STAGE}/hermes/SOUL.md     /root/.hermes/SOUL.md
cp -f  {STAGE}/hermes/env         /root/.hermes/.env
cp -rf {STAGE}/hermes/skills/.    /root/.hermes/skills/
cp -rf {STAGE}/hermes/scripts/.   /root/.hermes/scripts/
cp -rf {STAGE}/hermes/local-packages/. /root/.hermes/local-packages/
cp -rf {STAGE}/agent-knowledge/.  /root/agent-knowledge/
cp -rf {STAGE}/vault/.            /root/Documents/HermesVault/
cp -f  {STAGE}/obsidian.json      /root/.config/obsidian/obsidian.json
chmod 600 /root/.hermes/config.yaml /root/.hermes/.env

# 9) Browser/computer orchestration is a hosted service. Super Browser is
#    attached by URL as an MCP server (see config.yaml) rather than vendored:
#    the providers, Playwright runtime, and approval lifecycle all live on the
#    server. Vendoring a second copy also meant installing a second dependency
#    lock into this venv, which silently rewrote six of the agent's own pins.

# 10) AgentPhone bridge source (supervised entrypoint remains non-executable).
cp -f {STAGE}/agentphone-bridge/agentphone_bridge.py /root/.hermes_agentphone_bridge/
cp -f {STAGE}/agentphone-bridge/env                  /root/.hermes_agentphone_bridge/env
cp -f {STAGE}/agentphone-bridge/test_event_ordering.py /root/.hermes_agentphone_bridge/
chmod 700 /root/.hermes_agentphone_bridge/agentphone_bridge.py
chmod 600 /root/.hermes_agentphone_bridge/env

# 11) Latitude telemetry: register the local package directly in the locked
#     Hermes venv with standard-library-written .pth/.dist-info metadata and
#     apply the reasoning_config core hook patch (idempotent; re-run after any
#     `hermes update`). Fails the build loudly if the anchor moved.
bash /root/.hermes/scripts/latitude/install_local_telemetry_patch.sh

echo "revenue-partner-agent install complete"
""".strip()

# --------------------------------------------------------------------------
# hooks
# --------------------------------------------------------------------------
ON_FIRST_BOOT = """
mkdir -p /var/lib/orgo /var/log/orgo /root/.hermes/memories /root/.hermes/state
[ -f /var/lib/orgo/revenue-partner.stamp ] || echo "revenue partner first boot $(date -Iseconds)" > /var/lib/orgo/revenue-partner.stamp
# Lean + supervisord-safe (this also runs during the build). No hermes calls.
""".strip()

# on_resume: safely bridge allowlisted vault secrets into Hermes, then restart.
ON_RESUME = """
mkdir -p /root/.hermes /root/.hermes/state

# Parse allowlisted dotenv values without shell evaluation, quote them safely,
# and atomically replace ~/.hermes/.env with mode 0600.
/usr/local/bin/revenue-partner-env-bridge

# The 1Password service-account token lives in its own bootstrap file
# (~/.hermes/.op.env), NOT .env — hermes loads it before resolving op:// refs.
# The baked map ships disabled (token-less op prompts on /dev/tty and stalls
# interactive hermes starts); revenue-partner-op-enable flips it on with a token.
if [ -n "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]; then
  /usr/local/bin/revenue-partner-env-bridge \
    --target /root/.hermes/.op.env \
    --only OP_SERVICE_ACCOUNT_TOKEN
fi
python3 /usr/local/bin/revenue-partner-op-enable 2>/dev/null || true

# Restart the gateway so it re-reads .env + config (Hermes has no hot reload).
# AgentPhone credentials cannot wake the hard-stopped bridge in this release.
supervisorctl restart hermes-gateway 2>/dev/null || true
""".strip()

ON_EVERY_BOOT = """
# Idempotent boot checks; supervised services start independently.
#
# Recreate the daily brief if it is absent. The schedule is part of the image,
# not a manual post-install step -- a rebuilt box that boots without its daily
# loop is a silently inert agent, which is the failure this template keeps
# guarding against. Jobs are matched by name so a resume never duplicates one,
# and jobs.json is deliberately NOT baked into the payload: it carries run
# state, ids and next-run timestamps that must not ship.
#
# Delivery follows SLACK_HOME_CHANNEL. With no home channel there is nowhere to
# report, so the job is skipped rather than created to deliver into the void.
set +e
export HOME=/root HERMES_HOME=/root/.hermes
export PATH=/usr/local/bin:/root/.hermes/bin:/usr/bin:/bin:$PATH

BRIEF_NAME="Revenue Partner Daily Brief"
BRIEF_PROMPT=/root/.hermes/daily-brief.prompt
HOME_CHANNEL="$(grep -m1 '^SLACK_HOME_CHANNEL=' /root/.hermes/.env 2>/dev/null | cut -d= -f2-)"

if [ -s "$BRIEF_PROMPT" ] && [ -n "$HOME_CHANNEL" ] && command -v hermes >/dev/null 2>&1; then
  if ! hermes cron list 2>/dev/null | grep -qF "$BRIEF_NAME"; then
    hermes cron create '0 13 * * *' "$(cat "$BRIEF_PROMPT")" \
      --name "$BRIEF_NAME" --deliver "slack:${HOME_CHANNEL}" >/dev/null 2>&1 \
      && echo "daily_brief_scheduled" || echo "daily_brief_schedule_failed"
  fi
fi

exit 0
""".strip()

# --------------------------------------------------------------------------
# The template document
# --------------------------------------------------------------------------
template = {
    "api_version": "orgo.ai/v1",
    "template": {
        "name": NAME,
        "version": VERSION,
        "description": ("Revenue Partner — a source-grounded Hermes GTM operator on Orgo. "
                        "Runs one Money Desk across reactivation, targeted outbound, affiliates, "
                        "podcasts/stages/sponsors, and coordinated content with Super Browser "
                        "orchestration, an explicit campaign approval policy, durable browser/phone "
                        "gates, persistent knowledge, and optional Latitude observability. Disabled "
                        "connectors do not request or accept activation credentials in this release."),
        "publisher": "orgo",
        "license": "MIT",
        "homepage": "https://aiintegraterz.com/revenue-partner",

    },
    # Modest, matches the proven-green build shape (no explicit os/gpu).
    "hardware": {
        "cpu": 1,
        "ram_gb": 4,
        "disk_gb": 20,
        "resolution": "1280x720x24",
    },
    # Declarative only (names shown in the launch UI + vault). NOT referenced via
    # {secret:} anywhere (that crashes the build); on_resume bridges whatever the
    # vault injects. Only model/chat/telemetry setup values are accepted here;
    # disabled connector credentials are intentionally absent.
    "secrets": [
        {"name": "op_service_account_token", "optional": True,
         "description": "Optional 1Password service-account token for the narrow allowlisted model, Telegram, and telemetry map. It cannot activate disabled connectors.",
         "example": "ops_...", "docs_url": "https://developer.1password.com/docs/service-accounts/"},
        {"name": "latitude_api_key", "optional": True,
         "description": "Latitude API key — LLM/tool tracing (baked telemetry plugin) AND chat-side querying (latitude MCP). Pair with latitude_project.",
         "example": "…", "docs_url": "https://latitude.so"},
        {"name": "latitude_project", "optional": True,
         "description": "Latitude project slug for your traces.",
         "example": "my-agent"},
        {"name": "telegram_bot_token", "optional": True,
         "description": "Optional — the first-boot QR onboarding mints this for you. Supply a @BotFather token only if you prefer to bring your own.",
         "example": "123456789:AA...", "docs_url": "https://t.me/BotFather"},
        {"name": "telegram_allowed_users", "optional": True,
         "description": "Optional numeric Telegram user id allowlist (the QR onboarding auto-detects yours). Comma-separated.",
         "example": "123456789"},

    ],
    "build": {
        # MINIMAL + build-safe: no ca-certificates/openssl/curl (they'd upgrade
        # libssl3t64 and kill build-time supervisord). Python's venv bootstraps
        # the hash-locked Hermes runtime; Node is installed from a verified archive.
        "apt": ["git", "xz-utils", "python3-venv", "python3-yaml", "ripgrep", "ffmpeg"],
    },
    "files": files,
    "apps": [
        {
            "name": "hermes-gateway",
            "title": "Hermes Gateway",
            "description": ("Hermes gateway daemon — Slack and Telegram channels, 4 configured/enabled "
                            "MCP connections: the hosted Super Browser policy server, browser-box (read "
                            "tools), data-box and Scrape Creators; "
                            "model/telemetry plugins, with production-capable remote toolsets absent."),
            "install": INSTALL,
            "services": [
                {
                    "name": "hermes-gateway",
                    "title": "Hermes gateway",
                    "run": "/usr/local/bin/hermes-gateway-run.sh",
                    "user": "root",
                    "restart": "always",
                },
                {
                    "name": "agentphone-bridge",
                    "title": "AgentPhone bridge hard stop",
                    "run": "/usr/local/bin/revenue-partner-agentphone-bridge-run.sh",
                    "user": "root",
                    "restart": "always",
                },
            ],
            "autostart": [
                {"run": "/usr/local/bin/revenue-partner-onboard-launch.sh", "delay": 10},
                {"run": "/usr/local/bin/obsidian-launch", "delay": 16},
            ],
        }
    ],
    "hooks": {
        "on_first_boot": ON_FIRST_BOOT,
        "on_resume": ON_RESUME,
        "on_every_boot": ON_EVERY_BOOT,
    },
    "terminal": [
        {
            "name": "hermes",
            "title": "Hermes",
            "description": "Host shell for the Hermes agent (hermes auth, logs, config).",
            "cwd": "/root",
        }
    ],
}


# Capture the exact staged tree after every template byte has been assembled
# from Git-index blobs. Final side-effect gates require this identity unchanged.
ASSEMBLED_TREE = subprocess.check_output([GIT, *GIT_SAFE_ARGS, "write-tree"], cwd=HERE, text=True, env=_scrubbed_env()).strip()


# --------------------------------------------------------------------------
# validate / publish / build / launch
# --------------------------------------------------------------------------
def local_validate() -> bool:
    try:
        import jsonschema
    except ImportError:
        print("! jsonschema not installed — local schema validation unavailable")
        return False
    try:
        schema_bytes = Path(TEMPLATE_SCHEMA_PATH).read_bytes()
    except OSError as exc:
        print(f"! required bundled schema unavailable: {exc}")
        return False
    digest = hashlib.sha256(schema_bytes).hexdigest()
    if digest != TEMPLATE_SCHEMA_SHA256:
        print("! bundled template schema checksum mismatch")
        return False
    try:
        schema = json.loads(schema_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"! bundled template schema is invalid JSON: {exc}")
        return False
    try:
        jsonschema.validate(template, schema)
    except jsonschema.ValidationError as exc:
        print(f"! local jsonschema validation FAILED: {exc.message}")
        return False
    print("✓ local jsonschema validation PASSED")
    return True


def _json_body_bytes(body):
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def publication_envelope():
    return {"namespace": NAMESPACE, "name": NAME, "version": VERSION, "template": template}


def publication_body_bytes():
    return _json_body_bytes(publication_envelope())


def resolved_artifact_bytes():
    return (json.dumps(template, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def publication_body_within_limit():
    size = len(publication_body_bytes())
    ok = size < MAX_PUBLICATION_BODY_BYTES
    status = "PASSED" if ok else "FAILED"
    print(f"{status}: serialized publication request {size} < {MAX_PUBLICATION_BODY_BYTES} bytes")
    return ok


def _owner_only_regular_file(path):
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and info.st_uid == os.geteuid()


class _ApprovedRequest:
    __slots__ = ("operation", "method", "url", "body", "publication_digest", "publication_ref", "_used")

    def __init__(self, operation, method, url, body, publication_receipt=None):
        self.operation = operation
        self.method = method
        self.url = url
        self.body = body
        self.publication_digest = publication_receipt.digest if publication_receipt else None
        self.publication_ref = publication_receipt.ref if publication_receipt else None
        self._used = False

    def consume(self, expected_operation, publication_receipt=None):
        if self.operation != expected_operation:
            raise RuntimeError("release capability does not authorize this operation")
        if self._used:
            raise RuntimeError("release capability has already been consumed")
        if expected_operation in {"build", "events", "launch"}:
            if not isinstance(publication_receipt, _PublicationReceipt):
                raise RuntimeError("bounded immutable publication identity required")
            if (self.publication_digest, self.publication_ref) != (
                publication_receipt.digest,
                publication_receipt.ref,
            ):
                raise RuntimeError("release capability publication identity mismatch")
        self._used = True
        return self.method, self.url, self.body

class _PublicationReceipt:
    __slots__ = ("ref", "digest", "published", "response")

    def __init__(self, ref, digest, published, response):
        self.ref = ref
        self.digest = digest
        self.published = published
        self.response = response


class _BuildReceipt:
    __slots__ = ("ref", "digest", "status", "response")

    def __init__(self, ref, digest, status, response):
        self.ref = ref
        self.digest = digest
        self.status = status
        self.response = response


def _valid_publication_receipt(receipt):
    return (
        isinstance(receipt, _PublicationReceipt)
        and receipt.ref == f"{NAMESPACE}/{NAME}@{VERSION}"
        and isinstance(receipt.digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", receipt.digest) is not None
        and receipt.digest == hashlib.sha256(publication_body_bytes()).hexdigest()
    )


def _git_text(*args):
    return subprocess.check_output([GIT, *GIT_SAFE_ARGS, *args], cwd=HERE, text=True, env=_scrubbed_env()).strip()


def _assert_exact_assembled_tree():
    tree = _git_text("write-tree")
    if tree != ASSEMBLED_TREE:
        raise RuntimeError("Git index changed after exact-tree template assembly")
    diff = subprocess.run([GIT, *GIT_SAFE_ARGS, "diff", "--quiet", "--"], cwd=HERE, env=_scrubbed_env())
    if diff.returncode != 0:
        raise RuntimeError("tracked worktree differs from reviewed Git index")
    untracked = _git_text("ls-files", "--others", "--exclude-standard")
    if untracked:
        raise RuntimeError("non-ignored untracked files exist at the release side-effect boundary")
    return tree


def _review_statement_bytes(statement):
    return (json.dumps(statement, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _trusted_review_allowlist():
    external = Path(EXTERNAL_REVIEW_TRUST_ROOT_PATH)
    try:
        parent_info = external.parent.lstat()
        info = external.lstat()
        candidate_bytes = subprocess.check_output(
            [GIT, *GIT_SAFE_ARGS, "show", ":.github/reviewers.allowed_signers"], cwd=HERE, env=_scrubbed_env()
        )
        external_bytes = external.read_bytes()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"external reviewer trust root is unavailable: {exc}") from exc
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or parent_info.st_uid != 0
        or stat.S_IMODE(parent_info.st_mode) != 0o755
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != 0
        or stat.S_IMODE(info.st_mode) != 0o644
    ):
        raise RuntimeError("external reviewer trust root requires a root-owned 0755 directory and 0644 regular file")
    if external_bytes != candidate_bytes:
        raise RuntimeError("candidate reviewer allowlist differs from external reviewer trust policy")
    return str(external)


def _verify_review_signature(reviewer_id, statement, signature_path):
    if not signature_path.is_absolute() or not _owner_only_regular_file(signature_path):
        raise RuntimeError("review signature must be an absolute owner-only mode-0600 regular file")
    if signature_path.stat().st_size > 16384:
        raise RuntimeError("review signature is too large")
    trusted_allowlist = _trusted_review_allowlist()
    result = subprocess.run(
        [SSH_KEYGEN, "-Y", "verify", "-f", trusted_allowlist, "-I", reviewer_id,
         "-n", REVIEW_SIGNATURE_NAMESPACE, "-s", str(signature_path)],
        input=_review_statement_bytes(statement), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=_scrubbed_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"review signature verification failed for {reviewer_id}")


def _operation_intent_statement(operation, method, url, data, publication_receipt, nonce):
    if operation not in {"validate", "publish", "readback", "build", "events", "launch"}:
        raise RuntimeError("unsupported authenticated operation intent")
    if method not in {"GET", "POST"}:
        raise RuntimeError("operation intent method is invalid")
    if re.fullmatch(r"[0-9a-f]{64}", nonce or "") is None:
        raise RuntimeError("operation intent nonce must be 256-bit lowercase hex")
    publication_digest = None
    if publication_receipt is not None:
        if not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("operation intent publication identity is invalid")
        publication_digest = publication_receipt.digest
    if operation in {"readback", "build", "events", "launch"} and publication_digest is None:
        raise RuntimeError("operation intent requires immutable publication identity")
    tree = _assert_exact_assembled_tree()
    resolved = Path(HERE) / f"{NAME}.resolved.json"
    now = time.time()
    return {
        "operation": operation,
        "nonce": nonce,
        "issued_at": now,
        "expires_at": now + OPERATION_INTENT_WAIT_SECONDS,
        "method": method,
        "url": url,
        "body_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "template_ref": f"{NAMESPACE}/{NAME}@{VERSION}",
        "publication_digest": publication_digest,
        "tree": tree,
        "artifact_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "publication_sha256": hashlib.sha256(publication_body_bytes()).hexdigest(),
    }


def _write_private_exclusive(path, content):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _await_signed_operation_intent(operation, method, url, data=None, publication_receipt=None):
    directory_text = os.environ.get(OPERATION_INTENT_DIRECTORY_ENV, "")
    if not directory_text:
        raise RuntimeError(f"{OPERATION_INTENT_DIRECTORY_ENV} not set; externally signed operation intent required")
    directory = Path(directory_text)
    if not directory.is_absolute():
        raise RuntimeError("operation intent directory must use an absolute path")
    try:
        info = directory.lstat()
    except OSError as exc:
        raise RuntimeError(f"operation intent directory is unavailable: {exc}") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise RuntimeError("operation intent directory must be an owner-only non-symlink directory")
    nonce = secrets.token_hex(32)
    statement = _operation_intent_statement(operation, method, url, data, publication_receipt, nonce)
    stem = f"{operation}-{nonce}"
    pending_path = directory / f"{stem}.pending.json"
    intent_path = directory / f"{stem}.intent.json"
    _write_private_exclusive(pending_path, _review_statement_bytes(statement))
    print(f"awaiting external release-operator signature: {pending_path}")
    print(f"expected signed operation intent: {intent_path}")
    deadline = time.monotonic() + OPERATION_INTENT_WAIT_SECONDS
    while not intent_path.exists() and time.monotonic() < deadline:
        time.sleep(1)
    if not intent_path.exists():
        raise RuntimeError("timed out awaiting externally signed operation intent")
    return str(intent_path)


def _verify_release_clearance(resolved_path):
    tree = _assert_exact_assembled_tree()
    attestation_text = os.environ.get(REVIEW_ATTESTATIONS_ENV, "")
    if not attestation_text:
        raise RuntimeError(f"{REVIEW_ATTESTATIONS_ENV} not set; two signed exact-tree CLEAR reviews are required")
    attestation_path = Path(attestation_text)
    if not attestation_path.is_absolute() or not _owner_only_regular_file(attestation_path):
        raise RuntimeError("review attestation must be an absolute owner-only mode-0600 regular file")
    if attestation_path.stat().st_size > 131072:
        raise RuntimeError("review attestation is too large")
    try:
        record = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"review attestation is unreadable: {exc}") from exc

    resolved_bytes = Path(resolved_path).read_bytes()
    expected = {"tree": tree, "artifact_sha256": hashlib.sha256(resolved_bytes).hexdigest(),
                "publication_sha256": hashlib.sha256(publication_body_bytes()).hexdigest()}
    for key, value in expected.items():
        if record.get(key) != value:
            raise RuntimeError(f"review attestation {key} does not match current release bytes")

    reviews = record.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise RuntimeError("exactly two signed review attestations are required")
    required_reviewers = {"documentation", "security"}
    seen_reviewers = set()
    signature_paths = set()
    for review in reviews:
        if not isinstance(review, dict):
            raise RuntimeError("review attestation entry must be an object")
        reviewer_id = review.get("reviewer_id")
        statement = review.get("statement")
        signature_text = review.get("signature_path")
        if reviewer_id not in required_reviewers or not isinstance(statement, dict):
            raise RuntimeError("reviewer identity is not in the release-controlled signer allowlist")
        expected_statement = {**expected, "reviewer_id": reviewer_id, "verdict": "CLEAR"}
        if statement != expected_statement:
            raise RuntimeError("signed review statement does not exactly bind CLEAR to current release bytes")
        signature_path = Path(signature_text) if isinstance(signature_text, str) else Path()
        _verify_review_signature(reviewer_id, statement, signature_path)
        seen_reviewers.add(reviewer_id)
        signature_paths.add(str(signature_path.resolve()))
    if seen_reviewers != required_reviewers or len(signature_paths) != 2:
        raise RuntimeError("documentation and security reviews require distinct signatures")
    if _assert_exact_assembled_tree() != tree:
        raise RuntimeError("exact release tree changed during review verification")
    return tree


def require_release_clearance(
    resolved_path, *, operation, workspace_id=None, publication_receipt=None
):
    tree = _verify_release_clearance(resolved_path)
    print(f"✓ two signed exact-tree CLEAR reviews bound to {tree}")
    if operation == "validate":
        return _ApprovedRequest(operation, "POST", f"{API_BASE}/templates/validate", _json_body_bytes(template))
    if operation == "publish":
        return _ApprovedRequest(operation, "POST", f"{API_BASE}/templates", publication_body_bytes())
    if operation == "build":
        if not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("build requires a bounded immutable publication identity")
        return _ApprovedRequest(
            operation, "POST", f"{API_BASE}/templates/{NAMESPACE}/{NAME}/{VERSION}/build", None,
            publication_receipt,
        )
    if operation == "events":
        if not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("event streaming requires a bounded immutable publication identity")
        return _ApprovedRequest(
            operation,
            "GET",
            f"{API_BASE}/templates/{NAMESPACE}/{NAME}/{VERSION}/build/events",
            None,
            publication_receipt,
        )
    if operation == "launch":
        if not isinstance(workspace_id, str) or not workspace_id or len(workspace_id) > 256:
            raise RuntimeError("a bounded workspace identity is required for launch clearance")
        if not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("launch requires a bounded immutable publication identity")
        body = {
            "workspace_id": workspace_id,
            "name": "revenue-partner-smoke",
            "template_ref": publication_receipt.ref,
            "ram": 4,
            "cpu": 1,
        }
        return _ApprovedRequest(
            operation, "POST", f"{API_BASE}/computers", _json_body_bytes(body), publication_receipt
        )
    raise RuntimeError("unsupported release operation")


def _header_value(headers, name):
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    return getter(name) if callable(getter) else None


def _read_bounded_response(response, *, limit=MAX_ORGO_RESPONSE_BYTES, label="Orgo response"):
    declared = _header_value(getattr(response, "headers", None), "Content-Length")
    if declared is not None:
        try:
            declared_size = int(declared)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} has invalid Content-Length") from exc
        if declared_size < 0 or declared_size > limit:
            raise RuntimeError(f"{label} exceeds {limit} bytes")
    chunks = []
    total = 0
    while True:
        chunk = response.read(min(65_536, limit + 1 - total))
        if not chunk:
            break
        if not isinstance(chunk, (bytes, bytearray)):
            raise RuntimeError(f"{label} returned non-byte data")
        total += len(chunk)
        if total > limit:
            raise RuntimeError(f"{label} exceeds {limit} bytes")
        chunks.append(bytes(chunk))
    return b"".join(chunks).decode("utf-8", errors="replace")


def _read_bounded_http_error(error, *, label="Orgo error response"):
    try:
        return _read_bounded_response(error, label=label)
    finally:
        error.close()


def _json_object(text, label):
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return parsed


def _publication_receipt_from_response(status, body):
    if status < 200 or status >= 300:
        return None
    try:
        payload = _json_object(body, "publication response")
    except RuntimeError:
        return None
    ref = payload.get("ref")
    digest = payload.get("digest")
    published = payload.get("published")
    if ref != f"{NAMESPACE}/{NAME}@{VERSION}":
        return None
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        return None
    if digest != hashlib.sha256(publication_body_bytes()).hexdigest():
        return None
    if not isinstance(published, str) or not published:
        return None
    return _PublicationReceipt(ref, digest, published, payload)


def _build_receipt_from_response(status, body, publication_receipt):
    if status < 200 or status >= 300 or not _valid_publication_receipt(publication_receipt):
        return None
    try:
        payload = _json_object(body, "build response")
    except RuntimeError:
        return None
    ref = payload.get("ref")
    digest = payload.get("digest")
    build_status = payload.get("status")
    if ref != publication_receipt.ref or digest != publication_receipt.digest:
        return None
    if build_status not in {"building", "ready"}:
        return None
    return _BuildReceipt(ref, digest, build_status, payload)


def _broker_receipt_record(publication_receipt):
    if publication_receipt is None:
        return None
    if not _valid_publication_receipt(publication_receipt):
        raise RuntimeError("broker request requires a valid immutable publication receipt")
    return {"ref": publication_receipt.ref, "digest": publication_receipt.digest}


def _broker_exchange(operation, method, url, data, intent_path, publication_receipt=None):
    if "ORGO_API_KEY" in os.environ:
        raise RuntimeError("key-less builder must be launched through release_entry.py")
    fd_text = os.environ.get(BROKER_FD_ENV, "")
    if not fd_text.isdigit():
        raise RuntimeError("isolated authenticated transport broker is unavailable")
    key_sha256 = os.environ.get(BROKER_KEY_SHA256_ENV, "")
    if re.fullmatch(r"[0-9a-f]{64}", key_sha256 or "") is None:
        raise RuntimeError("builder must bind the exact credential digest supplied by the release entry")
    message = {
        "operation": operation,
        "method": method,
        "url": url,
        "body_b64": base64.b64encode(data).decode("ascii") if data is not None else None,
        "publication": _broker_receipt_record(publication_receipt),
        "build": None,
        "intent_path": intent_path,
        "key_sha256": key_sha256,
    }
    raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(raw) > 2_000_000:
        raise RuntimeError("broker request frame exceeds its byte ceiling")
    channel = socket.socket(fileno=os.dup(int(fd_text)))
    try:
        channel.sendall(raw)
        frames = []
        buffer = bytearray()
        while len(frames) < 2:
            chunk = channel.recv(min(65_536, 6_000_001 - len(buffer)))
            if not chunk:
                raise RuntimeError("authenticated transport broker closed without a response")
            buffer.extend(chunk)
            if len(buffer) > 6_000_000:
                raise RuntimeError("broker response frame exceeds its byte ceiling")
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                frames.append(bytes(line))
                if len(frames) == 2:
                    break
    finally:
        channel.close()
    response, mac_line = frames
    secret_text = os.environ.get(BROKER_SECRET_ENV, "")
    if re.fullmatch(r"[0-9a-f]{64}", secret_text or "") is None:
        raise RuntimeError("builder must verify broker responses with the release-entry MAC secret")
    expected_mac = hmac.new(secret_text.encode("ascii"), response + b"\n", hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac_line.decode("ascii", errors="replace"), expected_mac):
        raise RuntimeError("authenticated transport broker response failed MAC verification")
    try:
        record = json.loads(response)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("authenticated transport broker returned malformed JSON") from exc
    if not isinstance(record, dict) or set(record) not in ({"error"}, {"status", "body_b64"}):
        raise RuntimeError("authenticated transport broker returned malformed fields")
    if "error" in record:
        raise RuntimeError(f"authenticated transport broker failed closed: {record['error']}")
    try:
        status = int(record["status"])
        body = base64.b64decode(record["body_b64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("authenticated transport broker returned invalid response encoding") from exc
    if status < 100 or status > 599:
        raise RuntimeError("authenticated transport broker returned invalid HTTP status")
    ceiling = MAX_ORGO_SSE_TOTAL_BYTES if operation == "events" else MAX_ORGO_RESPONSE_BYTES
    if len(body) > ceiling:
        raise RuntimeError("authenticated transport broker response exceeds operation ceiling")
    return status, body


def _verify_remote_publication_receipt(publication_receipt, *, timeout=60):
    if not _valid_publication_receipt(publication_receipt):
        raise RuntimeError("bounded local publication identity required for remote readback")
    _verify_release_clearance(os.path.join(HERE, f"{NAME}.resolved.json"))
    url = f"{API_BASE}/templates/{NAMESPACE}/{NAME}/{VERSION}"
    intent_path = _await_signed_operation_intent("readback", "GET", url, None, publication_receipt)
    try:
        status, body_bytes = _broker_exchange(
            "readback", "GET", url, None, intent_path, publication_receipt
        )
        body = body_bytes.decode("utf-8", errors="replace")
    except RuntimeError as exc:
        raise RuntimeError(f"immutable publication readback failed closed: {exc}") from exc
    if status < 200 or status >= 300:
        raise RuntimeError(f"immutable publication readback returned HTTP {status}: {body[:200]}")
    readback = _publication_receipt_from_response(status, body)
    if readback is None or readback.digest != publication_receipt.digest or readback.ref != publication_receipt.ref:
        raise RuntimeError("immutable publication readback did not match reference and signed digest")
    return readback


def _validation_response_ok(status, body):
    if status < 200 or status >= 300:
        return False
    try:
        payload = _json_object(body, "validation response")
    except RuntimeError:
        return False
    if payload.get("ok") is not True:
        return False
    echoed = payload.get("template")
    if not isinstance(echoed, dict) or not isinstance(echoed.get("template"), dict):
        return False
    if echoed.get("api_version") != "orgo.ai/v1":
        return False
    if echoed["template"].get("name") != NAME or str(echoed["template"].get("version", "")) != VERSION:
        return False
    echoed_files = echoed.get("files")
    if not isinstance(echoed_files, list) or len(echoed_files) != len(template["files"]):
        return False
    expected_targets = {entry["to"] for entry in template["files"]}
    echoed_targets = {entry.get("to") for entry in echoed_files if isinstance(entry, dict)}
    return echoed_targets == expected_targets


def remote_validate(approved):
    try:
        status, body = _send_approved(approved, "validate")
    except RuntimeError as exc:
        print(f"POST /templates/validate failed closed: {exc}")
        return False
    print(f"POST /templates/validate → {status}: {body[:400]}")
    return _validation_response_ok(status, body)


def _validate_transport_request(expected_operation, method, url, data, publication_receipt):
    if method != "POST":
        raise RuntimeError("authenticated release transport permits POST only")
    if expected_operation == "validate":
        if url != f"{API_BASE}/templates/validate" or data != _json_body_bytes(template):
            raise RuntimeError("validation request does not match signed current template bytes")
        return
    if expected_operation == "publish":
        if url != f"{API_BASE}/templates" or data != publication_body_bytes():
            raise RuntimeError("publish request does not match signed current publication bytes")
        return
    if expected_operation == "build":
        if not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("build request lacks a bounded publication identity")
        expected_url = f"{API_BASE}/templates/{NAMESPACE}/{NAME}/{VERSION}/build"
        if url != expected_url or data is not None or not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("build request does not match the readback-gated immutable publication identity")
        return
    if expected_operation == "launch":
        if url != f"{API_BASE}/computers" or not _valid_publication_receipt(publication_receipt):
            raise RuntimeError("launch request does not match the readback-gated immutable publication identity")
        try:
            body = _json_object(data.decode("utf-8"), "launch request")
        except (AttributeError, UnicodeError, RuntimeError) as exc:
            raise RuntimeError("launch request body is invalid") from exc
        expected_keys = {"workspace_id", "name", "template_ref", "ram", "cpu"}
        if set(body) != expected_keys:
            raise RuntimeError("launch request contains unexpected fields")
        workspace_id = body.get("workspace_id")
        if not isinstance(workspace_id, str) or not workspace_id or len(workspace_id) > 256:
            raise RuntimeError("launch request workspace identity is invalid")
        if body != {
            "workspace_id": workspace_id,
            "name": "revenue-partner-smoke",
            "template_ref": publication_receipt.ref,
            "ram": 4,
            "cpu": 1,
        }:
            raise RuntimeError("launch request does not bind the immutable publication identity")
        return
    raise RuntimeError("unsupported authenticated release operation")


def _send_approved(approved, expected_operation, publication_receipt=None, timeout=60):
    if not isinstance(approved, _ApprovedRequest):
        raise RuntimeError("signed release capability required at authenticated transport")
    method, url, data = approved.consume(expected_operation, publication_receipt)
    _validate_transport_request(expected_operation, method, url, data, publication_receipt)
    _verify_release_clearance(os.path.join(HERE, f"{NAME}.resolved.json"))
    if expected_operation in {"build", "launch"}:
        _verify_remote_publication_receipt(publication_receipt, timeout=timeout)
    intent_path = _await_signed_operation_intent(
        expected_operation, method, url, data, publication_receipt
    )
    status, body = _broker_exchange(
        expected_operation, method, url, data, intent_path, publication_receipt
    )
    return status, body.decode("utf-8", errors="replace")


def publish(approved):
    try:
        status, body = _send_approved(approved, "publish")
    except RuntimeError as exc:
        print(f"POST /templates failed closed: {exc}")
        return None
    print(f"POST /templates → {status}: {body[:400]}")
    if status == 409:
        print("version already exists; refusing to build or launch unverified prior bytes — increment VERSION")
        return None
    receipt = _publication_receipt_from_response(status, body)
    if receipt is None:
        print("publication response lacked a matching reference, digest, and published timestamp")
        return None
    print(f"validated publication receipt {receipt.ref} digest {receipt.digest[:12]}…")
    return receipt


def _consume_build_events(response, *, deadline_seconds=ORGO_SSE_DEADLINE_SECONDS):
    started = time.monotonic()
    total_bytes = 0
    event_count = 0
    ready = False
    failed = False
    while True:
        if time.monotonic() - started > deadline_seconds:
            raise RuntimeError("build event stream exceeded its absolute deadline")
        line = response.readline(MAX_ORGO_SSE_LINE_BYTES + 1)
        if not line:
            break
        if not isinstance(line, (bytes, bytearray)):
            raise RuntimeError("build event stream returned non-byte data")
        if len(line) > MAX_ORGO_SSE_LINE_BYTES:
            raise RuntimeError("build event line exceeded its byte ceiling")
        total_bytes += len(line)
        if total_bytes > MAX_ORGO_SSE_TOTAL_BYTES:
            raise RuntimeError("build event stream exceeded its cumulative byte ceiling")
        text = bytes(line).decode("utf-8", errors="replace").rstrip()
        if text:
            print("  " + text[:2_000])
        if text.startswith("data: "):
            event_count += 1
            if event_count > MAX_ORGO_SSE_EVENTS:
                raise RuntimeError("build event stream exceeded its event-count ceiling")
            try:
                event = json.loads(text.removeprefix("data: "))
            except json.JSONDecodeError:
                event = {}
            if event.get("phase") == "ready" and event.get("level") == "success":
                ready = True
            if event.get("phase") in {"failed", "cancel", "timeout"} or event.get("level") == "error":
                failed = True
        if "build failed" in text.lower() or '"failed"' in text:
            failed = True
    return ready and not failed


def _stream_build_events(approved, publication_receipt):
    if not isinstance(approved, _ApprovedRequest):
        raise RuntimeError("signed one-use event capability required")
    if not _valid_publication_receipt(publication_receipt):
        raise RuntimeError("validated immutable publication identity required for event streaming")
    expected_url = f"{API_BASE}/templates/{NAMESPACE}/{NAME}/{VERSION}/build/events"
    method, url, data = approved.consume("events", publication_receipt)
    if method != "GET" or url != expected_url or data is not None:
        raise RuntimeError("event capability does not match immutable publication identity")
    _verify_remote_publication_receipt(publication_receipt, timeout=60)
    intent_path = _await_signed_operation_intent("events", "GET", url, None, publication_receipt)
    print("streaming build events (SSE):")
    try:
        status, body = _broker_exchange(
            "events", "GET", url, None, intent_path, publication_receipt
        )
        if status < 200 or status >= 300:
            print(f"build event stream returned HTTP {status}: {body[:200].decode('utf-8', errors='replace')}")
            return False
        return _consume_build_events(io.BytesIO(body))
    except RuntimeError as exc:
        print(f"build event stream failed closed: {exc}")
        return False


def build_and_stream(approved, publication_receipt):
    if not _valid_publication_receipt(publication_receipt):
        print("build refused: bounded immutable publication identity required")
        return False
    try:
        status, body = _send_approved(approved, "build", publication_receipt)
    except RuntimeError as exc:
        print(f"POST …/build failed closed: {exc}")
        return False
    print(f"POST …/build → {status}: {body[:200]}")
    build_receipt = _build_receipt_from_response(status, body, publication_receipt)
    if build_receipt is None:
        print("build response lacked a matching reference, digest, and build status")
        return False
    if build_receipt.status == "ready":
        print("✓ build already ready (reused golden snapshot)")
        return True
    try:
        event_capability = require_release_clearance(
            os.path.join(HERE, f"{NAME}.resolved.json"),
            operation="events",
            publication_receipt=publication_receipt,
        )
        return _stream_build_events(event_capability, publication_receipt)
    except RuntimeError as exc:
        print(f"build event stream refused: {exc}")
        return False


def launch(approved, publication_receipt):
    if not _valid_publication_receipt(publication_receipt):
        print("launch refused: bounded immutable publication identity required")
        return False
    try:
        request_body = _json_object(approved.body.decode("utf-8"), "launch request")
        status, response_text = _send_approved(approved, "launch", publication_receipt)
    except (AttributeError, UnicodeError, RuntimeError) as exc:
        print(f"POST /computers failed closed: {exc}")
        return False
    print(f"POST /computers → {status}: {response_text[:400]}")
    if status < 200 or status >= 300:
        return False
    try:
        parsed = _json_object(response_text, "launch response")
    except RuntimeError as exc:
        print(f"launch response rejected: {exc}")
        return False
    computer_id = parsed.get("id")
    workspace_id = parsed.get("workspace_id")
    if not isinstance(computer_id, (str, int)) or not str(computer_id).strip():
        print("launch response rejected: computer ID missing")
        return False
    if str(workspace_id) != request_body["workspace_id"]:
        print("launch response rejected: workspace identity mismatch")
        return False
    out = os.path.join(HERE, f"{NAME}.launch.json")
    with open(out, "w") as fh:
        json.dump(parsed, fh, indent=2)
    print(f"launch response → {os.path.relpath(out, HERE)}")
    return True


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Build, validate, publish, build, or launch the Revenue Partner template.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--remote-validate", action="store_true", help="validate the assembled template with Orgo")
    action.add_argument("--publish", action="store_true", help="publish the validated template")
    action.add_argument("--build", action="store_true", help="publish and build the validated template")
    parser.add_argument("--launch", metavar="WORKSPACE_ID", help="after --build, launch a smoke-test computer in the workspace")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.launch is not None and not args.build:
        sys.exit("--launch requires --build in the same invocation so the remote publication identity is bound")
    # Always assemble + dump the resolved, inspectable artifact.
    out = os.path.join(HERE, f"{NAME}.resolved.json")
    Path(out).write_bytes(resolved_artifact_bytes())
    n_files = len(template["files"])
    approx = sum(len(f.get("inline", "")) for f in template["files"])
    print(f"assembled template v{VERSION}: {n_files} files, ~{approx//1024}KB inline "
          f"→ {os.path.relpath(out, HERE)}")
    if not publication_body_within_limit():
        sys.exit("serialized publication request exceeds endpoint limit")
    local_ok = local_validate()
    remote_ok = False
    if args.remote_validate:
        try:
            validation_capability = require_release_clearance(out, operation="validate")
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            sys.exit(f"release clearance failed: {exc}")
        if not remote_validate(validation_capability):
            sys.exit("remote validation failed")
        remote_ok = True
    if not local_ok and not remote_ok and not (args.publish or args.build):
        sys.exit("local schema validation failed or unavailable")
    publication_receipt = None
    if args.publish or args.build:
        if not (local_ok or remote_ok):
            print("local validation unavailable; requiring authenticated remote validation")
            try:
                validation_capability = require_release_clearance(out, operation="validate")
            except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
                sys.exit(f"release clearance failed: {exc}")
            if not remote_validate(validation_capability):
                sys.exit("no successful schema validation; refusing publication")
            remote_ok = True
        try:
            publish_capability = require_release_clearance(out, operation="publish")
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            sys.exit(f"release clearance failed: {exc}")
        publication_receipt = publish(publish_capability)
        if not publication_receipt:
            sys.exit("publish failed")
    if args.build:
        try:
            build_capability = require_release_clearance(
                out, operation="build", publication_receipt=publication_receipt
            )
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            sys.exit(f"release clearance failed: {exc}")
        if not build_and_stream(build_capability, publication_receipt):
            sys.exit("build did not reach ready")
        print("✓ build ready")
    if args.launch is not None:
        try:
            launch_capability = require_release_clearance(
                out,
                operation="launch",
                workspace_id=args.launch,
                publication_receipt=publication_receipt,
            )
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            sys.exit(f"release clearance failed: {exc}")
        if not launch(launch_capability, publication_receipt):
            sys.exit("launch failed")


if __name__ == "__main__":
    main()
