"""Deterministic geometry screening for motorcycle tyre alternatives.

This module deliberately does not claim vehicle compatibility. It only ranks tyre
sizes that keep the same rim diameter and remain within configurable overall-
diameter and section-width tolerances. Final fitment still requires vehicle/OEM-
specific validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from moto_fitment import (
    Fitment,
    TyreSpec,
    diameter_delta_percent,
    find_fitment,
    is_reasonable_alternative,
)


@dataclass(frozen=True)
class AlternativeEvaluation:
    """A geometry-only evaluation of one candidate tyre size."""

    tyre: TyreSpec
    diameter_delta_percent: float
    width_delta_mm: int
    aspect_ratio_delta: int


@dataclass(frozen=True)
class CatalogTyre:
    """One sellable tyre catalog item with the geometry used for screening."""

    sku: str
    brand: str
    product_name: str
    tyre: TyreSpec

    def __post_init__(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku must not be empty")
        if not self.brand.strip():
            raise ValueError("brand must not be empty")
        if not self.product_name.strip():
            raise ValueError("product_name must not be empty")


@dataclass(frozen=True)
class CatalogAlternativeEvaluation:
    """Geometry screening result that preserves the sellable catalog identity."""

    item: CatalogTyre
    diameter_delta_percent: float
    width_delta_mm: int
    aspect_ratio_delta: int


@dataclass(frozen=True)
class FitmentAlternativeResult:
    """Verified OEM fitment plus geometry-screened front and rear candidates.

    The candidate lists are intentionally geometry-only. Their presence does not
    mean that load index, speed rating, rim-width approval, vehicle clearance,
    ABS/TC behavior, homologation, or manufacturer restrictions have been checked.
    """

    fitment: Fitment
    front: tuple[AlternativeEvaluation, ...]
    rear: tuple[AlternativeEvaluation, ...]


@dataclass(frozen=True)
class CatalogFitmentAlternativeResult:
    """Verified OEM fitment plus SKU-preserving front and rear catalog candidates."""

    fitment: Fitment
    front: tuple[CatalogAlternativeEvaluation, ...]
    rear: tuple[CatalogAlternativeEvaluation, ...]


def rank_geometry_alternatives(
    original: TyreSpec,
    candidates: Iterable[TyreSpec],
    *,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> tuple[AlternativeEvaluation, ...]:
    """Return deterministic geometry-screened candidates ordered by closeness.

    Exact duplicates of the OEM size are omitted, repeated candidate sizes are
    collapsed, different rim diameters are rejected, and candidates outside the
    requested overall-diameter or section-width tolerances are rejected.

    ``max_width_delta_mm`` is deliberately conservative. Similar rolling diameter
    alone is not enough to make a tyre a credible candidate: a much wider or
    narrower section may require a different rim width or create clearance issues.

    The result is a *screening list*, not a compatibility guarantee. Load index,
    speed rating, approved rim-width range, physical clearance, ABS/TC calibration,
    homologation and manufacturer restrictions remain outside this geometry-only
    calculation and must still be verified before a tyre is described as compatible.
    """
    if max_delta_percent < 0:
        raise ValueError("max_delta_percent must be non-negative")
    if max_width_delta_mm < 0:
        raise ValueError("max_width_delta_mm must be non-negative")

    seen: set[TyreSpec] = set()
    evaluations: list[AlternativeEvaluation] = []

    for candidate in candidates:
        if candidate == original or candidate in seen:
            continue
        seen.add(candidate)

        width_delta_mm = candidate.width_mm - original.width_mm
        if abs(width_delta_mm) > max_width_delta_mm:
            continue

        if not is_reasonable_alternative(
            original,
            candidate,
            max_delta_percent=max_delta_percent,
        ):
            continue

        evaluations.append(
            AlternativeEvaluation(
                tyre=candidate,
                diameter_delta_percent=diameter_delta_percent(original, candidate),
                width_delta_mm=width_delta_mm,
                aspect_ratio_delta=candidate.aspect_ratio - original.aspect_ratio,
            )
        )

    evaluations.sort(
        key=lambda item: (
            abs(item.diameter_delta_percent),
            abs(item.width_delta_mm),
            abs(item.aspect_ratio_delta),
            item.tyre.width_mm,
            item.tyre.aspect_ratio,
            item.tyre.rim_in,
        )
    )
    return tuple(evaluations)


def rank_catalog_alternatives(
    original: TyreSpec,
    catalog: Iterable[CatalogTyre],
    *,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> tuple[CatalogAlternativeEvaluation, ...]:
    """Screen sellable catalog rows while keeping SKU/product identity intact.

    Unlike :func:`rank_geometry_alternatives`, multiple SKUs with the same tyre size
    are preserved because they can represent different brands, patterns or stock
    records. Duplicate SKU values are rejected to prevent ambiguous commerce output.
    """
    if max_delta_percent < 0:
        raise ValueError("max_delta_percent must be non-negative")
    if max_width_delta_mm < 0:
        raise ValueError("max_width_delta_mm must be non-negative")

    seen_skus: set[str] = set()
    evaluations: list[CatalogAlternativeEvaluation] = []

    for item in catalog:
        sku_key = item.sku.strip().casefold()
        if sku_key in seen_skus:
            raise ValueError(f"duplicate sku in catalog: {item.sku}")
        seen_skus.add(sku_key)

        if item.tyre == original:
            continue

        width_delta_mm = item.tyre.width_mm - original.width_mm
        if abs(width_delta_mm) > max_width_delta_mm:
            continue
        if not is_reasonable_alternative(
            original,
            item.tyre,
            max_delta_percent=max_delta_percent,
        ):
            continue

        evaluations.append(
            CatalogAlternativeEvaluation(
                item=item,
                diameter_delta_percent=diameter_delta_percent(original, item.tyre),
                width_delta_mm=width_delta_mm,
                aspect_ratio_delta=item.tyre.aspect_ratio - original.aspect_ratio,
            )
        )

    evaluations.sort(
        key=lambda result: (
            abs(result.diameter_delta_percent),
            abs(result.width_delta_mm),
            abs(result.aspect_ratio_delta),
            result.item.brand.casefold(),
            result.item.product_name.casefold(),
            result.item.sku.casefold(),
        )
    )
    return tuple(evaluations)


def find_fitment_alternatives(
    make: str,
    model: str,
    year: int,
    candidates: Iterable[TyreSpec],
    records: Iterable[Fitment],
    *,
    require_verified: bool = True,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> FitmentAlternativeResult:
    """Resolve OEM fitment and screen one tyre catalog for both wheel positions.

    Production use is fail-closed by default: the matched fitment must have verified
    provenance. ``require_verified=False`` exists for explicit demo/test scenarios.
    The candidate iterable is materialized once so generators can be safely reused
    for front and rear screening.
    """
    fitment = find_fitment(
        make,
        model,
        year,
        records,
        require_verified=require_verified,
    )
    catalog = tuple(candidates)

    return FitmentAlternativeResult(
        fitment=fitment,
        front=rank_geometry_alternatives(
            fitment.front,
            catalog,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
        rear=rank_geometry_alternatives(
            fitment.rear,
            catalog,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
    )


def find_catalog_fitment_alternatives(
    make: str,
    model: str,
    year: int,
    catalog: Iterable[CatalogTyre],
    records: Iterable[Fitment],
    *,
    require_verified: bool = True,
    max_delta_percent: float = 3.0,
    max_width_delta_mm: int = 20,
) -> CatalogFitmentAlternativeResult:
    """Resolve a vehicle and return geometry-screened sellable SKU candidates."""
    fitment = find_fitment(
        make,
        model,
        year,
        records,
        require_verified=require_verified,
    )
    items = tuple(catalog)

    # Validate duplicate SKU identity once for the shared catalog before screening.
    sku_keys = [item.sku.strip().casefold() for item in items]
    if len(sku_keys) != len(set(sku_keys)):
        raise ValueError("duplicate sku in catalog")

    return CatalogFitmentAlternativeResult(
        fitment=fitment,
        front=rank_catalog_alternatives(
            fitment.front,
            items,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
        rear=rank_catalog_alternatives(
            fitment.rear,
            items,
            max_delta_percent=max_delta_percent,
            max_width_delta_mm=max_width_delta_mm,
        ),
    )
