"""
AIRA JavaScript/TypeScript Checker
Regex and heuristic-based analysis for JS/TS source files.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Finding:
    check_id: str
    check_name: str
    severity: str
    file: str
    line: int
    description: str
    snippet: Optional[str] = None


class JSChecker:
    """
    Analyzes JavaScript/TypeScript source files for AIRA failure patterns.
    Uses regex and structural heuristics (no full AST parse required).
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.source = Path(filepath).read_text(encoding="utf-8", errors="replace")
        self.lines = self.source.splitlines()
        self.findings: List[Finding] = []

    def run(self) -> List[Finding]:
        self._check_broad_exception_suppression()
        self._check_success_integrity()
        self._check_background_tasks()
        self._check_bypass_paths()
        self._check_environment_safety()
        self._check_determinism()
        self._check_confidence_misrepresentation()
        self._check_idempotency()
        self._check_fallback_scatter()
        self._check_audit_integrity()
        self._check_startup_integrity()
        self._check_ambiguous_returns()
        return self.findings

    def _snippet(self, lineno: int) -> str:
        idx = lineno - 1
        return self.lines[idx].strip() if 0 <= idx < len(self.lines) else ""

    def _add(self, check_id, check_name, severity, line, description):
        self.findings.append(Finding(
            check_id=check_id,
            check_name=check_name,
            severity=severity,
            file=self.filepath,
            line=line,
            description=description,
            snippet=self._snippet(line)
        ))

    def _window(self, lineno: int, before: int = 3, after: int = 8) -> str:
        start = max(0, lineno - 1 - before)
        end = min(len(self.lines), lineno + after)
        return "\n".join(self.lines[start:end])

    # ── CHECK 3: Broad Exception Suppression ─────────────────────
    def _check_broad_exception_suppression(self):
        """
        Detects catch blocks that are empty, only console.log, or only comment.
        """
        in_catch = False
        catch_line = 0
        brace_depth = 0
        catch_body_lines = []

        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            stripped = line.strip()

            # Detect catch block start
            catch_match = re.search(r'\bcatch\s*\(', line)
            if catch_match and '{' in line:
                in_catch = True
                catch_line = i + 1
                brace_depth = line.count('{') - line.count('}')
                catch_body_lines = []
                i += 1
                continue

            if in_catch:
                brace_depth += line.count('{') - line.count('}')
                catch_body_lines.append(stripped)
                if brace_depth <= 0:
                    in_catch = False
                    body = " ".join(catch_body_lines)
                    # Empty catch
                    if re.match(r'^\s*\}?\s*$', body) or body.strip() in ("}", ""):
                        self._add("C03", "BROAD EXCEPTION SUPPRESSION", "HIGH",
                                  catch_line, "Empty catch block — exception silently swallowed")
                    # Only console.log / console.error
                    elif re.match(r'^[\s\}]*console\.(log|error|warn)\(.*\)[\s;]*\}?\s*$', body):
                        self._add("C03", "BROAD EXCEPTION SUPPRESSION", "HIGH",
                                  catch_line,
                                  "Catch block only logs — failure semantics lost, no re-throw")
                    # No throw/reject/return error
                    elif not re.search(r'\b(throw|reject|return.*[Ee]rr|return false)\b', body):
                        self._add("C03", "BROAD EXCEPTION SUPPRESSION", "MEDIUM",
                                  catch_line,
                                  "Catch block does not throw or reject — verify failure is intentionally absorbed")
            i += 1

    # ── CHECK 1: Success Integrity ────────────────────────────────
    def _check_success_integrity(self):
        """Detect catch blocks that return success-like values."""
        patterns = [
            (r'return\s+true\s*;', "Catch block returns true — may misrepresent success after failure"),
            (r'return\s+\{\s*(?:success|status|ok)\s*:\s*true', "Catch block returns success object after error"),
            (r'resolve\s*\(\s*(?:true|null|\{\s*(?:success|ok)\s*:\s*true)', "Promise resolved with success value inside catch"),
        ]
        in_catch = False
        catch_line = 0
        brace_depth = 0
        catch_body = []

        for i, line in enumerate(self.lines):
            if re.search(r'\bcatch\s*\(', line) and '{' in line:
                in_catch = True
                catch_line = i + 1
                brace_depth = line.count('{') - line.count('}')
                catch_body = [line]
                continue
            if in_catch:
                brace_depth += line.count('{') - line.count('}')
                catch_body.append(line)
                if brace_depth <= 0:
                    in_catch = False
                    body = "\n".join(catch_body)
                    for pattern, msg in patterns:
                        if re.search(pattern, body, re.IGNORECASE):
                            self._add("C01", "SUCCESS INTEGRITY", "HIGH", catch_line, msg)

    # ── CHECK 8: Unsupervised Background Tasks ────────────────────
    def _check_background_tasks(self):
        patterns = [
            r'setTimeout\s*\(',
            r'setInterval\s*\(',
            r'(?:Promise\.all|Promise\.allSettled|Promise\.race)\s*\(',
            r'new\s+Worker\s*\(',
            r'\.then\s*\([^)]*\)\s*(?:;|$)',  # .then() without .catch()
        ]
        for i, line in enumerate(self.lines, start=1):
            for pattern in patterns:
                if re.search(pattern, line):
                    window = self._window(i)
                    # Flag if no .catch() or try/catch in vicinity
                    if not re.search(r'\.catch\s*\(|try\s*\{', window):
                        self._add("C08", "UNSUPERVISED BACKGROUND TASKS", "MEDIUM",
                                  i, f"Async operation without visible error handler: '{line.strip()}'")
                    break

    # ── CHECK 5: Bypass / Override Paths ─────────────────────────
    def _check_bypass_paths(self):
        bypass_patterns = [
            r'\btestingBypass\b', r'\bskipRouter\b', r'\bforceModelOutput\b',
            r'\ballowDegraded\b', r'\bbypassGovernance\b', r'\bskipValidation\b',
            r'\bskipAudit\b', r'\bdisableChecks\b', r'\bforcePass\b',
            r'\btesting_bypass\b', r'\bskip_validation\b'
        ]
        for i, line in enumerate(self.lines, start=1):
            for pattern in bypass_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self._add("C05", "BYPASS / OVERRIDE PATHS", "HIGH",
                              i, f"Potential governance bypass flag: '{line.strip()}'")

    # ── CHECK 9: Environment-Dependent Safety ─────────────────────
    def _check_environment_safety(self):
        patterns = [
            r'process\.env\.NODE_ENV\s*[!=]==?\s*["\'](?:development|dev|test|staging)',
            r'if\s*\(\s*(?:isDev|isTest|isStaging|debugMode)\b',
            r'(?:skip|disable|bypass)\w*\s*[=:]\s*(?:true|process\.env)',
        ]
        for i, line in enumerate(self.lines, start=1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self._add("C09", "ENVIRONMENT-DEPENDENT SAFETY", "HIGH",
                              i, f"Environment-conditional safety logic: '{line.strip()}'")

    # ── CHECK 11: Deterministic Reasoning Drift ───────────────────
    def _check_determinism(self):
        patterns = [
            r'temperature\s*:\s*(?!0(?:\.0+)?)[0-9]+(?:\.[0-9]+)?',
            r'"temperature"\s*:\s*(?!0(?:\.0+)?)[0-9]+(?:\.[0-9]+)?',
        ]
        for i, line in enumerate(self.lines, start=1):
            for pattern in patterns:
                if re.search(pattern, line):
                    self._add("C11", "DETERMINISTIC REASONING DRIFT", "HIGH",
                              i, f"Non-zero temperature in model call — verify not a commit path: '{line.strip()}'")

    # ── CHECK 13: Confidence Misrepresentation ────────────────────
    def _check_confidence_misrepresentation(self):
        result_fn_pattern = r'(?:function|const|let|var)\s+(\w*(?:predict|assess|evaluate|score|classify|recommend|decide|infer|generate|resolve)\w*)\s*[=(]'
        confidence_terms = r'(?:confidence|isConfident|certainty|isVerified|probability|isCached|isDefault|isEstimated)'

        for i, line in enumerate(self.lines, start=1):
            match = re.search(result_fn_pattern, line, re.IGNORECASE)
            if match:
                fn_name = match.group(1)
                # Look at next 30 lines for confidence metadata
                window_end = min(len(self.lines), i + 30)
                fn_body = "\n".join(self.lines[i:window_end])
                if not re.search(confidence_terms, fn_body, re.IGNORECASE):
                    self._add("C13", "CONFIDENCE MISREPRESENTATION", "MEDIUM",
                              i, f"Function '{fn_name}' appears to return results without confidence metadata")

    # ── CHECK 15: Retry / Idempotency Assumption Drift ───────────
    def _check_idempotency(self):
        retry_patterns = [r'\bretry\b', r'\bbackoff\b', r'for\s*\(.*attempt', r'\.retry\s*\(']
        write_patterns = [r'\b(?:insert|create|write|commit|publish|send|post|charge|submit)\b']
        idempotency_patterns = [r'\bidempotency[_-]?[Kk]ey\b', r'\bidempotent\b', r'\bdedup\b']

        for i, line in enumerate(self.lines, start=1):
            is_retry = any(re.search(p, line, re.IGNORECASE) for p in retry_patterns)
            if not is_retry:
                continue
            window = self._window(i, before=3, after=12)
            has_write = any(re.search(p, window, re.IGNORECASE) for p in write_patterns)
            has_idem = any(re.search(p, window, re.IGNORECASE) for p in idempotency_patterns)
            if has_write and not has_idem:
                self._add("C15", "RETRY / IDEMPOTENCY ASSUMPTION DRIFT", "HIGH",
                          i, f"Retry near write op without idempotency key: '{line.strip()}'")

    # ── CHECK 4: Fallback Scatter ─────────────────────────────────
    def _check_fallback_scatter(self):
        patterns = [r'\bfallback\b', r'\bdegraded\b', r'\bbestEffort\b', r'\bbest_effort\b']
        for i, line in enumerate(self.lines, start=1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self._add("C04", "DISTRIBUTED FALLBACK / DEGRADED EXECUTION", "LOW",
                              i, f"Fallback/degraded logic — verify centralized governance: '{line.strip()}'")

    # ── CHECK 2: Audit / Evidence Integrity ──────────────────────
    def _check_audit_integrity(self):
        audit_terms = r'(?:audit|evidence|logEvent|writeAudit|recordEvent|flushAudit)'
        for i, line in enumerate(self.lines, start=1):
            if re.search(audit_terms, line, re.IGNORECASE):
                window = self._window(i, before=2, after=6)
                if re.search(r'\bcatch\b', window) and not re.search(r'\bthrow\b', window):
                    self._add("C02", "AUDIT / EVIDENCE INTEGRITY", "HIGH",
                              i, f"Audit operation in try block with non-throwing catch — evidence loss possible: '{line.strip()}'")

    # ── CHECK 10: Startup Integrity ───────────────────────────────
    def _check_startup_integrity(self):
        startup_pattern = r'(?:function|const|async function)\s+\w*(?:init|startup|bootstrap|setup|onStart)\w*'
        for i, line in enumerate(self.lines, start=1):
            if re.search(startup_pattern, line, re.IGNORECASE):
                window_end = min(len(self.lines), i + 30)
                fn_body = "\n".join(self.lines[i:window_end])
                if re.search(r'\bcatch\b', fn_body) and not re.search(r'\b(?:throw|process\.exit)\b', fn_body):
                    self._add("C10", "STARTUP INTEGRITY", "HIGH",
                              i, f"Startup function catches exception without halting: '{line.strip()}'")

    # ── CHECK 6: Ambiguous Return Contracts ───────────────────────
    def _check_ambiguous_returns(self):
        """Flag functions with multiple return null/undefined/false in different contexts."""
        fn_pattern = r'(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))'
        null_return = r'\breturn\s+(?:null|undefined|false)\s*;'

        for i, line in enumerate(self.lines, start=1):
            if re.search(fn_pattern, line):
                window_end = min(len(self.lines), i + 40)
                fn_body = "\n".join(self.lines[i:window_end])
                null_returns = re.findall(null_return, fn_body)
                if len(null_returns) >= 2:
                    self._add("C06", "AMBIGUOUS RETURN CONTRACTS", "MEDIUM",
                              i, f"Function returns null/undefined/false in {len(null_returns)} locations — "
                                 "caller may not distinguish failure vs absence vs disabled")
