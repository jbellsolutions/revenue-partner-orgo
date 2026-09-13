"""Private, atomic setup state. Provider secrets never enter the progress file."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

STATES = {"not_started", "configured", "verified", "skipped", "needs_attention"}


class SetupError(RuntimeError):
    """Only safe, authored diagnostics belong in this exception."""


def private_directory(path):
    missing, ancestor = [], path
    while not ancestor.exists():
        missing.append(ancestor)
        ancestor = ancestor.parent
    owner = ancestor.stat()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.geteuid() == 0:
        for created in reversed(missing):
            os.chown(created, owner.st_uid, owner.st_gid)


def private_write(path: Path, content: str | bytes) -> None:
    private_directory(path.parent)
    if path.is_symlink():
        raise SetupError("A private setup file is a symbolic link; it was preserved.")
    fd, name = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode() if isinstance(content, str) else content)
            os.fchmod(stream.fileno(), 0o600)
            if os.geteuid() == 0:
                owner = path.stat() if path.exists() else path.parent.stat()
                os.fchown(stream.fileno(), owner.st_uid, owner.st_gid)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise SetupError("A saved setup file is unreadable; it was preserved for recovery.") from None


def read_env(path: Path) -> dict[str, str]:
    result = {}
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                result[key.strip()] = value
    return result


def update_env(path: Path, values: dict[str, str]) -> None:
    for key, value in values.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not isinstance(value, str):
            raise SetupError("Invalid private setting.")
        # dotenv interpolation, shell sourcing and multiline values must not execute code.
        if any(char in value for char in "\r\n\x00'`$"):
            raise SetupError("This private value contains an unsupported character.")
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.split("=", 1)[0].strip() not in values]
    lines.extend(f"{key}='{value}'" for key, value in values.items())
    private_write(path, "\n".join(lines) + "\n")


class State:
    def __init__(self, home: Path, role: str):
        self.directory = home / ".orgo-onboarding"
        self.path = self.directory / "progress.json"
        self.role = role

    @contextmanager
    def lock(self):
        private_directory(self.directory)
        os.chmod(self.directory, 0o700)
        # Keep the inode outside the tree replaced by update rollback.
        lock_path = self.directory.parent.parent / ("." + self.directory.parent.name + "-orgo-setup.lock")
        if lock_path.is_symlink():
            raise SetupError("The setup lock must not be a symbolic link.")
        with lock_path.open("a") as lock:
            os.fchmod(lock.fileno(), 0o600)
            if os.geteuid() == 0:
                owner = self.directory.stat()
                os.fchown(lock.fileno(), owner.st_uid, owner.st_gid)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SetupError("Another setup is running for this agent. Resume after it finishes.") from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self) -> dict:
        data = read_json(self.path, {"schema_version": 1, "role": self.role, "steps": {}})
        if data.get("schema_version") != 1 or data.get("role") != self.role or not isinstance(data.get("steps"), dict):
            raise SetupError("This setup state belongs to a different role or version.")
        return data

    def set(self, step: str, status: str, *, check: str = "", fingerprint: str = "") -> None:
        if status not in STATES or not re.fullmatch(r"[a-z][a-z0-9_-]*", step):
            raise SetupError("Invalid setup state transition.")
        # Store identifiers, not arbitrary command output, provider errors, or keys.
        if check and not re.fullmatch(r"[a-z0-9_-]{1,80}", check):
            raise SetupError("Verification evidence must be a check identifier.")
        if fingerprint and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise SetupError("Invalid connection fingerprint.")
        data = self.load()
        previous = data["steps"].get(step, {})
        configured_at = (previous.get("configured_at", previous.get("checked_at", 0))
                         if fingerprint == previous.get("fingerprint") else int(time.time()))
        data["steps"][step] = {"status": status, "check": check, "fingerprint": fingerprint,
                               "configured_at": configured_at, "checked_at": int(time.time())}
        private_write(self.path, json.dumps(data, indent=2) + "\n")

    def get(self, step: str) -> dict:
        return self.load()["steps"].get(step, {"status": "not_started"})

    def mark_attention(self, step):
        data = self.load()
        prior = data["steps"].get(step, {})
        data["steps"][step] = {**prior, "status": "needs_attention", "checked_at": int(time.time())}
        private_write(self.path, json.dumps(data, indent=2) + "\n")


def fingerprint(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def install_tree(source: Path, destination: Path, manifest_path: Path) -> None:
    prior = read_json(manifest_path)
    current = dict(prior)
    pending = []
    for item in sorted(source.rglob("*")):
        if not item.is_file() or "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        target = destination / item.relative_to(source)
        digest = hashlib.sha256(item.read_bytes()).hexdigest()
        key = str(item.relative_to(source))
        if target.exists():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest and actual != prior.get(key):
                raise SetupError("An installed integration was customized. Its files were preserved; review the change before updating.")
        pending.append((target, item.read_bytes()))
        current[key] = digest
    for target, content in pending:
        private_write(target, content)
    private_write(manifest_path, json.dumps(current, indent=2) + "\n")
