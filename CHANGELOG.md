# Changelog

All notable changes to AIRA Scanner will be documented here.

## [Unreleased]

- Added a documentation pack for scanner history, methodology, and formal check definitions
- Linked the new docs from the repository front door so the scanner's evolution is easier to reconstruct
- Added Supabase research schema v2 with append-only submission streams, normalized submission checks, and FTI-v1 scoring
- Disabled hosted public research writes by default so canonical records stay in internal curated CLI/CI workflows
- Added a manifest-driven `aira collect` workflow for curated public-repo dataset collection

## [v1.2.0] - 2026-03-29

This is the first version where the repository is coherent as a research instrument rather than only a web prototype.

- Formalized the scanner around the AIRA v1.2 check contract
- Added the CLI as a first-class interface for local, CI, and research use
- Added local-first provider routing for OpenAI-compatible endpoints, Ollama, Groq, Gemini, and OpenRouter
- Added provider health checks and Ollama model discovery / validation
- Added aggregate-only research submission from CLI and web
- Added richer research payloads including per-check counts and per-check severity matrices
- Added Airtable health checking and compatibility fallback behavior
- Added Supabase and JSONL research backends, making Supabase the preferred hosted path
- Added parser-backed deterministic static scanning, making static analysis the canonical non-LLM baseline
- Added a deterministic server-side static scan route for the web app

## [Pre-v1.2 Evolution]

### Browser Prototype

- Started as a mostly front-end scanner with a single-page web interface
- Focused on communicating the AIRA thesis and making the 15 checks legible
- Relied heavily on browser-side heuristics

### Server-Side API Connector

- Added an API-backed scan route so the web app could call structured LLM providers
- Preserved the original web experience while making the scanner more useful on real code

### Heuristic Safety Net

- Added a heuristic fallback so the public scanner remained usable under quota, outage, or configuration failure
- Established the principle that AIRA should still produce triage output even when the cloud path is unavailable

### Routed Providers And Health Surfaces

- Added routed cloud failover and provider health endpoints
- Improved visibility into whether the scanner was actually using an LLM or falling back

### CLI And Local-First Operation

- Added the CLI implementation
- Expanded the scanner so it could run on local files, whole repos, and CI targets
- Added support for local OpenAI-compatible endpoints and Ollama, not just hosted providers

### Research Data Collection

- Added aggregate-only research submission and schema documentation
- Started with Airtable compatibility because it was easy to stand up quickly
- Evolved toward richer per-check severity data as the research needs became clearer

### Deterministic Backbone

- Added parser-backed deterministic static scanning for Python and JavaScript
- Shifted the scanner architecture so deterministic analysis became the backbone and LLMs became optional augmentation

### Research Backend Maturation

- Added Supabase and JSONL as serious research sinks
- Repositioned Airtable as a legacy compatibility fallback rather than the preferred destination

### Ollama As A Stable Abstraction Layer

- Added Ollama model discovery and validation
- Clarified that AIRA should integrate with Ollama as an abstraction layer, regardless of whether the selected model is local or cloud-backed
