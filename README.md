# AIRA Scanner

**AI-Induced Risk Audit (AIRA)**  
Detecting fail-soft patterns in modern software systems

---

## Overview

AIRA Scanner is a research tool designed to identify patterns where systems:

- return success despite incomplete or failed operations  
- degrade silently instead of failing explicitly  
- obscure true system state under error conditions  

These patterns are not always treated as defects—but they directly impact system trustworthiness.

---

## Why this exists

Traditional software validation asks:

> “Does the system work?”

AIRA asks:

> **“Does the system tell the truth when it fails?”**

---

## Research Direction

We are investigating whether modern codebases—particularly those developed with AI assistance—exhibit consistent “fail-soft” patterns such as:

- broad exception suppression  
- distributed fallback logic  
- ambiguous return contracts  
- optimistic success signaling  

This tool is intended to **measure and surface these patterns**, not to assume their cause.

---

## Status

Early-stage research tool.  
Initial dataset included.  
Actively collecting additional results.

## Runtime Notes

The scanner now supports:

- `Auto` mode: uses the server-side Gemini proxy when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is configured
- `Local heuristic` fallback: browser-only deterministic checks when the model proxy is unavailable
- research submission through a server-side Airtable proxy when `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE`, and `AIRTABLE_TOKEN` are configured

No Airtable token is exposed in the browser.
