---
name: database-migration-review
description: Design or review Alembic and persistence changes for safe rollout, compatibility, data integrity, retention, rollback, and operational risk.
license: Same terms as this repository.
---

# Database migration review

1. Inspect all migration heads, the previous migration, affected ORM models, repositories, settings,
   retention/deletion jobs, and integration tests.
2. Classify the change as additive, backfill, constraint/index, rename/type change, or destructive.
3. Produce an expand/migrate/contract sequence for any change that is not safely additive. Explain
   mixed-version behavior while old and new application instances overlap.
4. Estimate lock and rewrite risk, row volume sensitivity, transaction size, disk/index growth, and
   timeout. Backfills must be bounded, resumable, observable, and safe to retry.
5. Protect audit and privacy semantics: source lineage, ownership/site scope, expiry, soft/hard delete,
   vector reconciliation, and erasure must remain consistent.
6. Verify one expected Alembic head and test on a disposable database:

   ```text
   uv run alembic heads
   uv run alembic upgrade head
   uv run pytest tests/integration
   ```

7. Report deployment order, prechecks, success signals, rollback or roll-forward procedure, backup
   requirements, and the point after which rollback would lose data.

Never edit an applied revision or claim a destructive downgrade is safe when it cannot reconstruct
data.
