"""Personalization that preserves existing identities unless explicitly renamed."""
import json
import re
import secrets

from .storage import SetupError, private_write, read_json, fingerprint


def configure(runtime, *, name=None, purpose=None, owner=None):
    path = runtime.home / "orgo-identity.json"
    saved = read_json(path)
    soul_path = runtime.home / "SOUL.md"
    soul = soul_path.read_text() if soul_path.exists() else ""
    legacy = read_json(runtime.home / "revenue-agent-identity.json")
    current_name = saved.get("display_name") or legacy.get("display_name")
    if not current_name and soul:
        match = re.search(r"^#\s+(.+)$", soul, re.M)
        current_name = match[1].strip().removeprefix("SOUL.md — ") if match else None
    display = name or current_name or runtime.role["name"]
    if not isinstance(display, str) or not 1 <= len(display) <= 35 or any(ord(c) < 32 or c in "<>[]`" for c in display):
        raise SetupError("Choose a plain display name between 1 and 35 characters for Slack.")
    # Preserve the body, including user modifications. Only replace the known
    # current name when an explicit rename was requested.
    if name and current_name and name != current_name:
        private_write(runtime.state.directory / "identity-before-rename.md", soul)
        if legacy:
            # Use Revenue Partner's existing identity renderer so its legacy
            # entrypoints and verifier agree with shared personalization.
            import importlib.util
            spec = importlib.util.spec_from_file_location("orgo_legacy_identity", runtime.root / "orgo/identity.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            old_lines, new_lines = module.identity_lines(current_name), module.identity_lines(name)
            for old, new in zip(old_lines, new_lines):
                if old not in soul:
                    raise SetupError("The introduction was customized. Preserve it and review the proposed name edit before applying it.")
                soul = soul.replace(old, new, 1)
        else:
            lines = soul.splitlines(keepends=True)
            for index in range(min(5, len(lines))):
                lines[index] = lines[index].replace(current_name, name)
            soul = "".join(lines)
    elif not soul:
        soul = f"# {display}\n\nYou are {display}.\n"
    private_write(soul_path, soul)
    result = {**saved, "schema_version": 1,
              "instance_id": saved.get("instance_id") or secrets.token_hex(12),
              "display_name": display,
              "purpose": purpose if purpose is not None else saved.get("purpose", runtime.role["purpose"]),
              "owner": owner if owner is not None else saved.get("owner", "")}
    private_write(path, json.dumps(result, indent=2) + "\n")
    # A managed section supplies the selected purpose/owner to the running agent;
    # the rest of the owner's instructions are preserved byte for byte.
    start, end = "<!-- orgo-personalization:start -->", "<!-- orgo-personalization:end -->"
    context = runtime.home / "AGENTS.md"
    body = context.read_text() if context.exists() else ""
    block = start + "\nDisplay name: " + display + "\nPurpose: " + str(result["purpose"]) + "\nOwner: " + (str(result["owner"]) or "Use the explicitly allowed primary-channel owner.") + "\nRead orgo-connections.md for selected account identities and setup status.\n" + end
    if start in body and end in body:
        body = body[:body.index(start)] + block + body[body.index(end) + len(end):]
    else:
        body = body.rstrip() + "\n\n" + block + "\n"
    private_write(context, body)
    if legacy:
        private_write(runtime.home / "revenue-agent-identity.json", json.dumps({"version": 2, "name_prefix": legacy.get("name_prefix", ""), "display_name": display}) + "\n")
    manifest_path = runtime.home / "slack-manifest.json"
    manifest = read_json(manifest_path)
    if not manifest:
        for candidate in runtime.role.get("slack_manifests", []):
            source = runtime.root / candidate
            if source.suffix in {".yml", ".yaml"} and source.exists():
                import yaml
                manifest = yaml.safe_load(source.read_text())
            else:
                manifest = read_json(source)
            if manifest:
                break
    if manifest:
        manifest.setdefault("display_information", {})["name"] = display
        manifest.setdefault("features", {}).setdefault("bot_user", {})["display_name"] = display
        private_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
    runtime.state.set("identity", "configured", check="local-identity-saved", fingerprint=fingerprint(result))
    return result


def verify_local(runtime):
    saved = read_json(runtime.home / "orgo-identity.json")
    name = saved.get("display_name")
    soul = (runtime.home / "SOUL.md").read_text()
    manifest = read_json(runtime.home / "slack-manifest.json")
    if not name or name not in soul:
        raise SetupError("The saved name and installed introduction do not agree.")
    if manifest and (manifest.get("display_information", {}).get("name") != name or
                     manifest.get("features", {}).get("bot_user", {}).get("display_name") != name):
        raise SetupError("The Slack manifest does not match this agent's display name.")
    runtime.state.set("identity", "verified", check="local-name-and-manifest", fingerprint=fingerprint(saved))
