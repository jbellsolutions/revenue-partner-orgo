"""Connection adapters. Presence of settings never counts as live verification."""
import hashlib
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from .catalog import SERVICES
from .http import fetch
from .storage import SetupError, fingerprint, install_tree, private_write, read_json

MCP_NAMES = {"super-browser": "super-browser", "agentcard": "agent-cards"}

def write_connection_context(runtime):
    lines = ["# Selected agent connections", "", "Use only the identities below. Never inherit a teammate’s credentials. External sends, calls, spending and permission changes need the owner’s explicit authorization in the trusted primary channel. Phone caller identity is not authorization.", ""]
    for name, field in (("agentphone", "number"), ("agentmail", "inbox_id")):
        selected = read_json(runtime.home / (name + ".json"))
        if selected.get(field):
            lines.append(name + ": " + selected[field])
    lines += ["", "Finish setup through orgo-onboard resume. A configured connection still needs its live capability check."]
    private_write(runtime.home / "orgo-connections.md", "\n".join(lines) + "\n")

def memory_host(runtime, config):
    explicit = runtime.env().get("HERMES_HONCHO_HOST")
    if explicit:
        return explicit
    if runtime.home.parent.name == "profiles":
        profile = "".join(c if c.isalnum() or c in "_-" else "_" for c in runtime.home.name).strip("_")
        return "hermes_" + (profile or "profile")
    return config.get("defaultHost") or "hermes"


def owner_aliases(runtime, extra=None):
    aliases = read_json(runtime.home / "owner-channels.json")
    channel = read_json(runtime.home / "orgo-channel.json").get("platform")
    if channel in {"slack", "telegram"}:
        aliases.update({channel + ":" + key: True for key in runtime.env().get(channel.upper() + "_ALLOWED_USERS", "").split(",") if key})
    aliases.update({"phone:" + key: True for key in read_json(runtime.home / "agentphone.json").get("owners", [])})
    aliases.update(extra or {})
    if any(not re.fullmatch(r"(?:(?:slack|telegram):[A-Za-z0-9_-]+|phone:\+[1-9][0-9]{7,14})", k) for k in aliases):
        raise SetupError("Owner memory mappings must contain explicit channel identities.")
    private_write(runtime.home / "owner-channels.json", json.dumps(aliases) + "\n")
    return aliases



def install_plugins(runtime):
    source = runtime.root / "onboarding/plugins"
    manifest = runtime.state.directory / "plugins.json"
    if not manifest.exists():
        known = read_json(runtime.root / "onboarding/donor-hashes.json")
        adopted = {}
        for relative, approved_hashes in known.items():
            target = runtime.home / "plugins" / relative
            if target.is_file():
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual in approved_hashes:
                    adopted[relative] = actual
        private_write(manifest, json.dumps(adopted) + "\n")
    install_tree(source, runtime.home / "plugins", runtime.state.directory / "plugins.json")


def mcp(runtime, name, url, *, key=None, header="Authorization", oauth=False, enabled=True):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SetupError("Use an authenticated HTTPS integration address.")
    settings = {"url": url, "enabled": enabled, "trust": "untrusted", "timeout": 60}
    if key:
        settings["headers"] = {header: ("Bearer " if header == "Authorization" else "") + "${" + key + "}"}
    if oauth:
        settings["auth"] = "oauth"
    runtime.set("mcp_servers." + name, settings)
    if oauth and enabled:
        runtime.hermes("mcp", "login", name, interactive=True, timeout=600)


def connection_fingerprint(runtime, service):
    env = runtime.env()
    values = {key: env.get(key, "") for key in SERVICES[service]["keys"]}
    values["settings"] = read_json(runtime.home / (service + ".json"))
    values["capture"] = env.get("LATITUDE_CAPTURE_MODE", "metadata") if service == "latitude" else ""
    if service == "super-browser":
        values.update({k: env.get(k, "") for k in ("SUPER_BROWSER_URL", "SUPER_BROWSER_TOKEN")})
    values["mcp"] = runtime.get("mcp_servers." + MCP_NAMES.get(service, service))
    if service == "a2a":
        values["peers"] = runtime.get("a2a_agents")
    if service == "honcho":
        values["memory"] = read_json(runtime.home / "honcho.json")
    return fingerprint(values)


def configure(runtime, service, options):
    try:
        _configure(runtime, service, options)
    except (SetupError, OSError, ValueError):
        runtime.state.mark_attention(service)
        raise


def restore_toolsets(runtime):
    for service in SERVICES:
        if runtime.get("mcp_servers." + MCP_NAMES.get(service, service) + ".enabled") is True:
            for platform in ("cli", "slack", "telegram"):
                key = "platform_toolsets." + platform
                selected = runtime.get(key)
                item = "mcp-" + MCP_NAMES.get(service, service)
                if isinstance(selected, list) and item not in selected:
                    runtime.set(key, selected + [item])


def adopt_connections(runtime):
    enabled = runtime.get("plugins.enabled") or []
    for service in SERVICES:
        if runtime.state.get(service)["status"] != "not_started":
            continue
        connected = runtime.get("mcp_servers." + MCP_NAMES.get(service, service) + ".enabled") is True
        connected |= service == "honcho" and runtime.get("memory.provider") == "honcho"
        connected |= service == "latitude" and "latitude-observer" in enabled
        if connected:
            runtime.state.set(service, "configured", check="existing-connection-detected", fingerprint=connection_fingerprint(runtime, service))
    write_connection_context(runtime)


def _configure(runtime, service, options):
    if service not in SERVICES:
        raise SetupError("Unknown optional connection.")
    env = runtime.env()
    values = {}
    for key in SERVICES[service]["keys"]:
        value = options.get(key) or env.get(key)
        if not value:
            raise SetupError("A required private credential or account setting is missing.")
        values[key] = value
    if service == "agentcard" and not values["AGENTCARD_API_KEY"].startswith("sk_test_"):
        raise SetupError("Use a dedicated AgentCard TEST key. Production credentials are not accepted during setup.")
    # Save only to this installation. No worker profile receives these values.
    if values:
        runtime.save_env(values)
        if runtime.kind == "compose":
            runtime.restart()
    if service == "honcho":
        identity = read_json(runtime.home / "orgo-identity.json")
        if not identity:
            raise SetupError("Personalize this agent before connecting memory.")
        path = runtime.home / "honcho.json"
        config = read_json(path)
        hosts = config.setdefault("hosts", {})
        host_key = memory_host(runtime, config)
        host = hosts.setdefault(host_key, hosts.get(host_key.replace("hermes_", "hermes.", 1), {}))
        # Existing workspace and peers are authoritative: never silently remap memory.
        instance = runtime.role["id"] + "-" + identity["instance_id"]
        defaults = {"enabled": True, "workspace": "orgo-" + instance, "aiPeer": instance,
                    "peerName": "owner-" + identity["instance_id"], "pinUserPeer": False,
                    "sessionStrategy": "per-session", "writeFrequency": "turn", "saveMessages": True}
        for key, value in defaults.items():
            host.setdefault(key, value)
        aliases = owner_aliases(runtime, options.get("owner_channels"))
        if not aliases:
            raise SetupError("Connect the owner's primary channel before mapping memory.")
        host.setdefault("userPeerAliases", {}).update({k.split(":", 1)[1]: host["peerName"] for k in aliases})
        # Key lives in the instance's private env; keep pre-existing config keys intact.
        private_write(path, json.dumps(config, indent=2) + "\n")
        runtime.set("memory.provider", "honcho")
        runtime.hermes("honcho", "sync", timeout=120)
    elif service == "latitude":
        mode = options.get("capture_mode", "metadata")
        if mode not in {"metadata", "sanitized"}:
            raise SetupError("Choose metadata or separately approved sanitized capture.")
        if mode == "sanitized" and options.get("sanitized_content_selected") is not True:
            raise SetupError("Sanitized conversation capture requires its own privacy selection.")
        runtime.save_env({"LATITUDE_CAPTURE_MODE": mode, "LATITUDE_SERVICE_NAME": runtime.role["id"]})
        install_plugins(runtime)
        runtime.hermes("plugins", "enable", "latitude-observer")
    elif service == "agentphone":
        from .phone import provision
        configure_phone(runtime, provision(runtime, options))
    elif service == "agentmail":
        from .discovery import select_inbox
        inbox = select_inbox(runtime, options)
        private_write(runtime.home / "agentmail.json", json.dumps({"inbox_id": inbox}) + "\n")
        mcp(runtime, service, SERVICES[service]["mcp"], key="AGENTMAIL_API_KEY", header="x-api-key")
    elif service == "composio":
        url = options.get("url") or runtime.get("mcp_servers.composio.url") or ("https://connect.composio.dev/mcp" if values["COMPOSIO_API_KEY"].startswith("ck_") else None)
        if not url:
            raise SetupError("Create this agent's Composio MCP session through the authorized account first.")
        host = urlsplit(url).hostname or ""
        if host not in {"connect.composio.dev", "mcp.composio.dev", "backend.composio.dev"}:
            raise SetupError("Use the MCP session address issued by Composio.")
        header = "x-consumer-api-key" if host == "connect.composio.dev" else "x-api-key"
        mcp(runtime, service, url, key="COMPOSIO_API_KEY", header=header)
    elif service == "pandadoc":
        region = options.get("region", "global")
        if region not in {"global", "eu"}:
            raise SetupError("Select the PandaDoc account's global or EU region.")
        mcp(runtime, service, "https://mcp.pandadoc." + ("eu" if region == "eu" else "com") + "/v1/mcp", oauth=True)
    elif service == "super-browser":
        if options.get("SUPER_BROWSER_TOKEN"):
            runtime.save_env({"SUPER_BROWSER_TOKEN": options["SUPER_BROWSER_TOKEN"]})
        url = options.get("url") or runtime.get("mcp_servers.super-browser.url") or (env.get("SUPER_BROWSER_URL", "").rstrip("/") + "/mcp" if env.get("SUPER_BROWSER_URL") else None)
        if not url:
            raise SetupError("Authorize this agent's Super Browser MCP connection first.")
        mcp(runtime, service, url, key="SUPER_BROWSER_TOKEN" if (options.get("SUPER_BROWSER_TOKEN") or env.get("SUPER_BROWSER_TOKEN")) else None, oauth=not (options.get("SUPER_BROWSER_TOKEN") or env.get("SUPER_BROWSER_TOKEN")))
    elif service == "scrapecreators":
        mcp(runtime, service, "https://api.scrapecreators.com/mcp", key="SCRAPECREATORS_API_KEY", header="x-api-key")
    elif service == "onepassword":
        vault = options.get("vault_id") or read_json(runtime.home / "onepassword.json").get("vault_id")
        if not vault:
            raise SetupError("Select the dedicated vault authorized for this agent.")
        private_write(runtime.home / "onepassword.json", json.dumps({"vault_id": vault}) + "\n")
    elif service == "a2a":
        from .collaboration import configure as pair
        pair(runtime, options)
    elif service == "agentcard":
        # A TEST-only API key cannot be switched into production by an MCP tool.
        if not values["AGENTCARD_API_KEY"].startswith("sk_test_"):
            raise SetupError("Use a dedicated AgentCard TEST key. Production credentials are not accepted during setup.")
        mcp(runtime, "agent-cards", "https://mcp.agentcard.sh/mcp", key="AGENTCARD_API_KEY")
        runtime.set("mcp_servers.agent-cards.tools", {"include": ["whoami", "get_instructions", "get_plan", "list_cards", "check_balance", "list_transactions"]})
        private_write(runtime.home / "agentcard.json", json.dumps({"mode": "TEST", "enabled": True, "spending_enabled": False}) + "\n")
    if service in {"agentphone", "agentmail", "composio", "pandadoc", "super-browser", "scrapecreators", "agentcard"}:
        for platform in ("cli", "slack", "telegram"):
            key = "platform_toolsets." + platform
            tools = runtime.get(key)
            if isinstance(tools, list):
                item = "mcp-" + MCP_NAMES.get(service, service)
                if item not in tools:
                    runtime.set(key, tools + [item])
    install_plugins(runtime)
    runtime.hermes("plugins", "enable", "setup-evidence")
    contract = read_json(runtime.state.directory / "connection-contracts.json")
    evidence_keys = SERVICES[service]["keys"] + SERVICES[service].get("optional_keys", [])
    contract[service] = {"keys": evidence_keys, "fingerprint": connection_fingerprint(runtime, service),
                         "credentials": fingerprint({k: runtime.env().get(k, "") for k in evidence_keys}),
                         "mcp_name": MCP_NAMES.get(service, service), "mcp": fingerprint(runtime.get("mcp_servers." + MCP_NAMES.get(service, service)) or {})}
    private_write(runtime.state.directory / "connection-contracts.json", json.dumps(contract) + "\n")
    write_connection_context(runtime)
    runtime.state.set(service, "configured", check="connection-saved", fingerprint=connection_fingerprint(runtime, service))
    runtime.restart()


def configure_phone(runtime, options):
    from .phone import business_profile, check_local_adapter, funnel
    saved = read_json(runtime.home / "agentphone.json")
    config = {**saved, **{key: options[key] for key in ("agent_id", "number_id", "number", "owners", "public_url", "port") if key in options}}
    for key in ("agent_id", "number_id"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", str(config.get(key, ""))):
            raise SetupError("Select the provider identity and number for this installation.")
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", str(config.get("number", ""))):
        raise SetupError("Select a phone number in international format.")
    owners = config.get("owners", [])
    if not isinstance(owners, list) or not owners or any(not re.fullmatch(r"\+[1-9][0-9]{7,14}", n) for n in owners):
        raise SetupError("Select the owner callers allowed to start a private phone conversation.")
    passphrase = options.get("owner_passphrase")
    if passphrase:
        if len(passphrase) < 20 or "." in passphrase:
            raise SetupError("Use a private phone passphrase of at least 20 characters without a period.")
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(passphrase.strip().casefold().encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        config["owner_access"] = {"salt": salt, "hash": digest}
    if not config.get("owner_access"):
        raise SetupError("Set a private phone passphrase through the trusted setup channel.")
    url = urlsplit(config.get("public_url", ""))
    if config.get("public_url") and (url.scheme != "https" or not (url.hostname or "").endswith(".ts.net") or url.path not in {"", "/"} or url.query or url.fragment or url.username):
        raise SetupError("Configure a dedicated Tailscale Funnel HTTPS origin for the phone adapter.")
    key = runtime.env()["AGENTPHONE_API_KEY"]
    base = "https://api.agentphone.ai/v1/agents/" + config["agent_id"]
    agent = fetch(base, token=key)
    numbers = agent.get("numbers", [])
    if not any(n.get("id") == config["number_id"] and (n.get("number") or n.get("phoneNumber")) == config["number"] for n in numbers):
        raise SetupError("This provider agent does not own the selected number. Attach the approved number first.")
    if agent.get("voiceMode") != "webhook":
        fetch(base, token=key, method="PATCH", body={"voiceMode": "webhook"})
    port = int(config.get("port", 9941))
    if not 9941 <= port <= 9990:
        raise SetupError("Use a dedicated phone port between 9941 and 9990.")
    config.update(bind="0.0.0.0" if runtime.kind == "compose" else "127.0.0.1", port=port, voice_deadline=25)
    business_profile(runtime, options, config)
    runtime.save_env({"AGENTPHONE_ALLOWED_USERS": ",".join(owners + list(config.get("business_callers", {}))),
                      "AGENTPHONE_ALLOW_ALL_USERS": "false", "AGENTPHONE_PORT": str(port)})
    if not runtime.env().get("AGENTPHONE_WEBHOOK_SECRET"):
        runtime.save_env({"AGENTPHONE_WEBHOOK_SECRET": secrets.token_hex(32)})
    private_write(runtime.home / "agentphone.json", json.dumps(config, indent=2) + "\n")
    install_plugins(runtime)
    runtime.hermes("plugins", "enable", "agentphone-channel")
    runtime.set("gateway.platforms.agentphone.enabled", True)
    runtime.set("platform_toolsets.agentphone", ["web"])
    runtime.set("display.platforms.agentphone.streaming", False)
    runtime.set("display.platforms.agentphone.interim_assistant_messages", False)
    runtime.restart()
    check_local_adapter(runtime, config)
    config["public_url"] = funnel(runtime, port, config.get("public_url"))
    target = config["public_url"].rstrip("/") + "/webhooks/agentphone"
    existing = fetch(base + "/webhook", token=key, missing_ok=True)
    # Resuming must not rotate a healthy signing secret.
    if not existing or existing.get("url") != target or not saved.get("webhook_registered") or saved.get("webhook_secret_hash") != hashlib.sha256(runtime.env()["AGENTPHONE_WEBHOOK_SECRET"].encode()).hexdigest():
        if existing and existing.get("url") != target and options.get("replace_webhook_selected") is not True:
            raise SetupError("This provider identity already has a different webhook. Select a separate identity or explicitly replace its route.")
        webhook = fetch(base + "/webhook", token=key, method="POST", body={"url": target, "contextLimit": 0, "timeout": 30})
        if not webhook.get("secret"):
            raise SetupError("Webhook registration did not return a signing secret.")
        runtime.save_env({"AGENTPHONE_WEBHOOK_SECRET": webhook["secret"]})
    config["webhook_registered"] = True
    config["webhook_secret_hash"] = hashlib.sha256(runtime.env()["AGENTPHONE_WEBHOOK_SECRET"].encode()).hexdigest()
    private_write(runtime.home / "agentphone.json", json.dumps(config, indent=2) + "\n")
    aliases = owner_aliases(runtime)
    honcho = read_json(runtime.home / "honcho.json")
    host = honcho.get("hosts", {}).get(memory_host(runtime, honcho), {})
    if host.get("peerName"):
        host.setdefault("userPeerAliases", {}).update({k.split(":", 1)[1]: host["peerName"] for k in aliases})
        private_write(runtime.home / "honcho.json", json.dumps(honcho) + "\n")
    mcp(runtime, "agentphone", "https://mcp.agentphone.ai/mcp", key="AGENTPHONE_API_KEY")
