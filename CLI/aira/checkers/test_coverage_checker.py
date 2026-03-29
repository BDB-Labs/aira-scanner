"""
AIRA Test Coverage Asymmetry Analyzer (Check 14)
Analyzes test files to measure happy-path vs failure-path coverage ratio.
Works for both Python and JavaScript/TypeScript test files.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class TestCoverageReport:
    file: str
    total_tests: int
    happy_path_tests: int
    failure_path_tests: int
    asymmetry_ratio: float  # happy/failure — higher = worse
    flagged_findings: List[dict]


# Patterns that indicate happy-path tests
HAPPY_PATH_PATTERNS = [
    r'(?:test|it|describe)\s*\(["\'].*(?:success|happy|works|correct|valid|pass|ok|return|resolv|complet)',
    r'expect\s*\(.*\)\s*\.\s*(?:toBe|toEqual|toReturn|toResolve|toBeTruthy|toMatchObject)',
    r'assert\s+\w+\s*==',
    r'assertEqual\s*\(',
    r'assertTrue\s*\(',
]

# Patterns that indicate failure/edge-case tests
FAILURE_PATH_PATTERNS = [
    r'(?:test|it|describe)\s*\(["\'].*(?:fail|error|invalid|reject|throw|exception|edge|missing|null|undefined|timeout|bad|wrong|corrupt|empty)',
    r'expect\s*\(.*\)\s*\.\s*(?:toThrow|toReject|toFail|toBeFalsy|toBeNull|toBeUndefined|toRaise)',
    r'assertRaises\s*\(',
    r'pytest\.raises\s*\(',
    r'with\s+(?:self\.)?assertRaises\s*\(',
    r'\.rejects\s*\.',
    r'expect\s*\(\s*\w+\s*\)\s*\.\s*rejects',
]

# Test file detection
TEST_FILE_PATTERNS = [
    r'test_.*\.py$',
    r'.*_test\.py$',
    r'.*\.test\.[jt]sx?$',
    r'.*\.spec\.[jt]sx?$',
    r'__tests__',
]


def is_test_file(filepath: str) -> bool:
    name = Path(filepath).name
    path_str = str(filepath)
    return any(re.search(p, path_str, re.IGNORECASE) for p in TEST_FILE_PATTERNS)


def analyze_test_file(filepath: str) -> TestCoverageReport:
    source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    happy = 0
    failure = 0
    total = 0
    findings = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        is_happy = any(re.search(p, stripped, re.IGNORECASE) for p in HAPPY_PATH_PATTERNS)
        is_failure = any(re.search(p, stripped, re.IGNORECASE) for p in FAILURE_PATH_PATTERNS)

        if is_happy and not is_failure:
            happy += 1
            total += 1
        elif is_failure:
            failure += 1
            total += 1
        elif re.search(r'(?:def test_|it\s*\(|test\s*\()', stripped):
            # Generic test — count as happy by default (conservative)
            happy += 1
            total += 1

    ratio = (happy / failure) if failure > 0 else float('inf')

    if ratio > 3.0 or (failure == 0 and total > 0):
        findings.append({
            "check_id": "C14",
            "check_name": "TEST COVERAGE ASYMMETRY",
            "severity": "HIGH" if (failure == 0 or ratio > 5.0) else "MEDIUM",
            "file": filepath,
            "line": 1,
            "description": (
                f"Test coverage heavily skewed toward happy paths. "
                f"Happy-path tests: {happy}, Failure-path tests: {failure}, "
                f"Ratio: {'∞' if failure == 0 else f'{ratio:.1f}:1'}. "
                "AI-generated test suites systematically under-cover failure branches."
            )
        })

    return TestCoverageReport(
        file=filepath,
        total_tests=total,
        happy_path_tests=happy,
        failure_path_tests=failure,
        asymmetry_ratio=ratio,
        flagged_findings=findings
    )


def scan_test_files(root: str) -> Tuple[List[TestCoverageReport], List[dict]]:
    """Scan all test files under root and return reports + findings."""
    reports = []
    all_findings = []

    for path in Path(root).rglob("*"):
        if path.is_file() and is_test_file(str(path)):
            try:
                report = analyze_test_file(str(path))
                reports.append(report)
                all_findings.extend(report.flagged_findings)
            except Exception:
                pass

    return reports, all_findings
