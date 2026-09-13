#!/usr/bin/env python3
"""Name the Orgo overlay consistently without changing runtime/product identity."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
import urllib.parse
import urllib.request


BRAND = "Revenue Agent"
SETTINGS = "revenue-agent-identity.json"
MANIFEST = "slack-manifest.json"
PROFILE_MARKER = ".revenue-partner-orgo-profile"
OLD_HEADER = "# SOUL.md — Revenue Partner"
OLD_INTRO = "You are the **Revenue Partner**:"


class IdentityError(ValueError):
    """A safe, credential-free diagnostic suitable for installer output."""


def normalize_prefix(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or any(
        unicodedata.category(char).startswith("C") or char in "\u2028\u2029"
        for char in value
    ):
        raise IdentityError("The name prefix must be text without control characters.")
    prefix = " ".join(value.split())
    # Accept a pasted full name, including repeated suffixes, without doubling branding.
    while prefix.casefold() == BRAND.casefold() or prefix.casefold().endswith(" " + BRAND.casefold()):
        prefix = prefix[:-len(BRAND)].rstrip()
    display = f"{prefix} {BRAND}" if prefix else BRAND
    if len(display) > 35:
        raise IdentityError("The complete Slack name must be at most 35 characters; use a prefix of at most 21 characters.")
    return prefix, display


def read_settings(home: Path) -> dict | None:
    path = home / SETTINGS
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        prefix, display = normalize_prefix(value["name_prefix"])
        if value["version"] != 1 or value["display_name"] != display or prefix != value["name_prefix"]:
            raise ValueError
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise IdentityError("The saved agent naming settings are invalid; no identity was changed.") from None


def resolve(home: Path, argument: str | None = None, *, use_environment: bool = True) -> dict | None:
    saved = read_settings(home)
    requested = argument
    if requested is None and use_environment:
        requested = os.environ.get("AGENT_NAME_PREFIX")
    if saved is None and (home / PROFILE_MARKER).exists():
        if requested is not None:
            raise IdentityError("This existing Orgo profile predates managed names. Its identity is preserved; automatic migration is not supported.")
        return None
    prefix, display = normalize_prefix(requested if requested is not None else (saved or {}).get("name_prefix", ""))
    return {"version": 1, "name_prefix": prefix, "display_name": display}


def markdown_name(name: str) -> str:
    return re.sub(r"([\\`*{}\[\]()#+.!_|<>])", r"\\\1", name)


def identity_lines(name: str) -> tuple[str, str]:
    visible = markdown_name(name)
    return (
        f"# SOUL.md — {visible}",
        f"Your name is **{visible}**. Use this full name when introducing yourself. "
        "Revenue Partner refers to your operating role and the program, not your personal name. "
        "You are the operator-facing go-to-market orchestrator responsible for connecting a business's front end into one measurable system.",
    )


def render_soul(source: str, name: str) -> str:
    header, intro = identity_lines(name)
    lines = source.splitlines(keepends=True)
    if len(lines) < 3 or lines[0].rstrip("\n") != OLD_HEADER or not lines[2].startswith(OLD_INTRO):
        raise IdentityError("The source identity format changed; review the naming renderer before installing.")
    lines[0], lines[2] = header + "\n", intro + "\n"
    return "".join(lines)


def render_manifest(root: Path, name: str) -> str:
    manifest = json.loads((root / MANIFEST).read_text())
    manifest["display_information"]["name"] = name
    manifest["features"]["bot_user"]["display_name"] = name
    # Keep the description generic: its product/offer identity is not the owner's name.
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def write_private(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".identity-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(content)
            os.fchmod(output.fileno(), mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare(root: Path, home: Path, argument: str | None = None) -> dict | None:
    """Seed new profiles or update only the two managed identity lines."""
    chosen = resolve(home, argument)
    if chosen is None:
        return None
    saved = read_settings(home)
    soul = home / "SOUL.md"
    name = chosen["display_name"]
    new_soul = None
    if saved is None:
        new_soul = render_soul((root / "files/SOUL.md").read_text(), name)
    elif saved != chosen:
        content = soul.read_text()
        old_lines = identity_lines(saved["display_name"])
        new_lines = identity_lines(name)
        lines = content.splitlines(keepends=True)
        if any(lines.count(line + "\n") != 1 for line in old_lines):
            raise IdentityError("Owner-edited identity lines were preserved. Restore the managed name lines before requesting a different prefix.")
        for old, new in zip(old_lines, new_lines):
            lines[lines.index(old + "\n")] = new + "\n"
        new_soul = "".join(lines)
    manifest = render_manifest(root, name)
    # Render and validate everything before writing. The settings are committed last.
    home.mkdir(parents=True, exist_ok=True)
    if saved is None and soul.exists():
        backup = home / "SOUL.md.before-revenue-partner"
        if not backup.exists():
            write_private(backup, soul.read_text())
    pending = {}
    if new_soul is not None:
        pending[soul] = new_soul
    pending[home / MANIFEST] = manifest
    pending[home / SETTINGS] = json.dumps(chosen, ensure_ascii=False, indent=2) + "\n"
    previous = {
        path: (path.read_text(), stat.S_IMODE(path.stat().st_mode)) if path.exists() else None
        for path in pending
    }
    written = []
    try:
        for path, content in pending.items():
            write_private(path, content)
            written.append(path)
    except OSError:
        # A failed settings write must not leave a new SOUL paired with an old name.
        try:
            for path in reversed(written):
                before = previous[path]
                if before is None:
                    path.unlink(missing_ok=True)
                else:
                    write_private(path, *before)
        except OSError:
            raise IdentityError("Naming update and file recovery failed. Check private SOUL, manifest, and naming settings before retrying.") from None
        raise IdentityError("Naming update failed; previous identity files were restored. Check available disk space and file permissions before retrying.") from None
    return chosen


def display_name(home: Path) -> str:
    saved = read_settings(home)
    if saved:
        return saved["display_name"]
    soul = home / "SOUL.md"
    if soul.exists():
        first = soul.read_text().splitlines()[:1]
        if first and first[0].startswith("# SOUL.md — "):
            value = first[0].removeprefix("# SOUL.md — ")
            if value and not any(unicodedata.category(c).startswith("C") for c in value):
                return value
    return "Revenue Partner" if (home / PROFILE_MARKER).exists() else BRAND


def install_desktop(root: Path, home: Path, desktop: Path) -> None:
    # Legacy installations keep the original launchers; never infer a migration.
    if read_settings(home) is None:
        return
    name = display_name(home).replace("\\", "\\\\")
    for filename, verb in (("RevenuePartner.desktop", "Open"), ("RevenuePartnerSetup.desktop", "Connect")):
        target = desktop / filename
        source = (target if target.exists() else root / "orgo" / filename).read_text()
        lines = source.splitlines(keepends=True)
        lines = [f"Name={verb} {name}\n" if line.startswith("Name=") else line for line in lines]
        # Never substitute user text into Exec or a shell command.
        write_private(target, "".join(lines), 0o755)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def slack_call(method: str, token: str, params: dict | None = None) -> dict:
    if method not in {"auth.test", "users.info"}:
        raise IdentityError("Only Slack identity reads are supported.")
    url = "https://slack.com/api/" + method
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        # No redirects or environment proxy can forward the bot credential elsewhere.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=15) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise ValueError
        return result
    except Exception:
        raise IdentityError("Slack identity could not be verified. Check connectivity, token validity, and users:read access; no Slack settings were changed.") from None


def verify(home: Path, *, local_only: bool = False, call=slack_call) -> list[str]:
    saved = read_settings(home)
    if saved is None:
        if (home / PROFILE_MARKER).exists():
            return ["Existing Orgo identity preserved; managed-name verification is not applicable."]
        raise IdentityError("No saved naming settings. Run the Orgo installer first.")
    name = saved["display_name"]
    try:
        manifest = json.loads((home / MANIFEST).read_text())
        if manifest["display_information"]["name"] != name or manifest["features"]["bot_user"]["display_name"] != name:
            raise ValueError
        soul = (home / "SOUL.md").read_text().splitlines()
        if any(line not in soul for line in identity_lines(name)):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise IdentityError("Saved name, local Slack manifest, and SOUL identity do not match. Owner files were not changed.") from None
    results = ["Saved name, Slack manifest, and SOUL identity match."]
    if local_only:
        return results + ["Slack identity read skipped (local-only check)."]
    try:
        from dotenv import dotenv_values
        # Match Hermes dotenv parsing, without sourcing shell or interpolating variables.
        values = dotenv_values(home / ".env", interpolate=False)
        token = os.environ.get("SLACK_BOT_TOKEN") or values.get("SLACK_BOT_TOKEN")
    except Exception:
        raise IdentityError("Slack token settings could not be read safely; use the installed Hermes Python interpreter.") from None
    if not token:
        return results + ["Slack is not connected; its displayed name has not been verified."]
    try:
        auth = call("auth.test", token)
        info = call("users.info", token, {"user": auth["user_id"]})
        user = info["user"]
        profile = user["profile"]
        if auth.get("ok") is not True or info.get("ok") is not True or user.get("id") != auth["user_id"] or not user.get("is_bot"):
            raise ValueError
        actual = profile.get("display_name") or profile.get("real_name") or user.get("real_name")
        if not isinstance(actual, str):
            raise ValueError
    except Exception:
        raise IdentityError("Slack identity could not be verified; no Slack settings were changed.") from None
    if actual != name:
        raise IdentityError("Connected Slack bot name differs from the saved name. Apply the generated manifest to that same app and check App Home's bot name. No Slack settings were changed.")
    return results + ["Connected Slack bot name matches the saved name."]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["resolve", "name", "manifest", "desktop", "verify"])
    parser.add_argument("--hermes-home", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--name-prefix")
    parser.add_argument("--desktop", type=Path)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            chosen = resolve(args.hermes_home, args.name_prefix)
            print(chosen["display_name"] if chosen else display_name(args.hermes_home))
        elif args.command == "name":
            print(display_name(args.hermes_home))
        elif args.command == "manifest":
            saved = read_settings(args.hermes_home)
            if saved is None:
                raise IdentityError("No managed name; the existing Slack app and manifest are preserved.")
            write_private(args.hermes_home / MANIFEST, render_manifest(args.root, saved["display_name"]))
            print(args.hermes_home / MANIFEST)
        elif args.command == "desktop":
            if args.desktop is None:
                parser.error("desktop requires --desktop")
            install_desktop(args.root, args.hermes_home, args.desktop)
        else:
            for result in verify(args.hermes_home, local_only=args.local_only):
                print(result)
    except IdentityError as error:
        parser.exit(1, f"Agent naming: {error}\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Agent naming: required local files could not be read or written; no Slack settings were changed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
