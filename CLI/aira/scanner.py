"""
AIRA Scanner — Core Orchestrator
Coordinates all checkers, aggregates findings, and produces YAML reports.
"""

import os
import sys
import json
import yaml
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aira.checkers.python_checker import PythonChecker
from aira.checkers.js_checker import JSChecker
from aira.checkers.test_coverage_checker import scan_test_files, is_test_file


# ── Check registry ──────────────────────────────────────────────
CHECKS = {
    "C01": ("success_integrity",         "SUCCESS INTEGRITY"),
    "C02": ("audit_integrity",           "AUDIT / EVIDENCE INTEGRITY"),
    "C03": ("exception_handling",        "BROAD EXCEPTION SUPPRESSION"),
    "C04": ("fallback_control",          "DISTRIBUTED FALLBACK / DEGRADED EXECUTION"),
    "C05": ("bypass_controls",           "BYPASS / OVERRIDE PATHS"),
    "C06": ("return_contracts",          "AMBIGUOUS RETURN CONTRACTS"),
    "C07": ("logic_consistency",         "PARALLEL LOGIC DRIFT"),
    "C08": ("background_tasks",          "UNSUPERVISED BACKGROUND TASKS"),
    "C09": ("environment_safety",        "ENVIRONMENT-DEPENDENT SAFETY"),
    "C10": ("startup_integrity",         "STARTUP INTEGRITY"),
    "C11": ("determinism",               "DETERMINISTIC REASONING DRIFT"),
    "C12": ("lineage",                   "SOURCE-TO-OUTPUT LINEAGE"),
    "C13": ("confidence_representation", "CONFIDENCE MISREPRESENTATION"),
    "C14": ("test_coverage_symmetry",    "TEST COVERAGE ASYMMETRY"),
    "C15": ("idempotency_safety",        "RETRY / IDEMPOTENCY ASSUMPTION DRIFT"),
}

SUPPORTED_EXTENSIONS = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".jsx":  "javascript",
    ".tsx":  "typescript",
    ".mjs":  "javascript",
    ".cjs":  "javascript",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".tox", "coverage", ".mypy_cache"
}


@dataclass
class ScanResult:
    target: str
    scanned_at: str
    files_scanned: int
    findings_total: int
    check_results: Dict[str, str]   # check_key -> PASS | FAIL | UNKNOWN
    findings: List[Dict[str, Any]]
    summary: Dict[str, Any]


class AIRAScanner:
    def __init__(self, target: str, exclude_dirs: Optional[List[str]] = None):
        self.target = Path(target).resolve()
        self.exclude_dirs = set(exclude_dirs or []) | SKIP_DIRS
        self.all_findings: List[Dict[str, Any]] = []
        self.files_scanned = 0

    def scan(self) -> ScanResult:
        """Run full AIRA scan against target path."""
        if self.target.is_file():
            self._scan_file(str(self.target))
        else:
            self._scan_directory(str(self.target))
            _, test_findings = scan_test_files(str(self.target))
            for f in test_findings:
                self.all_findings.append(f)

        return self._build_result()

    def _scan_directory(self, root: str):
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded dirs
            dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    fpath = os.path.join(dirpath, fname)
                    self._scan_file(fpath)

    def _scan_file(self, filepath: str):
        ext = Path(filepath).suffix.lower()
        lang = SUPPORTED_EXTENSIONS.get(ext)
        if not lang:
            return

        self.files_scanned += 1
        try:
            if lang == "python":
                checker = PythonChecker(filepath)
                findings = checker.run()
            else:
                checker = JSChecker(filepath)
                findings = checker.run()

            for f in findings:
                self.all_findings.append({
                    "check_id":   f.check_id,
                    "check_name": f.check_name,
                    "severity":   f.severity,
                    "file":       filepath,
                    "line":       f.line,
                    "description": f.description,
                    "snippet":    f.snippet or "",
                })
        except Exception as e:
            # Scanner itself must not silently fail — surface to caller
            self.all_findings.append({
                "check_id":   "SCANNER",
                "check_name": "SCANNER ERROR",
                "severity":   "LOW",
                "file":       filepath,
                "line":       0,
                "description": f"Scanner failed on file: {e}",
                "snippet":    "",
            })

    def _build_result(self) -> ScanResult:
        # Determine PASS/FAIL/UNKNOWN per check
        failed_checks = {f["check_id"] for f in self.all_findings if f["check_id"].startswith("C")}

        check_results = {}
        for check_id, (key, _) in CHECKS.items():
            if check_id in failed_checks:
                check_results[key] = "FAIL"
            elif self.files_scanned == 0:
                check_results[key] = "UNKNOWN"
            else:
                # C07 (logic drift) and C12 (lineage) require human review
                if check_id in ("C07", "C12"):
                    check_results[key] = "UNKNOWN"
                else:
                    check_results[key] = "PASS"

        # Severity breakdown
        high   = sum(1 for f in self.all_findings if f.get("severity") == "HIGH")
        medium = sum(1 for f in self.all_findings if f.get("severity") == "MEDIUM")
        low    = sum(1 for f in self.all_findings if f.get("severity") == "LOW")

        summary = {
            "files_scanned":   self.files_scanned,
            "findings_total":  len(self.all_findings),
            "by_severity": {
                "HIGH":   high,
                "MEDIUM": medium,
                "LOW":    low,
            },
            "checks_failed":  len(failed_checks),
            "checks_passed":  sum(1 for v in check_results.values() if v == "PASS"),
            "checks_unknown": sum(1 for v in check_results.values() if v == "UNKNOWN"),
            "requires_human_review": ["logic_consistency (C07)", "lineage (C12)"],
        }

        return ScanResult(
            target=str(self.target),
            scanned_at=datetime.now(timezone.utc).isoformat(),
            files_scanned=self.files_scanned,
            findings_total=len(self.all_findings),
            check_results=check_results,
            findings=sorted(self.all_findings, key=lambda x: (x.get("severity", "LOW"), x.get("file", ""))),
            summary=summary,
        )


def result_to_yaml(result: ScanResult) -> str:
    """Serialize ScanResult to AIRA-standard YAML format."""
    doc = {
        "aira_scan": {
            "version": "1.2",
            "target": result.target,
            "scanned_at": result.scanned_at,
            "summary": result.summary,
            "ai_failure_audit": result.check_results,
            "findings": result.findings,
        }
    }
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


def result_to_json(result: ScanResult) -> str:
    return json.dumps({
        "aira_scan": {
            "version": "1.2",
            "target": result.target,
            "scanned_at": result.scanned_at,
            "summary": result.summary,
            "ai_failure_audit": result.check_results,
            "findings": result.findings,
        }
    }, indent=2)
