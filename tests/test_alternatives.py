import unittest

from moto_alternatives import rank_geometry_alternatives
from moto_fitment import TyreSpec


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


if __name__ == "__main__":
    unittest.main()
