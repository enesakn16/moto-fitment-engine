"""Fail-closed import helpers for supplier/catalog tyre data.

The core fitment engine accepts normalized ``CatalogTyre`` objects. This module is the
boundary for CSV-like supplier rows: it parses commercial fields and converts a tyre
service description (for example ``58W``) into numeric load/speed metadata before the
row can enter safety screening.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Mapping, TextIO

from moto_alternatives import CatalogTyre, parse_service_description
from moto_fitment import TyreSpec

_REQUIRED_FIELDS = ("sku", "brand", "product_name", "tyre_size")


def _required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required and must be non-empty text")
    return value.strip()


def _optional_text(row: Mapping[str, object], field: str) -> str | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text when provided")
    value = value.strip()
    return value or None


def _optional_non_negative_int(row: Mapping[str, object], field: str) -> int | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer when provided")
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer when provided") from exc
    if str(parsed) != str(value).strip() or parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer when provided")
    return parsed


def _optional_positive_decimal(row: Mapping[str, object], field: str) -> Decimal | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a positive decimal when provided") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be a positive decimal when provided")
    return parsed


def catalog_tyre_from_mapping(row: Mapping[str, object]) -> CatalogTyre:
    """Normalize one supplier/catalog mapping into a validated ``CatalogTyre``.

    Required columns are ``sku``, ``brand``, ``product_name`` and ``tyre_size``.
    Optional commercial columns are ``stock_quantity``, ``price`` and ``product_url``.
    ``service_description`` is optional, but when present it must be parseable; invalid
    safety metadata is rejected rather than silently dropped.
    """
    values = {field: _required_text(row, field) for field in _REQUIRED_FIELDS}
    service_description = _optional_text(row, "service_description")
    load_index: int | None = None
    speed_kmh: int | None = None
    if service_description is not None:
        load_index, speed_kmh = parse_service_description(service_description)

    return CatalogTyre(
        sku=values["sku"],
        brand=values["brand"],
        product_name=values["product_name"],
        tyre=TyreSpec.parse(values["tyre_size"]),
        stock_quantity=_optional_non_negative_int(row, "stock_quantity"),
        price=_optional_positive_decimal(row, "price"),
        product_url=_optional_text(row, "product_url"),
        load_index=load_index,
        speed_kmh=speed_kmh,
    )


def load_catalog_csv(source: str | Path | TextIO) -> tuple[CatalogTyre, ...]:
    """Load a UTF-8 CSV catalog and fail with row context on malformed data."""
    should_close = False
    if isinstance(source, (str, Path)):
        handle: TextIO = Path(source).open("r", encoding="utf-8-sig", newline="")
        should_close = True
    else:
        handle = source

    try:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("catalog CSV must include a header row")
        missing = [field for field in _REQUIRED_FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError(f"catalog CSV missing required columns: {', '.join(missing)}")

        items: list[CatalogTyre] = []
        seen_skus: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            try:
                item = catalog_tyre_from_mapping(row)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid catalog row {row_number}: {exc}") from exc

            sku_key = item.sku.casefold()
            if sku_key in seen_skus:
                raise ValueError(f"invalid catalog row {row_number}: duplicate sku {item.sku}")
            seen_skus.add(sku_key)
            items.append(item)
        return tuple(items)
    finally:
        if should_close:
            handle.close()
