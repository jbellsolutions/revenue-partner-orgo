# Operator Guide

## Operating principle

Revenue Partner Agent coordinates the front end of the business. It is not authorized to invent customer facts, proof, pricing, consent, campaign scope, or performance.

The canonical CTA is **Book a Fit Call**.

## 1. Complete the knowledge vault

Before asking for campaign execution, fill the operator-controlled records under `files/agent-knowledge/` or their deployed equivalents.

Required minimum:

- company and paid offer;
- target customer and exclusions;
- validated proof and approved claims;
- sales capacity and closing owner;
- existing lists, channels, and systems;
- suppression, consent, and opt-out rules;
- CRM/source-of-truth mapping;
- budget and spend authority;
- current priorities.

Do not replace an unknown with a plausible assumption. Record it as `unknown` and resolve it.

## 2. Run the fit gate

The agent classifies the business as:

- `fit` — required evidence is present and no hard blocker is active;
- `conditional_fit` — the operating model may fit after named gaps are resolved;
- `not_fit` — a hard requirement is absent or expectations conflict with the model.

Hard requirements:

1. A paid offer with real commercial validation.
2. A defined audience or customer profile.
3. Capacity to answer and close qualified conversations.
4. Willingness to coordinate channels rather than isolate one forever.
5. Expectations aligned with compounding execution rather than an overnight spike.

A `conditional_fit` result must list the missing evidence, owner, and decision needed. It is not approval to launch.

## 3. Map the Money Desk

### Owned demand

Inventory:

- past customers;
- lapsed customers;
- dead or unworked leads;
- unclosed quotes and proposals;
- newsletter/list subscribers;
- prior event, webinar, or content audiences.

Record source, consent basis, recency, quality, suppression state, and recoverability.

### New demand

Map:

- direct outbound;
- affiliates and partners;
- podcasts, stages, conferences, seminars, and sponsors;
- coordinated newsletter/social content.

Do not start all channels simultaneously by default. Begin with the strongest evidence and shortest safe path to learning.

### Production connector activation

Writable MCP connectors and executable CLIs for [Orgo](https://orgo.ai?r=aiguy), Composio, AgentMail, AgentPhone, AgentCard, Linear, Spotify, and X do not ship in the runtime; the removed [Orgo](https://orgo.ai?r=aiguy) Desktop plugin/client/CLI also does not ship. Remote platform toolsets omit generic terminal, code-execution, scheduling, delegation, browser, computer-use, media-generation, and connector-control paths. A key, login, flag change, restart, approval record, or chat request cannot activate production execution in this immutable image. Enabling any connector requires operator-controlled source/configuration changes, complete verification, a fresh exact-tree review, a rebuilt image, and a new release.

## 4. Prepare research and drafts

The agent may autonomously perform logged read-only research, scoring, deduplication, analysis, local drafts, forecasts, and internal reports.

Every research artifact should include:

- source URL or system;
- retrieval time/status;
- extracted evidence;
- inference labels;
- deduplication key;
- missing fields;
- confidence and failure notes.

Internal campaign drafting remains local Hermes text work. Do not route it through a browser provider merely to generate copy.

## 5. Approve a campaign contract

Before any send, publish, CRM mutation, launch, activation, spend, suppression change, or consent-state change, approve a written contract containing:

- campaign objective;
- audience and exclusions;
- source and provenance;
- channel and sender identity;
- approved claims and variants;
- volume and pacing;
- schedule and geography;
- budget and spend ceiling;
- suppression/opt-out handling;
- CRM field mapping and source of truth;
- success, pause, and stop thresholds;
- approval owner and expiry.

Credentials establish connectivity only. They are never campaign approval.

## 6. Operate inside bounds

Pause and escalate when:

- the audience, sender, claim, volume, budget, or channel changes;
- consent or suppression evidence is missing;
- complaint, bounce, or reputation behavior is unusual;
- authentication or permissions change;
- a new integration or sensitive data class is introduced;
- retry behavior could duplicate an external write;
- the operator requests a commitment, contract, discount, placement, or purchase outside scope.

## 7. Report outcomes correctly

Keep these metrics separate:

1. Booked meetings.
2. Attended meetings.
3. Qualified meetings.
4. Opportunities.
5. Pipeline value.
6. Closed revenue.

Also report volume, delivery, replies, positive replies, complaints, opt-outs, cost, source coverage, and attribution caveats.

Never turn the source’s `2–4 booked meetings/day` target into a guarantee, benchmark, or claimed typical result.

## 8. Weekly decision review

For every active lane, return one recommendation:

- **continue** — evidence supports staying inside current bounds;
- **modify** — name the variable, evidence, and approval needed;
- **pause** — stop temporarily while a risk or dependency is resolved;
- **stop** — the lane fails fit, economics, consent, reputation, or quality requirements.

The operator owns final approval and relationship/closing decisions.

## Example safe requests

- “Assess fit using only facts in the vault; list unknowns.”
- “Research 100 relevant stages and preserve source URLs; do not contact anyone.”
- “Draft three internal reactivation variants locally; do not send.”
- “Separate booked, attended, qualified, opportunity, pipeline, and closed revenue.”

## Example production requests requiring approval

- “Launch the campaign.”
- “Publish this post.”
- “Send the sequence.”
- “Activate the ads.”
- “Update these CRM records.”
- “Change suppression status.”
- “Buy the sponsorship.”

Mixed requests remain production requests even if they also say “draft,” “research,” “review,” or “do not publish” elsewhere.