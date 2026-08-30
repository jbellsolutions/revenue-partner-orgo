# Revenue Partner on Orgo: the simple walkthrough

This version gives Revenue Partner its own visible cloud computer. It stays on,
keeps its files and memory, answers through Slack or Telegram, and can use the
desktop without touching the owner's personal computer.

## What the setup agent does

1. Open the Orgo workspace and launch an 8 GB Linux computer from
   `system/hermes-agent@1.0.0`.
2. Name it `revenue-partner-2`.
3. Open its terminal and run:

   ```bash
   git clone https://github.com/jbellsolutions/revenue-partner-orgo.git
   cd revenue-partner-orgo
   ./orgo/setup.sh
   ```

4. Connect the managed demonstration model or the customer's own model account.
5. Run `./orgo/connect-channels.sh` and connect Slack first. Run it again to add
   Telegram.
6. Run `./orgo/connect-tools.sh` for Calendar, inboxes, documents, CRM, and
   PandaDoc proposals.
7. Connect the second computer with [the A2A guide](A2A.md).
8. Run `./orgo/verify.sh`, send a real Slack message, and confirm the reply.

The installer handles the technical work. During a webinar, the owner only
approves the account sign-ins and privately supplies the values belonging to
their accounts.

## Why this works on Startup

Orgo's Startup plan can launch Orgo-maintained templates, including Hermes.
Private custom golden-template publishing is a Scale feature, so this repository
is a reproducible setup layer on top of the maintained Hermes template. The
resulting computer is still persistent and can be cloned after it is configured.

## Finish line

- The exact reviewed Hermes release is installed.
- Revenue Partner's identity, knowledge structure, and specialist skills load.
- Slack direct messages and channel threads work for authorized members.
- Telegram works when selected.
- Calendar/inbox reads and a private proposal draft pass without an external
  write.
- The agent-to-agent connection accepts only its named peer.
- `./orgo/verify.sh` passes without printing credentials.
