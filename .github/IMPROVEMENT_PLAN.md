# Sustainability and risk-reduction plan

Status: active  
Baseline date: 2026-08-21  
Review cadence: monthly and after every material incident, architecture change, or provider/model
change

This plan prioritizes controls that prevent irreversible data/security damage and architecture erosion
before convenience or scale work. Completion requires evidence, automation, an owner, and an ongoing
signal—not only a document or one-time review.

## P0 — protect the merge and data boundaries now

### 1. Enforce repository rules on the real default branch

Configure a GitHub ruleset for `main_library` (and `main` if it will remain) that blocks deletion and
force-push, requires pull requests, at least one non-author approval, dismissal of stale approvals,
resolved conversations, and passing `CI / verify`. Add code-owner review when ownership is known; do
not add placeholder owners. Restrict bypass to a small audited emergency group.

Evidence: exported ruleset or settings screenshot plus a test PR that cannot merge when CI fails.
This is high priority because the repository currently has a single commit and no repository-side file
can prove branch protection. OpenSSF rates branch protection and code review as high-value injection
controls. [OpenSSF checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md)

### 2. Enable platform security controls and the prepared workflow

Enable dependency graph, Dependabot alerts/security updates, private vulnerability reporting, secret
scanning with push protection, and CodeQL/Code Security when the plan/repository visibility supports
them. Then set `ENABLE_GITHUB_ADVANCED_SECURITY=true`, require dependency review for PRs, and confirm
SARIF reaches code scanning. Keep `pip-audit` as an independent scheduled control.

Evidence: a synthetic secret is blocked in a disposable branch, a vulnerable test dependency is
rejected, and a CodeQL test alert is visible and removed. GitHub documents both the capability limits
and dependency-review behavior. [Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)

### 3. Close current repository hygiene and credential-default risks

Stop tracking generated coverage/state artifacts, ignore Azurite data and local storage directories,
and remove realistic default passwords/connection strings from source and Compose. Use explicit local
bootstrap values that cannot be mistaken for production credentials. Search Git history and rotate any
value that has ever been real; deleting a file is not rotation.

Evidence: clean `git status` after local services/tests, secret scan of full history, documented local
bootstrap, and production startup tests that reject weak/local defaults.

### 4. Prove end-to-end authorization and AI data isolation

Add tests that forge user/site identifiers, attempt cross-user conversation and vector recall, inject
instructions through documents/web/tool output, replay tool calls, exceed call/token/rate budgets, and
exercise deletion/retention reconciliation. LLM output must never substitute for permission checks.

Evidence: adversarial integration suite, durable approved/rejected audit records, no sensitive payloads
in logs, and metrics for denial/budget/provider-failure paths. OWASP notes that RAG does not eliminate
prompt injection and that excessive agency can turn model errors into damaging actions.
[OWASP prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

## P1 — remove structural debt and make failure observable

### 5. Reduce the architecture baseline to zero

Replace the two application-to-infrastructure dependencies with application ports and move the shared
consistency-audit presenter mapping out of presentation. Delete each baseline entry as its dependency
is corrected. Add stable cross-module contracts for authorization/tool definitions instead of allowing
business modules to depend on another module's internal package.

Evidence: zero `allowed_violations`, a smaller explicit cross-module allowlist, passing architecture
guard, and contract tests. Target: no new debt immediately; existing four items removed before the
next major feature tranche.

### 6. Establish SLOs, budgets, and actionable alerts

Define availability, p95/p99 latency, error rate, tool denial/failure, queue/outbox age, retry/dead-letter,
context truncation, token/cost, vector lag, retention backlog, and erasure completion objectives.
Alerts must include a runbook, owner, severity, and burn-rate/sustained threshold to avoid noise.

Evidence: dashboards, alert tests, trace correlation from request to tool/provider/store, and a monthly
review of false positives, missed incidents, cost, and capacity.

### 7. Make workers and providers resilient by contract

Standardize bounded batches, timeout, jittered backoff, retry classification, idempotency keys,
circuit-breaking/load shedding, poison-item quarantine, cancellation, and reverse-order shutdown for
Kafka, blob, embedding, Pinecone, LLM, and retention/reconciliation work.

Evidence: deterministic fault-injection tests for partial writes, duplicates, provider timeouts,
shutdown mid-batch, stale vector state, and restart recovery.

### 8. Formalize privacy lifecycle and incident response

Create a data inventory and retention matrix for conversation turns, summaries, tool audit/trace,
documents/chunks, embeddings/vector metadata, logs, metrics, backups, and provider inputs. Define legal
purpose, minimization, access, residency, deletion SLA, backup deletion, and incident evidence handling.

Evidence: automated erasure/retention tests across Postgres/Pinecone/blob/backups, quarterly access
review, tabletop exercise, and verified security contact/response metrics. NIST SSDF supplies the
secure-development baseline. [NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final)

## P2 — strengthen the supply chain and safe delivery

### 9. Produce verifiable build provenance and an SBOM

Build an immutable non-root image, pin base images by digest with reviewed automated updates, generate
CycloneDX/SPDX SBOM, scan image and IaC, and create GitHub artifact attestations for releases. Promote
the same digest through environments; never rebuild per environment.

Evidence: verified attestation from a release, retained SBOM, vulnerability policy with remediation
SLA, and deployment record mapping environment to digest.
[GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)

### 10. Adopt staged, reversible deployment automation

Automate preflight configuration/migration checks, canary or blue-green rollout, health/SLO gates,
automatic halt/rollback, and post-deploy verification. Database changes follow expand/migrate/contract;
destructive cleanup waits beyond the rollback window.

Evidence: successful rollback game day, migration recovery rehearsal, and deployment lead-time/change-
failure metrics.

### 11. Add change evaluation for models, prompts, retrieval, and tools

Version evaluation datasets and acceptance thresholds for factual precision, citation validity,
authorization/refusal, tool selection/arguments, prompt injection, cross-scope leakage, latency,
unbounded consumption, and cost. Shadow/canary new models/providers and keep rollback configurable.

Evidence: machine-readable comparison attached to every relevant PR and a production drift signal.

## P3 — scale only from measured pressure

### 12. Capacity and ownership maturity

Define module owners, on-call/runbooks, dependency/service catalog, ADRs for material decisions, and
capacity models for database pools, Kafka partitions, blob throughput, Pinecone, provider rate limits,
and worker concurrency. Split the modular monolith only when ownership, scaling, deployment cadence, or
fault-isolation data justifies the distributed-system cost.

Evidence: quarterly capacity test, named owners/backups, stale-runbook check, ADR index, and a measured
threshold for any extraction proposal.

## Definition of a closed improvement

An item is closed only when its control is automated where practical, failure is visible, evidence is
linked, a maintainer owns it, the runbook/rollback is tested, and the scorecard or an operational metric
will detect regression. Accepted exceptions need an expiry date and must not weaken unrelated gates.
