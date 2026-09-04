# Moto Fitment Engine

Motorcycle tyre fitment lookup, verified OEM sizing, alternative geometry screening and commerce-ready catalog ranking for marketplaces, parts catalogs and workshop software.

[![Python CI](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml)

The engine resolves **make + model + year → verified front/rear OEM tyre sizes**, screens catalog alternatives conservatively, ranks eligible products for presentation, and can return a JSON-safe payload for an API or frontend.

It is designed to fail closed when verified fitment data is unavailable. A geometrically close tyre is **not** automatically manufacturer-approved: load/speed rating, rim width, clearance, ABS/TCS behavior, homologation and manufacturer documentation still require separate verification.

## What it does

- Normalizes make/model input and resolves model-year fitment records.
- Loads strict, source-traceable fitment data from JSON.
- Requires HTTPS provenance and a non-future verification date for production-loaded records.
- Parses metric tyre sizes such as `110/70-14`, `150/70R17` and `150/70ZR17`.
- Calculates overall diameter, circumference and signed diameter delta.
- Rejects alternatives on a different rim diameter.
- Screens alternatives with configurable diameter and width tolerances.
- Evaluates front and rear catalog candidates separately.
- Supports stock quantity, price, product URL, SKU and brand metadata.
- Can filter out unknown/out-of-stock products before presentation.
- Ranks already-eligible products by availability, geometry distance, price and stable tie-breakers.
- Produces exact-money, JSON-safe payloads suitable for API/UI consumers.
- Runs automated tests on Python 3.11 and 3.13 in GitHub Actions.

## Quick start

No third-party runtime dependencies are required.

```bash
git clone https://github.com/enesakn16/moto-fitment-engine.git
cd moto-fitment-engine
python -m unittest discover -s tests -v
```

## End-to-end catalog example

The public orchestration boundary is `resolve_catalog_fitment_payload()`. It combines verified OEM lookup, geometry screening, inventory-aware presentation ranking and serialization without weakening the safety rules in the lower layers.

```python
import json
from decimal import Decimal

from moto_alternatives import CatalogTyre
from moto_catalog_ranking import resolve_catalog_fitment_payload
from moto_fitment import TyreSpec, load_fitments_json

records = load_fitments_json("data/verified_fitments.json")

catalog = [
    CatalogTyre(
        sku="PCX-FRONT-001",
        tyre=TyreSpec.parse("110/70-14"),
        brand="Example",
        product_name="Example Scooter Front",
        stock_quantity=8,
        price=Decimal("2499.90"),
        product_url="https://example.com/products/pcx-front-001",
    ),
    CatalogTyre(
        sku="PCX-REAR-001",
        tyre=TyreSpec.parse("130/70-13"),
        brand="Example",
        product_name="Example Scooter Rear",
        stock_quantity=5,
        price=Decimal("2899.90"),
        product_url="https://example.com/products/pcx-rear-001",
    ),
]

payload = resolve_catalog_fitment_payload(
    "Honda",
    "PCX125",
    2025,
    catalog,
    records,
    require_verified=True,
    only_in_stock=True,
    limit_per_axle=5,
)

print(json.dumps(payload, ensure_ascii=False, indent=2))
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

The code keeps technical eligibility and commerce presentation separate:

1. **`moto_fitment.py` — verified fitment core**  
   Stores fitment records, validates external JSON, normalizes make/model/year input and calculates tyre geometry.

2. **`moto_alternatives.py` — catalog screening**  
   Screens front/rear catalog rows against OEM geometry and applies optional inventory filtering. It decides technical eligibility only within the engine's deliberately limited geometry rules.

3. **`moto_catalog_ranking.py` — presentation layer**  
   Orders already-screened candidates using explicit availability and geometry priorities, then serializes them for APIs/frontends. It never turns a commerce signal into a compatibility guarantee.

This separation is intentional: price or stock can change ordering, but they cannot make an otherwise ineligible tyre pass fitment screening.

## Verified dataset

[`data/verified_fitments.json`](data/verified_fitments.json) contains a deliberately limited set of Honda and Yamaha model-year records tied to official manufacturer pages or manufacturer-hosted specification documents.

Each record carries:

| Field | Type | Rule |
| --- | --- | --- |
| `make` | string | Non-blank manufacturer name |
| `model` | string | Non-blank model name |
| `year_from` | integer | `>= 1900` |
| `year_to` | integer | `>= year_from`, no more than two years in the future |
| `front` | string | Supported metric tyre size |
| `rear` | string | Supported metric tyre size |
| `source_note` | string | Human-readable provenance note |
| `source_url` | string | Absolute HTTPS URL |
| `verified_on` | string | ISO `YYYY-MM-DD`, not in the future |

Unknown fields, malformed tyre sizes, invalid year ranges, duplicate normalized ranges and JSON inputs larger than 1 MB are rejected.

The provenance validation is structural, not magical proof of correctness. An HTTPS source and verification date make a record traceable; production datasets still need human verification against manufacturer manuals, homologation documents or another authoritative source.

## Catalog presentation behavior

`rank_catalog_for_display()` receives only candidates that already passed geometry screening. Ranking is lexicographic:

1. availability tier when availability preference is enabled,
2. absolute overall-diameter delta,
3. absolute section-width delta,
4. absolute aspect-ratio delta,
5. known lower price as a late tie-breaker,
6. stable brand/product/SKU ordering.

That means a cheaper product cannot bypass or override the technical screening layer.

`resolve_catalog_fitment_payload()` requires verified fitment by default. `only_in_stock=True` removes zero and unknown inventory before presentation; `limit_per_axle` is applied after ranking.

## Safety boundary

The alternative engine currently checks a deliberately small subset of fitment constraints. A positive result means **geometry-screened candidate**, not "safe", "approved" or "guaranteed compatible".

The engine does not yet fully validate:

- manufacturer-approved rim width range,
- load index,
- speed symbol,
- construction restrictions,
- physical suspension/fender clearance,
- ABS/TCS calibration implications,
- homologation or market-specific approval,
- model variants that share a marketing name but differ mechanically.

Unknown, conflicting or ambiguous matches should remain **no match**, not be guessed.

## Tests and CI

Run the complete test suite locally:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.11 and 3.13. Tests cover fitment validation, overlap/conflict handling, geometry screening, catalog commerce metadata, presentation ranking and orchestration behavior.

## Roadmap

- Expand verified model/year coverage using authoritative manufacturer sources.
- Add variant-aware aliases while preserving original manufacturer naming.
- Add load/speed rating and rim-width rules.
- Return richer structured compatibility reasons for each rejected or accepted candidate.
- Detect competing authoritative fitment sources and require explicit resolution.
- Add a stable HTTP service layer for marketplace and product-catalog integrations.

## Status

**In development.** The lookup, strict JSON ingestion, geometry screening, catalog evaluation, presentation ranking and JSON-safe orchestration layers are test-backed and CI-backed. Dataset coverage and safety-critical compatibility attributes are still intentionally incomplete, so this repository should not be presented as a complete manufacturer-approved fitment catalog yet.
