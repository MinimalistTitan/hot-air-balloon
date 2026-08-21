#!/usr/bin/env python3
"""Calculate the evidence-backed repository governance score."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import architecture_guard

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / ".github" / "governance" / "scorecard-policy.json"


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric_id: str
    category: str
    weight: int
    passed: bool
    critical: bool
    description: str
    evidence: str
    reference: str


def _paths_exist(metric: dict[str, Any]) -> tuple[bool, str]:
    paths = metric["paths"]
    missing = [path for path in paths if not (ROOT / path).exists()]
    return (
        not missing,
        f"present: {', '.join(paths)}" if not missing else f"missing: {', '.join(missing)}",
    )


def _file_contains(metric: dict[str, Any]) -> tuple[bool, str]:
    path = ROOT / metric["path"]
    if not path.exists():
        return False, f"missing: {metric['path']}"
    content = path.read_text(encoding="utf-8")
    missing = [pattern for pattern in metric["patterns"] if pattern not in content]
    return (
        not missing,
        f"verified {metric['path']}" if not missing else f"missing patterns: {missing}",
    )


def _glob_count(metric: dict[str, Any]) -> tuple[bool, str]:
    matches = list(ROOT.glob(metric["pattern"]))
    minimum = int(metric["minimum"])
    return len(matches) >= minimum, f"{len(matches)} found; minimum {minimum}"


def _coverage_floor(metric: dict[str, Any]) -> tuple[bool, str]:
    path = ROOT / metric["path"]
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    match = re.search(r"^fail_under\s*=\s*(\d+(?:\.\d+)?)", content, re.MULTILINE)
    value = float(match.group(1)) if match else 0.0
    branch_enabled = bool(re.search(r"^branch\s*=\s*true\s*$", content, re.MULTILINE))
    minimum = float(metric["minimum"])
    passed = value >= minimum and branch_enabled
    return passed, f"branch={branch_enabled}, fail_under={value:g}, minimum={minimum:g}"


def _workflows_pinned(_: dict[str, Any]) -> tuple[bool, str]:
    unpinned: list[str] = []
    uses_pattern = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
    sha_pattern = re.compile(r"^[0-9a-fA-F]{40}$")
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for reference in uses_pattern.findall(workflow.read_text(encoding="utf-8")):
            if reference.startswith(("./", "docker://")):
                continue
            _, separator, revision = reference.rpartition("@")
            if not separator or not sha_pattern.fullmatch(revision):
                unpinned.append(f"{workflow.relative_to(ROOT).as_posix()}: {reference}")
    return (
        not unpinned,
        "all external actions use full SHAs" if not unpinned else "; ".join(unpinned),
    )


def _workflow_permissions(_: dict[str, Any]) -> tuple[bool, str]:
    missing: list[str] = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        content = workflow.read_text(encoding="utf-8")
        if not re.search(r"^permissions:\s*(?:\n|$)", content, re.MULTILINE):
            missing.append(workflow.relative_to(ROOT).as_posix())
    return (
        not missing,
        "all workflows declare permissions" if not missing else f"missing: {missing}",
    )


@lru_cache(maxsize=1)
def _architecture_result() -> dict[str, Any]:
    return architecture_guard.evaluate_architecture()


def _architecture(_: dict[str, Any]) -> tuple[bool, str]:
    result = _architecture_result()
    evidence = (
        f"{result['files_scanned']} files; {len(result['new_violations'])} new; "
        f"{len(result['baselined_violations'])} baselined"
    )
    return bool(result["passed"]), evidence


def _architecture_debt_zero(_: dict[str, Any]) -> tuple[bool, str]:
    result = _architecture_result()
    debt = len(result["baselined_violations"])
    return debt == 0, f"{debt} baselined violation(s); target 0"


def _technology_freshness(metric: dict[str, Any]) -> tuple[bool, str]:
    path = ROOT / metric["path"]
    if not path.exists():
        return False, f"missing: {metric['path']}"
    data = json.loads(path.read_text(encoding="utf-8"))
    verified = date.fromisoformat(data["last_verified"])
    max_age = int(data["max_age_days"])
    age = (datetime.now(UTC).date() - verified).days
    sources = data.get("sources", [])
    valid_sources = bool(sources) and all(
        source.get("id") and str(source.get("url", "")).startswith("https://") for source in sources
    )
    passed = 0 <= age <= max_age and valid_sources
    return (
        passed,
        f"verified {verified.isoformat()}; age {age} days; limit {max_age}; sources {len(sources)}",
    )


Evaluator = Callable[[dict[str, Any]], tuple[bool, str]]
EVALUATORS: dict[str, Evaluator] = {
    "architecture_guard": _architecture,
    "architecture_debt_zero": _architecture_debt_zero,
    "coverage_floor": _coverage_floor,
    "file_contains": _file_contains,
    "glob_count": _glob_count,
    "paths_exist": _paths_exist,
    "technology_freshness": _technology_freshness,
    "workflow_permissions": _workflow_permissions,
    "workflows_pinned": _workflows_pinned,
}


def _load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("version") != 1:
        raise ValueError(f"Unsupported scorecard policy version: {policy.get('version')!r}")
    total = sum(int(metric["weight"]) for metric in policy["metrics"])
    if total != 100:
        raise ValueError(f"Metric weights must total 100, found {total}")
    return policy


def evaluate(policy: dict[str, Any]) -> tuple[list[MetricResult], int]:
    results: list[MetricResult] = []
    score = 0
    for metric in policy["metrics"]:
        evaluator_name = metric["evaluator"]
        evaluator = EVALUATORS.get(evaluator_name)
        if evaluator is None:
            raise ValueError(f"Unknown evaluator {evaluator_name!r} for {metric['id']}")
        try:
            passed, evidence = evaluator(metric)
        except (OSError, ValueError, SyntaxError, json.JSONDecodeError) as error:
            passed, evidence = False, f"evaluation error: {type(error).__name__}: {error}"
        weight = int(metric["weight"])
        if passed:
            score += weight
        results.append(
            MetricResult(
                metric_id=metric["id"],
                category=metric["category"],
                weight=weight,
                passed=passed,
                critical=bool(metric.get("critical", False)),
                description=metric["description"],
                evidence=evidence,
                reference=metric["reference"],
            )
        )
    return results, score


def _markdown(results: list[MetricResult], score: int, minimum: int) -> str:
    category_possible: dict[str, int] = defaultdict(int)
    category_earned: dict[str, int] = defaultdict(int)
    for result in results:
        category_possible[result.category] += result.weight
        if result.passed:
            category_earned[result.category] += result.weight
    critical_failures = [
        result.metric_id for result in results if result.critical and not result.passed
    ]
    overall = "PASS" if score >= minimum and not critical_failures else "FAIL"
    lines = [
        "# Repository governance score",
        "",
        f"**{score}/100 — {overall}** (minimum {minimum}; critical failures: "
        f"{', '.join(critical_failures) if critical_failures else 'none'})",
        "",
        "This score measures versioned repository evidence, not GitHub organization settings or runtime security.",
        "",
        "| Category | Score |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {category} | {category_earned[category]}/{possible} |"
        for category, possible in category_possible.items()
    )
    lines.extend(
        [
            "",
            "| Metric | Result | Weight | Evidence | Reference |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for result in results:
        status = "PASS" if result.passed else ("CRITICAL FAIL" if result.critical else "FAIL")
        evidence = result.evidence.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {result.metric_id}: {result.description} | {status} | {result.weight} | "
            f"{evidence} | [source]({result.reference}) |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--min-score", type=int)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    policy = _load_policy(policy_path)
    minimum = int(args.min_score if args.min_score is not None else policy["minimum_score"])
    results, score = evaluate(policy)
    critical_failures = [
        result.metric_id for result in results if result.critical and not result.passed
    ]

    if args.format == "json":
        output = json.dumps(
            {
                "score": score,
                "minimum": minimum,
                "passed": score >= minimum and not critical_failures,
                "critical_failures": critical_failures,
                "metrics": [asdict(result) for result in results],
            },
            indent=2,
        )
    else:
        output = _markdown(results, score, minimum)
    print(output, end="" if output.endswith("\n") else "\n")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(_markdown(results, score, minimum))
    return 0 if score >= minimum and not critical_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
