from __future__ import annotations

from pathlib import Path

from moto_fitment_service import build_parser


def test_cli_parses_required_inputs_and_safe_defaults() -> None:
    args = build_parser().parse_args(
        [
            "Honda",
            "PCX125",
            "2024",
            "--catalog",
            "supplier.csv",
            "--fitments",
            "fitments.json",
        ]
    )

    assert args.make == "Honda"
    assert args.model == "PCX125"
    assert args.year == 2024
    assert args.catalog == Path("supplier.csv")
    assert args.fitments == Path("fitments.json")
    assert args.only_in_stock is False
    assert args.limit_per_axle is None
    assert args.max_delta_percent == 3.0
    assert args.max_width_delta_mm == 20
    assert args.no_prefer_available is False


def test_cli_accepts_inventory_and_ranking_controls() -> None:
    args = build_parser().parse_args(
        [
            "Yamaha",
            "NMAX125",
            "2025",
            "--catalog",
            "supplier.csv",
            "--fitments",
            "fitments.json",
            "--only-in-stock",
            "--limit-per-axle",
            "3",
            "--max-delta-percent",
            "2.5",
            "--max-width-delta-mm",
            "10",
            "--no-prefer-available",
        ]
    )

    assert args.only_in_stock is True
    assert args.limit_per_axle == 3
    assert args.max_delta_percent == 2.5
    assert args.max_width_delta_mm == 10
    assert args.no_prefer_available is True
