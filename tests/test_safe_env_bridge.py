from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "files/safe-env-bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("safe_env_bridge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SafeEnvironmentBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()

    def test_shell_significant_values_are_quoted_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "hermes.env"
            marker = root / "executed"
            value = f"http://user:p@ss word;$(touch {marker})#@proxy.example:8080"
            target.write_text("KEEP=value\nHERMES_YOLO_MODE=1\nBLOCKED_PROVIDER_SECRET=old\n")

            count = self.bridge.update_env(
                target,
                [target],
                environ={"LATITUDE_API_KEY": value, "AI_GATEWAY_API_KEY": "safe value"},
            )
            self.assertEqual(count, 2)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            rendered = target.read_text()
            self.assertNotIn("KEEP=value", rendered)
            self.assertNotIn("HERMES_YOLO_MODE", rendered)

            command = [
                "bash",
                "-c",
                "set -a; . \"$1\"; printf '%s' \"$LATITUDE_API_KEY\"",
                "bridge-test",
                str(target),
            ]
            result = subprocess.run(command, text=True, capture_output=True, check=False, env={"PATH": os.environ["PATH"]})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, value)
            self.assertFalse(marker.exists())

    def test_newlines_and_unparseable_source_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.env"
            target = root / "target.env"
            source.write_text("LATITUDE_API_KEY=$(touch bad file)\nSAFE_OTHER=keep\n")
            self.bridge.update_env(target, [source], environ={"LATITUDE_API_KEY": "line1\nline2"})
            self.assertNotIn("LATITUDE_API_KEY", target.read_text())

    def test_exec_exports_allowlisted_values_without_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.env"
            target = root / "target.env"
            marker = root / "must-not-exist"
            value = f"value with spaces;$(touch {marker})"
            source.write_text(f"LATITUDE_API_KEY={value!r}\nUNMANAGED=blocked\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    str(target),
                    "--source",
                    str(source),
                    "--exec",
                    sys.executable,
                    "-c",
                    (
                        "import os; print(os.environ['LATITUDE_API_KEY']); "
                        "assert 'UNMANAGED' not in os.environ; "
                        "assert 'UNMANAGED_SECRET' not in os.environ; "
                        "assert 'HERMES_YOLO_MODE' not in os.environ; "
                        "assert 'PATH' in os.environ"
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
                env={
                    "PATH": os.environ["PATH"],
                    "UNMANAGED_SECRET": "must-not-cross",
                    "HERMES_YOLO_MODE": "1",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(value, result.stdout)
            self.assertFalse(marker.exists())

    def test_cli_default_excludes_disabled_connector_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.env"
            target = root / "target.env"
            source.write_text(
                "LATITUDE_API_KEY=latitude-test-value\n"
                "MODEL_API_KEY=model-test-value\n"
                "TELEGRAM_BOT_TOKEN=telegram-test-value\n"
                "COMPOSIO_CONSUMER_KEY=disabled-composio-value\n"
                "ORGO_API_KEY=disabled-orgo-value\n"
                "REVENUE_PARTNER_REVIEW_ATTESTATIONS=/tmp/review-attestation.json\n"
                "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY=/tmp/event-intent.json\n"
                "REVENUE_PARTNER_NONCE_LEDGER=/tmp/nonce-ledger\n"
                "NOTION_API_KEY=disabled-notion-value\n"
                "SLACK_BOT_TOKEN=disabled-slack-value\n"
                "AGENTPHONE_API_KEY=disabled-phone-value\n"
                "AGENTMAIL_API_KEY=disabled-mail-value\n"
                "OP_SERVICE_ACCOUNT_TOKEN=bootstrap-only-value\n"
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--target", str(target), "--source", str(source)],
                text=True,
                capture_output=True,
                check=False,
                env={"PATH": os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = target.read_text()
            for allowed in ("LATITUDE_API_KEY", "MODEL_API_KEY", "TELEGRAM_BOT_TOKEN", "SLACK_BOT_TOKEN"):
                self.assertIn(allowed, rendered)
            for blocked in (
                "COMPOSIO_CONSUMER_KEY",
                "ORGO_API_KEY",
                "REVENUE_PARTNER_REVIEW_ATTESTATIONS",
                "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY",
                "REVENUE_PARTNER_NONCE_LEDGER",
                "NOTION_API_KEY",
                "AGENTPHONE_API_KEY",
                "AGENTMAIL_API_KEY",
                "OP_SERVICE_ACCOUNT_TOKEN",
            ):
                self.assertNotIn(blocked, rendered)

            release_target = root / "release.env"
            release_probe = (
                "import json,os; print(json.dumps({k:v for k,v in os.environ.items() "
                "if k in ['ORGO_API_KEY','REVENUE_PARTNER_REVIEW_ATTESTATIONS','REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY','REVENUE_PARTNER_NONCE_LEDGER','COMPOSIO_CONSUMER_KEY','MODEL_API_KEY']},sort_keys=True))"
            )
            release_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    str(release_target),
                    "--source",
                    str(source),
                    "--only",
                    "ORGO_API_KEY",
                    "--only",
                    "REVENUE_PARTNER_REVIEW_ATTESTATIONS",
                    "--only",
                    "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY",
                    "--only",
                    "REVENUE_PARTNER_NONCE_LEDGER",
                    "--exec",
                    sys.executable,
                    "-c",
                    release_probe,
                ],
                text=True,
                capture_output=True,
                check=False,
                env={"PATH": os.environ["PATH"]},
            )
            self.assertEqual(release_result.returncode, 0, release_result.stderr)
            self.assertEqual(
                json.loads(release_result.stdout.splitlines()[-1]),
                {
                    "ORGO_API_KEY": "disabled-orgo-value",
                    "REVENUE_PARTNER_REVIEW_ATTESTATIONS": "/tmp/review-attestation.json",
                    "REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY": "/tmp/event-intent.json",
                    "REVENUE_PARTNER_NONCE_LEDGER": "/tmp/nonce-ledger",
                },
            )
            for document in (ROOT / "LEGACY-TEMPLATE.md", ROOT / "docs/DEPLOYMENT.md"):
                documented = document.read_text()
                self.assertIn("--only ORGO_API_KEY", documented)
                self.assertIn("--only REVENUE_PARTNER_REVIEW_ATTESTATIONS", documented)
                self.assertIn("--only REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY", documented)
                self.assertIn("--only REVENUE_PARTNER_NONCE_LEDGER", documented)
                self.assertIn("release_entry.py", documented)
                self.assertIn("-I -s -E", documented)
            connector_target = root / "connector.env"
            connector_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--target",
                    str(connector_target),
                    "--source",
                    str(source),
                    "--only",
                    "COMPOSIO_CONSUMER_KEY",
                ],
                text=True,
                capture_output=True,
                check=False,
                env={"PATH": os.environ["PATH"]},
            )
            self.assertEqual(connector_result.returncode, 2)
            self.assertIn("invalid choice", connector_result.stderr)
            self.assertFalse(connector_target.exists())


if __name__ == "__main__":
    unittest.main()
