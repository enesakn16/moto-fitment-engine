import unittest
from pathlib import Path

from moto_alternatives import (
    CatalogTyre,
    find_catalog_fitment_alternatives,
    rank_catalog_alternatives,
)
from moto_fitment import Fitment, TyreSpec, load_fitments_json


class SafetyRatingScreeningTests(unittest.TestCase):
    def test_catalog_screening_fails_closed_for_missing_or_insufficient_ratings(self) -> None:
        original = TyreSpec.parse("120/70-17")
        catalog = (
            CatalogTyre(
                "SAFE",
                "Example",
                "Meets both minimums",
                TyreSpec.parse("110/80-17"),
                load_index=58,
                speed_kmh=210,
            ),
            CatalogTyre(
                "MISSING-LOAD",
                "Example",
                "Missing load index",
                TyreSpec.parse("110/80-17"),
                speed_kmh=210,
            ),
            CatalogTyre(
                "MISSING-SPEED",
                "Example",
                "Missing speed rating",
                TyreSpec.parse("110/80-17"),
                load_index=58,
            ),
            CatalogTyre(
                "LOW-LOAD",
                "Example",
                "Insufficient load index",
                TyreSpec.parse("110/80-17"),
                load_index=57,
                speed_kmh=210,
            ),
            CatalogTyre(
                "LOW-SPEED",
                "Example",
                "Insufficient speed rating",
                TyreSpec.parse("110/80-17"),
                load_index=58,
                speed_kmh=209,
            ),
        )

        results = rank_catalog_alternatives(
            original,
            catalog,
            minimum_load_index=58,
            minimum_speed_kmh=210,
        )

        self.assertEqual([result.item.sku for result in results], ["SAFE"])

    def test_rating_thresholds_are_inclusive(self) -> None:
        results = rank_catalog_alternatives(
            TyreSpec.parse("120/70-17"),
            (
                CatalogTyre(
                    "BOUNDARY",
                    "Example",
                    "Exactly at safety minimum",
                    TyreSpec.parse("110/80-17"),
                    load_index=58,
                    speed_kmh=210,
                ),
            ),
            minimum_load_index=58,
            minimum_speed_kmh=210,
        )

        self.assertEqual([result.item.sku for result in results], ["BOUNDARY"])

    def test_vehicle_screening_applies_front_and_rear_minimums_independently(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Safety 500",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Verified test fixture",
            source_url="https://example.com/oem-fitment",
            verified_on="2026-09-01",
        )
        catalog = (
            CatalogTyre(
                "FRONT-SAFE",
                "Example",
                "Front candidate",
                TyreSpec.parse("110/80-17"),
                load_index=58,
                speed_kmh=210,
            ),
            CatalogTyre(
                "FRONT-TOO-LOW",
                "Example",
                "Front candidate below front minimum",
                TyreSpec.parse("110/80-17"),
                load_index=57,
                speed_kmh=210,
            ),
            CatalogTyre(
                "REAR-SAFE",
                "Example",
                "Rear candidate",
                TyreSpec.parse("150/65-17"),
                load_index=69,
                speed_kmh=210,
            ),
            CatalogTyre(
                "REAR-FRONT-ONLY",
                "Example",
                "Rear geometry but only front-level load rating",
                TyreSpec.parse("150/65-17"),
                load_index=58,
                speed_kmh=210,
            ),
        )

        result = find_catalog_fitment_alternatives(
            "Example",
            "Safety 500",
            2026,
            catalog,
            (fitment,),
            front_minimum_load_index=58,
            rear_minimum_load_index=69,
            front_minimum_speed_kmh=210,
            rear_minimum_speed_kmh=210,
        )

        self.assertEqual([item.item.sku for item in result.front], ["FRONT-SAFE"])
        self.assertEqual([item.item.sku for item in result.rear], ["REAR-SAFE"])

    def test_verified_fitment_safety_requirements_are_applied_automatically(self) -> None:
        fitment = Fitment(
            make="Example",
            model="OEM Safety 700",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Verified OEM safety fixture",
            source_url="https://example.com/oem-safety-fitment",
            verified_on="2026-09-01",
            front_minimum_load_index=58,
            rear_minimum_load_index=69,
            front_minimum_speed_kmh=210,
            rear_minimum_speed_kmh=240,
        )
        catalog = (
            CatalogTyre(
                "FRONT-OEM-SAFE",
                "Example",
                "Front meets OEM minimum",
                TyreSpec.parse("110/80-17"),
                load_index=58,
                speed_kmh=210,
            ),
            CatalogTyre(
                "FRONT-BELOW-OEM",
                "Example",
                "Front below OEM load minimum",
                TyreSpec.parse("110/80-17"),
                load_index=57,
                speed_kmh=210,
            ),
            CatalogTyre(
                "REAR-OEM-SAFE",
                "Example",
                "Rear meets OEM minimum",
                TyreSpec.parse("150/65-17"),
                load_index=69,
                speed_kmh=240,
            ),
            CatalogTyre(
                "REAR-BELOW-OEM",
                "Example",
                "Rear below OEM speed minimum",
                TyreSpec.parse("150/65-17"),
                load_index=69,
                speed_kmh=210,
            ),
        )

        result = find_catalog_fitment_alternatives(
            "Example",
            "OEM Safety 700",
            2026,
            catalog,
            (fitment,),
            front_minimum_load_index=40,
            rear_minimum_load_index=40,
            front_minimum_speed_kmh=120,
            rear_minimum_speed_kmh=120,
        )

        self.assertEqual([item.item.sku for item in result.front], ["FRONT-OEM-SAFE"])
        self.assertEqual([item.item.sku for item in result.rear], ["REAR-OEM-SAFE"])

    def test_verified_dataset_safety_thresholds_are_enforced_end_to_end(self) -> None:
        records = load_fitments_json(
            Path(__file__).resolve().parents[1] / "data" / "verified_fitments.json"
        )
        catalog = (
            CatalogTyre(
                "PCX-FRONT-SAFE",
                "Example",
                "PCX front alternative at OEM safety minimum",
                TyreSpec.parse("120/60-14"),
                load_index=50,
                speed_kmh=150,
            ),
            CatalogTyre(
                "PCX-FRONT-LOW-LOAD",
                "Example",
                "PCX front alternative below OEM load minimum",
                TyreSpec.parse("120/60-14"),
                load_index=49,
                speed_kmh=150,
            ),
            CatalogTyre(
                "PCX-REAR-SAFE",
                "Example",
                "PCX rear alternative at OEM safety minimum",
                TyreSpec.parse("140/60-13"),
                load_index=63,
                speed_kmh=150,
            ),
            CatalogTyre(
                "PCX-REAR-LOW-SPEED",
                "Example",
                "PCX rear alternative below OEM speed minimum",
                TyreSpec.parse("140/60-13"),
                load_index=63,
                speed_kmh=149,
            ),
        )

        result = find_catalog_fitment_alternatives(
            "Honda",
            "PCX125",
            2025,
            catalog,
            records,
        )

        self.assertEqual([item.item.sku for item in result.front], ["PCX-FRONT-SAFE"])
        self.assertEqual([item.item.sku for item in result.rear], ["PCX-REAR-SAFE"])

    def test_invalid_safety_thresholds_are_rejected(self) -> None:
        for invalid in (0, -1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "minimum_load_index"):
                    rank_catalog_alternatives(
                        TyreSpec.parse("120/70-17"),
                        (),
                        minimum_load_index=invalid,
                    )


if __name__ == "__main__":
    unittest.main()
