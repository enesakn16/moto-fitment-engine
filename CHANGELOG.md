# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows Semantic Versioning for published releases.

## [0.1.0] - 2026-09-12

### Added

- Verified `make + model + year` motorcycle tyre fitment lookup backed by source-traceable JSON records.
- Strict supplier CSV ingestion with required-field validation, case-insensitive duplicate-SKU detection, stock and price validation, and explicit row-number errors.
- Metric tyre-size parsing and geometry helpers for overall diameter, circumference, width and signed diameter deltas.
- Conservative front/rear alternative screening that rejects rim-diameter mismatches and applies explicit width and diameter tolerances.
- Parsing and enforcement of unambiguous tyre service descriptions, including OEM minimum load-index and speed-capability checks when those thresholds are present in verified fitment data.
- Inventory-aware and geometry-first catalog ranking with deterministic tie-breaking and exact-money JSON serialization.
- File-backed orchestration API through `resolve_catalog_fitment_from_files()` for back-office, API and frontend integrations.
- Installable `moto-fitment` CLI for querying verified fitments against supplier catalogs from the terminal.
- Automated unit and end-to-end coverage for fitment loading, supplier ingestion, safety screening, ranking, orchestration and CLI argument handling.
- GitHub Actions CI on Python 3.11 and 3.13, including installed-package and console-entry-point smoke tests outside the source tree.

### Safety

- Production-loaded fitment records require traceable HTTPS provenance and a non-future verification date.
- Malformed, ambiguous, duplicated or unsupported safety-critical data fails closed instead of being silently accepted.
- Caller-supplied options cannot weaken stricter OEM load/speed minimums contained in the verified dataset.
- A returned alternative is an engine-screened candidate, not a manufacturer approval or guaranteed physical fitment. Rim-width approval, physical clearance, ABS/TCS behavior, construction restrictions, homologation and market/model-specific variants still require authoritative verification.

### Known limitations

- The bundled verified dataset is intentionally limited rather than pretending to provide broad unsupported vehicle coverage.
- Rim-width compatibility, suspension/fender clearance, ABS/TCS calibration and homologation are not yet modeled as first-class constraints.
- No hosted HTTP API or public demo is included in this release; the supported interfaces are the Python API and installed CLI.

[0.1.0]: https://github.com/enesakn16/moto-fitment-engine/releases/tag/v0.1.0
