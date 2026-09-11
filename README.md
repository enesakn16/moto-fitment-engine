# Moto Fitment Engine

Motorcycle tyre fitment lookup, verified OEM sizing, conservative alternative screening and commerce-ready catalog ranking for marketplaces, parts catalogs and workshop software.

[![Python CI](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml)

The engine resolves **make + model + year → verified front/rear OEM tyre sizes**, imports supplier catalog rows, screens alternatives conservatively, enforces available OEM load/speed minimums, ranks eligible products and returns JSON-safe output for an API or frontend.

It is designed to fail closed when verified fitment or safety-critical catalog data is malformed. A geometrically close tyre is **not** automatically manufacturer-approved: rim width, clearance, ABS/TCS behavior, construction restrictions, homologation and manufacturer documentation can still require separate verification.

## Quick start

No third-party runtime dependencies are required.

```bash
git clone https://github.com/enesakn16/moto-fitment-engine.git
cd moto-fitment-engine
python -m pip install .
```

Run a verified model/year query directly from the terminal:

```bash
moto-fitment Honda PCX125 2025 \
  --fitments data/verified_fitments.json \
  --catalog supplier_catalog.csv \
  --only-in-stock \
  --limit-per-axle 5
```

The command prints a JSON payload containing the matched vehicle and verified OEM fitment metadata plus ranked front/rear catalog candidates. Supplier rows that are malformed, ambiguous, duplicated or below available OEM load/speed minimums fail closed instead of being silently accepted.

For development, run the full test suite with:

```bash
python -m unittest discover -s tests -v
```

## What it does

- Resolves normalized make/model/year input against source-traceable fitment records.
- Requires HTTPS provenance and a non-future verification date for production-loaded fitments.
- Parses metric tyre sizes such as `110/70-14`, `150/70R17` and `150/70ZR17`.
- Parses unambiguous service descriptions such as `58W` and `63P` into load index + speed capability.
- Rejects ambiguous service descriptions instead of guessing.
- Imports UTF-8 supplier/catalog CSV data with row-level validation and duplicate-SKU detection.
- Calculates overall diameter, circumference and signed diameter delta.
- Rejects alternatives on a different rim diameter.
- Screens alternatives with configurable diameter and width tolerances.
- Enforces verified OEM load-index and speed minimums where the fitment record provides them.
- Supports stock quantity, price, product URL, SKU and brand metadata.
- Filters unknown/out-of-stock products when requested.
- Ranks already-eligible products by availability, geometry distance, price and stable tie-breakers.
- Produces exact-money, JSON-safe payloads suitable for API/UI consumers.
- Runs automated tests on Python 3.11 and 3.13 in GitHub Actions.

## Supplier catalog CSV

`catalog_import.py` is the fail-closed boundary between supplier data and the fitment engine.

Required columns:

```text
sku,brand,product_name,tyre_size
```

Optional columns:

```text
stock_quantity,price,product_url,service_description
```

Example:

```csv
sku,brand,product_name,tyre_size,stock_quantity,price,product_url,service_description
ANLAS-001,Anlas,Capra RD,120/70-17,12,2499.90,https://example.com/anlas-001,58W
ANLAS-002,Anlas,Capra R,160/60-17,5,3299.90,https://example.com/anlas-002,69W
```

Load it with:

```python
from catalog_import import load_catalog_csv

catalog = load_catalog_csv("supplier_catalog.csv")
```

Importer rules are intentionally strict:

- `sku`, `brand`, `product_name` and `tyre_size` must be non-empty.
- duplicate SKUs are rejected case-insensitively.
- stock must be a non-negative integer when supplied.
- price must be a positive finite decimal when supplied.
- an included `service_description` must be unambiguous and supported.
- malformed rows report their CSV row number instead of silently degrading safety metadata.

## End-to-end catalog example

For Python callers, `resolve_catalog_fitment_from_files()` is the simplest file-backed integration boundary. It combines verified OEM lookup, strict supplier ingestion, technical screening, OEM safety thresholds, inventory-aware ranking and JSON-safe serialization.

```python
from moto_fitment_service import resolve_catalog_fitment_from_files

payload = resolve_catalog_fitment_from_files(
    "Honda",
    "PCX125",
    2025,
    "supplier_catalog.csv",
    "data/verified_fitments.json",
    only_in_stock=True,
    limit_per_axle=5,
)
```

Money values are serialized as strings so `Decimal` precision is preserved. The response includes vehicle identity, OEM sizes, verification metadata, ranked front/rear candidates and an explicit safety disclaimer.

## Basic fitment lookup

For callers that only need OEM sizing and geometry helpers:

```python
from moto_fitment import (
    TyreSpec,
    diameter_delta_percent,
    find_fitment,
    is_reasonable_alternative,
    load_fitments_json,
)

records = load_fitments_json("data/verified_fitments.json")
fitment = find_fitment(
    "Honda",
    "PCX125",
    2025,
    records=records,
    require_verified=True,
)

print(fitment.front)
print(fitment.rear)

original = TyreSpec.parse("150/70-17")
alternative = TyreSpec.parse("150/60-17")

print(round(diameter_delta_percent(original, alternative), 2))
print(is_reasonable_alternative(original, alternative))
```

## Architecture

The code keeps ingestion, technical eligibility and commerce presentation separate:

1. **`moto_fitment.py` — verified fitment core**  
   Stores fitment records, validates external JSON, normalizes make/model/year input and calculates tyre geometry.

2. **`catalog_import.py` — supplier ingestion boundary**  
   Converts CSV-like supplier rows into validated `CatalogTyre` objects, parses supported service descriptions and rejects malformed or duplicate data before screening.

3. **`moto_alternatives.py` — catalog screening**  
   Screens front/rear catalog rows against OEM geometry and available OEM load/speed minimums. It decides technical eligibility only within the engine's deliberately limited rules.

4. **`moto_catalog_ranking.py` — presentation layer**  
   Orders already-screened candidates using explicit availability and geometry priorities, then serializes them for APIs/frontends. It never turns a commerce signal into a compatibility guarantee.

5. **`moto_fitment_service.py` — file/CLI orchestration**  
   Composes the strict loaders and ranking pipeline for terminal, API and back-office integrations without duplicating safety rules.

This separation is intentional: price or stock can change ordering, but they cannot make an otherwise ineligible tyre pass fitment screening.

## Verified dataset

[`data/verified_fitments.json`](data/verified_fitments.json) contains a deliberately limited set of Honda and Yamaha model-year records tied to official manufacturer pages or manufacturer-hosted specification documents.

Core provenance fields include:

| Field | Rule |
| --- | --- |
| `make` / `model` | Non-blank manufacturer identity |
| `year_from` / `year_to` | Valid model-year range |
| `front` / `rear` | Supported metric tyre size |
| `source_note` | Human-readable provenance |
| `source_url` | Absolute HTTPS source |
| `verified_on` | ISO date, not in the future |

Records can also carry verified front/rear minimum load index and speed capability. When those values exist, catalog screening applies them automatically; callers cannot weaken a stricter OEM minimum by passing a lower threshold.

Unknown fields, malformed tyre sizes, invalid year ranges, duplicate normalized ranges and JSON inputs larger than 1 MB are rejected.

The provenance validation is structural, not magical proof of correctness. An HTTPS source and verification date make a record traceable; production datasets still need human verification against manufacturer manuals, homologation documents or another authoritative source.

## Catalog presentation behavior

`rank_catalog_for_display()` receives only candidates that already passed technical screening. Ranking is lexicographic:

1. availability tier when availability preference is enabled,
2. absolute overall-diameter delta,
3. absolute section-width delta,
4. absolute aspect-ratio delta,
5. known lower price as a late tie-breaker,
6. stable brand/product/SKU ordering.

A cheaper product therefore cannot bypass geometry or OEM safety thresholds.

`resolve_catalog_fitment_payload()` requires verified fitment by default. `only_in_stock=True` removes zero and unknown inventory before presentation; `limit_per_axle` is applied after ranking.

## Safety boundary

A positive result means **engine-screened candidate**, not "manufacturer approved", "guaranteed compatible" or a replacement for professional fitment verification.

The engine currently checks tyre geometry and, where authoritative fitment data contains them, minimum load index and speed capability. It does **not** yet fully validate:

- manufacturer-approved rim width range,
- physical suspension/fender clearance,
- construction restrictions beyond the parsed tyre size,
- ABS/TCS calibration implications,
- homologation or market-specific approval,
- model variants that share a marketing name but differ mechanically.

Unknown, conflicting or ambiguous matches remain **no match**, not a guess.

## Tests and CI

Run the complete suite locally:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.11 and 3.13, verifies the installed package outside the source tree and smoke-tests the installed `moto-fitment` console entry point. Tests cover fitment validation, overlap/conflict handling, geometry screening, verified load/speed thresholds, service-description parsing, supplier CSV ingestion, commerce metadata, presentation ranking and orchestration behavior.

## Roadmap

- Expand verified model/year coverage using authoritative manufacturer sources.
- Add variant-aware aliases while preserving original manufacturer naming.
- Add manufacturer-approved rim-width rules and richer compatibility reasons.
- Add a stable HTTP service layer for marketplace and product-catalog integrations.
- Add controlled dataset conflict resolution when authoritative sources disagree.

## Status

**In development.** Verified lookup, strict JSON ingestion, supplier CSV ingestion, geometry screening, supported OEM load/speed enforcement, catalog evaluation, presentation ranking, JSON-safe orchestration and an installable CLI are test-backed and CI-backed. Dataset coverage and several safety-critical fitment attributes remain intentionally incomplete, so this repository should not be presented as a complete manufacturer-approved fitment catalog yet.
