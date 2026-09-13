# Self-install and optional connections

The supported setup walkthrough is [Guided Orgo self-install](../onboarding/GUIDE.md). Give the setup AI the repository link; it does the technical work and leads the owner through sign-in, consent and billing choices. Every optional service has Connect now, Learn more and Skip.

Use `./orgo-onboard resume` to finish a partially completed installation and `./orgo-onboard status` to see verified, skipped and unfinished steps. A saved API key is not a successful live test.

This release is a candidate until the live Revenue Partner Orgo canary and both architecture acceptance checks are recorded. Repository tests do not authorize automatic production rollout.

The CI workflow verifies the supported native Orgo path, and Shared onboarding tests the module against the pinned Hermes source and container image. The former custom-template publishing matrix remains available through the manual Legacy custom-template verification workflow. It targets the retired custom image and its older dependency graph; it is not a live readiness test for this installer.
