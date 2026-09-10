import io
import json
import unittest
from pathlib import Path

from moto_fitment_service import resolve_catalog_fitment_from_files


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFIED_FITMENTS = REPO_ROOT / "data" / "verified_fitments.json"


class FileBackedFitmentServiceTests(unittest.TestCase):
    def test_verified_dataset_and_supplier_csv_are_screened_end_to_end(self) -> None:
        catalog = io.StringIO(
            "sku,brand,product_name,tyre_size,stock_quantity,price,service_description\n"
            "FRONT-SAFE,Example,PCX front alternative,120/60-14,4,2100.00,50P\n"
            "FRONT-LOW-LOAD,Example,PCX front under-rated,120/60-14,7,1900.00,49P\n"
            "REAR-SAFE,Example,PCX rear alternative,140/60-13,3,2400.00,63P\n"
            "REAR-LOW-LOAD,Example,PCX rear under-rated,140/60-13,5,2200.00,62P\n"
        )

        payload = resolve_catalog_fitment_from_files(
            "Honda",
            "PCX125",
            2025,
            catalog,
            VERIFIED_FITMENTS,
            only_in_stock=True,
        )
        decoded = json.loads(json.dumps(payload))

        self.assertEqual(decoded["vehicle"]["make"], "Honda")
        self.assertEqual(decoded["vehicle"]["model"], "PCX125")
        self.assertEqual(decoded["oem"]["front_tyre_size"], "110/70-14")
        self.assertEqual(decoded["oem"]["rear_tyre_size"], "130/70-13")
        self.assertTrue(decoded["verification"]["is_verified"])

        front_skus = [item["sku"] for item in decoded["candidates"]["front"]]
        rear_skus = [item["sku"] for item in decoded["candidates"]["rear"]]

        self.assertEqual(front_skus, ["FRONT-SAFE"])
        self.assertEqual(rear_skus, ["REAR-SAFE"])
        self.assertNotIn("FRONT-LOW-LOAD", front_skus)
        self.assertNotIn("REAR-LOW-LOAD", rear_skus)

    def test_invalid_supplier_safety_metadata_fails_before_matching(self) -> None:
        catalog = io.StringIO(
            "sku,brand,product_name,tyre_size,stock_quantity,price,service_description\n"
            "BAD,Example,Ambiguous rating,120/60-14,1,2000.00,50Z\n"
        )

        with self.assertRaisesRegex(ValueError, "invalid catalog row 2"):
            resolve_catalog_fitment_from_files(
                "Honda",
                "PCX125",
                2025,
                catalog,
                VERIFIED_FITMENTS,
            )


if __name__ == "__main__":
    unittest.main()
