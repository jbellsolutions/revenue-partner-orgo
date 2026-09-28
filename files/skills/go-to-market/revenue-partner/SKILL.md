---
name: revenue-partner
description: "Use when operating a unified Revenue Partner GTM system."
version: 1.0.1
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [go-to-market, revenue, outbound, reactivation, affiliates, content, partnerships]
    category: go-to-market
    related_skills: [grounded-research, agent-observability, agent-knowledge-vaults]
    created_by: agent
---

# Revenue Partner

## Purpose

Design and operate the complete front end as one coordinated Money Desk, not as disconnected channel tasks. Use one approved story, one outcome dashboard, and bounded specialists for research, analysis, and local drafting. External execution is unavailable in this image.

## Trigger Conditions

Load this skill when the user asks to:

- Build or operate a go-to-market/revenue system.
- Qualify an offer or map an ICP.
- Reactivate a database, lapsed customers, dead leads, or unclosed quotes.
- Build Direct outbound, Affiliates/partners, podcast/stage/sponsor opportunities, or Social and content.
- Create a campaign, partner program, prospect list, newsletter, weekly revenue report, or Fit Call map.
- Coordinate several GTM channels or replace disconnected vendors with one operating system.

## Non-Negotiable Outcome

Own the connected system and measure outcomes. Do not optimize for send counts, impressions, scraped-row totals, or draft volume at the expense of booked, attended, qualified, opportunity, pipeline, and closed-revenue outcomes.

## Stage Gate

Every engagement moves through:

`FIT_ASSESSMENT -> MAPPING -> ARCHITECTURE -> INFRASTRUCTURE_READY -> LAUNCH -> OPERATE_AND_OPTIMIZE`

Do not skip a gate. Read `references/operating-system.md` before designing a channel plan. Channel launch executes through Super Browser's approval lifecycle — see Campaign Approval.

### Fit assessment

Return one of:

- `fit` — paid offer, defined audience, sales capacity, coordinated-system willingness, realistic expectations.
- `conditional_fit` — a fixable readiness gap with an explicit prerequisite plan.
- `not_fit` — no validated paid offer, no target audience, no capacity to close, lowest-price-only intent, or permanent single-channel cherry-picking.

Produce a Fit Map with evidence, unknowns, starting engine, and recommendation.

### Canonical program CTA

When the offer being presented is the Revenue Partner program, use **Book a Fit Call**: a **30–45 minute, no-pitch, honest fit assessment**. The call should determine fit, produce or inform the Fit Map, and say so plainly when the program is not a fit. Do not relabel it as a demo or high-pressure sales call. A client campaign's CTA may differ only when approved in its campaign contract.

## Money Desk

### Engine 1 — owned demand

- Database reactivation.
- Lapsed-customer win-back.
- Dead-lead and unclosed-quote recovery.
- Newsletter and list warming.

### Engine 2 — new demand

- Affiliates and partners.
- Direct outbound.
- Podcasts, stages, conferences, seminars, and sponsors.
- Social and content distribution.

The four channel systems are **Affiliates and partners**, **Direct outbound**, **Reactivation**, and **Social and content**. Use shared positioning and proof across them.

## Operating Surfaces — the concrete work

These are the actual jobs, the platform each runs on, and the tool that performs
it. Route through the named tool; do not improvise a different path.

### Lead mining — the core job

This system began as a lead-mining and posting system and that is still its
purpose. Everything else is downstream: mine candidates from communities and
platforms, qualify them on real signals, enrich contacts off-platform, and post
back into those sources under approval.

Pipeline: **discover → normalize/dedupe → qualify → enrich → export → post.**
Oversample 3–5× the target at discovery; filtering attrition is large. No single
source has everything — merge and deduplicate across sources.

#### Two planes — do not confuse them

```text
agent
  ↓
lead-mining-posting MCP        ← CONTROL PLANE (ours)
  ├─ bounded strategies, provenance records
  ├─ dedupe / qualification boundary
  ├─ no posting, no CRM writes
  └─ Scrape Creators adapter   ← DATA PLANE (vendor)
       └─ scrape-creators hosted MCP / REST
```

**Route lead work through the control plane, not the vendor MCP.** The owned
server exposes ten typed tools — `provider_status`, `list_sources`,
`list_workflows`, `lead_strategy`, `youtube_search_creators`,
`youtube_channel_profile`, `youtube_creator_prospect`,
`link_in_bio_contact_surface`, plus bounded `scrape_public_route` /
`scrape_public_path` escape hatches that reach the whole provider surface. Unknown
routes, write methods and unbounded pagination fail closed.

Go direct to the vendor `scrape-creators` MCP only when a specific provider
endpoint is genuinely needed. The control plane keeps the provider interchangeable;
binding the agent to vendor endpoints throws that away.

#### Contact evidence — three outcomes, never collapsed

A creator search does not produce emails. Keep these distinct and never merge them:

- `public_email_returned`
- `public_contact_surface_found`
- `no_public_contact_found`

**Never turn `no_public_contact_found` into a guessed address.** The provider's
YouTube channel route frequently returns `email: null`; channel metadata alone
does not guarantee an email. The reliable path is: creator → channel profile →
public/social links → Linktree/Komi/Pillar/Linkbio/Linkme → public contact
surface → optional separate enrichment. A published address is **contact
evidence, not consent to outreach.**

#### Posting safety contract

Discovery and enrichment never imply a post. Every external action requires all
five: an exact draft and target scope; an unexpired explicit approval; a durable
one-use execution record; evidence of the submitted action or an explicit
ambiguous outcome; and reconciliation rather than blind retry when the outcome is
uncertain.

#### Export evidence

A production export carries: requested target and achieved unique count;
source/coverage ledger with provider run or dataset IDs; schema and field
definitions; canonicalization and dedupe rules; contact evidence URLs and
verification statuses; known gaps, blocked lanes and cost summary; and local
artifacts with a manifest. **A pilot is a preflight, not the deliverable.** Do not
invent missing fields or silently downscope a requested list.

| Source | What is minable | Route |
|---|---|---|
| **Skool groups** | Group lists, members, posts, comments, engagement | Primary community source — see invariants |
| Facebook groups | Posts, commenters, member activity | `super-browser` on a saved-cookie profile |
| LinkedIn | Posts, post commenters, company/profile | Public routes first; account only as last resort |
| Instagram / TikTok / YouTube | Creators, popular posts, commenters | `scrape-creators` public routes, no login |
| Reddit | Subreddit posts and commenters | `scrape-creators` |
| Craigslist / Marketplace | Listings as lead sources | `super-browser`, no login for reads |
| Circle / Mighty Networks / Discord / Slack / Telegram | Members, activity | Same email invariant as Skool |

#### Skool invariants — established, do not relitigate

- **Skool never exposes member emails.** Not by DOM, not by API, not to an
  authenticated member viewing a group they belong to — every member returns
  `email: ""`. This is a privacy invariant, not a scrape-depth problem. Actors
  advertising "Skool member scraper with email" return an empty `email` field;
  their own output schemas say so. Do not spend on them.
- **Qualify on engagement; capture email off-platform.** Post count, last-active,
  classroom activity and comments are real and minable — qualify on those. Email
  comes from the member's own linked website/socials, or from opt-in capture
  (connect → lead magnet → email) over weeks. There is no one-shot path to
  thousands of Skool emails, and pretending otherwise wastes budget.
- **`lastOffline` is MICROSECONDS**, as are `approvedAt` and `requestedAt`. The
  wrong divisor still lands in 2026 and looks correct — sanity-check every parsed
  date; year 1970 or 56,000+ means the power of ten is wrong.
- **The active window is 9 days**, not the 90-day cold-outreach default. Confirm
  the window on every new request rather than assuming either number.
- **`/users/<UID>/groups` paginates with `?offset=N`**, not a cursor; the response
  is `{groups, has_more, members: null}` — stop when `has_more` is false. The
  public `/-/members?p=N` is different: 1-indexed, 30 per page.
- **`user_id` lives in the `auth_token` JWT**, not the HTML — the page carries
  several 32-hex values and scraping it grabs the wrong one. Skool has no `/me`.
- **Owner socials are snake_case on the public page, camelCase on the authed API**
  (`link_website` vs `linkWebsite`). Probe the keys on one record before writing a
  worker, or the batch returns blank and has to be re-scraped.

#### Rate limits and blocks are a stop signal

If a source rate-limits, challenges, or blocks, **stop and report it**. Do not
retry harder, and do not route around the block. Circumventing an access control
after a platform has refused is where ToS violation becomes CFAA exposure, and it
is out of scope for this agent regardless of what a scraper library makes
possible. Prefer a documented API, a lower rate, or a source that permits the
access.

#### Paid-actor rule

Never run a paid marketplace actor on its title and description. Open the README
and read the actual output schema, read the 1- and 2-star reviews, and run a
free-tier test first. Actors routinely advertise fields they return empty.

### Affiliate and influencer sourcing → recruiting

| Job | Platform | Tool |
|---|---|---|
| Find affiliate/influencer candidates | Instagram, TikTok, YouTube, LinkedIn, Reddit | `scrape-creators` public routes; `super-browser` (Apify / Bright Data lanes) |
| Pull a candidate's most-engaged recent posts | same | `scrape-creators` profile/post routes |
| Extract who commented on those posts | Instagram, Reddit | `scrape-creators` `post_comments`, `post_comment_replies` |
| Score and dedupe candidates into a lead list | local | vault + `03.Campaigns/<id>/sources.csv` |
| Recruit candidates and run the affiliate program | email / DM | `affiliate-manager` (Instantly + SmartLead, reply daemons) |

Commenters on an affiliate's post are themselves warm leads: they self-selected
into the topic. Capture them with provenance, never as anonymous volume.

### Social engagement

| Job | Platform | Tool |
|---|---|---|
| Comment on a candidate's post to earn attention | Instagram, LinkedIn, Reddit, X | `super-browser` (Airtop / Browser Use on a logged-in profile) |
| DM / outreach to a candidate | X, LinkedIn | `super-browser` on a logged-in profile |

**Comments disclose affiliation.** Undisclosed promotional comments are FTC
Endorsement Guides exposure, separate from any platform ToS question — and a
disclosed comment from someone with a stake converts better than anonymous
praise. Write comments that add something a reader would value even if they never
click. Never post generic filler.

### Classified and marketplace posting

| Job | Platform | Tool |
|---|---|---|
| Post an ad | Craigslist, Facebook Marketplace | local Chrome profile first; Orgo desktop as fallback when the local machine is unavailable |
| Post into groups | Facebook groups | `super-browser` (Browser Use / Hyperbrowser) on a saved-cookie profile |
| Scrape listings for leads | Craigslist | `super-browser` (Playwright / Bright Data unlocker) — no login |
| Poll replies to posted ads | Craigslist, Marketplace, groups | same profile that posted |

These platforms have no API by design. Posting runs on the operator's own
logged-in profiles, with immutable audit records and idempotency keys so a retry
never double-posts. **No detection evasion** — no proxy rotation, fingerprint
spoofing, or CAPTCHA solving.

### Email

| Job | Tool |
|---|---|
| Launch a cold campaign | `affiliate-manager` (Instantly / SmartLead) |
| Classify and draft replies to responses | `affiliate-manager` reply daemons |
| Read a specific inbox thread | Composio Gmail, behind the connector gate |

Campaign launch and Gmail send stay approval-gated: email reputation and domain
health are not recoverable the way a re-post is.

## Four Pillars Readiness Check

For every proposed channel, score:

1. Architecture.
2. Data.
3. Infrastructure.
4. Execution: the named tool for the job, the account or profile it runs on, the volume and cadence, and the stop rule.

A channel stays blocked until its required owner, story, source data, exclusions, sender/infrastructure, tracking, approvals, and success/stop rules are explicit.

## Default Planning and Drafting Order

1. Inspect owned demand/reactivation first.
2. Prepare targeted outbound plans and drafts when deliverability, data, and sales capacity pass.
3. Design affiliate/partner recruiting and management as an active operating plan, not a passive signup page.
4. Use **SpeakerAgent Riley** to discover and score podcast, stage, conference, seminar, and sponsor opportunities.
5. Coordinate newsletter/social drafts so every channel tells the same approved story.

Phased rollout is supported. Permanent isolated-channel operation is not the Revenue Partner model.

## Campaign Approval

Before any external campaign action, create and obtain approval for `references/campaign-contract.md`.

Autonomous by default when logged:

- Read-only research.
- Source validation.
- Scoring and deduplication.
- Analysis and recommendations.
- Internal drafts and reports.

External writes execute through Super Browser's approval lifecycle: an
approval id, stage, action fingerprint and plan fingerprint, a 30-minute
freshness window, atomic execution claim, and duplicate-write retry protection.
An approval authorizes one exact action; a changed plan invalidates it.

Standing approval covers repetitive posting on the operator's own profiles —
Craigslist, Marketplace, and Facebook groups — where a mistake costs a re-post.
Per-action approval is still required for anything whose blast radius is not
recoverable: cold-email campaign launch, Gmail send, paid placement or spend,
bulk CRM mutation, and any commitment on pricing, contract, or affiliate terms.

## Web Work and Production-Scale Data

All browser, scraping, research, or lead-generation work begins with a structured **five-round council**:

1. Classify the task.
2. Identify eligible providers and data lanes.
3. Compare at least three viable routes when available.
4. Check live readiness, cost, evidence, and safety.
5. Select execution/fallback plus a verification contract.

Which server does what:

| Work | Route |
|---|---|
| Read a page, check a site, research a company or person | browser-box `fetch` (fast, free); `read` when `fetch` comes back empty or needs JavaScript |
| Read behind a login | browser-box `session` (the operator signs in once), then `read` |
| Clean content or links from a known URL, with a cost cap | data-box `scrape`; follow slow calls with `job` |
| Public social data (TikTok, Instagram, YouTube, LinkedIn, Facebook, Reddit, Threads, ad libraries) | Scrape Creators |
| Bulk lead lists (Apify / Bright Data lanes, thousands of records) | Super Browser |
| Any external write: posting, commenting, DMs, form submissions | Super Browser's approval lifecycle only (see Campaign Approval) |

browser-box here has read tools only; it cannot post or send. Call `status` on a server before
relying on it, and report a refusal (private address, busy browser) instead of retrying it unchanged.

Do not claim readiness without proof. Preserve source URL, retrieval status, provenance, evidence/inference labels, deduplication criteria, coverage, exact count, and failures.

If the user requests a list without quantity, target at least **5,000** unique verified records when sources and budget permit. Label pilots as pilots and continue to production scale unless the user asks to stop. Never silently downscope or invent missing fields.

## SpeakerAgent Riley

Riley is a bounded opportunity-research and drafting specialist:

- Find relevant shows, podcasts, conferences, seminars, stages, and sponsors.
- Score audience fit, reachability, strategic value, and evidence quality.
- Draft pitches and preparation in the approved voice.
- Track source, status, owner, and next action.

A human owns the relationship and closing. Riley must not autonomously negotiate terms, promise attendance, accept sponsorship commitments, or impersonate the operator. A campaign approval does not enable those actions in this image.

## Target and Claim Guardrail

The source page says the target is **2–4 booked meetings/day** from hot leads. This is a **target/expectation, not a guarantee or typical result**. Always pair the figure with the caveat that outcomes depend on offer, market, and close rate.

Never invent:

- Price or commission percentage.
- Attribution window.
- Contract/SLA/cancellation terms.
- Case studies or performance history.
- Client names, logos, or proof permission.
- Revenue, ROI, sponsor, placement, attendance, or close-rate guarantees.

### Canonical cost response

When asked “What does it cost?”, answer only from the page:

- The commercial model has three components: an ongoing Money Desk, one-time infrastructure setup, and one-time talent placement.
- The ongoing Money Desk may be structured as an internal base plus commission **or** as straight growth monthly.
- Exact numbers and percentages are not published in the supplied source.
- Offer to **Book a Fit Call** for the fit map, starting point, timing, and a source-authorized commercial discussion. Do not invent a dollar amount, fee, or commission percentage.

## Required Artifacts

Write durable artifacts into the knowledge vault:

- Fit Map.
- Canonical Positioning and Approved Claims.
- Money Desk Map.
- Channel Readiness Matrix.
- Campaign Contract.
- Source and Suppression Ledger.
- Daily Action Queue.
- Opportunity/Partner Scorecard.
- Weekly Revenue Report with `continue|modify|stop` decisions.
- Decision log and postmortems.

Secrets never enter the vault.

## Daily Operating Loop

1. Read `$HERMES_HOME/agent-knowledge/INDEX.md` (or the deployed equivalent)
   and its linked current priorities.
2. Read active campaign contracts and open decisions.
3. Reconcile changed outcomes and blockers.
4. Execute the highest-value approved work.
5. Verify external effects and log evidence.
6. Escalate only decisions, deviations, and failures that require the operator.

## Weekly Operating Loop

1. Reconcile attribution and funnel stages.
2. Report booked, attended, qualified, opportunity, pipeline, and revenue separately.
3. Compare results with the campaign contract.
4. Issue `continue`, `modify`, or `stop` for every experiment.
5. Update source-backed learnings and propose the next bounded test.

## Verification

Before claiming completion:

- Fit decision exists and is evidence-backed.
- Activated channels passed all four pillars.
- Campaign contract is approved for any external action.
- Sources, provenance, deduplication, coverage, and exact counts are reported.
- External writes have durable IDs or read-back evidence.
- Target language includes the non-guarantee caveat.
- Weekly outcomes are separated from activity metrics.
- Failures and approval deviations are visible in observability/logs.

See:

- `references/operating-system.md`
- `references/campaign-contract.md`
- `references/source-ledger.md`
- `references/acceptance-tests.md`
