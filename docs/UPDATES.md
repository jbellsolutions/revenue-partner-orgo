# Current Runtime and Update Procedure

## Reviewed baseline

The recommended VPS path is pinned to:

- Hermes Agent `0.20.6`;
- release tag `v2026.8.27`;
- official multi-platform image digest
  `sha256:e0df6adebddf29b91112aefc999d4aaf6846c9eb544faca5672a16a13590ff79`.

The older [Orgo](https://orgo.ai?r=aiguy) template remains deliberately locked to Hermes 0.18.0 and its
reviewed dependency graph. It is an advanced deterministic release path, not
the recommended new Slack installation.

## Useful current features

The reviewed 0.20.6 baseline adds or carries forward:

- Slack Agent view and active-context labels;
- complete native Slack slash-command generation;
- one-tap Slack clarification buttons;
- channel allowlists and deny-by-default user authorization;
- background work, goals, loops, queueing, steering, and process notifications;
- skill discovery across official, trusted, community, GitHub, and URL sources;
- skill security scans, provenance-aware update checks, audits, and optional
  human approval for agent-created skill changes;
- result caching, lean-tail context compression, improved tool search, gateway
  update coordination, Docker identity improvements, and remote MCP expansion.

Fresh installs also select the full Hermes CLI and Slack toolsets, enable lean
tail compression, and stage agent-created skill changes for owner review. The
guided `deploy/connect-tools.sh` path adds current Composio Connect and regional
PandaDoc MCP configuration without changing the legacy [Orgo](https://orgo.ai?r=aiguy) release.

## Update the container

For Docker installations, do not run an in-place source updater inside the
container. The image is replaceable and the private `/opt/data` mount is
persistent.

```bash
cd revenue-partner-agent
./deploy/update.sh
```

The helper pulls the repository's reviewed image pin, recreates the container,
preserves private data and edited skills, audits skills, and regenerates the
Slack manifest. Apply the regenerated manifest in Slack and reinstall the app
when Slack requests it.

## Review a future Hermes release

Before changing the image pin:

1. Read the official release notes.
2. Resolve the immutable Docker digest for the release tag.
3. Update both tag and digest in `deploy/compose.yml` and the setup/update
   helpers.
4. Regenerate the Slack Agent-view manifest from that exact release.
5. Run the repository verification and a fresh VPS smoke installation.
6. Prove a Slack DM, a channel thread, buttons, native commands, skills, and a
   restart before publishing.

Never point production at floating `latest`.
