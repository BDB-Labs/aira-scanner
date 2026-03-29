"""
AIRA research submission helpers for CLI/CI usage.

This path is intentionally aggregate-only:
- no source code
- no file-level findings
- no snippets
- no raw target paths
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import error, parse, request


BASELINE_FIELD_ORDER = (
    "Submitted At",
    "Checks JSON",
    "High Count",
    "Medium Count",
    "Low Count",
    "Total Findings",
    "Checks Failed",
    "Engine",
    "Source",
)

OPTIONAL_FIELD_ORDER = (
    "Check Count JSON",
    "Check Severity JSON",
    "Checks Passed",
    "Checks Unknown",
    "Files Scanned",
    "Scan Mode",
    "Provider",
    "Model",
    "Target Kind",
    "CI Workflow",
    "CI Run ID",
    "CI Ref",
)

UNKNOWN_FIELD_RE = re.compile(r'Unknown field name:\s*"?(?P<field>[^"]+)"?')


class ResearchSubmissionError(RuntimeError):
    """Raised when aggregate research submission fails."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def infer_research_source(explicit_source: Optional[str] = None) -> str:
    if explicit_source:
        return explicit_source
    if _env("GITHUB_REPOSITORY"):
        return f"github:{_env('GITHUB_REPOSITORY')}"
    if _env("CI"):
        return "ci"
    return "aira-cli"


def _airtable_target() -> tuple[Optional[str], str, Optional[str]]:
    return (
        _env("AIRTABLE_BASE_ID"),
        _env("AIRTABLE_TABLE") or "Submissions",
        _env("AIRTABLE_TOKEN"),
    )


def airtable_config_snapshot() -> Dict[str, Any]:
    base_id, table, token = _airtable_target()
    return {
        "configured": bool(base_id and token),
        "base_id_configured": bool(base_id),
        "table": table,
        "token_configured": bool(token),
    }


def _engine_label(result) -> str:
    metadata = result.metadata or {}
    provider = metadata.get("provider") or metadata.get("engine")
    model = metadata.get("model")
    if provider and model:
        return f"{provider}:{model}"
    if provider:
        return str(provider)
    return str(metadata.get("mode", "static"))


def build_check_finding_counts(result) -> Dict[str, int]:
    counts: Dict[str, int] = {f"C{index:02d}": 0 for index in range(1, 16)}
    for finding in result.findings or []:
        check_id = str(finding.get("check_id") or "UNSPECIFIED").upper()
        counts[check_id] = counts.get(check_id, 0) + 1
    return counts


def build_check_severity_counts(result) -> Dict[str, Dict[str, int]]:
    severity_counts: Dict[str, Dict[str, int]] = {
        f"C{index:02d}": {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}
        for index in range(1, 16)
    }
    for finding in result.findings or []:
        check_id = str(finding.get("check_id") or "UNSPECIFIED").upper()
        if check_id not in severity_counts:
            severity_counts[check_id] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}
        severity = str(finding.get("severity") or "LOW").upper()
        if severity not in {"HIGH", "MEDIUM", "LOW"}:
            severity = "LOW"
        severity_counts[check_id][severity] += 1
        severity_counts[check_id]["TOTAL"] += 1
    return severity_counts


def build_baseline_submission_fields(result, source: Optional[str] = None) -> Dict[str, Any]:
    summary = result.summary or {}
    checks = result.check_results or {}
    return {
        "Submitted At": datetime.now(timezone.utc).isoformat(),
        "Checks JSON": json.dumps(checks, sort_keys=True),
        "High Count": int((summary.get("by_severity") or {}).get("HIGH", 0)),
        "Medium Count": int((summary.get("by_severity") or {}).get("MEDIUM", 0)),
        "Low Count": int((summary.get("by_severity") or {}).get("LOW", 0)),
        "Total Findings": int(summary.get("findings_total", 0)),
        "Checks Failed": int(summary.get("checks_failed", 0)),
        "Engine": _engine_label(result),
        "Source": infer_research_source(source),
    }


def build_optional_submission_fields(result) -> Dict[str, Any]:
    summary = result.summary or {}
    metadata = result.metadata or {}
    target_kind = "directory"
    try:
        target_kind = "file" if Path(result.target).is_file() else "directory"
    except OSError:
        pass

    fields = {
        "Check Count JSON": json.dumps(build_check_finding_counts(result), sort_keys=True),
        "Check Severity JSON": json.dumps(build_check_severity_counts(result), sort_keys=True),
        "Checks Passed": int(summary.get("checks_passed", 0)),
        "Checks Unknown": int(summary.get("checks_unknown", 0)),
        "Files Scanned": int(summary.get("files_scanned", 0)),
        "Scan Mode": str(metadata.get("mode", "static")),
        "Provider": str(metadata.get("provider") or metadata.get("engine") or "static"),
        "Model": str(metadata.get("model") or ""),
        "Target Kind": target_kind,
    }

    if _env("GITHUB_WORKFLOW"):
        fields["CI Workflow"] = _env("GITHUB_WORKFLOW")
    if _env("GITHUB_RUN_ID"):
        fields["CI Run ID"] = _env("GITHUB_RUN_ID")
    if _env("GITHUB_REF_NAME"):
        fields["CI Ref"] = _env("GITHUB_REF_NAME")

    return fields


def build_aggregate_submission_fields(result, source: Optional[str] = None) -> Dict[str, Any]:
    return {
        **build_baseline_submission_fields(result, source=source),
        **build_optional_submission_fields(result),
    }


def _airtable_url(base_id: str, table: str, query: str = "") -> str:
    url = f"https://api.airtable.com/v0/{parse.quote(base_id)}/{parse.quote(table)}"
    if query:
        return f"{url}?{query}"
    return url


def _decode_error_message(raw: str, exc: error.HTTPError) -> str:
    try:
        parsed = json.loads(raw or "{}")
        err = parsed.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("type") or raw or exc)
        if err:
            return str(err)
    except Exception:
        pass
    return raw or str(exc)


def _airtable_request_json(
    method: str,
    url: str,
    token: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 15,
) -> Dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw or "{}")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ResearchSubmissionError(_decode_error_message(raw, exc), status_code=exc.code) from exc
    except error.URLError as exc:
        raise ResearchSubmissionError(f"Airtable request failed: {exc.reason}") from exc


def _extract_unknown_field(message: str) -> Optional[str]:
    match = UNKNOWN_FIELD_RE.search(message)
    if not match:
        return None
    return match.group("field")


def check_airtable_connection(timeout_seconds: int = 10) -> Dict[str, Any]:
    snapshot = airtable_config_snapshot()
    if not snapshot["configured"]:
        return {
            **snapshot,
            "ok": False,
            "reachable": False,
            "message": "AIRTABLE_BASE_ID and AIRTABLE_TOKEN are not configured.",
        }

    base_id, table, token = _airtable_target()
    assert base_id is not None and token is not None
    url = _airtable_url(base_id, table, query=parse.urlencode({"maxRecords": 1}))

    try:
        _airtable_request_json("GET", url, token, timeout_seconds=timeout_seconds)
        return {
            **snapshot,
            "ok": True,
            "reachable": True,
            "message": "Airtable connection verified.",
        }
    except ResearchSubmissionError as exc:
        return {
            **snapshot,
            "ok": False,
            "reachable": False,
            "message": str(exc),
            "status_code": exc.status_code,
        }


def submit_aggregate_research(result, source: Optional[str] = None, timeout_seconds: int = 15) -> Dict[str, Any]:
    base_id, table, token = _airtable_target()
    if not base_id or not token:
        raise ResearchSubmissionError(
            "AIRTABLE_BASE_ID and AIRTABLE_TOKEN must be configured for research submission."
        )

    baseline_fields = build_baseline_submission_fields(result, source=source)
    optional_fields = build_optional_submission_fields(result)
    dropped_optional_fields = []
    url = _airtable_url(base_id, table)

    while True:
        fields = {**baseline_fields, **optional_fields}
        try:
            response = _airtable_request_json(
                "POST",
                url,
                token,
                payload={"fields": fields},
                timeout_seconds=timeout_seconds,
            )
            response["submitted_fields"] = sorted(fields)
            response["dropped_optional_fields"] = dropped_optional_fields
            return response
        except ResearchSubmissionError as exc:
            unknown_field = _extract_unknown_field(str(exc))
            if exc.status_code != 422 or not unknown_field:
                raise ResearchSubmissionError(f"Airtable submission failed: {exc}", status_code=exc.status_code) from exc
            if unknown_field not in optional_fields:
                raise ResearchSubmissionError(
                    f"Airtable submission failed: required field '{unknown_field}' is missing from the table.",
                    status_code=exc.status_code,
                ) from exc

            optional_fields.pop(unknown_field, None)
            dropped_optional_fields.append(unknown_field)
