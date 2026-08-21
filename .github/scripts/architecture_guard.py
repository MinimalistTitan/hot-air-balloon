#!/usr/bin/env python3
"""Enforce modular-monolith dependency direction using only the Python standard library."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / ".github" / "governance" / "architecture-policy.json"
MODULES_ROOT = ROOT / "src" / "app" / "modules"


@dataclass(frozen=True, slots=True)
class Violation:
    key: str
    source: str
    line: int
    imported: str
    rule: str
    detail: str


def _load_policy(policy_path: Path) -> dict[str, Any]:
    with policy_path.open(encoding="utf-8") as policy_file:
        policy = json.load(policy_file)
    if policy.get("version") != 1:
        raise ValueError(f"Unsupported architecture policy version: {policy.get('version')!r}")
    return policy


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _key(source: str, imported: str, rule: str) -> str:
    return f"{source}|{imported}|{rule}"


def _is_allowed_prefix(imported: str, allowed_prefixes: list[str]) -> bool:
    return any(
        imported == prefix or imported.startswith(f"{prefix}.") for prefix in allowed_prefixes
    )


def _scan_module_file(path: Path, policy: dict[str, Any]) -> list[Violation]:
    relative = path.relative_to(ROOT).as_posix()
    parts = path.relative_to(ROOT).parts
    source_module = parts[3]
    source_layer = "wiring" if path.name == "wiring.py" else Path(parts[4]).stem
    unrestricted = set(policy["unrestricted_source_layers"])
    layer_dependencies: dict[str, list[str]] = policy["layer_dependencies"]
    cross_module: dict[str, list[str]] = policy["allowed_cross_module_imports"]
    violations: list[Violation] = []

    for line, imported in _imports(path):
        imported_parts = imported.split(".")
        if len(imported_parts) < 3 or imported_parts[:2] != ["app", "modules"]:
            continue
        if len(imported_parts) < 4:
            continue
        target_module = imported_parts[2]
        target_layer = imported_parts[3]

        if target_module != source_module:
            allowed = cross_module.get(source_module, [])
            if not _is_allowed_prefix(imported, allowed):
                rule = "cross-module-boundary"
                violations.append(
                    Violation(
                        key=_key(relative, imported, rule),
                        source=relative,
                        line=line,
                        imported=imported,
                        rule=rule,
                        detail=(
                            f"Module '{source_module}' may not import '{target_module}' through this "
                            "path; use an approved contract/port and composition-root wiring."
                        ),
                    )
                )
            continue

        if source_layer in unrestricted:
            continue
        allowed_layers = layer_dependencies.get(source_layer)
        if allowed_layers is None:
            continue
        if target_layer not in allowed_layers:
            rule = "layer-direction"
            violations.append(
                Violation(
                    key=_key(relative, imported, rule),
                    source=relative,
                    line=line,
                    imported=imported,
                    rule=rule,
                    detail=(
                        f"Layer '{source_layer}' may depend only on {allowed_layers}; "
                        f"'{target_layer}' points outward."
                    ),
                )
            )
    return violations


def _scan_module_free_roots(policy: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    for configured_root in policy["module_free_roots"]:
        root = ROOT / configured_root
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            for line, imported in _imports(path):
                if imported == "app.modules" or imported.startswith("app.modules."):
                    rule = "module-free-root"
                    violations.append(
                        Violation(
                            key=_key(relative, imported, rule),
                            source=relative,
                            line=line,
                            imported=imported,
                            rule=rule,
                            detail=f"'{configured_root}' must remain independent of business modules.",
                        )
                    )
    return violations


def evaluate_architecture(
    root: Path = ROOT,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    if root.resolve() != ROOT.resolve():
        raise ValueError("This guard must run from its repository installation")
    selected_policy = policy_path or DEFAULT_POLICY
    policy = _load_policy(selected_policy)
    violations: list[Violation] = []
    for path in sorted(MODULES_ROOT.rglob("*.py")):
        violations.extend(_scan_module_file(path, policy))
    violations.extend(_scan_module_free_roots(policy))

    baseline_entries = {entry["key"]: entry for entry in policy["allowed_violations"]}
    observed = {violation.key: violation for violation in violations}
    new_violations = [
        violation for violation in violations if violation.key not in baseline_entries
    ]
    baselined = [violation for violation in violations if violation.key in baseline_entries]
    resolved_baseline = sorted(set(baseline_entries) - set(observed))
    return {
        "passed": not new_violations,
        "policy": selected_policy.relative_to(ROOT).as_posix(),
        "files_scanned": len(list(MODULES_ROOT.rglob("*.py"))),
        "new_violations": [asdict(item) for item in new_violations],
        "baselined_violations": [asdict(item) for item in baselined],
        "resolved_baseline": resolved_baseline,
    }


def _text_report(result: dict[str, Any]) -> str:
    status = "PASS" if result["passed"] else "FAIL"
    lines = [
        f"Architecture guard: {status}",
        f"Files scanned: {result['files_scanned']}",
        f"Baselined debt: {len(result['baselined_violations'])}",
        f"New violations: {len(result['new_violations'])}",
    ]
    lines.extend(
        (
            f"- {violation['source']}:{violation['line']} [{violation['rule']}] "
            f"{violation['imported']} — {violation['detail']}"
        )
        for violation in result["new_violations"]
    )
    if result["resolved_baseline"]:
        lines.append("Resolved baseline entries (remove them from the policy):")
        lines.extend(f"- {item}" for item in result["resolved_baseline"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    result = evaluate_architecture(policy_path=policy_path)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(_text_report(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
