# Verification and Release Evidence

## Evidence policy

A local green suite, an authenticated schema response, a published template, a ready image, a launched computer, and a live conversational smoke are separate gates. This project does not collapse them into “deployed.”

## Release identity

- Template: `default/revenue-partner-agent@1.0.1`
- Intended canonical source identity after publication: GitHub tag `v1.0.1`
- Exact commit/tree, resolved-artifact size/checksum, credential scan, and final independent-review verdict must be read back from GitHub release notes before publication is claimed
- Runtime target: Linux x86_64 / Python 3.11

Older candidate hashes and artifact sizes are intentionally not presented as current release evidence. Any runtime, payload, documentation, or CI edit requires affected tests and a new exact-candidate review before the release tag moves.

## Verification matrix

| Gate | Result | Evidence boundary |
|---|---|---|
| Focused campaign approval regression | Passed | Production/draft-smuggling variants stop at `awaiting_approval`; provider sentinel not reached |
| Revenue Partner test suite | 93/93 passed | Current Orgo Startup profile, beginner setup, A2A, builder, behavior, exact Git-index credential scan, exact serialized publication-body evidence, payload, safe env, locked bootstrap, provider hard stops, approval boundaries, telemetry, shell syntax, and immutable dependency evidence; real Chromium fixture execution remains an image-build live-smoke gate, and live browser/channel checks remain separate deployment gates |
| Latitude telemetry suite | 7/7 passed | Reasoning metadata, canonical fixed ingest origin, environment override rejection, no-proxy/no-redirect transport, and thread-safe repeat registration |
| Serialized publication request | Passed below endpoint ceiling | Canonical publish serializer enforces `< 1,000,000` bytes on the default CI builder path; exact post-freeze bytes belong in the release manifest |
| Deterministic payload inventory | 33 files; passed | Dropped from 109 to 33 files when the vendored Super Browser left the image. Generated `build/`, `dist/`, `node_modules/`, cache, and `*.egg-info` paths excluded; model-callable Orgo Desktop plugin/client paths are absent |
| AgentPhone ordering/media/webhook boundary | 17/17 passed | Immutable network/tunnel/main hard stops plus event ordering, direct-audience binding, signed group-webhook rejection before job creation, retained exact-origin/no-redirect defense-in-depth, approved-root, arbitrary-path, traversal, symlink, private-cache, arbitrary remote attachment rejection, and pre-read webhook-size controls |

| Python compilation | Passed | Builder, tests, bridges, packaged source |
| Super Browser runtime registration | Passed twice | Atomic standard-library `.pth`/`.dist-info` plus verified console entry point; no build backend or resolver |
| Shell syntax | 24 passed | Count derived from every tracked shell program plus assembled template hooks by `.github/scripts/check_shell_syntax.py` |
| Markdown/HTML local links and assets | 98 resolved | Count derived by `.github/scripts/check_markdown_links.py`; Markdown links/images plus HTML `src`/`href` references |
| Exact candidate export | Passed | Non-Python launcher rejects tracked/index differences and non-ignored untracked files, captures `git write-tree`, verifies archive parity, and runs all tests/builds inside that export |
| Local JSON Schema | Passed | Disposable environment populated from `requirements-ci.lock` under `--require-hashes` |
| Authenticated Orgo validation | Passed for this exact tree | `POST /api/templates/validate` returned HTTP `200` with `ok: true`, `api_version: orgo.ai/v1`, the echoed `revenue-partner-agent@1.0.1` identity, and the bound 22-entry file inventory. Exact bytes below. Schema acceptance only — not publication, image readiness, launch, or live runtime |
| Resolved body | Recorded in release notes | Exact final candidate output |
| Exact staged credential scan | 0 matches | Actual supplied values and credential-shape patterns |
| Independent security/correctness review | Recorded in release notes | Exact immutable release candidate |
| Orgo template publication | Blocked by account tier | `403 UPGRADE_REQUIRED`; no publication reference/digest. Publishing requires an Orgo **Scale** plan; the authenticated workspace is `hacker_v2`. Independently confirmed read-side: `GET /api/templates` returns `{"templates":[]}` and `GET /api/templates/default/revenue-partner-agent/1.0.1` returns `404 not found` |
| Image build | Not run | Publication did not occur. The install program itself was executed on a provisioned computer; see provisioned-runtime evidence, which is a separate and weaker gate |
| Computer launch | Not run | No published template |
| Live smoke | Not run | No live computer |

## Authenticated validation evidence (1.0.1)

Recorded from a direct authenticated call to the documented side-effect-free validation endpoint.
The transport was the exact assembled bytes, not a paraphrase.

| Field | Value |
|---|---|
| Exact Git tree | `e1cba9051ea09b74635ce5d8ce09aa5c388034b2` |
| Resolved artifact SHA-256 | `ec5953b59e7bbd7423f2db6d72ed9abe11e5114388777f88ee8a9d1a6012498e` |
| Validation body SHA-256 | `dfebb8007ab9fcc2ca6271fdf272bd967eef2663c236a4176498380b440aa077` (314,356 bytes) |
| Publication body SHA-256 | `39d6178fe8ee59120845c096890d255f9e5125c2bdd1f37608a785fd19e05ef5` (314,440 bytes) |
| Endpoint | `POST https://www.orgo.ai/api/templates/validate` |
| Status | `200` |
| Response | `ok: true`; `api_version: orgo.ai/v1`; `revenue-partner-agent@1.0.1`; 22-entry file inventory echoed |

The artifact was regenerated from the exact Git index immediately after the call and compared
byte-for-byte against the transmitted bytes; the digests are identical, so the `200` binds this tree
rather than a stale build output.

Scope boundary, stated explicitly so this gate is not read as more than it is: **schema acceptance
only.** It is not publication, not a digest, not image readiness, not a launch, and not live runtime
proof. Publication remains blocked by account tier, and the account holds no published template.

## Provisioned-runtime evidence (1.0.1)

The build-time install script and boot hooks were executed directly on a provisioned
Linux x86_64 computer by staging the assembled `files[]` inventory and payload to their
declared paths, then running `apps[].install`. This is **not** an Orgo template image
build: no template was published, no image was built, and no golden snapshot exists. It
is a separate, weaker gate that exercises the same install program the image build would
run, and it is recorded separately for exactly that reason.

| Step | Result |
|---|---|
| Deterministic payload + 23-file inventory staged to declared paths and modes | Passed |
| Node, 1Password CLI, Obsidian, and all three Playwright archives | `sha256sum -c` passed for every pinned artifact |
| Hermes runtime prune and CLI detach | `hermes_runtime_pruned 7`, `hermes_cli_detached 2` |
| Hermes entrypoint | `Hermes Agent v0.18.0 (2026.7.1)` on Python 3.12.3 — note this differs from the stated Python 3.11 runtime target; the locked runtime resolved `cp312` wheels cleanly, but the image-build target remains 3.11 and is not evidenced by this run |
| Super Browser runtime | `super_browser_import_ok 8 26` — eight providers, 26 resources |
| Playwright runtime | `playwright_runtime_ok` — real Chromium launched headless |
| Latitude telemetry registration | `latitude-telemetry-hermes 0.1.0+revenuepartner.1` |
| Install completion | `revenue-partner-agent install complete` |
| Supervised services | `hermes-gateway` and `agentphone-bridge` both `RUNNING` |
| Allowlisted environment bridge | `bridged 10 allowlisted environment values` |
| Model sign-in | Completed headlessly — OpenRouter via `hermes auth add openrouter --type api-key`; no device-code OAuth needed. Default model moved to `anthropic/claude-sonnet-5` |
| Telegram pairing | Not completed — QR pairing is operator-interactive |
| Conversational smoke | Passed — the agent answers correctly through OpenRouter (`anthropic/claude-sonnet-5`), naming all six outcome metrics separately and refusing to fabricate tool output |
| **Runtime reproducibility after this run** | **Broken — read this before trusting the rows above.** The provisioned box was manually corrected post-install: `mcp` was pinned back to `1.26.0` with a direct `pip install`, outside `--require-hashes` and not derivable from any lock in this tree. Rebuilding from this tree installs `mcp 2.0.0` (see the runtime-lock conflict below) and every HTTP MCP connection fails. The live box therefore does **not** match what `build_template.py` produces, and will not until the packaged Super Browser is retired in favour of the hosted MCP server. |

### Runtime-lock conflict (open)

`apps[].install` installs `build-locks/hermes-runtime.lock` and then the packaged Super Browser's
`requirements-runtime.lock` into the **same interpreter**. Both are hash-locked and deterministic in
isolation; installed sequentially, the second silently upgrades six shared pins, and Super Browser
installs last:

| Package | hermes-runtime.lock | super-browser lock | effective |
|---|---|---|---|
| `cryptography` | 46.0.7 | 50.0.0 | 50.0.0 |
| `idna` | 3.19 | 3.18 | 3.18 |
| **`mcp`** | **1.26.0** | **2.0.0** | **2.0.0** |
| `python-multipart` | 0.0.27 | 0.0.32 | 0.0.32 |
| `starlette` | 1.0.1 | 1.6.0 | 1.6.0 |
| `uvicorn` | 0.41.0 | 0.52.3 | 0.52.3 |

`hermes-agent 0.18.0` pins `mcp==1.26.0` exactly. Against `mcp 2.0.0` the HTTP MCP transport fails
three ways — the removed `streamablehttp_client` alias latches the availability flag to `False`;
`streamable_http_client` yields two values where the client unpacks three; and `CallToolResult`
exposes `is_error`, not `isError`. With `mcp==1.26.0` restored, **stock unpatched Hermes connects to
the hosted Super Browser in 267 ms and discovers all 22 tools.**

**Resolved** by retiring the packaged Super Browser: the install program now consumes exactly one
runtime lock. `RuntimeLockConsistencyTests` enforces that, and the assembled-artifact gate
(`verify_assembled_super_browser.py`) rejects any payload that reintroduces a second lock.

Two defects were found by this gate that every prior gate passed over, because no gate in
this repository had ever executed the install program:

1. The runtime pruner removed `hermes_cli/subcommands/slack.py` while `hermes_cli/main.py`
   still imported and registered it at module scope, so every `hermes` invocation died on
   `ModuleNotFoundError` and the install aborted under `set -e`.
2. All three pinned Playwright digests were wrong and had never been computed from a real
   download, so `sha256sum -c` failed closed on the first archive. Additionally the
   telemetry patch defaulted to a core-loop path that omitted the venv `site-packages`
   segment and could never resolve.

Both are fixed and re-verified; see the changelog for exact digests and provenance.

## Reproduce locally

```bash
REVENUE_PARTNER_VERIFY_PYTHON=/absolute/path/to/trusted/python3.11 bash .github/scripts/verify_release
```

Hosted CI invokes the same launcher with the trusted absolute interpreter supplied by the pinned `setup-python` action. The shell launcher clears Python/pip/proxy/certificate startup contamination, invokes Python with `-I -s -E`, exports one exact Git-index tree, and refuses mutable/untracked source. Inside that export, the verifier consumes `requirements-ci.lock` under `--require-hashes`, parses every exact-index YAML document, runs the Revenue Partner, Latitude, AgentPhone, and packaged Super Browser suites, and owns links/assets, compilation, tracked/embedded shell, exact-tree parity, schema assembly, and assembled-payload verification.

## Critical approval regression

`tests/test_revenue_partner_template.py::RevenuePartnerTemplateTests::test_super_browser_ad_campaign_phrases_require_approval`

The test uses `execute=True` and replaces provider execution with a sentinel that raises if reached. It covers:

- articles, possessives, modifiers, plurality, and punctuation;
- create/run/launch/start/activate/enable/resume/schedule/deploy/promote synonyms;
- advert/adverts/advertisement/advertising/campaign forms;
- production actions before and after draft terms;
- pronoun follow-ups;
- mixed research/report/local-output plus activation;
- unknown activation language;
- strict bounded read-only/public-search negatives.

## Super Browser provenance

The vendored package records its upstream base revision in `UPSTREAM_COMMIT`. Local Revenue Partner approval hardening is explicitly documented in `LOCAL_PATCHES.md`; modified policy bytes are not described as byte-identical to upstream.

The retained focused upstream test evidence is limited. This repository does not claim the entire upstream Super Browser suite passed.

## Publication status language

Allowed:

- “GitHub source published and CI verified” after remote readback and CI pass.
- “Orgo schema validated” after authenticated `200`.
- “Orgo template published” only after the response binds the exact `namespace/name@version` reference, a server digest matching the signed publication bytes, and a published timestamp, validated from a bounded response.
- “Image ready” only after immutable-reference remote readback matches the signed reference/digest, the build response binds the same reference/digest with a `building` or `ready` status, and a second-readback-gated bounded event stream for that exact reference reaches explicit success/ready before the absolute deadline.
- “Live deployment proven” only after another immutable-reference remote readback matches the signed bytes, launch submits that reference, and a matching computer ID, workspace ID, runtime, and conversational smoke tests pass.

Current 1.0.1 status is **implemented, locally verified, authenticated-schema-validated for the exact tree `e1cba905`, and install-verified on a provisioned computer whose runtime was then manually corrected and is not reproducible from this tree; exact GitHub publication/review evidence is release-bound; not yet published, image-built, or live on Orgo**.
