"""Presentation ranking for geometry-screened motorcycle tyre catalog results.

This module intentionally sits *after* fitment screening. It never changes or
recomputes technical eligibility; it only orders already-screened catalog rows for
commerce presentation using explicit, lexicographic priorities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

from moto_alternatives import (
    CatalogAlternativeEvaluation,
    CatalogFitmentAlternativeResult,
)


class AvailabilityTier(IntEnum):
    """Presentation-only inventory state; lower values rank first."""

    IN_STOCK = 0
    UNKNOWN = 1
    OUT_OF_STOCK = 2


@dataclass(frozen=True)
class CatalogPresentationCandidate:
    """One screened catalog result plus transparent presentation metadata."""

    evaluation: CatalogAlternativeEvaluation
    availability: AvailabilityTier

    @property
    def sku(self) -> str:
        return self.evaluation.item.sku

    @property
    def availability_label(self) -> str:
        """Stable machine-readable inventory label for API/UI consumers."""
        return {
            AvailabilityTier.IN_STOCK: "in_stock",
            AvailabilityTier.UNKNOWN: "unknown",
            AvailabilityTier.OUT_OF_STOCK: "out_of_stock",
        }[self.availability]

    @property
    def ranking_reason(self) -> str:
        """Explain why this screened candidate is useful without claiming fitment safety.

        The text deliberately describes presentation facts only. Technical eligibility
        has already been decided by the fitment layer and is never restated as a safety
        or compatibility guarantee here.
        """
        evaluation = self.evaluation
        item = evaluation.item
        inventory = {
            AvailabilityTier.IN_STOCK: "stokta",
            AvailabilityTier.UNKNOWN: "stok bilgisi bilinmiyor",
            AvailabilityTier.OUT_OF_STOCK: "stokta değil",
        }[self.availability]
        price = f", fiyat {item.price:g}" if item.price is not None else ""
        return (
            f"{inventory}; çap farkı %{abs(evaluation.diameter_delta_percent):.2f}, "
            f"genişlik farkı {abs(evaluation.width_delta_mm):g} mm, "
            f"yanak oranı farkı {abs(evaluation.aspect_ratio_delta):g}{price}"
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe presentation payload for API/UI consumers.

        ``Decimal`` is intentionally serialized as a string so money remains exact
        and callers can pass the result directly to standard-library JSON encoders
        without silently introducing binary floating-point rounding.
        """
        item = self.evaluation.item
        return {
            "sku": item.sku,
            "brand": item.brand,
            "product_name": item.product_name,
            "tyre_size": str(item.tyre),
            "availability": self.availability_label,
            "stock_quantity": item.stock_quantity,
            "price": str(item.price) if item.price is not None else None,
            "product_url": item.product_url,
            "diameter_delta_percent": self.evaluation.diameter_delta_percent,
            "width_delta_mm": self.evaluation.width_delta_mm,
            "aspect_ratio_delta": self.evaluation.aspect_ratio_delta,
            "ranking_reason": self.ranking_reason,
        }


def availability_tier(evaluation: CatalogAlternativeEvaluation) -> AvailabilityTier:
    """Map inventory metadata to an explicit presentation tier."""
    quantity = evaluation.item.stock_quantity
    if quantity is None:
        return AvailabilityTier.UNKNOWN
    if quantity > 0:
        return AvailabilityTier.IN_STOCK
    return AvailabilityTier.OUT_OF_STOCK


def rank_catalog_for_display(
    candidates: Iterable[CatalogAlternativeEvaluation],
    *,
    prefer_available: bool = True,
) -> tuple[CatalogPresentationCandidate, ...]:
    """Order screened candidates without mixing commerce into fitment safety.

    Ranking is deliberately lexicographic rather than a blended numeric score:

    1. availability tier, when ``prefer_available`` is enabled;
    2. absolute overall-diameter delta;
    3. absolute section-width delta;
    4. absolute aspect-ratio delta;
    5. known lower price as a late presentation tie-breaker;
    6. stable brand/product/SKU ordering.

    Price can therefore never make a technically more distant tyre outrank a closer
    candidate within the same availability tier. Technical eligibility itself must
    already have been established by ``rank_catalog_alternatives`` or
    ``find_catalog_fitment_alternatives``.
    """
    wrapped = [
        CatalogPresentationCandidate(
            evaluation=candidate,
            availability=availability_tier(candidate),
        )
        for candidate in candidates
    ]

    def sort_key(candidate: CatalogPresentationCandidate) -> tuple[object, ...]:
        evaluation = candidate.evaluation
        item = evaluation.item
        availability_key = int(candidate.availability) if prefer_available else 0
        price_missing = item.price is None
        price_value = item.price if item.price is not None else 0
        return (
            availability_key,
            abs(evaluation.diameter_delta_percent),
            abs(evaluation.width_delta_mm),
            abs(evaluation.aspect_ratio_delta),
            price_missing,
            price_value,
            item.brand.casefold(),
            item.product_name.casefold(),
            item.sku.casefold(),
        )

    wrapped.sort(key=sort_key)
    return tuple(wrapped)


def build_catalog_fitment_payload(
    result: CatalogFitmentAlternativeResult,
    *,
    prefer_available: bool = True,
    limit_per_axle: int | None = None,
) -> dict[str, object]:
    """Build a JSON-safe vehicle fitment response for API and frontend consumers.

    The input must already come from the verified fitment + geometry screening layer.
    This function performs presentation ranking and serialization only; it does not
    upgrade geometry-screened alternatives into a compatibility or safety guarantee.

    ``limit_per_axle`` is applied only after ranking so callers can return a compact
    response without changing which candidates are considered technically eligible.
    """
    if limit_per_axle is not None and limit_per_axle <= 0:
        raise ValueError("limit_per_axle must be positive when provided")

    fitment = result.fitment
    front = rank_catalog_for_display(result.front, prefer_available=prefer_available)
    rear = rank_catalog_for_display(result.rear, prefer_available=prefer_available)

    if limit_per_axle is not None:
        front = front[:limit_per_axle]
        rear = rear[:limit_per_axle]

    return {
        "vehicle": {
            "make": fitment.make,
            "model": fitment.model,
            "year_from": fitment.year_from,
            "year_to": fitment.year_to,
        },
        "oem": {
            "front_tyre_size": str(fitment.front),
            "rear_tyre_size": str(fitment.rear),
        },
        "verification": {
            "is_verified": fitment.is_verified,
            "source_note": fitment.source_note,
            "source_url": fitment.source_url,
            "verified_on": fitment.verified_on,
        },
        "candidates": {
            "front": [candidate.as_dict() for candidate in front],
            "rear": [candidate.as_dict() for candidate in rear],
        },
        "disclaimer": (
            "Alternatifler geometri taramasından geçmiştir; yük/hız endeksi, jant "
            "genişliği, fiziksel açıklık, ABS/TC, homologasyon ve üretici kısıtları "
            "ayrıca doğrulanmalıdır."
        ),
    }
