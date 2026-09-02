from decimal import Decimal
import json
import unittest

from moto_alternatives import CatalogTyre, rank_catalog_alternatives
from moto_catalog_ranking import AvailabilityTier, rank_catalog_for_display
from moto_fitment import TyreSpec


class CatalogPresentationRankingTests(unittest.TestCase):
    def test_in_stock_items_rank_before_unknown_and_sold_out(self) -> None:
        original = TyreSpec.parse("120/70-17")
        screened = rank_catalog_alternatives(
            original,
            (
                CatalogTyre("OUT", "Brand", "Sold out", TyreSpec.parse("110/80-17"), stock_quantity=0),
                CatalogTyre("UNKNOWN", "Brand", "Unknown", TyreSpec.parse("110/80-17")),
                CatalogTyre("IN", "Brand", "Available", TyreSpec.parse("110/80-17"), stock_quantity=2),
            ),
        )

        ranked = rank_catalog_for_display(screened)

        self.assertEqual([candidate.sku for candidate in ranked], ["IN", "UNKNOWN", "OUT"])
        self.assertEqual(
            [candidate.availability for candidate in ranked],
            [AvailabilityTier.IN_STOCK, AvailabilityTier.UNKNOWN, AvailabilityTier.OUT_OF_STOCK],
        )

    def test_price_never_beats_better_geometry_within_same_availability(self) -> None:
        original = TyreSpec.parse("120/70-17")
        screened = rank_catalog_alternatives(
            original,
            (
                CatalogTyre(
                    "CHEAP-FARTHER",
                    "Brand",
                    "Cheap farther",
                    TyreSpec.parse("110/80-17"),
                    stock_quantity=1,
                    price=Decimal("1000"),
                ),
                CatalogTyre(
                    "EXPENSIVE-CLOSER",
                    "Brand",
                    "Expensive closer",
                    TyreSpec.parse("130/65-17"),
                    stock_quantity=1,
                    price=Decimal("5000"),
                ),
            ),
        )

        ranked = rank_catalog_for_display(screened)

        self.assertEqual(ranked[0].sku, "EXPENSIVE-CLOSER")
        self.assertLess(
            abs(ranked[0].evaluation.diameter_delta_percent),
            abs(ranked[1].evaluation.diameter_delta_percent),
        )

    def test_price_is_only_a_late_tie_breaker(self) -> None:
        original = TyreSpec.parse("120/70-17")
        screened = rank_catalog_alternatives(
            original,
            (
                CatalogTyre(
                    "HIGH",
                    "Brand B",
                    "Same size",
                    TyreSpec.parse("110/80-17"),
                    stock_quantity=1,
                    price=Decimal("3000"),
                ),
                CatalogTyre(
                    "LOW",
                    "Brand A",
                    "Same size",
                    TyreSpec.parse("110/80-17"),
                    stock_quantity=1,
                    price=Decimal("2000"),
                ),
            ),
        )

        ranked = rank_catalog_for_display(screened)

        self.assertEqual([candidate.sku for candidate in ranked], ["LOW", "HIGH"])

    def test_presentation_payload_is_json_safe_and_preserves_money_exactly(self) -> None:
        original = TyreSpec.parse("120/70-17")
        screened = rank_catalog_alternatives(
            original,
            (
                CatalogTyre(
                    "SKU-JSON",
                    "Brand",
                    "JSON candidate",
                    TyreSpec.parse("110/80-17"),
                    stock_quantity=3,
                    price=Decimal("2499.90"),
                    product_url="https://example.com/products/sku-json",
                ),
            ),
        )

        payload = rank_catalog_for_display(screened)[0].as_dict()
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)

        self.assertEqual(decoded["price"], "2499.90")
        self.assertEqual(decoded["availability"], "in_stock")
        self.assertEqual(decoded["stock_quantity"], 3)
        self.assertEqual(decoded["product_url"], "https://example.com/products/sku-json")


if __name__ == "__main__":
    unittest.main()
