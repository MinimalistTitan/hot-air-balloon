## Outcome

<!-- State the user/system outcome, not a list of edited files. -->

## Evidence

<!-- Link the requirement/issue and show tests, measurements, or current primary-source citations. -->

## Risk assessment

- Architecture impact: <!-- boundaries/imports/contracts changed, or "none" with reason -->
- Security/privacy impact: <!-- data, authz, secrets, logs, AI/tool/RAG threat surface -->
- Compatibility/migration impact: <!-- API/event/schema/model/provider/deployment compatibility -->
- Operational impact: <!-- latency, cost, capacity, failure modes, observability -->
- Rollback: <!-- exact safe rollback or roll-forward procedure -->

## Validation

- [ ] Relevant success, boundary, denial, and failure-path tests added/updated
- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy src tests`
- [ ] `uv run pytest`
- [ ] `uv run pip-audit`
- [ ] `uv run python .github/scripts/architecture_guard.py`
- [ ] `uv run python .github/scripts/governance_score.py --min-score 85`
- [ ] Migration tested on a disposable database, or not applicable
- [ ] Logs/telemetry contain no secrets, prompt content, personal data, or document content
- [ ] Documentation/configuration and primary-source verification date updated where applicable

## Residual risk and follow-up

<!-- No hidden TODOs: give each accepted risk an owner, priority, and target date. -->
