# Slack Setup: Screen by Screen

This is the Slack path for the supported Orgo installation. It uses Socket
Mode, so the Orgo computer does not need a public webhook or Slack-facing port.

## Before the installer starts

The owner needs:

- permission to install an app in the intended Slack workspace;
- a model account selected during Hermes setup;
- their Slack Member ID;
- one or more channels where the app may be invited.

Run `./orgo/setup.sh` first, optionally with `--name-prefix "Acme"`. The default
name is **Revenue Agent**; a custom prefix produces **Acme Revenue Agent**.
The installer uses the included [`slack-manifest.json`](../slack-manifest.json)
as a base and writes the personalized version to
`$HERMES_HOME/slack-manifest.json` (normally `~/.hermes/slack-manifest.json`).
It sets both the app name and bot display name from the saved installation name,
retaining Hermes Agent 0.20.6's Agent view, permissions, events, and commands.
Use the personalized file printed by setup, not the repository's base file.

## 1. Create the app from the manifest

1. Open [Slack App Settings](https://api.slack.com/apps).
2. Select **Create New App**.
3. Select **From an app manifest**.
4. Pick the workspace.
5. Choose the **JSON** tab.
6. Paste the complete contents of the personalized `~/.hermes/slack-manifest.json`
   (or the path printed by setup when `HERMES_HOME` is customized).
7. Select **Next**, review the requested access, then select **Create**.

The manifest enables Slack's current Agent messaging experience. Slack warns
that an app cannot switch back from Agent view after applying it. This is
expected for a newly created Revenue Agent app.

The manifest also enables Socket Mode, messages, files, reactions, Agent DMs,
and every current Hermes slash command. No public request URL is required.

## 2. Install the app and copy the bot token

1. In the app sidebar, open **Install App**.
2. Select **Install to Workspace**.
3. Review the workspace and permissions.
4. Select **Allow**.
5. Copy the **Bot User OAuth Token** beginning `xoxb-`.
6. Paste it only into the installer's hidden `xoxb-` prompt.

Do not paste the token into ordinary Slack messages, documentation, or GitHub.

## 3. Create the Socket Mode token

1. Open **Settings → Basic Information**.
2. Scroll to **App-Level Tokens**.
3. Select **Generate Token and Scopes**.
4. Name it `revenue-partner-socket`.
5. Add the `connections:write` scope.
6. Select **Generate**.
7. Copy the token beginning `xapp-`.
8. Paste it only into the installer's hidden `xapp-` prompt.

The `xoxb-` token acts as the bot. The `xapp-` token opens the private Socket
Mode connection. Both are required.

## 4. Allow the owner

Hermes denies Slack users by default. To copy the owner's Member ID:

1. Open the owner's profile in Slack.
2. Select **More**.
3. Select **Copy member ID**.
4. Paste the `U…` or `W…` value into the installer.

For more than one owner, enter comma-separated Member IDs. Do not use a display
name or email address.

## 5. Connect Slack and optionally choose a home channel

Run `./orgo/connect-channels.sh`, choose Slack, and provide the tokens and Slack
Member ID at its private prompts. For the examples below, replace **Revenue
Agent** with the full installed name, such as **Acme Revenue Agent**.

The home channel receives scheduled reports and proactive messages. To use one:

1. Open the intended channel.
2. Open **Channel details → About**.
3. Copy the Channel ID at the bottom.
4. Have the setup agent store the `C…` or `G…` value as `SLACK_HOME_CHANNEL` in
   the private Hermes environment and restart the gateway.
5. In that channel, run `/invite @Revenue Agent`, selecting the actual named app.

Skip this optional configuration if scheduled Slack delivery is not needed yet.

## 6. Test the actual Slack behavior

### Direct message

Open **Apps → Revenue Agent** (or its full custom name) and send:

```text
hello
```

The app answers every authorized DM without an `@mention`.

### Channel

Invite the app, then send:

```text
@Revenue Agent give me a one-sentence status
```

In channels, an `@mention` starts the conversation. The agent replies in
a thread. Once it is active in that thread, follow-up replies do not need
another mention.

### Commands and buttons

Type `/` and confirm commands such as `/help`, `/new`, `/reload-skills`, `/btw`,
`/stop`, `/approve`, and `/deny` appear. Slack caps an app at 50 native slash
commands, so use `!skills` or `/hermes skills` for the skill manager and
`!revenue-partner <request>` for the Revenue Partner skill. When it asks a bounded
multiple-choice question, Slack shows one-tap buttons plus an **Other…** choice.

## 7. Keep Slack current

For installations with saved naming settings, refresh the manifest from the
current repository without reinstalling Hermes or changing the saved name:

```bash
cd revenue-partner-orgo
python3 orgo/identity.py manifest --hermes-home "${HERMES_HOME:-$HOME/.hermes}"
```

Then open the same installed app in **Slack App Settings → Features → App
Manifest → Edit**, paste the generated JSON, and save. Reinstall if Slack
requests it. Generating a local manifest alone does not update Slack.

Run `./orgo/verify.sh` to compare the saved name, local manifest, SOUL identity,
and the bot associated with the actual token. It uses only `auth.test` and
`users.info`, never sends a message, and never renames an app. Slack errors or
mismatches fail verification without showing credentials. `--allow-unconnected`
checks local naming only and explicitly skips the Slack read.

Existing Orgo profiles without `revenue-agent-identity.json` retain their names
and report that managed-name verification does not apply. Do not replace an
existing app with the repository's default manifest just to adopt this feature.

Slack has separate app and bot names. **Basic Information → Display Information**
edits the app name; **App Home → Your App's Presence** edits the bot name. Changing
these in Slack does not update the agent's SOUL. The supported installer always
includes **Revenue Agent** in generated names, but Slack administrators still
control their app settings; there is no background name enforcement.

## Troubleshooting

| Symptom | Fix |
|---|---|
| App is offline | Run `hermes gateway status` and verify both tokens were entered |
| DM is ignored | Confirm the sender's exact Member ID is in `SLACK_ALLOWED_USERS` |
| Channel mention is ignored | Run `/invite @Revenue Agent` using the actual full app name |
| Old name remains in Slack | Confirm the generated manifest was applied to the same app as the bot token, and check both app and bot name fields |
| Name check cannot reach Slack | Check connection, token validity, and `users:read`; an unavailable check is not a successful name verification |
| Commands are missing | Regenerate and reapply the manifest, then reinstall when prompted |
| Replies appear outside the expected place | Begin with an `@mention` in the intended channel and continue in its thread |
| A token was exposed | Revoke it immediately in Slack, generate a replacement, and rerun setup |
