# Security Model

## Security objectives

Revenue Partner Agent is designed to:

1. keep credentials out of Git and the golden image;
2. prevent ambiguous production requests from becoming approval-free provider execution;
3. reduce the blast radius of inbound channels and specialists;
4. preserve source, consent, suppression, spend, and CRM boundaries;
5. fail closed when validation, publication, build, or approval evidence is missing;
6. describe enforcement honestly rather than claiming every optional integration has the same runtime gate.

## Threat model

Primary risks:

- credential leakage through committed dotenv files, logs, generated launch files, or template payloads;
- shell evaluation of untrusted environment values;
- natural-language authorization bypass using articles, synonyms, modifiers, punctuation, word order, pronouns, or mixed intents;
- stale, missing, expired, or mismatched approval records;
- provider execution before approval persistence;
- inbound phone requests enabling broad tools;
- duplicate external writes during retry/resume;
- tenant identity or customer facts leaking into reusable artifacts;
- source marketing claims being presented as verified results;
- validation or publication failures being treated as success.

## Secret handling

- The repository contains key names/references, not credential values.
- Runtime secrets belong in the operator environment or configured secret manager.
- `.env`, launch JSON, generated resolved output, caches, and research captures are ignored.
- `safe-env-bridge.py` parses only allowlisted keys, rewrites the target as allowlist-only, and does not execute shell syntax.
- Output replacement is atomic and mode `0600`.
- Child processes are invoked as argv with `os.execvpe`, not a shell command string.
- Exec children receive only a minimal safe process-context allowlist plus managed values parsed from the target file; unmanaged inherited variables and Hermes policy flags are dropped.
- Release verification compares actual supplied credential values against staged blobs without printing the values.
- The hash-locked environment is created and synchronized before credentials enter any process. Both `safe-env-bridge.py` and `release_entry.py` are started by that absolute interpreter with `-I -s -E`; the entrypoint refuses non-isolated startup, then forks before inspecting any credential value. Each child computes the credential digest from its own environment copy; the broker child alone retains `ORGO_API_KEY`, while the builder child drops the key and `execve`s the key-less `build_template.py`, again under `-I -s -E`. The builder exposes no credential accessor, TLS opener, or generic authenticated request primitive. The isolated broker independently verifies current tree/artifact/publication bytes against `/etc/revenue-partner/reviewers.allowed_signers`, which must be root-owned, non-writable, and byte-identical to the tracked declaration. Candidate-controlled signer bytes alone grant no authority.
- Remote validation requires a semantic `{ok: true, template}` response whose echoed document binds the canonical `api_version`, template name/version, and the exact file inventory; an empty or merely successful 2xx fails closed. Authenticated publication and readback responses must bind the exact `namespace/name@version` reference and a digest matching the signed publication bytes; build responses must bind the same reference/digest with a `building` or `ready` status; launch responses must bind the requested workspace ID and a computer ID.
- Every authenticated operation additionally requires an external `release-operator` signature over a fresh nonce, `issued_at`/`expires_at` freshness window, operation, exact method/URL, request-body digest, publication/build identities where applicable, tree, and product digests. The broker accepts only six operation-specific canonical request shapes. It independently validates and atomically consumes the nonce in a fixed launcher-controlled ledger (`REVENUE_PARTNER_NONCE_LEDGER`, an owner-only directory under a root-owned sticky parent) before reading `ORGO_API_KEY`, constructing a fresh proxy-free/no-redirect opener, or constructing the exact request. Caller-controlled `HOME` cannot select or reset the ledger. Resetting mutable builder state, direct helper import, replay, receipt mutation, missing intent, or signature failure cannot expose the key or reach authenticated network transport.
- The release entry generates a per-run MAC secret; each child computes the SHA-256 of the exact credential from its own environment copy. The builder must bind the credential digest in every broker request, and every broker response frame is HMAC-authenticated with the per-run secret; a forged or unauthenticated IPC peer cannot fabricate publication, readback, build, event, or launch evidence. The broker itself re-validates every 2xx response body against the operation-specific identity contract before returning it.
- Authenticated event streams are read incrementally inside the broker with per-line, cumulative-byte, event-count, and absolute monotonic deadline limits; a trickling stream cannot hold the credential-bearing broker open past the deadline. Every `HTTPError` response is closed on all paths in the broker, the public raw-HTTP helper, and the Latitude telemetry transport.
- Every `git`/`ssh-keygen` subprocess spawned by the release entry, the key-less builder, or the credential-bearing broker runs in a from-scratch environment containing only `PATH`, `HOME=/tmp`, `GIT_CONFIG_NOSYSTEM=1`, and `GIT_CONFIG_GLOBAL=/dev/null`, and every `git` invocation additionally passes `-c core.fsmonitor=false`. The release entry builds both child environments from scratch and forwards only the explicit release allowlist (`ORGO_API_KEY`, `REVENUE_PARTNER_REVIEW_ATTESTATIONS`, `REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY`, `REVENUE_PARTNER_NONCE_LEDGER`). Operator gitconfig, `core.fsmonitor` hooks (including `GIT_CONFIG_COUNT`/`GIT_CONFIG_PARAMETERS` injection), and index/object-directory redirection cannot execute code or redirect Git state in a process that holds `ORGO_API_KEY`.

## Production approval boundary

Fresh explicit approval is required before:

- outbound sends;
- publication;
- CRM mutation;
- campaign/ad launch, activation, resume, or schedule;
- spending or paid placement;
- suppression or consent-state changes;
- sensitive or regulated data use;
- pricing, contract, discount, affiliate, sponsor, or other commitments;
- new integrations or permission expansion.

Credentials prove connectivity only. A draft, plan, research request, stored plan flag, or delegated specialist task is not authority.

Hermes runs with `approvals.mode: manual`, MCP reload and destructive slash confirmations enabled, and hook auto-accept disabled. Release-listed [Orgo](https://orgo.ai?r=aiguy), Composio, AgentMail, AgentPhone, AgentCard, and X connector runtimes/CLIs are absent; the hash-locked upstream Hermes wheel's Spotify, Slack, Discord, and Linear catalog surfaces are removed by a version-bound, fail-closed image-build pruner before Hermes executes. Their credentials are rejected by the safe-environment bridge, including explicit `--only` selection. Remote platform toolsets omit terminal, code execution, scheduling, delegation, browser, computer-use, media-generation, and connector-control surfaces. Enabling one of those named connectors requires separately reviewed source/configuration changes, a rebuilt image, and a new release. Super Browser omits approval from MCP, CLI, Slack, handoff, and agent command surfaces; approval-required runs cannot execute inside this template runtime.

## Super Browser enforcement

The protected object family includes ad, advert, advertisement, advertising, and campaign, singular or plural.

If such an object reaches Super Browser:

- it is not classified as generic draft-only work;
- it fails closed to external-write approval;
- exceptions are limited to anchored whole-request read-only forms and a bounded public-search submission;
- early local-output, local-delivery, search, or read-only helpers cannot swallow a production follow-up;
- planning persists `awaiting_approval` before execution is considered;
- resume stops while approval is pending;
- adapters recompute policy and block approval-required work before provider construction; approval records are audit evidence only and cannot activate execution in this image.
- ordinary outbound verbs such as send, dispatch, deliver, forward, notify, invite, and broadcast fail closed even when they do not use campaign terminology.

Internal campaign drafting remains autonomous only as local Hermes text work.

## AgentPhone enforcement

- deny-all before sender allowlisting;
- no full-tool or YOLO inheritance;
- toolsets clamped to `web` and `vision`;
- inbound requests cannot directly authorize production work;
- production requests return to the primary operator channel.
- local attachments must originate under the operator-owned generated-media root;
- arbitrary absolute paths, traversal, and file/directory symlink escapes are rejected;
- approved files are opened with `O_NOFOLLOW` and copied into a non-symlink mode-`0700` cache as mode-`0600` short-lived entries.
- arbitrary remote attachments are always rejected; only bridge-generated URLs backed by approved local files are attachable, so downstream DNS resolution and redirects cannot expand the trust boundary.
- webhook bodies are capped before buffering or HMAC verification; oversized unauthenticated requests receive `413` without body reads or pre-auth logging.

## Source and tenant isolation

Reusable template content distinguishes:

- direct source claims;
- self-reported claims;
- targets;
- implementation inference;
- unknown customer facts;
- live verified results.

Customer-specific facts remain unset in the golden template. Raw research captures stay excluded unless deliberately curated.

## Build supply chain

- Hermes, uv, QR support, and their complete transitive graph are version- and hash-locked.
- No model-callable filesystem MCP or remote connector MCP is installed; the only configured MCP is the locally bundled Super Browser policy server.
- Node, 1Password CLI, and Obsidian use versioned URLs plus SHA-256 verification before execution.
- Super Browser installs its complete transitive graph under `--require-hashes`, then registers reviewed source and metadata directly with the standard library; no local pip project install, setuptools, wheel, PEP 517, dependency resolution, build isolation, or network is used.
- Floating `latest` downloads, pipe-to-shell installers, unpinned npm fallbacks, and runtime QR installs are prohibited by regression tests.

These controls cover application-level inputs, not the [Orgo](https://orgo.ai?r=aiguy) base image or apt repository snapshot. See [`SUPPLY_CHAIN.md`](SUPPLY_CHAIN.md).

## Validation and release controls

- local JSON Schema validation fails closed;
- authenticated remote validation is a separate gate;
- publication collision fails;
- build must reach explicit `ready`;
- launch response is captured separately;
- exact staged tree receives independent review;
- any source edit invalidates prior review;
- release credential scans operate on immutable staged blobs;
- publication, build, launch, and smoke are reported separately.

## Known enforcement limits

SOUL and skill instructions govern agent behavior, but they are not universal durable gates for every optional connector.

Durable code gates are specifically implemented in the hardened Super Browser path and AgentPhone reference bridge. The named production integrations in this release contract are absent or removed by the exact-version build pruner and their credentials are rejected. The upstream Hermes distribution may contain unrelated optional transport code outside this release contract; it is not configured, credentialed, or represented as removed. Future activation of any production integration requires separately reviewed source and configuration changes, updated locks, an image rebuild, a new immutable release, and fresh exact-tree clearance. Do not represent any integration as bound to a campaign-record approval unless code and tests establish that fact.

## Safe failure behavior

When uncertain:

- preserve data and evidence;
- do not send, publish, mutate, activate, spend, or change consent;
- return `awaiting_approval` or stop;
- state the missing approval/evidence;
- avoid retries that could duplicate an external write;
- log the decision and escalate.

## Reporting a vulnerability

Follow the private reporting instructions in the repository-level [`SECURITY.md`](../SECURITY.md). Do not open a public issue containing credentials, bypass payloads against a live account, private customer data, or exploit-ready details.