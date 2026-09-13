"""Checks produce evidence, never a success label based on credentials alone."""
import hashlib
import json
import secrets
import sqlite3
import time
from urllib.parse import quote

from .connections import connection_fingerprint
from .http import fetch
from .identity import verify_local
from .storage import SetupError, private_write, read_json


def model(runtime):
    nonce = "orgo-check-" + secrets.token_hex(8)
    result = runtime.hermes("chat", "-Q", "--query-file", "-", "--toolsets", "clarify", "--max-turns", "1",
                            input_text="Reply with exactly this harmless setup code: " + nonce, timeout=120)
    if nonce not in result.stdout:
        raise SetupError("The model did not return the setup test response.")
    runtime.state.set("model", "verified", check="local-model-response")


def channel(runtime):
    config = read_json(runtime.home / "orgo-channel.json")
    platform = config.get("platform")
    env = runtime.env()
    if platform == "slack":
        auth = fetch("https://slack.com/api/auth.test", token=env.get("SLACK_BOT_TOKEN", ""))
        if not auth.get("ok"):
            raise SetupError("Slack did not accept this agent's token.")
        who = fetch("https://slack.com/api/users.info?user=" + quote(auth["user_id"], safe=""), token=env["SLACK_BOT_TOKEN"])
        bot = who.get("user", {}).get("profile", {})
        expected = read_json(runtime.home / "orgo-identity.json").get("display_name")
        if expected not in (bot.get("display_name"), bot.get("real_name")):
            raise SetupError("The connected Slack bot name differs from the saved agent name.")
        # Prove two owner turns and two actual platform replies in the same thread.
        room = config.get("test_channel")
        thread = config.get("test_thread")
        if (not room or not thread) and (runtime.home / "state.db").exists():
            try:
                with sqlite3.connect((runtime.home / "state.db").as_uri() + "?mode=ro", uri=True) as db:
                    rows = db.execute("SELECT chat_id, thread_id FROM delivery_obligations WHERE platform='slack' AND state='delivered' AND thread_id IS NOT NULL ORDER BY created_at DESC LIMIT 1").fetchall()
                if rows:
                    room, thread = rows[0]
            except sqlite3.Error:
                pass
        if not room or not thread:
            raise SetupError("Complete an owner conversation and thread follow-up, then save its private channel and thread identifiers.")
        data = fetch("https://slack.com/api/conversations.replies?channel=" + quote(room, safe="") + "&ts=" + quote(thread, safe=""), token=env["SLACK_BOT_TOKEN"])
        messages = data.get("messages", []) if data.get("ok") else []
        owners = set(env.get("SLACK_ALLOWED_USERS", "").split(","))
        turns = [m for m in messages if m.get("user") in owners and m.get("text")]
        replies = [m for m in messages if m.get("user") == auth["user_id"] and m.get("text")]
        if len(turns) < 2 or len(replies) < 2 or float(replies[-1].get("ts", 0)) <= float(turns[-1].get("ts", 0)):
            raise SetupError("Slack conversation and thread follow-up delivery are not yet proven.")
        manifest_key = env.get("SLACK_CONFIGURATION_TOKEN")
        if not manifest_key:
            raise SetupError("The Slack bot and conversation passed. Authorize Slack app-manifest readback to verify its app name.")
        manifest = fetch("https://slack.com/api/apps.manifest.export", token=manifest_key, method="POST", body={"app_id": auth.get("app_id") or config.get("app_id")})
        if manifest.get("manifest", {}).get("display_information", {}).get("name") != expected:
            raise SetupError("The live Slack app name does not match the saved agent name.")
    elif platform == "telegram":
        # getMe proves auth, but cannot prove a received reply. Read Hermes's
        # delivery ledger in the Telegram adapter instead of consuming getUpdates.
        data = fetch("https://api.telegram.org/bot" + env.get("TELEGRAM_BOT_TOKEN", "") + "/getMe")
        if not data.get("ok"):
            raise SetupError("Telegram rejected this agent's token.")
        db_path = runtime.home / "state.db"
        if not db_path.exists():
            raise SetupError("Telegram identity passed; an authorized inbound message and delivered reply are still needed.")
        with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as db:
            rows = db.execute("SELECT d.session_key FROM delivery_obligations d JOIN sessions s ON s.session_key=d.session_key WHERE d.platform='telegram' AND d.state='delivered' AND d.created_at>=? AND s.user_id IN (" + ",".join("?" for _ in env.get("TELEGRAM_ALLOWED_USERS", "").split(",")) + ")", [config.get("connected_at", 0), *env.get("TELEGRAM_ALLOWED_USERS", "").split(",")]).fetchall()
        if not rows:
            raise SetupError("Telegram identity passed; the gateway has not recorded an authorized delivered reply.")
    else:
        raise SetupError("Connect Slack or Telegram first.")
    runtime.state.set("channel", "verified", check=platform + "-conversation")


def optional(runtime, service):
    env = runtime.env()
    expected = connection_fingerprint(runtime, service)
    started = runtime.state.get(service).get("configured_at", 0)
    if service == "latitude":
        receipt = read_json(runtime.state.directory / "latitude-receipt.json")
        connection = hashlib.sha256((env.get("LATITUDE_API_KEY", "") + ":" + env.get("LATITUDE_PROJECT_SLUG", "")).encode()).hexdigest()
        if receipt.get("connection") != connection or receipt.get("mode") != env.get("LATITUDE_CAPTURE_MODE", "metadata") or receipt.get("accepted_at", 0) < started:
            raise SetupError("Run a harmless agent conversation, then verify the accepted Latitude trace. No matching live trace is recorded yet.")
        check = "accepted-hermes-trace"
    elif service == "honcho":
        if runtime.get("memory.provider") != "honcho":
            raise SetupError("Honcho is not the selected memory provider.")
        runtime.hermes("honcho", "status", timeout=30)
        proof_path = runtime.state.directory / "honcho-probe.json"
        probe = read_json(proof_path)
        if probe.get("connection") != expected:
            probe = {"connection": expected, "label": "test-" + secrets.token_hex(6), "fact": secrets.token_hex(12)}
            private_write(proof_path, json.dumps(probe) + "\n")
        label, fact = probe["label"], probe["fact"]
        # Separate CLI invocations create separate sessions. Neither gets file or
        # shell tools; the second prompt never contains the expected answer.
        runtime.hermes("chat", "-Q", "--query-file", "-", "--toolsets", "clarify", "--max-turns", "1",
                       input_text=f"Remember this harmless setup fact: the verification value for {label} is {fact}.", timeout=120)
        recalled = runtime.hermes("chat", "-Q", "--query-file", "-", "--toolsets", "clarify", "--max-turns", "1",
                                 input_text=f"What is the verification value for {label}? Recall it from memory; do not guess.", timeout=120)
        if fact not in recalled.stdout:
            raise SetupError("Honcho recall across sessions did not pass yet. Retry after memory processing completes.")
        check = "honcho-cross-session-recall"
    elif service == "agentphone":
        settings = read_json(runtime.home / "agentphone.json")
        base = "https://api.agentphone.ai/v1/agents/" + settings.get("agent_id", "")
        agent = fetch(base, token=env.get("AGENTPHONE_API_KEY", ""))
        hook = fetch(base + "/webhook", token=env.get("AGENTPHONE_API_KEY", ""))
        if agent.get("voiceMode") != "webhook" or not hook or hook.get("url") != settings.get("public_url", "").rstrip("/") + "/webhooks/agentphone":
            raise SetupError("The provider phone route does not match this running agent.")
        path = runtime.home / "agentphone/delivery.sqlite3"
        if not path.is_file():
            raise SetupError("No inbound phone conversations have been delivered yet.")
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            channels = {row[0] for row in db.execute("SELECT DISTINCT channel FROM events WHERE state='sent' AND created>=?", (started,))}
            unresolved = db.execute("SELECT COUNT(*) FROM events WHERE state='needs_attention'").fetchone()[0]
        if channels != {"sms", "voice"} or unresolved:
            raise SetupError("Phone verification needs successful SMS and voice conversations with no unresolved deliveries.")
        receipt = read_json(runtime.state.directory / "phone-outbound-tests.json")
        if receipt.get("connection") != expected or not receipt.get("sms_delivered") or not receipt.get("voice_completed"):
            raise SetupError("Inbound phone conversations passed; approved outbound text and call delivery still need verification.")
        check = "phone-inbound-outbound-sms-voice"
    elif service == "a2a":
        from .collaboration import verify as verify_peer
        verify_peer(runtime)
        check = "private-peer-roundtrip-and-unknown-rejected"
    elif service == "onepassword":
        vault = read_json(runtime.home / "onepassword.json").get("vault_id")
        if not vault:
            raise SetupError("Select a dedicated vault first.")
        result = runtime.command("op", "vault", "get", vault, "--format=json", extra_env={"OP_SERVICE_ACCOUNT_TOKEN": env.get("OP_SERVICE_ACCOUNT_TOKEN", "")})
        if not json.loads(result.stdout).get("id"):
            raise SetupError("The selected vault could not be read.")
        check = "dedicated-vault-read"
    else:
        receipt = read_json(runtime.state.directory / (service + "-capability.json"))
        if receipt.get("verified_at", 0) < started or time.time() - receipt.get("verified_at", 0) > 86400 or receipt.get("connection") != expected or not receipt.get("tool"):
            raise SetupError("The account may be connected; the documented capability check has not completed yet.")
        check = "live-capability-read"
    runtime.state.set(service, "verified", check=check, fingerprint=expected)


def verify(runtime, step):
    try:
        if step == "identity":
            verify_local(runtime)
        elif step == "runtime":
            if not runtime.health() or not runtime.pinned():
                raise SetupError("The agent gateway is not healthy at the reviewed Hermes release.")
            runtime.state.set(step, "verified", check="pinned-gateway-health")
        elif step == "model":
            model(runtime)
        elif step == "channel":
            channel(runtime)
        else:
            optional(runtime, step)
    except SetupError:
        # Preserve connection fingerprint and original configured_at so retrying a
        # failed verification does not invalidate evidence gathered in between.
        runtime.state.mark_attention(step)
        raise
