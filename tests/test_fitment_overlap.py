import json
import tempfile
import unittest
from pathlib import Path

from moto_fitment import load_fitments_json


class OverlappingFitmentRangeTests(unittest.TestCase):
    def _write_json(self, payload) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "fitments.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    @staticmethod
    def _record(*, year_from: int, year_to: int, source_url: str) -> dict:
        return {
            "make": "Honda",
            "model": "PCX 125",
            "year_from": year_from,
            "year_to": year_to,
            "front": "110/70-14",
            "rear": "130/70-13",
            "source_note": "manufacturer fixture",
            "source_url": source_url,
            "verified_on": "2026-01-01",
        }

    def test_rejects_partially_overlapping_year_ranges(self) -> None:
        first = self._record(
            year_from=2021,
            year_to=2024,
            source_url="https://example.com/pcx-2021-2024",
        )
        overlapping = self._record(
            year_from=2024,
            year_to=2026,
            source_url="https://example.com/pcx-2024-2026",
        )

        with self.assertRaisesRegex(ValueError, "overlaps an existing fitment range"):
            load_fitments_json(self._write_json([first, overlapping]))

    def test_allows_adjacent_non_overlapping_year_ranges(self) -> None:
        first = self._record(
            year_from=2021,
            year_to=2024,
            source_url="https://example.com/pcx-2021-2024",
        )
        next_generation = self._record(
            year_from=2025,
            year_to=2026,
            source_url="https://example.com/pcx-2025-2026",
        )

        records = load_fitments_json(self._write_json([first, next_generation]))

        self.assertEqual(len(records), 2)
        self.assertEqual((records[0].year_from, records[0].year_to), (2021, 2024))
        self.assertEqual((records[1].year_from, records[1].year_to), (2025, 2026))


if __name__ == "__main__":
    unittest.main()
