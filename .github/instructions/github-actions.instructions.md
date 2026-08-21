---
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Actions

- Declare least-privilege `permissions`, job timeouts, and concurrency. Default to `contents: read`.
- Pin every external action to a reviewed full 40-character commit SHA and retain a version comment.
  Set checkout `persist-credentials: false` unless a reviewed step must push.
- Never interpolate untrusted PR/issue fields directly into `run` scripts. Pass values through an
  environment variable and validate them. Do not use `pull_request_target` with untrusted checkout.
- Keep secrets out of command lines, logs, artifacts, caches, and forked-PR jobs. Use environments
  with approval for deployments and OIDC rather than long-lived cloud credentials.
- Lock dependencies, set explicit tool/runtime versions, bound artifact retention, and make scheduled
  scans reproducible. Dependabot owns action SHA updates; review release notes before merging.
- Optional licensed features must be feature-gated and documented so an unavailable GitHub feature
  cannot break baseline CI.
