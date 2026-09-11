"""High-level file-backed orchestration for motorcycle tyre fitment lookup.

This module is the simplest integration boundary for CLI tools, APIs and back-office
software that have a verified fitment JSON file plus a supplier catalogue CSV file.
It composes the existing strict loaders and screening/ranking pipeline without
reimplementing safety or commerce rules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence, TextIO

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
    """Return a commerce-ready fitment payload from catalogue and fitment files."""
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moto-fitment",
        description="Resolve verified motorcycle tyre fitment against a supplier CSV.",
    )
    parser.add_argument("make", help="Motorcycle manufacturer, for example Honda")
    parser.add_argument("model", help="Motorcycle model, for example PCX125")
    parser.add_argument("year", type=int, help="Model year")
    parser.add_argument("--catalog", required=True, type=Path, help="Supplier catalogue CSV")
    parser.add_argument("--fitments", required=True, type=Path, help="Verified fitment JSON")
    parser.add_argument("--only-in-stock", action="store_true", help="Exclude out-of-stock catalogue items")
    parser.add_argument("--limit-per-axle", type=int, default=None, help="Maximum ranked results per axle")
    parser.add_argument("--max-delta-percent", type=float, default=3.0, help="Maximum rolling-diameter delta percent")
    parser.add_argument("--max-width-delta-mm", type=int, default=20, help="Maximum tyre width delta in millimetres")
    parser.add_argument("--no-prefer-available", action="store_true", help="Do not rank available items ahead of unavailable items")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = resolve_catalog_fitment_from_files(
        args.make,
        args.model,
        args.year,
        args.catalog,
        args.fitments,
        max_delta_percent=args.max_delta_percent,
        max_width_delta_mm=args.max_width_delta_mm,
        only_in_stock=args.only_in_stock,
        prefer_available=not args.no_prefer_available,
        limit_per_axle=args.limit_per_axle,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
