# Governance and early-warning system

This directory turns repository expectations into evidence. It is designed to detect architectural
erosion, stale technical guidance, weakened quality/security controls, and supply-chain exposure
before those risks become routine technical debt.

## What runs

`uv run python .github/scripts/architecture_guard.py` parses Python imports and enforces the configured
module/layer direction. Four existing outward dependencies are baselined as named debt. A new
violation fails immediately; removing debt produces a reminder to delete its baseline entry.

`uv run python .github/scripts/governance_score.py --min-score 85` evaluates weighted, versioned metrics.
The score is out of 100, but a critical metric fails even when the aggregate is above 85. Each metric
contains its evidence rule and a primary reference. CI publishes the Markdown report in the job log
and GitHub step summary.

The weekly CI schedule reruns tests, the dependency vulnerability audit, architecture guard, score,
and migration validation. Dependabot watches Python/uv, containers, and Actions. The technology
watchlist expires after 45 days; this makes unreviewed "latest" claims a visible CI failure.

The optional `advanced-security.yml` is prepared with least-privilege permissions and immutable action
SHAs. Set repository variable `ENABLE_GITHUB_ADVANCED_SECURITY=true` only after Code Security/Advanced
Security, the dependency graph, and code scanning are available for this repository. Until then,
baseline CI remains functional and `pip-audit` supplies the dependency-advisory gate.

## Scoring model

| Category | Weight | What it protects |
| --- | ---: | --- |
| Architecture | 25 | Dependency direction, integration boundaries, migration and rollback discipline |
| Quality | 20 | Static checks, tests, branch coverage, deterministic AI/failure-path testing |
| Security and privacy | 30 | Workflow supply chain, dependency risk, vulnerability intake, AI/data controls |
| Automation and freshness | 15 | Default-branch coverage, scheduled detection, policy automation, source freshness |
| Maintainability | 10 | Copilot context, path rules, reusable review skills, evidence-oriented PRs |

This is a repository-control score, not a claim that the running system is 100% secure or reliable.
It cannot see GitHub rulesets, review behavior, organization identity controls, secret-scanning state,
cloud configuration, production SLOs, incident response performance, or runtime vulnerabilities.
Those are tracked in the improvement plan and should be assessed separately.

## Changing policy safely

1. Explain the threat, failure, or quality signal the metric addresses.
2. Use an objective repository-evidence evaluator and a current primary reference.
3. Keep total metric weight at exactly 100. Do not lower the minimum or remove `critical` to land an
   unrelated change.
4. Run both scripts locally and review the evidence, not just the final number.
5. Record material policy decisions in the PR risk assessment and update the improvement plan.

Architecture exceptions are stricter: prefer a port/contract and composition-root wiring. If an
exception is temporarily unavoidable, name the exact import, reason, owner, and measurable removal
condition. Baselines may never use broad globs.

## Evidence basis (verified 2026-08-21)

- GitHub supports repository-wide instructions, path-specific instructions, and `.github/skills`
  project skills. [GitHub Copilot customization](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- GitHub recommends explicit workflow permissions and full-SHA action pins to reduce workflow and
  supply-chain risk. [GitHub threat protection guidance](https://docs.github.com/en/code-security/tutorials/secure-your-organization/protect-against-threats)
- Dependency review can block vulnerable dependencies introduced by a PR, subject to repository
  feature availability. [GitHub dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review)
- OpenSSF Scorecard identifies branch protection, code review, dangerous workflows, pinned
  dependencies, SAST, dependency updates, and vulnerabilities as measurable supply-chain controls.
  [OpenSSF Scorecard checks](https://github.com/ossf/scorecard/blob/main/docs/checks.md)
- NIST SSDF v1.1 is the current final baseline; v1.2 is a draft being monitored.
  [NIST SSDF publications](https://csrc.nist.gov/projects/ssdf/publications)
- The OWASP 2025 LLM/GenAI list includes prompt injection, sensitive disclosure, excessive agency,
  vector/embedding weaknesses, and unbounded consumption—directly relevant to this service.
  [OWASP GenAI Top 10](https://genai.owasp.org/llm-top-10/)
