"""Presentation ranking for geometry-screened motorcycle tyre catalog results.

This module intentionally sits *after* fitment screening. It never changes or
recomputes technical eligibility; it only orders already-screened catalog rows for
commerce presentation using explicit, lexicographic priorities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

from moto_alternatives import CatalogAlternativeEvaluation


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
