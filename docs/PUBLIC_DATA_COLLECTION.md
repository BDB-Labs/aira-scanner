# Public Data Collection

This document describes the curated public-repo collection workflow for AIRA research.

The intended model is:

- the public website highlights the problem
- internal researchers build the canonical dataset
- canonical records come from curated public repos and documented manifests

## Why this exists

Public web users do not necessarily understand the research posture or what a valid study record should contain.

That means the cleanest dataset is usually built from:

- public repositories
- explicit sampling criteria
- explicit attribution policy
- reproducible sample manifests

## Collector workflow

The CLI now includes a manifest-driven collector:

```bash
aira collect ./docs/examples/public-collection.yaml --submit-research-aggregate
```

What it does:

1. Reads a YAML or JSON manifest.
2. Shallow-clones each public repo.
3. Optionally checks out a requested ref.
4. Runs AIRA locally against the clone.
5. Submits aggregate-only results to the configured research backend.
6. If the backend is Supabase, upserts a matching `aira_sample_manifests` row.

## Manifest format

Top-level required fields:

- `sampling_method`
- `sampling_frame`
- `attribution_policy`
- `samples`

Optional top-level fields:

- `inclusion_criteria`
- `exclusion_criteria`
- `random_seed`
- `notes`
- `defaults`

Each sample should include:

- `repo`: `owner/repo` or a git URL

Optional per-sample fields:

- `ref`
- `sample_name`
- `sample_version`
- `attribution_class`
- `source_id`
- `source_kind`
- `notes`

If omitted:

- `sample_name` defaults to `github:owner/repo`
- `sample_version` defaults to the resolved commit SHA
- `source_id` defaults to `owner/repo`
- `source_kind` defaults to `repo`
- `attribution_class` defaults to `unknown`, unless set in `defaults`

## Example

See [examples/public-collection.yaml](./examples/public-collection.yaml).

## Recommended usage

For canonical studies:

- keep public web submission disabled
- use `aira collect` for curated public repos
- store manifests alongside the resulting records
- set `attribution_class` deliberately instead of inferring it loosely
