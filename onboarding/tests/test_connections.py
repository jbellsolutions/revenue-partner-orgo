import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from onboarding.connections import configure, connection_fingerprint
from onboarding.identity import configure as identity
from onboarding.runtime import Runtime
from onboarding.storage import private_write, read_json, SetupError
from onboarding.__main__ import report
from onboarding.verification import optional


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        (self.root / 'onboarding').mkdir(parents=True)
        private_write(self.root / 'onboarding/role.json', json.dumps({'id':'test-role','name':'Revenue Partner','purpose':'Help','runtime':'native'}))
        self.runtime = Runtime(self.root, home=Path(self.tmp.name) / 'agent-a')
        identity(self.runtime)
        self.command = patch.object(Runtime, 'hermes')
        self.command.start(); self.addCleanup(self.command.stop)
        self.restart = patch.object(Runtime, 'restart')
        self.restart.start(); self.addCleanup(self.restart.stop)

    def test_honcho_maps_owner_and_keeps_distinct_agent_memories(self):
        other = Runtime(self.root, home=Path(self.tmp.name) / 'agent-b')
        identity(other)
        for runtime in (self.runtime, other):
            runtime.save_env({'SLACK_ALLOWED_USERS':'UOWNER'})
            private_write(runtime.home / 'orgo-channel.json', json.dumps({'platform':'slack'}))
            configure(runtime, 'honcho', {'HONCHO_API_KEY':'honcho-fixture'})
        a = read_json(self.runtime.home / 'honcho.json')['hosts']['hermes']
        b = read_json(other.home / 'honcho.json')['hosts']['hermes']
        self.assertNotEqual(a['workspace'], b['workspace'])
        self.assertNotEqual(a['aiPeer'], b['aiPeer'])
        self.assertEqual(a['userPeerAliases']['UOWNER'], a['peerName'])
        configure(self.runtime, 'honcho', {'HONCHO_API_KEY':'rotated-fixture'})
        self.assertEqual(read_json(self.runtime.home / 'honcho.json')['hosts']['hermes']['aiPeer'], a['aiPeer'])

    def test_sanitized_capture_needs_separate_selection_and_raw_is_rejected(self):
        settings = {'LATITUDE_API_KEY':'latitude-fixture', 'LATITUDE_PROJECT_SLUG':'test-project'}
        for mode in ('raw', 'sanitized'):
            with self.assertRaises(SetupError):
                configure(self.runtime, 'latitude', {**settings, 'capture_mode':mode})
        self.assertEqual(self.runtime.state.get('latitude')['status'], 'needs_attention')
        configure(self.runtime, 'latitude', settings)
        self.assertEqual(self.runtime.env()['LATITUDE_CAPTURE_MODE'], 'metadata')
        self.assertEqual(self.runtime.state.get('latitude')['status'], 'configured')

    def test_production_card_key_is_rejected_before_any_credential_write(self):
        with self.assertRaises(SetupError):
            configure(self.runtime, 'agentcard', {'AGENTCARD_API_KEY':'production-fixture'})
        self.assertNotIn('AGENTCARD_API_KEY', self.runtime.env())
        configure(self.runtime, 'agentcard', {'AGENTCARD_API_KEY':'sk_test_fixture'})
        self.assertNotIn('create_card', self.runtime.get('mcp_servers.agent-cards.tools')['include'])
        self.assertFalse(read_json(self.runtime.home / 'agentcard.json')['spending_enabled'])

    def test_invalid_inbox_credential_is_unverified_and_resume_reuses_created_identity(self):
        with patch('onboarding.discovery.fetch', side_effect=SetupError('Credential rejected')):
            with self.assertRaises(SetupError):
                configure(self.runtime, 'agentmail', {'AGENTMAIL_API_KEY':'expired-fixture','inbox_id':'inbox-a'})
        self.assertEqual(self.runtime.state.get('agentmail')['status'], 'needs_attention')
        client_id = 'orgo-' + read_json(self.runtime.home / 'orgo-identity.json')['instance_id']
        with patch('onboarding.discovery.fetch', return_value={'inboxes':[{'inbox_id':'inbox-a','client_id':client_id}]}) as provider:
            configure(self.runtime, 'agentmail', {'AGENTMAIL_API_KEY':'valid-fixture','create_inbox_selected':True})
            self.assertTrue(all(call.kwargs.get('method','GET') == 'GET' for call in provider.call_args_list))
        self.assertEqual(read_json(self.runtime.home / 'agentmail.json')['inbox_id'], 'inbox-a')
        self.assertEqual(self.runtime.state.get('agentmail')['status'], 'configured')
        with self.assertRaises(SetupError): optional(self.runtime, 'agentmail')

    def test_connection_change_invalidates_success_and_never_reuses_old_receipt(self):
        configure(self.runtime, 'composio', {'COMPOSIO_API_KEY':'ck_fixture'})
        before = connection_fingerprint(self.runtime, 'composio')
        self.runtime.state.set('composio', 'verified', check='test-fixture', fingerprint=before)
        self.runtime.save_env({'COMPOSIO_API_KEY':'ck_rotated_fixture'})
        self.assertEqual(report(self.runtime)['steps']['composio']['status'], 'needs_attention')
        self.assertNotEqual(before, connection_fingerprint(self.runtime, 'composio'))
        self.assertNotIn('ck_rotated_fixture', json.dumps(report(self.runtime)))

    @unittest.skipUnless(os.environ.get('HERMES_SOURCE'), 'Actual Hermes secret scope required')
    def test_successful_tool_receipt_is_bound_to_actual_scoped_credentials(self):
        sys.path.insert(0, os.environ['HERMES_SOURCE'])
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from agent.secret_scope import set_secret_scope, reset_secret_scope
        configure(self.runtime, 'composio', {'COMPOSIO_API_KEY':'ck_fixture'})
        plugin = Path(__file__).resolve().parents[1] / 'plugins/setup-evidence/__init__.py'
        spec = importlib.util.spec_from_file_location('setup_evidence_test', plugin)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        home_context = set_hermes_home_override(self.runtime.home)
        secret_context = set_secret_scope({'COMPOSIO_API_KEY':'ck_fixture'})
        try:
            module.on_tool(tool_name='mcp__composio__list_accounts', status='success', result='{"accounts": []}')
        finally:
            reset_secret_scope(secret_context); reset_hermes_home_override(home_context)
        optional(self.runtime, 'composio')
        self.assertEqual(self.runtime.state.get('composio')['status'], 'verified')
        self.runtime.save_env({'COMPOSIO_API_KEY':'ck_changed'})
        with self.assertRaises(SetupError): optional(self.runtime, 'composio')


if __name__ == '__main__':
    unittest.main()
