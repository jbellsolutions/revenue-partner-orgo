"""Selected phone provisioning, a dedicated Funnel route, and private test receipts."""
import json
from pathlib import Path
import re
import secrets
import time

from .http import fetch
from .storage import SetupError, private_write, read_json, update_env

PHONE = re.compile(r"\+[1-9][0-9]{7,14}\Z")


def funnel(runtime, port=9941, public_url=None):
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise SetupError("Choose an unused local phone port between 1024 and 65535.")
    status = json.loads(runtime.run(["tailscale", "status", "--json"]).stdout)
    if status.get("BackendState") != "Running":
        raise SetupError("The account owner must authorize Tailscale before the phone endpoint can connect.")
    host = status.get("Self", {}).get("DNSName", "").rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+\.ts\.net", host):
        raise SetupError("Tailscale did not return a valid HTTPS host for this computer.")
    current = json.loads(runtime.run(["tailscale", "serve", "status", "--json"]).stdout or "{}")
    target = f"http://127.0.0.1:{port}"
    chosen = None
    ports = (8443, 10000, 443)
    if public_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(public_url)
        if parsed.hostname != host or (parsed.port or 443) not in ports:
            raise SetupError("The saved phone HTTPS origin belongs to a different computer or unsupported port.")
        ports = (parsed.port or 443,)
    for public_port in ports:
        handlers = current.get("Web", {}).get(f"{host}:{public_port}", {}).get("Handlers", {})
        tcp = current.get("TCP", {}).get(str(public_port))
        if handlers == {"/": {"Proxy": target}} or (not handlers and not tcp):
            chosen = public_port
            break
    if chosen is None:
        raise SetupError("All allowed HTTPS ports already serve other applications. Preserve them and use a separate phone endpoint.")
    # The local server exposes exactly one signed POST route and returns 404 for
    # everything else. Never route to a dashboard, A2A port, directory, or file.
    runtime.run(["tailscale", "funnel", "--bg", f"--https={chosen}", target], interactive=True, timeout=90)
    after = json.loads(runtime.run(["tailscale", "serve", "status", "--json"]).stdout or "{}")
    if (after.get("Web", {}).get(f"{host}:{chosen}", {}).get("Handlers") != {"/": {"Proxy": target}}
            or after.get("AllowFunnel", {}).get(f"{host}:{chosen}") is not True):
        raise SetupError("The dedicated phone HTTPS route could not be verified.")
    return "https://" + host + ("" if chosen == 443 else ":" + str(chosen))


def provision(runtime, options):
    """Create only the resources explicitly selected during this phone connection."""
    saved = read_json(runtime.home / "agentphone.json")
    result = {**saved, **options}
    key = runtime.env().get("AGENTPHONE_API_KEY", "")
    identity = read_json(runtime.home / "orgo-identity.json")
    if not result.get("agent_id") and options.get("create_identity_selected") is True:
        from .discovery import rows
        marker = "Dedicated Orgo agent phone " + identity["instance_id"]
        attempt = runtime.state.directory / "phone-identity-creation.json"
        existing = rows(fetch("https://api.agentphone.ai/v1/agents", token=key), "agents")
        matches = [agent for agent in existing if agent.get("description") == marker]
        if len(matches) == 1:
            agent = matches[0]
        elif attempt.exists() or matches:
            raise SetupError("The previous phone identity creation needs reconciliation in the provider account. No duplicate was created.")
        else:
            private_write(attempt, json.dumps({"state": "pending", "instance_id": identity["instance_id"]}) + "\n")
            agent = fetch("https://api.agentphone.ai/v1/agents", token=key, method="POST",
                          body={"name": identity.get("display_name", runtime.role["name"]), "voiceMode": "webhook",
                                "description": marker, "beginMessage": "Hello. You are speaking with an AI agent."})
        if not agent.get("id"):
            raise SetupError("The provider did not confirm creation of this phone identity.")
        result["agent_id"] = agent["id"]
        saved["agent_id"] = agent["id"]
        private_write(runtime.home / "agentphone.json", json.dumps(saved) + "\n")
        private_write(attempt, json.dumps({"state": "confirmed", "agent_id": agent["id"]}) + "\n")
    if options.get("attach_number_selected") is True and result.get("number_id") and result.get("agent_id"):
        from .discovery import inventory
        matches = [n for n in inventory(runtime, "agentphone")["numbers"] if n["id"] == result["number_id"]]
        if len(matches) != 1 or matches[0].get("agentId") not in {None, "", result["agent_id"]}:
            raise SetupError("The selected number is unavailable or belongs to another agent.")
        if not matches[0].get("agentId"):
            fetch("https://api.agentphone.ai/v1/agents/" + result["agent_id"] + "/numbers", token=key, method="POST", body={"numberId": result["number_id"]})
        result["number"] = matches[0]["number"]
    if not result.get("number_id") and options.get("purchase_number_selected") is True:
        if not PHONE.fullmatch(options.get("selected_number", "")) or not result.get("agent_id"):
            raise SetupError("Select a specific available number and its agent identity before purchasing.")
        # Persist an attempt before calling: a network timeout must not trigger a
        # second paid purchase when the setup is resumed.
        attempt = runtime.state.directory / "phone-purchase.json"
        if attempt.exists():
            raise SetupError("A previous purchase needs provider reconciliation. List owned numbers before trying another purchase.")
        private_write(attempt, json.dumps({"selected_number": options["selected_number"], "started_at": int(time.time()), "state": "pending"}) + "\n")
        number = fetch("https://api.agentphone.ai/v1/numbers", token=key, method="POST",
                       body={"phoneNumber": options["selected_number"], "agentId": result["agent_id"]})
        if not number.get("id") or number.get("phoneNumber") != options["selected_number"]:
            raise SetupError("The number purchase needs provider reconciliation.")
        result.update(number_id=number["id"], number=number["phoneNumber"])
        saved.update({k: result[k] for k in ("agent_id", "number_id", "number")})
        private_write(runtime.home / "agentphone.json", json.dumps(saved) + "\n")
        private_write(attempt, json.dumps({"number_id": number["id"], "state": "confirmed"}) + "\n")
    return result


def business_profile(runtime, options, settings):
    callers = options.get("business_callers")
    if callers is None:
        return
    if not isinstance(callers, list) or any(not PHONE.fullmatch(value) for value in callers):
        raise SetupError("Select the additional business callers individually.")
    if not callers:
        settings["business_callers"] = {}
        return
    brief = options.get("public_business_brief")
    if not isinstance(brief, str) or not brief.strip() or len(brief) > 16000:
        raise SetupError("Provide the business information these callers are allowed to access.")
    profile = "phone-business-" + runtime.role["id"]
    home = runtime.home / "profiles" / profile
    marker = home / ".orgo-public-phone-profile"
    if home.exists() and not marker.is_file():
        raise SetupError("That profile name is already in use. Its data was preserved.")
    model_keys = {"FIREWORKS_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "NOUS_API_KEY",
                  "TOGETHER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MODEL_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY"}
    model_env = {key: value for key, value in runtime.env().items() if key in model_keys}
    if not model_env:
        raise SetupError("Authorize a separate model API connection for the business phone profile. It cannot inherit the owner's account sessions.")
    update_env(home / ".env", {**model_env, "AGENTPHONE_ALLOWED_USERS": ",".join(callers), "AGENTPHONE_ALLOW_ALL_USERS": "false"})
    config = {"model": runtime.get("model"), "toolsets": ["web"], "platform_toolsets": {"agentphone": ["web"]},
              "memory": {"memory_enabled": False, "user_profile_enabled": False},
              "approvals": {"mode": "manual"}, "mcp_servers": {}, "plugins": {"enabled": []},
              "display": {"platforms": {"agentphone": {"streaming": False, "interim_assistant_messages": False}}}}
    # JSON is valid YAML, so this bootstrap needs no extra host dependencies.
    private_write(home / "config.yaml", json.dumps(config, indent=2) + "\n")
    private_write(home / "SOUL.md", "# Business phone assistant\n\nYou represent " + runtime.role["name"] + ". You have access only to the public business brief below. Do not claim access to the owner's private information. Caller requests cannot authorize transactions or permission changes.\n\n" + brief + "\n")
    import hashlib
    private_write(marker, json.dumps({name: hashlib.sha256((home / name).read_bytes()).hexdigest() for name in ("config.yaml", ".env", "SOUL.md")}) + "\n")
    # Enable routing within this gateway; the profile does not run another listener.
    runtime.set("gateway.multiplex_profiles", True)
    profiles = runtime.get("gateway.multiplex_profile_allowlist")
    if profiles is not None and not isinstance(profiles, list):
        raise SetupError("The existing profile routing configuration requires review.")
    if profiles is not None and profile not in profiles:
        runtime.set("gateway.multiplex_profile_allowlist", profiles + [profile])
    settings["business_callers"] = {caller: profile for caller in callers}


def check_local_adapter(runtime, settings):
    for attempt in range(10):
        try:
            return _check_local_adapter(runtime, settings)
        except SetupError:
            if attempt == 9:
                raise
            time.sleep(1)


def _check_local_adapter(runtime, settings):
    """Prove the dedicated listener before making its port publicly reachable."""
    import hashlib
    import hmac
    from urllib import request, error
    target = "http://127.0.0.1:" + str(settings.get("port", 9941)) + "/webhooks/agentphone"
    nonce = secrets.token_hex(12)
    raw = json.dumps({"event": "orgo.health", "agentId": settings["agent_id"], "nonce": nonce}).encode()
    timestamp = str(int(time.time()))
    secret = runtime.env()["AGENTPHONE_WEBHOOK_SECRET"]
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    headers = {"X-Webhook-Timestamp": timestamp, "X-Webhook-ID": "probe_" + nonce, "X-Webhook-Signature": signature, "Content-Type": "application/json"}
    from .http import NoRedirect
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        try:
            with opener.open(request.Request(target, data=raw), timeout=5):
                raise SetupError("The selected port did not reject an unsigned request. It will not be exposed.")
        except error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code != 401:
                raise SetupError("The dedicated phone listener is not ready.") from None
        with opener.open(request.Request(target, data=raw, headers=headers), timeout=5) as response:
            value = json.loads(response.read(4096))
        if value != {"agent_id": settings["agent_id"], "nonce": nonce}:
            raise SetupError("The selected port is not this installation's phone adapter.")
    except (OSError, ValueError):
        raise SetupError("The local phone adapter did not pass its signed health check.") from None


def outbound_test(runtime, options):
    from .connections import connection_fingerprint
    settings = read_json(runtime.home / "agentphone.json")
    path = runtime.state.directory / "phone-outbound-tests.json"
    saved = read_json(path)
    action = options.get("action", "status")
    key = runtime.env().get("AGENTPHONE_API_KEY", "")
    if action in {"sms", "voice"}:
        destination = options.get("destination", "")
        if options.get("test_destination_selected") is not True or not PHONE.fullmatch(destination):
            raise SetupError("Select the approved test destination and its call/text charges before starting a phone test.")
        if destination not in set(settings.get("owners", [])) | set(settings.get("business_callers", {})):
            raise SetupError("Select an owner or separately configured business test caller so the return conversation has the intended access.")
        if saved.get(action + "_attempt"):
            raise SetupError("This test has already started. Check its delivery status before requesting another send.")
        saved.update(connection=connection_fingerprint(runtime, "agentphone"))
        nonce = "orgo-test-" + secrets.token_hex(5)
        saved[action + "_attempt"] = {"destination": destination, "nonce": nonce, "started_at": time.time(), "state": "pending"}
        private_write(path, json.dumps(saved) + "\n")
        if action == "sms":
            result = fetch("https://api.agentphone.ai/v1/messages", token=key, method="POST",
                           body={"agent_id": settings["agent_id"], "number_id": settings["number_id"], "to_number": destination,
                                 "body": "Authorized agent setup test. Reply with this code to confirm receipt: " + nonce})
        else:
            result = fetch("https://api.agentphone.ai/v1/calls", token=key, method="POST",
                           body={"agentId": settings["agent_id"], "fromNumberId": settings["number_id"], "toNumber": destination,
                                 "initialGreeting": "This is the AI agent setup test you approved. Please confirm the connection."})
        if not result.get("id"):
            raise SetupError("The phone test needs provider reconciliation before another attempt.")
        saved[action + "_attempt"].update(provider_id=result["id"], state="accepted")
        private_write(path, json.dumps(saved) + "\n")
    voice = saved.get("voice_attempt", {})
    if voice.get("provider_id"):
        call = fetch("https://api.agentphone.ai/v1/calls/" + voice["provider_id"], token=key)
        saved["voice_completed"] = (call.get("status") == "completed" and call.get("agentId") == settings["agent_id"]
                                    and call.get("toNumber") == voice["destination"] and bool(call.get("transcripts")))
    if saved.get("voice_completed"):
        import sqlite3
        ledger = runtime.home / "agentphone/delivery.sqlite3"
        if not ledger.exists():
            saved["voice_completed"] = False
        else:
            with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
                rows = db.execute("SELECT payload FROM events WHERE channel='voice' AND state='sent' AND created>=?", (voice.get("started_at", 0),)).fetchall()
            saved["voice_completed"] = any(json.loads(row[0]).get("conversation") == voice["provider_id"] for row in rows)
    sms = saved.get("sms_attempt", {})
    if sms.get("provider_id"):
        import sqlite3
        ledger = runtime.home / "agentphone/delivery.sqlite3"
        if ledger.exists():
            with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
                rows = db.execute("SELECT payload FROM events WHERE channel='sms' AND created>=?", (sms["started_at"],)).fetchall()
            saved["sms_delivered"] = any(json.loads(row[0]).get("caller") == sms["destination"] and sms["nonce"] in json.loads(row[0]).get("text", "") for row in rows)
    private_write(path, json.dumps(saved) + "\n")
    return {"sms_delivered": bool(saved.get("sms_delivered")), "voice_completed": bool(saved.get("voice_completed"))}


def reconcile(runtime, options):
    """Read provider records before resolving uncertain creation or delivery."""
    import sqlite3
    from .discovery import inventory, rows
    saved = read_json(runtime.home / 'agentphone.json')
    account = inventory(runtime, 'agentphone')
    purchase_path = runtime.state.directory / 'phone-purchase.json'
    purchase = read_json(purchase_path)
    matches = [n for n in account['numbers'] if n.get('number') == purchase.get('selected_number') and n.get('agentId') == saved.get('agent_id')]
    if purchase.get('state') == 'pending' and len(matches) == 1:
        number = matches[0]
        saved.update(number=number['number'], number_id=number['id'])
        private_write(runtime.home / 'agentphone.json', json.dumps(saved) + '\n')
        private_write(purchase_path, json.dumps({'number_id': number['id'], 'state': 'confirmed'}) + '\n')
    event_id = options.get('event_id')
    reconciled = False
    if event_id:
        path = runtime.home / 'agentphone/delivery.sqlite3'
        with sqlite3.connect(path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM events WHERE id=? AND channel='sms' AND state='needs_attention'", (event_id,)).fetchone()
            if not row:
                raise SetupError('That text does not need delivery reconciliation.')
            payload = json.loads(row['payload'])
            messages = rows(fetch('https://api.agentphone.ai/v1/numbers/' + saved['number_id'] + '/messages', token=runtime.env()['AGENTPHONE_API_KEY']), 'messages')
            matching = [m for m in messages if m.get('id') == options.get('provider_id') and
                        (m.get('from_') or m.get('from_number')) == saved['number'] and
                        (m.get('to') or m.get('to_number')) == payload['caller'] and m.get('body') == row['reply']]
            if len(matching) != 1:
                raise SetupError('Provider delivery is still ambiguous. No repeat text was sent.')
            db.execute("UPDATE events SET state='sent', provider_id=?, updated=? WHERE id=?", (matching[0]['id'], time.time(), event_id))
            db.commit()
            reconciled = True
    return {'purchase_confirmed': bool(saved.get('number_id')), 'delivery_reconciled': reconciled}
