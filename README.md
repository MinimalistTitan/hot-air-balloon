# Hot Aire Balloon

A production-oriented Python 3.14 service for an ERP-style operations platform built as a modular
monolith. The application exposes a FastAPI API, composes a dependency container at startup, and
organizes business capabilities into focused modules rather than a single all-in-one service.

The implementation includes user management, document processing, operations data access, and an AI assistant that can invoke tools across the business modules. Domain logic stays inside each module, while the app bootstrap and container wire infrastructure concerns such as SQLAlchemy sessions, messaging, blob storage, and telemetry.

## System architecture

The runtime composition is intentionally layered and module-based.

```text
Clients
  |
  v
FastAPI app
  |
  +--> API routers
  |       |
  |       +--> users module
  |       +--> documents module
  |       +--> operations module
  |       +--> assistant module
  |       +--> health endpoints
  |
  +--> Container.build()
          |
          +--> settings + database engine + session factory
          +--> modules: users, documents, operations, assistant
          +--> managed resources: Azure blob, Kafka outbox, etc.

Each module owns its domain, use cases, ports, and adapters; cross-module cooperation occurs
through explicit tool definitions, contracts, and infrastructure wiring in the composition root.
```

### Composition root

The application entry point in [src/app/main.py](src/app/main.py) creates the FastAPI application,
configures logging, request context middleware, tracing/metrics, exception handlers, and includes the
main API router. The module graph is assembled in [src/app/container.py](src/app/container.py), which
creates the SQLAlchemy engine and session factory before building each module and starting any managed
resources.

The router in [src/app/bootstrap/router.py](src/app/bootstrap/router.py) mounts the module-specific
APIRouters under a shared API prefix, enabling a clean, modular API surface for users, documents,
assistant interactions, operations, and health checks.

## Module breakdown

### Users module

The user module is centered on identity and account lifecycle. It exposes use cases for registration,
retrieval, and consistency auditing, and it defines a tool that can be surfaced to the assistant for
user-related validation tasks. It follows the same layered pattern as the rest of the application:
domain + application use cases + SQLAlchemy unit of work + presentation endpoints.

### Documents module

The document module handles uploads and integrates with Azure Blob Storage and event publishing. When
enabled, it creates the necessary infrastructure resources and publishes document lifecycle events via an
outbox pattern backed by Kafka. The module is designed so that blob storage and publisher behavior can
be injected during composition rather than hard-coded into the domain layer.

### Operations module

The operations module models ERP operational data and exposes read/write tooling to the assistant. It
includes work order, asset, maintenance, spare parts, and production schedule views, alongside a write
operation for updating work order status. These tools are registered with the assistant tool gateway so
that an LLM orchestrator can call them as part of a workflow instead of bypassing the domain layer.

### Assistant module

The assistant module is the orchestration layer for conversational and tool-augmented workflows. It
builds a LangGraph-based agent orchestrator, registers tool definitions from the modules, composes a
tool runtime, stores conversation state, and emits telemetry. The default behavior is to restrict tool
use via a policy that whitelists the available tools, avoids excessive loops, and fails closed when the
policy is violated.

## Architectural principles

- Modularity first: each business feature is assembled as a module with its own wiring,
  infrastructure, and application services.
- Dependency inversion: ports and adapters isolate the domain from persistence and external systems.
- Composition over embedded framework logic: the container wires resources and dependencies instead of
  scattering them across request handlers.
- Explicit integration boundaries: modules collaborate through tool definitions and contracts, not by
  importing each other’s implementation details.
- Resource lifecycle management: managed services are started and stopped centrally through the
  container lifecycle.

## Stack

- Python 3.14.6 and uv 0.12.1
- FastAPI, Pydantic Settings, SQLAlchemy async, Alembic, and PostgreSQL
- Structlog JSON logging, request correlation, Prometheus metrics, and health probes
- Ruff, strict mypy, pytest with branch coverage, pip-audit, and architecture tests
- Non-root Docker image, migration-gated Compose stack, and immutable-action CI

Runtime and development dependencies are reproducibly pinned in `uv.lock`.

## Local development

Install Python 3.14.6 and uv, then run:

```powershell
Copy-Item .env.example .env
uv sync --all-groups
uv run alembic upgrade head
uv run serve
```

The API listens on `http://127.0.0.1:8000`; OpenAPI UI is at
`http://127.0.0.1:8000/docs`.

To use PostgreSQL and the production image locally:

```powershell
docker compose up --build
```

## API surface

| Method | Path                 | Purpose            |
| ------ | -------------------- | ------------------ |
| `POST` | `/api/v1/users`      | Register a user    |
| `GET`  | `/api/v1/users/{id}` | Retrieve a user    |
| `GET`  | `/health/live`       | Process liveness   |
| `GET`  | `/health/ready`      | Database readiness |
| `GET`  | `/metrics`           | Prometheus metrics |

Additional endpoints are exposed by the documents, operations, and assistant modules as part of the
module routers.

## Quality gates

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run pip-audit
```

The test suite enforces at least 80% branch coverage and checks module import direction.

## Design

```text
HTTP / database adapters -> application use cases -> domain
             composition root wires dependencies
```

This remains the core layered model, but the current implementation extends it with multiple business
modules and explicit tool contracts. Business modules do not import another module's API or
infrastructure. Instead, the composition root binds them together with dependency injection, tool
registration, and resource management.

See [docs/architecture.md](docs/architecture.md) for module rules and the planned RAG boundary, and
[docs/operations.md](docs/operations.md) for deployment and production guidance.