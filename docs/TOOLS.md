# Tools and Business Connections

This guide applies to the recommended Hermes Agent 0.20.6 VPS installation.
It is additive: it does not change the older deterministic [Orgo](https://orgo.ai?r=aiguy) release or its
documented connector boundaries.

## What Revenue Partner starts with

Fresh installs explicitly enable the full current Hermes toolset for the private
command line and approved Slack owners. That includes files, web research,
browser automation when its browser backend is available, memory, skills,
vision and image generation when the chosen provider supports them, tasks,
schedules, terminal and code work, delegation, and session search.

Every capability still has its own prerequisite. A tool is not called connected
merely because its name appears: the owner must authorize the account, and the
least-privileged test below must succeed.

## Business tools included in the walkthrough

| Job | Connection | First proof |
|---|---|---|
| Google Calendar | Composio Connect | read the next three events |
| Gmail or Outlook | Composio Connect | list three recent subject lines |
| Drive, Docs, Sheets, Notion, CRM, and other apps | Composio Connect | read one small, private item |
| Proposals and signatures | PandaDoc MCP | list three recent documents before creating a private draft |

Composio Connect currently provides one MCP connection for more than 1,000
business apps. The installer uses its consumer key (`ck_…`) in the
`x-consumer-api-key` header and keeps the value only in the private VPS data
directory. A Platform project key (`ak_…`) is a different credential and is
rejected by the helper.

PandaDoc uses its official OAuth MCP endpoint. Global and European PandaDoc
accounts use different endpoints, so the helper asks which sign-in address the
owner uses before opening authorization.

Official references:

- [Composio Connect](https://docs.composio.dev/docs/composio-connect)
- [PandaDoc MCP setup](https://developers.pandadoc.com/docs/getting-started-with-mcp)
- [Hermes MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)

## Run the guided connector

The main installer opens it automatically. To return later, run:

```bash
cd revenue-partner-agent
./deploy/connect-tools.sh
```

The numbered menu does four things:

1. connects Composio for Calendar, inboxes, files, CRM, and other business apps;
2. connects the correct regional PandaDoc proposal service;
3. shows the current MCP connection status; or
4. finishes without changing another connection.

Secrets are entered in hidden prompts. Public configuration contains only the
`${COMPOSIO_API_KEY}` reference, never the key itself. Connected services are
marked `untrusted`, so Hermes asks for approval before a tool marked as
write-capable runs.

## Safe first tests in Slack

Calendar:

```text
Read my next three calendar events. Do not create, change, or cancel anything.
```

Inbox:

```text
List three recent message subject lines. Do not send, move, or change anything.
```

PandaDoc:

```text
List my three most recent PandaDoc documents. Do not create, send, or change anything.
```

Only after these read-only checks succeed should the owner try a private draft.
Sending email, inviting people to calendar events, changing CRM records, sending
a proposal, requesting a signature, publishing, spending, or launching a
campaign requires approval for the exact action and target. Revenue Partner must
read the resulting status back after an approved write.

## Connection is complete when

- `hermes mcp list` shows the intended server;
- the account authorization finished without an error;
- a read-only Slack test returns real account data;
- no private credential appears in Git or an ordinary Slack message; and
- a write-capable test pauses for approval before it changes anything.
