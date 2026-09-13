"""Shared setup/resume/connect/status interface for all five Orgo roles."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import time

from . import VERSION
from .catalog import CORE, SERVICES, describe
from .connections import configure, connection_fingerprint, install_plugins, adopt_connections, restore_toolsets
from .identity import configure as personalize
from .install import install, desktop
from .runtime import Runtime
from .storage import SetupError, private_write, read_json, update_env
from .verification import verify


def report(runtime):
    steps = runtime.state.load()["steps"]
    for service in SERVICES:
        item = steps.get(service, {})
        if item.get("status") == "verified" and item.get("fingerprint") != connection_fingerprint(runtime, service):
            runtime.state.mark_attention(service)
    steps = runtime.state.load()["steps"]
    return {"version": VERSION, "role": runtime.role["id"],
            "basic_ready": all(steps.get(key, {}).get("status") == "verified" for key in CORE),
            "steps": {key: steps.get(key, {"status": "not_started"}) for key in (*CORE, *SERVICES)},
            "resume_command": "./orgo-onboard resume"}


def show_status(runtime, as_json=False):
    data = report(runtime)
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        print(runtime.role["name"] + (": basic setup verified" if data["basic_ready"] else ": setup can be resumed"))
        for step, value in data["steps"].items():
            print("  " + SERVICES.get(step, {}).get("name", step.title()) + ": " + value["status"].replace("_", " "))
        print("Optional choices can be revisited with Finish agent setup. Credentials are not included in this report.")


def private_options(path):
    if not path:
        return {}
    if path == "-":
        value = json.load(sys.stdin)
    else:
        candidate = Path(path)
        if candidate.stat().st_mode & 0o077:
            raise SetupError("Private setup input must have permissions 600.")
        value = read_json(candidate)
    if not isinstance(value, dict):
        raise SetupError("Setup input must be a JSON object.")
    return value


def connect_channel(runtime, options):
    platform = options.get("platform", "slack")
    if platform not in {"slack", "telegram"}:
        raise SetupError("Choose Slack or Telegram.")
    keys = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALLOWED_USERS"] if platform == "slack" else ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"]
    env = runtime.env()
    values = {key: options.get(key) or env.get(key, "") for key in keys}
    if not all(values.values()):
        raise SetupError("The channel credential and owner's allowed user identity are required.")
    import re
    pattern = r"[UW][A-Z0-9]+" if platform == "slack" else r"[0-9]+"
    if any(not re.fullmatch(pattern, item) for item in values[platform.upper() + "_ALLOWED_USERS"].split(",")):
        raise SetupError("Use the owner's actual channel member identity; open access is not a default.")
    for key in ("SLACK_CONFIGURATION_TOKEN",):
        if options.get(key):
            values[key] = options[key]
    values[platform.upper() + "_ALLOW_ALL_USERS"] = "false"
    values["GATEWAY_ALLOW_ALL_USERS"] = "false"
    runtime.save_env(values)
    runtime.set("gateway.platforms." + platform + ".enabled", True)
    prior = read_json(runtime.home / "orgo-channel.json")
    saved = {**prior, "platform": platform, "connected_at": prior.get("connected_at", int(time.time()))}
    saved.update({key: options[key] for key in ("test_channel", "test_thread", "app_id") if key in options})
    private_write(runtime.home / "orgo-channel.json", json.dumps(saved, indent=2) + "\n")
    runtime.state.set("channel", "configured", check=platform + "-connected")
    runtime.restart()


def interactive_options(runtime, service):
    result = {}
    for key in SERVICES[service]["keys"]:
        if not runtime.env().get(key):
            result[key] = getpass.getpass(key.replace("_", " ").title() + " (hidden): ")
    fields = {
        "latitude": [("LATITUDE_PROJECT_SLUG", "Latitude project")],

        "composio": [("url", "This agent's authorized Composio MCP session address")],
        "super-browser": [("url", "Authorized Super Browser MCP address")],

    }
    saved = read_json(runtime.home / (service + ".json"))
    for key, label in fields.get(service, []):
        if not saved.get(key) and not result.get(key) and not runtime.env().get(key):
            result[key] = input(label + ": ").strip()
    if service in {"agentmail", "agentphone", "onepassword"}:
        from .discovery import inventory, choose
        account = inventory(runtime, service, result)
        if service == "agentmail" and not saved.get("inbox_id"):
            if input("Create a dedicated inbox with this account's selected plan? [create/existing/later]: ").strip() == "create":
                result["create_inbox_selected"] = True
            else:
                result["inbox_id"] = choose(account["inboxes"], "inbox", "inbox_id", "email")["inbox_id"]
        elif service == "onepassword" and not saved.get("vault_id"):
            result["vault_id"] = choose(account["vaults"], "dedicated vault")["id"]
        elif service == "agentphone" and not saved.get("number_id"):
            selected = choose(account["agents"], "dedicated phone identity")
            result["agent_id"] = selected["id"]
            numbers = [n for n in account["numbers"] if n.get("agentId") == selected["id"]]
            number = choose(numbers, "owned phone number", display_key="number")
            result.update(number_id=number["id"], number=number["number"])
    if service == "agentphone" and not saved.get("owners"):
        result["owners"] = [input("Approved owner's phone number: ").strip()]
        result["owner_passphrase"] = getpass.getpass("Private phone passphrase (20+ characters, hidden): ")
    if service == "latitude":
        choice = input("Capture metadata (recommended), or separately opt in to sanitized content? [metadata/sanitized]: ").strip()
        result["capture_mode"] = "sanitized" if choice == "sanitized" else "metadata"
        result["sanitized_content_selected"] = choice == "sanitized"
    return result


def journey(runtime, args):
    report(runtime)
    first = not runtime.installed()
    if not runtime.installed() or args.update or not runtime.pinned():
        if runtime.kind == "compose":
            from .storage import read_env
            model_file = runtime.env_file if runtime.env_file.exists() else runtime.source_config
            existing = read_env(model_file)
            model_key = existing.get("FIREWORKS_API_KEY", "")
            if not model_key or model_key == "fw_REPLACE_ME":
                if not sys.stdin.isatty():
                    raise SetupError("The setup agent must supply the model connection privately before installing.")
                if not model_file.exists():
                    private_write(model_file, (runtime.root / "agent.example.env").read_text())
                update_env(model_file, {"AGENT_NAME": existing.get("AGENT_NAME") or runtime.role["id"],
                                       "BASE_DIR": str(runtime.deployment),
                                       "FIREWORKS_API_KEY": getpass.getpass("Fireworks model API key (hidden): ")})
        install(runtime, name_prefix=args.name_prefix)
    personalize(runtime, name=args.name or (runtime.role["name"] if first and args.name_prefix is None else None),
                purpose=args.purpose, owner=args.owner)
    verify(runtime, "identity")
    install_plugins(runtime)
    runtime.hermes("plugins", "enable", "setup-evidence")
    adopt_connections(runtime)
    restore_toolsets(runtime)
    desktop(runtime)
    if runtime.state.get("model")["status"] != "verified":
        try:
            verify(runtime, "model")
        except SetupError:
            if not sys.stdin.isatty():
                raise
            runtime.hermes("setup", interactive=True, timeout=900)
            verify(runtime, "model")
    if runtime.role.get("team_helper") and not (runtime.home / "profiles/head-of-ops").is_dir():
        runtime.run(["bash", str(runtime.root / runtime.role["team_helper"])], interactive=True, timeout=300)
    try:
        verify(runtime, "runtime")
    except SetupError:
        runtime.restart()
        verify(runtime, "runtime")
    if not read_json(runtime.home / "orgo-channel.json"):
        env = runtime.env()
        for platform, token in (("slack", "SLACK_BOT_TOKEN"), ("telegram", "TELEGRAM_BOT_TOKEN")):
            if env.get(token) and env.get(platform.upper() + "_ALLOWED_USERS"):
                connect_channel(runtime, {"platform": platform})
                break
    if runtime.state.get("channel")["status"] != "verified":
        if sys.stdin.isatty() and runtime.state.get("channel")["status"] == "not_started":
            choice = input("Connect Slack (recommended), Telegram, or finish this step later? [slack/telegram/later]: ").strip().lower()
            if choice in {"slack", "telegram"}:
                options = {"platform": choice}
                keys = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALLOWED_USERS"] if choice == "slack" else ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"]
                for key in keys:
                    options[key] = runtime.env().get(key) or getpass.getpass(key.replace("_", " ").title() + " (hidden): ")
                connect_channel(runtime, options)
        try:
            verify(runtime, "channel")
        except SetupError as exc:
            print(str(exc))
    # An unfinished channel does not prevent discussing the optional enhancements.
    for service in runtime.role.get("services", SERVICES):
        state = runtime.state.get(service)["status"]
        if state == "verified":
            if time.time() - runtime.state.get(service).get("checked_at", 0) > 86400:
                try:
                    verify(runtime, service)
                except SetupError:
                    state = "needs_attention"
            if state == "verified":
                continue
        if state == "skipped":
            continue
        if args.skip_optional and state == "not_started":
            runtime.state.set(service, "skipped", check="owner-skipped")
            continue
        if not sys.stdin.isatty():
            continue
        print("\n" + describe(service))
        while True:
            choice = input("Connect now, learn more, or skip? [connect/learn/skip]: ").strip().lower()
            if choice == "learn":
                print(describe(service))
                continue
            if choice == "skip":
                runtime.state.set(service, "skipped", check="owner-skipped")
                break
            if choice == "connect":
                try:
                    if state != "configured":
                        configure(runtime, service, interactive_options(runtime, service))
                    verify(runtime, service)
                except SetupError as exc:
                    print(str(exc) + " Basic setup remains usable; this step can be resumed.")
                break
    show_status(runtime, args.json)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guided setup for this Orgo agent; private data stays on its computer.")
    parser.add_argument("command", choices=["setup", "resume", "status", "catalog", "connect", "verify", "skip", "personalize", "phone-test", "discover", "phone-reconcile"])
    parser.add_argument("service", nargs="?")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--deployment", type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--config", type=Path, help="Existing private Docker model configuration")
    parser.add_argument("--input", help="Private JSON options file (600), or - for stdin. Never pass secrets as arguments.")
    parser.add_argument("--name")
    parser.add_argument("--name-prefix")
    parser.add_argument("--purpose")
    parser.add_argument("--owner")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-optional", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            print(json.dumps(SERVICES, indent=2) if args.json else "\n\n".join(describe(s) for s in SERVICES))
            return 0
        runtime = Runtime(args.root, args.deployment, args.home, args.config)
        with runtime.state.lock():
            if args.command in {"setup", "resume"}:
                journey(runtime, args)
            elif args.command == "status":
                show_status(runtime, args.json)
            elif args.command == "personalize":
                options = private_options(args.input)
                personalize(runtime, name=args.name or options.get("name"), purpose=args.purpose or options.get("purpose"), owner=args.owner or options.get("owner"))
                verify(runtime, "identity")
            elif args.command == "skip":
                if args.service not in SERVICES:
                    raise SetupError("Only optional services can be skipped.")
                runtime.state.set(args.service, "skipped", check="owner-skipped")
            elif args.command == "connect":
                options = private_options(args.input)
                if args.service == "channel":
                    connect_channel(runtime, options)
                else:
                    if args.service not in SERVICES:
                        raise SetupError("Choose a service listed in the setup catalog.")
                    if not args.input:
                        if not sys.stdin.isatty():
                            raise SetupError("Supply connection options through private JSON input.")
                        print(describe(args.service))
                        options = interactive_options(runtime, args.service)
                    configure(runtime, args.service, options)
            elif args.command == "verify":
                if args.service not in (*CORE, *SERVICES):
                    raise SetupError("Choose the setup step to verify.")
                verify(runtime, args.service)
                print(args.service + ": verified")
            elif args.command == "discover":
                from .discovery import inventory
                # Account identifiers are private. The setup agent reads this on
                # the intended computer, never includes it in public reports.
                print(json.dumps(inventory(runtime, args.service, private_options(args.input))))
            elif args.command == "phone-reconcile":
                from .phone import reconcile
                print(json.dumps(reconcile(runtime, private_options(args.input))))
            elif args.command == "phone-test":
                from .phone import outbound_test
                print(json.dumps(outbound_test(runtime, private_options(args.input))))
        return 0
    except (SetupError, OSError, ValueError, KeyError) as exc:
        print("Setup needs attention: " + (str(exc) if isinstance(exc, SetupError) else "A required setting or local service is unavailable. Existing private files were preserved."), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Setup progress was saved. Finish agent setup resumes it later.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
