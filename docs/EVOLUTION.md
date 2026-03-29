# AIRA Scanner Evolution

This document explains how AIRA Scanner evolved from its earliest form into the current web-plus-CLI research tool.

It exists for two reasons:

- to help new readers understand that the scanner did not appear fully formed
- to make the methodological shifts explicit, especially the move from heuristics and hosted inference toward a more disciplined deterministic backbone

## 1. Original Thesis

AIRA began from a research hypothesis, not from a generic desire to lint code.

The motivating question was:

> When a software system fails, does it report that failure honestly, or does it preserve the appearance of success?

The project was shaped by a deeper claim:

- some failure-concealment patterns in AI-assisted code are not random bugs
- they may be recurring artifacts of training and approval-shaped optimization
- those patterns are especially dangerous in governance, audit, safety, and assurance-sensitive systems

From the start, AIRA was intended to surface those patterns in a measurable way.

## 2. Earliest Form: Web Prototype

The earliest repository form was a browser-first scanner:

- a single-page web application
- an emphasis on the AIRA framework and the 15 checks
- lightweight scanning behavior intended to demonstrate the concept quickly

At that stage, the project was valuable as a framing device and public artifact, but it was still closer to a prototype than a disciplined measurement system.

## 3. API-Connected Web Scanner

The next major step was adding a server-side API-backed scan route.

That changed the scanner from:

- a mostly browser-driven demonstration

into:

- a web app that could route structured prompts through a server-side model connector

This made the scanner more useful on real code, but it also introduced new reliability questions:

- what happens when the provider is unavailable?
- what happens when the model output is too optimistic?
- what happens when quotas or rate limits make the public scanner unreliable?

## 4. Heuristic Fallbacks

To keep the public scanner usable, heuristic fallbacks were added.

This was an important transitional step:

- the scanner could continue working when LLM access failed
- users were not left with a blank or broken interface
- the project started to formalize the difference between “best-effort public scan” and “serious audit signal”

But heuristic-only scanning also made the limits of the system clearer. Regex-style detection is useful for triage, but it is not enough by itself for a credible research instrument.

## 5. Routed Provider Support

The scanner then grew beyond a single provider path.

Server-side routing and health surfaces were added so AIRA could:

- try multiple providers
- expose whether a provider was actually configured
- distinguish cloud-assisted results from deterministic fallbacks

This reduced fragility and made the system more honest about how each result was produced.

## 6. CLI And Local-First Expansion

The project changed materially once the CLI was added.

That was the point where AIRA stopped being only a web interface and became:

- a scanner that could run on repos directly
- a tool that fit into CI and local developer workflows
- a system that could plug into existing local inference setups

The CLI also clarified an important design principle:

- AIRA should not force one hosted provider path
- users should be able to run it statically, with local endpoints, or through Ollama

## 7. Research Collection And Schema Refinement

Once the scanner started producing useful results, the research sink became a real issue.

The repository first supported Airtable because it was quick to stand up, but the research needs became more demanding:

- overall severity totals were not enough
- the study needed to know which of the 15 checks failed
- it also needed counts by severity within each check

That requirement drove the richer aggregate payload shape:

- check status map
- per-check finding counts
- per-check severity matrix
- scan mode and provider metadata

The hosted research path later shifted toward Supabase, with JSONL support for local and CI collection.

## 8. Deterministic Static Analysis Becomes The Backbone

This was the most important methodological shift in the repo.

The scanner moved from:

- “LLM scan plus heuristic fallback”

toward:

- “deterministic scan as the backbone, with LLMs as optional augmentation”

That change happened because:

- public cloud availability is uneven
- rate limits make hosted-only scanning fragile
- repo-scale LLM audits can become overly smooth or optimistic
- deterministic rules are easier to inspect, reproduce, and benchmark

The current architecture reflects that shift clearly:

- parser-backed deterministic analysis for Python
- parser-backed JavaScript analysis when `esprima` is available
- web static-scan route for server-side deterministic fallback
- browser heuristics as the last-resort fallback, not the primary engine

## 9. Ollama As The Clean Abstraction Layer

Another important evolution was the move toward Ollama as a stable model abstraction layer.

Instead of teaching AIRA about every cloud model vendor individually, the scanner now treats Ollama as a generic interface:

- discover available models
- validate the selected model
- pass prompts and parse structured results

That allows the same scanner surface to work with:

- fully local models
- local wrappers around remote models
- cloud-backed Ollama offerings

without making the scanner itself vendor-dependent.

## 10. Current Shape

Today the repository is best understood as four connected systems:

1. A public web scanner
2. A CLI for local and CI usage
3. A deterministic rule engine that anchors the research posture
4. A research collection path for aggregate-only study data

That is materially different from the original prototype.

## 11. What Still Is Not Finished

AIRA is more coherent than it was, but it is not complete.

Open work still includes:

- benchmark corpora and reproducible fixture packs
- richer rule documentation and calibration notes
- stronger repo-level and cross-file reasoning
- more formal methodology and validation writeups
- broader sample outputs and comparison datasets

## 12. The Important Through-Line

The strongest continuity across the repo’s evolution is this:

- AIRA is not trying to prove code correctness
- it is trying to surface truthfulness failures under error, degradation, and uncertainty

Everything in the repository now makes more sense when read through that lens.
