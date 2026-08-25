# System Operational Test and Coverage Plan

Status: proposed execution plan  
Baseline date: 2026-08-24  
Scope: the complete `src/app` runtime, with extra depth for LangGraph orchestration,
context and memory management, and tool calling

## 1. Goal

Prove that the system works as an integrated ERP assistant, not merely that individual lines of
Python execute. The test program must answer four separate questions:

1. **Code coverage:** how much production code and branching logic executed?
2. **Functional coverage:** how many required system behaviors have passing automated tests?
3. **Role coverage:** is every production file assigned to a system capability and linked to tests?
4. **Operational coverage:** do startup, persistence, external boundaries, failure recovery,
   security, observability, and shutdown work in a production-like environment?

No single percentage answers all four questions. The release report must show all four.

## 2. Current measurable baseline

The baseline command was:

```powershell
uv run pytest --ignore=tests/unit/user/test_user_repository_roles.py --cov-report=term
```

The exclusion was necessary because the normal `uv run pytest` stops during collection:
`tests/unit/user/test_user_repository_roles.py` imports `tests.fixtures`, but that module is absent.

Current result:

| Measure | Baseline | Interpretation |
| --- | ---: | --- |
| Tests executed | 56 passed | Excludes the uncollectable user repository test module |
| Statement coverage | 2,377 / 3,128 = **75.99%** | Lines/statements executed |
| Branch coverage | 153 / 408 = **37.50%** | Decision outcomes executed |
| Coverage.py combined result | **71.55%** | Current configured branch-aware coverage result |
| Configured gate | **80%** | The suite currently fails this gate |
| Functional coverage | **Not yet validly measurable** | No approved capability/scenario denominator exists |

Coverage by major code area:

| Code area | Statement execution | Branch execution | Combined baseline |
| --- | ---: | ---: | ---: |
| App composition | 3 / 161 | 0 / 30 | **1.57%** |
| Assistant | 1,347 / 1,650 | 110 / 244 | **76.93%** |
| Core | 131 / 171 | 19 / 50 | **67.87%** |
| Documents | 106 / 124 | 7 / 20 | **78.47%** |
| Operations | 490 / 590 | 12 / 32 | **80.71%** |
| User | 300 / 432 | 5 / 32 | **65.73%** |

Focused assistant baselines:

| Assistant area | Statement execution | Branch execution | Combined baseline |
| --- | ---: | ---: | ---: |
| LangGraph orchestration | 162 / 191 | 7 / 16 | **81.64%** |
| Context assembly and budgeting | 138 / 142 | 14 / 18 | **95.00%** |
| Short-term memory | 113 / 157 | 10 / 26 | **67.21%** |
| Long-term memory and RAG | 343 / 458 | 35 / 86 | **69.49%** |
| Tool gateway and runtime | 280 / 303 | 20 / 36 | **88.50%** |
| Application composition (`container.py`, `main.py`, `__main__.py`) | 0 / 152 | 0 / 30 | **0.00%** |

These percentages are a snapshot of the current working tree and should be regenerated after the
test harness is repaired.

## 3. Code-role inventory

Every production file must belong to exactly one primary role in the capability manifest. A file may
support other roles, but one owner prevents files from disappearing between metrics.

| Role ID | Code area | System responsibility |
| --- | --- | --- |
| APP | `app/main.py`, `app/container.py`, `app/bootstrap`, lifecycle | App construction, dependency composition, resource start/rollback/stop, routing, errors, middleware |
| CFG | `app/core` | Settings validation, database/session creation, logging, metrics, shared SQLAlchemy behavior |
| USR | `app/modules/user` | User lifecycle, roles, sites, authorization context, consistency audit |
| DOC | `app/modules/documents` | Upload validation, blob persistence, outbox, extraction, chunking, ingestion state |
| OPS | `app/modules/operations` | Operational reads, work-order transitions, repositories, assistant tool definitions |
| ORCH | `assistant/infrastructure/agents/langgraph` | Graph nodes, routing, loop limits, checkpointer, final response |
| CTX | `assistant/application/context`, `assistant/domain/context` | Context providers, token accounting, allocation, deterministic render, failure isolation |
| STM | `assistant/infrastructure/conversation_memory/short_term` | Owner-scoped turns, conversation lineage, expiry, short-term retention |
| LTM | `assistant/infrastructure/conversation_memory/long_term` | Fact extraction/promotion, mirror store, embeddings, vectors, sync, reconciliation, retention, erasure |
| TOOL | `assistant/tool_gateway`, `tool_runtime`, tool adapters | Registration, schema validation, permission and site scope, approval, rate limiting, retries, audit and trace |
| API | module `presentation` packages and contracts | HTTP validation, authorization propagation, response contracts, status/error mapping |
| EXT | Azure Blob, Pinecone, OpenAI, Kafka adapters | Vendor request/response mapping, timeout/error translation, retry-safe behavior |

Create `tests/coverage/capabilities.yaml` during implementation with, at minimum:

```yaml
- id: ORCH-TOOL-LOOP
  role: ORCH
  priority: P0
  requirement: The graph can call an allowed tool and use its result in the final answer.
  source:
    - src/app/modules/assistant/infrastructure/agents/langgraph/orchestrator.py
    - src/app/modules/assistant/infrastructure/agents/langgraph/nodes/tool_call.py
  tests:
    - tests/component/assistant/test_agent_workflow.py::test_allowed_tool_result_reaches_answer
  required_level: component
  status: passing
```

The manifest must fail validation if a production `.py` file has no role, if a required test ID no
longer exists, or if a P0/P1 capability has no test.

## 4. Coverage calculations

### 4.1 Code coverage

Report statements and branches independently:

```text
statement_coverage = covered_statements / total_statements * 100
branch_coverage    = covered_branches / total_branches * 100
```

Do not use code coverage as the functional percentage. A test can execute a line without checking
that its behavior is correct.

### 4.2 Functional capability coverage

Each manifest scenario is binary: passing or not passing. Skipped, xfailed, flaky, manual-only, and
partially asserted scenarios do not count as passing.

```text
priority weights: P0 = 5, P1 = 3, P2 = 1

functional_coverage =
  sum(weight of passing scenarios) / sum(weight of all required scenarios) * 100
```

Also publish the unweighted `passing scenarios / required scenarios` count. Adding many low-risk
scenarios must not hide a missing authorization or data-isolation scenario.

### 4.3 Role coverage

```text
role_assignment_coverage = assigned production files / all production files * 100
role_test_link_coverage   = files linked to a passing scenario / all production files * 100
```

Role assignment must be 100%. Generated migration files and declarative model-only files may be
verified by migration/schema tests rather than one unit test per file, but they still need a role and
a test link.

### 4.4 Operational-path coverage

Track the following production paths as a checklist rather than lines:

- application startup, failed-start rollback, normal shutdown, and failed-stop aggregation;
- PostgreSQL migrations from empty database and from the last supported release;
- HTTP request through router, authorization, use case, persistence/tool call, and response;
- background worker start, one successful poll, transient failure, retry, cancellation, and stop;
- OpenAI/Pinecone/Blob/Kafka contract behavior without calling live services in the normal CI suite;
- telemetry and audit evidence for success and denial paths.

## 5. Test layers

### Layer 1 — Unit

Pure policies, state transitions, parsing, token allocation, authorization, scope filtering, retry
decisions, and mapping logic. These tests must be fast and must not require network or Docker.

### Layer 2 — Component

Assemble real collaborators around one capability with deterministic fakes only at external
boundaries. Examples: a complete LangGraph workflow with a scripted brain and real tool gateway; or
context assembly with real providers and an in-memory vector adapter.

### Layer 3 — Integration

Use real PostgreSQL and apply Alembic migrations. SQLite is useful for fast tests but cannot prove
PostgreSQL arrays, row locking, `SKIP LOCKED`, concurrent uniqueness, or checkpointer behavior.

### Layer 4 — API end-to-end

Run the FastAPI lifespan and send HTTP requests through middleware and routers. Override only vendor
boundaries. Assert status, response body, database changes, audit/trace rows, and conversation state.

### Layer 5 — Contract and smoke

Recorded or sandboxed provider contract tests verify OpenAI structured output, embeddings, Pinecone,
Azure Blob, and Kafka mappings. Live smoke tests are opt-in, credential-gated, and never part of a
developer's default unit run.

### Layer 6 — Non-functional

Measure assistant request p50/p95/p99 latency, concurrent conversation isolation, memory growth,
worker throughput, rate-limit behavior, and recovery after dependency timeouts. The documented p95
assistant target is under eight seconds.

## 6. Required scenario matrix

### 6.1 LangGraph agent orchestrator

- Direct answer with tools disabled.
- One allowed tool call, observed result, and grounded final answer.
- Multiple tool iterations up to the total-call budget.
- Per-tool budget enforcement.
- Unknown/disallowed tool request becomes `POLICY_BLOCKED` without invoking a handler.
- Zero and negative requested budgets become zero effective calls.
- Empty model answer becomes the documented fallback.
- Brain exception, tool exception, and malformed structured output map to a controlled failure.
- Same `conversation_id` uses the same checkpointer thread; different users/conversations do not
  share graph state.
- Interrupted/resumed execution works against the PostgreSQL checkpointer if resume is a supported
  capability.

The existing test proves only the single allowed-tool happy path. It does not prove the direct,
policy-blocked, exception, multi-call, or durable checkpoint paths.

### 6.2 Context and token management

- Recent turns, user memory, and permitted document recall all reach the exact model input.
- Assembled context is not merely stored in graph state; the planner and responder consume it.
- Stable rendering order for identical inputs.
- Empty context behavior.
- Exact budget boundary, oversized single block, zero/negative token count, and all blocks dropped.
- Per-kind shares, spill behavior, and documented drop priority.
- One provider failure degrades the request; cancellation still propagates.
- Token counts are measured once and the final prompt never exceeds the configured budget.
- Tool results are budgeted before a subsequent model call.

High-priority characterization test: the current orchestrator initializes `answer` with
`context.render()`, while the current `AgentBrain` prompts read `conversation_history` and tool calls.
A component test must assert the assembled context appears in the actual planner/responder input. This
test should detect any path where context is assembled but not consumed.

### 6.3 Short-term memory

- New conversation and user/assistant turns are recorded atomically enough for the documented
  failure semantics.
- Recent turns return in chronological order and are limited correctly.
- Owner A cannot read or append to owner B's conversation.
- Expiry timestamps and conversation counters are correct.
- Retention deletes only expired data, preserves live data, handles batch boundaries, retries after a
  transient database failure, and stops promptly.
- Concurrent appends preserve all turns and valid counters.
- In-memory adapter follows the same behavioral contract as PostgreSQL.

### 6.4 Long-term memory and RAG

- Fact extraction accepts valid structured output and rejects malformed output.
- Every accepted fact cites valid source turns.
- Volatile, authorization-derived, tool-rederivable, oversized, and disallowed facts are rejected.
- Normalized duplicate facts merge lineage; concurrent duplicate promotion creates one active record.
- Vector sync covers success, embedding failure, upsert failure, retry metadata, retry success, and
  batch boundaries.
- Reconciliation deletes only orphans and tolerates one namespace failure according to policy.
- Retention covers unsynced, already-deleted, vector-delete-failed, and hard-delete retry states.
- User erasure removes owner records and lineage-derived records while preserving other users.
- Document recall embeds the query, filters candidates, rechecks permission/site scope in SQL,
  preserves vector ranking, and excludes deleted/unsynced records.
- User A memory and vectors are never recalled for user B.

### 6.5 Tool calling

- Registry rejects duplicate names and unknown lookup is controlled.
- Strict input rejects missing, unknown, and wrong-type fields before authorization or handler calls.
- Permission and site checks deny before handler execution and create audit/trace evidence.
- Approval absent, rejected, and approved paths.
- Rate limit below limit, at boundary, exceeded, per-actor isolation, and window reset.
- Read tools and write tools use the correct permissions and site field.
- Handler success validates output schema and strips gateway-only fields correctly.
- Transient handler failure retries exactly `max_retries`; permanent failure does not emit a false
  success event.
- Conversation ID is present on every related audit and trace row.
- Sensitive values are not exposed in logs, audit reasons, or model-visible tool results.

### 6.6 Business modules and HTTP API

- User register/get, duplicate email, invalid input, role and site persistence, and consistency audit.
- Document upload size/type checks, blob failure, duplicate, outbox commit, ingestion success/failure,
  and PDF/DOCX/text extraction.
- Each operations read endpoint and read tool maps repository data correctly and enforces site scope.
- Every legal and illegal work-order transition, same-state no-op, reason requirement, terminal state,
  unknown order, and optimistic concurrency conflict.
- Assistant query and both memory-erasure endpoints enforce identity and admin policy.
- Health live/ready, metrics, exception mapping, trusted-host, CORS, request context, OpenAPI toggle,
  startup, and shutdown.

## 7. Execution phases

### Phase 0 — Stabilize the harness

1. Restore or replace the missing `tests.fixtures` helper and make test imports unambiguous.
2. Make `uv run pytest --collect-only` pass before measuring coverage.
3. Add markers for `unit`, `component`, `integration`, `e2e`, `contract`, `live`, and `slow`.
4. Ensure the default run makes no network calls and needs no secrets.
5. Regenerate the baseline without exclusions and preserve XML, HTML, and JSON coverage artifacts in
   CI.

Exit: all tests collect; no test module is ignored; the baseline is reproducible locally and in CI.

### Phase 1 — Establish traceability

1. Add the capability manifest described above.
2. Assign every `src/app/**/*.py` file to one role.
3. Link current tests to scenarios and mark uncovered scenarios as planned.
4. Add a validator that fails for orphan source files, missing test IDs, duplicate capability IDs, or
   an untested P0/P1 scenario.
5. Publish functional and role coverage alongside code coverage.

Exit: role assignment is 100%; the functional-coverage denominator is reviewable and stable.

### Phase 2 — Protect the critical assistant flow

1. Add component tests around `OrchestrateAssistantQuery` and the real LangGraph workflow.
2. Prove assembled context reaches model input.
3. Complete routing, policy limit, tool failure, and fallback-answer cases.
4. Add context share/spill/drop and tool-result budget tests.
5. Add short-term owner isolation and persistence-failure tests.

Exit: all ORCH, CTX, STM, and TOOL P0 scenarios pass.

### Phase 3 — Production persistence

1. Start PostgreSQL for integration tests.
2. Apply all Alembic migrations to an empty database and validate expected constraints/indexes.
3. Test `SKIP LOCKED`, concurrent fact deduplication, repository queries, retention, reconciliation,
   and checkpointer persistence.
4. Run integration tests in transactions or isolated schemas for repeatability.

Exit: no PostgreSQL-only behavior relies solely on SQLite tests.

### Phase 4 — Full API and lifecycle

1. Build the real container with deterministic vendor fakes.
2. Run the FastAPI lifespan and exercise each endpoint over HTTP.
3. Test resource start order, rollback on failed start, reverse stop order, and error aggregation.
4. Assert HTTP results together with persistence, tool audit/trace, telemetry, and memory effects.

Exit: at least one end-to-end scenario covers every router and every application module.

### Phase 5 — External contracts and resilience

1. Add adapter-level contract fixtures for OpenAI, Pinecone, Azure Blob, and Kafka.
2. Cover timeout, throttling, malformed response, partial failure, and idempotent retry cases.
3. Add opt-in live smoke checks in a protected CI environment.
4. Add concurrency, leakage, retention, erasure, and latency tests.

Exit: supported provider failures are observable, controlled, and do not violate scope or data
integrity.

## 8. Recommended release gates

Initial gates, to be ratcheted upward rather than lowered when a build fails:

| Gate | Pull request | Release |
| --- | ---: | ---: |
| Tests collect without exclusions | Required | Required |
| Overall statement coverage | >= 85% | >= 90% |
| Overall branch coverage | >= 70% | >= 80% |
| Changed-code coverage | >= 90% | >= 95% |
| ORCH/CTX/STM/LTM/TOOL P0 functional coverage | 100% | 100% |
| All P0 functional coverage | 100% | 100% |
| Weighted functional coverage | >= 85% | >= 95% |
| Role assignment coverage | 100% | 100% |
| P0/P1 scenarios linked to automated tests | 100% | 100% |
| Live external smoke suite | Optional | Passing in protected environment |

Keep the existing 80% combined gate while phases 0–2 are implemented, but report statement and branch
coverage separately immediately. Raise the gate only after tests assert behavior rather than importing
files for coverage.

## 9. Standard commands and outputs

Target command set after markers and PostgreSQL fixtures exist:

```powershell
uv run pytest -m unit
uv run pytest -m "component or integration"
uv run pytest -m e2e
uv run pytest --cov=app --cov-branch --cov-report=term-missing `
  --cov-report=xml:artifacts/coverage.xml `
  --cov-report=json:artifacts/coverage.json
uv run mypy src tests
uv run ruff check .
```

CI should publish:

- test counts by layer and pass/fail/skip status;
- statement and branch coverage overall and by role;
- weighted and unweighted functional coverage;
- uncovered P0/P1 scenario IDs;
- roleless or test-unlinked source files;
- performance percentiles and flaky-test history;
- contract/live-smoke status, clearly separated from the hermetic suite.

## 10. Definition of complete system coverage

The system is not “fully tested” because it reaches a line percentage. It is release-ready when:

1. every production file has a documented role and a traceable test strategy;
2. all P0 behavior and security/isolation scenarios pass at the required layer;
3. each public endpoint and background worker has success, denial/invalid-input, and failure-recovery
   coverage;
4. LangGraph, context, memory, and tool gateway work together in component and API end-to-end tests;
5. PostgreSQL and provider-specific contracts are exercised where fakes cannot prove semantics;
6. statement, branch, functional, role, and operational coverage gates all pass.
