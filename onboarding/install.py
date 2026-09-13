"""Wrap the role's existing installer with private snapshots and rollback."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import time

from .connections import install_plugins, restore_toolsets
from .storage import SetupError, private_write


def copy_private_tree(source, target, **kwargs):
    shutil.copytree(source, target, **kwargs)
    if os.geteuid() == 0:
        for path in [source, *source.rglob("*")]:
            original = path.lstat()
            os.chown(target / path.relative_to(source), original.st_uid, original.st_gid, follow_symlinks=False)


@contextmanager
def checkpoint(runtime):
    if not runtime.installed():
        yield None
        return
    # A stopped gateway gives a consistent filesystem/SQLite snapshot. Only the
    # intended installation is stopped; other services and computers are untouched.
    healthy = runtime.health()
    if healthy:
        if runtime.kind == "compose":
            runtime.run([*runtime.compose(), "stop", "hermes"])
        else:
            runtime.hermes("gateway", "stop")
    folder = runtime.home.parent / ".orgo-backups" / (runtime.role["id"] + "-" + str(time.time_ns()))
    complete = False
    runtime_path = None
    try:
        folder.mkdir(mode=0o700, parents=True)
        os.chmod(folder.parent, 0o700)
        copy_private_tree(runtime.home, folder / "home", symlinks=True)
        for name, source in (("deployment.env", runtime.env_file), ("compose.yml", runtime.deployment / "compose.yml")):
            if source.is_file():
                shutil.copy2(source, folder / name)
        # Native runtime includes its dependency environment. Keeping it makes a
        # rollback restore the reviewed old executable and dependencies together.
        if runtime.kind == "native":
            for candidate in (Path("/usr/local/lib/hermes-agent"), runtime.home / "hermes-agent"):
                if (candidate / ".git").exists():
                    runtime_path = candidate
                    if not candidate.is_relative_to(runtime.home):
                        copy_private_tree(candidate, folder / "runtime", symlinks=True)
                    break
        private_write(folder / "snapshot.json", json.dumps({"schema_version": 1, "healthy": healthy, "runtime_path": str(runtime_path) if runtime_path else None}) + "\n")
        complete = True
        yield folder
        if healthy:
            runtime.restart()
        if healthy and not runtime.health():
            raise SetupError("The updated agent failed its health check.")
    except Exception:
        if complete:
            # Preserve the failed tree for diagnosis rather than delete private data.
            failed = folder / "failed-home"
            if runtime.home.exists():
                shutil.move(str(runtime.home), failed)
            copy_private_tree(folder / "home", runtime.home, symlinks=True)
            for name, target in (("deployment.env", runtime.env_file), ("compose.yml", runtime.deployment / "compose.yml")):
                if (folder / name).is_file():
                    shutil.copy2(folder / name, target)
            if (folder / "runtime").is_dir() and runtime_path:
                shutil.move(str(runtime_path), folder / "failed-runtime")
                copy_private_tree(folder / "runtime", runtime_path, symlinks=True)
        if healthy:
            runtime.restart()
        raise


def install(runtime, *, name_prefix=None):
    previous = runtime.state.load()["steps"]
    with checkpoint(runtime):
        if runtime.kind == "native":
            args = ["bash", str(runtime.root / "orgo/setup.sh"), "--runtime-only"]
            if name_prefix is not None and runtime.role["id"] == "revenue-partner":
                args += ["--name-prefix", name_prefix]
            runtime.run(args, interactive=True, timeout=1800)
        else:
            if not shutil.which("docker"):
                runtime.run(["bash", str(runtime.root / "provision-vps.sh")], interactive=True, timeout=900)
            env = runtime.env_file if runtime.env_file.exists() else runtime.source_config
            if not env.exists():
                raise SetupError("Create this installation's private model configuration through guided setup first.")
            runtime.run(["bash", str(runtime.root / "new-agent.sh"), str(env), "--runtime-only"], interactive=True, timeout=1800)
        install_plugins(runtime)
        runtime.hermes("plugins", "enable", "setup-evidence")
        restore_toolsets(runtime)
        runtime.state.set("runtime", "configured", check="role-installer-complete")
        runtime.restart()
        # Existing working installations must still answer after an update.
        from .verification import verify
        for step in ("model", "channel"):
            if previous.get(step, {}).get("status") == "verified":
                verify(runtime, step)


def desktop(runtime):
    import shlex
    desktop_dir = Path.home() / "Desktop"
    if not desktop_dir.is_dir():
        return
    import hashlib
    command = shlex.join(["bash", str(runtime.root / "orgo-onboard"), "resume",
                          "--home", str(runtime.home), "--deployment", str(runtime.deployment)])
    # Desktop Entry Exec is not a shell command. Route through a script with safe
    # shell quoting and quote the path using the Desktop Entry escaping rules.
    launcher = runtime.state.directory / "finish-setup.sh"
    private_write(launcher, "#!/usr/bin/env bash\nexec " + command + "\n")
    launcher.chmod(0o700)
    quoted = str(launcher).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    suffix = hashlib.sha256(str(runtime.home).encode()).hexdigest()[:12]
    shortcut = desktop_dir / ("orgo-finish-setup-" + suffix + ".desktop")
    private_write(shortcut, '[Desktop Entry]\nType=Application\nName=Finish ' + runtime.role["name"] + ' setup\nExec="' + quoted + '"\nTerminal=true\nIcon=preferences-system\n')
    shortcut.chmod(0o700)
