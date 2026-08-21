---
applyTo: "tests/**/*.py"
---

# Test design

- Test observable behavior and security invariants, not implementation call order. Use fixed UUIDs,
  UTC timestamps, deterministic clocks/randomness, and local fakes; no live cloud or public network.
- Every feature covers success, malformed/boundary input, authorization denial, dependency failure,
  cancellation/cleanup, and idempotent retry where applicable.
- For AI flows, assert structured decisions, tool calls, budgets, scope filters, audit events, and
  safe degradation. Do not assert brittle natural-language model prose.
- Unit tests remain fast and isolated. Integration tests own SQLAlchemy mappings, migrations,
  transaction semantics, outbox/reconciliation, and external-adapter contracts using disposable
  substitutes.
- A regression test must fail for the original defect. Do not lower coverage, broaden ignores, add
  sleeps, or weaken assertions to make a test pass.

