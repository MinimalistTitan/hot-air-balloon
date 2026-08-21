---
applyTo: "migrations/**/*.py"
---

# Alembic migration safety

- Never edit an applied migration. Add a new, uniquely identified revision with one correct
  `down_revision`; verify the repository still has a single expected head.
- Prefer expand/migrate/contract changes. Add nullable columns or safe defaults first, backfill in
  bounded resumable batches, deploy compatible code, then enforce constraints in a later revision.
- Avoid table rewrites, long locks, unbounded data updates, destructive type changes, and irreversible
  drops in a single deployment. Document lock, duration, disk, rollback, and mixed-version risks.
- Use deterministic SQL and explicit names for constraints/indexes. Make data transformations
  idempotent where retry is possible. Never embed production identifiers or secrets.
- Test upgrade from the prior schema and `upgrade head` on a disposable database. If downgrade cannot
  safely restore data, say so and provide a tested roll-forward recovery plan.
- Keep ORM/schema changes, retention behavior, audit lineage, and migration changes in the same PR.
  Use the `database-migration-review` skill before completion.

