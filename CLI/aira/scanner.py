"""
AIRA Scanner — Core orchestrator.

Supports:
- static scanning via language-specific checkers
- optional provider-assisted LLM scans
- hybrid mode that merges static and LLM findings
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from aira.checkers.js_checker import JSChecker
from aira.checkers.python_checker import PythonChecker
from aira.checkers.test_coverage_checker import scan_test_files
from aira.llm import LLMConfig, LLMRoutingError, run_llm_json_audit


CHECKS = {
    "C01": ("success_integrity", "SUCCESS INTEGRITY"),
    "C02": ("audit_integrity", "AUDIT / EVIDENCE INTEGRITY"),
    "C03": ("exception_handling", "BROAD EXCEPTION SUPPRESSION"),
    "C04": ("fallback_control", "DISTRIBUTED FALLBACK / DEGRADED EXECUTION"),
    "C05": ("bypass_controls", "BYPASS / OVERRIDE PATHS"),
    "C06": ("return_contracts", "AMBIGUOUS RETURN CONTRACTS"),
    "C07": ("logic_consistency", "PARALLEL LOGIC DRIFT"),
    "C08": ("background_tasks", "UNSUPERVISED BACKGROUND TASKS"),
    "C09": ("environment_safety", "ENVIRONMENT-DEPENDENT SAFETY"),
    "C10": ("startup_integrity", "STARTUP INTEGRITY"),
    "C11": ("determinism", "DETERMINISTIC REASONING DRIFT"),
    "C12": ("lineage", "SOURCE-TO-OUTPUT LINEAGE"),
    "C13": ("confidence_representation", "CONFIDENCE MISREPRESENTATION"),
    "C14": ("test_coverage_symmetry", "TEST COVERAGE ASYMMETRY"),
    "C15": ("idempotency_safety", "RETRY / IDEMPOTENCY ASSUMPTION DRIFT"),
}
CHECK_ID_BY_KEY = {key: check_id for check_id, (key, _) in CHECKS.items()}
CHECK_NAME_BY_KEY = {key: label for _, (key, label) in CHECKS.items()}

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".tox", "coverage", ".mypy_cache",
}

LLM_SYSTEM_PROMPT = (
    "You are AIRA — the AI-Induced Risk Audit scanner v1.2. "
    "You audit code for truthful failure handling. Return JSON only."
)


@dataclass
class ScanResult:
    target: str
    scanned_at: str
    files_scanned: int
    findings_total: int
    check_results: Dict[str, str]
    findings: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


def _default_check_results(files_scanned: int) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for check_id, (key, _) in CHECKS.items():
        if files_scanned == 0 or check_id in {"C07", "C12"}:
            results[key] = "UNKNOWN"
        else:
            results[key] = "PASS"
    return results


def _summarize(findings: List[Dict[str, Any]], check_results: Dict[str, str], files_scanned: int) -> Dict[str, Any]:
    high = sum(1 for finding in findings if finding.get("severity") == "HIGH")
    medium = sum(1 for finding in findings if finding.get("severity") == "MEDIUM")
    low = sum(1 for finding in findings if finding.get("severity") == "LOW")
    return {
        "files_scanned": files_scanned,
        "findings_total": len(findings),
        "by_severity": {
            "HIGH": high,
            "MEDIUM": medium,
            "LOW": low,
        },
        "checks_failed": sum(1 for value in check_results.values() if value == "FAIL"),
        "checks_passed": sum(1 for value in check_results.values() if value == "PASS"),
        "checks_unknown": sum(1 for value in check_results.values() if value == "UNKNOWN"),
        "requires_human_review": ["logic_consistency (C07)", "lineage (C12)"],
    }


def _normalize_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    normalized = []
    for finding in findings:
        normalized.append({
            "check_id": finding.get("check_id", "C00"),
            "check_name": finding.get("check_name", "UNSPECIFIED"),
            "severity": finding.get("severity", "LOW") if finding.get("severity") in {"HIGH", "MEDIUM", "LOW"} else "LOW",
            "file": finding.get("file", ""),
            "line": int(finding.get("line", 0) or 0),
            "description": str(finding.get("description", "")),
            "snippet": str(finding.get("snippet", "") or ""),
        })
    return sorted(normalized, key=lambda item: (severity_rank.get(item["severity"], 3), item["file"], item["line"], item["check_id"]))


def _build_result(
    target: Path,
    files_scanned: int,
    findings: List[Dict[str, Any]],
    check_results: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ScanResult:
    normalized_findings = _normalize_findings(findings)
    final_check_results = check_results or _default_check_results(files_scanned)
    summary = _summarize(normalized_findings, final_check_results, files_scanned)
    return ScanResult(
        target=str(target),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        files_scanned=files_scanned,
        findings_total=len(normalized_findings),
        check_results=final_check_results,
        findings=normalized_findings,
        summary=summary,
        metadata=metadata or {},
    )


def _merge_check_status(left: str, right: str) -> str:
    if "FAIL" in {left, right}:
        return "FAIL"
    if "PASS" in {left, right}:
        return "PASS"
    return "UNKNOWN"


def merge_scan_results(primary: ScanResult, secondary: ScanResult, mode: str) -> ScanResult:
    merged_findings = primary.findings + secondary.findings
    deduped = {}
    for finding in merged_findings:
        key = (
            finding.get("check_id"),
            finding.get("file"),
            finding.get("line"),
            finding.get("description"),
        )
        deduped[key] = finding

    merged_checks = {
        key: _merge_check_status(primary.check_results.get(key, "UNKNOWN"), secondary.check_results.get(key, "UNKNOWN"))
        for _, (key, _) in CHECKS.items()
    }
    metadata = {
        "mode": mode,
        "sources": [primary.metadata, secondary.metadata],
    }
    return _build_result(
        Path(primary.target),
        max(primary.files_scanned, secondary.files_scanned),
        list(deduped.values()),
        check_results=merged_checks,
        metadata=metadata,
    )


class AIRAScanner:
    def __init__(self, target: str, exclude_dirs: Optional[List[str]] = None):
        self.target = Path(target).resolve()
        self.exclude_dirs = set(exclude_dirs or []) | SKIP_DIRS

    def scan(self, mode: str = "static", llm_config: Optional[LLMConfig] = None) -> ScanResult:
        if mode not in {"static", "llm", "hybrid"}:
            raise ValueError(f"Unsupported scan mode: {mode}")

        if mode == "static":
            return self._scan_static()
        if mode == "llm":
            return self._scan_llm(llm_config or LLMConfig())

        static_result = self._scan_static()
        try:
            llm_result = self._scan_llm(llm_config or LLMConfig())
        except LLMRoutingError as exc:
            static_result.metadata = {
                **static_result.metadata,
                "mode": "hybrid",
                "llm_fallback": "static_only",
                "notes": [f"LLM scan unavailable: {exc}"],
            }
            return static_result

        return merge_scan_results(static_result, llm_result, mode="hybrid")

    def _scan_static(self) -> ScanResult:
        findings: List[Dict[str, Any]] = []
        files_scanned = 0

        if self.target.is_file():
            file_findings, scanned = self._scan_static_file(self.target)
            findings.extend(file_findings)
            files_scanned += scanned
        else:
            for filepath in self._iter_supported_files():
                file_findings, scanned = self._scan_static_file(filepath)
                findings.extend(file_findings)
                files_scanned += scanned

            _, test_findings = scan_test_files(str(self.target))
            findings.extend(test_findings)

        failed_checks = {finding["check_id"] for finding in findings if str(finding.get("check_id", "")).startswith("C")}
        check_results = _default_check_results(files_scanned)
        for check_id, (key, _) in CHECKS.items():
            if check_id in failed_checks:
                check_results[key] = "FAIL"

        return _build_result(
            self.target,
            files_scanned,
            findings,
            check_results=check_results,
            metadata={"mode": "static", "engine": "static"},
        )

    def _scan_static_file(self, filepath: Path) -> Tuple[List[Dict[str, Any]], int]:
        ext = filepath.suffix.lower()
        lang = SUPPORTED_EXTENSIONS.get(ext)
        if not lang:
            return [], 0

        try:
            checker = PythonChecker(str(filepath)) if lang == "python" else JSChecker(str(filepath))
            display_path = self._display_path(filepath)
            findings = [
                {
                    "check_id": item.check_id,
                    "check_name": item.check_name,
                    "severity": item.severity,
                    "file": display_path,
                    "line": item.line,
                    "description": item.description,
                    "snippet": item.snippet or "",
                }
                for item in checker.run()
            ]
            return findings, 1
        except Exception as exc:
            return [{
                "check_id": "SCANNER",
                "check_name": "SCANNER ERROR",
                "severity": "LOW",
                "file": self._display_path(filepath),
                "line": 0,
                "description": f"Scanner failed on file: {exc}",
                "snippet": "",
            }], 1

    def _display_path(self, filepath: Path) -> str:
        if self.target.is_file():
            return filepath.name
        return str(filepath.relative_to(self.target))

    def _iter_supported_files(self) -> List[Path]:
        files: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.target):
            dirnames[:] = [name for name in dirnames if name not in self.exclude_dirs]
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(filepath)
        return sorted(files)

    def _scan_llm(self, llm_config: LLMConfig) -> ScanResult:
        combined_source, files_scanned, truncated = self._build_llm_input(llm_config.max_context_chars)
        prompt = self._build_llm_prompt(combined_source)
        response = run_llm_json_audit(llm_config, LLM_SYSTEM_PROMPT, prompt)
        result = self._normalize_llm_result(response, files_scanned, truncated, llm_config)
        return result

    def _build_llm_input(self, max_context_chars: int) -> Tuple[str, int, bool]:
        files = [self.target] if self.target.is_file() else self._iter_supported_files()
        sections: List[str] = []
        total_chars = 0
        truncated = False

        for filepath in files:
            rel_path = filepath.name if self.target.is_file() else str(filepath.relative_to(self.target))
            content = filepath.read_text(encoding="utf-8", errors="replace")
            section = f"# FILE: {rel_path}\n{content}\n"
            if total_chars + len(section) <= max_context_chars:
                sections.append(section)
                total_chars += len(section)
                continue

            remaining = max_context_chars - total_chars
            if remaining > 0:
                snippet = section[:remaining]
                sections.append(f"{snippet}\n[...truncated for size...]\n")
                total_chars += len(snippet)
            truncated = True
            break

        return "\n".join(sections), len(files), truncated

    def _build_llm_prompt(self, combined_source: str) -> str:
        return f"""Analyze the following code snapshot with AIRA v1.2.

Return ONLY valid JSON in this exact structure:
{{
  "ai_failure_audit": {{
    "success_integrity": "PASS|FAIL|UNKNOWN",
    "audit_integrity": "PASS|FAIL|UNKNOWN",
    "exception_handling": "PASS|FAIL|UNKNOWN",
    "fallback_control": "PASS|FAIL|UNKNOWN",
    "bypass_controls": "PASS|FAIL|UNKNOWN",
    "return_contracts": "PASS|FAIL|UNKNOWN",
    "logic_consistency": "UNKNOWN",
    "background_tasks": "PASS|FAIL|UNKNOWN",
    "environment_safety": "PASS|FAIL|UNKNOWN",
    "startup_integrity": "PASS|FAIL|UNKNOWN",
    "determinism": "PASS|FAIL|UNKNOWN",
    "lineage": "UNKNOWN",
    "confidence_representation": "PASS|FAIL|UNKNOWN",
    "test_coverage_symmetry": "PASS|FAIL|UNKNOWN",
    "idempotency_safety": "PASS|FAIL|UNKNOWN"
  }},
  "findings": [
    {{
      "check_id": "C01",
      "check_name": "SUCCESS INTEGRITY",
      "severity": "HIGH|MEDIUM|LOW",
      "file": "relative/path.py",
      "line": 42,
      "description": "Specific grounded violation",
      "snippet": "optional code snippet"
    }}
  ]
}}

Rules:
- Keep C07 and C12 as UNKNOWN.
- Include only grounded findings.
- Use the file headers in the input for file attribution.
- If an exact file or line is unclear, use an empty file and line 0.

Code snapshot:

{combined_source}
"""

    def _normalize_llm_result(
        self,
        response: Dict[str, Any],
        files_scanned: int,
        truncated: bool,
        llm_config: LLMConfig,
    ) -> ScanResult:
        try:
            raw = json.loads(response["text"])
        except Exception as exc:
            raise LLMRoutingError(f"LLM returned invalid JSON: {exc}") from exc

        raw_checks = raw.get("ai_failure_audit") or {}
        check_results = _default_check_results(files_scanned)
        for _, (key, _) in CHECKS.items():
            value = raw_checks.get(key)
            if value in {"PASS", "FAIL", "UNKNOWN"}:
                check_results[key] = value
        check_results["logic_consistency"] = "UNKNOWN"
        check_results["lineage"] = "UNKNOWN"

        findings = []
        for item in raw.get("findings", []) if isinstance(raw.get("findings"), list) else []:
            check_id = item.get("check_id", "")
            normalized_check_id = check_id or CHECK_ID_BY_KEY.get(item.get("check_key", ""), "C00")
            if normalized_check_id in {"C07", "C12"}:
                continue
            check_name = item.get("check_name") or CHECKS.get(check_id, ("", "UNSPECIFIED"))[1]
            findings.append({
                "check_id": normalized_check_id,
                "check_name": check_name,
                "severity": item.get("severity", "LOW"),
                "file": str(item.get("file", "") or ""),
                "line": int(item.get("line", 0) or 0),
                "description": str(item.get("description", "")),
                "snippet": str(item.get("snippet", "") or ""),
            })

        return _build_result(
            self.target,
            files_scanned,
            findings,
            check_results=check_results,
            metadata={
                "mode": "llm",
                "provider": response.get("provider"),
                "model": response.get("model"),
                "configured_provider": llm_config.provider,
                "truncated": truncated,
                "engine": "llm",
            },
        )


def result_to_yaml(result: ScanResult) -> str:
    doc = {
        "aira_scan": {
            "version": "1.2",
            "target": result.target,
            "scanned_at": result.scanned_at,
            "summary": result.summary,
            "metadata": result.metadata,
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
            "metadata": result.metadata,
            "ai_failure_audit": result.check_results,
            "findings": result.findings,
        }
    }, indent=2)
