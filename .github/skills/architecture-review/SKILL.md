---
name: architecture-review
description: Review structural changes to modules, ports, adapters, wiring, contracts, workers, or cross-module imports. Use before accepting a change that could alter dependency direction or system boundaries.
license: Same terms as this repository.
---

# Architecture review

Use this skill for a new module, provider, repository, worker, API boundary, cross-module call, or
meaningful refactor.

1. Read `.github/copilot-instructions.md`, `.github/governance/architecture-policy.json`, the affected
   module `wiring.py`, application ports, domain types, presentation entry points, and tests.
2. Draw the before/after dependency direction in a few lines. Identify the source of truth, transaction
   boundary, authorization boundary, side effects, failure containment, and ownership of lifecycle.
3. Reject proposals where domain imports framework/I/O code, application constructs adapters,
   routers hold business policy, modules reach into another module's infrastructure/presentation, or
   an LLM/provider becomes a policy authority.
4. Prefer a narrow port and composition-root binding. Version public contracts and keep old and new
   versions interoperable during rollout.
5. For workers/providers, verify bounded work, idempotency, timeout, retry/backoff, cancellation,
   telemetry, poison-item handling, and shutdown order.
6. Run:

   ```text
   uv run python .github/scripts/architecture_guard.py
   uv run mypy src tests
   uv run pytest
   ```

7. Report: decision (`approve`, `approve with follow-up`, or `block`), violated/strengthened
   invariants, evidence by file, migration/compatibility impact, rollback path, and residual risks.

Do not add an allowlisted edge or baseline violation merely to make the guard pass. If an exception is
unavoidable, document its owner, expiry/removal condition, and why a composition-root solution is not
possible.
