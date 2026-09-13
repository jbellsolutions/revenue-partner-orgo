> Legacy custom-template reference. The supported Orgo installation and live verification contract is [the shared walkthrough](../onboarding/GUIDE.md). Do not use the disabled legacy phone bridge for new installs.

# Deployment Guide

> This document covers the advanced deterministic [Orgo](https://orgo.ai?r=aiguy) release pipeline. For a
> new owner who wants Revenue Partner working in Slack on a private VPS, use
> [`START-HERE.md`](../START-HERE.md) and [`SLACK-SETUP.md`](SLACK-SETUP.md).

## Release identity

- Template namespace: `default`
- Template name: `revenue-partner-agent`
- Template version: `1.0.1`
- Target runtime: Linux x86_64, Python 3.11

Template versions are immutable. Change `VERSION` for any rebuilt release.

## Prerequisites

Local:

- Python 3.11
- `uv`
- Git
- network access to the authenticated [Orgo](https://orgo.ai?r=aiguy) API

[Orgo](https://orgo.ai?r=aiguy):

- API key with template validation/build access;
- workspace ID;
- an account tier that permits template publication (the API currently requires Scale or higher for this operation);
- capacity for a 4 GB RAM / 1 CPU smoke computer.

Credentials must remain outside the repository. A minimal external environment file contains:

```dotenv
ORGO_API_KEY=...
ORGO_WORKSPACE_ID=...
REVENUE_PARTNER_REVIEW_ATTESTATIONS=/absolute/path/to/attestation.json
REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY=/absolute/path/to/mode-0700-directory
REVENUE_PARTNER_NONCE_LEDGER=/absolute/path/to/mode-0700-directory
```

The nonce ledger must be an owner-only mode-`0700` directory whose parent is root-owned and sticky (mode `1777`), so a caller-controlled `HOME` cannot select or reset consumed nonces. Create it once with an admin:

```bash
sudo install -d -o root -m 1777 /var/tmp/revenue-partner
install -d -m 0700 /var/tmp/revenue-partner/consumed-operation-intents
```

and set `REVENUE_PARTNER_NONCE_LEDGER=/var/tmp/revenue-partner/consumed-operation-intents`.

Never source that file as shell code. Use `files/safe-env-bridge.py`.

Application-level build dependencies are pinned by Python locks and checksum constants documented in [`SUPPLY_CHAIN.md`](SUPPLY_CHAIN.md). Regenerating a lock or changing an artifact pin is a release change that requires a version bump and fresh review.

## 1. Verify the checkout and assemble locally

```bash
REVENUE_PARTNER_VERIFY_PYTHON=/absolute/path/to/trusted/python3.11 bash .github/scripts/verify_release
```

Hosted CI uses this same launcher with the absolute interpreter supplied by the pinned `setup-python` action. The non-Python launcher rejects mutable/untracked source, archives one exact Git-index tree, clears Python/pip/proxy/certificate startup contamination, and invokes an isolated interpreter. It creates a disposable environment from `requirements-ci.lock` under `--require-hashes`; parses exact-index YAML and skill frontmatter; scans exact-index credentials; validates links/assets; runs the Revenue Partner, Latitude telemetry, packaged Super Browser, and AgentPhone suites; compiles shipped Python; checks tracked and embedded shell programs; rechecks exact-tree parity; validates against the checksum-bound [Orgo](https://orgo.ai?r=aiguy) schema; assembles the template; and verifies the decoded assembled Super Browser payload.

Expected result:

- `revenue-partner-agent.resolved.json` is produced;
- local JSON Schema validation passes;
- no publication occurs.

The resolved file is generated and ignored by Git.

## 2. Authenticated remote validation

Before loading any credential, create a fresh interpreter from the same hash-locked verification requirements. The resulting absolute path is reused for the isolated safe bridge and release entry:

```bash
uv venv --python /absolute/path/to/trusted/python3.11 .artifacts/release-venv
uv pip sync --python .artifacts/release-venv/bin/python --require-hashes requirements-ci.lock
LOCKED_RELEASE_PY="$PWD/.artifacts/release-venv/bin/python"
"$LOCKED_RELEASE_PY" -I -s -E files/safe-env-bridge.py \
  --source /absolute/path/to/revenue-partner.env \
  --target /tmp/revenue-partner.env \
  --only ORGO_API_KEY \
  --only REVENUE_PARTNER_REVIEW_ATTESTATIONS \
  --only REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY \
  --only REVENUE_PARTNER_NONCE_LEDGER \
  --exec env -u VIRTUAL_ENV -u PYTHONPATH \
  "$LOCKED_RELEASE_PY" -I -s -E \
    release_entry.py --remote-validate
```

A successful response from `/api/templates/validate` is evidence of schema acceptance only. It is not publication, image readiness, launch, or live runtime proof. Because this endpoint is authenticated, remote validation requires the same two signed exact-tree reviews as publication. A 2xx status alone is rejected: the response must contain `ok: true` and an echoed template document binding the canonical `api_version`, template name/version, and the exact file inventory. `release_entry.py` forks an isolated broker that alone retains `ORGO_API_KEY`, removes the key before execing the builder, and permits transport only after the broker independently re-verifies signed current bytes and consumes the exact one-use validation intent.

Before publication, the documentation and security reviewers must each return exactly `CLEAR` for the frozen tree. Each reviewer then signs a canonical statement containing that verdict, the exact Git tree, resolved-artifact SHA-256, and serialized-publication-envelope SHA-256 using their external Ed25519 key and the `revenue-partner-review` SSH signature namespace. The candidate declaration [`.github/reviewers.allowed_signers`](../.github/reviewers.allowed_signers) is not a trust root. An administrator must install identical bytes as the fixed root-owned external policy before any authenticated operation:

```bash
sudo install -d -o root -m 0755 /etc/revenue-partner
sudo install -o root -m 0644 .github/reviewers.allowed_signers /etc/revenue-partner/reviewers.allowed_signers
cmp .github/reviewers.allowed_signers /etc/revenue-partner/reviewers.allowed_signers
```

Both the key-less builder clearance gate and the isolated broker reject a missing, writable, non-root-owned, or byte-mismatched external policy. Signature files and the JSON attestation must be owner-only mode-`0600` regular files. Put the attestation's absolute path in the external environment file as `REVENUE_PARTNER_REVIEW_ATTESTATIONS=/absolute/path/to/attestation.json`.

The builder rejects worktree/index drift and non-ignored untracked files. The broker independently repeats those checks, reads candidate signer metadata from the exact Git index, verifies both OpenSSH signatures through fixed `/usr/bin/ssh-keygen` and the external policy, and strips the key from every Git/signature-verifier subprocess environment. A one-use request intent carries the exact method, URL, immutable body bytes, and publication identity, but that Python object is not trusted as authorization: the broker independently re-verifies the signed current tree/artifact/publication bytes and exact operation/body immediately before request construction. Reviewer private keys remain outside the repository and publication runtime; changing either signer declaration or external policy invalidates clearance.

## 3. Publish and build

```bash
"$LOCKED_RELEASE_PY" -I -s -E files/safe-env-bridge.py \
  --source /absolute/path/to/revenue-partner.env \
  --target /tmp/revenue-partner.env \
  --only ORGO_API_KEY \
  --only REVENUE_PARTNER_REVIEW_ATTESTATIONS \
  --only REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY \
  --only REVENUE_PARTNER_NONCE_LEDGER \
  --exec env -u VIRTUAL_ENV -u PYTHONPATH \
  "$LOCKED_RELEASE_PY" -I -s -E \
    release_entry.py --build --launch 'WORKSPACE_ID'
```

The builder:

1. reassembles and validates the artifact;
2. publishes `default/revenue-partner-agent@1.0.1`;
3. requires the response to bind the exact template reference, a server-returned digest matching the signed publication bytes, and a published timestamp;
4. refuses a version collision;
5. reads the immutable `namespace/name@version` back and requires the remote reference and digest to match immediately before build, then addresses build by that immutable reference;
6. requires the build response to bind the same reference and digest with a `building` or `ready` status;
7. repeats immutable publication readback, then requires a separate `release-operator` signature over a fresh 256-bit nonce, method `GET`, exact event URL, current tree, and both product digests; atomically consumes that nonce at the lowest SSE transport boundary before credential lookup, addresses the canonical `…/build/events` stream, and accepts `ready` only from that exact reference under fixed line, byte, event-count, socket-timeout, and wall-clock ceilings;
8. exits nonzero unless the build reaches `ready`;
9. reads the immutable publication reference back again immediately before launch, submits that reference, and requires a matching computer ID and workspace ID in the response.

Publication, build, ready-event, and launch identities are bound to the immutable `namespace/name@version` reference and content digest; conflicting or missing fields are rejected.

Every authenticated `HTTPError` body is read through the same bounded reader and closed in `finally`, including declared-size rejection, streamed overflow, JSON rejection, publication/build/launch failures, and SSE failures.

Set `REVENUE_PARTNER_OPERATION_INTENT_DIRECTORY` to an existing absolute owner-only mode-`0700` directory before any authenticated validation or deployment command. Immediately before **every** authenticated request—validation, publication, immutable readback, build, build-event GET, and launch—the key-less builder writes `<operation>-<nonce>.pending.json` mode `0600` there and waits up to ten minutes for the corresponding `.intent.json`. In a separate approved operator terminal, inspect and sign the exact pending bytes with the external release-operator key and namespace `revenue-partner-operation`, then atomically create the final mode-`0600` JSON record as `{"statement": <pending object>, "signature_path": "/absolute/path/to/signature"}`. The signed statement binds operation, nonce, method, exact URL, body digest, publication/build identities where applicable, exact tree, and both product digests. The broker verifies both exact-tree reviews and the operation signature against the root-owned policy, then atomically consumes the nonce before reading `ORGO_API_KEY`; resetting a Python capability or mutating a receipt cannot authorize or replay network access. The release-operator private key never enters the repository or publication process.

## 4. Launch a smoke computer

Replace `'WORKSPACE_ID'` with the literal non-secret workspace ID and use `--build --launch 'WORKSPACE_ID'` in the single command above. A standalone `--launch` is intentionally rejected because a mutable namespace/name/version reference cannot prove which remote bytes will launch. `safe-env-bridge.py` executes argv directly and does not invoke a shell, so pass the non-secret workspace ID as a literal argument rather than expecting `$ORGO_WORKSPACE_ID` expansion after the bridge starts. A successful launch writes `revenue-partner-agent.launch.json`. It may contain environment-specific identifiers and must not be committed.

## 5. Live smoke checklist

Treat each gate separately:

### Infrastructure

- computer status reaches `running`;
- returned CPU/RAM match the request;
- live endpoint/desktop access is available;
- supervisor-managed services are healthy.

### Runtime

- `hermes` exists and starts;
- Revenue Partner SOUL and skill are installed;
- knowledge vault exists;
- safe environment bridge is mode `0600` where written;
- no credential value exists in golden-image files.
- AgentPhone local attachments are accepted only from its operator-owned generated-media root; traversal, arbitrary absolute paths, and symlinks are rejected.

### Super Browser

- package imports;
- eight adapters enumerate;
- bundle manifest has zero missing required paths;
- MCP initialize/tools/resources calls succeed;
- Playwright Chromium launches;
- a read-only request stays read-only;
- a production ad/campaign request stops at `awaiting_approval` with zero provider execution.

### Conversational behavior

Ask the live agent to:

1. distinguish direct source claims, implementation inference, and unknown customer facts;
2. refuse to invent pricing, case studies, consent, or performance;
3. preserve **Book a Fit Call** as the CTA;
4. label `2–4 booked meetings/day` as a target, not a guarantee;
5. separate booked, attended, qualified, opportunity, pipeline, and closed revenue;
6. draft locally without sending;
7. require approval for launch, send, publish, CRM mutation, consent changes, or spend.

## Current 1.0.1 deployment evidence

- Local schema validation: passed.
- Authenticated remote validation: not evidenced for this exact tree; source/clean-export matrices establish local schema acceptance only.
- Resolved-artifact size and checksum are recorded against the exact GitHub release candidate rather than copied from an earlier build.
- Template publication/build: not completed; the authenticated workspace returned `403 UPGRADE_REQUIRED` because template publishing requires Scale or higher.
- Computer launch/live smoke: not completed because no published template exists.

This repository does not claim a live [Orgo](https://orgo.ai?r=aiguy) deployment until publication, build, launch, and live smoke all pass.

## Troubleshooting

### `403 UPGRADE_REQUIRED`

The credential is valid but the account lacks template-publishing entitlement. Upgrade the [Orgo](https://orgo.ai?r=aiguy) workspace to the required tier, then rerun `--build` without changing repository bytes.

### `409` on publication

The immutable version already exists. Do not reuse unknown remote bytes. Change the source-controlled `VERSION` constant to a new semver, then repeat the complete freeze, matrix, review, publication, and readback ratchet.

### Local validation unavailable

Install/run through the isolated command above. The builder must not publish based on an unavailable local validator unless authenticated remote validation succeeds.

### Build never reaches ready

Preserve the event stream. Treat timeout, failed phase, or error event as a failed release. Do not launch from a failed or ambiguous build.
