from decimal import Decimal
import unittest

from moto_alternatives import CatalogTyre, find_catalog_fitment_alternatives, rank_catalog_alternatives
from moto_fitment import Fitment, TyreSpec


class CatalogCommerceTests(unittest.TestCase):
    def test_catalog_item_validates_commerce_metadata(self) -> None:
        item = CatalogTyre(
            "SKU-1",
            "Anlas",
            "Tournee",
            TyreSpec.parse("110/80-17"),
            stock_quantity=4,
            price=Decimal("2499.90"),
            product_url="https://example.com/products/sku-1",
        )

        self.assertTrue(item.is_in_stock)
        self.assertEqual(item.stock_quantity, 4)
        self.assertEqual(item.price, Decimal("2499.90"))

        with self.assertRaisesRegex(ValueError, "stock_quantity"):
            CatalogTyre("NEG", "Anlas", "Bad stock", TyreSpec.parse("110/80-17"), stock_quantity=-1)
        with self.assertRaisesRegex(ValueError, "price"):
            CatalogTyre("FREE", "Anlas", "Bad price", TyreSpec.parse("110/80-17"), price=Decimal("0"))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            CatalogTyre(
                "URL",
                "Anlas",
                "Bad URL",
                TyreSpec.parse("110/80-17"),
                product_url="http://example.com/products/url",
            )

    def test_only_in_stock_excludes_zero_and_unknown_inventory(self) -> None:
        original = TyreSpec.parse("120/70-17")
        catalog = (
            CatalogTyre("AVAILABLE", "IRC", "Available", TyreSpec.parse("110/80-17"), stock_quantity=3),
            CatalogTyre("ZERO", "Anlas", "Zero", TyreSpec.parse("110/80-17"), stock_quantity=0),
            CatalogTyre("UNKNOWN", "Pirelli", "Unknown", TyreSpec.parse("110/80-17")),
        )

        results = rank_catalog_alternatives(original, catalog, only_in_stock=True)

        self.assertEqual([result.item.sku for result in results], ["AVAILABLE"])

    def test_vehicle_lookup_propagates_stock_filter_to_both_wheels(self) -> None:
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
            CatalogTyre("FRONT-IN", "IRC", "Front", TyreSpec.parse("110/80-17"), stock_quantity=2),
            CatalogTyre("FRONT-OUT", "Anlas", "Front sold out", TyreSpec.parse("110/80-17"), stock_quantity=0),
            CatalogTyre("REAR-IN", "Anlas", "Rear", TyreSpec.parse("150/65-17"), stock_quantity=1),
        )

        result = find_catalog_fitment_alternatives(
            "Example",
            "Commerce 500",
            2026,
            catalog,
            (fitment,),
            only_in_stock=True,
        )

        self.assertEqual([candidate.item.sku for candidate in result.front], ["FRONT-IN"])
        self.assertEqual([candidate.item.sku for candidate in result.rear], ["REAR-IN"])


if __name__ == "__main__":
    unittest.main()
