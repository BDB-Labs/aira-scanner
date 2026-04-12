"""
Deterministic inline scan helpers for server-side fallback routes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from aira.scanner import AIRAScanner

try:
    import esprima  # type: ignore
except ImportError:  # pragma: no cover - optional parser dependency
    esprima = None


LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
}


def _metadata_for_language(lang: str) -> Dict[str, Any]:
    normalized = (lang or "").lower()
    if normalized == "python":
        return {
            "engine": "deterministic-static",
            "engine_label": "Deterministic parser-backed scan",
            "note": "Server-side deterministic scan using Python AST-backed rules.",
            "parser_backed": True,
        }
    if normalized == "javascript":
        return {
            "engine": "deterministic-static",
            "engine_label": "Deterministic parser-backed scan" if esprima is not None else "Deterministic static scan",
            "note": "Server-side deterministic scan using JavaScript AST-backed rules." if esprima is not None else "Server-side deterministic scan using structured JavaScript checks.",
            "parser_backed": esprima is not None,
        }
    if normalized == "typescript":
        return {
            "engine": "deterministic-static",
            "engine_label": "Deterministic static scan",
            "note": "Server-side deterministic scan using structured TypeScript checks.",
            "parser_backed": False,
        }
    return {
        "engine": "deterministic-static",
        "engine_label": "Deterministic static scan",
        "note": "Server-side deterministic scan using static AIRA rules.",
        "parser_backed": False,
    }


def scan_inline_source(code: str, lang: str) -> Dict[str, Any]:
    normalized_lang = (lang or "").lower()
    extension = LANGUAGE_EXTENSIONS.get(normalized_lang)
    if not extension:
        raise ValueError(f"Unsupported language for deterministic scan: {lang}")

    with tempfile.TemporaryDirectory(prefix="aira-static-") as tmpdir:
        target = Path(tmpdir) / f"snippet{extension}"
        target.write_text(code, encoding="utf-8")
        result = AIRAScanner(str(target)).scan(mode="static")

    return {
        "checks": result.check_results,
        "findings": [
            {
                "check_id": finding["check_id"],
                "check_name": finding["check_name"],
                "severity": finding["severity"],
                "line": finding["line"],
                "description": finding["description"],
                "snippet": finding["snippet"],
            }
            for finding in result.findings
        ],
        "summary": {
            "high": int((result.summary.get("by_severity") or {}).get("HIGH", 0)),
            "medium": int((result.summary.get("by_severity") or {}).get("MEDIUM", 0)),
            "low": int((result.summary.get("by_severity") or {}).get("LOW", 0)),
            "total": int(result.summary.get("findings_total", 0)),
            "files_scanned": int(result.summary.get("files_scanned", 0)),
        },
        "meta": {
            **_metadata_for_language(normalized_lang),
            "language": normalized_lang,
        },
    }
