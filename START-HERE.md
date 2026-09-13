# Start Here: Revenue Partner on an [Orgo](https://orgo.ai?r=aiguy) computer

> **[Orgo](https://orgo.ai?r=aiguy) partner offer:** Get 25% off your first three months on a monthly plan or your first year on a yearly plan. Add-ons are not discounted.

This walkthrough is for someone creating a cloud computer for the first time.
You do not need to know server commands. Give this repository to Codex or Claude
Code and let the setup agent operate [Orgo](https://orgo.ai?r=aiguy) and the terminal while the owner
approves account access.

Setup agents should also read [AGENTS.md](AGENTS.md). It contains the complete
handoff, security rules, deployment contract, and definition of done. The
machine-readable version is [`llms.txt`](llms.txt).

## The one message to start with

```text
Install Revenue Partner from this repository:
https://github.com/jbellsolutions/revenue-partner-orgo

Read AGENTS.md, START-HERE.md, and docs/ORGO-SETUP.md first. Use my Orgo Startup account and
launch the maintained Hermes template. Handle every technical step yourself.
Walk me through only the private account approvals, one screen and one choice at
a time. Never display, repeat, or commit a key. Connect Slack first, add Telegram,
Calendar, inboxes, and PandaDoc when available, then connect Head of Ops through
private authenticated A2A. Finish only after a real message receives a reply and
orgo/verify.sh passes.
```

## Before the call

The setup agent confirms:

- the [Orgo](https://orgo.ai?r=aiguy) account is on Startup or another paid plan;
- the intended Slack workspace is available;
- the owner can create a Telegram bot if Telegram is wanted;
- a demonstration model account or the customer's own model account is ready;
- Calendar, inbox, and PandaDoc can be connected after the first message works.

Private values are entered only into hidden prompts on the [Orgo](https://orgo.ai?r=aiguy) computer. They
never go in GitHub, screenshots, webinar chat, notes, or copy-and-paste prompts.

## Step 1 — Create the computer

In [Orgo](https://orgo.ai?r=aiguy), create or open the customer workspace. Launch one Linux computer from
the maintained template `system/hermes-agent@1.0.0` with:

- Name: `ai-guy-revenue-partner`
- Memory: 8 GB
- CPU: 2 vCPU
- Disk: 40 GB
- Display: 1440 × 900

Wait until [Orgo](https://orgo.ai?r=aiguy) says the computer is running, then open its visible desktop and
Terminal. The owner does not need to create firewall rules, a public website, or
an inbound Slack webhook.

## Step 2 — Install Revenue Partner

The setup agent runs:

```bash
git clone https://github.com/jbellsolutions/revenue-partner-orgo.git
cd revenue-partner-orgo
./orgo/setup.sh
```

The installer pins the reviewed Hermes 0.20.6 release, installs the Revenue
Partner identity, knowledge structure, GTM skill, browser specialists, full
operator toolset, approval rules, and the safe A2A foundation. It also places
simple launch and connection icons on the [Orgo](https://orgo.ai?r=aiguy) desktop.

## Step 3 — Connect the model

If the demonstration account is already attached, the setup agent verifies it
without printing the credential. For a customer-owned account, it runs:

```bash
hermes setup
```

The owner signs in or pastes the provider key into the hidden prompt. The setup
agent sends one harmless local test and confirms the model answers before adding
messaging channels.

## Step 4 — Connect Slack

Use the included [slack-manifest.json](slack-manifest.json) and the exact
[Slack screen walkthrough](docs/SLACK-SETUP.md). Then run:

```bash
./orgo/connect-channels.sh
```

Choose Slack. The helper privately stores the `xoxb-` Bot Token, the `xapp-`
Socket Mode token, and the owner's Slack Member ID. Invite Revenue Partner only
to channels it is allowed to read.

Prove three things:

1. Send `hello` in a direct message and receive a reply.
2. Invite Revenue Partner to one approved channel and mention it once.
3. Reply inside that thread without another mention and receive the follow-up.

## Step 5 — Add Telegram

Run `./orgo/connect-channels.sh` again and choose Telegram. Create the bot with
`@BotFather`, enter the token in the hidden prompt, send `hello`, and verify the
reply. Telegram uses outbound long-polling, so no public port is needed.

## Step 6 — Connect Calendar, inboxes, files, CRM, and proposals

Run:

```bash
./orgo/connect-tools.sh
```

Connect Composio for the intended Calendar, Gmail or Outlook, Drive, documents,
CRM, and other business apps. Connect PandaDoc separately for proposals. Start
with safe proof requests:

```text
Read my next three calendar events. Do not create, change, or cancel anything.
List three recent inbox subject lines. Do not send, move, or change anything.
Create a private draft proposal titled "Connection Test". Do not send it.
```

## Step 7 — Connect Head of Ops privately

Follow [docs/A2A.md](docs/A2A.md). Both computers join the same private Tailscale
network and receive separate one-direction credentials. Neither agent exposes a
public A2A port, and an inbound peer task cannot chain to another peer.

## Step 8 — Finish with proof

Run:

```bash
./orgo/verify.sh
```

Setup is done only when:

- the reviewed Hermes release is installed;
- the Revenue Partner identity and skills load;
- Slack direct message and channel-thread tests pass;
- Telegram passes when selected;
- Calendar/inbox reads and the private proposal draft pass when connected;
- Head of Ops answers one harmless A2A readiness request;
- no credential appears in Git, logs shown on screen, or documentation;
- `orgo/verify.sh` passes.

If a connection is not ready during the call, leave the computer intact and run
the relevant connection helper again later. Do not delete `~/.hermes`; that is
where Revenue Partner keeps its memory, skills, configuration, and sessions.
