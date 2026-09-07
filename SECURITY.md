# Security and fitment safety policy

`moto-fitment-engine` processes motorcycle fitment and tyre-catalog data. Incorrect data can create a physical-safety risk even when the software itself has no conventional security vulnerability, so this project treats data provenance and compatibility claims as part of its security boundary.

## Supported code

Security fixes are applied to the current `main` branch. Until a stable release line is published, older commits and copied example datasets should be treated as unsupported.

## Report a vulnerability

Please use GitHub's private vulnerability reporting feature for this repository when available. Do not open a public issue for a report that includes an exploitable security weakness, leaked credential, sensitive production data, or a reproducible path to unsafe fitment output.

A useful report should include:

- affected commit or release;
- minimal reproduction steps;
- expected versus actual behavior;
- security or physical-safety impact;
- whether the issue depends on untrusted input or a specific dataset.

Do not include real customer, supplier, credential, or private inventory data in reports.

## Safety-sensitive behavior

The engine intentionally fails closed in production-oriented flows. A result must not be described as vehicle-compatible solely because tyre geometry is close to the OEM size.

Before a candidate can be treated as a real fitment recommendation, the application using this library must validate the relevant manufacturer requirements, including as applicable:

- load index;
- speed rating;
- approved rim-width range;
- physical clearance;
- front/rear construction and fitment restrictions;
- ABS/TCS and rolling-circumference constraints;
- homologation and market-specific requirements;
- manufacturer service information or other authoritative fitment data.

The current geometry-screening APIs are deliberately narrower than a compatibility guarantee. Missing safety metadata must not be interpreted as approval.

## Fitment data provenance

Production datasets should use `load_fitments_json()` and retain verifiable provenance. The loader requires an HTTPS source URL and verification date and rejects malformed, overlapping, undocumented, or structurally unexpected records.

When updating fitment data:

1. Prefer manufacturer or other authoritative primary documentation.
2. Record the exact source URL and verification date.
3. Do not copy unverified marketplace, forum, or generated values into the verified dataset.
4. Keep demo/example records clearly separated from production-verified records.
5. Re-run the full test suite and CI before publishing the change.

## Secrets and configuration

This repository should not contain API tokens, supplier credentials, private catalog exports, customer information, or production database dumps. Examples must use synthetic data and HTTPS placeholder URLs.

If a secret is committed, revoke or rotate it first; deleting it from a later commit is not sufficient because Git history may retain the value.

## Dependency and CI changes

Dependency and GitHub Actions upgrades should be reviewed for breaking changes and runner requirements before merge. Major-version automation updates must not be auto-merged solely because Dependabot opened them.

## Scope note

A fitment-data error that can cause an unsafe recommendation is worth reporting even if it would not normally be classified as a software-security vulnerability. Provide the smallest reproducible case and the authoritative source that contradicts the result.