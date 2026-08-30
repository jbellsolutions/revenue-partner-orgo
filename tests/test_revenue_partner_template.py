from __future__ import annotations

import importlib.util
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import tomllib
import pathlib
import unittest
from unittest import mock
import urllib.error
import yaml

ROOT = Path(__file__).resolve().parents[1]
LEGACY_README = ROOT / "LEGACY-TEMPLATE.md"
FILES = ROOT / "files"
SKILL = FILES / "skills/go-to-market/revenue-partner/SKILL.md"
SB = FILES / "local-packages/super-browser"


def load_builder():
    spec = importlib.util.spec_from_file_location("revenue_partner_builder", ROOT / "build_template.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RevenuePartnerTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()

    def test_template_identity_is_revenue_partner(self):
        self.assertEqual(self.builder.NAME, "revenue-partner-agent")
        self.assertRegex(self.builder.VERSION, r"^\d+\.\d+\.\d+$")
        self.assertNotIn("Buzz", self.builder.template["template"]["name"])
        self.assertIn("Revenue Partner", self.builder.template["template"]["description"])

    def test_serialized_publication_request_stays_below_endpoint_limit(self):
        body = self.builder.publication_body_bytes()
        envelope = json.loads(body)
        self.assertEqual(envelope["namespace"], self.builder.NAMESPACE)
        self.assertEqual(envelope["name"], self.builder.NAME)
        self.assertEqual(envelope["version"], self.builder.VERSION)
        self.assertEqual(envelope["template"], self.builder.template)
        self.assertLess(len(body), self.builder.MAX_PUBLICATION_BODY_BYTES)
        artifact = self.builder.resolved_artifact_bytes()
        self.assertEqual(artifact, (json.dumps(self.builder.template, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertTrue(artifact.endswith(b"\n"))
        self.assertFalse(artifact.endswith(b"\n\n"))
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.object(self.builder, "HERE", directory),
                mock.patch.object(self.builder, "local_validate", return_value=True),
            ):
                self.builder.main([])
            generated = Path(directory) / f"{self.builder.NAME}.resolved.json"
            self.assertEqual(generated.read_bytes(), artifact)
        source = (ROOT / "build_template.py").read_text()
        self.assertIn("if not publication_body_within_limit():", source)
        self.assertIn('sys.exit("serialized publication request exceeds endpoint limit")', source)

    def test_public_inventory_matches_configured_mcp_servers_and_enabled_plugins(self):
        config = yaml.safe_load((FILES / "config.yaml").read_text())
        mcp_servers = config["mcp_servers"]
        enabled_mcp = sum(server.get("enabled", True) for server in mcp_servers.values())
        enabled_plugins = config["plugins"]["enabled"]
        self.assertEqual((len(mcp_servers), enabled_mcp, len(enabled_plugins)), (2, 2, 9))

        readme = LEGACY_README.read_text()
        app_description = self.builder.template["apps"][0]["description"]
        self.assertIn("2 hosted MCP servers (attached by URL)", readme)
        self.assertIn("MCP_configured-2_hosted", readme)
        self.assertIn("9 enabled model/telemetry plugins", readme)
        self.assertIn("2 configured/enabled MCP connections", app_description)

    def test_readme_badges_do_not_overstate_or_link_to_missing_targets(self):
        readme = LEGACY_README.read_text()
        # CI now runs and passes in the published repository, so the live badge
        # is accurate rather than an overstatement. The placeholder must be gone.
        self.assertIn("actions/workflows/ci.yml/badge.svg", readme)
        self.assertNotIn("CI-not_yet_run", readme)
        # Authenticated Orgo validation IS evidenced (HTTP 200 for the exact
        # tree, digests in VERIFICATION.md) -- but publication, image build and
        # launch are not. The badge must claim the first and not the rest.
        self.assertIn("schema_validated_not_published", readme)
        self.assertNotIn("local_schema_ok_not_live", readme)
        for overclaim in ("Orgo-published", "Orgo-live", "image_ready", "deployed"):
            self.assertNotIn(f"badge/{overclaim}", readme)
        # The Super Browser badge must not link to a nonexistent repository, and
        # must not point into the retired vendored tree either -- it now
        # describes a hosted service, so it links to the architecture doc.
        self.assertNotIn("github.com/jbellsolutions/super-browser)", readme)
        self.assertNotIn("files/local-packages/super-browser/", readme)
        self.assertIn("docs/ARCHITECTURE.md", readme)

    def test_release_evidence_matches_current_suites_and_remote_media_policy(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        verification = (ROOT / "docs/VERIFICATION.md").read_text()
        supply_chain = (ROOT / "docs/SUPPLY_CHAIN.md").read_text()
        self.assertIn("93/93 passed", changelog)
        self.assertIn("93/93 passed", verification)
        self.assertIn("7/7 passed", changelog)
        self.assertIn("7/7 passed", verification)
        self.assertIn("33 files; passed", verification)
        self.assertNotIn("54/54", changelog + verification)
        self.assertNotIn("53/53", changelog + verification)
        self.assertNotIn("33/33", changelog + verification)
        self.assertNotIn("31/31", changelog + verification)
        self.assertNotIn("49/49", changelog + verification)
        self.assertNotIn("48/48", changelog + verification)
        self.assertNotIn("42/42", changelog + verification)
        self.assertNotIn("40/40", changelog + verification)
        self.assertNotIn("37/37", changelog + verification)
        self.assertNotIn("39/39", changelog + verification)
        link_result = subprocess.run(
            [sys.executable, str(ROOT / ".github/scripts/check_markdown_links.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        resolved_count = int(link_result.stdout.strip().rsplit(" ", 1)[1])
        documented_match = re.search(
            r"Markdown/HTML local links and assets \| (\d+) resolved", verification
        )
        if documented_match is None:
            self.fail("verification evidence row for Markdown/HTML links is missing")
        self.assertEqual(int(documented_match.group(1)), resolved_count)
        shell_result = subprocess.run(
            [sys.executable, str(ROOT / ".github/scripts/check_shell_syntax.py")],
            cwd=ROOT,
            env={**os.environ, "REVENUE_PARTNER_VERIFY_GIT": "/usr/bin/git"},
            check=True,
            capture_output=True,
            text=True,
        )
        shell_count = int(shell_result.stdout.strip().rsplit(" ", 1)[1])
        shell_match = re.search(r"Shell syntax \| (\d+) passed", verification)
        if shell_match is None:
            self.fail("verification evidence row for shell syntax is missing")
        self.assertEqual(int(shell_match.group(1)), shell_count)
        self.assertIn("arbitrary remote attachment rejection", verification)
        self.assertNotIn("public-HTTPS", verification)
        current_size = len(self.builder.publication_body_bytes())
        self.assertLess(current_size, self.builder.MAX_PUBLICATION_BODY_BYTES)
        self.assertIn("exact post-freeze bytes belong in the release manifest", verification)
        self.assertIn("release manifest rather than this recursively packaged document", supply_chain)

    def test_required_product_files_exist(self):
        required = [
            SKILL,
            SKILL.parent / "references/operating-system.md",
            SKILL.parent / "references/campaign-contract.md",
            SKILL.parent / "references/source-ledger.md",
            SKILL.parent / "references/acceptance-tests.md",
            FILES / "agent-knowledge/INDEX.md",
            FILES / "agent-knowledge/01.Agent Operating System/02.Permissions.md",
            FILES / "agent-knowledge/02.GTM System/01.Company and Offer.md",
            FILES / "agent-knowledge/02.GTM System/02.ICP and Fit.md",
            FILES / "agent-knowledge/03.Campaigns/INDEX.md",
            FILES / "safe-env-bridge.py",
            FILES / "build-locks/hermes-runtime.lock",
            SB / "UPSTREAM_COMMIT",
            SB / "PACKAGE_METADATA.toml",
            SB / "src/super_browser/mcp_server.py",
            SB / ".codex-plugin/plugin.json",
            SB / ".mcp.json",
            SB / "scripts/verify-super-browser",
        ]
        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), str(path))

    def test_config_attaches_hosted_super_browser_by_url(self):
        """Super Browser is a hosted service attached by URL, never vendored.

        A local copy diverges from the server and, worse, dragged a second
        dependency lock into the agent's venv that silently rewrote six of its
        own pins. The config must carry a URL and bearer header and must not
        spawn a bundled stdio server.
        """
        config = (FILES / "config.yaml").read_text()
        self.assertIn("super-browser:", config)
        self.assertIn("url: ${SUPER_BROWSER_URL}/mcp", config)
        self.assertIn("Authorization: Bearer ${SUPER_BROWSER_TOKEN}", config)
        self.assertNotIn("/usr/local/bin/super-browser-server", config)
        self.assertNotIn("SUPER_BROWSER_STATE_DIR", config)
        self.assertNotIn("Buzz", config)
        parsed = yaml.safe_load(config)
        server = parsed["mcp_servers"]["super-browser"]
        self.assertNotIn("command", server)
        self.assertTrue(server["enabled"])

    def test_builder_does_not_vendor_super_browser_or_a_browser_runtime(self):
        """The image ships no second copy of Super Browser and no local browser.

        Both belong to the hosted service. Vendoring them is what installed a
        conflicting dependency lock into the agent venv; see
        RuntimeLockConsistencyTests and docs/VERIFICATION.md.
        """
        text = (ROOT / "build_template.py").read_text()
        for absent in (
            "local-packages/super-browser",
            "install_local_super_browser.sh",
            "super_browser.providers",
            "super_browser.mcp_server",
            "/usr/local/bin/super-browser-server",
            "SB_ROOT",
        ):
            self.assertNotIn(absent, text, absent)
        for archive in ("CHROMIUM", "HEADLESS", "FFMPEG"):
            self.assertNotIn(f"PLAYWRIGHT_{archive}_URL", text)
        self.assertNotIn("playwright install chromium", text)
        # The latitude plugin is still vendored and still installs under hashes.
        self.assertIn("--require-hashes", text)
        self.assertIn("latitude-telemetry-hermes", text)

    def test_no_local_super_browser_registration_surface_remains(self):
        """The vendored registration path is gone, not merely unused."""
        builder = (ROOT / "build_template.py").read_text()
        self.assertNotIn("install_local_super_browser.sh", builder)
        self.assertNotIn('pip install --python "$VENV_PY" --no-deps -e "$SB_ROOT"', builder)

    def test_build_dependency_sources_are_immutable_and_verified(self):
        text = (ROOT / "build_template.py").read_text()
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        telemetry_installer = FILES / "scripts/latitude/install_local_telemetry_patch.sh"
        self.assertTrue(telemetry_installer.is_file())
        telemetry_text = telemetry_installer.read_text()
        readme_text = LEGACY_README.read_text()
        self.assertIn("/root/.hermes/scripts/latitude/install_local_telemetry_patch.sh", text)
        self.assertNotIn("pip install", telemetry_text)
        self.assertNotIn("--no-build-isolation", telemetry_text)
        self.assertIn("latitude_telemetry_hermes.pth", telemetry_text)
        self.assertIn(".dist-info", telemetry_text)
        self.assertIn("entry_points.txt", telemetry_text)
        self.assertIn("hermes_agent.plugins", telemetry_text)
        self.assertNotIn("pip-installed", readme_text)
        self.assertNotIn("pip plugin", text)
        self.assertNotIn("pip-install the local package", text)
        verifier_text = (ROOT / ".github/scripts/verify_release.py").read_text()
        verify_command = "bash .github/scripts/verify_release"
        self.assertIn(f"run: {verify_command}", workflow)
        self.assertIn("check_shell_syntax.py", verifier_text)
        self.assertIn('"compileall"', verifier_text)
        self.assertIn('"--require-hashes"', verifier_text)
        self.assertIn('"requirements-ci.lock"', verifier_text)
        self.assertIn("scripts/verify-super-browser", verifier_text)
        self.assertIn('("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV")', verifier_text)
        self.assertIn('bootstrap_env["PYTHONNOUSERSITE"] = "1"', verifier_text)
        self.assertIn("verify_assembled_super_browser.py", verifier_text)
        self.assertTrue((ROOT / "template-schema.json").is_file())
        self.assertIn("619fbd1becd060a4c5c0de28c325f8e96b4f6cb456ef6c8f8cacdb0789932dd7", text)
        self.assertNotIn("/template-schema", text)
        self.assertNotIn('os.environ.get("VERSION"', text)
        self.assertNotIn('os.environ.get("ORGO_API_BASE"', text)
        locked_child_text = (ROOT / ".github/scripts/_verify_release_locked.py").read_text()
        self.assertTrue((ROOT / ".github/scripts/verify_assembled_super_browser.py").is_file())
        self.assertIn("check_candidate_yaml.py", verifier_text)
        self.assertIn("check_candidate_credentials.py", verifier_text)
        self.assertIn('files/local-packages/latitude-telemetry-hermes/tests", "-v"', verifier_text)
        self.assertIn('latitude_env["PYTHONPATH"]', verifier_text)
        self.assertIn('"-I", "-s"', verifier_text)
        self.assertIn("pass_fds=(read_fd,)", verifier_text)
        self.assertIn("os.pipe()", verifier_text)
        self.assertNotIn("VERIFY_TOKEN", verifier_text + locked_child_text)
        self.assertNotIn("VERIFY_SENTINEL", verifier_text + locked_child_text)
        self.assertNotIn("running_in_locked_environment", verifier_text)
        self.assertIn('spec_from_file_location("revenue_partner_verify_release", VERIFIER)', locked_child_text)
        self.assertNotIn("sys.path", locked_child_text)
        self.assertNotIn("PYTHONPATH", locked_child_text)
        self.assertTrue((ROOT / ".github/scripts/_verify_release_locked.py").is_file())
        self.assertTrue((ROOT / ".github/scripts/check_candidate_credentials.py").is_file())
        self.assertTrue((ROOT / ".github/scripts/check_candidate_yaml.py").is_file())
        for rel in ("LEGACY-TEMPLATE.md", "CONTRIBUTING.md", "docs/DEPLOYMENT.md", "docs/VERIFICATION.md"):
            self.assertIn(verify_command, (ROOT / rel).read_text(), rel)
        self.assertTrue((ROOT / ".github/scripts/check_shell_syntax.py").is_file())
        self.assertNotIn("releases/latest", text)
        self.assertNotIn("install.sh | bash", text)
        self.assertNotIn("npm install -g", text)
        self.assertNotIn("npx -y", text)

        verifier_spec = importlib.util.spec_from_file_location(
            "release_verifier_under_test", ROOT / ".github/scripts/verify_release.py"
        )
        assert verifier_spec and verifier_spec.loader
        verifier_module = importlib.util.module_from_spec(verifier_spec)
        verifier_spec.loader.exec_module(verifier_module)
        with (
            mock.patch.dict(
                os.environ,
                {
                    "REVENUE_PARTNER_VERIFY_LOCKED_ENV": "1",
                    "REVENUE_PARTNER_VERIFY_INNER_TOKEN": "caller-chosen-token",
                    "REVENUE_PARTNER_VERIFY_INNER_PREFIX": "/tmp/caller-venv",
                    "REVENUE_PARTNER_VERIFY_INNER_SENTINEL": "/tmp/caller-sentinel",
                    "PYTHONPATH": "/tmp/hostile-pythonpath",
                },
                clear=False,
            ),
            mock.patch.object(verifier_module, "bootstrap_locked_environment", return_value=73) as bootstrap,
            mock.patch.object(sys, "argv", ["verify_release.py"]),
        ):
            self.assertEqual(verifier_module.main(), 2)
            bootstrap.assert_not_called()

        child = ROOT / ".github/scripts/_verify_release_locked.py"
        direct = subprocess.run([sys.executable, str(child)], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(direct.returncode, 0)
        self.assertNotIn("release_verification_ok", direct.stdout)
        with tempfile.TemporaryDirectory() as child_tmp:
            forged_env = os.environ.copy()
            forged_env.update(
                {
                    "REVENUE_PARTNER_VERIFY_AUTH_FD": "99",
                    "REVENUE_PARTNER_VERIFY_VENV": child_tmp,
                    "REVENUE_PARTNER_VERIFY_PARENT_PID": str(os.getpid()),
                }
            )
            forged = subprocess.run(
                [sys.executable, str(child)], cwd=ROOT, env=forged_env, capture_output=True, text=True
            )
            self.assertNotEqual(forged.returncode, 0)
            self.assertNotIn("release_verification_ok", forged.stdout)

        with tempfile.TemporaryDirectory() as verify_tmp:
            package_verify_env = {
                **os.environ,
                "PYTHONPYCACHEPREFIX": str(Path(verify_tmp) / "pycache"),
                "SUPER_BROWSER_VERIFY_TMP_DIR": str(Path(verify_tmp) / "state"),
            }
            package_verify = subprocess.run(
                ["bash", str(SB / "scripts/verify-super-browser")],
                env=package_verify_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(package_verify.returncode, 0, package_verify.stderr + package_verify.stdout)

        telemetry_package = FILES / "local-packages/latitude-telemetry-hermes"
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            venv = fixture / "venv"
            subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
            python = venv / "bin/python"
            core_loop = fixture / "conversation_loop.py"
            core_loop.write_text(
                "                            max_tokens=agent.max_tokens,\n"
                "                            started_at=api_start_time,\n"
            )
            installer_env = {
                **os.environ,
                "LATITUDE_TELEMETRY_VENV_PY": str(python),
                "LATITUDE_TELEMETRY_PACKAGE_DIR": str(telemetry_package),
                "LATITUDE_TELEMETRY_CORE_LOOP": str(core_loop),
                "LATITUDE_TELEMETRY_VALIDATE_SCRIPT": str(fixture / "absent-validator.py"),
            }
            subprocess.run(["bash", str(telemetry_installer)], env=installer_env, check=True)
            purelib = Path(
                subprocess.run(
                    [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
            dist_info = purelib / "latitude_telemetry_hermes-0.1.0+revenuepartner.1.dist-info"
            (dist_info / "STALE").write_text("must disappear")
            subprocess.run(["bash", str(telemetry_installer)], env=installer_env, check=True)
            self.assertFalse((dist_info / "STALE").exists())
            registration = subprocess.run(
                [
                    str(python),
                    "-c",
                    "import importlib.metadata as m,pathlib,latitude_telemetry_hermes as p; "
                    "assert m.version('latitude-telemetry-hermes') == '0.1.0+revenuepartner.1'; "
                    "eps=list(m.entry_points(group='hermes_agent.plugins', name='latitude')); "
                    "assert len(eps) == 1 and eps[0].load().__name__ == 'latitude_telemetry_hermes'; "
                    f"assert pathlib.Path(p.__file__).resolve().is_relative_to(pathlib.Path({str(telemetry_package)!r}).resolve()); "
                    "print('telemetry_registration_ok')",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("telemetry_registration_ok", registration.stdout)

        telemetry_policy = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json,os; from latitude_telemetry_hermes.config import _load_config; "
                "from latitude_telemetry_hermes.otlp import _encode_attrs; "
                "assert not _load_config()['allow_content']; "
                "os.environ['LATITUDE_HERMES_ALLOW_CONTENT']='true'; assert _load_config()['allow_content']; "
                "encoded=_encode_attrs({'payload:gated':{'api_key':'sk-abcdefghijklmnop','nested':['authorization: Bearer abcdefghijklmnop']},'summary':'safe'},True); "
                "raw=json.dumps(encoded); assert 'sk-abcdefghijklmnop' not in raw and 'abcdefghijklmnop' not in raw; "
                "assert '[REDACTED]' in raw; "
                "os.environ['LATITUDE_HERMES_NO_CONTENT']='true'; assert not _load_config()['allow_content']; "
                "assert not any(i['key']=='payload' for i in _encode_attrs({'payload:gated':'secret'},False)); "
                "print('telemetry_content_policy_ok')",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(telemetry_package),
                "LATITUDE_API_KEY": "test-only",
                "LATITUDE_PROJECT": "test-only",
                "LATITUDE_HERMES_ALLOW_CONTENT": "",
                "LATITUDE_ALLOW_CONTENT": "",
                "LATITUDE_HERMES_NO_CONTENT": "",
                "LATITUDE_NO_CONTENT": "",
            },
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("telemetry_content_policy_ok", telemetry_policy.stdout)

        agent_facing = []
        for path in SB.rglob("*"):
            if not path.is_file() or path.name == "LOCAL_PATCHES.md":
                continue
            if path.suffix not in {".html", ".md", ".py", ".sh", ".yaml", ".yml", ".json"}:
                continue
            agent_facing.append(path.read_text(errors="ignore"))
        agent_text = "\n".join(agent_facing)
        self.assertIsNone(re.search(r"(?:^|[`\s])(?:python3?\s+-m\s+)?pip\s+install\b", agent_text))
        self.assertNotIn("npx -y", agent_text)
        self.assertIsNone(re.search(r"(?:^|[`\s])uvx\s+", agent_text))
        self.assertNotIn("source .env", agent_text)
        self.assertNotIn("releases/latest", agent_text)
        self.assertNotIn("scripts/sb.mjs", agent_text)
        self.assertNotIn("SUPER_BROWSER_URL", agent_text)
        self.assertNotIn("git clone https://github.com/jbellsolutions/super-browser", agent_text)
        self.assertIsNone(re.search(r"\bnpm\s+(?:i|install)\s+-g\b", agent_text))
        self.assertNotIn("playwright install chromium", agent_text)
        self.assertNotIn("python3 -m playwright install chromium", agent_text)
        self.assertNotIn("Use signup URLs", agent_text)
        self.assertNotIn("Provider signup links", agent_text)
        self.assertNotIn("Configure provider credentials", agent_text)
        self.assertNotIn("request exact missing setup", agent_text)
        self.assertNotIn("Actor execution requires operator-configured provider credentials", agent_text)
        self.assertNotIn("configured provider execution", agent_text)
        self.assertNotIn("form filling", agent_text)
        for stale_capability in (
            "scripts/talk_super_browser.py",
            "scripts/super_browser_server.py",
            "scripts/daily_browser_ops.py",
            "scripts/tool_watch.py",
            "scripts/post_to_leads.py",
            "fullenrich.py",
            "deep_lookup_enrich.py",
            "lead_pipeline.py",
            "apify_tools",
            "vault/super_browser/knowledge/providers/",
            "deploy/vps/super-browser-tool-watch",
            "SUPER_BROWSER_API_TOKEN",
            "/Users/home/Desktop/super-browser-extension",
            "super-browser profiles create",
            "references/live-test-matrix.md",
            "tools-35",
            "status-alive",
            "clone, install, API keys",
            "clone, pip, skills, MCP, doctor",
            "Proxy hint (decodo/auto/sticky or full proxy URL)",
            "scheduled GTM workflows",
            "AIRTOP_AGENT_ID",
            "AIRTOP_WEBHOOK_ID",
            "residential proxy routing",
            "Cheap residential proxy requests",
            "Geo-targeting and proxy rotation",
            'super-browser run --goal "Use a desktop computer',
            'super-browser run --goal "Search a protected public site',
            "| Browser Use | [browser-use.md](browser-use.md) | stable |",
            "| Orgo | [orgo.md](orgo.md) | stable |",
        ):
            self.assertNotIn(stale_capability, agent_text)
        mcp_text = (SB / "src/super_browser/mcp_server.py").read_text()
        self.assertIn(
            '"resume_browser_run": "Resume an eligible read-only run; approval-required and blocked runs remain non-executable in this image."',
            mcp_text,
        )
        self.assertIn(
            '"setup_walkthrough": "Return baked-runtime verification, provider readiness, and read-only fixture steps without mutating the image."',
            mcp_text,
        )
        self.assertNotIn("already approved provider action", mcp_text)
        self.assertNotIn("install-skill/init-MCP", mcp_text)
        self.assertIn('"enum": ["local", "fixtures"]', mcp_text)
        self.assertIn("hosted provider live tests are unavailable in this image", mcp_text)
        self.assertNotIn('"all", *PROVIDER_NAMES', mcp_text)
        package_metadata = tomllib.loads((SB / "PACKAGE_METADATA.toml").read_text())
        plugin_metadata = json.loads((SB / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(package_metadata["version"], plugin_metadata["version"])
        self.assertIn('"version": SERVER_VERSION', mcp_text)
        for marker in (
            "hermes-runtime.lock",
            "--require-hashes",
            "OP_CLI_SHA",
            "NODE_SHA",
        ):
            self.assertIn(marker, text)

        hermes_lock = (FILES / "build-locks/hermes-runtime.lock").read_text()
        for requirement in ("hermes-agent==0.18.0", "qrcode==8.2", "uv==0.12.4"):
            self.assertIn(requirement, hermes_lock)
        self.assertIn("--hash=sha256:", hermes_lock)

        self.assertFalse((FILES / "npm-build/package.json").exists())
        self.assertFalse((FILES / "npm-build/package-lock.json").exists())

    def test_candidate_credential_scan_reads_index_blobs_not_worktree_bytes(self):
        scanner = ROOT / ".github/scripts/check_candidate_credentials.py"
        yaml_scanner = ROOT / ".github/scripts/check_candidate_yaml.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            bridge = repo / "files/safe-env-bridge.py"
            bridge.parent.mkdir(parents=True)
            bridge.write_text(
                "MANAGED_KEYS = (\n"
                "    'OP_SERVICE_ACCOUNT_TOKEN', 'AI_GATEWAY_API_KEY', 'MODEL_API_KEY',\n"
                "    'OPENROUTER_API_KEY', 'XAI_API_KEY', 'COMPOSIO_CONSUMER_KEY', 'AGENTMAIL_API_KEY',\n"
                ")\n"
            )
            subprocess.run(["git", "add", "files/safe-env-bridge.py"], cwd=repo, check=True)
            secret = "gh" + "p_" + ("A" * 32)
            target = repo / "candidate.txt"
            target.write_text(secret)
            subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)
            target.write_text("safe working tree bytes\n")
            result = subprocess.run(
                [sys.executable, str(scanner), "--root", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("candidate.txt: github_token", result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
            subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)
            clean = subprocess.run(
                [sys.executable, str(scanner), "--root", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)

            for index, env_name in enumerate(
                (
                    "OP_SERVICE_ACCOUNT_TOKEN",
                    "AI_GATEWAY_API_KEY",
                    "MODEL_API_KEY",
                    "OPENROUTER_API_KEY",
                    "XAI_API_KEY",
                    "COMPOSIO_CONSUMER_KEY",
                    "AGENTMAIL_API_KEY",
                )
            ):
                supplied = f"exact-supplied-secret-family-{index}-value"
                target.write_text(supplied)
                subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)
                env = os.environ.copy()
                env[env_name] = supplied
                family = subprocess.run(
                    [sys.executable, str(scanner), "--root", str(repo)],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(family.returncode, 1, env_name + family.stdout + family.stderr)
                self.assertIn("candidate.txt: supplied_secret_value", family.stderr)
                self.assertNotIn(supplied, family.stdout + family.stderr)
            target.write_text("safe working tree bytes\n")
            subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)

            accepted_names = (
                "ORGO_API_KEY",
                "LATITUDE_API_KEY",
                "OP_SERVICE_ACCOUNT_TOKEN",
                "AI_GATEWAY_API_KEY",
                "MODEL_API_KEY",
                "OPENROUTER_API_KEY",
                "XAI_API_KEY",
                "COMPOSIO_CONSUMER_KEY",
                "AGENTMAIL_API_KEY",
            )
            for index, env_name in enumerate(accepted_names):
                target.write_text(f"{env_name}=production-secret-family-{index}-value-123456789\n")
                subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)
                assignment = subprocess.run(
                    [sys.executable, str(scanner), "--root", str(repo)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(assignment.returncode, 1, env_name + assignment.stdout + assignment.stderr)
                self.assertIn(f"candidate.txt: non_placeholder_assignment:{env_name}", assignment.stderr)
                self.assertNotIn("production-secret-family", assignment.stdout + assignment.stderr)
            target.write_text("ORGO_API_KEY=${ORGO_API_KEY}\nLATITUDE_API_KEY=[REDACTED]\n")
            subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)
            placeholders = subprocess.run(
                [sys.executable, str(scanner), "--root", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(placeholders.returncode, 0, placeholders.stdout + placeholders.stderr)
            target.write_text("safe working tree bytes\n")
            subprocess.run(["git", "add", "candidate.txt"], cwd=repo, check=True)

            manifest = repo / "manifest.yaml"
            manifest.write_text("broken: [\n")
            subprocess.run(["git", "add", "manifest.yaml"], cwd=repo, check=True)
            manifest.write_text("safe: true\n")
            malformed = subprocess.run(
                [sys.executable, str(yaml_scanner), "--root", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(malformed.returncode, 1, malformed.stdout + malformed.stderr)
            self.assertIn("manifest.yaml: ParserError", malformed.stderr)
            subprocess.run(["git", "add", "manifest.yaml"], cwd=repo, check=True)
            valid = subprocess.run(
                [sys.executable, str(yaml_scanner), "--root", str(repo)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)

        with tempfile.TemporaryDirectory() as fake_bin_dir:
            fake_git = Path(fake_bin_dir) / "git"
            fake_git.write_text("#!/bin/sh\nprintf 'fake git must not run\\n' >&2\nexit 0\n")
            fake_git.chmod(0o755)
            trusted_env = os.environ.copy()
            trusted_env["PATH"] = f"{fake_bin_dir}:{trusted_env.get('PATH', '')}"
            trusted_env["REVENUE_PARTNER_VERIFY_GIT"] = "/usr/bin/git"
            expected_inventory = {
                scanner: "candidate_credentials_ok 197",
                yaml_scanner: "candidate_yaml_ok 4",
                ROOT / ".github/scripts/check_skill_frontmatter.py": "candidate_skill_frontmatter_ok 17",
                ROOT / ".github/scripts/check_shell_syntax.py": "shell_syntax_ok 24",
            }
            for checker, expected in expected_inventory.items():
                result = subprocess.run(
                    [sys.executable, str(checker)],
                    cwd=ROOT,
                    env=trusted_env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)
                self.assertNotIn("fake git must not run", result.stdout + result.stderr)
            untrusted_env = trusted_env.copy()
            untrusted_env["REVENUE_PARTNER_VERIFY_GIT"] = "git"
            rejected = subprocess.run(
                [sys.executable, str(scanner)],
                cwd=ROOT,
                env=untrusted_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("trusted absolute Git executable unavailable", rejected.stderr)

    def test_runtime_contains_no_model_callable_filesystem_or_writable_connector_mcp(self):
        config = (FILES / "config.yaml").read_text()
        self.assertNotIn("mcp-server-filesystem", config + self.builder.INSTALL)
        self.assertNotIn("obsidian-vault:", config)
        self.assertNotIn("api.latitude.so/v1/mcp", config)
        security_model = (ROOT / "docs/SECURITY_MODEL.md").read_text()
        self.assertNotIn("disabled by default", security_model)
        self.assertNotIn("when deliberately enabled", security_model)
        public_docs = "\n".join(
            (ROOT / rel).read_text()
            for rel in ("LEGACY-TEMPLATE.md", "docs/VERIFICATION.md")
        )
        self.assertNotIn("exact-loopback fixture execution", public_docs)
        self.assertNotIn("build-time Playwright verification", public_docs)
        self.assertIn("real browser launch remains an image-build live-smoke gate", public_docs)
        self.assertIn("real Chromium fixture execution remains an image-build live-smoke gate", public_docs)
        self.assertNotIn("/usr/local/bin/orgo-mcp", config + self.builder.INSTALL)
        self.assertNotIn("/usr/local/bin/agentphone-mcp", config + self.builder.INSTALL)
        self.assertNotIn("/usr/local/bin/xurl", config + self.builder.INSTALL)
        self.assertNotIn("cloudflared", self.builder.INSTALL)
        self.assertNotIn("github:nickvasilescu/orgo-mcp", config)
        self.assertNotIn("command: npx", config)

    def test_resume_hook_never_sources_or_raw_echoes_secrets(self):
        hook = self.builder.ON_RESUME
        self.assertIn("revenue-partner-env-bridge", hook)
        self.assertNotIn(". /root/.env", hook)
        self.assertNotIn(". /root/.hermes/.env", hook)
        self.assertNotIn('echo "${K}=${V}"', hook)

    def test_gateway_execs_through_safe_environment_bridge(self):
        gateway = (FILES / "gateway-run.sh").read_text()
        self.assertIn("revenue-partner-env-bridge --exec", gateway)
        self.assertNotIn(". /root/.env", gateway)
        self.assertNotIn('. "$HERMES_HOME/.env"', gateway)

    def test_unavailable_local_validation_fails_closed(self):
        with mock.patch.dict(sys.modules, {"jsonschema": None}):
            self.assertFalse(self.builder.local_validate())
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / "template-schema.json"
            tampered.write_text('{"type":"object"}')
            with mock.patch.object(self.builder, "TEMPLATE_SCHEMA_PATH", str(tampered)):
                self.assertFalse(self.builder.local_validate())
        with (
            mock.patch.object(self.builder, "API_BASE", "https://attacker.invalid/api"),
            mock.patch.object(self.builder, "_broker_exchange", side_effect=AssertionError("broker used")),
        ):
            self.assertTrue(self.builder.local_validate())

    def test_default_ci_invocation_fails_when_local_schema_validation_is_unavailable(self):
        with (
            mock.patch.object(self.builder, "local_validate", return_value=False),
            mock.patch.object(sys, "argv", ["build_template.py"]),
        ):
            with self.assertRaises(SystemExit) as stopped:
                self.builder.main()
        self.assertIn("local schema validation failed", str(stopped.exception))

    def test_publish_requires_successful_local_or_remote_validation(self):
        with (
            mock.patch.object(self.builder, "local_validate", return_value=False),
            mock.patch.object(self.builder, "remote_validate", return_value=False),
            mock.patch.object(self.builder, "publish") as publish,
            mock.patch.object(self.builder, "require_release_clearance", return_value=object()),
            mock.patch.object(sys, "argv", ["build_template.py", "--publish"]),
        ):
            with self.assertRaises(SystemExit):
                self.builder.main()
            publish.assert_not_called()

        with (
            mock.patch.object(self.builder, "local_validate", return_value=True),
            mock.patch.object(self.builder, "publish") as publish,
            mock.patch.dict(os.environ, {self.builder.REVIEW_ATTESTATIONS_ENV: ""}),
            mock.patch.object(sys, "argv", ["build_template.py", "--publish"]),
        ):
            with self.assertRaises(SystemExit) as stopped:
                self.builder.main()
            self.assertIn("two signed exact-tree CLEAR reviews", str(stopped.exception))
            publish.assert_not_called()

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            resolved = directory_path / "revenue-partner-agent.resolved.json"
            resolved.write_text(json.dumps(self.builder.template, indent=2))
            allowed_signers = directory_path / "reviewers.allowed_signers"
            key_paths = {}
            allowed_lines = []
            for reviewer_id in ("documentation", "security", "release-operator"):
                key = directory_path / reviewer_id
                subprocess.run(
                    [self.builder.SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", reviewer_id, "-f", str(key)],
                    check=True,
                )
                key_paths[reviewer_id] = key
                public_parts = key.with_suffix(".pub").read_text().split()
                allowed_lines.append(f"{reviewer_id} {public_parts[0]} {public_parts[1]}\n")
            allowed_signers.write_text("".join(allowed_lines))
            tree = subprocess.check_output([self.builder.GIT, "write-tree"], cwd=ROOT, text=True).strip()
            expected = {
                "tree": tree,
                "artifact_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
                "publication_sha256": hashlib.sha256(self.builder.publication_body_bytes()).hexdigest(),
            }
            reviews = []
            for reviewer_id in ("documentation", "security"):
                statement = {**expected, "reviewer_id": reviewer_id, "verdict": "CLEAR"}
                signature = directory_path / f"{reviewer_id}.sig"
                signed = subprocess.run(
                    [self.builder.SSH_KEYGEN, "-Y", "sign", "-f", str(key_paths[reviewer_id]),
                     "-n", self.builder.REVIEW_SIGNATURE_NAMESPACE],
                    input=self.builder._review_statement_bytes(statement),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                signature.write_bytes(signed.stdout)
                signature.chmod(0o600)
                reviews.append({"reviewer_id": reviewer_id, "statement": statement, "signature_path": str(signature)})
            record = {**expected, "reviews": reviews}
            attestation = directory_path / "attestation.json"
            attestation.write_text(json.dumps(record))
            attestation.chmod(0o600)
            with (
                mock.patch.dict(os.environ, {self.builder.REVIEW_ATTESTATIONS_ENV: str(attestation)}),
                mock.patch.object(self.builder, "_trusted_review_allowlist", return_value=str(allowed_signers)),
            ):
                capability = self.builder.require_release_clearance(resolved, operation="publish")
                approved_bytes = capability.body
                original_name = self.builder.template["template"]["name"]
                self.builder.template["template"]["name"] = "post-clearance mutation"
                try:
                    self.assertEqual(capability.body, approved_bytes)
                    self.assertNotEqual(capability.body, self.builder.publication_body_bytes())
                    method, url, body = capability.consume("publish")
                    self.assertEqual((method, url, body), ("POST", f"{self.builder.API_BASE}/templates", approved_bytes))
                    with self.assertRaisesRegex(RuntimeError, "already been consumed"):
                        capability.consume("publish")
                finally:
                    self.builder.template["template"]["name"] = original_name

                publication_receipt = self.builder._PublicationReceipt(
                    f"{self.builder.NAMESPACE}/{self.builder.NAME}@{self.builder.VERSION}",
                    expected["publication_sha256"], "2026-08-19T00:00:00Z", {},
                )
                event_url = f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build/events"
                nonce = "ab" * 32
                with (
                    mock.patch.object(self.builder, "HERE", str(directory_path)),
                    mock.patch.object(self.builder, "_assert_exact_assembled_tree", return_value=tree),
                ):
                    event_statement = self.builder._operation_intent_statement(
                        "events", "GET", event_url, None, publication_receipt, nonce
                    )
                event_signature = directory_path / "event.sig"
                signed_event = subprocess.run(
                    [self.builder.SSH_KEYGEN, "-Y", "sign", "-f", str(key_paths["release-operator"]),
                     "-n", self.builder.OPERATION_SIGNATURE_NAMESPACE],
                    input=self.builder._review_statement_bytes(event_statement),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
                )
                event_signature.write_bytes(signed_event.stdout)
                event_signature.chmod(0o600)
                event_intent = directory_path / "event-intent.json"
                event_intent.write_text(json.dumps({
                    "statement": event_statement,
                    "signature_path": str(event_signature),
                }))
                event_intent.chmod(0o600)
                ledger = directory_path / "nonce-ledger"
                ledger.mkdir(mode=0o700)
                broker_spec = importlib.util.spec_from_file_location(
                    "orgo_release_broker_intent_test", ROOT / ".github/scripts/orgo_release_broker.py"
                )
                assert broker_spec and broker_spec.loader
                broker = importlib.util.module_from_spec(broker_spec)
                broker_spec.loader.exec_module(broker)
                broker_request = {
                    "operation": "events",
                    "method": "GET",
                    "url": event_url,
                    "body": None,
                    "publication_digest": publication_receipt.digest,
                    "intent_path": str(event_intent),
                }
                with (
                    mock.patch.object(broker, "nonce_ledger", return_value=ledger),
                    mock.patch.object(broker, "trust_policy", return_value=str(allowed_signers)),
                ):
                    self.assertIsNone(
                        broker.consume_intent(
                            broker_request,
                            tree,
                            expected["artifact_sha256"],
                            expected["publication_sha256"],
                        )
                    )
                    with self.assertRaisesRegex(RuntimeError, "already consumed"):
                        broker.consume_intent(
                            broker_request,
                            tree,
                            expected["artifact_sha256"],
                            expected["publication_sha256"],
                        )

                forged = json.loads(json.dumps(record))
                forged["reviews"][1]["statement"]["verdict"] = "CLEAR "
                attestation.write_text(json.dumps(forged))
                attestation.chmod(0o600)
                with self.assertRaisesRegex(RuntimeError, "does not exactly bind CLEAR"):
                    self.builder.require_release_clearance(resolved, operation="publish")

        with (
            mock.patch.object(self.builder, "local_validate", return_value=True),
            mock.patch.object(self.builder, "require_release_clearance") as clearance,
            mock.patch.object(self.builder, "publish", return_value=True) as publish,
            mock.patch.object(sys, "argv", ["build_template.py", "--publish"]),
        ):
            self.builder.main()
            clearance.assert_called_once()
            publish.assert_called_once()

    def test_release_assembly_excludes_untracked_payloads_and_uses_trusted_git(self):
        self.assertEqual(self.builder.GIT, "/usr/bin/git")
        baseline_payload = self.builder.payload_b64()
        probe = FILES / "agent-knowledge/untracked-review-bypass.md"
        try:
            probe.write_text("unreviewed instructions\n")
            self.assertEqual(self.builder.payload_b64(), baseline_payload)
            with self.assertRaisesRegex(RuntimeError, "untracked files"):
                self.builder._assert_exact_assembled_tree()
        finally:
            probe.unlink(missing_ok=True)

        with tempfile.TemporaryDirectory() as directory:
            fake_git = Path(directory) / "git"
            fake_git.write_text("#!/bin/sh\nprintf '%s\\n' forged-tree\n")
            fake_git.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": f"{directory}:{os.environ.get('PATH', '')}"}):
                self.assertEqual(
                    self.builder._git_text("write-tree"),
                    subprocess.check_output(["/usr/bin/git", "write-tree"], cwd=ROOT, text=True).strip(),
                )

    def test_http_failures_are_not_reported_as_success(self):
        self.assertEqual(self.builder.API_BASE, "https://www.orgo.ai/api")
        self.assertEqual(self.builder.VERSION, "1.0.1")
        self.assertFalse(hasattr(self.builder, "_ORGO_OPENER"))
        self.assertFalse(hasattr(self.builder, "_orgo_api_key"))
        entry_source = (ROOT / "release_entry.py").read_text()
        broker_source = (ROOT / ".github/scripts/orgo_release_broker.py").read_text()
        self.assertIn("authenticated release entry requires trusted Python -I -s -E", entry_source)
        self.assertIn("authenticated broker requires trusted Python -I -s -E", broker_source)
        self.assertIn("os.fork()", entry_source)
        self.assertIn('builder_env.pop("ORGO_API_KEY", None)', entry_source)
        self.assertNotIn("def _orgo_api_key", broker_source)
        self.assertNotIn("_ORGO_OPENER", broker_source)
        nonisolated = subprocess.run(
            [sys.executable, "release_entry.py", "--remote-validate"],
            cwd=ROOT,
            env={**os.environ, "ORGO_API_KEY": "sentinel-not-used"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertNotEqual(nonisolated.returncode, 0)
        self.assertIn("requires trusted Python -I -s -E", nonisolated.stdout)
        with mock.patch.dict(os.environ, {
            "ORGO_API_KEY": "sentinel",
            "REVENUE_PARTNER_BROKER_FD": "7",
        }, clear=False):
            broker_spec = importlib.util.spec_from_file_location(
                "orgo_release_broker_environment_test", ROOT / ".github/scripts/orgo_release_broker.py"
            )
            assert broker_spec and broker_spec.loader
            broker_module = importlib.util.module_from_spec(broker_spec)
            broker_spec.loader.exec_module(broker_module)
            sanitized = broker_module.keyless_subprocess_environment()
            self.assertNotIn("ORGO_API_KEY", sanitized)
            self.assertNotIn("REVENUE_PARTNER_BROKER_FD", sanitized)
        self.assertLess(
            broker_source.index("consume_intent(request"),
            broker_source.index('key = os.environ.get("ORGO_API_KEY"'),
        )
        self.assertIn("broker_key_sha256", broker_source)
        self.assertIn("hmac.new(broker_secret()", broker_source)
        self.assertIn("validate_response_semantics", broker_source)
        self.assertIn("REVENUE_PARTNER_NONCE_LEDGER", broker_source)
        self.assertIn("issued_at", broker_source)
        self.assertIn("expires_at", broker_source)
        self.assertIn("read1(", broker_source)
        self.assertIn("absolute deadline", broker_source)
        for target in (
            "http://www.orgo.ai/api/templates",
            "https://attacker.invalid/api/templates",
            "https://user:pass@www.orgo.ai/api/templates",
            "https://www.orgo.ai.evil/api/templates",
            "https://www.orgo.ai/other",
        ):
            with self.assertRaises(ValueError, msg=target):
                self.builder._validate_orgo_url(target)
        self.assertFalse(hasattr(self.builder, "_req"))
        self.assertFalse(hasattr(self.builder, "_APPROVAL_SEAL"))
        self.assertFalse(hasattr(self.builder, "_approved_request_for"))
        with self.assertRaisesRegex(RuntimeError, "release capability required"):
            self.builder._send_approved(None, "publish")
        direct_request = self.builder._ApprovedRequest(
            "publish", "POST", f"{self.builder.API_BASE}/templates", self.builder.publication_body_bytes()
        )
        with mock.patch.dict(os.environ, {self.builder.REVIEW_ATTESTATIONS_ENV: ""}, clear=False):
            with mock.patch.object(self.builder, "_broker_exchange") as broker_exchange:
                with self.assertRaisesRegex(RuntimeError, "REVENUE_PARTNER_REVIEW_ATTESTATIONS"):
                    self.builder._send_approved(direct_request, "publish")
                broker_exchange.assert_not_called()
        replay_request = self.builder._ApprovedRequest(
            "publish", "POST", f"{self.builder.API_BASE}/templates", self.builder.publication_body_bytes()
        )
        with (
            mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40),
            mock.patch.object(
                self.builder, "_await_signed_operation_intent",
                side_effect=RuntimeError("externally signed operation intent required"),
            ) as signed_intent,
            mock.patch.object(self.builder, "_broker_exchange") as broker_exchange,
        ):
            with self.assertRaisesRegex(RuntimeError, "externally signed operation intent"):
                self.builder._send_approved(replay_request, "publish")
            replay_request._used = False
            with self.assertRaisesRegex(RuntimeError, "externally signed operation intent"):
                self.builder._send_approved(replay_request, "publish")
            self.assertEqual(signed_intent.call_count, 2)
            broker_exchange.assert_not_called()
        with mock.patch.object(self.builder, "_broker_exchange") as broker_exchange:
            self.assertFalse(self.builder.remote_validate(None))
            broker_exchange.assert_not_called()
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, "{}")):
            self.assertFalse(self.builder.remote_validate(object()))
        validation_body = json.dumps({
            "ok": True,
            "template": self.builder.template,
        })
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, validation_body)):
            self.assertTrue(self.builder.remote_validate(object()))
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, json.dumps({"ok": True, "template": {"api_version": "orgo.ai/v1", "template": {"name": "wrong", "version": "9.9.9"}}}))):
            self.assertFalse(self.builder.remote_validate(object()))
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, json.dumps({"ok": False, "errors": []}))):
            self.assertFalse(self.builder.remote_validate(object()))
        with mock.patch.object(self.builder, "_send_approved", return_value=(409, "collision")):
            self.assertFalse(self.builder.publish(object()))
        with mock.patch.object(self.builder, "_send_approved", return_value=(500, "failed")):
            self.assertFalse(self.builder.build_and_stream(object(), None))

        expected_ref = f"{self.builder.NAMESPACE}/{self.builder.NAME}@{self.builder.VERSION}"
        expected_digest = hashlib.sha256(self.builder.publication_body_bytes()).hexdigest()
        valid_publication = json.dumps(
            {"ref": expected_ref, "digest": expected_digest, "published": "2026-08-19T00:00:00Z"}
        )
        receipt = self.builder._publication_receipt_from_response(200, valid_publication)
        self.assertTrue(self.builder._valid_publication_receipt(receipt))
        for body in (
            "{}",
            "[]",
            json.dumps({"ref": "default/wrong@1.0.0", "digest": expected_digest, "published": "2026-08-19T00:00:00Z"}),
            json.dumps({"ref": expected_ref, "digest": expected_digest}),
            json.dumps({"ref": expected_ref, "digest": "0" * 64, "published": "2026-08-19T00:00:00Z"}),
            json.dumps({"ref": expected_ref, "digest": expected_digest, "published": ""}),
        ):
            self.assertIsNone(self.builder._publication_receipt_from_response(200, body), body)

        class BodyResponse:
            def __init__(self, body, declared=None, status=200):
                self.body = body
                self.offset = 0
                self.headers = {} if declared is None else {"Content-Length": str(declared)}
                self.status = status

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, size):
                part = self.body[self.offset:self.offset + size]
                self.offset += len(part)
                return part

        with mock.patch.dict(os.environ, {self.builder.REVIEW_ATTESTATIONS_ENV: ""}, clear=False):
            with mock.patch.object(self.builder, "_broker_exchange") as broker_exchange:
                with self.assertRaisesRegex(RuntimeError, "REVENUE_PARTNER_REVIEW_ATTESTATIONS"):
                    self.builder._verify_remote_publication_receipt(receipt)
                broker_exchange.assert_not_called()
        mismatched_readback = json.dumps(
            {"ref": expected_ref, "digest": "0" * 64, "published": "2026-08-19T00:00:00Z"}
        ).encode()
        with (
            mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40),
            mock.patch.dict(os.environ, {self.builder.OPERATION_INTENT_DIRECTORY_ENV: ""}, clear=False),
            mock.patch.object(self.builder, "_broker_exchange") as broker_exchange,
        ):
            with self.assertRaisesRegex(RuntimeError, "externally signed operation intent"):
                self.builder._verify_remote_publication_receipt(receipt)
            broker_exchange.assert_not_called()
        with (
            mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40),
            mock.patch.object(self.builder, "_await_signed_operation_intent", return_value="/intent"),
            mock.patch.object(self.builder, "_broker_exchange", return_value=(200, mismatched_readback)),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not match reference and signed digest"):
                self.builder._verify_remote_publication_receipt(receipt)
        with (
            mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40),
            mock.patch.object(self.builder, "_await_signed_operation_intent", return_value="/intent"),
            mock.patch.object(
                self.builder, "_broker_exchange", return_value=(200, valid_publication.encode())
            ) as broker_exchange,
        ):
            readback = self.builder._verify_remote_publication_receipt(receipt)
            self.assertEqual(readback.digest, expected_digest)
            requested = broker_exchange.call_args.args
            self.assertEqual(requested[:4], (
                "readback", "GET",
                f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}",
                None,
            ))
        with mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40):
            build_request = self.builder.require_release_clearance(
                ROOT / f"{self.builder.NAME}.resolved.json",
                operation="build",
                publication_receipt=receipt,
            )
        self.assertEqual(
            build_request.url,
            f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build",
        )

        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            self.builder._read_bounded_response(
                BodyResponse(b"", self.builder.MAX_ORGO_RESPONSE_BYTES + 1)
            )
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            self.builder._read_bounded_response(
                BodyResponse(b"x" * (self.builder.MAX_ORGO_RESPONSE_BYTES + 1))
            )

        api_base = self.builder.API_BASE

        class TrackingHTTPError(urllib.error.HTTPError):
            def __init__(self, body, declared=None):
                headers = {} if declared is None else {"Content-Length": str(declared)}
                super().__init__(f"{api_base}/templates", 400, "bad request", headers, io.BytesIO(body))
                self.was_closed = False

            def close(self):
                self.was_closed = True
                super().close()

        ordinary_error = TrackingHTTPError(b"ordinary failure")
        self.assertEqual(self.builder._read_bounded_http_error(ordinary_error), "ordinary failure")
        self.assertTrue(ordinary_error.was_closed)
        declared_error = TrackingHTTPError(b"", self.builder.MAX_ORGO_RESPONSE_BYTES + 1)
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            self.builder._read_bounded_http_error(declared_error)
        self.assertTrue(declared_error.was_closed)
        streamed_error = TrackingHTTPError(b"x" * (self.builder.MAX_ORGO_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            self.builder._read_bounded_http_error(streamed_error)
        self.assertTrue(streamed_error.was_closed)
        parser_error = TrackingHTTPError(b"not-json")
        parser_capability = self.builder._ApprovedRequest(
            "publish", "POST", f"{self.builder.API_BASE}/templates", self.builder.publication_body_bytes()
        )
        with (
            mock.patch.object(self.builder, "_verify_release_clearance", return_value="a" * 40),
            mock.patch.object(self.builder, "_await_signed_operation_intent", return_value="/intent"),
            mock.patch.object(self.builder, "_broker_exchange", return_value=(400, b"not-json")),
        ):
            self.assertIsNone(self.builder.publish(parser_capability))

        class EventResponse:
            def __init__(self, lines):
                self.lines = iter(lines)

            def readline(self, size):
                del size
                return next(self.lines, b"")

        generic_ready_line = b'data: {"phase":"ready","level":"success"}\n'
        valid_build_response = json.dumps(
            {"ref": expected_ref, "digest": expected_digest, "status": "building"}
        )
        build_receipt = self.builder._build_receipt_from_response(200, valid_build_response, receipt)
        self.assertIsNotNone(build_receipt)
        self.assertIsNone(self.builder._build_receipt_from_response(200, "{}", receipt))
        self.assertIsNone(
            self.builder._build_receipt_from_response(
                200,
                json.dumps({"ref": "default/wrong@1.0.0", "digest": expected_digest, "status": "building"}),
                receipt,
            )
        )
        self.assertIsNone(
            self.builder._build_receipt_from_response(
                200,
                json.dumps({"ref": expected_ref, "digest": expected_digest, "status": "failed"}),
                receipt,
            )
        )
        build_capability = self.builder._ApprovedRequest(
            "build",
            "POST",
            f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build",
            None,
            receipt,
        )
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, "{}")):
            self.assertFalse(self.builder.build_and_stream(build_capability, receipt))
        with mock.patch.object(self.builder, "_broker_exchange") as broker_exchange:
            with self.assertRaisesRegex(RuntimeError, "signed one-use event capability"):
                self.builder._stream_build_events(None, receipt)
            broker_exchange.assert_not_called()
        event_capability = self.builder._ApprovedRequest(
            "events",
            "GET",
            f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build/events",
            None,
            receipt,
        )
        with mock.patch.dict(os.environ, {self.builder.REVIEW_ATTESTATIONS_ENV: ""}, clear=False):
            with mock.patch.object(self.builder, "_broker_exchange") as broker_exchange:
                with self.assertRaisesRegex(RuntimeError, "REVENUE_PARTNER_REVIEW_ATTESTATIONS"):
                    self.builder._stream_build_events(event_capability, receipt)
                broker_exchange.assert_not_called()
        event_capability = self.builder._ApprovedRequest(
            "events",
            "GET",
            f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build/events",
            None,
            receipt,
        )
        with (
            mock.patch.object(self.builder, "_verify_remote_publication_receipt", return_value=receipt),
            mock.patch.dict(os.environ, {self.builder.OPERATION_INTENT_DIRECTORY_ENV: ""}, clear=False),
            mock.patch.object(self.builder, "_broker_exchange") as broker_exchange,
        ):
            with self.assertRaisesRegex(RuntimeError, "externally signed operation intent"):
                self.builder._stream_build_events(event_capability, receipt)
            broker_exchange.assert_not_called()
        sse_error = TrackingHTTPError(b"event failure")
        event_capability = self.builder._ApprovedRequest(
            "events",
            "GET",
            f"{self.builder.API_BASE}/templates/{self.builder.NAMESPACE}/{self.builder.NAME}/{self.builder.VERSION}/build/events",
            None,
            receipt,
        )
        with (
            mock.patch.object(self.builder, "_verify_remote_publication_receipt", return_value=receipt),
            mock.patch.object(self.builder, "_await_signed_operation_intent", return_value="/intent"),
            mock.patch.object(self.builder, "_broker_exchange", side_effect=RuntimeError("event failure")),
        ):
            self.assertFalse(self.builder._stream_build_events(event_capability, receipt))
        ready_line = b'data: {"phase":"ready","level":"success"}\n'
        self.assertTrue(self.builder._consume_build_events(EventResponse([generic_ready_line])))
        self.assertTrue(self.builder._consume_build_events(EventResponse([ready_line])))
        with self.assertRaisesRegex(RuntimeError, "line exceeded"):
            self.builder._consume_build_events(
                EventResponse([b"x" * (self.builder.MAX_ORGO_SSE_LINE_BYTES + 1)])
            )
        with mock.patch.object(self.builder, "MAX_ORGO_SSE_TOTAL_BYTES", 4):
            with self.assertRaisesRegex(RuntimeError, "cumulative byte"):
                self.builder._consume_build_events(EventResponse([b"abc\n", b"d\n"]))
        with mock.patch.object(self.builder, "MAX_ORGO_SSE_EVENTS", 1):
            with self.assertRaisesRegex(RuntimeError, "event-count"):
                self.builder._consume_build_events(EventResponse([ready_line, ready_line]))
        with mock.patch.object(self.builder.time, "monotonic", side_effect=[0.0, 2.0]):
            with self.assertRaisesRegex(RuntimeError, "absolute deadline"):
                self.builder._consume_build_events(EventResponse([]), deadline_seconds=1)

        launch_body = self.builder._json_body_bytes(
            {"workspace_id": "workspace-1", "name": "revenue-partner-smoke", "template_ref": expected_ref,
             "ram": 4, "cpu": 1}
        )
        launch_capability = self.builder._ApprovedRequest(
            "launch", "POST", f"{self.builder.API_BASE}/computers", launch_body, receipt
        )
        with mock.patch.object(self.builder, "_send_approved", return_value=(200, "{}")):
            self.assertFalse(self.builder.launch(launch_capability, receipt))
        launch_without_publication_id = json.dumps(
            {"id": "computer-1", "workspace_id": "workspace-1"}
        )
        launch_capability = self.builder._ApprovedRequest(
            "launch", "POST", f"{self.builder.API_BASE}/computers", launch_body, receipt
        )
        with mock.patch.object(
            self.builder, "_send_approved", return_value=(200, launch_without_publication_id)
        ):
            self.assertTrue(self.builder.launch(launch_capability, receipt))
        launch_path = ROOT / f"{self.builder.NAME}.launch.json"
        launch_path.unlink(missing_ok=True)
        wrong_workspace = json.dumps(
            {"id": "computer-1", "workspace_id": "other-workspace"}
        )
        launch_capability = self.builder._ApprovedRequest(
            "launch", "POST", f"{self.builder.API_BASE}/computers", launch_body, receipt
        )
        with mock.patch.object(
            self.builder, "_send_approved", return_value=(200, wrong_workspace)
        ):
            self.assertFalse(self.builder.launch(launch_capability, receipt))
        valid_launch = json.dumps(
            {"id": "computer-1", "workspace_id": "workspace-1", "status": "running"}
        )
        launch_capability = self.builder._ApprovedRequest(
            "launch", "POST", f"{self.builder.API_BASE}/computers", launch_body, receipt
        )
        launch_path = ROOT / f"{self.builder.NAME}.launch.json"
        try:
            with mock.patch.object(self.builder, "_send_approved", return_value=(200, valid_launch)):
                self.assertTrue(self.builder.launch(launch_capability, receipt))
        finally:
            launch_path.unlink(missing_ok=True)

        mismatched_receipt = self.builder._PublicationReceipt(expected_ref, "0" * 64, "2026-08-19T00:00:00Z", {})
        build_capability = self.builder._ApprovedRequest(
            "build", "POST", f"{self.builder.API_BASE}/templates/x/build", None, receipt
        )
        with self.assertRaisesRegex(RuntimeError, "publication identity mismatch"):
            build_capability.consume("build", mismatched_receipt)

    def test_isolated_orgo_broker_enforces_operation_and_key_boundaries(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)
        publication_bytes = self.builder.publication_body_bytes()
        artifact_digest = hashlib.sha256(self.builder.resolved_artifact_bytes()).hexdigest()
        publication_digest = hashlib.sha256(publication_bytes).hexdigest()
        publish_message = {
            "operation": "publish",
            "method": "POST",
            "url": f"{broker.API_BASE}/templates",
            "body_b64": base64.b64encode(publication_bytes).decode(),
            "publication": None,
            "build": None,
            "intent_path": "/intent",
            "key_sha256": "ab" * 32,
        }
        normalized, body = broker.validate_request(
            publish_message, self.builder.template, publication_bytes
        )
        self.assertEqual(body, publication_bytes)
        self.assertEqual(normalized["url"], f"{broker.API_BASE}/templates")
        with self.assertRaisesRegex(RuntimeError, "fixed Orgo API authority"):
            broker.validate_request(
                {**publish_message, "url": "https://attacker.invalid/api/templates"},
                self.builder.template,
                publication_bytes,
            )
        with self.assertRaisesRegex(RuntimeError, "canonical operation bytes"):
            broker.validate_request(
                {**publish_message, "body_b64": base64.b64encode(b"{}").decode()},
                self.builder.template,
                publication_bytes,
            )

        parent, peer = socket.socketpair()
        captured = []
        mac_secret = "cd" * 32

        def fake_broker():
            frame = bytearray()
            while not frame.endswith(b"\n"):
                frame.extend(peer.recv(65536))
            captured.append(json.loads(frame))
            raw = json.dumps({
                "status": 200,
                "body_b64": base64.b64encode(b"ok").decode(),
            }).encode() + b"\n"
            mac = hmac.new(mac_secret.encode(), raw, hashlib.sha256).hexdigest().encode() + b"\n"
            peer.sendall(raw + mac)
            peer.close()

        worker = threading.Thread(target=fake_broker)
        worker.start()
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "REVENUE_PARTNER_BROKER_FD": str(parent.fileno()),
                    "REVENUE_PARTNER_BROKER_SECRET": mac_secret,
                    "REVENUE_PARTNER_BROKER_KEY_SHA256": "ab" * 32,
                },
                clear=False,
            ):
                os.environ.pop("ORGO_API_KEY", None)
                status, response_body = self.builder._broker_exchange(
                    "publish",
                    "POST",
                    f"{self.builder.API_BASE}/templates",
                    publication_bytes,
                    "/intent",
                )
            self.assertEqual((status, response_body), (200, b"ok"))
            self.assertEqual(captured[0]["operation"], "publish")
            self.assertEqual(base64.b64decode(captured[0]["body_b64"]), publication_bytes)
        finally:
            parent.close()
            worker.join(timeout=2)
        with mock.patch.dict(os.environ, {
            "ORGO_API_KEY": "sentinel",
            "REVENUE_PARTNER_BROKER_FD": "9",
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "key-less builder"):
                self.builder._broker_exchange(
                    "publish", "POST", f"{self.builder.API_BASE}/templates", b"x", "/intent"
                )

        class TrackingResponse:
            def __init__(self, body):
                self.headers = {}
                self.status = 200
                self.closed = False
                self._body = body

            def read(self, size):
                del size
                return self._body

            def close(self):
                self.closed = True

        class RecordingOpener:
            def __init__(self, response, order):
                self.response = response
                self.order = order

            def open(self, request, timeout):
                del timeout
                self.order.append(("open", request.full_url, request.get_method(), request.data))
                return self.response

        broker_side, client_side = socket.socketpair()
        publish_response_body = json.dumps({
            "ref": f"{broker.NAMESPACE}/{broker.NAME}@{broker.VERSION}",
            "digest": publication_digest,
            "published": "2026-08-19T00:00:00Z",
        }).encode()
        response = TrackingResponse(publish_response_body)
        order = []
        placeholder_key = "test-only-placeholder"
        canonical_request = {
            "operation": "publish",
            "method": "POST",
            "url": f"{broker.API_BASE}/templates",
            "body": publication_bytes,
            "publication_digest": None,
            "intent_path": "/intent",
            "key_sha256": broker.broker_key_sha256(placeholder_key),
            "workspace_id": None,
        }

        class GuardedEnvironment(dict):
            def get(self, key, default=None):
                if key == "ORGO_API_KEY" and (not order or order[-1] != "intent"):
                    raise AssertionError("credential read before intent consumption")
                return super().get(key, default)

        guarded = GuardedEnvironment(os.environ)
        broker_fd = broker_side.detach()
        guarded[broker.BROKER_FD_ENV] = str(broker_fd)
        guarded[broker.BROKER_SECRET_ENV] = "ef" * 32
        guarded["ORGO_API_KEY"] = placeholder_key

        def consumed(*_args):
            order.append("intent")

        def reviews_verified(*_args):
            order.append("reviews")

        with (
            mock.patch.object(broker, "exact_tree", return_value="a" * 40),
            mock.patch.object(
                broker,
                "canonical_products",
                return_value=(artifact_digest, publication_digest, self.builder.template, publication_bytes),
            ),
            mock.patch.object(broker, "validate_request", return_value=(canonical_request, publication_bytes)),
            mock.patch.object(broker, "verify_reviews", side_effect=reviews_verified),
            mock.patch.object(broker, "consume_intent", side_effect=consumed),
            mock.patch.object(
                broker.sys,
                "flags",
                mock.Mock(isolated=1, ignore_environment=1, no_user_site=1),
            ),
            mock.patch.object(
                broker.urllib.request,
                "build_opener",
                return_value=RecordingOpener(response, order),
            ),
            mock.patch.object(broker.os, "environ", guarded),
        ):
            broker_thread = threading.Thread(target=broker.main)
            broker_thread.start()
            client_side.sendall(json.dumps(publish_message).encode() + b"\n")
            reply = bytearray()
            while reply.count(b"\n") < 2:
                reply.extend(client_side.recv(65536))
            client_side.close()
            broker_thread.join(timeout=2)
        self.assertFalse(broker_thread.is_alive())
        self.assertTrue(response.closed)
        self.assertEqual(order[:2], ["reviews", "intent"])
        self.assertEqual(
            order[2],
            ("open", f"{broker.API_BASE}/templates", "POST", publication_bytes),
        )
        json_line, mac_line = reply.split(b"\n", 1)
        self.assertEqual(json.loads(json_line)["status"], 200)
        expected_mac = hmac.new(b"ef" * 32, json_line + b"\n", hashlib.sha256).hexdigest()
        self.assertEqual(mac_line.decode("ascii").strip(), expected_mac)

    def test_broker_events_response_reaches_sse_parser(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_events_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)
        publication_bytes = self.builder.publication_body_bytes()
        artifact_digest = hashlib.sha256(self.builder.resolved_artifact_bytes()).hexdigest()
        publication_digest = hashlib.sha256(publication_bytes).hexdigest()
        sse_body = (
            b'data: {"phase":"building","level":"info"}\n\n'
            b'data: {"phase":"ready","level":"success"}\n\n'
        )
        # Direct semantic validation must skip JSON parsing for events.
        broker.validate_response_semantics(
            {"operation": "events", "publication_digest": publication_digest},
            200,
            sse_body,
            publication_digest,
            json.loads(self.builder.resolved_artifact_bytes()),
        )
        ready, failed = broker.parse_sse_events(sse_body)
        self.assertTrue(ready)
        self.assertFalse(failed)

        class SseResponse:
            def __init__(self, body):
                self.headers = {}
                self.status = 200
                self.closed = False
                self._body = body
                self._sent = False

            def read1(self, size):
                del size
                if self._sent:
                    return b""
                self._sent = True
                return self._body

            def close(self):
                self.closed = True

        class RecordingOpener:
            def __init__(self, response, order):
                self.response = response
                self.order = order

            def open(self, request, timeout):
                del timeout
                self.order.append(("open", request.full_url, request.get_method(), request.data))
                return self.response

        broker_side, client_side = socket.socketpair()
        response = SseResponse(sse_body)
        order = []
        placeholder_key = "test-only-placeholder"
        canonical_request = {
            "operation": "events",
            "method": "GET",
            "url": f"{broker.API_BASE}/templates/{broker.NAMESPACE}/{broker.NAME}/{broker.VERSION}/build/events",
            "body": None,
            "publication_digest": publication_digest,
            "intent_path": "/intent",
            "key_sha256": broker.broker_key_sha256(placeholder_key),
            "workspace_id": None,
        }
        events_message = {
            "operation": "events",
            "method": "GET",
            "url": f"{broker.API_BASE}/templates/{broker.NAMESPACE}/{broker.NAME}/{broker.VERSION}/build/events",
            "body_b64": None,
            "publication": {"ref": f"{broker.NAMESPACE}/{broker.NAME}@{broker.VERSION}", "digest": publication_digest},
            "build": None,
            "intent_path": "/intent",
            "key_sha256": broker.broker_key_sha256(placeholder_key),
        }

        class GuardedEnvironment(dict):
            def get(self, key, default=None):
                if key == "ORGO_API_KEY" and (not order or order[-1] != "intent"):
                    raise AssertionError("credential read before intent consumption")
                return super().get(key, default)

        guarded = GuardedEnvironment(os.environ)
        broker_fd = broker_side.detach()
        guarded[broker.BROKER_FD_ENV] = str(broker_fd)
        guarded[broker.BROKER_SECRET_ENV] = "ef" * 32
        guarded["ORGO_API_KEY"] = placeholder_key

        def consumed(*_args):
            order.append("intent")

        def reviews_verified(*_args):
            order.append("reviews")

        with (
            mock.patch.object(broker, "exact_tree", return_value="a" * 40),
            mock.patch.object(
                broker,
                "canonical_products",
                return_value=(artifact_digest, publication_digest, self.builder.template, publication_bytes),
            ),
            mock.patch.object(broker, "validate_request", return_value=(canonical_request, None)),
            mock.patch.object(broker, "verify_reviews", side_effect=reviews_verified),
            mock.patch.object(broker, "consume_intent", side_effect=consumed),
            mock.patch.object(
                broker.sys,
                "flags",
                mock.Mock(isolated=1, ignore_environment=1, no_user_site=1),
            ),
            mock.patch.object(
                broker.urllib.request,
                "build_opener",
                return_value=RecordingOpener(response, order),
            ),
            mock.patch.object(broker.os, "environ", guarded),
        ):
            broker_thread = threading.Thread(target=broker.main)
            broker_thread.start()
            client_side.sendall(json.dumps(events_message).encode() + b"\n")
            reply = bytearray()
            while reply.count(b"\n") < 2:
                reply.extend(client_side.recv(65536))
            client_side.close()
            broker_thread.join(timeout=2)
        self.assertFalse(broker_thread.is_alive())
        self.assertTrue(response.closed)
        self.assertEqual(order[:2], ["reviews", "intent"])
        self.assertEqual(
            order[2],
            ("open", f"{broker.API_BASE}/templates/{broker.NAMESPACE}/{broker.NAME}/{broker.VERSION}/build/events", "GET", None),
        )
        json_line, mac_line = reply.split(b"\n", 1)
        record = json.loads(json_line)
        self.assertEqual(record["status"], 200)
        self.assertEqual(base64.b64decode(record["body_b64"]), sse_body)
        expected_mac = hmac.new(b"ef" * 32, json_line + b"\n", hashlib.sha256).hexdigest()
        self.assertEqual(mac_line.decode("ascii").strip(), expected_mac)

    def test_broker_validate_response_binds_exact_template_inventory(self):
        # Regression for the P1 where the validate branch referenced an
        # undefined `template` name and deterministically raised NameError.
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_validate_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)
        template = json.loads(self.builder.resolved_artifact_bytes())
        publication_digest = hashlib.sha256(self.builder.publication_body_bytes()).hexdigest()
        request = {"operation": "validate", "publication_digest": publication_digest}
        echoed = {
            "ok": True,
            "template": {
                "api_version": "orgo.ai/v1",
                "template": {"name": broker.NAME, "version": broker.VERSION},
                "files": [{"to": entry["to"]} for entry in template["files"]],
            },
        }
        # A correctly-shaped live response must pass without raising.
        broker.validate_response_semantics(
            request, 200, json.dumps(echoed).encode(), publication_digest, template
        )
        # A file inventory that does not match the exact template bytes must fail closed.
        wrong_inventory = json.loads(json.dumps(echoed))
        wrong_inventory["template"]["files"] = wrong_inventory["template"]["files"][:-1]
        with self.assertRaisesRegex(RuntimeError, "file inventory"):
            broker.validate_response_semantics(
                request, 200, json.dumps(wrong_inventory).encode(), publication_digest, template
            )
        # A wrong name/version binding must fail closed.
        wrong_reference = json.loads(json.dumps(echoed))
        wrong_reference["template"]["template"]["version"] = "9.9.9"
        with self.assertRaisesRegex(RuntimeError, "canonical template reference"):
            broker.validate_response_semantics(
                request, 200, json.dumps(wrong_reference).encode(), publication_digest, template
            )
        # A 2xx without `ok: true` must fail closed.
        with self.assertRaisesRegex(RuntimeError, "bound acceptance"):
            broker.validate_response_semantics(
                request, 200, json.dumps({"ok": False}).encode(), publication_digest, template
            )

    def test_release_path_scrubs_home_and_git_config_from_subprocesses(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_scrub_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)
        with tempfile.TemporaryDirectory() as directory:
            hostile_home = Path(directory) / "hostile-home"
            hostile_home.mkdir()
            marker = Path(directory) / "fsmonitor-ran"
            hook = Path(directory) / "fsmonitor-hook"
            hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
            hook.chmod(0o755)
            (hostile_home / ".gitconfig").write_text(
                f"[core]\n\tfsmonitor = {hook}\n"
            )
            hostile = {
                "HOME": str(hostile_home),
                "GIT_CONFIG_GLOBAL": str(hostile_home / ".gitconfig"),
                "GIT_CONFIG_SYSTEM": str(hostile_home / "system"),
                "GIT_CONFIG_NOSYSTEM": "0",
                "GIT_DIR": str(hostile_home / "gitdir"),
                "GIT_WORK_TREE": str(hostile_home / "worktree"),
                "GIT_INDEX_FILE": str(hostile_home / "index"),
                "GIT_OBJECT_DIRECTORY": str(hostile_home / "objects"),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(hostile_home / "alt"),
                "XDG_CONFIG_HOME": str(hostile_home / "xdg"),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor",
                "GIT_CONFIG_VALUE_0": str(hook),
                "GIT_CONFIG_PARAMETERS": f"'core.fsmonitor'='{hook}'",
                "GIT_SSH_COMMAND": str(hook),
                "GIT_ASKPASS": str(hook),
                "GIT_EXTERNAL_DIFF": str(hook),
                "GIT_PAGER": str(hook),
                "GIT_EDITOR": str(hook),
                "GIT_SEQUENCE_EDITOR": str(hook),
                "GIT_EXEC_PATH": str(hostile_home / "exec"),
                "GIT_TEMPLATE_DIR": str(hostile_home / "template"),
                "GIT_ATTR_NOSYSTEM": "0",
                "GIT_ATTR_GLOBAL": str(hostile_home / "attrs"),
                "ORGO_API_KEY": "hostile-sentinel",
                "REVENUE_PARTNER_BROKER_FD": "7",
                "REVENUE_PARTNER_BROKER_SECRET": "ab" * 32,
                "REVENUE_PARTNER_BROKER_KEY_SHA256": "cd" * 32,
            }
            with mock.patch.dict(os.environ, hostile, clear=False):
                broker_env = broker.keyless_subprocess_environment()
                builder_env = self.builder._scrubbed_env()
            for scrubbed in (broker_env, builder_env):
                # From-scratch: only PATH/HOME and the two git-neutralizing
                # variables survive; every operator variable is gone.
                self.assertEqual(set(scrubbed), {"PATH", "HOME", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"})
                self.assertEqual(scrubbed["HOME"], "/tmp")
                self.assertEqual(scrubbed["GIT_CONFIG_GLOBAL"], "/dev/null")
                self.assertEqual(scrubbed["GIT_CONFIG_NOSYSTEM"], "1")
            # A git status/diff in the scrubbed environment must not invoke the
            # hostile fsmonitor hook, even when injected via GIT_CONFIG_COUNT
            # or GIT_CONFIG_PARAMETERS.
            subprocess.run(
                ["/usr/bin/git", *broker.GIT_SAFE_ARGS, "status", "--porcelain"],
                cwd=ROOT,
                env=broker_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            self.assertFalse(marker.exists(), "hostile core.fsmonitor executed in scrubbed environment")
            entry_source = (ROOT / "release_entry.py").read_text()
            self.assertIn("_scrubbed_child_environment", entry_source)
            self.assertIn("RELEASE_ALLOWLIST", entry_source)
            self.assertIn('"GIT_CONFIG_GLOBAL": "/dev/null"', entry_source)
            self.assertIn('"REVENUE_PARTNER_NONCE_LEDGER"', entry_source)
            # The release entry's child environment must carry only the
            # allowlisted release variables plus the neutralized git base.
            entry_spec = importlib.util.spec_from_file_location(
                "release_entry_scrub_test", ROOT / "release_entry.py"
            )
            assert entry_spec and entry_spec.loader
            entry = importlib.util.module_from_spec(entry_spec)
            entry_spec.loader.exec_module(entry)
            with mock.patch.dict(os.environ, hostile, clear=False):
                child_env = entry._scrubbed_child_environment()
            self.assertEqual(
                set(child_env),
                {"PATH", "HOME", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL", "ORGO_API_KEY"},
            )
            self.assertEqual(child_env["ORGO_API_KEY"], "hostile-sentinel")
            self.assertNotIn("GIT_CONFIG_COUNT", child_env)
            self.assertNotIn("GIT_CONFIG_PARAMETERS", child_env)
            self.assertNotIn("REVENUE_PARTNER_BROKER_FD", child_env)

    def test_install_script_copies_only_staged_sources(self):
        # Every `{STAGE}/...` path referenced in the install script must be
        # produced by either the deterministic payload tarball or an F()
        # staged entry; a missing source would abort the image build under
        # `set -e`.
        install = self.builder.INSTALL
        staged_sources = {entry["to"] for entry in self.builder.files}
        payload_arcnames = set()
        import base64 as _b64
        import gzip as _gzip
        import io as _io
        import tarfile as _tarfile
        payload = _b64.b64decode(self.builder.payload_b64())
        with _tarfile.open(fileobj=_io.BytesIO(payload), mode="r:gz") as tar:
            for member in tar.getmembers():
                payload_arcnames.add(member.name)
        stage_prefix = f"{self.builder.STAGE}/"
        referenced = set()
        for line in install.splitlines():
            stripped = line.strip()
            if not stripped.startswith("cp -rf "):
                continue
            source = stripped.split()[2]
            assert source.startswith(stage_prefix), source
            referenced.add(source)
        # Also cover every other {STAGE}/... reference (e.g. the pruner path).
        for line in install.splitlines():
            start = 0
            while True:
                index = line.find(stage_prefix, start)
                if index == -1:
                    break
                end = index + len(stage_prefix)
                while end < len(line) and line[end] not in " \t\n\"'":
                    end += 1
                referenced.add(line[index:end])
                start = end
        for source in sorted(referenced):
            source_norm = source[:-2] if source.endswith("/.") else source
            rel = source_norm[len(stage_prefix):]
            self.assertTrue(
                source in staged_sources
                or rel in payload_arcnames
                or any(name.startswith(rel + "/") for name in payload_arcnames)
                or any(name.startswith(source_norm + "/") for name in staged_sources),
                f"install source {source} is never staged",
            )
        # The pruned connector plugin tree must not be referenced anywhere.
        self.assertNotIn("hermes/plugins", install)
        self.assertNotIn("hermes/plugins", "\n".join(sorted(payload_arcnames)))
        self.assertNotIn('("plugins", "hermes/plugins")', (ROOT / "build_template.py").read_text())
        # The connector pruner must be invoked at its payload arcname.
        self.assertIn(f"{self.builder.STAGE}/hermes/scripts/prune_hermes_runtime.py", install)
        self.assertIn("hermes/scripts/prune_hermes_runtime.py", payload_arcnames)

    def test_broker_events_http_error_falls_back_to_read(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_events_error_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)

        class ErrorResponse:
            def __init__(self):
                self.headers = {}
                self.status = 401
                self.closed = False
                self._sent = False

            def read(self, size):
                del size
                if self._sent:
                    return b""
                self._sent = True
                return b'{"error": "unauthorized"}'

            def getcode(self):
                return 401

            def close(self):
                self.closed = True

        response = ErrorResponse()
        status, body = broker.read_bounded_response(response, "events")
        self.assertEqual(status, 401)
        self.assertEqual(body, b'{"error": "unauthorized"}')

    def test_broker_rejects_forged_peer_without_mac_secret(self):
        parent, peer = socket.socketpair()

        def forged_peer():
            frame = bytearray()
            while not frame.endswith(b"\n"):
                frame.extend(peer.recv(65536))
            raw = json.dumps({"status": 200, "body_b64": base64.b64encode(b"{}").decode()}).encode() + b"\n"
            peer.sendall(raw + b"0" * 64 + b"\n")
            peer.close()

        worker = threading.Thread(target=forged_peer)
        worker.start()
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "REVENUE_PARTNER_BROKER_FD": str(parent.fileno()),
                    "REVENUE_PARTNER_BROKER_KEY_SHA256": "ab" * 32,
                },
                clear=False,
            ):
                os.environ.pop("ORGO_API_KEY", None)
                os.environ.pop("REVENUE_PARTNER_BROKER_SECRET", None)
                with self.assertRaisesRegex(RuntimeError, "MAC secret"):
                    self.builder._broker_exchange(
                        "publish", "POST", f"{self.builder.API_BASE}/templates", b"x", "/intent"
                    )
        finally:
            parent.close()
            worker.join(timeout=2)

    def test_broker_rejects_forged_peer_with_wrong_mac(self):
        parent, peer = socket.socketpair()

        def forged_peer():
            frame = bytearray()
            while not frame.endswith(b"\n"):
                frame.extend(peer.recv(65536))
            raw = json.dumps({"status": 200, "body_b64": base64.b64encode(b"{}").decode()}).encode() + b"\n"
            peer.sendall(raw + b"0" * 64 + b"\n")
            peer.close()

        worker = threading.Thread(target=forged_peer)
        worker.start()
        try:
            with mock.patch.dict(
                os.environ,
                {
                    "REVENUE_PARTNER_BROKER_FD": str(parent.fileno()),
                    "REVENUE_PARTNER_BROKER_SECRET": "ef" * 32,
                    "REVENUE_PARTNER_BROKER_KEY_SHA256": "ab" * 32,
                },
                clear=False,
            ):
                os.environ.pop("ORGO_API_KEY", None)
                with self.assertRaisesRegex(RuntimeError, "MAC verification"):
                    self.builder._broker_exchange(
                        "publish", "POST", f"{self.builder.API_BASE}/templates", b"x", "/intent"
                    )
        finally:
            parent.close()
            worker.join(timeout=2)

    def test_broker_sse_read_enforces_absolute_deadline(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_sse_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)

        class TrickleResponse:
            def __init__(self):
                self.headers = {}
                self.status = 200
                self.closed = False
                self._released = threading.Event()

            def read1(self, size):
                del size
                self._released.wait(timeout=2)
                return b""

            def close(self):
                self.closed = True
                self._released.set()

        response = TrickleResponse()
        with mock.patch.object(broker, "MAX_SSE_DEADLINE_SECONDS", 1):
            try:
                with self.assertRaisesRegex(RuntimeError, "absolute deadline"):
                    broker.read_bounded_response(response, "events")
            finally:
                response.close()
        self.assertTrue(response.closed)

    def test_broker_http_error_responses_are_closed(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_http_error_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)

        class ErrorResponse:
            def __init__(self):
                self.headers = {}
                self.status = 400
                self.closed = False

            def read(self, size):
                del size
                return b'{"error": "bad request"}'

            def close(self):
                self.closed = True

        response = ErrorResponse()
        status, body = broker.read_bounded_response(response, "publish")
        self.assertEqual(status, 400)
        self.assertEqual(body, b'{"error": "bad request"}')

    def test_raw_http_and_latitude_http_errors_are_closed(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        with tempfile.TemporaryDirectory() as state_dir:
            code = f'''\
import json
from pathlib import Path
from unittest.mock import patch
import urllib.error
import super_browser.adapters as adapters
from super_browser.models import Plan, TaskSpec

root = Path({state_dir!r})
plan = Plan(task=TaskSpec(goal="read public JSON", url="http://93.184.216.34/data", raw_http=True), primary_provider="decodo-http")

class RecordingError(urllib.error.HTTPError):
    def __init__(self):
        super().__init__("http://93.184.216.34/data", 500, "boom", {{}}, None)
        self.closed = False
    def close(self):
        self.closed = True

error = RecordingError()
class RaisingOpener:
    def open(self, request, timeout):
        raise error

with patch("super_browser.adapters.build_opener", return_value=RaisingOpener()):
    try:
        adapters._open_raw_http_request(
            adapters.Request("http://93.184.216.34/data", method="GET"),
            10, None, adapters._TargetScopeRedirectHandler("public_web"),
        )
    except urllib.error.HTTPError:
        pass
assert error.closed, "raw HTTP HTTPError was not closed"
print("RAW_HTTP_ERROR closed=True")
'''
            result = subprocess.run(
                [sys.executable, "-c", code], env=env, text=True, capture_output=True, check=False
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

        latitude_env = os.environ.copy()
        latitude_env["PYTHONPATH"] = str(ROOT / "files/local-packages/latitude-telemetry-hermes")
        latitude_code = '''\
import urllib.error
from unittest.mock import patch
from latitude_telemetry_hermes import transport

class RecordingError(urllib.error.HTTPError):
    def __init__(self):
        super().__init__("https://ingest.latitude.so/v1/traces", 500, "boom", {}, None)
        self.closed = False
    def close(self):
        self.closed = True

error = RecordingError()
class RaisingOpener:
    def open(self, request, timeout):
        raise error

with patch.object(transport._OPENER, "open", side_effect=error):
    transport._post_traces({"trace": "x"})
assert error.closed, "latitude HTTPError was not closed"
print("LATITUDE_HTTP_ERROR closed=True")
'''
        latitude_result = subprocess.run(
            [sys.executable, "-c", latitude_code], env=latitude_env, text=True, capture_output=True, check=False
        )
        self.assertEqual(latitude_result.returncode, 0, latitude_result.stderr + latitude_result.stdout)

    def test_nonce_ledger_is_fixed_and_home_independent(self):
        broker_spec = importlib.util.spec_from_file_location(
            "orgo_release_broker_ledger_test", ROOT / ".github/scripts/orgo_release_broker.py"
        )
        assert broker_spec and broker_spec.loader
        broker = importlib.util.module_from_spec(broker_spec)
        broker_spec.loader.exec_module(broker)
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            ledger = directory_path / "ledger"
            ledger.mkdir(mode=0o700)
            nonce = "ab" * 32
            now = time.time()
            statement = {
                "operation": "publish",
                "nonce": nonce,
                "issued_at": now,
                "expires_at": now + 600,
                "method": "POST",
                "url": f"{broker.API_BASE}/templates",
                "body_sha256": hashlib.sha256(b"x").hexdigest(),
                "template_ref": broker.CANONICAL_REF,
                "publication_digest": None,
                "tree": "a" * 40,
                "artifact_sha256": "b" * 64,
                "publication_sha256": "c" * 64,
            }
            intent = directory_path / "intent.json"
            intent.write_text(json.dumps({"statement": statement, "signature_path": str(directory_path / "sig")}))
            intent.chmod(0o600)
            (directory_path / "sig").write_text("sig")
            (directory_path / "sig").chmod(0o600)
            request = {
                "operation": "publish",
                "method": "POST",
                "url": f"{broker.API_BASE}/templates",
                "body": b"x",
                "publication_digest": None,
                "intent_path": str(intent),
            }
            marker = ledger / nonce
            marker.write_text("consumed\n")
            marker.chmod(0o600)
            with (
                mock.patch.object(broker, "nonce_ledger", return_value=ledger),
                mock.patch.object(broker, "verify_signature"),
            ):
                with self.assertRaisesRegex(RuntimeError, "already consumed"):
                    broker.consume_intent(request, "a" * 40, "b" * 64, "c" * 64)
            # A different HOME must not create a second ledger: the broker reads
            # only the launcher-controlled absolute path.
            with mock.patch.dict(os.environ, {"HOME": str(directory_path / "other-home")}, clear=False):
                with (
                    mock.patch.object(broker, "nonce_ledger", return_value=ledger),
                    mock.patch.object(broker, "verify_signature"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "already consumed"):
                        broker.consume_intent(request, "a" * 40, "b" * 64, "c" * 64)

    def test_launch_without_workspace_is_controlled_error(self):
        env = os.environ.copy()
        env["ORGO_API_KEY"] = "test-only-placeholder"
        cases = [
            (["--launch"], "argument --launch: expected one argument"),
            (["--launch", "workspace-1"], "--launch requires --build"),
            (["--buid"], "unrecognized arguments: --buid"),
            (["--publish", "surplus"], "unrecognized arguments: surplus"),
            (["--publish", "--build"], "not allowed with argument --publish"),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "build_template.py"), *args],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr + result.stdout)
                self.assertNotIn("IndexError", result.stderr)

    def test_template_does_not_advertise_blocked_provider_credentials(self):
        names = {item["name"] for item in self.builder.template["secrets"]}
        for name in {
            "browser_use_api_key",
            "airtop_api_key",
            "decodo_proxy",
            "hyperbrowser_api_key",
            "steel_api_key",
            "browserbase_api_key",
            "exa_api_key",
            "firecrawl_api_key",
            "vidiq_api_key",
            "vidiq_mcp_api_key",
            "x_app_only_bearer_token",
            "ideabrowser_key",
        }:
            self.assertNotIn(name, names)
            env_name = name.upper()
            self.assertNotIn(env_name, (FILES / "config.yaml").read_text())
            self.assertNotIn(env_name, (FILES / "hermes.env").read_text())
            self.assertNotIn(f'"{env_name}"', (FILES / "safe-env-bridge.py").read_text())
        self.assertNotIn("orgo_api_key", names)
        self.assertNotIn("orgo_default_computer_id", names)
        rendered = str(self.builder.template)
        supplied_key = os.environ.get("ORGO_API_KEY", "")
        if supplied_key:
            self.assertNotIn(supplied_key, rendered)

    def test_locked_hermes_runtime_prunes_connector_surfaces(self):
        script_path = FILES / "scripts/prune_hermes_runtime.py"
        spec = importlib.util.spec_from_file_location("prune_hermes_runtime_test", script_path)
        if spec is None or spec.loader is None:
            self.fail("cannot import Hermes runtime pruner")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Slack is intentionally NOT pruned: it is an operator-connected inbound
        # channel. What the agent may do when reached over Slack is bounded by
        # platform_toolsets, not by removing the platform from the image.
        expected = {
            "plugins/spotify",
            "plugins/platforms/discord",
            "optional-mcps/linear",
            "tools/discord_tool.py",
        }
        self.assertEqual(set(module.REMOVED_PATHS), expected)
        self.assertIn(f'"$VENV_PY" {self.builder.STAGE}/hermes/scripts/prune_hermes_runtime.py', self.builder.INSTALL)
        # Removing a module that the CLI entry imports at module scope makes every
        # `hermes` invocation die on ModuleNotFoundError, which only surfaces at
        # image-build time. The pruner must detach the call sites in the same pass.
        self.assertEqual(module.CLI_ENTRY, "hermes_cli/main.py")
        self.assertEqual(module.CLI_DANGLING_NAMES, ("build_slack_parser",))
        self.assertTrue(module.CLI_DETACHED_ANCHORS)
        # The detach must fire only when the module it references was pruned.
        # Retaining Slack while still stripping its parser would remove a CLI
        # surface that works, which is the mirror image of the original defect.
        self.assertNotIn("hermes_cli/subcommands/slack.py", module.REMOVED_PATHS)
        source = (FILES / "scripts/prune_hermes_runtime.py").read_text()
        self.assertIn('if "hermes_cli/subcommands/slack.py" not in REMOVED_PATHS:', source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel_dir = root / "wheel"
            wheel_dir.mkdir()
            subprocess.run(
                [sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--no-deps",
                 "--only-binary=:all:", "--no-cache-dir", "--index-url", "https://pypi.org/simple",
                 "--dest", str(wheel_dir), "hermes-agent==0.18.0"],
                check=True,
            )
            wheels = list(wheel_dir.glob("hermes_agent-0.18.0-*.whl"))
            self.assertEqual(len(wheels), 1)
            self.assertEqual(
                hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
                "bf75c02d59f7c464cd0d85026fb7ee2e6bb15f003beccab3442b572f1ae1fd37",
            )
            venv_dir = root / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            venv_python = venv_dir / "bin/python"
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
                 "--no-index", str(wheels[0])],
                check=True,
            )
            subprocess.run([str(venv_python), "-I", "-s", "-E", str(script_path)], check=True)
            verification = subprocess.run(
                [str(venv_python), "-I", "-s", "-E", "-c",
                 "import importlib.util,pathlib;"
                 f"p={str(script_path)!r};s=importlib.util.spec_from_file_location('prune_verify',p);"
                 "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                 "d=m.importlib.metadata.distribution('hermes-agent');"
                 "assert all(not m._surface_target(d,r).exists() for r in m.REMOVED_PATHS);"
                 "e=m._surface_target(d,m.CLI_ENTRY);src=e.read_text(encoding='utf-8');"
                 # A dangling reference is only a defect when the module it names was
                 # actually pruned. With Slack retained the parser call is valid and
                 # must survive; either way the entry has to still compile.
                 "pruned='hermes_cli/subcommands/slack.py' in m.REMOVED_PATHS;"
                 "assert (not pruned) or all(n not in src for n in m.CLI_DANGLING_NAMES),"
                 " 'pruned CLI reference survived';"
                 "assert pruned or any(n in src for n in m.CLI_DANGLING_NAMES),"
                 " 'retained Slack parser was stripped anyway';"
                 "compile(src,str(e),'exec')"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(verification.returncode, 0, verification.stdout + verification.stderr)

        bridge = (FILES / "safe-env-bridge.py").read_text()
        for absent_credential in (
            "COMPOSIO_CONSUMER_KEY",
            "AGENTPHONE_API_KEY",
            "AGENTMAIL_API_KEY",
            "HERMES_SPOTIFY_CLIENT_ID",
            "DISCORD_BOT_TOKEN",
        ):
            self.assertNotIn(f'"{absent_credential}"', bridge)

    def test_vendor_is_pinned_and_importable(self):
        commit = (SB / "UPSTREAM_COMMIT").read_text().strip()
        self.assertEqual(commit, "552822fd86a74d574ff9c0d87db6e6b82f929d96")
        for rel in (
            ".codex-plugin/plugin.json",
            ".mcp.json",
            "references/provider-matrix.md",
            "skills/playwright-specialist/SKILL.md",
            "skills/super-browser-orchestrator/SKILL.md",
            "configs/hermes-mcp.yaml",
            "docs/setup-walkthrough.md",
            "scripts/super-browser",
            "scripts/verify-super-browser",
        ):
            self.assertTrue((SB / rel).exists(), rel)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        env["SUPER_BROWSER_REPO_ROOT"] = str(SB)
        code = (
            "from super_browser.providers import PROVIDERS; "
            "assert len(PROVIDERS) == 8; "
            "from super_browser.mcp_server import main, list_resources; "
            "assert len(list_resources()) >= 20; "
            "print(','.join(PROVIDERS))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, text=True, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.strip().split(",")), 8)

        manifest_code = (
            "from pathlib import Path; from super_browser.bundle import RESOURCE_URIS, build_bundle_manifest; from super_browser.mcp_server import RESOURCE_FILES, list_resources; "
            f"m=build_bundle_manifest(Path({str(SB)!r})); "
            "assert m['status']=='ok' and not m['missing_required_paths']; "
            "assert set(RESOURCE_URIS) == set(RESOURCE_FILES), (set(RESOURCE_URIS), set(RESOURCE_FILES)); "
            "assert set(m['resources']) == {item['uri'] for item in list_resources()}, (set(m['resources']), {item['uri'] for item in list_resources()})"
        )
        manifest_env = env.copy()
        manifest_env.pop("SUPER_BROWSER_REPO_ROOT", None)
        manifest = subprocess.run(
            [sys.executable, "-c", manifest_code], env=manifest_env, text=True, capture_output=True, check=False
        )
        self.assertEqual(manifest.returncode, 0, manifest.stderr)

    def test_super_browser_ad_campaign_phrases_require_approval(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        env["SUPER_BROWSER_REPO_ROOT"] = str(SB)
        blocked_phrases = [
            "launch an ad campaign",
            "create an ad",
            "run the campaign",
            "create a campaign",
            "launch a paid social campaign",
            "run an advertising campaign",
            "activate the ads",
            "launch a paid-social campaign",
            "create an email campaign",
            "launch our ad campaign",
            "create the new ad campaign",
            "start a B2B campaign",
            "activate an influencer campaign",
            "run my advertising campaign",
            "enable our retargeting ads",
            "turn on the search campaign",
            "take our campaign live",
            "kick off our campaign",
            "fire up that email campaign",
            "go live with the B2B campaign",
            "roll out our influencer campaign",
            "deploy the new campaign",
            "schedule my campaign",
            "promote our campaign",
            "Draft an internal ad campaign plan, then launch it",
            "Create an ad campaign draft for internal review only; then publish it",
            "For internal review, outline the campaign and activate it",
            "Draft campaign copy, do not publish it; launch the campaign instead",
            "Prepare an internal advertising strategy. After review, go live with it",
            "Create a campaign proposal for review and schedule it tomorrow",
            "Create a local CSV of leads, then launch the ad campaign",
            "Export prospects to a local JSON file and activate the advertising campaign",
            "Save customer leads locally; then schedule our campaign",
            "Launch adverts",
            "Fire up an advert",
            "Search for ad campaign examples, then launch it",
            "Send me a report on the ad campaign, then activate it",
            "Review our campaign metrics and then schedule it",
            "What is this ad campaign? Then turn it on",
            "Analyze and then launch our ad campaign",
            "Explain how to launch the campaign",
            "Compare these campaigns and activate the winner",
            "Draft an internal campaign plan, then greenlight it",
            "Send me a report on the ad campaign, then greenlight it",
            "Search for ad campaign examples, then greenlight one",
            "Analyze the campaign and greenlight it",
            "draft an ad campaign plan for internal review; do not launch it",
            "create an ad campaign draft for internal review only; do not publish",
            "Draft an internal advert plan without launching it",
            "Launch it after you draft an internal ad campaign plan",
            "Activate it before drafting the internal advert proposal",
            "Greenlight it after you draft an internal ad campaign plan",
            "Draft an internal campaign plan to greenlight it",
            "Draft an internal advert plan: greenlight it",
            "Draft internal advertising copy—ship it",
            "For review only, draft a campaign plan to commission it",
            "Never launch it; draft an internal campaign plan, afterward greenlight it",
            "dispatch an email to alice@example.com through Gmail",
            "Use Gmail to transmit the note to alice@example.com",
            "Convey this note to Alice through Gmail",
            "Use the contact form to convey my request",
            "Click the paper airplane in Gmail",
            "Click the paper-plane icon",
            "Click the paper plane",
            "Click the airplane button",
            "Click the send icon",
            "Email Alice the note through Gmail",
            "E-mail Alice the proposal",
            "Mail Alice the proposal",
            "Send me a report via Gmail",
            "Read my Gmail messages",
            "Use the contact form to reach out to Alice",
            "deliver this message to the customer",
            "forward the proposal to alice@example.com",
            "What is Gmail? Then send this message.",
            "Explain email basics, then click the send icon.",
            "What is Gmail? Then click the paper airplane.",
            "Create a posting schedule outline, then click the send icon.",
            "Create local notes about public email docs, then click the send button.",
            "Push the dashboard to production",
            "Ship the UI to prod",
            "Release the app to production",
            "Promote the site to live",
            "Roll out the dashboard to production",
            "Deploy the UI in prod",
            "Publish the website to production",
            "On the desktop, make this site live by clicking the rocket icon",
            "Go live by clicking the final action button",
            "Click the rocket icon to make the dashboard live",
            "Click the final action button",
        ]
        safe_phrases = [
            "research examples of ad campaigns",
            "analyze our ad campaign performance",
            "compare three advertising campaigns",
            "what is an ad campaign?",
            "What is Gmail?",
            "explain advertising campaign metrics",
            "give me a report on ad campaigns",
            "Submit the public search form for visible advert examples",
        ]
        with tempfile.TemporaryDirectory() as state_dir:
            env["SUPER_BROWSER_STATE_DIR"] = state_dir
            code = (
                "import super_browser.runtime as runtime; import super_browser.adapters as adapters; "
                "from super_browser.models import plan_fingerprint, action_fingerprint_from_plan, utc_now; from pathlib import Path; "
                f"blocked={blocked_phrases!r}; safe={safe_phrases!r}; "
                "runtime.execute_plan=lambda plan: (_ for _ in ()).throw(RuntimeError('provider execution reached')); "
                "blocked_runs=[runtime.create_run(goal, execute=True) for goal in blocked]; "
                "safe_runs=[runtime.create_run(goal, execute=False) for goal in safe]; "
                "assert all(run.status == 'awaiting_approval' for run in blocked_runs), "
                "list(zip(blocked, [run.status for run in blocked_runs])); "
                "assert all(run.status == 'planned' and not run.approvals for run in safe_runs), "
                "list(zip(safe, [(run.status, len(run.approvals)) for run in safe_runs])); "
                "tampered=blocked_runs[0]; tampered.status='approved'; runtime.RunStore().save(tampered); "
                "resumed=runtime.resume_run(tampered.run_id); "
                "assert resumed.status == 'awaiting_approval', resumed.to_dict(); "
                "import unittest; unittest.TestCase().assertRaises(PermissionError, runtime.approve_run, tampered.run_id, reason='self approved', execute=True); "
                "plan=runtime._plan_from_run(tampered); now=utc_now(); forged={'status':'approved','approval_id':'self-made','decided_at':now,'decided_by':'agent','required_before':'provider_execution','action_fingerprint':action_fingerprint_from_plan(plan),'plan_sha256':plan_fingerprint(plan)}; "
                f"direct=adapters.execute_plan(plan, 'run_direct', Path({state_dir!r})); "
                "assert direct.status == 'blocked' and not direct.verification.get('attempts'), direct.to_dict(); "
                f"unittest.TestCase().assertRaises(TypeError, adapters.execute_plan, plan, 'run_forged', Path({state_dir!r}), approval_granted=True, approval_context=forged)"
            )
            result = subprocess.run(
                [sys.executable, "-c", code], env=env, text=True, capture_output=True, check=False
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_super_browser_network_targets_fail_closed_against_loopback_and_rebinding(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        env.pop("DECODO_PROXY", None)
        with tempfile.TemporaryDirectory() as state_dir:
            code = f'''\
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch
import super_browser.adapters as adapters
from super_browser.models import Plan, TaskSpec
from super_browser.policy import approval_required

root = Path({state_dir!r})
loop_url = "http://127.0.0.1:4567/data.json"
loop_task = TaskSpec(goal="summarize this public page", url=loop_url, target_scope="loopback")
loop_plan = Plan(task=loop_task, primary_provider="playwright")
assert approval_required(loop_task)
central_loop = adapters.execute_plan(loop_plan, "loop-central", root)
assert central_loop.status == "blocked" and not central_loop.verification.get("attempts"), central_loop.to_dict()
direct_loop = adapters.PlaywrightAdapter().execute(loop_plan, "loop-direct", root)
assert direct_loop.status == "blocked" and "approval-required" in direct_loop.error, direct_loop.to_dict()

os.environ["SUPER_BROWSER_TEST_MODE"] = "1"
os.environ["SUPER_BROWSER_TEST_TARGET_ALLOWLIST_JSON"] = json.dumps([loop_url])
assert not approval_required(loop_task)
assert adapters._direct_adapter_security_block("playwright", loop_task) is None
wrong_loop = TaskSpec(goal="summarize this public page", url="http://127.0.0.1:4568/data.json", target_scope="loopback")
assert approval_required(wrong_loop)
assert adapters._direct_adapter_security_block("playwright", wrong_loop).status == "blocked"
os.environ.pop("SUPER_BROWSER_TEST_MODE")
os.environ.pop("SUPER_BROWSER_TEST_TARGET_ALLOWLIST_JSON")

public_plan = Plan(task=TaskSpec(goal="summarize this public page", url="https://example.com"), primary_provider="airtop")
public_playwright_plan = Plan(task=TaskSpec(goal="summarize this public page", url="https://example.com"), primary_provider="playwright")
public_playwright_direct = adapters.PlaywrightAdapter().execute(public_playwright_plan, "public-playwright-direct", root)
assert public_playwright_direct.status == "blocked" and "Public-web Playwright" in public_playwright_direct.error, public_playwright_direct.to_dict()
public_playwright_central = adapters.execute_plan(public_playwright_plan, "public-playwright-central", root)
assert public_playwright_central.status == "blocked" and not public_playwright_central.verification.get("attempts"), public_playwright_central.to_dict()
remote_direct = adapters.AirtopAdapter().execute(public_plan, "remote-direct", root)
assert remote_direct.status == "blocked" and "connected peer addresses" in remote_direct.error, remote_direct.to_dict()
adapters.get_adapter = lambda name: (_ for _ in ()).throw(RuntimeError("adapter construction reached"))
remote_central = adapters.execute_plan(public_plan, "remote-central", root)
assert remote_central.status == "blocked" and not remote_central.verification.get("attempts"), remote_central.to_dict()
raw_plan = Plan(task=TaskSpec(goal="summarize this public JSON endpoint", url="https://example.com/data.json", raw_http=True), primary_provider="decodo-http")
raw_direct = adapters.RawHttpAdapter().execute(raw_plan, "raw-direct", root)
assert raw_direct.status == "blocked" and "public IP-literal URL" in raw_direct.error, raw_direct.to_dict()
raw_central = adapters.execute_plan(raw_plan, "raw-central", root)
assert raw_central.status == "blocked" and not raw_central.verification.get("attempts"), raw_central.to_dict()

public_answer = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]
private_answer = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]
with patch("super_browser.adapters.socket.getaddrinfo", return_value=public_answer):
    assert adapters._validated_chromium_host_pin("https://example.com") == ("example.com", "93.184.216.34")
assert "--host-resolver-rules=MAP {{host}} {{address}},MAP * ~NOTFOUND" in Path(adapters.__file__).read_text()

class Request:
    url = "https://example.com/private"
    method = "GET"
    resource_type = "document"
class Route:
    request = Request()
    aborted = False
    continued = False
    def abort(self): self.aborted = True
    def continue_(self): self.continued = True
route = Route()
guard = adapters._BrowserRequestScopeGuard("public_web", "example.com")
with patch("super_browser.adapters.socket.getaddrinfo", return_value=private_answer):
    guard.route(route)
assert route.aborted and not route.continued and guard.blocked_requests[0]["resolved_addresses"][0]["target_scope"] == "loopback", guard.blocked_requests
cross_route = Route()
cross_route.request.url = "https://other.example/resource"
guard.route(cross_route)
assert cross_route.aborted and guard.blocked_requests[-1]["target_scope"] == "cross_host", guard.blocked_requests
for unsafe_method in ("POST", "PUT", "PATCH", "DELETE"):
    unsafe_request = type("UnsafeRequest", (), {{"url": "https://example.com/mutate", "method": unsafe_method, "resource_type": "fetch", "post_data": "payload"}})()
    unsafe_route = type("UnsafeRoute", (), {{"request": unsafe_request, "aborted": False, "continued": False, "abort": lambda self: setattr(self, "aborted", True), "continue_": lambda self: setattr(self, "continued", True)}})()
    unsafe_guard = adapters._BrowserRequestScopeGuard("public_web", "example.com")
    unsafe_guard.route(unsafe_route)
    assert unsafe_route.aborted and not unsafe_route.continued and unsafe_guard.blocked_requests[0]["target_scope"] == "unsafe_method"
body_get_request = type("BodyGetRequest", (), {{"url": "https://example.com/mutate", "method": "GET", "resource_type": "fetch", "post_data": "payload"}})()
body_get_route = type("BodyGetRoute", (), {{"request": body_get_request, "aborted": False, "continued": False, "abort": lambda self: setattr(self, "aborted", True), "continue_": lambda self: setattr(self, "continued", True)}})()
adapters._BrowserRequestScopeGuard("public_web", "example.com").route(body_get_route)
assert body_get_route.aborted and not body_get_route.continued

class FakeHeaders:
    def get(self, name): return None
    def items(self): return []
class OversizedResponse:
    headers = FakeHeaders()
    status = 200
    closed = False
    read_limit = None
    def read(self, limit):
        self.read_limit = limit
        return b"x" * limit
    def getcode(self): return self.status
    def geturl(self): return "http://93.184.216.34/data"
    def close(self): self.closed = True
oversized = OversizedResponse()
valid_raw_request = adapters.Request("http://93.184.216.34/data", method="GET")
raw_handler = adapters._TargetScopeRedirectHandler("public_web")
class FakeOpener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout): return self.response
class StatefulRawRequest:
    def __init__(self):
        self.url_reads = 0
        self.method_reads = 0
        self.data_reads = 0
    @property
    def full_url(self):
        self.url_reads += 1
        return "http://93.184.216.34/data" if self.url_reads == 1 else "http://127.0.0.1/admin"
    def get_method(self):
        self.method_reads += 1
        return "GET" if self.method_reads == 1 else "POST"
    @property
    def data(self):
        self.data_reads += 1
        return None if self.data_reads == 1 else b"mutate"
class CapturingOpener(FakeOpener):
    def __init__(self, response):
        super().__init__(response)
        self.observed = []
    def open(self, request, timeout):
        self.observed.append((request, request.full_url, request.get_method(), request.data, request.header_items()))
        return self.response
stateful = StatefulRawRequest()
stateful_response = OversizedResponse()
stateful_response.read = lambda limit: b"ok"
capturing_opener = CapturingOpener(stateful_response)
with patch("super_browser.adapters.build_opener", return_value=capturing_opener):
    stateful_result = adapters._open_raw_http_request(
        stateful, 1, None, adapters._TargetScopeRedirectHandler("public_web")
    )
observed_request, observed_url, observed_method, observed_data, observed_headers = capturing_opener.observed[0]
assert observed_request is not stateful
assert observed_url == "http://93.184.216.34/data" and observed_method == "GET" and observed_data is None
assert observed_headers == [("Accept", "*/*")]
assert (stateful.url_reads, stateful.method_reads, stateful.data_reads) == (1, 1, 1)
assert stateful_result.body == b"ok" and stateful_response.closed
with patch("super_browser.adapters.build_opener", return_value=FakeOpener(oversized)):
    try:
        adapters._open_raw_http_request(valid_raw_request, 1, None, raw_handler)
        raise AssertionError("oversized response escaped final helper")
    except adapters.ResponseSizeLimitError as exc:
        assert "2 MiB ceiling" in str(exc)
assert oversized.read_limit == adapters.RAW_HTTP_MAX_BYTES + 1 and oversized.closed
class DeclaredOversizedHeaders(FakeHeaders):
    def get(self, name): return str(adapters.RAW_HTTP_MAX_BYTES + 1) if name == "Content-Length" else None
declared_oversized = OversizedResponse()
declared_oversized.headers = DeclaredOversizedHeaders()
def forbidden_read(limit): raise AssertionError("body read reached after oversized Content-Length")
declared_oversized.read = forbidden_read
with patch("super_browser.adapters.build_opener", return_value=FakeOpener(declared_oversized)):
    try:
        adapters._open_raw_http_request(valid_raw_request, 1, None, adapters._TargetScopeRedirectHandler("public_web"))
        raise AssertionError("declared oversized response escaped final helper")
    except adapters.ResponseSizeLimitError as exc:
        assert "Content-Length exceeds" in str(exc)
assert declared_oversized.closed
bounded = OversizedResponse()
bounded.read = lambda limit: b"ok"
with patch("super_browser.adapters.build_opener", return_value=FakeOpener(bounded)):
    bounded_result = adapters._open_raw_http_request(valid_raw_request, 1, None, adapters._TargetScopeRedirectHandler("public_web"))
assert bounded_result.body == b"ok" and bounded_result.status == 200 and bounded_result.final_url == "http://93.184.216.34/data"
assert bounded.closed and not hasattr(bounded_result, "read")
'''
            result = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        adapter_source = (SB / "src/super_browser/adapters.py").read_text()
        self.assertNotIn('os.environ.get("DECODO_PROXY")', adapter_source)
        for marker in (
            'service_workers="block"',
            'java_script_enabled=False',
            'accept_downloads=False',
            'full_page=False',
            'RAW_HTTP_MAX_BYTES + 1',
            'playwright_public_web_non_executable',
            'route_web_socket("**/*"',
            "RTCPeerConnection",
            "WebTransport",
            "MAP * ~NOTFOUND",
            "--disable-quic",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        ):
            self.assertIn(marker, adapter_source)

    def test_super_browser_rejects_caller_proxies_and_autonomous_read_adapters(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        with tempfile.TemporaryDirectory() as state_dir:
            code = (
                "from pathlib import Path; import inspect, unittest; from urllib.request import Request; "
                "import super_browser.adapters as adapters; "
                "from super_browser.models import Plan, TaskSpec; "
                "from super_browser.router import _purpose_for, _specialist_review, build_plan, infer_task; "
                "from super_browser.runtime import create_run; "
                "import super_browser.mcp_server as mcp; "
                "from super_browser.mcp_server import PLAN_INPUT_SCHEMA; "
                "from super_browser.providers import SUPPORTED_LIVE_WORKFLOW_CLASSES, provider_readiness; "
                "from super_browser.provider_signup import PROVIDER_SIGNUP; "
                "from super_browser.setup_walkthrough import launch_setup; "
                "from super_browser.proxy import playwright_proxy_settings, proxy_dict_for_requests, resolve_proxy_url; "
                "case=unittest.TestCase(); "
                "assert 'proxy' not in PLAN_INPUT_SCHEMA['properties']; "
                "assert 'proxy' not in inspect.signature(infer_task).parameters; "
                "assert 'proxy' not in inspect.signature(create_run).parameters; "
                "forbidden={'install_super_browser_skill','init_super_browser_mcp','create_browser_profile','delete_browser_profile'}; "
                "assert not (forbidden & {item['name'] for item in mcp.TOOLS}); "
                "assert all((lambda n: (case.assertRaises(ValueError, mcp._call_tool_from_params, {'name':n,'arguments':{}}) or True))(name) for name in forbidden); "
                "assert all(not SUPPORTED_LIVE_WORKFLOW_CLASSES.get(name) for name in ('airtop','browser-use','browserbase','hyperbrowser','orgo','steel')); "
                "readiness={item['name']:item for item in provider_readiness()}; "
                "blocked_providers={'airtop','browser-use','browserbase','hyperbrowser','orgo','steel'}; "
                "assert all(_purpose_for(name, TaskSpec(goal='compare providers')).startswith('Planning/reference record only') for name in blocked_providers); "
                "reviews=[_specialist_review(name, TaskSpec(goal='compare providers'), [name], name) for name in blocked_providers]; "
                "assert all(item['recommendation']=='comparison only — non-executable' and not item['required_env'] and not item['missing_env'] for item in reviews), reviews; "
                "council=build_plan(TaskSpec(goal='scrape a public anti-bot catalog', url='https://example.com', anti_bot_risk=True, target_scope='public_web')).council_report; "
                "assert not (blocked_providers & set(council['execution_sequence'])), council; "
                "assert not (blocked_providers & set(council['selected_sequence'])), council; "
                "comparison_blocked=blocked_providers & set(council['planning_comparison_sequence']); "
                "assert len(comparison_blocked) >= 5, council; "
                "assert not council['combo_steps'] and council['execution_pattern']=='single', council; "
                "assert council['planner_decision']['primary_provider'] not in blocked_providers, council; "
                "assert comparison_blocked == set(council['planner_decision']['planning_only_providers']), council; "
                "assert not PROVIDER_SIGNUP; "
                "assert all(readiness[name]['readiness_status']=='non_executable_in_image' and not readiness[name]['configured'] and readiness[name]['configuration_status']=='not_applicable_planning_only' and not readiness[name]['usable_now'] and not readiness[name]['production_ready'] for name in blocked_providers); "
                "assert not ({item['provider'] for item in launch_setup()['provider_signup']} & set(blocked_providers)); "
                "assert 'slack' not in launch_setup()['docs']; "
                "proxies=['decodo','auto','sticky','http://127.0.0.1:8080','http://10.0.0.5:8888','https://proxy.example:443']; "
                "[(lambda task, value: (setattr(task, 'proxy', value), case.assertRaises(ValueError, resolve_proxy_url, task)))(TaskSpec(goal='read public docs'), value) for value in proxies]; "
                "assert resolve_proxy_url(TaskSpec(goal='read public docs')) is None; "
                "[case.assertRaises(ValueError, playwright_proxy_settings, value) for value in proxies]; "
                "[case.assertRaises(ValueError, proxy_dict_for_requests, value) for value in proxies]; "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://93.184.216.34/data', method='GET'), 1, 'decodo', adapters._TargetScopeRedirectHandler('public_web')); "
                "captured=[]; from types import SimpleNamespace; "
                "raw_response=SimpleNamespace(headers={}, status=200, read=lambda limit:b'ok', geturl=lambda:'http://93.184.216.34/data', close=lambda:None); "
                "adapters.build_opener=lambda *handlers: (captured.extend(handlers) or SimpleNamespace(open=lambda request, timeout: raw_response)); "
                "handler=adapters._TargetScopeRedirectHandler('public_web'); valid_request=Request('http://93.184.216.34/data', method='GET'); "
                "bounded=adapters._open_raw_http_request(valid_request, 1, None, handler); assert bounded.body==b'ok' and bounded.status==200 and not hasattr(bounded,'read'); "
                "assert captured and type(captured[0]).__name__=='ProxyHandler' and captured[0].proxies=={}, captured; "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://127.0.0.1/admin', data=b'x=1', method='POST'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://93.184.216.34/admin', method='DELETE'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://93.184.216.34/data', data=b'x=1', method='GET'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('https://example.com/data', method='GET'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://user:pass@93.184.216.34/data', method='GET'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, Request('http://[2001:4860:4860::8888]/data', method='GET'), 1, None, handler); "
                "case.assertRaises(ValueError, adapters._open_raw_http_request, valid_request, 1, None, adapters._TargetScopeRedirectHandler('loopback')); "
                "adapters.get_adapter=lambda name: (_ for _ in ()).throw(RuntimeError('adapter construction reached')); "
                f"root=Path({state_dir!r}); "
                "results=[]; "
                "[(results.append(adapters.execute_plan(Plan(task=TaskSpec(goal='summarize this public page', url='https://example.com', target_scope='public_web'), primary_provider=provider), 'run_'+provider, root))) for provider in blocked_providers]; "
                "assert all(result.status == 'blocked' and not result.verification.get('attempts') for result in results), [result.to_dict() for result in results]"
            )
            result = subprocess.run(
                [sys.executable, "-c", code], env=env, text=True, capture_output=True, check=False
            )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

        adapter_source = (SB / "src/super_browser/adapters.py").read_text()
        proxy_source = (SB / "src/super_browser/proxy.py").read_text()
        cli_source = (SB / "src/super_browser/cli.py").read_text()
        agent_contract = "\n".join(
            (SB / rel).read_text()
            for rel in (
                "README.md",
                "SKILL.md",
                "skills/super-browser-orchestrator/SKILL.md",
                "skills/browser-use-specialist/SKILL.md",
                "skills/orgo-specialist/SKILL.md",
                "references/provider-matrix.md",
                "references/routing-playbook.md",
                "references/security-and-approval-policy.md",
            )
        )
        telemetry_contract = (FILES / "local-packages/latitude-telemetry-hermes/README.md").read_text()
        self.assertIn("AUTONOMOUS_INTERACTION_PROVIDERS", adapter_source)
        self.assertIn("proxy routing is disabled in this image", proxy_source)
        self.assertNotIn('"--proxy"', cli_source)
        self.assertIn("planning/reference", agent_contract)
        self.assertIn("blocked before adapter construction", agent_contract)
        self.assertNotIn("editable mode", telemetry_contract)
        self.assertNotIn("editable fork", telemetry_contract)
        self.assertNotIn("playwright install chromium", agent_contract)
        self.assertNotIn("python3 -m playwright install chromium", agent_contract)
        self.assertIn(".pth", telemetry_contract)
        self.assertIn(".dist-info", telemetry_contract)

    def test_payload_contains_skill_vendor_and_vault_seed(self):
        setup = self.builder.template["apps"][0]["install"]
        self.assertIn("agent-knowledge", setup)
        self.assertIn("super-browser", setup)
        inline = "\n".join(item.get("inline", "") for item in self.builder.template["files"])
        supplied_key = os.environ.get("ORGO_API_KEY", "")
        if supplied_key:
            self.assertNotIn(supplied_key, inline)

    def test_payload_ships_only_curated_revenue_partner_skill(self):
        payload = next(item for item in self.builder.template["files"] if item["to"].endswith("payload.tgz.b64"))
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(payload["inline"])), mode="r:gz") as archive:
            skill_files = {
                member.name
                for member in archive.getmembers()
                if member.name.startswith("hermes/skills/") and member.name.endswith("/SKILL.md")
            }
        self.assertEqual(skill_files, {"hermes/skills/go-to-market/revenue-partner/SKILL.md"})

    def test_payload_excludes_local_python_build_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            files_root = Path(directory)
            package = files_root / "local-packages/super-browser"
            (package / "src/super_browser").mkdir(parents=True)
            (package / "src/super_browser/runtime.py").write_text("SAFE = True\n")
            (package / "build/lib/super_browser").mkdir(parents=True)
            (package / "build/lib/super_browser/runtime.py").write_text("STALE = True\n")
            (package / "src/super_browser.egg-info").mkdir(parents=True)
            (package / "src/super_browser.egg-info/PKG-INFO").write_text("generated\n")
            (files_root / "npm-build/node_modules/example").mkdir(parents=True)
            (files_root / "npm-build/node_modules/example/index.js").write_text("stale\n")
            previous = getattr(self.builder, "FILES")
            setattr(self.builder, "FILES", str(files_root))
            try:
                archive = base64.b64decode(self.builder.payload_b64())
            finally:
                setattr(self.builder, "FILES", previous)
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as payload:
                names = payload.getnames()
            # Super Browser is no longer vendored; the latitude plugin is the
            # remaining local package and carries the same exclusion contract.
            self.assertFalse(
                any(name.startswith("hermes/local-packages/super-browser/") for name in names),
                "the vendored Super Browser must not reappear in the payload",
            )
            self.assertTrue(
                any(name.startswith("hermes/local-packages/latitude-telemetry-hermes/")
                    for name in names),
                names,
            )
            self.assertFalse(
                any("/build/" in name or ".egg-info/" in name or "/node_modules/" in name for name in names),
                names,
            )

    def test_agentphone_is_deny_by_default_and_cannot_enable_full_tools(self):
        bridge = (FILES / "agentphone-bridge/agentphone_bridge.py").read_text()
        bridge_env = (FILES / "agentphone-bridge/env").read_text()
        endpoint_inputs = (
            (FILES / "safe-env-bridge.py").read_text()
            + (FILES / "hermes.env").read_text()
            + (FILES / "config.yaml").read_text()
        )
        self.assertNotIn("HERMES_YOLO_MODE", bridge_env)
        self.assertNotIn("FULL_HERMES_TOOLSETS", bridge + bridge_env)
        self.assertNotIn('"all"', bridge_env)
        self.assertIn("if not allowed or sender not in allowed", bridge)
        self.assertIn('(\"web\", \"vision\")', bridge)
        self.assertIn("AgentPhone network execution is non-executable in this immutable image", bridge)
        self.assertNotIn("public https image URL", bridge)
        self.assertIn("approved generated local file", bridge)
        self.assertNotIn("AGENTPHONE_BASE_URL", endpoint_inputs)
        self.assertIn('API_BASE = "https://api.agentphone.ai"', bridge)
        self.assertIn("AGENTPHONE_EXECUTION_AVAILABLE = False", bridge)
        self.assertIn("def deny_agentphone_execution()", bridge)
        self.assertIn("deny_agentphone_execution()", bridge)
        self.assertIn("return 78", bridge)
        self.assertIn("validate_agentphone_base_url(API_BASE)", bridge)
        self.assertIn("NoRedirectHandler", bridge)
        self.assertIn("authorized_reply_target(fields, allowed)", bridge)
        self.assertIn('"ignored": "group audience not allowlisted"', bridge)

        bridge_runner = (FILES / "agentphone-bridge-run.sh").read_text()
        self.assertIn("exec sleep infinity", bridge_runner)
        self.assertIn("non-executable in this image", bridge_runner)
        self.assertNotIn("AGENTPHONE_API_KEY", bridge_runner)
        self.assertNotIn("agentphone_bridge.py", bridge_runner)

    def test_shipped_capability_guidance_matches_immutable_image(self):
        roots = [ROOT / "README.md", LEGACY_README, ROOT / "docs", FILES]
        texts: list[str] = []
        for root in roots:
            paths = [root] if root.is_file() else root.rglob("*")
            for path in paths:
                if not path.is_file() or path.suffix not in {".html", ".md", ".py", ".sh", ".yaml", ".yml"}:
                    continue
                texts.append(path.read_text(errors="ignore"))
        shipped_text = "\n".join(texts)
        for stale_guidance in (
            "Power-ups — add any of these at any time",
            "Keys land automatically: parked MCP servers revive",
            "the webhook bridge starts on the next resume",
            "Readiness requires operator-configured credentials",
            "after an Orgo image is built and providers are ready",
            "the Orgo desktop plugin is also disabled",
            "MCP and CLI proxy inputs are enum-restricted",
            "geo-targeted proxy scrape experiments",
        ):
            self.assertNotIn(stale_guidance, shipped_text)
        readme = LEGACY_README.read_text()
        security = (ROOT / "docs/SECURITY_MODEL.md").read_text()
        operator = (ROOT / "docs/OPERATOR_GUIDE.md").read_text()
        onboarding = (FILES / "onboard.sh").read_text()
        self.assertIn("removed by the exact-version image-build pruner", readme)
        self.assertIn("direct network helpers are hard-stopped", readme)
        self.assertIn("Release-listed Orgo, Composio, AgentMail, AgentPhone, AgentCard, and X", security)
        self.assertIn("removed Orgo Desktop plugin/client/CLI also does not ship", operator)
        self.assertIn("Credentials and restarts cannot enable them", onboarding)
        self.assertNotIn("hermes mcp login", onboarding)

        self.assertEqual(
            {item["name"] for item in self.builder.template["secrets"]},
            {
                "op_service_account_token",
                "latitude_api_key",
                "latitude_project",
                "telegram_bot_token",
                "telegram_allowed_users",
            },
        )
        config = yaml.safe_load((FILES / "config.yaml").read_text())
        self.assertEqual(
            set(config["secrets"]["onepassword"]["env"]),
            {
                "LATITUDE_API_KEY",
                "TELEGRAM_BOT_TOKEN",
                "XAI_API_KEY",
                "OPENROUTER_API_KEY",
                "AI_GATEWAY_API_KEY",
                "MODEL_API_KEY",
            },
        )

    def test_unknown_intents_and_authenticated_profiles_fail_closed(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from super_browser.models import TaskSpec; "
                "from super_browser.policy import approval_required,infer_risk; "
                "mutation='Choose the pencil beside the headline, replace its contents with Security Researcher, and use the blue confirmation control.'; "
                "assert infer_risk(mutation) == 'mutating', infer_risk(mutation); "
                "assert infer_risk('Perform the requested operation in the account dashboard') == 'mutating'; "
                "assert infer_risk('Navigate to https://example.com and extract the public pricing table') == 'read'; "
                "auth=TaskSpec(goal='Open the account dashboard and inspect the headline', requires_auth=True, profile='existing'); "
                "assert approval_required(auth); "
                "print('fail_closed_policy_ok')",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SB / "src")},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("fail_closed_policy_ok", result.stdout)
        with tempfile.TemporaryDirectory() as state_dir:
            profile_code = r'''
import json
import os
import sqlite3
from pathlib import Path
from super_browser.profiles import ProfileStore
from super_browser.runtime import create_run

path = Path(os.environ["SUPER_BROWSER_STATE_DIR"]) / "profiles.sqlite"
path.parent.mkdir(parents=True, exist_ok=True)
payload = json.dumps({"name": "operator-profile", "preferred_provider": "playwright"})
with sqlite3.connect(path) as conn:
    conn.execute("CREATE TABLE profiles (name TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO profiles VALUES (?, ?, ?, ?)", ("operator-profile", payload, "operator", "operator"))

store = ProfileStore(create=False)
assert store.get("operator-profile") is not None
for call in (
    lambda: ProfileStore(create=True),
    lambda: store.create("new-profile"),
    lambda: store.delete("operator-profile"),
    lambda: store.bind_provider_id("operator-profile", "playwright", "remote"),
):
    try:
        call()
    except PermissionError:
        pass
    else:
        raise AssertionError("profile mutation surface did not fail closed")

run = create_run("Inspect the current account page", profile="operator-profile", execute=True)
assert run.status == "awaiting_approval", run.status
assert not any(event.get("type") == "execution_started" for event in run.events)
print("profile_execution_blocked")
'''
            profile_result = subprocess.run(
                [sys.executable, "-c", profile_code],
                cwd=ROOT,
                env={
                    **os.environ,
                    "PYTHONPATH": str(SB / "src"),
                    "SUPER_BROWSER_STATE_DIR": state_dir,
                },
                capture_output=True,
                text=True,
                check=True,
            )
        self.assertIn("profile_execution_blocked", profile_result.stdout)

    def test_direct_hosted_provider_helpers_fail_before_client_construction(self):
        code = r'''
import asyncio
from super_browser.adapters import BrowserUseAdapter, _browser_use_profile_id, _http_json, _orgo_resolve_computer_id, _url_host_is_public_ip_literal, _validated_chromium_host_pin, get_adapter
from super_browser.models import TaskSpec

task = TaskSpec(goal="read public page")
assert _url_host_is_public_ip_literal("https://93.184.216.34/")
assert not _url_host_is_public_ip_literal("https://[2606:4700:4700::1111]/")
try:
    _validated_chromium_host_pin("https://[2606:4700:4700::1111]/")
except ValueError:
    pass
else:
    raise AssertionError("IPv6 literal escaped the IPv4-only Chromium pin contract")
for call in (
    lambda: _browser_use_profile_id(task),
    lambda: _orgo_resolve_computer_id("https://invalid.example", {"Authorization": "secret"}, 30),
):
    try:
        call()
    except RuntimeError as exc:
        assert "planning-only" in str(exc)
    else:
        raise AssertionError("direct hosted helper did not fail closed")

class TrapClient:
    def __init__(self):
        raise AssertionError("hosted client was constructed")

try:
    asyncio.run(BrowserUseAdapter()._run_browser_use(TrapClient, task))
except RuntimeError as exc:
    assert "planning-only" in str(exc)
else:
    raise AssertionError("direct Browser Use runner did not fail closed")
for provider in ("airtop", "browser-use", "browserbase", "hyperbrowser", "orgo", "steel"):
    try:
        get_adapter(provider)
    except RuntimeError as exc:
        assert "planning/provenance" in str(exc)
    else:
        raise AssertionError(f"hosted adapter factory constructed {provider}")
try:
    _http_json("https://attacker.example/mutate", {"write": True}, {"Authorization": "Bearer secret"})
except RuntimeError as exc:
    assert "HTTP construction is disabled" in str(exc)
else:
    raise AssertionError("hosted HTTP helper remained callable")
print("direct_hosted_helpers_blocked")
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTHONPATH": str(SB / "src")},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("direct_hosted_helpers_blocked", result.stdout)

    def test_production_approval_requires_host_confirmation_and_is_not_agent_self_service(self):
        config_source = (FILES / "config.yaml").read_text()
        config = yaml.safe_load(config_source)
        self.assertEqual(config["approvals"]["mode"], "manual")
        self.assertTrue(config["approvals"]["mcp_reload_confirm"])
        self.assertTrue(config["approvals"]["destructive_slash_confirm"])
        self.assertFalse(config["hooks_auto_accept"])
        for connector in ("orgo", "composio", "agentmail", "agentphone", "agent-cards", "linear"):
            self.assertNotIn(connector, config["mcp_servers"], connector)
        self.assertNotIn("spotify", config["plugins"]["enabled"])
        self.assertNotIn("known_plugin_toolsets", config)
        self.assertNotIn("orgo-desktop-local", config["plugins"]["enabled"])
        self.assertNotIn("orgo_desktop", config_source)
        # `cli` is reached only through the authenticated Orgo API and needs a
        # working toolset for the agent to do anything. Every *inbound* chat
        # platform stays read-only; widening cli must never widen those.
        # `cli` (authenticated Orgo API) and `slack` (operator-connected channel,
        # trusted workspace) carry the working set. Every other inbound platform
        # stays read-only, so widening these two cannot widen the rest.
        safe_remote_toolsets = {"session_search"}
        working_toolsets = {
            "session_search", "super-browser", "scrape-creators",
            "skills", "memory", "file", "todo",
        }
        platform_toolsets = config["platform_toolsets"]
        operator_channels = {"cli", "slack"}
        for name in operator_channels:
            self.assertEqual(set(platform_toolsets[name]), working_toolsets, name)
        for name, toolsets in platform_toolsets.items():
            if name in operator_channels:
                continue
            self.assertEqual(set(toolsets), safe_remote_toolsets, name)
        self.assertGreaterEqual(
            len(platform_toolsets) - len(operator_channels), 8,
            "most inbound platforms must remain read-only",
        )
        # The dangerous surfaces stay off every platform, cli included.
        for platform, toolsets in platform_toolsets.items():
            for forbidden in ("terminal", "code_execution", "delegation", "computer_use"):
                self.assertNotIn(forbidden, toolsets, f"{platform}/{forbidden}")
        self.assertNotIn("browser-browser-use", config["plugins"]["enabled"])
        self.assertNotIn("browser-firecrawl", config["plugins"]["enabled"])
        self.assertIn("browser-browser-use", config["plugins"]["disabled"])
        self.assertIn("browser-firecrawl", config["plugins"]["disabled"])
        for plugin_name in ("web-exa", "web-xai", "web/firecrawl"):
            self.assertNotIn(plugin_name, config["plugins"]["enabled"])
            self.assertIn(plugin_name, config["plugins"]["disabled"])
        for removed_research_mcp in ("vidiq", "x-docs", "xapi", "xapi-app-only", "ideabrowser"):
            self.assertNotIn(removed_research_mcp, config["mcp_servers"])
        self.assertFalse((FILES / "plugins/orgo-desktop-local").exists())
        self.assertFalse((FILES / "scripts/orgo_desktop").exists())
        self.assertFalse((SB / "src/super_browser/fleet.py").exists())
        builder_source = (ROOT / "build_template.py").read_text()
        readme_source = (ROOT / "README.md").read_text()
        self.assertNotIn("orgo-desktop-local", builder_source + readme_source)
        runtime_source = (SB / "src/super_browser/runtime.py").read_text()
        adapter_source = (SB / "src/super_browser/adapters.py").read_text()
        cli_source = (SB / "src/super_browser/cli.py").read_text()
        mcp_source = (SB / "src/super_browser/mcp_server.py").read_text()
        fleet_surface_text = "\n".join(path.read_text(errors="ignore") for path in (SB / "src/super_browser").glob("*.py"))
        for removed_fleet_surface in ("fleet_size", "fleet_index", "create_fleet_runs", 'add_argument("--fleet"'):
            self.assertNotIn(removed_fleet_surface, fleet_surface_text)
        setup_helpers = (SB / "src/super_browser/setup_helpers.py").read_text()
        self.assertNotIn("http://www.google.com", builder_source)
        self.assertNotIn("date -s", builder_source)
        self.assertIn("age_seconds < 0 or age_seconds > ttl_seconds", runtime_source)
        self.assertIn("local production approval is disabled", runtime_source)
        self.assertNotIn('add_parser("approve"', cli_source)
        self.assertNotIn("approve_run(", cli_source)
        self.assertFalse((SB / "src/super_browser/agent.py").exists())
        for removed_surface in (
            'add_parser("install-skill"',
            'add_parser("init-mcp"',
            'add_parser("agent"',
            'add_parser("create"',
            'add_parser("delete"',
        ):
            self.assertNotIn(removed_surface, cli_source)
        for removed_helper in ("install_skill_bundle", "write_mcp_config", "_merged_mcp_config"):
            self.assertNotIn(removed_helper, setup_helpers)
        self.assertNotIn("run_slack_daemon", mcp_source + cli_source)
        packaged_text = config_source + "\n" + "\n".join(
            path.read_text(errors="ignore")
            for path in SB.rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".sh", ".yaml", ".yml", ".json"}
        )
        self.assertNotIn("super-browser approve", packaged_text)
        self.assertNotIn("SUPER_BROWSER_SLACK_EXECUTE", packaged_text)
        self.assertNotIn("Use create_run plus approve/resume", packaged_text)
        self.assertIn("separately reviewed operator-controlled integration and rebuilt release", adapter_source)
        for stale_instruction in (
            "Plan, run, approve, resume",
            "JSON tools: plan, run, approve",
            "you `approve` with reason",
            "(`plan`, `run`, `profiles`, `approve`, `fleet`, `doctor`)",
            "plan/run/approve/verify",
            "resume or approve with execute",
        ):
            self.assertNotIn(stale_instruction, packaged_text, stale_instruction)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SB / "src")
        result = subprocess.run(
            [sys.executable, "-c", "from super_browser.mcp_server import TOOL_INPUT_SCHEMAS; assert 'approve_browser_run' not in TOOL_INPUT_SCHEMAS"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_metadata_does_not_point_to_base_template(self):
        self.assertNotIn("source", self.builder.template["template"])

    def test_shell_checker_rejects_malformed_embedded_template_program(self):
        checker = ROOT / ".github/scripts/check_shell_syntax.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            scripts = repo / ".github/scripts"
            scripts.mkdir(parents=True)
            (scripts / "check_shell_syntax.py").write_text(checker.read_text())
            (repo / "build_template.py").write_text(
                "template = {\n"
                "    'apps': [{'install': 'set -e\\nprintf ok\\n'}],\n"
                "    'hooks': {\n"
                "        'on_first_boot': 'exit 0',\n"
                "        'on_resume': 'if then\\n',\n"
                "        'on_every_boot': 'exit 0',\n"
                "    },\n"
                "}\n"
            )
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            result = subprocess.run(
                [sys.executable, ".github/scripts/check_shell_syntax.py"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("template.hooks.on_resume", result.stderr)

    def test_ci_and_release_docs_use_one_locked_verification_entrypoint(self):
        verifier = ROOT / ".github/scripts/verify_release"
        self.assertTrue(verifier.is_file())
        command = "bash .github/scripts/verify_release"
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn(f"run: {command}", workflow)
        self.assertIn("REVENUE_PARTNER_VERIFY_PYTHON: ${{ env.pythonLocation }}/bin/python", workflow)
        for guide in (
            LEGACY_README,
            ROOT / "CONTRIBUTING.md",
            ROOT / "docs/DEPLOYMENT.md",
            ROOT / "docs/VERIFICATION.md",
        ):
            text = guide.read_text()
            self.assertIn(command, text, str(guide))
            self.assertIn("REVENUE_PARTNER_VERIFY_PYTHON=/absolute/path/to/trusted/python3.11", text, str(guide))
            self.assertNotIn("--with jsonschema --with certifi", text, str(guide))
        verify_env = {**os.environ, "REVENUE_PARTNER_VERIFY_PYTHON": sys.executable}
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "forged-ran"
            fake = Path(directory) / "python3.11"
            fake.write_text(f"#!/bin/sh\ntouch {shlex.quote(str(marker))}\nexit 0\n")
            fake.chmod(0o755)
            hostile_env = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}"}
            hostile_env.pop("REVENUE_PARTNER_VERIFY_PYTHON", None)
            rejected = subprocess.run(
                ["bash", str(verifier), "--list"], cwd=ROOT, env=hostile_env, text=True, capture_output=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertIn("set REVENUE_PARTNER_VERIFY_PYTHON", rejected.stderr)
        result = subprocess.run(
            ["bash", str(verifier), "--list"],
            cwd=ROOT,
            env=verify_env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in (
            "pip --require-hashes requirements-ci.lock",
            "candidate index YAML parse",
            "candidate skill frontmatter parse",
            "candidate index credential scan",
            "exact candidate tree parity",
            "markdown links/assets",
            "revenue partner tests",
            "latitude telemetry tests",
            "agentphone tests",

            "python compile",
            "tracked and embedded shell syntax",
            "template schema assembly",
        ):
            self.assertIn(marker, result.stdout)

        target = ROOT / "README.md"
        original = target.read_bytes()
        try:
            target.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            mutated = subprocess.run(
                ["bash", str(verifier), "--list"],
                cwd=ROOT,
                env=verify_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(mutated.returncode, 0)
            self.assertIn("tracked worktree bytes differ", mutated.stderr)
        finally:
            target.write_bytes(original)

        untracked = FILES / "untracked-payload-probe.txt"
        try:
            untracked.write_text("must be rejected\n")
            extra = subprocess.run(
                ["bash", str(verifier), "--list"],
                cwd=ROOT,
                env=verify_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(extra.returncode, 0)
            self.assertIn("untracked non-ignored files", extra.stderr)
        finally:
            untracked.unlink(missing_ok=True)

    def test_super_browser_live_test_and_handoff_surfaces_fail_closed_truthfully(self):
        code = r'''
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from super_browser.cli import _live_test_exit_code
from super_browser.handoff import _next_steps, _resume_state
from super_browser.live_tests import _run_playwright_fixture

captured = {}
def fake_create_run(goal, **kwargs):
    captured["url"] = kwargs["url"]
    captured["allowlist"] = json.loads(os.environ["SUPER_BROWSER_TEST_TARGET_ALLOWLIST_JSON"])
    return SimpleNamespace(
        status="complete",
        run_id="fixture-run",
        verification={"status": "verified"},
        artifacts=[],
        events=[],
    )

with patch("super_browser.live_tests.create_run", fake_create_run):
    result = _run_playwright_fixture()
assert result["status"] == "passed", result
assert captured["url"].startswith("http://127.0.0.1:"), captured
assert captured["allowlist"] == [captured["url"]], captured

assert _live_test_exit_code({"status": "passed"}) == 0
assert _live_test_exit_code({"status": "failed"}) != 0
assert _live_test_exit_code({"status": "partial"}) != 0
assert _live_test_exit_code({"status": "skipped"}) != 0

verification = {
    "policy_guard": {"approval_required": True},
    "plan_integrity": {"status": "verified"},
    "approval_integrity": {"status": "verified"},
    "approval_expiry": {"status": "expired"},
    "write_retry_guard": {"external_write_retry_non_executable": True},
    "failures": [],
}
resume = _resume_state({"status": "approved"}, {"pending": False}, verification)
assert resume["safe_to_resume"] is False, resume
assert resume["will_execute_provider"] is False, resume
assert "cannot resume" in resume["reason"].lower(), resume
steps = _next_steps({"status": "approved"}, {}, {"pending": False}, verification)
joined = " ".join(steps).lower()
assert "cannot resume" in joined, steps
for stale in ("resume the approved run", "resolve the pending approval", "resume will create a fresh approval"):
    assert stale not in joined, steps
print("live_test_and_handoff_truth_ok")
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SB / "src")},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("live_test_and_handoff_truth_ok", result.stdout)

        shipped = "\n".join(
            path.read_text(errors="ignore")
            for root in (SB, ROOT / "docs")
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".py"}
        ).lower()
        for stale in (
            "resume the approved run",
            "resolve the pending approval before execution",
            "create an approved run for",
            "adapter checks structured, fingerprint-bound approval before provider construction/execution",
            "fresh approval is required",
            "pending retry approval",
        ):
            self.assertNotIn(stale, shipped)

    def test_shipped_template_has_no_base_runtime_identity(self):
        rendered = str(self.builder.template)
        for legacy in ("nicks-stack", "Dewey", "Minions", "Hubert"):
            self.assertNotIn(legacy, rendered)
        self.assertIn("/opt/revenue-partner/stage", rendered)
        self.assertIn("revenue-partner-onboard-launch.sh", rendered)

    def test_readme_qualifies_campaign_enforcement_boundary(self):
        readme = LEGACY_README.read_text()
        self.assertIn("Hard runtime gating is implemented in Super Browser and the AgentPhone bridge", readme)
        self.assertIn("rather than a claimed universal campaign-record gate", readme)


if __name__ == "__main__":
    unittest.main()


class RuntimeLockConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()

    """Locks installed into one venv must not disagree.

    The install script pip-installs `build-locks/hermes-runtime.lock` and then
    the packaged Super Browser's `requirements-runtime.lock` into the *same*
    interpreter. Both are hash-locked, so each looks deterministic in isolation,
    but the second install silently upgrades anything the first pinned lower --
    last writer wins. That is how `mcp` reached 2.0.0 in a runtime whose agent
    pins `mcp==1.26.0`, which broke every HTTP MCP connection at image-build
    time and could not be seen by any test that reads a single lock.
    """

    @staticmethod
    def _pins(path):
        pins = {}
        for line in pathlib.Path(path).read_text().splitlines():
            match = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", line.strip())
            if match:
                pins[match.group(1).lower().replace("_", "-")] = match.group(2)
        return pins

    def test_install_program_installs_exactly_one_runtime_lock(self):
        """Only one dependency lock may be installed into the agent's venv.

        Two hash-locked files each look deterministic alone; installed
        sequentially into one interpreter the second silently upgrades whatever
        the first pinned lower. That is how `mcp` reached 2.0.0 in a runtime
        whose agent pins `mcp==1.26.0`, breaking every HTTP MCP connection at
        image-build time -- invisible to any check that reads a single lock.
        """
        install = self.builder.INSTALL
        installed = set(re.findall(r"--require-hashes -r ([^\s\\]+)", install))
        self.assertEqual(
            {name.rsplit("/", 1)[-1] for name in installed},
            {"hermes-runtime.lock"},
            f"exactly one runtime lock may reach the venv; found {sorted(installed)}",
        )
        self.assertNotIn("requirements-runtime.lock", install)

    def test_retired_vendored_locks_are_not_shipped(self):
        """A lock that is no longer installed must also not ride in the payload."""
        archive = base64.b64decode(self.builder.payload_b64())
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as payload:
            names = payload.getnames()
        self.assertFalse(
            [n for n in names if n.endswith("requirements-runtime.lock")],
            "the vendored Super Browser lock must not ship in the payload",
        )

    def test_agent_runtime_pin_matches_the_declared_requirement(self):
        hermes = self._pins(FILES / "build-locks/hermes-runtime.lock")
        self.assertEqual(hermes.get("mcp"), "1.26.0", "hermes-agent 0.18.0 pins mcp==1.26.0 exactly")


class GatewayLauncherTests(unittest.TestCase):
    """The supervised launcher must never park silently on a stale lock.

    `flock` with no timeout blocks forever behind an orphaned holder while
    supervisord reports the parked process as RUNNING. Field-observed: an
    orphaned gateway held the lock for two days, every restart was a silent
    no-op, and config changes appeared to deploy while the live gateway never
    saw them. A dead gateway must not look healthy.
    """

    def test_gateway_lock_wait_is_bounded_and_reports_failure(self):
        launcher = (FILES / "gateway-run.sh").read_text()
        self.assertIn("flock", launcher)
        self.assertRegex(
            launcher,
            r"flock\s+-w\s+\d+",
            "flock must use a bounded -w timeout; an unbounded wait parks forever "
            "behind a stale holder and supervisord reports it as healthy",
        )
        self.assertRegex(
            launcher, r"-E\s+\d+",
            "flock needs a distinct conflict exit code so a stuck lock is "
            "distinguishable from a gateway crash",
        )

    def test_gateway_launcher_still_serializes_starts(self):
        """The boot-race guard must survive the timeout change."""
        launcher = (FILES / "gateway-run.sh").read_text()
        self.assertIn("/var/lib/orgo/hermes-gateway.lock", launcher)
        self.assertIn("hermes gateway run", launcher)
        self.assertIn("--replace", launcher)

    def test_gateway_launcher_reaps_orphaned_gateways(self):
        """A gateway orphaned by a previous supervisor cycle must be reaped.

        `flock` forks rather than execs, so the gateway runs as its child and
        inherits the lock fd. If the wrapper dies and the gateway does not, the
        orphan holds a lock that supervisord no longer owns and every
        subsequent start blocks behind it. Only PPID 1 is reaped: a gateway
        still parented to a live supervisord is a legitimate sibling that
        `--replace` should handle.
        """
        launcher = (FILES / "gateway-run.sh").read_text()
        self.assertIn("pgrep -f 'hermes gateway run'", launcher)
        self.assertRegex(launcher, r"ppid=\$\(ps -o ppid= -p", "must read the parent pid")
        self.assertIn('"$ppid" = "1"', launcher)
        self.assertIn("kill -9", launcher)
        # The reaper must run BEFORE the lock is contended, or it cannot help.
        # Anchor on the actual invocation, not the word "flock" in the comments
        # that explain it.
        invocation = launcher.index("exec /usr/local/bin/revenue-partner-env-bridge")
        self.assertLess(
            launcher.index("pgrep -f 'hermes gateway run'"),
            invocation,
            "the orphan reaper must run before flock contends for the lock",
        )


class ScheduledWorkTests(unittest.TestCase):
    """The daily loop must ship with the image, not be a manual post-install step.

    A rebuilt box that boots without its daily brief is a silently inert agent:
    it answers when spoken to and never initiates anything. That is the failure
    this template keeps guarding against, so the schedule belongs in the boot
    hook rather than in an operator's runbook.
    """

    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()

    def test_daily_brief_is_scheduled_at_boot_and_is_idempotent(self):
        hook = self.builder.ON_EVERY_BOOT
        self.assertIn("hermes cron create", hook)
        self.assertIn("Revenue Partner Daily Brief", hook)
        # Matched by name so a resume cannot duplicate the job.
        self.assertIn("hermes cron list", hook)
        self.assertRegex(hook, r"grep -qF .*BRIEF_NAME")

    def test_daily_brief_delivers_to_the_configured_home_channel(self):
        hook = self.builder.ON_EVERY_BOOT
        self.assertIn("SLACK_HOME_CHANNEL", hook)
        self.assertIn("slack:${HOME_CHANNEL}", hook)
        # With no home channel there is nowhere to report, so skip rather than
        # create a job that delivers into the void.
        self.assertIn('[ -n "$HOME_CHANNEL" ]', hook)

    def test_cron_state_is_never_baked_into_the_payload(self):
        """jobs.json carries ids, run state and next-run timestamps."""
        archive = base64.b64decode(self.builder.payload_b64())
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as payload:
            names = payload.getnames()
        self.assertFalse(
            [n for n in names if n.endswith("jobs.json")],
            "cron run state must not ship in the image",
        )

    def test_daily_brief_prompt_forbids_fabrication(self):
        prompt = (FILES / "daily-brief.prompt").read_text()
        self.assertIn("never infer", prompt)
        self.assertIn("Do not fabricate", prompt)
        self.assertIn("If you did no work, say so", prompt)


class ModelChainTests(unittest.TestCase):
    """The model chain must be declared, ordered, and reachable.

    `fallback_providers` is Hermes's primary source of truth for failover and is
    walked in order. A typo'd model id here fails only at the moment the primary
    is already down, which is the worst time to discover it.
    """

    EXPECTED_CHAIN = [
        "deepseek/deepseek-v4-pro",
        "openai/gpt-5.6-luna",
        "minimax/minimax-m3",
    ]

    def setUp(self):
        self.config = yaml.safe_load((FILES / "config.yaml").read_text())

    def test_primary_is_glm_52_on_openrouter(self):
        self.assertEqual(self.config["model"]["default"], "z-ai/glm-5.2")
        self.assertEqual(self.config["model"]["provider"], "openrouter")

    def test_fallback_chain_is_ordered_as_configured(self):
        chain = [f["model"] for f in self.config["fallback_providers"]]
        self.assertEqual(chain, self.EXPECTED_CHAIN)

    def test_every_chain_entry_uses_openrouter_and_the_bridged_key(self):
        for entry in self.config["fallback_providers"]:
            self.assertEqual(entry["base_url"], "https://openrouter.ai/api/v1", entry)
            self.assertEqual(entry["key_env"], "OPENROUTER_API_KEY", entry)

    def test_no_unpublished_model_snapshot_is_used(self):
        """`deepseek-v4-pro-0423` was requested but does not exist on OpenRouter.

        Pinning a snapshot that was never published breaks failover silently, at
        the moment the primary is already down. The id may appear in a comment
        explaining its absence -- it must never appear as a model VALUE.
        """
        values = [self.config["model"]["default"]]
        values += [f["model"] for f in self.config["fallback_providers"]]
        for value in values:
            self.assertNotIn("0423", value, f"unpublished snapshot pinned: {value}")

    def test_transport_key_survives_the_bridge(self):
        bridge = (FILES / "safe-env-bridge.py").read_text()
        self.assertIn("OPENROUTER_API_KEY", bridge)
