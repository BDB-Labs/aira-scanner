# Airtable Research Schema

Create the base and table:

1. Create a base named `AIRA Research`
2. Rename the default table to `Submissions`

## Recommended Fields

Paste this into Airtable as your setup checklist:

| Field Name | Field Type | Notes |
| --- | --- | --- |
| Submitted At | Date | Include time |
| Language | Single line text | Optional; web scanner sends selected language |
| High Count | Number | Required |
| Medium Count | Number | Required |
| Low Count | Number | Required |
| Total Findings | Number | Required |
| Checks Failed | Number | Required |
| Checks Passed | Number | Optional |
| Checks Unknown | Number | Optional |
| Checks JSON | Long text | Required; check status map |
| Check Count JSON | Long text | Optional; total findings per AIRA check |
| Check Severity JSON | Long text | Optional; per-check `HIGH/MEDIUM/LOW/TOTAL` matrix |
| Files Scanned | Number | Optional |
| Scan Mode | Single line text | Optional |
| Engine | Single line text | Required |
| Provider | Single line text | Optional |
| Model | Single line text | Optional |
| Target Kind | Single line text | Optional |
| Source | Single line text | Required |
| CI Workflow | Single line text | Optional |
| CI Run ID | Single line text | Optional |
| CI Ref | Single line text | Optional |

## Why `Check Severity JSON` Matters

The existing minimal schema can tell you:

- how many findings existed overall
- how many checks failed

It cannot tell you:

- which of the 15 checks generated the findings
- how severe those findings were within each check

`Check Severity JSON` solves that.

## Example `Checks JSON`

```json
{
  "success_integrity": "FAIL",
  "audit_integrity": "PASS",
  "exception_handling": "FAIL",
  "fallback_control": "PASS",
  "bypass_controls": "UNKNOWN"
}
```

## Example `Check Count JSON`

```json
{
  "C01": 13,
  "C02": 0,
  "C03": 4,
  "C04": 1,
  "C05": 0
}
```

## Example `Check Severity JSON`

```json
{
  "C01": { "HIGH": 6, "MEDIUM": 2, "LOW": 5, "TOTAL": 13 },
  "C02": { "HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0 },
  "C03": { "HIGH": 3, "MEDIUM": 1, "LOW": 0, "TOTAL": 4 },
  "C04": { "HIGH": 0, "MEDIUM": 1, "LOW": 0, "TOTAL": 1 }
}
```

This is the field that lets you answer questions like:

- Which checks dominate the failure profile?
- Is `C01` mostly `HIGH` severity or mostly `LOW` severity?
- Are AI-heavy repos over-indexing on `C03` or `C04`?

## Backward Compatibility

The current web and CLI submitters are backward-compatible with the smaller schema. If Airtable does not have one of the optional fields above, AIRA drops it and retries instead of failing the whole submission.

That means you can start with the minimal required fields and add the richer fields later. But for the research study, `Check Severity JSON` is strongly recommended.
