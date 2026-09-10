"""High-level file-backed orchestration for motorcycle tyre fitment lookup.

This module is the simplest integration boundary for CLI tools, APIs and back-office
software that have a verified fitment JSON file plus a supplier catalogue CSV file.
It composes the existing strict loaders and screening/ranking pipeline without
reimplementing safety or commerce rules.
"""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from catalog_import import load_catalog_csv
from moto_catalog_ranking import resolve_catalog_fitment_payload
from moto_fitment import load_fitments_json


def resolve_catalog_fitment_from_files(
    make: str,
    model: str,
    year: int,
    catalog_csv: str | Path | TextIO,
    fitments_json: str | Path,
    *,
    require_verified: bool = True,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
    only_in_stock: bool = False,
    prefer_available: bool = True,
    limit_per_axle: int | None = None,
) -> dict[str, object]:
    """Return a commerce-ready fitment payload from catalogue and fitment files.

    Both inputs cross their existing fail-closed ingestion boundaries before matching:

    * ``fitments_json`` must pass provenance, schema, year-range and tyre-size checks.
    * ``catalog_csv`` must pass required-field, duplicate-SKU, price/stock and service
      description validation.

    OEM load/speed requirements stored in the verified fitment record are enforced by
    the lower-level screening pipeline automatically. This wrapper intentionally does
    not accept caller-supplied load/speed overrides so an integration cannot weaken or
    accidentally invent safety-critical thresholds at this high-level API boundary.
    """
    records = load_fitments_json(fitments_json)
    catalog = load_catalog_csv(catalog_csv)

    return resolve_catalog_fitment_payload(
        make,
        model,
        year,
        catalog,
        records,
        require_verified=require_verified,
        max_delta_percent=max_delta_percent,
        max_width_delta_mm=max_width_delta_mm,
        only_in_stock=only_in_stock,
        prefer_available=prefer_available,
        limit_per_axle=limit_per_axle,
    )
