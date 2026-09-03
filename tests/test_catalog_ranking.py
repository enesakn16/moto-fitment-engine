from decimal import Decimal
import json
import unittest

from moto_alternatives import (
    CatalogFitmentAlternativeResult,
    CatalogTyre,
    rank_catalog_alternatives,
)
from moto_catalog_ranking import (
    AvailabilityTier,
    build_catalog_fitment_payload,
    rank_catalog_for_display,
    resolve_catalog_fitment_payload,
)
from moto_fitment import Fitment, TyreSpec


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

    def test_vehicle_payload_is_json_safe_ranked_and_limited_per_axle(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Roadster 500",
            year_from=2024,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Manufacturer fitment table",
            source_url="https://example.com/fitment",
            verified_on="2026-08-01",
        )
        front = rank_catalog_alternatives(
            fitment.front,
            (
                CatalogTyre(
                    "F-UNKNOWN",
                    "Brand",
                    "Front unknown",
                    TyreSpec.parse("130/65-17"),
                    price=Decimal("2100.00"),
                ),
                CatalogTyre(
                    "F-IN",
                    "Brand",
                    "Front available",
                    TyreSpec.parse("110/80-17"),
                    stock_quantity=4,
                    price=Decimal("2500.00"),
                ),
            ),
        )
        rear = rank_catalog_alternatives(
            fitment.rear,
            (
                CatalogTyre(
                    "R-IN",
                    "Brand",
                    "Rear available",
                    TyreSpec.parse("150/65-17"),
                    stock_quantity=2,
                    price=Decimal("3200.50"),
                ),
            ),
        )
        result = CatalogFitmentAlternativeResult(fitment=fitment, front=front, rear=rear)

        payload = build_catalog_fitment_payload(result, limit_per_axle=1)
        decoded = json.loads(json.dumps(payload))

        self.assertEqual(decoded["vehicle"], {
            "make": "Example",
            "model": "Roadster 500",
            "year_from": 2024,
            "year_to": 2026,
        })
        self.assertEqual(decoded["oem"]["front_tyre_size"], "120/70-17")
        self.assertEqual(decoded["oem"]["rear_tyre_size"], "160/60-17")
        self.assertTrue(decoded["verification"]["is_verified"])
        self.assertEqual(decoded["verification"]["source_url"], "https://example.com/fitment")
        self.assertEqual([item["sku"] for item in decoded["candidates"]["front"]], ["F-IN"])
        self.assertEqual([item["sku"] for item in decoded["candidates"]["rear"]], ["R-IN"])
        self.assertEqual(decoded["candidates"]["rear"][0]["price"], "3200.50")
        self.assertIn("ayrıca doğrulanmalıdır", decoded["disclaimer"])

    def test_vehicle_payload_rejects_non_positive_limit(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Roadster 500",
            year_from=2024,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Manufacturer fitment table",
            source_url="https://example.com/fitment",
            verified_on="2026-08-01",
        )
        result = CatalogFitmentAlternativeResult(fitment=fitment, front=(), rear=())

        with self.assertRaisesRegex(ValueError, "limit_per_axle must be positive"):
            build_catalog_fitment_payload(result, limit_per_axle=0)

    def test_resolve_service_matches_vehicle_filters_stock_and_limits_results(self) -> None:
        fitment = Fitment(
            make="Example",
            model="Roadster 500",
            year_from=2024,
            year_to=2026,
            front=TyreSpec.parse("120/70-17"),
            rear=TyreSpec.parse("160/60-17"),
            source_note="Manufacturer fitment table",
            source_url="https://example.com/fitment",
            verified_on="2026-08-01",
        )
        catalog = (
            CatalogTyre(
                "F-IN",
                "Brand",
                "Front available",
                TyreSpec.parse("130/65-17"),
                stock_quantity=2,
                price=Decimal("2300.00"),
            ),
            CatalogTyre(
                "F-UNKNOWN",
                "Brand",
                "Front unknown",
                TyreSpec.parse("110/80-17"),
                price=Decimal("2100.00"),
            ),
            CatalogTyre(
                "R-IN",
                "Brand",
                "Rear available",
                TyreSpec.parse("150/65-17"),
                stock_quantity=3,
                price=Decimal("3200.50"),
            ),
            CatalogTyre(
                "R-OUT",
                "Brand",
                "Rear sold out",
                TyreSpec.parse("170/55-17"),
                stock_quantity=0,
                price=Decimal("3000.00"),
            ),
        )

        payload = resolve_catalog_fitment_payload(
            " example ",
            "roadster   500",
            2025,
            catalog,
            (fitment,),
            only_in_stock=True,
            limit_per_axle=1,
        )
        decoded = json.loads(json.dumps(payload))

        self.assertEqual(decoded["vehicle"]["make"], "Example")
        self.assertEqual(decoded["vehicle"]["model"], "Roadster 500")
        self.assertEqual([item["sku"] for item in decoded["candidates"]["front"]], ["F-IN"])
        self.assertEqual([item["sku"] for item in decoded["candidates"]["rear"]], ["R-IN"])
        self.assertEqual(decoded["candidates"]["rear"][0]["price"], "3200.50")

    def test_resolve_service_fails_closed_for_unverified_fitment_by_default(self) -> None:
        unverified = Fitment(
            make="Example",
            model="Prototype 400",
            year_from=2026,
            year_to=2026,
            front=TyreSpec.parse("110/70-17"),
            rear=TyreSpec.parse("140/70-17"),
        )

        with self.assertRaises(ValueError):
            resolve_catalog_fitment_payload(
                "Example",
                "Prototype 400",
                2026,
                (),
                (unverified,),
            )


if __name__ == "__main__":
    unittest.main()
