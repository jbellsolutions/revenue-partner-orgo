import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.observer = module("latitude_onboarding_test", ROOT / "plugins/latitude-observer/__init__.py")

    def test_metadata_never_contains_conversation_or_tool_content(self):
        with patch.object(self.observer, "_secret", side_effect=lambda key, default="": default):
            self.assertIsNone(self.observer._content({"token": "private", "customer": "private customer"}))
            self.assertEqual(self.observer._capture_mode(), "metadata")

    def test_sanitized_requires_redaction_and_has_no_raw_mode(self):
        with patch.object(self.observer, "_secret", return_value="raw"):
            self.assertEqual(self.observer._capture_mode(), "metadata")
        with patch.object(self.observer, "_secret", return_value="sanitized"), patch.object(self.observer, "_redact", return_value="[redacted]"):
            self.assertEqual(self.observer._content("private"), "[redacted]")

    def test_destination_is_pinned_and_redirects_are_rejected(self):
        with patch.object(self.observer, "_secret", return_value="https://wrong.example/collect"):
            self.assertIsNone(self.observer._endpoint())
        handler = self.observer._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, "https://wrong.example"))

    def test_export_outage_is_fail_open_and_bounded(self):
        exporter = object.__new__(self.observer.Exporter)
        exporter.endpoint, exporter.api_key, exporter.project, exporter.service = self.observer.DEFAULT_ENDPOINT, "test-key", "test-project", "test-agent"
        with patch.object(self.observer.request, "build_opener") as opener, patch.object(self.observer.time, "sleep"):
            opener.return_value.open.side_effect = OSError("offline")
            exporter._send([{"traceId": "a" * 32, "spanId": "b" * 16, "name": "hermes.agent.turn"}])
            self.assertEqual(opener.return_value.open.call_count, 3)

    @unittest.skipUnless(os.environ.get("HERMES_SOURCE"), "Pinned Hermes source required")
    def test_real_plugin_manifests_parse_and_register(self):
        sys.path.insert(0, os.environ["HERMES_SOURCE"])
        from hermes_cli.plugins import PluginContext, PluginManager
        from hermes_cli.plugins_manifest import parse_manifest_file
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"HERMES_HOME": directory}):
            manager = PluginManager()
            for plugin in ["latitude-observer", "setup-evidence", "agentphone-channel"]:
                manifest = parse_manifest_file(ROOT / "plugins" / plugin / "plugin.yaml", ROOT / "plugins" / plugin, source="user", prefix="")
                self.assertIsNotNone(manifest)
                spec = importlib.util.spec_from_file_location("load_test_" + plugin.replace("-", "_"), ROOT / "plugins" / plugin / "__init__.py", submodule_search_locations=[str(ROOT / "plugins" / plugin)])
                loaded = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = loaded
                spec.loader.exec_module(loaded)
                loaded.register(PluginContext(manifest, manager))

    @unittest.skipUnless(os.environ.get("HERMES_SOURCE"), "Pinned Hermes source required")
    def test_each_profile_uses_its_own_exporter_and_empty_scope_inherits_nothing(self):
        sys.path.insert(0, os.environ["HERMES_SOURCE"])
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from agent.secret_scope import set_secret_scope, reset_secret_scope
        with tempfile.TemporaryDirectory() as directory, patch.object(self.observer.Exporter, "_run"):
            def get(name, values):
                home = set_hermes_home_override(Path(directory) / name)
                scope = set_secret_scope(values)
                try:
                    return self.observer._exporter()
                finally:
                    reset_secret_scope(scope)
                    reset_hermes_home_override(home)
            a = get("a", {"LATITUDE_API_KEY": "key-a", "LATITUDE_PROJECT_SLUG": "project-a"})
            b = get("b", {"LATITUDE_API_KEY": "key-b", "LATITUDE_PROJECT_SLUG": "project-b", "LATITUDE_CAPTURE_MODE": "sanitized"})
            self.assertIsNot(a, b)
            self.assertEqual((a.api_key, a.project, a.mode), ("key-a", "project-a", "metadata"))
            self.assertEqual((b.api_key, b.project, b.mode), ("key-b", "project-b", "sanitized"))
            self.assertIsNone(get("worker", {}))
            a.close(); b.close()


if __name__ == "__main__":
    unittest.main()
