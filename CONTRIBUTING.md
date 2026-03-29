# Contributing to AIRA Scanner

Thank you for contributing to AIRA Scanner.

AIRA is an early-stage research tool focused on detecting fail-soft patterns in modern software systems, especially AI-assisted codebases. Contributions should prioritize clarity, reproducibility, and disciplined claims over novelty for its own sake.

## Ways to contribute

We especially welcome contributions in the following areas:

- detection rule improvements
- false-positive and false-negative reduction
- scanner output clarity
- comparative scan datasets
- documentation and methodology refinement
- benchmark repos and fixtures

## Contribution principles

Please keep these principles in mind:

- **Do not overclaim.** AIRA is a measurement tool, not a proof engine.
- **Prefer explicitness.** If a rule is heuristic, label it as heuristic.
- **Favor reproducibility.** New findings should be testable or inspectable.
- **Preserve credibility.** Research tone matters as much as code quality here.

## Pull requests

When submitting a pull request, please include:

- a short summary of the change
- the reason for the change
- any expected impact on findings
- any known false-positive or false-negative implications

## Detection rules

If you add or change a detection rule, please include:

- the risk pattern being targeted
- why it matters
- example code before/after if relevant
- whether the rule is deterministic or heuristic

## Datasets and examples

If you contribute scan outputs or benchmark examples:

- remove anything sensitive
- note whether the target codebase was AI-assisted, human-authored, or unknown
- avoid making causal claims that the data does not support

## Research posture

AIRA is investigating whether fail-soft patterns appear with meaningful regularity in modern codebases, particularly AI-assisted ones.

Please frame contributions accordingly:

- “observed”
- “measured”
- “suggests”
- “may indicate”

Avoid language like:

- “proves”
- “all AI-generated code”
- “universal”

## Questions

For major structural changes, open an issue first so the repo can evolve coherently.
