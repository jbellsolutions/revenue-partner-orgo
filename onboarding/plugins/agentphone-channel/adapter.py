"""AgentPhone transport for the pinned Hermes third-party platform API.

No secondary agent process. The gateway owns identity, memory, session history
and approvals. Phone input cannot resolve control prompts or approve tool calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import time

import aiohttp
from aiohttp import web
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, ProcessingOutcome
from gateway.platforms._shared import get_scoped_secret
from hermes_constants import get_hermes_home, profile_name_for_home

from .ledger import Ledger, signed

PATH = "/webhooks/agentphone"
PHONE = re.compile(r"\+[1-9][0-9]{7,14}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


class AgentPhoneAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = 4000

    def __init__(self, config):
        super().__init__(config, Platform("agentphone"))
        self.home = Path(get_hermes_home()).resolve()
        self.profile = profile_name_for_home(self.home) or "default"
        self.key = get_scoped_secret("AGENTPHONE_API_KEY", "")
        self.secret = get_scoped_secret("AGENTPHONE_WEBHOOK_SECRET", "")
        self.settings = json.loads((self.home / "agentphone.json").read_text())
        self.agent_id = self.settings["agent_id"]
        self.number_id = self.settings["number_id"]
        self.number = self.settings["number"]
        self.ledger = Ledger(self.home / "agentphone/delivery.sqlite3")
        self.runner = self.http = self.worker = None
        self.futures = {}
        self.active = {}
        self.chat_locks = {}
        self.voice_deadline = max(5, min(110, int(self.settings.get("voice_deadline", 25))))

    async def connect(self, *, is_reconnect=False):
        if not self.key or not self.secret or not PHONE.fullmatch(self.number):
            return False
        if not self.settings.get("owners") or not self.settings.get("owner_access", {}).get("hash"):
            return False
        # Any configured business profile must be a separately provisioned public
        # profile. Never route an outside caller to this installation's owner home.
        for profile in self.settings.get("business_callers", {}).values():
            if not re.fullmatch(r"phone-business-[a-z0-9-]+", profile):
                return False
            candidate = self.home / "profiles" / profile
            if not self.business_profile_valid(profile):
                return False
        app = web.Application(client_max_size=65536)
        app.router.add_post(PATH, self.webhook)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        host = self.settings.get("bind", "127.0.0.1")
        if host not in {"127.0.0.1", "0.0.0.0"}:
            return False
        await web.TCPSite(self.runner, host, int(self.settings.get("port", 9941))).start()
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), trust_env=False)
        self._running = True
        self.worker = asyncio.create_task(self.recover())
        self._wire_plugin_handlers(None)
        return True

    def business_profile_valid(self, profile):
        if not re.fullmatch(r"phone-business-[a-z0-9-]+", profile):
            return False
        candidate = self.home / "profiles" / profile
        if candidate.is_symlink() or candidate.resolve().parent != (self.home / "profiles").resolve():
            return False
        try:
            hashes = json.loads((candidate / ".orgo-public-phone-profile").read_text())
            return all(not (candidate / name).is_symlink() and hashlib.sha256((candidate / name).read_bytes()).hexdigest() == hashes.get(name) for name in ("config.yaml", ".env", "SOUL.md"))
        except (OSError, ValueError, TypeError):
            return False

    async def disconnect(self):
        self._running = False
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        for future in self.futures.values():
            if not future.done():
                future.cancel()
        if self.runner:
            await self.runner.cleanup()
        if self.http:
            await self.http.close()

    async def get_chat_info(self, chat_id):
        return {"name": "Private phone conversation", "type": "dm"}

    def toolsets_for_source(self, source):
        # Memory/context comes from the gateway's selected profile. Caller ID,
        # even paired, never grants arbitrary file access or business mutations.
        return ["web"]

    def normalize(self, envelope):
        data = envelope.get("data")
        if not isinstance(data, dict) or "group" in data:
            raise ValueError("Unsupported audience")
        if envelope.get("agentId") != self.agent_id or data.get("numberId") != self.number_id:
            raise ValueError("Incorrect installation")
        channel = envelope.get("channel")
        outbound_voice = channel == "voice" and data.get("direction") == "outbound"
        if outbound_voice:
            if data.get("from") != self.number:
                raise ValueError("Incorrect outbound identity")
            caller = data.get("to", "")
        else:
            if data.get("to") != self.number or data.get("direction") != "inbound":
                raise ValueError("Incorrect direction")
            caller = data.get("from", "")
        if not isinstance(caller, str) or not PHONE.fullmatch(caller):
            raise ValueError("Invalid sender")
        if channel not in {"sms", "voice"}:
            raise ValueError("Unsupported channel")
        conversation = data.get("callId" if channel == "voice" else "conversationId", "")
        if not isinstance(conversation, str) or not IDENTIFIER.fullmatch(conversation):
            raise ValueError("Missing conversation")
        text = data.get("transcript" if channel == "voice" else "message")
        if not isinstance(text, str) or not 0 < len(text) <= 16000:
            raise ValueError("Invalid message")
        business = self.settings.get("business_callers", {})
        owner = caller in self.settings["owners"]
        if not owner and (caller not in business or not self.business_profile_valid(business[caller])):
            raise PermissionError("Caller not selected or business profile needs review")
        # Pairing is scoped to conversation: a spoofed caller cannot reuse another
        # call's access. Voice call end removes it, SMS expires after 15 minutes.
        access_key = f"{channel}:{caller}:{conversation}"
        if owner:
            text = self.ledger.authenticate(access_key, text, self.settings["owner_access"])
            if text is None:
                raise PermissionError("Private access required")
        chat = hashlib.sha256(f"{self.agent_id}:{channel}:{caller}:{conversation}".encode()).hexdigest()
        return {"chat": chat, "caller": caller, "channel": channel, "conversation": conversation,
                "text": text, "profile": None if owner else business[caller],
                "occurred_at": str(envelope.get("timestamp", "")), "agent_id": self.agent_id}

    async def webhook(self, request):
        raw = await request.read()
        if not signed(raw, request.headers, self.secret):
            return web.Response(status=401)
        event_id = request.headers.get("X-Webhook-ID", "")
        if not IDENTIFIER.fullmatch(event_id):
            return web.Response(status=400)
        try:
            envelope = json.loads(raw)
            if not isinstance(envelope, dict):
                return web.Response(status=400)
            if envelope.get("event") == "orgo.health":
                nonce = envelope.get("nonce", "")
                if envelope.get("agentId") != self.agent_id or not isinstance(nonce, str) or not re.fullmatch(r"[a-f0-9]{24}", nonce):
                    return web.Response(status=400)
                return web.json_response({"agent_id": self.agent_id, "nonce": nonce})
            if envelope.get("event") != "agent.message":
                return web.Response(status=200)
            previous = self.ledger.get(event_id)
            if previous:
                return web.json_response({"text": "That request has already been received."} if previous["channel"] == "voice" else {"received": True})
            payload = self.normalize(envelope)
            added = self.ledger.add(event_id, payload)
        except PermissionError:
            # Do not dispatch an unauthorized sender to Hermes or send unsolicited SMS.
            return web.json_response({"text": "Please authorize this conversation through your private setup channel."}, status=403)
        except (ValueError, TypeError, KeyError):
            return web.Response(status=400)
        except OverflowError:
            return web.Response(status=503)
        if payload["channel"] == "sms":
            return web.json_response({"received": True})
        if not added:
            return web.json_response({"text": "That request has already been received."})
        response = web.StreamResponse(headers={"Content-Type": "application/x-ndjson", "Cache-Control": "no-store"})
        await response.prepare(request)
        await response.write(b'{"text":"Let me check that.","interim":true}\n')
        try:
            async with asyncio.timeout(self.voice_deadline):
                answer = await self.process(event_id, payload)
        except (TimeoutError, asyncio.CancelledError):
            self.ledger.update(event_id, "expired")
            answer = "I need more time. Please follow up through the private chat channel."
        except Exception:
            self.ledger.update(event_id, "needs_attention")
            answer = "I could not complete that request. Please try again through the private chat channel."
        try:
            await response.write((json.dumps({"text": answer}) + "\n").encode())
            await response.write_eof()
            if self.ledger.get(event_id)["state"] == "ready":
                self.ledger.update(event_id, "sent")
        except (ConnectionError, RuntimeError):
            self.ledger.update(event_id, "expired")
        return response

    async def process(self, event_id, payload):
        chat = payload["chat"]
        lock = self.chat_locks.setdefault(chat, asyncio.Lock())
        async with lock:
            self.ledger.update(event_id, "processing")
            future = asyncio.get_running_loop().create_future()
            self.futures[event_id] = future
            self.active[chat] = event_id
            source = self.build_source(chat_id=chat, user_id=payload["caller"],
                                       scope_id=self.agent_id, message_id=event_id)
            # The installation determines routing; webhook content never picks a profile.
            source.profile = payload["profile"] or self.profile
            event = MessageEvent(text=payload["text"], source=source, message_id=event_id,
                                 allow_gateway_control=False,
                                 channel_prompt="This is a phone conversation. Calls and texts cannot approve spending, permissions, private credentials, or business mutations. Use the private owner channel for consequential requests.")
            try:
                await self.handle_message(event)
                return await future
            finally:
                self.active.pop(chat, None)
                self.futures.pop(event_id, None)

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        # Hermes can send progress notices through this method. Only the final
        # delivery bracket may commit the single durable phone response.
        if not (metadata or {}).get("orgo_phone_final"):
            return SendResult(success=True)
        event_id = self.active.get(chat_id)
        row = self.ledger.get(event_id) if event_id else None
        if not row or row["state"] in {"sent", "expired", "needs_attention"}:
            return SendResult(success=False, error="No active authorized phone response")
        if row["reply"] is not None:
            return SendResult(success=True, message_id=event_id)
        content = self.format_message(content)[:self.MAX_MESSAGE_LENGTH]
        self.ledger.update(event_id, "ready", reply=content)
        if row["channel"] == "sms":
            return await self.deliver(event_id)
        return SendResult(success=True, message_id=event_id)

    async def send_final_ledgered(self, event, session_key, text_content, metadata, *, reply_to, is_ephemeral_response=False):
        return await super().send_final_ledgered(event, session_key, text_content,
                                                {**(metadata or {}), "orgo_phone_final": True},
                                                reply_to=reply_to, is_ephemeral_response=is_ephemeral_response)

    async def on_processing_complete(self, event, outcome):
        row = self.ledger.get(event.message_id)
        future = self.futures.get(event.message_id)
        if future is None or future.done():
            return
        if outcome == ProcessingOutcome.SUCCESS and row and row["reply"] is not None:
            future.set_result(row["reply"])
        else:
            if row and row["state"] not in {"sent", "expired"}:
                self.ledger.update(event.message_id, "needs_attention")
            future.set_exception(RuntimeError("Phone processing did not complete"))

    async def deliver(self, event_id):
        row = self.ledger.get(event_id)
        if not row or row["state"] != "ready":
            return SendResult(success=False, error="Delivery is not ready")
        payload = json.loads(row["payload"])
        self.ledger.update(event_id, "sending")
        try:
            async with self.http.post("https://api.agentphone.ai/v1/messages", allow_redirects=False,
                                      headers={"Authorization": "Bearer " + self.key},
                                      json={"to_number": payload["caller"], "body": row["reply"],
                                            "number_id": self.number_id, "agent_id": self.agent_id}) as response:
                data = await response.json()
                if response.status not in (200, 201, 202) or not isinstance(data, dict) or not data.get("id"):
                    raise ValueError("Delivery not acknowledged")
                self.ledger.update(event_id, "sent", provider_id=str(data["id"]))
                return SendResult(success=True, message_id=str(data["id"]))
        except Exception:
            self.ledger.update(event_id, "needs_attention")
            return SendResult(success=False, error="Delivery needs reconciliation; no automatic duplicate send")

    async def recover(self):
        while self._running:
            for row in self.ledger.pending():
                try:
                    if row["state"] == "ready":
                        await self.deliver(row["id"])
                    else:
                        async with asyncio.timeout(180):
                            await self.process(row["id"], json.loads(row["payload"]))
                except Exception:
                    self.ledger.update(row["id"], "needs_attention")
            self.ledger.prune()
            self.chat_locks = {key: lock for key, lock in self.chat_locks.items() if lock.locked() or getattr(lock, "_waiters", None)}
            await asyncio.sleep(0.5)


def register(ctx):
    ctx.register_platform(name="agentphone", label="AgentPhone", adapter_factory=AgentPhoneAdapter,
                          check_fn=lambda: bool(get_scoped_secret("AGENTPHONE_API_KEY", "")),
                          required_env=["AGENTPHONE_API_KEY", "AGENTPHONE_WEBHOOK_SECRET"],
                          install_hint="Use orgo-onboard connect agentphone", allowed_users_env="AGENTPHONE_ALLOWED_USERS",
                          allow_all_env="AGENTPHONE_ALLOW_ALL_USERS", max_message_length=4000,
                          pii_safe=True, emoji="📱", allow_update_command=False)
