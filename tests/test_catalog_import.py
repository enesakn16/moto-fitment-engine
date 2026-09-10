import io
import unittest
from decimal import Decimal

from catalog_import import catalog_tyre_from_mapping, load_catalog_csv


class CatalogImportTests(unittest.TestCase):
    def test_mapping_normalizes_commerce_and_service_description(self) -> None:
        item = catalog_tyre_from_mapping(
            {
                "sku": " ANLAS-001 ",
                "brand": " Anlas ",
                "product_name": " Capra RD ",
                "tyre_size": "120/70-17",
                "stock_quantity": "12",
                "price": "2499.90",
                "product_url": "https://example.com/anlas-001",
                "service_description": "58W",
            }
        )

        self.assertEqual(item.sku, "ANLAS-001")
        self.assertEqual(str(item.tyre), "120/70-17")
        self.assertEqual(item.stock_quantity, 12)
        self.assertEqual(item.price, Decimal("2499.90"))
        self.assertEqual(item.load_index, 58)
        self.assertEqual(item.speed_kmh, 270)

    def test_invalid_service_description_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported or ambiguous"):
            catalog_tyre_from_mapping(
                {
                    "sku": "SKU-1",
                    "brand": "Example",
                    "product_name": "Example tyre",
                    "tyre_size": "120/70-17",
                    "service_description": "58Z",
                }
            )

    def test_csv_loader_reports_row_number_for_bad_safety_data(self) -> None:
        source = io.StringIO(
            "sku,brand,product_name,tyre_size,stock_quantity,price,service_description\n"
            "SAFE,Example,Safe tyre,120/70-17,3,1500.00,58W\n"
            "BAD,Example,Bad tyre,110/80-17,2,1400.00,58Z\n"
        )

        with self.assertRaisesRegex(ValueError, "invalid catalog row 3"):
            load_catalog_csv(source)

    def test_csv_loader_rejects_duplicate_sku_case_insensitively(self) -> None:
        source = io.StringIO(
            "sku,brand,product_name,tyre_size,service_description\n"
            "SKU-1,Example,First,120/70-17,58W\n"
            "sku-1,Example,Second,110/80-17,58W\n"
        )

        with self.assertRaisesRegex(ValueError, "duplicate sku sku-1"):
            load_catalog_csv(source)

    def test_csv_loader_allows_missing_optional_service_description(self) -> None:
        source = io.StringIO(
            "sku,brand,product_name,tyre_size,stock_quantity,price,product_url,service_description\n"
            "SKU-1,Example,Tyre,120/70-17,0,999.50,,\n"
        )

        (item,) = load_catalog_csv(source)
        self.assertEqual(item.stock_quantity, 0)
        self.assertEqual(item.price, Decimal("999.50"))
        self.assertIsNone(item.load_index)
        self.assertIsNone(item.speed_kmh)

    def test_csv_loader_requires_core_columns(self) -> None:
        source = io.StringIO("sku,brand,tyre_size\nSKU-1,Example,120/70-17\n")
        with self.assertRaisesRegex(ValueError, "missing required columns: product_name"):
            load_catalog_csv(source)


if __name__ == "__main__":
    unittest.main()
