---
applyTo: "**/*.py"
---

- All function, method, and callback parameters must have explicit types.
- All functions must have explicit return types, including `-> None`.
- Fully parameterize generic types such as `Callable`, `dict`, and `list`.
- Do not use untyped `Callable`; specify its parameter and return types.
- Code must pass `uv run ruff check .` and `uv run mypy src tests`.
- Follow the repository's strict mypy configuration.