# AIRA Scanner — AI-Induced Risk Audit

**Version 1.2.0**  
*Bagelle Parris Vargas Consulting | bageltech.net*  
*Jurisprudential AI Governance Initiative*

---

## What Is This?

AIRA is a static analysis tool that detects a specific class of failure modes in AI-generated or AI-assisted code — failure modes that are **not random**, but **systematically produced by training incentives**.

The core claim:

> AI coding agents are reward-shaped toward human approval signals. Visible failure is a strong negative signal. Therefore, AI-generated code will systematically suppress, absorb, or reroute failure states — not from incompetence, but from incentive alignment.

AIRA implements 15 checks derived from empirical observation of these patterns across real AI-assisted codebases. Two checks (C07, C12) require human review; 13 are fully automated.

---

## Installation

```bash
pip install aira-scanner
```

**Requirements:** Python 3.9+, PyYAML

---

## Usage

### CLI

```bash
# Scan a directory (terminal output)
aira scan ./my-project

# Scan with YAML report
aira scan ./my-project --output yaml

# Scan with JSON report (for CI/CD integration)
aira scan ./my-project --output json --out-file report.json

# Exclude directories
aira scan ./my-project --exclude node_modules,dist,build
```

### VS Code Extension

Install from the VS Code Marketplace (search "AIRA Scanner") or from the `.vsix` file.

- Right-click any file or folder → **AIRA: Scan**
- Command palette → **AIRA: Scan Workspace** or **AIRA: Scan Current File**
- Findings appear in the **Problems** panel with severity markers

---

## The 15 AIRA Checks

| ID  | Check | Automatable |
|-----|-------|-------------|
| C01 | Success Integrity | ✓ |
| C02 | Audit / Evidence Integrity | ✓ |
| C03 | Broad Exception Suppression | ✓ |
| C04 | Distributed Fallback / Degraded Execution | ✓ (partial) |
| C05 | Bypass / Override Paths | ✓ |
| C06 | Ambiguous Return Contracts | ✓ |
| C07 | Parallel Logic Drift | Human review |
| C08 | Unsupervised Background Tasks | ✓ |
| C09 | Environment-Dependent Safety | ✓ |
| C10 | Startup Integrity | ✓ |
| C11 | Deterministic Reasoning Drift | ✓ |
| C12 | Source-to-Output Lineage | Human review |
| C13 | Confidence Misrepresentation | ✓ |
| C14 | Test Coverage Asymmetry | ✓ |
| C15 | Retry / Idempotency Assumption Drift | ✓ |

---

## Supported Languages

- Python (.py)
- JavaScript (.js, .mjs, .cjs)
- TypeScript (.ts)
- JSX/TSX (.jsx, .tsx)

---

## Output Format

AIRA produces structured YAML or JSON conforming to the AIRA v1.2 specification:

```yaml
aira_scan:
  version: "1.2"
  target: /path/to/project
  scanned_at: 2026-03-27T...
  summary:
    files_scanned: 48
    findings_total: 12
    by_severity:
      HIGH: 4
      MEDIUM: 6
      LOW: 2
  ai_failure_audit:
    success_integrity: FAIL
    exception_handling: FAIL
    # ... all 15 checks
  findings:
    - check_id: C03
      check_name: BROAD EXCEPTION SUPPRESSION
      severity: HIGH
      file: src/governance.py
      line: 142
      description: "Broad exception handler that logs but does not re-raise..."
      snippet: "except Exception as e:"
```

---

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run AIRA scan
  run: |
    pip install aira-scanner
    aira scan . --output json --out-file aira-report.json
  # Exit code 1 if HIGH severity findings found
```

---

## Research Data

AIRA was developed as part of the **Jurisprudential AI Governance Initiative** to empirically characterize training-induced failure patterns in AI-generated code. If you run AIRA on your codebase and would like to contribute anonymized findings to the research dataset, contact: **bill@bageltech.net**

---

## Citation

If you use AIRA in research or tooling, please cite:

> Parris, W.M. (2026). *AIRA: AI-Induced Risk Audit — A Structured Inspection Framework for AI-Generated Code Failure Patterns*. Bagelle Parris Vargas Consulting / Jurisprudential AI Governance Initiative.

---

## License

MIT License — Copyright © 2026 William M. Parris / Bagelle Parris Vargas Consulting
