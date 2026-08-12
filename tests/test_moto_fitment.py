import unittest

from moto_fitment import (
    Fitment,
    TyreSpec,
    diameter_delta_percent,
    find_fitment,
    is_reasonable_alternative,
)


class TyreSpecTests(unittest.TestCase):
    def test_parses_common_radial_and_zr_notation(self) -> None:
        self.assertEqual(TyreSpec.parse("150/70R17"), TyreSpec(150, 70, 17))
        self.assertEqual(TyreSpec.parse("180/55ZR17"), TyreSpec(180, 55, 17))

    def test_rejects_unsupported_size(self) -> None:
        with self.assertRaises(ValueError):
            TyreSpec.parse("3.50-10")

    def test_diameter_and_circumference_are_positive(self) -> None:
        tyre = TyreSpec.parse("150/70-17")
        self.assertAlmostEqual(tyre.diameter_mm, 641.8, places=1)
        self.assertGreater(tyre.circumference_mm, tyre.diameter_mm)


class FitmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = (
            Fitment(
                make="Honda",
                model="PCX 125",
                year_from=2021,
                year_to=2024,
                front=TyreSpec.parse("110/70-14"),
                rear=TyreSpec.parse("130/70-13"),
                source_note="fixture",
            ),
        )

    def test_find_fitment_normalizes_case_and_whitespace(self) -> None:
        result = find_fitment(" HONDA ", " pcx   125 ", 2023, self.records)
        self.assertEqual(result.model, "PCX 125")

    def test_year_range_is_inclusive(self) -> None:
        self.assertTrue(self.records[0].supports_year(2021))
        self.assertTrue(self.records[0].supports_year(2024))
        self.assertFalse(self.records[0].supports_year(2025))

    def test_unknown_fitment_fails_closed(self) -> None:
        with self.assertRaises(LookupError):
            find_fitment("Honda", "PCX 125", 2025, self.records)


class AlternativeGeometryTests(unittest.TestCase):
    def test_known_diameter_delta(self) -> None:
        original = TyreSpec.parse("150/70-17")
        alternative = TyreSpec.parse("150/60-17")
        self.assertAlmostEqual(diameter_delta_percent(original, alternative), -4.674, places=3)

    def test_rejects_different_rim_even_when_geometry_might_be_close(self) -> None:
        original = TyreSpec.parse("130/70-17")
        alternative = TyreSpec.parse("130/80-16")
        self.assertFalse(is_reasonable_alternative(original, alternative, max_delta_percent=10.0))

    def test_threshold_is_configurable_but_does_not_claim_vehicle_compatibility(self) -> None:
        original = TyreSpec.parse("150/70-17")
        alternative = TyreSpec.parse("140/70-17")
        self.assertTrue(is_reasonable_alternative(original, alternative, max_delta_percent=3.0))
        self.assertFalse(is_reasonable_alternative(original, alternative, max_delta_percent=1.0))


if __name__ == "__main__":
    unittest.main()
