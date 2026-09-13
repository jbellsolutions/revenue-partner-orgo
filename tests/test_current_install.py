from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMAGE = (
    "nousresearch/hermes-agent:v2026.8.27@"
    "sha256:e0df6adebddf29b91112aefc999d4aaf6846c9eb544faca5672a16a13590ff79"
)


class CurrentInstallTests(unittest.TestCase):
    def test_current_image_is_release_and_digest_pinned(self) -> None:
        for relative in ("deploy/compose.yml", "deploy/setup.sh", "deploy/update.sh"):
            text = (ROOT / relative).read_text()
            self.assertIn(IMAGE, text, relative)
            self.assertNotIn("hermes-agent:latest", text, relative)

    def test_slack_agent_manifest_is_complete(self) -> None:
        manifest = json.loads((ROOT / "slack-manifest.json").read_text())
        self.assertEqual("Revenue Partner", manifest["display_information"]["name"])
        self.assertIn("agent_view", manifest["features"])
        scopes = manifest["oauth_config"]["scopes"]["bot"]
        events = manifest["settings"]["event_subscriptions"]["bot_events"]
        self.assertIn("assistant:write", scopes)
        self.assertIn("app_context_changed", events)
        self.assertIn("app_home_opened", events)
        self.assertTrue(manifest["settings"]["socket_mode_enabled"])
        commands = {
            row["command"] for row in manifest["features"]["slash_commands"]
        }
        self.assertEqual(50, len(commands))
        for command in ("/hermes", "/btw", "/goal", "/reload-skills", "/approve", "/stop"):
            self.assertIn(command, commands)

    def test_beginner_guides_cover_security_and_skills(self) -> None:
        start = (ROOT / "START-HERE.md").read_text()
        slack = (ROOT / "docs/SLACK-SETUP.md").read_text()
        skills = (ROOT / "docs/SKILLS.md").read_text()
        tools = (ROOT / "docs/TOOLS.md").read_text()
        for required in ("orgo/setup.sh", "Slack Member ID", "real message"):
            self.assertIn(required, start)
        for required in ("xoxb-", "xapp-", "connections:write", "Agent view", "@Revenue Partner"):
            self.assertIn(required, slack)
        for required in ("Hermes Skills Hub", "skills audit", "!skills approval on", "revenue-partner"):
            self.assertIn(required, skills)
        for required in ("Composio Connect", "PandaDoc MCP", "read-only", "untrusted"):
            self.assertIn(required, tools)

    def test_orgo_startup_profile_has_current_runtime_tools_and_a2a(self) -> None:
        deployment = json.loads((ROOT / "orgo/deployment.json").read_text())
        self.assertEqual("system/hermes-agent@1.0.0", deployment["orgo_template_ref"])
        self.assertEqual("ai-guy-revenue-partner", deployment["computer_name"])
        self.assertEqual(8, deployment["hardware"]["ram_gb"])
        self.assertEqual(2, deployment["hardware"]["cpu"])
        setup = (ROOT / "orgo/setup.sh").read_text()
        for required in (
            "v2026.9.11",
            "939e45c91d751fadd94dcd1b873ac3cb44846213",
            'platform_toolsets.slack=["hermes-slack","a2a"]',
            'platform_toolsets.telegram=["hermes-telegram","a2a"]',
            "skills.write_approval=true",
            "approvals.mode=manual",
        ):
            self.assertIn(required, setup)
        a2a = (ROOT / "orgo/connect-a2a.sh").read_text()
        for required in ("A2A_PEER_TOKENS", "A2A_TRUSTED_PEERS", "tailscale ip -4"):
            self.assertIn(required, a2a)

    def test_agent_handoff_is_self_contained_and_source_grounded(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text()
        llms = (ROOT / "llms.txt").read_text()
        orgo_reference = (ROOT / "docs/ORGO-REFERENCE.md").read_text()
        for required in (
            "ai-guy-revenue-partner",
            "orgo/deployment.json",
            "./orgo/verify.sh",
            "Definition of done",
        ):
            self.assertIn(required, agents)
        for required in ("AI setup brief", "system/hermes-agent@1.0.0", "docs.orgo.ai/llms.txt"):
            self.assertIn(required, llms)
        for required in ("August 30, 2026", "POST /computers", "workspace-scoped"):
            self.assertIn(required, orgo_reference)

    def test_fresh_install_enables_full_tools_and_reviewed_skill_writes(self) -> None:
        setup = (ROOT / "deploy/setup.sh").read_text()
        for required in (
            'platform_toolsets.cli=["hermes-cli"]',
            'platform_toolsets.slack=["hermes-slack"]',
            'skills.write_approval=true',
            'skills.guard_agent_created=true',
            'compression.tail_mode=lean',
        ):
            self.assertIn(required, setup)
        self.assertIn('if [ "$FRESH_INSTALL" = true ]', setup)
        self.assertIn("Existing owner tool choices and approval settings were preserved", setup)

    def test_business_tool_helper_uses_secret_refs_and_untrusted_mcp(self) -> None:
        helper = (ROOT / "deploy/connect-tools.sh").read_text()
        for required in (
            "https://connect.composio.dev/mcp",
            "x-consumer-api-key",
            "${COMPOSIO_API_KEY}",
            "mcp_servers.composio.trust untrusted",
            "https://mcp.pandadoc.com/v1/mcp",
            "https://mcp.pandadoc.eu/v1/mcp",
            "mcp_servers.pandadoc.auth oauth",
            "mcp_servers.pandadoc.trust untrusted",
        ):
            self.assertIn(required, helper)
        self.assertNotIn("set -x", helper)

    def test_seed_sync_preserves_owner_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            subprocess.run(
                ["python3", str(ROOT / "deploy/sync_seed.py"), str(ROOT), str(data)],
                check=True,
                capture_output=True,
                text=True,
            )
            skill = data / "skills/go-to-market/revenue-partner/SKILL.md"
            original_hash = hashlib.sha256(skill.read_bytes()).hexdigest()
            self.assertEqual(
                hashlib.sha256(
                    (ROOT / "files/skills/go-to-market/revenue-partner/SKILL.md").read_bytes()
                ).hexdigest(),
                original_hash,
            )
            skill.write_text(skill.read_text() + "\nOwner customization.\n")
            subprocess.run(
                ["python3", str(ROOT / "deploy/sync_seed.py"), str(ROOT), str(data)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Owner customization.", skill.read_text())


if __name__ == "__main__":
    unittest.main()
