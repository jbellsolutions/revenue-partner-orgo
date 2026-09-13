import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from onboarding.catalog import CORE, SERVICES
from onboarding.storage import State, SetupError, private_write, update_env, read_env, install_tree
from onboarding.runtime import Runtime
from onboarding.identity import configure, verify_local
from onboarding.__main__ import main, report
from onboarding.install import checkpoint


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.root = self.base / "repo"
        (self.root / "onboarding").mkdir(parents=True)
        self.role = {"id": "test-agent", "runtime": "native", "name": "Revenue Partner", "purpose": "Help the business", "slack_manifests": ["slack-manifest.json"]}
        (self.root / "onboarding/role.json").write_text(json.dumps(self.role))
        (self.root / "slack-manifest.json").write_text(json.dumps({"display_information": {"name": "Original"}, "features": {"bot_user": {"display_name": "Original"}}}))
        self.runtime = Runtime(self.root, home=self.home)

    def test_explicit_docker_configuration_selects_its_deployment(self):
        self.role["runtime"] = "compose"
        (self.root / "onboarding/role.json").write_text(json.dumps(self.role))
        config = self.base / "customer.env"
        deployment = (self.base / "customer installation").resolve()
        update_env(config, {"BASE_DIR": str(deployment)})
        runtime = Runtime(self.root, config=config)
        self.assertEqual(runtime.home, deployment / "hermes/data")
        self.assertEqual(runtime.env_file, deployment / ".env")
        self.assertEqual(runtime.source_config, config.resolve())
        with self.assertRaises(SetupError):
            Runtime(self.root, config=config, home=deployment / "hermes/data/profiles/worker")

    def test_private_state_and_secret_free_report(self):
        state = self.runtime.state
        with state.lock():
            state.set("honcho", "configured", fingerprint="a" * 64)
            state.mark_attention("honcho")
        self.assertEqual(state.get("honcho")["status"], "needs_attention")
        self.assertEqual(state.get("honcho")["fingerprint"], "a" * 64)
        self.assertEqual(state.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("SECRET", state.path.read_text())
        with self.assertRaises(SetupError):
            state.set("honcho", "verified", check="SECRET / arbitrary diagnostic")

    def test_interrupted_progress_and_skip_resume(self):
        with self.runtime.state.lock():
            self.runtime.state.set("honcho", "skipped")
        restored = State(self.home, "test-agent")
        self.assertEqual(restored.get("honcho")["status"], "skipped")
        self.assertEqual(restored.get("latitude")["status"], "not_started")
        with restored.lock():
            with self.assertRaises(SetupError), restored.lock():
                pass

    def test_corrupt_state_fails_without_reset(self):
        private_write(self.runtime.state.path, "not valid json")
        with self.assertRaises(SetupError):
            self.runtime.state.load()
        self.assertEqual(self.runtime.state.path.read_text(), "not valid json")

    def test_private_env_preserves_other_values_and_rejects_shell_syntax(self):
        path = self.home / ".env"
        update_env(path, {"FIRST_KEY": "existing", "SECOND_KEY": "private value # safely quoted"})
        update_env(path, {"FIRST_KEY": "updated"})
        self.assertEqual(read_env(path), {"FIRST_KEY": "updated", "SECOND_KEY": "private value # safely quoted"})
        for value in ["$(touch bad)", "x\nANOTHER_KEY=x", "x`id`", "bad'quote"]:
            with self.assertRaises(SetupError):
                update_env(path, {"FIRST_KEY": value})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_personalization_defaults_and_preserves_existing(self):
        value = configure(self.runtime)
        self.assertEqual(value["display_name"], "Revenue Partner")
        configure(self.runtime, name="Acme Revenue")
        verify_local(self.runtime)
        self.assertEqual(configure(self.runtime)["display_name"], "Acme Revenue")
        self.assertEqual(json.loads((self.home / "slack-manifest.json").read_text())["features"]["bot_user"]["display_name"], "Acme Revenue")

    def test_update_preflights_all_custom_files(self):
        source, target = self.base / "source", self.base / "target"
        source.mkdir(); target.mkdir()
        (source / "a").write_text("new")
        (source / "b").write_text("new")
        (target / "a").write_text("old")
        (target / "b").write_text("custom")
        import hashlib
        manifest = self.base / "manifest.json"
        private_write(manifest, json.dumps({"a": hashlib.sha256(b"old").hexdigest()}))
        with self.assertRaises(SetupError):
            install_tree(source, target, manifest)
        self.assertEqual((target / "a").read_text(), "old")
        self.assertEqual((target / "b").read_text(), "custom")

    def test_fresh_journey_can_skip_all_optional_services(self):
        def fake_install(runtime, **kwargs):
            private_write(runtime.home / "SOUL.md", "# Revenue Partner\n\nYou are Revenue Partner.\n")
            private_write(runtime.home / "config.yaml", "{}")
        def fake_verify(runtime, step):
            if step == "channel":
                raise SetupError("A live channel remains to be verified")
            runtime.state.set(step, "verified", check="test-fixture")
        with patch.object(Runtime, "hermes"), patch("onboarding.__main__.install", fake_install), patch("onboarding.__main__.verify", fake_verify), patch("onboarding.__main__.desktop"), patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            code = main(["setup", "--root", str(self.root), "--home", str(self.home), "--skip-optional"])
        self.assertEqual(code, 0)
        self.assertTrue(all(self.runtime.state.get(key)["status"] == "skipped" for key in SERVICES))
        self.assertFalse(report(self.runtime)["basic_ready"])

    def test_native_rollback_preserves_custom_identity_and_secret(self):
        private_write(self.home / "SOUL.md", "custom identity")
        private_write(self.home / "config.yaml", "custom: true")
        private_write(self.home / ".env", "SECRET_KEY='private'")
        with patch.object(self.runtime, "health", return_value=False), self.assertRaises(RuntimeError):
            with checkpoint(self.runtime):
                private_write(self.home / "SOUL.md", "broken")
                raise RuntimeError("simulated failed update")
        self.assertEqual((self.home / "SOUL.md").read_text(), "custom identity")
        self.assertEqual(read_env(self.home / ".env")["SECRET_KEY"], "private")

    def test_incomplete_backup_never_replaces_live_home(self):
        private_write(self.home / "SOUL.md", "custom identity")
        private_write(self.home / "config.yaml", "custom: true")
        with patch.object(self.runtime, "health", return_value=False), patch("onboarding.install.shutil.copytree", side_effect=OSError("disk full")), self.assertRaises(OSError):
            with checkpoint(self.runtime):
                self.fail("must not start update without a complete snapshot")
        self.assertEqual((self.home / "SOUL.md").read_text(), "custom identity")

    def test_compose_adapter_uses_selected_deployment(self):
        self.role["runtime"] = "compose"
        (self.root / "onboarding/role.json").write_text(json.dumps(self.role))
        deployment = (self.base / "my deployment").resolve()
        runtime = Runtime(self.root, deployment=deployment)
        self.assertEqual(runtime.home, deployment / "hermes/data")
        self.assertEqual(runtime.compose(), ["docker", "compose", "--env-file", str(deployment / ".env"), "-f", str(deployment / "compose.yml")])


if __name__ == "__main__":
    unittest.main()
