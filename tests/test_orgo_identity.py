from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("orgo_identity", ROOT / "orgo/identity.py")
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class NamingTests(unittest.TestCase):
    def test_default_custom_and_duplicate_suffixes(self):
        for raw, prefix, name in (
            ("", "", "Revenue Agent"),
            ("  Acme  North  ", "Acme North", "Acme North Revenue Agent"),
            ("Revenue Agent", "", "Revenue Agent"),
            ("Acme Revenue Agent", "Acme", "Acme Revenue Agent"),
            ("Acme revenue agent Revenue Agent", "Acme", "Acme Revenue Agent"),
            ("Café", "Café", "Café Revenue Agent"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual((prefix, name), identity.normalize_prefix(raw))

    def test_length_boundary_is_not_truncated(self):
        self.assertEqual(35, len(identity.normalize_prefix("A" * 21)[1]))
        with self.assertRaises(identity.IdentityError):
            identity.normalize_prefix("A" * 22)

    def test_control_characters_are_rejected(self):
        for control in ("\n", "\r", "\t", "\x00", "\x1b", "\x7f", "\u202e", "\u2028", "\u200b"):
            with self.subTest(control=repr(control)), self.assertRaises(identity.IdentityError):
                identity.normalize_prefix("Acme" + control)

    def test_precedence_and_explicit_empty_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"AGENT_NAME_PREFIX": "Environment"}):
                self.assertEqual("Argument Revenue Agent", identity.resolve(home, "Argument")["display_name"])
                self.assertEqual("Revenue Agent", identity.resolve(home, "")["display_name"])
                self.assertEqual("Environment Revenue Agent", identity.resolve(home)["display_name"])
            with patch.dict(os.environ, {}, clear=True):
                identity.prepare(ROOT, home, "Saved")
                self.assertEqual("Saved Revenue Agent", identity.resolve(home)["display_name"])


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "hermes"
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def sync(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "orgo/sync_seed.py"), str(ROOT), str(self.home), *args],
            check=True, capture_output=True, text=True, env=env,
        )

    def test_fresh_install_names_match_and_product_instructions_are_preserved(self):
        self.sync("--name-prefix", "Acme")
        saved = identity.read_settings(self.home)
        self.assertEqual("Acme Revenue Agent", saved["display_name"])
        self.assertEqual(0o600, stat.S_IMODE((self.home / identity.SETTINGS).stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE((self.home / "SOUL.md").stat().st_mode))
        self.assertTrue((self.home / identity.PROFILE_MARKER).exists())
        installed = (self.home / "SOUL.md").read_text()
        source = (ROOT / "files/SOUL.md").read_text()
        self.assertEqual(source.splitlines()[3:], installed.splitlines()[3:])
        self.assertIn("Revenue Partner program", installed)
        self.assertIn("Acme Revenue Agent", installed)
        self.assertIn("Slack identity read skipped", " ".join(identity.verify(self.home, local_only=True)))

    def test_only_two_manifest_fields_change_and_all_commands_survive(self):
        self.sync("--name-prefix", "Acme")
        source = json.loads((ROOT / "slack-manifest.json").read_text())
        generated = json.loads((self.home / "slack-manifest.json").read_text())
        self.assertEqual("Acme Revenue Agent", generated["display_information"]["name"])
        self.assertEqual("Acme Revenue Agent", generated["features"]["bot_user"]["display_name"])
        generated["display_information"]["name"] = source["display_information"]["name"]
        generated["features"]["bot_user"]["display_name"] = source["features"]["bot_user"]["display_name"]
        self.assertEqual(source, generated)
        self.assertEqual(50, len(generated["features"]["slash_commands"]))

    def test_default_is_revenue_agent(self):
        self.sync()
        self.assertEqual("Revenue Agent", identity.display_name(self.home))

    def test_repeat_setup_preserves_owner_soul_skills_and_saved_name(self):
        self.sync("--name-prefix", "Acme")
        soul = self.home / "SOUL.md"
        soul.write_text(soul.read_text() + "\nOwner's specific operating instructions.\n")
        skill = self.home / "skills/go-to-market/revenue-partner/SKILL.md"
        skill.write_text(skill.read_text() + "\nOwner's skill changes.\n")
        before_soul, before_skill = soul.read_bytes(), skill.read_bytes()
        self.sync()
        self.assertEqual(before_soul, soul.read_bytes())
        self.assertEqual(before_skill, skill.read_bytes())
        self.assertEqual("Acme Revenue Agent", identity.display_name(self.home))

    def test_explicit_new_prefix_changes_only_managed_identity_lines(self):
        self.sync("--name-prefix", "Acme")
        soul = self.home / "SOUL.md"
        soul.write_text(soul.read_text() + "\nKeep this instruction and the Revenue Partner offer.\n")
        before = soul.read_text().splitlines()[3:]
        self.sync("--name-prefix", "Second")
        self.assertEqual(before, soul.read_text().splitlines()[3:])
        self.assertIn("Second Revenue Agent", soul.read_text())
        identity.verify(self.home, local_only=True)

    def test_edited_identity_blocks_rename_before_any_write(self):
        self.sync("--name-prefix", "Acme")
        soul = self.home / "SOUL.md"
        soul.write_text(soul.read_text().replace("# SOUL.md — Acme Revenue Agent", "# Owner's preferred identity"))
        before = {p.name: p.read_bytes() for p in (soul, self.home / identity.SETTINGS, self.home / identity.MANIFEST)}
        with self.assertRaises(identity.IdentityError):
            identity.prepare(ROOT, self.home, "Second")
        self.assertEqual(before, {name: (self.home / name).read_bytes() for name in before})
        # A normal rerun also preserves the customization, but verification reports drift.
        self.sync()
        self.assertEqual(before["SOUL.md"], soul.read_bytes())
        with self.assertRaises(identity.IdentityError):
            identity.verify(self.home, local_only=True)

    def test_existing_profile_without_settings_is_never_migrated(self):
        self.home.mkdir()
        (self.home / identity.PROFILE_MARKER).write_text("previous installation")
        (self.home / "SOUL.md").write_text("# SOUL.md — Existing Owner Name\nPrivate instructions.\n")
        (self.home / identity.MANIFEST).write_text('{"existing":"manifest"}')
        before = (self.home / "SOUL.md").read_bytes()
        self.sync()
        self.assertEqual(before, (self.home / "SOUL.md").read_bytes())
        self.assertFalse((self.home / identity.SETTINGS).exists())
        self.assertEqual('{"existing":"manifest"}', (self.home / identity.MANIFEST).read_text())
        self.assertEqual("Existing Owner Name", identity.display_name(self.home))
        with self.assertRaises(identity.IdentityError):
            identity.prepare(ROOT, self.home, "Acme")
        self.assertIn("preserved", identity.verify(self.home)[0])

    def test_preexisting_base_template_soul_is_backed_up_once(self):
        self.home.mkdir()
        (self.home / "SOUL.md").write_text("Base Hermes identity")
        self.sync()
        self.sync()
        backup = self.home / "SOUL.md.before-revenue-partner"
        self.assertEqual("Base Hermes identity", backup.read_text())
        self.assertEqual(0o600, stat.S_IMODE(backup.stat().st_mode))

    def test_preexisting_owner_skill_is_preserved_on_every_install(self):
        skill = self.home / "skills/go-to-market/revenue-partner/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("Owner's skill from before this installer was used.\n")
        before = skill.read_bytes()
        self.sync()
        self.sync()
        self.assertEqual(before, skill.read_bytes())

    def test_invalid_prefix_cannot_create_or_change_an_installation(self):
        with self.assertRaises(identity.IdentityError):
            identity.prepare(ROOT, self.home, "bad\nname")
        self.assertFalse(self.home.exists())
        self.sync()
        before = (self.home / identity.SETTINGS).read_bytes()
        with self.assertRaises(identity.IdentityError):
            identity.prepare(ROOT, self.home, "A" * 22)
        self.assertEqual(before, (self.home / identity.SETTINGS).read_bytes())

    def test_malformed_settings_do_not_reset_identity(self):
        self.sync()
        (self.home / identity.SETTINGS).write_text('{"unexpected":"field"}')
        before = (self.home / "SOUL.md").read_bytes()
        with self.assertRaises(identity.IdentityError):
            identity.prepare(ROOT, self.home)
        self.assertEqual(before, (self.home / "SOUL.md").read_bytes())

    def test_name_is_data_never_executable_desktop_content(self):
        self.sync("--name-prefix", '$(touch NOPE)')
        desktop = Path(self.temporary.name) / "Desktop"
        identity.install_desktop(ROOT, self.home, desktop)
        for filename in ("RevenuePartner.desktop", "RevenuePartnerSetup.desktop"):
            original = (ROOT / "orgo" / filename).read_text().splitlines()
            generated = (desktop / filename).read_text().splitlines()
            self.assertEqual([l for l in original if l.startswith("Exec=")], [l for l in generated if l.startswith("Exec=")])
            self.assertIn('$(touch NOPE) Revenue Agent', "\n".join(generated))
        self.assertFalse((ROOT / "NOPE").exists())
        identity.verify(self.home, local_only=True)

    def test_manifest_refresh_uses_saved_name_not_environment(self):
        self.sync("--name-prefix", "Acme")
        env = {**os.environ, "AGENT_NAME_PREFIX": "Unrelated"}
        subprocess.run([sys.executable, str(ROOT / "orgo/identity.py"), "manifest", "--hermes-home", str(self.home)], env=env, capture_output=True, check=True)
        identity.verify(self.home, local_only=True)
        self.assertEqual("Acme Revenue Agent", identity.display_name(self.home))

    def test_failed_settings_write_restores_previous_files_and_can_retry(self):
        self.sync("--name-prefix", "Acme")
        paths = [self.home / name for name in ("SOUL.md", identity.MANIFEST, identity.SETTINGS)]
        before = {path: path.read_bytes() for path in paths}
        real_write = identity.write_private
        def fail_settings(path, *args):
            if path.name == identity.SETTINGS:
                raise OSError("test-only disk error")
            real_write(path, *args)
        with patch.object(identity, "write_private", side_effect=fail_settings):
            with self.assertRaisesRegex(identity.IdentityError, "restored"):
                identity.prepare(ROOT, self.home, "Second")
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        identity.prepare(ROOT, self.home, "Second")
        identity.verify(self.home, local_only=True)

    def test_repeat_desktop_render_preserves_owner_launch_command_and_icon(self):
        self.sync("--name-prefix", "Acme")
        desktop = Path(self.temporary.name) / "Desktop"
        identity.install_desktop(ROOT, self.home, desktop)
        launcher = desktop / "RevenuePartner.desktop"
        content = launcher.read_text().replace("Icon=utilities-terminal", "Icon=owner-icon")
        content = content.replace("Exec=xfce4-terminal", "Exec=owner-terminal")
        launcher.write_text(content)
        identity.install_desktop(ROOT, self.home, desktop)
        self.assertEqual(content, launcher.read_text())


class SlackVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        identity.prepare(ROOT, self.home, "Acme")
        self.secret = "test-only-private-credential"
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.dotenv = patch.dict(sys.modules, {"dotenv": types.SimpleNamespace(dotenv_values=lambda *a, **k: {"SLACK_BOT_TOKEN": self.secret})})
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def call(self, method, token, params=None, *, display="Acme Revenue Agent", real="Acme Revenue Agent"):
        self.assertEqual(self.secret, token)
        if method == "auth.test":
            return {"ok": True, "user_id": "U_TEST_BOT"}
        self.assertEqual("users.info", method)
        self.assertEqual({"user": "U_TEST_BOT"}, params)
        return {"ok": True, "user": {"id": "U_TEST_BOT", "is_bot": True, "profile": {"display_name": display, "real_name": real}}}

    def test_matching_slack_profile_and_empty_display_name_fallback(self):
        self.assertIn("Connected Slack bot name matches", identity.verify(self.home, call=self.call)[-1])
        self.assertIn("matches", identity.verify(self.home, call=lambda *args: self.call(*args, display=""))[-1])

    def test_slack_mismatch_is_reported_without_writes(self):
        before = {p.name: p.read_bytes() for p in self.home.iterdir() if p.is_file()}
        with self.assertRaisesRegex(identity.IdentityError, "differs"):
            identity.verify(self.home, call=lambda *args: self.call(*args, display="Old Name"))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.home.iterdir() if p.is_file()})

    def test_missing_token_is_explicitly_unverified(self):
        with patch.dict(sys.modules, {"dotenv": types.SimpleNamespace(dotenv_values=lambda *a, **k: {})}):
            self.assertIn("not been verified", identity.verify(self.home, call=self.call)[-1])

    def test_local_only_never_contacts_slack(self):
        def prohibited(*args):
            self.fail("local verification contacted Slack")
        identity.verify(self.home, local_only=True, call=prohibited)

    def test_api_failure_or_malformed_reply_never_exposes_credentials(self):
        def failure(*args):
            raise RuntimeError(self.secret)
        for call in (failure, lambda *args: {"ok": False, "error": self.secret}, lambda *args: {}):
            with self.subTest(call=call), self.assertRaises(identity.IdentityError) as error:
                identity.verify(self.home, call=call)
            self.assertNotIn(self.secret, str(error.exception))

    def test_http_is_bounded_read_only_and_does_not_follow_redirects(self):
        response = types.SimpleNamespace(read=lambda count: b'{"ok":true}')
        class Context:
            def __enter__(self):
                return response
            def __exit__(self, *args):
                pass
        requests = []
        def open_request(request, timeout):
            requests.append(request)
            self.assertEqual(15, timeout)
            return Context()
        with patch.object(identity.urllib.request, "build_opener", return_value=types.SimpleNamespace(open=open_request)) as opener:
            identity.slack_call("auth.test", self.secret)
            identity.slack_call("users.info", self.secret, {"user": "U_TEST_BOT"})
            self.assertEqual({}, opener.call_args.args[0].proxies)
            self.assertIsInstance(opener.call_args.args[1], identity.NoRedirect)
        for request in requests:
            self.assertEqual("GET", request.get_method())
            self.assertTrue(request.full_url.startswith("https://slack.com/api/"))
            self.assertNotIn(self.secret, request.full_url)
        self.assertIsNone(identity.NoRedirect().redirect_request(None, None, 302, None, {}, "https://example.com"))
        with self.assertRaises(identity.IdentityError):
            identity.slack_call("users.profile.set", self.secret)

    def test_transport_exception_is_redacted(self):
        with patch.object(identity.urllib.request, "build_opener", side_effect=RuntimeError(self.secret)):
            with self.assertRaises(identity.IdentityError) as error:
                identity.slack_call("auth.test", self.secret)
        self.assertNotIn(self.secret, str(error.exception))

    def test_wrong_bot_or_user_id_is_not_accepted_as_matching(self):
        for is_bot, user_id in ((False, "U_TEST_BOT"), (True, "U_WRONG")):
            def wrong_identity(method, token, params=None):
                result = self.call(method, token, params)
                if method == "users.info":
                    result["user"].update(is_bot=is_bot, id=user_id)
                return result
            with self.subTest(is_bot=is_bot, user_id=user_id), self.assertRaises(identity.IdentityError):
                identity.verify(self.home, call=wrong_identity)

    def test_each_local_name_mismatch_is_detected(self):
        for field in ("app", "bot", "soul"):
            with self.subTest(field=field):
                identity.write_private(self.home / identity.MANIFEST, identity.render_manifest(ROOT, "Acme Revenue Agent"))
                identity.write_private(self.home / "SOUL.md", identity.render_soul((ROOT / "files/SOUL.md").read_text(), "Acme Revenue Agent"))
                if field == "soul":
                    (self.home / "SOUL.md").write_text("Wrong identity")
                else:
                    path = self.home / identity.MANIFEST
                    manifest = json.loads(path.read_text())
                    if field == "app":
                        manifest["display_information"]["name"] = "Wrong"
                    else:
                        manifest["features"]["bot_user"]["display_name"] = "Wrong"
                    path.write_text(json.dumps(manifest))
                with self.assertRaises(identity.IdentityError):
                    identity.verify(self.home, local_only=True)


if __name__ == "__main__":
    unittest.main()
