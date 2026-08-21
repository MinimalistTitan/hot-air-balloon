---
name: security-privacy-review
description: Perform a threat, privacy, and abuse-case review for authorization, tools, LLM/RAG, documents, storage, telemetry, external providers, or sensitive data changes.
license: Same terms as this repository.
---

# Security and privacy review

Use this skill when a change touches trust boundaries, identities, permissions, tools, uploads,
retrieval, memory, prompts, logs, providers, secrets, or personal/business data.

## Review method

1. Map assets, actors, entry points, data flows, stores, external providers, and trust boundaries.
2. Enumerate abuse cases using STRIDE plus the current OWASP GenAI risks: prompt injection,
   sensitive-information disclosure, supply-chain/data poisoning, improper output handling,
   excessive agency, system-prompt leakage, vector/embedding weaknesses, misinformation, and
   unbounded consumption.
3. Trace authorization from authenticated server context to use case, tool gateway, database query,
   vector metadata filter, and response. Test horizontal access, site-scope bypass, forged identifiers,
   stale roles, and confused-deputy behavior.
4. Inventory each data field: purpose, sensitivity, source, destination, retention, deletion, audit,
   encryption, and log/telemetry exposure. Apply minimization and deny-by-default retention.
5. Verify validation, output encoding, upload bounds/type verification, parameterized queries,
   secret redaction, timeout/rate/cost budgets, safe error text, idempotency, and fail-closed behavior.
6. Add adversarial and negative tests. Do not claim prompt text alone mitigates prompt injection or
   information disclosure.

## Output contract

Return a table with threat, affected asset/boundary, likelihood, impact, existing control, missing
control, evidence, owner, and priority. Mark release blockers explicitly. Cite current primary sources
and include an `as of YYYY-MM-DD` date.

Primary references:

- OWASP GenAI Top 10: https://genai.owasp.org/llm-top-10/
- NIST SSDF publications: https://csrc.nist.gov/projects/ssdf/publications
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
