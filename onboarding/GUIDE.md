# Guided Orgo self-install

Revenue Partner Orgo maintains the versioned onboarding code distributed with all five supported roles. Orgo is the supported customer path. Revenue Partner and Head of Ops keep their native Hermes installation; AI Co-Founder keeps its native core and worker profiles; Operator and Go-to-Market keep Docker Compose. Do not replace one architecture with another.

## The customer experience

Give your setup AI this repository link and say: “Install this agent on my intended Orgo computer and walk me through setup.” The setup AI inspects the account and computer, reuses the healthy installation and connections, and does the commands, configuration, checks and recovery. The owner participates only for sign-in, private authorization, consent and billing choices.

The setup AI leads these steps, one at a time:

1. Inspect the intended computer, existing runtime, connected accounts and saved progress. Confirm the target by its workspace and computer identity; never choose a machine merely because it is running.
2. Personalize the display name, business purpose and owner. Keep the role’s default name unless the owner chooses another. Preserve an existing custom name. Use the generated private Slack manifest for both app and bot names.
3. Install the pinned runtime, connect the selected model, and obtain a real local response.
4. Recommend Slack; offer Telegram. Restrict the initial channel to the owner. Complete a real conversation; Slack also needs a thread follow-up and live app/bot name readback.
5. Offer Honcho, Latitude, the agent’s own phone and its own inbox separately. For each, explain the benefit, account, possible charges and data access, then offer **Connect now**, **Learn more**, or **Skip**.
6. Offer relevant Calendar, personal inbox, Drive and CRM accounts through Composio; PandaDoc; Super Browser; ScrapeCreators; a dedicated 1Password vault; and private collaboration with individually selected agents. AgentCard is a separate optional TEST connection, with purchasing disabled during setup.
7. Show what is verified, skipped, configured but unproven, or needs attention. Finish the basic setup even when an optional service is unavailable. “Finish agent setup” returns to the remaining choices without repeating completed work.

Useful wording: “This is optional. It can help with [specific benefit]. You can connect it now, learn more, or skip it and come back later.” Do not invent claims about customer adoption. Latitude monitoring reveals activity and failures; it does not automatically optimize the agent.

## Interface for the setup AI

Use `./orgo-onboard setup`, `resume`, `status --json`, `catalog --json`, `personalize`, `connect SERVICE`, `verify STEP`, and `skip SERVICE`. Existing native `orgo/setup.sh` and Docker `new-agent.sh` entrypoints enter the same journey. `--skip-optional` leaves every unselected enhancement skipped. `--update` uses a private backup and restores the previous installation when installation or health checks fail. Do not invoke `--runtime-only` directly for a customer update; it is the internal architecture adapter.

The human-facing conversation is run by the setup AI. The terminal prompts are a fallback, not a list of commands to hand to the owner. Resolve technical account IDs through `discover agentphone`, `discover agentmail`, `discover onepassword`, provider tools or the signed-in dashboard. Create accounts and install missing provider CLIs on the intended runtime as part of the setup; pause only for the owner-only steps.

Supply settings through `--input -` on stdin or a private JSON file with mode 600. Never put credentials in arguments, public reports, screenshots or Git. On a fresh Docker host, the setup AI runs `provision-vps.sh` first to install Docker and prepares the private model connection. Native `--home` selects a private Hermes home; Docker `--deployment` selects the exact Compose deployment. Connection input uses the service’s environment key names listed by `catalog` plus these fields:

| Connection | Private options and checks |
|---|---|
| Primary channel | `platform` slack/telegram, channel credentials, owner allowed-user IDs; Slack `test_channel`, `test_thread`, `app_id`, and `SLACK_CONFIGURATION_TOKEN` for app-manifest readback. Setup AI obtains these from the actual conversation and Slack app settings. |
| Honcho | `HONCHO_API_KEY`, optional `owner_channels` mapping such as `slack:U123` or `telegram:123`; primary-channel and paired phone owners are mapped automatically. Each installation gets a distinct workspace and AI peer. Existing memory identities are preserved. Verify a harmless fact recalled in a second session; retry the same saved probe if indexing is delayed. |
| Latitude | `LATITUDE_API_KEY`, `LATITUDE_PROJECT_SLUG`, `capture_mode` defaults to metadata. `sanitized_content_selected: true` is required for sanitized capture. Run a harmless conversation; the observer records an actual accepted trace. No raw mode. |
| Phone | `AGENTPHONE_API_KEY`; selected `agent_id`, `number_id`, `number`, `owners`, and private `owner_passphrase` of 20+ characters without a period. `create_identity_selected` creates a dedicated provider identity. `attach_number_selected` attaches an unassigned owned number. `purchase_number_selected` plus a specific `selected_number` is the explicit paid selection. Never reuse another installed agent’s identity, number or credential. A provider-wide key must belong to a dedicated account; subaccounts sharing a master key are not independent credentials. |
| Inbox | `AGENTMAIL_API_KEY` and `inbox_id`, or explicit `create_inbox_selected: true`. Discover/reuse by the installation’s stable identity; save only its selected inbox. Use an inbox-scoped key or a dedicated provider account. |
| Composio | `COMPOSIO_API_KEY`; Connect keys beginning `ck_` use the official Connect endpoint. Other accounts need the exact authorized MCP session `url` issued by Composio. Select Calendar, inbox, Drive and CRM accounts/scopes separately. |
| PandaDoc | `region` global/eu; the setup AI opens the OAuth consent flow. First check account/template read access; create only a private unsent draft when selected. |
| Super Browser | Reuse the private `SUPER_BROWSER_URL`/`SUPER_BROWSER_TOKEN`, or supply the authorized HTTPS MCP `url`. Bearer connections use `SUPER_BROWSER_TOKEN`; otherwise complete OAuth. Do not assume a provider URL or invent an account. |
| ScrapeCreators | `SCRAPECREATORS_API_KEY`; official hosted MCP, then a selected public-content lookup. Discuss request credits before the check. |
| 1Password | Install the official `op` CLI in the agent runtime, then `OP_SERVICE_ACCOUNT_TOKEN` and a selected dedicated `vault_id`. Read vault metadata, never secret values, for verification. |
| Private collaboration | Supply `peer_name`, `peer_ip`, `incoming_token` and `outgoing_token` after pairing both intended agents; the shared helper binds to the private Tailscale interface and verifies a round trip plus rejection of an unknown peer. The older role helpers remain compatible. Keep dashboards and A2A private. |
| AgentCard | Separate `AGENTCARD_API_KEY` beginning `sk_test_`; setup rejects production keys. Only account/plan/balance/list tools are exposed. A real read proves the TEST connection. Production and purchasing require a later explicit authorization. |

Successful MCP capability checks are observed from real Hermes tool executions and bound to the connection fingerprint. The setup AI uses only a harmless read from the selected service, then runs `verify`. Account discovery alone is not proof. A status report describes the last completed check; re-run verification for a fresh live result. Changed credentials/settings invalidate prior evidence; expired credentials leave the step needing attention. Reconnecting allows new private credentials. Skipping a previously connected service does not revoke its provider account: use the provider’s disconnect/revoke control when that is the intended action.

## Phone transport and access

The supported phone transport is `onboarding/plugins/agentphone-channel`, a third-party Hermes platform adapter. It dispatches into the running Hermes gateway’s sessions and selected profile. The disabled legacy bridge is not used. Hosted AgentPhone MCP provides separately approved business call/text tools through the trusted primary channel. Direct SMS and voice reply through the running agent; outbound call tests omit `systemPrompt` so AgentPhone cannot substitute its hosted assistant.

The setup AI authorizes Tailscale on the intended computer, verifies a signed local adapter probe, and provisions a dedicated HTTPS Funnel port. Only the phone POST endpoint is exposed. It refuses to overwrite another service’s route and checks the resulting route and Funnel status. Hermes dashboard and A2A stay private.

Signed webhook timestamps have a five-minute window; event IDs and normalized payloads are deduplicated. SMS is saved before acknowledgement and recovered after restart. Uncertain outbound deliveries are held for reconciliation, never blindly resent. Voice streams an immediate acknowledgement and has a 25-second default deadline; late answers cannot become duplicate replies.

Approved owners pair each conversation using `Access <private passphrase>. <message>`; pairing expires after 15 minutes. The passphrase is removed before persistence or model processing. Caller ID alone cannot access owner context. Neither paired phone callers nor business callers can approve spending, permission changes or tool control prompts. Phone tool access is restricted to research; approved business mutations originate in the trusted primary channel.

Additional callers need an explicit `business_callers` list and a `public_business_brief`. They route to a separate profile with no owner memory, private apps or owner sessions. Workers do not inherit phone or inbox credentials. Give each independently selected installation its own connection; do not copy a root profile’s secrets to workers.

For live phone acceptance, use `phone-test --input PRIVATE_FILE` with `action` sms/voice, an approved `destination`, and `test_destination_selected: true`. The selection includes the relevant call/text charges. `action: status` reads provider evidence. Confirm receipt from the approved destination; complete both inbound and outbound voice/SMS. `phone-reconcile` checks a pending purchase or an uncertain SMS by `event_id` and its actual `provider_id`, validating the selected number, recipient and exact reply. Unresolved provider records remain needs-attention. If US SMS requires carrier registration, the setup AI walks through AgentPhone’s current registration requirements before claiming SMS readiness.

## Verification and release

Progress is private under `HERMES_HOME/.orgo-onboarding`, with `not_started`, `configured`, `verified`, `skipped` and `needs_attention` states. Reports contain check identifiers and fingerprints, not credentials or conversation text. Private provider receipts and delivery ledgers stay on the intended computer.

The reviewed runtime is Hermes **0.21.2**, tag **v2026.9.11**, commit **939e45c91d751fadd94dcd1b873ac3cb44846213**. Docker uses digest **sha256:9469b3e78b9545b6d576eb8887a95352e9a0ea83730eaf31431cf862ca1010e1**. Native installer downloads are checksum checked. Updates back up the private home, environment, deployment definition and native runtime, preserve custom identity/conversations/connections, and restore a complete backup after failure. Never restore an incomplete backup. Keep the failed tree for private diagnosis.

Run the repository’s installation checks and the shared adapter suite against that exact Hermes source. Unit and fixture tests are not live integration readiness. Promotion requires a fresh all-optionals-skipped install, interruption/resume, invalid credentials, custom Slack names, Honcho cross-session recall and agent isolation, real Latitude trace and outage behavior, two separate phone agents, voice delays, duplicate events, restart/failure recovery, and an update preserving private data. Validate Revenue Partner on an identified test Orgo computer first; then validate native and Docker roles and distribute/promote the same shared release. No specialized or Private Funding repositories are in this release.

## Primary integration references

- [Hermes platform adapters](https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters)
- [Honcho memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/honcho)
- [AgentPhone webhooks](https://docs.agentphone.ai/documentation/guides/webhooks)
- [AgentPhone calls](https://docs.agentphone.ai/documentation/guides/calls)
- [AgentMail inbox creation](https://docs.agentmail.to/api-reference/inboxes/create)
- [Composio MCP sessions](https://docs.composio.dev/docs/sessions-via-mcp)
- [ScrapeCreators hosted MCP](https://docs.scrapecreators.com/integrations/cli/)
- [AgentCard MCP](https://www.agentcard.sh/mcp) and [TEST key isolation](https://www.agentcard.sh/updates)
- [Tailscale Funnel](https://tailscale.com/docs/reference/tailscale-cli/funnel)
