---
applyTo: "**/*.py"
---

- Target Python 3.14 and use `uv`; do not add compatibility shims for older Python versions.
- Give every function, method, callback, and return value an explicit type. Fully parameterize
  generics and `Callable`. Avoid `Any`; isolate and justify unavoidable untyped SDK boundaries.
- Prefer protocols at application boundaries, immutable dataclasses/value objects, dependency
  injection, exhaustive `match`, early validation, and explicit domain errors.
- Async code must not perform blocking I/O. Bound concurrency, retries, collection size, and time.
  Propagate cancellation and make cleanup deterministic.
- Catch only errors that can be handled. Preserve causal chains with `raise ... from error`; never
  silently convert authorization, integrity, cancellation, or programming errors into success.
- Use timezone-aware UTC datetimes. Never use mutable default arguments or global mutable state.
- Use parameterized SQL/SQLAlchemy expressions. Secrets use `SecretStr` and never appear in logs,
  exception text, fixtures, snapshots, or telemetry.
- New behavior requires tests for the success path, boundary values, denied/failed paths, and async
  cleanup where relevant. Tests must be deterministic and must not require public network access.
- Code must pass Ruff format/lint, strict mypy, pytest with branch coverage, and relevant governance
  guards. Do not suppress a rule without a narrow scope and a written reason.
