# AIRA Scanner

**AI-Induced Risk Audit (AIRA)**
Detecting fail-soft patterns in modern software systems

---

## Overview

AIRA Scanner is a research tool for detecting fail-soft patterns in software systems, especially those developed with significant AI assistance.

These patterns include cases where systems:

* return success despite incomplete or failed operations
* degrade silently instead of failing explicitly
* obscure true system state under error conditions
* preserve the appearance of function while weakening actual guarantees

These behaviors are not always treated as conventional defects. But in reliability, governance, audit, and safety-sensitive systems, they directly affect trustworthiness.

---

## About

AIRA is a research initiative developed by **BDB Labs**.
Project homepage: **https://aira.bageltech.net**

The scanner exists to help identify a class of software risks that are often missed by traditional linting, style enforcement, and happy-path testing.

---

## Why this exists

Traditional software validation asks:

> “Does the system work?”

AIRA asks:

> **“Does the system tell the truth when it fails?”**

AIRA is designed to detect patterns where systems continue, degrade, or signal success in ways that may conceal broken guarantees.

---

## Research Direction

AIRA is motivated by the hypothesis that modern codebases—particularly those developed with significant AI assistance—may exhibit recurring fail-soft patterns such as:

* broad exception suppression
* distributed fallback logic
* ambiguous return contracts
* optimistic success signaling
* silent degradation of guarantees

This tool is intended to **measure and surface these patterns**, not to presume universal cause or make claims beyond the available evidence.

---

## What AIRA looks for

AIRA currently focuses on patterns such as:

* success integrity violations
* audit and evidence integrity gaps
* broad exception suppression
* distributed fallback and degraded execution
* bypass and override paths
* ambiguous return contracts
* parallel logic drift
* unsupervised background tasks
* environment-dependent safety drift
* startup integrity weaknesses
* deterministic reasoning drift
* source-to-output lineage gaps
* confidence misrepresentation
* failure-path test asymmetry
* retry and idempotency assumption drift

---

## Status

Early-stage research tool.
Initial scanner and rule set are live.
Empirical datasets and expanded detection rules are in progress.

---

## Runtime Notes

The scanner currently supports:

* `Auto` mode: routes through Groq first, then configured fallbacks
* deterministic static scanning through `/api/static-scan`
* optional cloud providers:

  * `GROQ_API_KEY` with optional `GROQ_MODEL`
  * `GEMINI_API_KEY` or `GOOGLE_API_KEY` with optional `GEMINI_MODEL`
  * `OPENROUTER_API_KEY` with `OPENROUTER_MODEL`
* browser heuristic fallback for local deterministic triage when both cloud routing and server-side static scanning are unavailable
* research submission through a server-side Airtable proxy when:

  * `AIRTABLE_BASE_ID`
  * `AIRTABLE_TABLE`
  * `AIRTABLE_TOKEN`
    are configured
* CLI/CI aggregate-only submission to Airtable with `aira scan --submit-research-aggregate`
* read-only CLI Airtable verification with `aira health --check-airtable`
* direct web Airtable verification with `/api/airtable-health`

No Airtable token is exposed in the browser.

### Recommended zero-cost setup

For the current public scanner, the recommended path is:

* set `GROQ_API_KEY`
* optionally set `GROQ_MODEL`
* leave the UI on `Auto`

That gives AIRA a free structured-output cloud path with the browser heuristic scanner still available as the final fallback.

### Quick health check

To confirm Groq is wired without running a full scan:

```bash
curl http://localhost:3000/api/health
```

Or after deployment:

```bash
curl https://your-domain.example/api/health
```

You should see `groq` listed under `configured_providers` when `GROQ_API_KEY` is set.

To verify Airtable specifically:

```bash
curl https://your-domain.example/api/airtable-health
```

The recommended Airtable table layout is documented in [AIRTABLE_SCHEMA.md](/Users/billp/Documents/GitHub/aira-scanner/AIRTABLE_SCHEMA.md).

To probe the deterministic static scan route directly:

```bash
curl -X POST https://your-domain.example/api/static-scan \
  -H "Content-Type: application/json" \
  -d '{"lang":"python","code":"def ok():\n    return True\n"}'
```

---

## Project Philosophy

AIRA is not primarily a bug detector.

It is a **truthfulness detector for software under failure**.

Its purpose is not to eliminate defects, but to identify conditions where defects can silently alter a system’s representation of its own correctness.

---

## Current Scope

AIRA should currently be understood as:

* a research scanner
* an evolving inspection framework
* a measurement tool for fail-soft behavior

It should not yet be treated as:

* a formal verifier
* a complete security audit
* a substitute for runtime testing or human review

---

## Contributing

Contributions are welcome, especially in these areas:

* new detection rules
* false-positive and false-negative reduction
* comparative scans across AI-assisted and non-AI-assisted codebases
* documentation improvements
* datasets and benchmark cases

---

## Repository Hygiene Roadmap

Short-term repo improvements include:

* formal contribution guidelines
* versioned changelog
* methodology documentation
* sample scan outputs
* benchmark datasets
* rule documentation

---

## Final Note

AIRA is based on a simple but demanding question:

> **When a system fails, does it reveal that failure honestly—or does it preserve the appearance of success?**
