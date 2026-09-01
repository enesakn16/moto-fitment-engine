import unittest

from moto_alternatives import find_fitment_alternatives, rank_geometry_alternatives
from moto_fitment import Fitment, TyreSpec


class GeometryAlternativeRankingTests(unittest.TestCase):
    def test_filters_and_ranks_candidates_deterministically(self) -> None:
        original = TyreSpec.parse("150/70-17")
        candidates = (
            TyreSpec.parse("150/70-17"),  # exact OEM size: not an alternative
            TyreSpec.parse("160/60-17"),
            TyreSpec.parse("140/70-17"),
            TyreSpec.parse("150/65-17"),
            TyreSpec.parse("140/70-17"),  # duplicate candidate
            TyreSpec.parse("130/80-16"),  # wrong rim
            TyreSpec.parse("150/60-17"),  # outside default 3% diameter tolerance
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
            TyreSpec.parse("130/80-17"),  # exactly -20 mm: allowed by width bound
            TyreSpec.parse("120/90-17"),  # -30 mm: rejected despite similar diameter
            TyreSpec.parse("170/60-17"),  # exactly +20 mm: allowed by width bound
            TyreSpec.parse("180/55-17"),  # +30 mm: rejected despite similar diameter
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
            ["150/65-17", "170/55-17"],
        )

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


if __name__ == "__main__":
    unittest.main()
