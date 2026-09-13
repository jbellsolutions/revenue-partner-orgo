# Revenue Partner Agent Documentation

This directory documents the public operating, security, deployment, evidence, and verification contracts for `revenue-partner-agent`.

## Start here

| Document | Purpose |
|---|---|
| [Beginner installation](../START-HERE.md) | Launch Revenue Partner on an [Orgo](https://orgo.ai?r=aiguy) computer and connect the selected channels and tools |
| [Setup-agent brief](../AGENTS.md) | Complete AI handoff, deployment contract, security rules, and finish line |
| [Machine-readable handoff](../llms.txt) | Concise agent summary, documentation map, and primary source links |
| [Orgo setup](ORGO-SETUP.md) | Natural-language [Orgo](https://orgo.ai?r=aiguy) deployment and completion checklist |
| [Orgo reference](ORGO-REFERENCE.md) | Applied [Orgo](https://orgo.ai?r=aiguy) `llms.txt`, API operations, templates, and sizing notes |
| [Slack setup](SLACK-SETUP.md) | Create the Slack Agent-view app, tokens, allowlists, channels, and tests |
| [Skills](SKILLS.md) | Included skills, Skills Hub, approvals, audits, and updates |
| [Tools](TOOLS.md) | Full Hermes toolset plus guided Calendar, inbox, app, and PandaDoc connections |
| [Updates](UPDATES.md) | Current image pin, reviewed features, and update procedure |
| [Architecture](ARCHITECTURE.md) | Components, trust boundaries, runtime flow, and extension points |
| [Operator guide](OPERATOR_GUIDE.md) | Configure the offer, assess fit, run the Money Desk, approve campaigns, and report results |
| [Deployment](DEPLOYMENT.md) | Validate, publish, build, launch, and smoke-test the [Orgo](https://orgo.ai?r=aiguy) template |
| [Security model](SECURITY_MODEL.md) | Secrets, approval controls, provider boundaries, bridge restrictions, and failure modes |
| [Supply chain](SUPPLY_CHAIN.md) | Python locks, checksum-verified artifacts, regeneration, and platform trust limits |
| [Source grounding](SOURCE_GROUNDING.md) | Authoritative sources, claim classes, evidence limits, and prohibited inferences |
| [Verification](VERIFICATION.md) | Reproducible test matrix, reviewed artifact identity, and current release status |

Repository-level documents:

- [`README.md`](../README.md) — product overview and quick start.
- [`SECURITY.md`](../SECURITY.md) — vulnerability reporting and supported release policy.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — development and review workflow.
- [`CHANGELOG.md`](../CHANGELOG.md) — release history.
- [`slack-manifest.json`](../slack-manifest.json) — current ready-to-paste Slack Agent-view manifest.
- [`LICENSE`](../LICENSE) — MIT license and upstream attribution.

## Canonical implementation contracts

Public summaries in `docs/` do not replace the executable contracts:

- Persona and operating rules: [`files/SOUL.md`](../files/SOUL.md)
- Revenue Partner skill: [`files/skills/go-to-market/revenue-partner/SKILL.md`](../files/skills/go-to-market/revenue-partner/SKILL.md)
- Campaign approval contract: [`campaign-contract.md`](../files/skills/go-to-market/revenue-partner/references/campaign-contract.md)
- Source ledger: [`source-ledger.md`](../files/skills/go-to-market/revenue-partner/references/source-ledger.md)
- Acceptance tests: [`acceptance-tests.md`](../files/skills/go-to-market/revenue-partner/references/acceptance-tests.md)
- Template builder: [`build_template.py`](../build_template.py)
- Release tests: [`tests/`](../tests)

If documentation and executable behavior disagree, treat the tests and current implementation as the release boundary, then open an issue to correct the documentation.
