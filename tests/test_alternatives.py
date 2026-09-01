import unittest

from moto_alternatives import (
    CatalogTyre,
    find_catalog_fitment_alternatives,
    find_fitment_alternatives,
    rank_catalog_alternatives,
    rank_geometry_alternatives,
)
from moto_fitment import Fitment, TyreSpec


class GeometryAlternativeRankingTests(unittest.TestCase):
    def test_filters_and_ranks_candidates_deterministically(self) -> None:
        original = TyreSpec.parse("150/70-17")
        candidates = (
            TyreSpec.parse("150/70-17"),
            TyreSpec.parse("160/60-17"),
            TyreSpec.parse("140/70-17"),
            TyreSpec.parse("150/65-17"),
            TyreSpec.parse("140/70-17"),
            TyreSpec.parse("130/80-16"),
            TyreSpec.parse("150/60-17"),
        )

        results = rank_geometry_alternatives(original, candidates)

        self.assertEqual(
            [str(item.tyre) for item in results],
            ["140/70-17", "150/65-17", "160/60-17"],
        )
        self.assertTrue(all(abs(item.diameter_delta_percent) <= 3.0 for item in results))
        self.assertEqual(results[0].width_delta_mm, -10)
        self.assertEqual(results[1].aspect_ratio_delta, -5)

    def test_custom_tolerance_can_narrow_results(self) -> None:
        original = TyreSpec.parse("150/70-17")
        candidates = (
            TyreSpec.parse("140/70-17"),
            TyreSpec.parse("150/65-17"),
        )

        results = rank_geometry_alternatives(
            original,
            candidates,
            max_delta_percent=2.2,
        )

        self.assertEqual([str(item.tyre) for item in results], ["140/70-17"])

    def test_width_tolerance_is_inclusive_and_rejects_wider_candidates(self) -> None:
        original = TyreSpec.parse("150/70-17")
        candidates = (
            TyreSpec.parse("130/80-17"),
            TyreSpec.parse("120/90-17"),
            TyreSpec.parse("170/60-17"),
            TyreSpec.parse("180/55-17"),
        )

        results = rank_geometry_alternatives(
            original,
            candidates,
            max_delta_percent=5.0,
            max_width_delta_mm=20,
        )

        self.assertEqual(
            [str(item.tyre) for item in results],
            ["130/80-17", "170/60-17"],
        )
        self.assertTrue(all(abs(item.width_delta_mm) <= 20 for item in results))

    def test_negative_tolerance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be non-negative"):
            rank_geometry_alternatives(
                TyreSpec.parse("150/70-17"),
                (),
                max_delta_percent=-0.1,
            )

        with self.assertRaisesRegex(ValueError, "must be non-negative"):
            rank_geometry_alternatives(
                TyreSpec.parse("150/70-17"),
                (),
                max_width_delta_mm=-1,
            )

    def test_vehicle_lookup_screens_catalog_for_both_wheels(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Tourer 500",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Verified test fixture",
            source_url="https://example.com/oem-fitment",
            verified_on="2026-01-01",
        )
        catalog = (
            TyreSpec.parse(value)
            for value in (
                "110/80-17",
                "120/65-17",
                "150/65-17",
                "170/55-17",
                "180/55-17",
                "120/70-17",
                "160/60-17",
            )
        )

        result = find_fitment_alternatives(
            " example ",
            "Tourer 500",
            2026,
            catalog,
            (fitment,),
        )

        self.assertIs(result.fitment, fitment)
        self.assertEqual(
            [str(item.tyre) for item in result.front],
            ["110/80-17", "120/65-17"],
        )
        self.assertLess(
            abs(result.front[0].diameter_delta_percent),
            abs(result.front[1].diameter_delta_percent),
        )
        self.assertEqual(
            [str(item.tyre) for item in result.rear],
            ["150/65-17", "170/55-17", "180/55-17"],
        )
        self.assertTrue(all(abs(item.width_delta_mm) <= 20 for item in result.rear))

    def test_vehicle_lookup_requires_verified_provenance_by_default(self) -> None:
        unverified = Fitment(
            make="Example",
            model="Demo 125",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("100/80-17"),
            rear=TyreSpec.parse("120/70-17"),
            source_note="Demo only",
        )

        with self.assertRaisesRegex(LookupError, "no verified provenance"):
            find_fitment_alternatives(
                "Example",
                "Demo 125",
                2026,
                (),
                (unverified,),
            )

    def test_catalog_screening_preserves_sellable_sku_identity(self) -> None:
        original = TyreSpec.parse("120/70-17")
        catalog = (
            CatalogTyre("SKU-IRC-01", "IRC", "Road Winner", TyreSpec.parse("110/80-17")),
            CatalogTyre("SKU-ANLAS-02", "Anlas", "Tournee", TyreSpec.parse("110/80-17")),
            CatalogTyre("SKU-OEM", "Example", "OEM size", TyreSpec.parse("120/70-17")),
            CatalogTyre("SKU-WRONG-RIM", "Example", "Wrong rim", TyreSpec.parse("120/70-16")),
        )

        results = rank_catalog_alternatives(original, catalog)

        self.assertEqual(
            [result.item.sku for result in results],
            ["SKU-ANLAS-02", "SKU-IRC-01"],
        )
        self.assertTrue(all(str(result.item.tyre) == "110/80-17" for result in results))

    def test_catalog_lookup_returns_front_and_rear_skus(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Commerce 500",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Verified test fixture",
            source_url="https://example.com/oem-fitment",
            verified_on="2026-01-01",
        )
        catalog = (
            CatalogTyre("FRONT-1", "IRC", "Front Candidate", TyreSpec.parse("110/80-17")),
            CatalogTyre("REAR-1", "Anlas", "Rear Candidate", TyreSpec.parse("150/65-17")),
        )

        result = find_catalog_fitment_alternatives(
            "Example",
            "Commerce 500",
            2026,
            catalog,
            (fitment,),
        )

        self.assertEqual([item.item.sku for item in result.front], ["FRONT-1"])
        self.assertEqual([item.item.sku for item in result.rear], ["REAR-1"])

    def test_catalog_rejects_duplicate_skus(self) -> None:
        catalog = (
            CatalogTyre("SKU-1", "IRC", "One", TyreSpec.parse("110/80-17")),
            CatalogTyre(" sku-1 ", "Anlas", "Two", TyreSpec.parse("110/80-17")),
        )

        with self.assertRaisesRegex(ValueError, "duplicate sku"):
            rank_catalog_alternatives(TyreSpec.parse("120/70-17"), catalog)


if __name__ == "__main__":
    unittest.main()
