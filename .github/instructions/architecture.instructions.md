---
applyTo: "src/app/modules/**/*.py"
---

# Module architecture

- Keep dependencies inward: presentation and infrastructure may call application; application may
  call domain and contracts; domain must not know frameworks, persistence, transport, or wiring.
- Define I/O and provider needs as application/domain protocols. Implement them in infrastructure
  and bind them in the module `wiring.py` or `app/container.py`.
- Cross-module imports require an explicit stable contract or approved port. Update
  `.github/governance/architecture-policy.json` only after documenting why the dependency is stable,
  directional, and cannot be composed at the root.
- Never expand `allowed_violations`. When removing a baselined violation, remove its baseline entry.
- Business rules, authorization decisions, and side-effect policy do not belong in routers, ORM
  models, LLM prompts, or SDK adapters.
- New modules mirror the domain/application/infrastructure/presentation/wiring layout and include
  boundary tests. Run `uv run python .github/scripts/architecture_guard.py` after import changes.
