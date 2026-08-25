# Moto Fitment Engine

Motorcycle tyre fitment lookup and geometry screening for commerce, catalog and workshop software.

[![Python CI](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml)

The project provides a small, testable core for resolving **make + model + year → front/rear tyre size** and for screening alternative tyre dimensions by overall-diameter difference.

> **Important:** a geometrically close tyre is not automatically safe or manufacturer-approved for a motorcycle. Rim width, load/speed rating, clearance, ABS/TCS calibration, homologation and manufacturer documentation still matter. The bundled fitment records are demo data and must not be treated as production fitment truth.

## Current capabilities

- Normalize make/model input and match by model year.
- Parse common metric tyre sizes such as `110/70-14`, `150/70R17` and `150/70ZR17`.
- Load strictly validated, source-traceable fitment records from JSON.
- Reject unknown fields, malformed tyre sizes, invalid year ranges, duplicate fitment ranges and oversized JSON inputs.
- Require HTTPS source provenance plus a non-future ISO verification date for production-loaded records.
- Fail closed when no verified fitment record is available.
- Calculate overall diameter and circumference.
- Calculate signed diameter difference between an OEM size and an alternative.
- Reject alternatives on a different rim diameter.
- Apply a configurable diameter-delta screen without claiming vehicle compatibility.
- Run automated tests on Python 3.11 and 3.13 in GitHub Actions.

## Quick start

No third-party runtime dependencies are required.

```bash
git clone https://github.com/enesakn16/moto-fitment-engine.git
cd moto-fitment-engine
python moto_fitment.py
```

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

## Example usage

```python
from moto_fitment import (
    TyreSpec,
    diameter_delta_percent,
    find_fitment,
    is_reasonable_alternative,
    load_fitments_json,
)

records = load_fitments_json("fitments.json")
fitment = find_fitment(
    "Honda",
    "PCX 125",
    2023,
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

## Verified JSON data contract

`load_fitments_json()` accepts a non-empty JSON array. Every record must contain exactly these fields:

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

Unknown fields are rejected. A normalized `make + model + year_from + year_to` range may appear only once. Files larger than 1 MB are rejected before parsing.

The loader's provenance check is intentionally **structural**, not a claim that a URL is authoritative. An HTTPS URL and verification date make a record traceable; they do not prove the underlying fitment is correct. Production datasets still need human verification against manufacturer manuals, homologation documents or another authoritative source.

## Architecture

The core is intentionally dependency-light and separates four concerns:

1. **Fitment records** — `Fitment` stores make, model, year range, tyre sizes and provenance.
2. **Data ingestion** — `load_fitments_json()` validates external production records before they reach lookup logic.
3. **Tyre geometry** — `TyreSpec` parses sizes and derives diameter/circumference.
4. **Decision helpers** — lookup and alternative-screening functions expose a small API that can later sit behind REST, CLI or catalog-import layers.

The bundled in-module dataset remains deliberately tiny and unverified. Production callers should load an external verified dataset and use `require_verified=True`.

## Data quality contract

For production use, preserve at least:

- make, model and normalized aliases,
- year and variant boundaries,
- front and rear OEM sizes,
- load and speed ratings where authoritative data provides them,
- source URL or document identifier,
- verification date and verification notes,
- reviewer or approval state in the dataset-management process.

Unknown, conflicting or ambiguous matches should remain **no match**, not be guessed. A future variant/alias layer should also preserve the original manufacturer naming rather than silently rewriting source data.

## Alternative tyre screening

`is_reasonable_alternative()` is intentionally conservative and limited. It currently checks:

- the same rim diameter, and
- absolute overall-diameter difference within a configurable threshold (default: 3%).

It does **not** verify rim-width compatibility, physical clearance, load index, speed symbol, tyre construction, ABS/TCS behavior or manufacturer approval. Applications using this engine should present the result as a geometry screen, not a fitment guarantee.

## Roadmap

- Verified, source-traceable motorcycle fitment dataset maintained outside demo code.
- Variant-aware matching for model names and model-year changes.
- Load/speed rating and rim-width rules.
- Structured compatibility reasons instead of a boolean-only alternative check.
- Conflict detection for overlapping year ranges and competing authoritative sources.
- Stable service/API layer for marketplace and product-catalog integrations.

## Status

**In development.** The geometry, strict JSON ingestion and lookup core are tested and CI-backed. The repository intentionally does not ship a production motorcycle fitment dataset until authoritative source records can be verified and maintained.