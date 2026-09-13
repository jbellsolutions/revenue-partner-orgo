# Revenue Partner on [Orgo](https://orgo.ai?r=aiguy): the simple walkthrough

This version gives Revenue Partner its own visible cloud computer. It stays on,
keeps its files and memory, answers through Slack or Telegram, and can use the
desktop without touching the owner's personal computer.

Give an AI setup agent the repository link. It reads the root `AGENTS.md`, this
walkthrough, and `orgo/deployment.json`; it then performs the technical work and
pauses only for private account-holder authorization. The official platform
facts and API map are in [ORGO-REFERENCE.md](ORGO-REFERENCE.md), grounded in
[Orgo's current `llms.txt`](https://docs.orgo.ai/llms.txt).

## What the setup agent does

1. Open the [Orgo](https://orgo.ai?r=aiguy) workspace and launch an 8 GB Linux computer from
   `system/hermes-agent@1.0.0`.
2. Name it `ai-guy-revenue-partner`.
3. Open its terminal and run:

   ```bash
   git clone https://github.com/jbellsolutions/revenue-partner-orgo.git
   cd revenue-partner-orgo
   ./orgo/setup.sh
   ```

   The new agent defaults to **Revenue Agent**. An optional
   `--name-prefix "Acme"` gives **Acme Revenue Agent** in Slack, its introduction,
   and desktop labels. Setup prints the personalized Slack manifest path;
   use that file when creating the Slack app. Repeat installs preserve the
   saved name. Existing profiles are not automatically renamed.

4. Connect the managed demonstration model or the customer's own model account.
5. Run `./orgo/connect-channels.sh` and connect Slack first. Run it again to add
   Telegram.
6. Run `./orgo/connect-tools.sh` for Calendar, inboxes, documents, CRM, and
   PandaDoc proposals.
7. Connect the second computer with [the A2A guide](A2A.md).
8. Run `./orgo/verify.sh`, send a real Slack message, and confirm the reply.

The process is safe to resume. If the workspace or computer already exists, the
setup agent inspects and reuses it instead of creating a duplicate. It must not
modify any unrelated computer or connect an existing Funding Revenue Partner to
this agent.

The installer handles the technical work. During a webinar, the owner only
approves the account sign-ins and privately supplies the values belonging to
their accounts.

## Why this works on Startup

[Orgo](https://orgo.ai?r=aiguy)'s Startup plan can launch [Orgo](https://orgo.ai?r=aiguy)-maintained templates, including Hermes.
Private custom golden-template publishing is a Scale feature, so this repository
is a reproducible setup layer on top of the maintained Hermes template. The
resulting computer is still persistent and can be cloned after it is configured.

Current [Orgo](https://orgo.ai?r=aiguy) facts must be rechecked at deployment time using the official
[`llms.txt`](https://docs.orgo.ai/llms.txt). The repository's selected computer
shape is 8 GB RAM, 2 vCPU, and 40 GB disk; it does not claim that plan limits or
pricing will remain unchanged.

## Finish line

- The exact reviewed Hermes release is installed.
- Revenue Partner's identity, knowledge structure, and specialist skills load.
- Slack direct messages and channel threads work for authorized members.
- Telegram works when selected.
- Calendar/inbox reads and a private proposal draft pass without an external
  write.
- The agent-to-agent connection accepts only its named peer.
- `./orgo/verify.sh` passes without printing credentials.
