# Security policy

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities, leaked credentials, authorization bypasses,
cross-user/site data exposure, prompt-injection chains, or unsafe tool actions.

Use GitHub private vulnerability reporting at:
https://github.com/MinimalistTitan/hot-air-balloon/security/advisories/new

Include the affected revision, component and entry point, reproduction steps or proof of concept,
impact and data scope, required privileges, observed logs (redacted), and any suggested mitigation. Do
not include real credentials, personal data, customer documents, or production prompt/tool payloads.

## Response targets

- Acknowledgement: within 2 business days.
- Initial severity and containment decision: within 5 business days.
- Critical/high issues: contain immediately and publish a remediation plan after affected secrets,
  sessions, data, and downstream systems have been assessed.

These are response targets, not a promise of a fix date. Coordinated disclosure timing is agreed with
the reporter after users can be protected.

## Scope priorities

Highest priority includes authentication/authorization bypass, cross-user or cross-site retrieval,
arbitrary tool execution, prompt injection leading to data disclosure or side effects, secret leakage,
unsafe file processing, SQL/command injection, dependency/workflow supply-chain compromise, retention
or erasure failure, and audit-log tampering.

Only test systems and data you are authorized to use. Avoid privacy violations, service disruption,
social engineering, persistence, destructive actions, and accessing data beyond the minimum needed to
demonstrate impact.

