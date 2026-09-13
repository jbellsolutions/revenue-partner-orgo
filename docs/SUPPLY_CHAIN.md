# Supply-Chain Reproducibility

## Scope

Revenue Partner Agent pins and verifies application-level build dependencies. The deterministic source payload, Python locks, committed [Orgo](https://orgo.ai?r=aiguy) schema, and downloaded release artifacts are reproducible inputs. The [Orgo](https://orgo.ai?r=aiguy) base image and apt repository snapshot are platform inputs and are not claimed to be content-addressed by this repository.

## Source-bound [Orgo](https://orgo.ai?r=aiguy) schema

- `template-schema.json` is the vendored [Orgo](https://orgo.ai?r=aiguy) `orgo.ai/v1` template schema used by the canonical local matrix.
- `build_template.py` requires SHA-256 `619fbd1becd060a4c5c0de28c325f8e96b4f6cb456ef6c8f8cacdb0789932dd7` before parsing it.
- Neither `ORGO_API_BASE` nor another caller-controlled endpoint can select the schema or authenticated [Orgo](https://orgo.ai?r=aiguy) authority used by release commands. Authenticated `--remote-validate` is a separate current-service compatibility gate and never substitutes for the committed schema gate.

## Locked Python environments

### Hermes runtime

`files/build-locks/hermes-runtime.lock` is generated for Linux x86_64 and Python 3.11. It locks the complete transitive graph with SHA-256 hashes, including:

- `hermes-agent[all]==0.18.0`
- `uv==0.12.4`
- `qrcode[pil]==8.2`

The image creates `/usr/local/lib/hermes-agent/venv` using `python3 -m venv`, then installs with:

```bash
python -m pip install --require-hashes \
  -r /opt/revenue-partner/stage/build-locks/hermes-runtime.lock
```

No live Hermes installer is downloaded or executed.

Regenerate deliberately from the repository root:

```bash
uv pip compile \
  --python-version 3.11 \
  --python-platform x86_64-unknown-linux-gnu \
  --generate-hashes \
  --no-annotate --no-header \
  --output-file files/build-locks/hermes-runtime.lock \
  <(printf 'hermes-agent[all]==0.18.0\nqrcode[pil]==8.2\nuv==0.12.4\n')
```

Review the complete diff and bump the template version before accepting any regenerated lock.

The upstream Hermes wheel includes optional Spotify, Slack, Discord, and Linear catalog surfaces that are outside this release contract. Immediately after the hash-locked install—and before any Hermes command runs—the committed `files/scripts/prune_hermes_runtime.py` requires Hermes `0.18.0`, resolves package files through `distribution.files`/`distribution.locate_file`, resolves the wheel's `.data/data/optional-mcps/linear` relocation under `sys.prefix`, removes seven exact plugin/CLI/catalog paths, and fails the image build if the expected wheel layout drifts or any target survives. The canonical test downloads the actual 0.18.0 wheel, verifies its locked SHA-256, installs it without dependencies into an isolated venv, executes the real pruner, and proves all seven surfaces absent. The safe-environment bridge rejects those connector credentials even through explicit selection.

### Super Browser runtime

`files/local-packages/super-browser/requirements-runtime.lock` locks the complete Super Browser runtime graph with hashes. After that lock succeeds, `files/scripts/super-browser/install_local_super_browser.sh` registers the staged pure-Python source directly with atomically written `.pth` and `.dist-info` metadata and a verified console entry point. No pip project install, setuptools, wheel, PEP 517 backend, dependency resolution, build isolation, or network participates in local package registration. See [`RUNTIME_LOCK.md`](../files/local-packages/super-browser/RUNTIME_LOCK.md).

### Local telemetry fork

The staged `latitude-telemetry-hermes` fork is registered directly in the locked Hermes venv with atomically written `.pth` and `.dist-info` metadata using Python’s standard library. No package build backend, dependency resolver, network access, ambient `setuptools`, or `wheel` version participates. The installer verifies the exact distribution version, plugin entry point, and imported module, while the core-hook patch remains idempotent and fails closed if the expected Hermes source anchor drifts. Telemetry POSTs are pinned to the canonical `https://ingest.latitude.so` origin; environment overrides, redirects, and proxy inheritance are disabled. Hook registration is process-wide repeat-safe. The builder and regression suite both require the invoked registration script to exist in the payload.

## Node runtime boundary

The pinned Node.js artifact supports the desktop setup applications only. This release contains no npm package manifest, npm lock, model-callable filesystem MCP, or lifecycle-script installation surface. Named Hermes connector CLIs/plugins covered by this release are removed by the version-bound prune step above.

## Checksum-verified release artifacts

Exact URLs and SHA-256 values live as constants in `build_template.py`:

| Artifact | Pin |
|---|---|
| Node.js | v24.19.0 Linux x64 |
| 1Password CLI | v2.34.1 Linux amd64 |
| Obsidian | v1.12.7 amd64 `.deb` |
| Playwright Chromium | revision 1234 / Chrome for Testing 151.0.7922.34 Linux x64 |
| Playwright headless shell | revision 1234 / Chrome for Testing 151.0.7922.34 Linux x64 |
| Playwright FFmpeg | revision 1011 Linux x64 |

Every artifact is downloaded from a versioned URL and checked with `sha256sum -c` before extraction or execution. Do not use `releases/latest`, pipe installers into a shell, or add unchecked fallback downloads.

## Deterministic source payload

`build_template.py` creates one curated tarball with:

- lexicographically sorted entries;
- normalized uid/gid and modification times;
- explicit modes;
- only selected runtime roots;
- build and runtime lock files included before installation.

The publication envelope uses one canonical compact JSON serializer for both the HTTP request and the CI size check. The default builder fails closed unless those exact serialized bytes are below `1,000,000`. Exact byte counts and checksums are generated only after the source tree is frozen and belong in the release manifest rather than this recursively packaged document.

Generated resolved JSON, raw research captures, caches, and credentials are excluded from Git.

## Remaining platform inputs

The following are outside this repository's content-addressed guarantee:

- the [Orgo](https://orgo.ai?r=aiguy) base image selected by the template service;
- apt package versions provided by that image's configured repositories;
- availability of the versioned upstream artifact URLs.

A successful schema validation is not proof that those artifacts were downloaded or that the image booted. Image build and live smoke results must be reported separately.

## Verification gates

Before release:

1. run the complete test suite;
2. confirm no floating installer/download patterns exist in `build_template.py`;
3. parse both lockfiles;
4. verify all required checksum constants and `sha256sum -c` commands remain present;
5. assemble the resolved template under JSON Schema validation;
6. assert the canonical serialized publication envelope remains below `1,000,000` bytes;
7. run authenticated remote schema validation;
8. build an image and smoke-test only when the [Orgo](https://orgo.ai?r=aiguy) workspace tier permits it;
9. record exact Git commit/tree and live evidence independently.
