"""Run with HERMES_SOURCE pointing at the pinned checkout for real adapter tests."""
import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/agentphone-channel"
spec = importlib.util.spec_from_file_location("orgo_phone_test", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from orgo_phone_test.ledger import Ledger, signed, password_hash


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "phone/ledger.db"
        self.ledger = Ledger(self.path)
        self.addCleanup(self.ledger.db.close)

    def test_signature_timestamp_and_tampering(self):
        raw, secret = b'{"a":1}', "private-signing-key"
        headers = {"X-Webhook-Timestamp": "1000", "X-Webhook-Signature": "sha256=" + hmac.new(secret.encode(), b"1000." + raw, hashlib.sha256).hexdigest()}
        self.assertTrue(signed(raw, headers, secret, now=1100))
        self.assertFalse(signed(raw, headers, secret, now=1301))
        self.assertFalse(signed(raw + b" ", headers, secret, now=1000))
        self.assertFalse(signed(raw, {**headers, "X-Webhook-Timestamp": "nan"}, secret, now=1000))

    def test_dedup_and_restart_recovery(self):
        event = {"chat": "chat-a", "channel": "sms", "text": "test"}
        self.assertTrue(self.ledger.add("event-a", event))
        self.assertFalse(self.ledger.add("event-a", event))
        self.assertFalse(self.ledger.add("event-retry", event))
        self.ledger.update("event-a", "processing")
        other = Ledger(self.path)
        self.addCleanup(other.db.close)
        self.assertEqual(other.pending()[0]["state"], "pending")
        other.update("event-a", "sending", reply="reply")
        restarted = Ledger(self.path)
        self.addCleanup(restarted.db.close)
        self.assertEqual(restarted.get("event-a")["state"], "needs_attention")
        self.assertEqual(restarted.pending(), [])

    def test_private_pairing_not_caller_identity(self):
        phrase = "four private words for owner access"
        salt = "01" * 16
        config = {"salt": salt, "hash": password_hash(phrase, salt)}
        self.assertIsNone(self.ledger.authenticate("caller-1", "show private context", config, now=1000))
        self.assertEqual(self.ledger.authenticate("caller-1", "Access " + phrase + ". hello", config, now=1001), "hello")
        self.assertEqual(self.ledger.authenticate("caller-1", "follow up", config, now=1002), "follow up")
        self.assertIsNone(self.ledger.authenticate("caller-2", "show private context", config, now=1002))
        self.assertIsNone(self.ledger.authenticate("caller-1", "follow up", config, now=2000))
        self.assertNotIn(phrase.encode(), self.path.read_bytes())


@unittest.skipUnless(os.environ.get("HERMES_SOURCE"), "Pinned Hermes checkout required for adapter integration tests")
class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"HERMES_HOME": str(self.home), "AGENTPHONE_API_KEY": "key-a", "AGENTPHONE_WEBHOOK_SECRET": "hook-a"})
        self.env.start(); self.addCleanup(self.env.stop)
        sys.path.insert(0, os.environ["HERMES_SOURCE"])
        from orgo_phone_test.adapter import AgentPhoneAdapter, register
        from gateway.platform_registry import platform_registry, PlatformEntry
        class Context:
            def register_platform(self, **kwargs):
                platform_registry.register(PlatformEntry(**kwargs, source="plugin"))
        register(Context())
        from gateway.config import PlatformConfig
        from aiohttp.test_utils import TestClient, TestServer
        from aiohttp import web
        self.phrase = "four private words for owner access"
        salt = "02" * 16
        self.settings = {"agent_id": "agt_a", "number_id": "num_a", "number": "+15550000001", "owners": ["+15550000002"], "owner_access": {"salt": salt, "hash": password_hash(self.phrase, salt)}, "port": 0}
        (self.home / "agentphone.json").write_text(json.dumps(self.settings))
        self.adapter = AgentPhoneAdapter(PlatformConfig(enabled=True))
        self.addCleanup(self.adapter.ledger.db.close)
        self.events = []
        async def handle(event):
            self.events.append(event)
            return "A real Hermes adapter response"
        self.adapter.set_message_handler(handle)
        app = web.Application(client_max_size=65536)
        app.router.add_post("/webhooks/agentphone", self.adapter.webhook)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    def envelope(self, channel="voice", text=None):
        return {"event": "agent.message", "channel": channel, "timestamp": "2026-09-13T12:00:00Z", "agentId": "agt_a",
                "data": {"numberId": "num_a", "from": "+15550000002", "to": "+15550000001", "direction": "inbound",
                         "callId": "call_a", "conversationId": "conv_a",
                         "transcript" if channel == "voice" else "message": text or "Access " + self.phrase + ". hello"}}

    async def post(self, body, event_id="evt_a", secret="hook-a"):
        raw = json.dumps(body).encode()
        timestamp = str(int(time.time()))
        signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return await self.client.post("/webhooks/agentphone", data=raw, headers={"X-Webhook-ID": event_id, "X-Webhook-Timestamp": timestamp, "X-Webhook-Signature": signature})

    async def test_voice_streams_ack_then_final_through_real_base_adapter(self):
        response = await self.post(self.envelope())
        self.assertEqual(response.status, 200)
        chunks = [json.loads(line) for line in (await response.text()).splitlines()]
        self.assertTrue(chunks[0]["interim"])
        self.assertEqual(chunks[1]["text"], "A real Hermes adapter response")
        self.assertEqual(self.events[0].text, "hello")
        self.assertFalse(self.events[0].allow_gateway_control)
        self.assertEqual(self.events[0].source.scope_id, "agt_a")
        self.assertEqual(self.adapter.ledger.get("evt_a")["state"], "sent")
        again = await self.post(self.envelope())
        self.assertEqual(again.status, 200)
        self.assertEqual(len(self.events), 1)

    async def test_crossed_credentials_route_and_group_rejected(self):
        self.assertEqual((await self.post(self.envelope(), secret="other-agent-key")).status, 401)
        body = self.envelope(); body["agentId"] = "agt_other"
        self.assertEqual((await self.post(body)).status, 400)
        body = self.envelope(); body["data"]["group"] = {}
        self.assertEqual((await self.post(body)).status, 400)
        self.assertEqual(self.events, [])

    async def test_unpaired_owner_cannot_enter_private_session(self):
        self.assertEqual((await self.post(self.envelope(text="/approve all"))).status, 403)
        self.assertEqual(self.events, [])

    async def test_voice_timeout_is_bounded_and_late_response_is_not_sent(self):
        async def slow(event):
            await asyncio.sleep(0.15)
            return "too late"
        self.adapter.set_message_handler(slow)
        self.adapter.voice_deadline = 0.02
        response = await self.post(self.envelope())
        chunks = [json.loads(line) for line in (await response.text()).splitlines()]
        self.assertTrue(chunks[0]["interim"])
        self.assertIn("more time", chunks[-1]["text"])
        await asyncio.sleep(0.2)
        self.assertEqual(self.adapter.ledger.get("evt_a")["state"], "expired")

    async def test_sms_delivery_uses_own_credentials_and_uncertain_send_is_not_retried(self):
        body = self.envelope("sms")
        await self.post(body)
        row = self.adapter.ledger.get("evt_a")
        payload = json.loads(row["payload"])
        sent = []
        class Reply:
            status = 200
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def json(self): return {"id": "provider-a"}
        class Client:
            def post(inner, url, **kwargs):
                sent.append((url, kwargs))
                return Reply()
        self.adapter.http = Client()
        await self.adapter.process("evt_a", payload)
        self.assertEqual(self.adapter.ledger.get("evt_a")["state"], "sent")
        self.assertEqual(sent[0][1]["headers"]["Authorization"], "Bearer key-a")
        self.assertEqual(sent[0][1]["json"]["agent_id"], "agt_a")
        self.assertEqual(sent[0][1]["json"]["number_id"], "num_a")
        self.assertFalse(sent[0][1]["allow_redirects"])
        await self.adapter.deliver("evt_a")
        self.assertEqual(len(sent), 1)
        self.adapter.ledger.add("evt_failed", {**payload, "text": "another message"})
        self.adapter.ledger.update("evt_failed", "ready", reply="reply")
        with patch.object(self.adapter.http, "post", side_effect=OSError("uncertain provider response")) as attempt:
            self.assertFalse((await self.adapter.deliver("evt_failed")).success)
            self.assertFalse((await self.adapter.deliver("evt_failed")).success)
            self.assertEqual(attempt.call_count, 1)
        self.assertEqual(self.adapter.ledger.get("evt_failed")["state"], "needs_attention")

    async def test_two_running_adapters_isolate_credentials_sessions_and_phone_memory_routes(self):
        from orgo_phone_test.adapter import AgentPhoneAdapter
        from gateway.config import PlatformConfig
        from gateway.session import build_session_key
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from agent.secret_scope import set_secret_scope, reset_secret_scope
        other_home = self.home / "other-agent"
        other_home.mkdir()
        other_settings = {**self.settings, "agent_id": "agt_b", "number_id": "num_b", "number": "+15550000003"}
        (other_home / "agentphone.json").write_text(json.dumps(other_settings))
        home_context = set_hermes_home_override(other_home)
        scope_context = set_secret_scope({"AGENTPHONE_API_KEY": "key-b", "AGENTPHONE_WEBHOOK_SECRET": "hook-b"})
        try:
            other = AgentPhoneAdapter(PlatformConfig(enabled=True))
        finally:
            reset_secret_scope(scope_context)
            reset_hermes_home_override(home_context)
        self.addCleanup(other.ledger.db.close)
        body_a = self.envelope()
        body_b = self.envelope()
        body_b["agentId"], body_b["data"]["numberId"], body_b["data"]["to"] = "agt_b", "num_b", "+15550000003"
        a, b = self.adapter.normalize(body_a), other.normalize(body_b)
        self.assertNotEqual(a["chat"], b["chat"])
        source_a = self.adapter.build_source(chat_id=a["chat"], user_id=a["caller"])
        source_b = other.build_source(chat_id=b["chat"], user_id=b["caller"])
        self.assertNotEqual(build_session_key(source_a), build_session_key(source_b))
        self.assertEqual((self.adapter.key, other.key), ("key-a", "key-b"))
        self.assertEqual((self.adapter.secret, other.secret), ("hook-a", "hook-b"))
        with self.assertRaises(ValueError): other.normalize(body_a)
        with self.assertRaises(ValueError): self.adapter.normalize(body_b)
        self.adapter.ledger.add("same-provider-event", a)
        other.ledger.add("same-provider-event", b)
        self.assertNotEqual(self.adapter.ledger.get("same-provider-event")["chat"], other.ledger.get("same-provider-event")["chat"])

    async def test_sms_is_durable_before_ack(self):
        response = await self.post(self.envelope("sms"))
        self.assertEqual(response.status, 200)
        self.assertEqual(self.adapter.ledger.pending()[0]["state"], "pending")
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
