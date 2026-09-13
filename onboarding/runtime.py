"""Native and Compose adapters; secrets are passed through private files only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import shutil

from .storage import SetupError, State, read_env, read_json, update_env, private_write


class Runtime:
    def __init__(self, root: Path, deployment: Path | None = None, home: Path | None = None, config: Path | None = None):
        self.root = root.resolve()
        self.role = read_json(self.root / "onboarding/role.json")
        self.kind = self.role["runtime"]
        self.source_config = (config or self.root / "agent.env").expanduser().resolve()
        if self.kind == "compose":
            record = Path.home() / ".config/ai-guy-agent" / (self.role["id"] + ".json")
            saved = read_json(record)
            env = read_env(self.source_config)
            default = str(Path.home() / "agents" / self.role["id"])
            self.deployment = (deployment or Path((env.get("BASE_DIR") if config else saved.get("deployment_dir")) or env.get("BASE_DIR") or default)).expanduser().resolve()
            self.home = home or self.deployment / "hermes/data"
            if home and home.expanduser().resolve() != self.deployment / "hermes/data":
                raise SetupError("Use a separate Docker deployment for an independently connected agent; worker credentials must not enter the root environment.")
            self.env_file = self.deployment / ".env"
        else:
            self.deployment = root
            self.home = home or Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
            self.env_file = self.home / ".env"
        self.home = self.home.expanduser().resolve()
        self.state = State(self.home, self.role["id"])

    def compose(self) -> list[str]:
        return ["docker", "compose", "--env-file", str(self.env_file), "-f", str(self.deployment / "compose.yml")]

    def run(self, command: list[str], *, interactive=False, input_text=None, timeout=120, check=True, extra_env=None):
        env = os.environ.copy()
        env.update(extra_env or {})
        if self.kind == "native":
            env["HERMES_HOME"] = str(self.home)
        try:
            result = subprocess.run(command, cwd=self.deployment if self.deployment.exists() else self.root, env=env, text=True,
                                    input=input_text, capture_output=not interactive, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise SetupError("The setup command could not finish. Existing private data was preserved.") from None
        if check and result.returncode:
            raise SetupError("The connection check failed. Reconnect the service or resume setup later.")
        return result

    def hermes(self, *args, interactive=False, **kwargs):
        prefix = [*self.compose(), "exec"] if self.kind == "compose" else []
        if prefix and not interactive:
            prefix.append("-T")
        if prefix:
            prefix.append("hermes")
        return self.run([*prefix, "hermes", *map(str, args)], interactive=interactive, **kwargs)

    def get(self, key: str):
        path = self.home / "config.yaml"
        if not path.exists():
            return None
        import yaml
        try:
            value = yaml.safe_load(path.read_text()) or {}
            for component in key.split("."):
                if not isinstance(value, dict):
                    return None
                value = value.get(component)
            return value
        except (ValueError, yaml.YAMLError):
            raise SetupError("The existing runtime configuration needs repair; it was preserved.") from None

    def set(self, key: str, value) -> None:
        # Private settings never enter a command's argument list.
        import yaml
        path = self.home / "config.yaml"
        try:
            config = yaml.safe_load(path.read_text()) if path.exists() else {}
            if not isinstance(config, dict):
                raise ValueError()
            target = config
            parts = key.split(".")
            for component in parts[:-1]:
                target = target.setdefault(component, {})
                if not isinstance(target, dict):
                    raise ValueError()
            target[parts[-1]] = value
            private_write(path, yaml.safe_dump(config, sort_keys=False))
        except (ValueError, yaml.YAMLError):
            raise SetupError("The existing runtime configuration needs repair; it was preserved.") from None

    def command(self, *args, **kwargs):
        prefix = [*self.compose(), "exec", "-T", "hermes"] if self.kind == "compose" else []
        return self.run([*prefix, *args], **kwargs)

    def env(self) -> dict[str, str]:
        return read_env(self.env_file)

    def save_env(self, values: dict[str, str]) -> None:
        update_env(self.env_file, values)

    def restart(self) -> None:
        if self.kind == "compose":
            self.run([*self.compose(), "up", "-d", "--force-recreate", "hermes"], timeout=180)
        else:
            self.hermes("gateway", "restart", timeout=90)

    def health(self) -> bool:
        return self.hermes("gateway", "status", check=False).returncode == 0

    def pinned(self) -> bool:
        if self.kind == "compose":
            container = self.run([*self.compose(), "ps", "-q", "hermes"]).stdout.strip()
            if not container:
                return False
            reference = self.run(["docker", "inspect", "--format", "{{.Config.Image}}", container]).stdout.strip()
            return reference == "nousresearch/hermes-agent:v2026.9.11@sha256:9469b3e78b9545b6d576eb8887a95352e9a0ea83730eaf31431cf862ca1010e1"
        binary = shutil.which("hermes")
        if not binary:
            return False
        resolved = Path(binary).resolve()
        candidates = [Path("/usr/local/lib/hermes-agent"), self.home / "hermes-agent"]
        for root in candidates:
            if (root / ".git").exists() and (resolved.is_relative_to(root) or str(root) in resolved.read_text(errors="ignore")[:4096]):
                actual = self.run(["git", "-C", str(root), "rev-parse", "HEAD"]).stdout.strip()
                return actual == "939e45c91d751fadd94dcd1b873ac3cb44846213"
        return False

    def installed(self) -> bool:
        return (self.home / "SOUL.md").is_file() and (self.home / "config.yaml").is_file()
