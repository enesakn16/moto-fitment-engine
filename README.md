# Moto Fitment Engine

Motorcycle tyre fitment lookup and geometry screening for commerce, catalog and workshop software.

[![Python CI](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/enesakn16/moto-fitment-engine/actions/workflows/ci.yml)

The project provides a small, testable core for resolving **make + model + year → front/rear tyre size** and for screening alternative tyre dimensions by overall-diameter difference.

> **Important:** a geometrically close tyre is not automatically safe or manufacturer-approved for a motorcycle. Rim width, load/speed rating, clearance, ABS/TCS calibration, homologation and manufacturer documentation still matter. The bundled fitment records are demo data and must not be treated as production fitment truth.

## Current capabilities

- Normalize make/model input and match by model year.
- Parse common metric tyre sizes such as `110/70-14`, `150/70R17` and `150/70ZR17`.
- Calculate overall diameter and circumference.
- Calculate signed diameter difference between an OEM size and an alternative.
- Reject alternatives on a different rim diameter.
- Apply a configurable diameter-delta screen without claiming vehicle compatibility.
- Fail closed when no verified fitment record is available.
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
)

fitment = find_fitment("Honda", "PCX 125", 2023)
print(fitment.front)  # 110/70-14
print(fitment.rear)   # 130/70-13

original = TyreSpec.parse("150/70-17")
alternative = TyreSpec.parse("150/60-17")

print(round(diameter_delta_percent(original, alternative), 2))
print(is_reasonable_alternative(original, alternative))
```

## Architecture

The core is intentionally dependency-light and separates three concerns:

1. **Fitment records** — `Fitment` stores make, model, year range and front/rear sizes.
2. **Tyre geometry** — `TyreSpec` parses sizes and derives diameter/circumference.
3. **Decision helpers** — lookup and alternative-screening functions expose a small API that can later sit behind REST, CLI or catalog-import layers.

The current in-module dataset is deliberately tiny. The next production step is to move verified fitment records into a versioned data source such as CSV, JSON or SQLite while preserving provenance per record.

## Data quality contract

Production fitment data should be accepted only when it has traceable provenance. A future record format should preserve at least:

- make, model and normalized aliases,
- year/variant range,
- front and rear OEM sizes,
- load and speed ratings where available,
- source URL/document identifier,
- source type and verification date,
- reviewer/verification state.

Unknown or ambiguous matches should remain **no match**, not be guessed.

## Alternative tyre screening

`is_reasonable_alternative()` is intentionally conservative and limited. It currently checks:

- the same rim diameter, and
- absolute overall-diameter difference within a configurable threshold (default: 3%).

It does **not** verify rim-width compatibility, physical clearance, load index, speed symbol, tyre construction, ABS/TCS behavior or manufacturer approval. Applications using this engine should present the result as a geometry screen, not a fitment guarantee.

## Roadmap

- Verified, source-traceable motorcycle fitment dataset.
- Variant-aware matching for model names and model-year changes.
- Load/speed rating and rim-width rules.
- Structured compatibility reasons instead of a boolean-only alternative check.
- CSV/JSON import validation and duplicate/conflict detection.
- Stable service/API layer for marketplace and product-catalog integrations.

## Status

**In development.** The geometry and lookup core are tested and CI-backed; the included motorcycle records remain demonstrative until a verified production dataset is introduced.
