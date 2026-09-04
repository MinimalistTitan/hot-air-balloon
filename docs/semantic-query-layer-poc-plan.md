# Semantic Query Layer Proof of Concept

## Purpose

Demonstrate that the assistant can answer a multi-table ERP question dynamically without allowing an LLM to execute arbitrary SQL.

The proof of concept covers one relationship traversal:

```text
prior work orders -> affected assets -> asset name and code
```

Example conversation:

```text
User: Show me three open work orders at PLANT-HCM.
User: What assets do they affect?
```

Expected result:

```text
WO-HCM-0101 affects <asset name> (<asset code>).
WO-HCM-0001 affects <asset name> (<asset code>).
```

## Non-Goals

- No direct LLM-generated SQL execution.
- No write operations, DDL, arbitrary functions, arbitrary joins, or multi-statement queries.
- No replacement of the existing tool gateway, authorization, audit, or deterministic reference resolution.
- No generalized natural-language-to-SQL product feature.
- No public API contract change.

## Architecture

```text
User query
  -> structured LLM query proposal
  -> server-side proposal validation
  -> prior-evidence reference resolution
  -> authorized semantic-query compiler
  -> parameterized read-only database query
  -> result schema validation and bounds checks
  -> deterministic response formatter
```

The LLM may propose an operation. The server decides whether it is valid, authorized, and executable.

## POC Query Contract

Use a Pydantic model or immutable application value object rather than SQL text:

```python
class SemanticQueryPlan(BaseModel):
    operation: Literal["follow_relationship"]
    source: Literal["previous_collection"]
    relationship: Literal["work_order.asset"]
    fields: tuple[Literal["id", "code", "name"], ...]
    limit: int
```

The POC accepts only:

```json
{
  "operation": "follow_relationship",
  "source": "previous_collection",
  "relationship": "work_order.asset",
  "fields": ["id", "code", "name"],
  "limit": 20
}
```

Reject all unknown operations, fields, relationships, source types, and limits.

## Source Evidence Resolution

1. Use the existing owner-scoped `assistant_conversation_evidence` records.
2. Resolve `they`, `those`, `previous work orders`, and `above work orders` to the latest eligible work-order collection.
3. Extract the persisted `asset_id` from each selected work-order evidence item.
4. Deduplicate IDs and enforce a maximum source-ID count, for example 20.
5. Fail closed when the prior collection has no asset IDs, is ambiguous, expired, belongs to another conversation, or does not represent work orders.

The work-order result adapter must retain `asset_id` as structured evidence. It may also retain `asset_code` if that supports response formatting, but IDs are the authoritative relationship key.

## Authorized Query Execution

Create an application port such as:

```python
class SemanticQueryPort(Protocol):
    async def list_assets_for_work_orders(
        self,
        work_order_ids: tuple[UUID, ...],
        authorization_context: AuthorizationContext,
        limit: int,
    ) -> tuple[AssetProjection, ...]: ...
```

The infrastructure adapter compiles a fixed ORM/SQLAlchemy query. It must never accept SQL text.

Conceptual SQL:

```sql
SELECT DISTINCT
    wo.id AS work_order_id,
    wo.code AS work_order_code,
    a.id AS asset_id,
    a.code AS asset_code,
    a.name AS asset_name
FROM work_orders AS wo
JOIN assets AS a ON a.id = wo.asset_id
WHERE wo.id = ANY(:work_order_ids)
  AND a.site_id = ANY(:authorized_site_ids)
LIMIT :limit;
```

Authorization requirements:

- Derive user identity and site scope only from trusted `AuthorizationContext`.
- Require `assets:read` and `work_orders:read` before execution.
- Inject site scope server-side; never trust site scope from the model or conversation evidence.
- Revalidate the relationship through the database on every execution.
- Use the existing gateway or an equivalent single enforcement boundary with audit and rate limits.

Database requirements:

- Parameterize all values.
- Use a least-privilege read-only database role.
- Enforce statement timeout and bounded result count.
- Return only allowlisted projection columns.
- Do not log raw SQL, raw result rows, prompts, or model outputs.

## Response

Use a deterministic formatter. The LLM is optional only after validated fact selection; it must not select facts or infer relationships.

Example formatter output:

```text
WO-HCM-0101 affects STAMP-PRESS-01 (Stamping Press 01).
WO-HCM-0001 affects CNC-MILL-01 (CNC Milling Machine 01).
```

For missing or inaccessible data:

```text
I cannot resolve the affected assets from the referenced work orders.
```

Do not broaden into an unfiltered work-order or asset list.

## Implementation Phases

### Phase 1: Evidence and Contract

1. Extend the work-order evidence adapter to retain `asset_id`.
2. Add a tested `SemanticQueryPlan` model with `extra="forbid"`.
3. Add a deterministic parser for the narrow POC phrase family:
   - `what assets do they affect`
   - `assets involved in the previous work orders`
   - `asset for the second work order`
4. Return typed outcomes: resolved, no reference, unsupported relationship, ambiguous, unauthorized, or empty.

### Phase 2: Query Port and Adapter

1. Define the application port and an `AssetProjection` value object.
2. Implement a fixed SQLAlchemy repository method joining work orders to assets by bounded IDs.
3. Enforce permissions and site scope at the gateway/use-case boundary and query boundary.
4. Add deterministic response formatting.

### Phase 3: LLM Proposal Experiment

1. Add an optional structured-output LLM classifier that can propose only the POC `SemanticQueryPlan`.
2. Compare it with the deterministic phrase parser.
3. Accept a proposal only after Pydantic validation and server-side policy validation.
4. Fall back to clarification or the existing assistant planner if no safe plan is available.

## Test Matrix

Unit tests:

- Valid work-order-to-asset plan parses and validates.
- Unknown operation, relationship, field, source, or limit is rejected.
- Prior evidence resolves only the latest eligible work-order collection.
- Missing asset IDs, ordinal overflow, and ambiguous references return safe outcomes.
- IDs are deduplicated and capped.
- Formatter handles one, many, empty, and inaccessible projections.

Integration tests:

- Query returns only assets linked to the provided work-order IDs.
- Cross-site and cross-user requests return no unauthorized rows.
- A forged evidence asset ID cannot bypass current authorization.
- Database timeout and repository failure produce safe observable failure results.
- Migration and retention remove expired conversation evidence.

End-to-end scenario:

```text
1. List PLANT-HCM open work orders.
2. Ask a priority question.
3. Ask which assets the same work orders affect.
4. Verify exactly the linked assets are returned.
5. Verify no unfiltered work-order query or unscoped asset query occurs.
```

## Success Criteria

- The example returns only assets related to the prior work-order set.
- No LLM-generated SQL reaches the database.
- All queries are parameterized and bounded.
- Current user/site authorization is enforced at execution time.
- Unsupported or ambiguous requests clarify rather than broadening retrieval.
- Query plans, validation decisions, result counts, and latency are auditable without logging sensitive contents.
- Focused unit/integration tests pass, followed by repository quality and architecture gates.

## Rollout and Rollback

Add the POC behind a disabled-by-default typed setting.

Enable it only for a test environment first. Monitor safe-plan acceptance, validation failures, unresolved references, row counts, query latency, and authorization denials.

Rollback is configuration-only: disable semantic-query plan execution and retain the additive evidence fields/migration. No data migration or destructive rollback is required.
