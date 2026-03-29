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
# Static scan a directory (terminal output)
aira scan ./my-project

# Hybrid scan using your local/model provider configuration
aira scan ./my-project --engine hybrid

# LLM-only scan against a local OpenAI-compatible endpoint
aira scan ./my-project --engine llm --provider openai-compatible --base-url http://localhost:1234/v1 --model gpt-oss-120b

# Health check provider wiring
aira health

# List supported providers and env vars
aira providers

# Scan with YAML report
aira scan ./my-project --output yaml

# Scan with JSON report (for CI/CD integration)
aira scan ./my-project --output json --out-file report.json

# Exclude directories
aira scan ./my-project --exclude node_modules,dist,build

# Fail on MEDIUM or above instead of only HIGH
aira scan ./my-project --fail-on medium

# Submit aggregate-only results to Airtable for the research study
aira scan ./my-project --output json --submit-research-aggregate

# Verify Airtable connectivity without writing a record
aira health --check-airtable
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

## Provider Modes

AIRA CLI supports:

- `static`: deterministic built-in analysis only
- `llm`: provider-assisted analysis only
- `hybrid`: merge static and LLM findings

Provider routing is local-first:

1. OpenAI-compatible local endpoint
2. Ollama
3. Groq
4. Gemini
5. OpenRouter

Useful environment variables:

```bash
# OpenAI-compatible local or hosted endpoint
export AIRA_OPENAI_BASE_URL="http://localhost:1234/v1"
export AIRA_OPENAI_MODEL="gpt-oss-120b"

# Ollama
export AIRA_OLLAMA_MODEL="qwen3:32b"
export AIRA_OLLAMA_HOST="http://127.0.0.1:11434"

# Groq
export GROQ_API_KEY="..."
export GROQ_MODEL="your-provider-model-id"

# Airtable research submission
export AIRTABLE_BASE_ID="app..."
export AIRTABLE_TABLE="Submissions"
export AIRTABLE_TOKEN="pat..."
```

## Research Submission

The CLI can submit **aggregate-only** study data to Airtable:

```bash
aira scan . --output json --submit-research-aggregate
```

What is sent:

- AIRA check statuses
- severity totals
- total findings
- failed/passed/unknown check counts
- per-check finding counts
- scan mode / provider / model metadata
- CI metadata when available

What is **not** sent:

- source code
- file paths from findings
- snippets
- raw file contents

### Airtable table format

The CLI is compatible with the current minimal Airtable schema already implied by the web app proxy:

- `Submitted At`
- `Checks JSON`
- `High Count`
- `Medium Count`
- `Low Count`
- `Total Findings`
- `Checks Failed`
- `Engine`
- `Source`

If your Airtable table also includes richer optional fields, AIRA will populate them when present:

- `Check Count JSON`
- `Checks Passed`
- `Checks Unknown`
- `Files Scanned`
- `Scan Mode`
- `Provider`
- `Model`
- `Target Kind`
- `CI Workflow`
- `CI Run ID`
- `CI Ref`

If one of those optional fields does not exist in Airtable yet, the CLI drops it and retries instead of failing the entire submission.

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
