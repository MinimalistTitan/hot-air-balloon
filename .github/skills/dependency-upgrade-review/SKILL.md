---
name: dependency-upgrade-review
description: Review Python, Docker, GitHub Actions, AI model/provider, and infrastructure dependency upgrades using current official advisories and release notes.
license: Same terms as this repository.
---

# Dependency upgrade review

Use this skill for Dependabot PRs, lockfile changes, base images, actions, SDKs, models, or provider API
versions.

1. Identify direct/transitive changes from the manifest and lockfile. Never infer a lockfile change
   from a version range alone.
2. Verify the latest stable version, release date, supported runtime, breaking/deprecation notes, and
   security advisories from the maintainer's official documentation/repository. Include direct links
   and an `as of YYYY-MM-DD` date; do not rely on snippets or unsourced summaries.
3. Evaluate API/schema behavior, Python 3.14 support, async/cancellation behavior, data migrations,
   serialization, telemetry, privacy terms, pricing/rate limits, and rollback compatibility.
4. For AI/model changes, run a representative evaluation set covering correctness, citations,
   permission denial, prompt injection, tool selection, latency, token/cost budgets, and provider
   failure. Keep the previous provider/model selectable until the rollout is proven.
5. For GitHub Actions, inspect the diff between pinned SHAs, retain full-SHA pins, and verify runtime
   requirements. For images, prefer immutable digests and review upstream CVEs.
6. Run relevant tests plus `uv run pip-audit`; regenerate the lock only with the repository's pinned
   `uv` workflow.

Output a decision, changed surface, security impact, compatibility risk, evidence, validation results,
rollout/rollback plan, and any follow-up with an owner and deadline. Separate a security patch from
unrelated major upgrades when possible.
