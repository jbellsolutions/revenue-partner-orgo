<div align="center">

<img src="docs/assets/revenue-partner-hero-v2.webp" alt="Revenue Partner connects revenue, operations, calendar, inbox, customers, proposals, and daily priorities" width="1000"/>

# Revenue Partner for Orgo

### Practical AI for revenue, operations, and everyday life.

One calm, always-available partner that finds opportunities, keeps follow-up
moving, prepares proposals, organizes the work, and gives people time back.

[**Start the Orgo walkthrough →**](START-HERE.md) &nbsp;·&nbsp;
[Setup-agent brief](AGENTS.md) &nbsp;·&nbsp;
[Connect Slack](docs/SLACK-SETUP.md) &nbsp;·&nbsp;
[See every tool](docs/TOOLS.md) &nbsp;·&nbsp;
[Connect Head of Ops](docs/A2A.md)

</div>

<div align="center">

[![CI](https://github.com/jbellsolutions/revenue-partner-orgo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jbellsolutions/revenue-partner-orgo/actions/workflows/ci.yml)
[![Orgo](https://img.shields.io/badge/Orgo-Startup_ready-0f766e)](docs/ORGO-SETUP.md)
[![Hermes](https://img.shields.io/badge/Hermes_Agent-0.20.6-0f766e)](https://github.com/NousResearch/hermes-agent)
[![A2A](https://img.shields.io/badge/A2A-private_peer-2563eb)](docs/A2A.md)
[![Secrets](https://img.shields.io/badge/baked_secrets-0-e11d48)](SECURITY.md)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

## AI should make life lighter

Revenue Partner is the revenue-and-operations side of **The AI Guy** approach:
use practical AI to remove busywork, keep important work moving, and make more
room to think, sell, serve customers, and live life.

It is not another dashboard to babysit. It is an operator you can talk to in
plain language from Slack, Telegram, or its own visible Orgo computer.

<table>
<tr>
<td width="33%" valign="top">

### Grow revenue

Find and qualify opportunities, coordinate outreach and partner channels, keep
follow-up clear, prepare proposals, and report the numbers that matter.

</td>
<td width="33%" valign="top">

### Run operations

Work across inboxes, calendars, documents, CRM, research, tasks, skills, and
repeatable workflows without living in a dozen tabs.

</td>
<td width="33%" valign="top">

### Get time back

Turn scattered requests into a clear plan, protect personal time, remember the
details, and finish the day knowing what moved forward.

</td>
</tr>
</table>

<div align="center">
<img src="docs/assets/revenue-partner-workflow-v1.webp" alt="A simple flow from opportunities to organized operations, proposals, schedules, and a calmer completed day" width="1000"/>
</div>

---

## One GitHub link. One visible cloud computer.

Give a setup agent this repository:

```text
https://github.com/jbellsolutions/revenue-partner-orgo
```

The root [setup-agent brief](AGENTS.md) and [`llms.txt`](llms.txt) give another
AI the summary, deployment contract, safety boundary, source links, and finish
line automatically after it opens or clones the repository.

Then say:

```text
Install Revenue Partner on my Orgo computer. Read START-HERE.md first, handle
every technical step, and walk me through only the private account approvals.
Finish when it answers a real Slack message and passes the Orgo verification.
```

The setup agent launches Orgo's maintained Hermes computer, installs the exact
reviewed Hermes release and Revenue Partner profile, connects the accounts the
owner chooses, and proves the result. No public webhook is required. No private
token belongs in GitHub.

### What comes with it

| Layer | Included |
|---|---|
| **Private computer** | Persistent Orgo Linux desktop with visible terminal, browser, files, and agent memory |
| **Revenue brain** | Fit gates, offer and ICP context, approved claims, campaign rules, Money Desk reporting, and GTM operating procedures |
| **Conversation** | Slack Agent view, threaded channel work, Telegram, and the local Hermes chat |
| **Everyday tools** | Research, browser, computer use, files, documents, code, vision, images, tasks, schedules, memory, and delegation |
| **Business tools** | Guided Calendar, inbox, Drive, CRM, and business-app connection through Composio plus PandaDoc proposals |
| **Skills** | Revenue Partner operating skill, browser specialists, the bundled Hermes catalog, audits, updates, and owner-reviewed skill changes |
| **A2A** | Private, authenticated collaboration with Head of Ops over Tailscale; no public A2A port |
| **Safety** | Member allowlists, hidden secret entry, read-only first tests, untrusted connectors, and approval before consequential writes |

Revenue Partner can research, analyze, organize, and prepare private drafts.
Sending, publishing, spending, changing customer records, inviting people, or
launching a campaign remains behind an explicit approval step.

---

## The simple setup

1. Launch one Orgo Hermes computer named `ai-guy-revenue-partner`.
2. Run `./orgo/setup.sh` from this repository.
3. Connect Slack and Telegram with `./orgo/connect-channels.sh`.
4. Connect Calendar, inboxes, files, CRM, and proposals with
   `./orgo/connect-tools.sh`.
5. Connect Head of Ops privately with `./orgo/connect-a2a.sh`.
6. Run `./orgo/verify.sh` and send a real message.

The screen-by-screen version is in [START-HERE.md](START-HERE.md). The precise
Orgo handoff is in [docs/ORGO-SETUP.md](docs/ORGO-SETUP.md).

### Startup-plan packaging

Orgo Startup launches Orgo-maintained templates. Publishing private custom
golden templates is a Scale feature, so this repository deliberately installs
as a reproducible profile on `system/hermes-agent@1.0.0`. After setup, the
configured computer remains persistent and can be cloned from Orgo.

---

## Documentation

| Guide | Covers |
|---|---|
| [Start Here](START-HERE.md) | First-time installation from one repository link |
| [Setup-agent brief](AGENTS.md) | Self-contained instructions for Codex, Claude Code, and other setup agents |
| [`llms.txt`](llms.txt) | Machine-readable summary, entry points, contract, and source links |
| [Orgo setup](docs/ORGO-SETUP.md) | Computer shape, install, connections, proof, and Startup-plan notes |
| [Orgo reference](docs/ORGO-REFERENCE.md) | Applied Orgo `llms.txt`, API operations, template rules, and sizing notes |
| [Slack setup](docs/SLACK-SETUP.md) | App manifest, tokens, Member ID, direct message, and channel-thread test |
| [Tools](docs/TOOLS.md) | Calendar, inboxes, files, CRM, business apps, proposals, and safe tests |
| [Skills](docs/SKILLS.md) | Included skills, the [Hermes Skills system](https://hermes-agent.nousresearch.com/docs/skills), audits, and updates |
| [A2A](docs/A2A.md) | Private Head of Ops connection, trust, audit, and anti-loop controls |
| [Security](SECURITY.md) | Credentials, approvals, private data, and disclosure policy |

The older VPS and custom-template engineering assets remain in this copy for
advanced operators and source parity. The beginner path above is the supported
Orgo Startup walkthrough. Optional connections activate only when configured;
missing credentials never become placeholder data or silent permission.

MIT licensed. Hermes Agent is maintained by Nous Research. This repository is
not affiliated with Orgo, Nous Research, Slack, Telegram, Composio, PandaDoc,
OpenRouter, or Tailscale.
