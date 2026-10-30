"""CLI argument contract coverage for the project's unittest-based CI."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import unittest

from moto_fitment_service import build_parser


class CliParserTests(unittest.TestCase):
    def test_parses_required_inputs_and_safe_defaults(self) -> None:
        args = build_parser().parse_args(
            ["Honda", "PCX125", "2024", "--catalog", "supplier.csv", "--fitments", "fitments.json"]
        )

        self.assertEqual(args.make, "Honda")
        self.assertEqual(args.model, "PCX125")
        self.assertEqual(args.year, 2024)
        self.assertEqual(args.catalog, Path("supplier.csv"))
        self.assertEqual(args.fitments, Path("fitments.json"))
        self.assertFalse(args.only_in_stock)
        self.assertIsNone(args.limit_per_axle)
        self.assertEqual(args.max_delta_percent, 3.0)
        self.assertEqual(args.max_width_delta_mm, 20)
        self.assertFalse(args.no_prefer_available)

    def test_accepts_inventory_and_ranking_controls(self) -> None:
        args = build_parser().parse_args(
            [
                "Yamaha", "NMAX125", "2025",
                "--catalog", "supplier.csv", "--fitments", "fitments.json",
                "--only-in-stock", "--limit-per-axle", "3",
                "--max-delta-percent", "2.5", "--max-width-delta-mm", "10",
                "--no-prefer-available",
            ]
        )

        self.assertTrue(args.only_in_stock)
        self.assertEqual(args.limit_per_axle, 3)
        self.assertEqual(args.max_delta_percent, 2.5)
        self.assertEqual(args.max_width_delta_mm, 10)
        self.assertTrue(args.no_prefer_available)

    def test_rejects_missing_required_source_paths(self) -> None:
        cases = (
            ["Honda", "PCX125", "2024"],
            ["Honda", "PCX125", "2024", "--catalog", "supplier.csv"],
            ["Honda", "PCX125", "2024", "--fitments", "fitments.json"],
        )
        for argv in cases:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    build_parser().parse_args(argv)
                self.assertEqual(raised.exception.code, 2)

    def test_rejects_non_integer_model_year(self) -> None:
        argv = [
            "Honda", "PCX125", "twenty-twenty-four",
            "--catalog", "supplier.csv", "--fitments", "fitments.json",
        ]
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                build_parser().parse_args(argv)
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
